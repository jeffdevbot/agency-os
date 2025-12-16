-- =====================================================================
-- MIGRATION: Command Center Ghost Profiles + Secure Profile Updates
-- Purpose:
--   1) Remove privilege escalation (users updating their own profiles)
--   2) Enable Ghost Profiles by decoupling profiles.id from auth.users.id
--   3) Add auth_user_id + email constraints needed for merge-on-login
--   4) Update signup trigger to merge Ghost Profiles into canonical profile
-- Notes:
--   - Preserves existing app behavior: logged-in users still use profiles.id = auth.uid()
--   - Ghost Profiles are temporary rows with auth_user_id = NULL and a random UUID id
-- =====================================================================

-- ---------------------------------------------------------------------
-- 0. Harden RLS on profiles (prevent privilege escalation)
-- ---------------------------------------------------------------------
drop policy if exists "Users can update own profile" on public.profiles;

drop policy if exists "Admins can update any profile" on public.profiles;
drop policy if exists "Only admins can update profiles" on public.profiles;
create policy "Only admins can update profiles"
  on public.profiles for update
  to authenticated
  using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid() and p.is_admin = true
    )
  )
  with check (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid() and p.is_admin = true
    )
  );

-- ---------------------------------------------------------------------
-- 1. Enable Ghost Profiles: drop FK tying profiles.id → auth.users(id)
-- ---------------------------------------------------------------------
alter table public.profiles
  drop constraint if exists profiles_id_fkey;

-- ---------------------------------------------------------------------
-- 2. Add auth_user_id + backfill for existing users
-- ---------------------------------------------------------------------
alter table public.profiles
  add column if not exists auth_user_id uuid references auth.users(id) on delete set null;

-- Existing rows historically used profiles.id = auth.users.id.
update public.profiles
set auth_user_id = id
where auth_user_id is null;

-- Backfill email from auth.users when missing.
update public.profiles p
set email = au.email
from auth.users au
where p.id = au.id
  and p.email is null;

do $$
begin
  if exists (select 1 from public.profiles where email is null) then
    raise exception 'profiles.email contains NULLs; backfill required before setting NOT NULL';
  end if;
end;
$$;

alter table public.profiles
  alter column email set not null;

-- ---------------------------------------------------------------------
-- 3. Uniqueness + performance indexes
-- ---------------------------------------------------------------------
-- Allow Ghost and canonical rows to temporarily share an email during merge-on-login.
create unique index if not exists idx_profiles_email_lower_unique_ghost
  on public.profiles (lower(email))
  where auth_user_id is null;

create unique index if not exists idx_profiles_email_lower_unique_auth
  on public.profiles (lower(email))
  where auth_user_id is not null;

create unique index if not exists idx_profiles_auth_user_id_unique
  on public.profiles(auth_user_id)
  where auth_user_id is not null;

-- ---------------------------------------------------------------------
-- 4. Update signup trigger function to support Ghost merge-on-login
-- ---------------------------------------------------------------------
create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path to 'public'
as $$
declare
  ghost_profile_id uuid;
begin
  -- Find a Ghost Profile for this email (case-insensitive).
  select id into ghost_profile_id
  from public.profiles
  where lower(email) = lower(new.email)
    and auth_user_id is null
  limit 1;

  -- Ensure canonical profile exists for the logged-in user (id = auth uid).
  insert into public.profiles (id, auth_user_id, email, full_name, display_name, avatar_url, is_admin, role)
  values (
    new.id,
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name'),
    coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name'),
    new.raw_user_meta_data->>'avatar_url',
    false,
    'member'::team_role
  )
  on conflict (id) do update
    set auth_user_id = excluded.auth_user_id,
        email = coalesce(public.profiles.email, excluded.email),
        full_name = coalesce(public.profiles.full_name, excluded.full_name),
        display_name = coalesce(public.profiles.display_name, excluded.display_name),
        avatar_url = coalesce(public.profiles.avatar_url, excluded.avatar_url),
        updated_at = now();

  -- If a Ghost Profile exists, merge it into the canonical profile.
  if ghost_profile_id is not null and ghost_profile_id != new.id then
    -- Remap known foreign keys to the canonical profile id.
    update public.client_assignments
      set profile_id = new.id
      where profile_id = ghost_profile_id;

    update public.client_assignments
      set assigned_by = new.id
      where assigned_by = ghost_profile_id;

    -- Copy any missing metadata from Ghost → canonical profile.
    update public.profiles canonical
    set
      full_name = coalesce(canonical.full_name, ghost.full_name),
      display_name = coalesce(canonical.display_name, ghost.display_name),
      avatar_url = coalesce(canonical.avatar_url, ghost.avatar_url),
      is_admin = canonical.is_admin or ghost.is_admin,
      role = case
        when canonical.role = 'member'::team_role and ghost.role = 'admin'::team_role then ghost.role
        else canonical.role
      end,
      updated_at = now()
    from public.profiles ghost
    where canonical.id = new.id
      and ghost.id = ghost_profile_id;

    -- Delete Ghost Profile (email uniqueness restored).
    delete from public.profiles
      where id = ghost_profile_id;
  end if;

  return new;
end;
$$;
