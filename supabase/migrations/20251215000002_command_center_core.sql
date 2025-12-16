-- =====================================================================
-- MIGRATION: Command Center Core Tables (Roles, Brands, Assignments)
-- Purpose:
--   - Create `agency_roles` + seed default role slugs
--   - Create `brands` (per `docs/07_command_center_schema_api.md`)
--   - Evolve `client_assignments` into role assignments (brand + role scope)
--   - Add Command Center profile fields (allowed_tools, employment/bench status, mappings)
--   - Remove obsolete Team Central invite table/trigger (team_members_pending)
--   - Add bench_status sync trigger on assignment changes
--   - Update `handle_new_auth_user()` to remap `team_member_id` on ghost merge
-- =====================================================================

-- ---------------------------------------------------------------------
-- 0) Shared helper: updated_at
-- ---------------------------------------------------------------------
create or replace function public.update_updated_at_column()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------
-- 1) Profiles: Command Center fields
-- ---------------------------------------------------------------------
alter table public.profiles
  add column if not exists allowed_tools text[] not null default '{}'::text[],
  add column if not exists employment_status text not null default 'active',
  add column if not exists bench_status text not null default 'available',
  add column if not exists clickup_user_id text,
  add column if not exists slack_user_id text;

-- Allow admins to create Ghost Profiles (insert) in Command Center.
drop policy if exists "Only admins can insert profiles" on public.profiles;
create policy "Only admins can insert profiles"
  on public.profiles for insert
  to authenticated
  with check (exists (select 1 from public.profiles where id = auth.uid() and is_admin = true));

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'profiles_employment_status_check'
      and conrelid = 'public.profiles'::regclass
  ) then
    alter table public.profiles
      add constraint profiles_employment_status_check
      check (employment_status in ('active', 'inactive', 'contractor'));
  end if;

  if not exists (
    select 1 from pg_constraint
    where conname = 'profiles_bench_status_check'
      and conrelid = 'public.profiles'::regclass
  ) then
    alter table public.profiles
      add constraint profiles_bench_status_check
      check (bench_status in ('available', 'assigned', 'unavailable'));
  end if;
end;
$$;

create index if not exists idx_profiles_allowed_tools
  on public.profiles using gin(allowed_tools);

create index if not exists idx_profiles_clickup_user_id
  on public.profiles (clickup_user_id)
  where clickup_user_id is not null;

-- ---------------------------------------------------------------------
-- 2) Remove Team Central invite system (replaced by Ghost Profiles)
-- ---------------------------------------------------------------------
drop trigger if exists on_auth_user_created_link_invite on public.profiles;
drop function if exists public.handle_new_user_from_invite();
drop table if exists public.team_members_pending;

-- ---------------------------------------------------------------------
-- 3) Roles
-- ---------------------------------------------------------------------
create table if not exists public.agency_roles (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null,
  name text not null,
  created_at timestamptz not null default now()
);

insert into public.agency_roles (slug, name)
values
  ('strategy_director', 'Strategy Director'),
  ('brand_manager', 'Brand Manager'),
  ('catalog_strategist', 'Catalog Strategist'),
  ('catalog_specialist', 'Catalog Specialist'),
  ('ppc_strategist', 'PPC Strategist'),
  ('ppc_specialist', 'PPC Specialist'),
  ('report_specialist', 'Report Specialist')
on conflict (slug) do nothing;

alter table public.agency_roles enable row level security;

drop policy if exists "Authenticated users can view roles" on public.agency_roles;
create policy "Authenticated users can view roles"
  on public.agency_roles for select
  to authenticated
  using (true);

drop policy if exists "Only admins can manage roles" on public.agency_roles;
create policy "Only admins can manage roles"
  on public.agency_roles for all
  to authenticated
  using (exists (select 1 from public.profiles where id = auth.uid() and is_admin = true))
  with check (exists (select 1 from public.profiles where id = auth.uid() and is_admin = true));

-- ---------------------------------------------------------------------
-- 4) Brands
-- ---------------------------------------------------------------------
create table if not exists public.brands (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.agency_clients(id) on delete restrict,
  name text not null,
  product_keywords text[] not null default '{}'::text[],
  amazon_marketplaces text[] not null default '{}'::text[],
  clickup_space_id text,
  clickup_list_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_brands_client
  on public.brands(client_id);

create index if not exists idx_brands_clickup_space
  on public.brands(clickup_space_id)
  where clickup_space_id is not null;

create index if not exists idx_brands_clickup_list
  on public.brands(clickup_list_id)
  where clickup_list_id is not null;

create index if not exists idx_brands_keywords
  on public.brands using gin(product_keywords);

drop trigger if exists update_brands_updated_at on public.brands;
create trigger update_brands_updated_at
  before update on public.brands
  for each row execute function public.update_updated_at_column();

alter table public.brands enable row level security;

drop policy if exists "Authenticated users can view brands" on public.brands;
create policy "Authenticated users can view brands"
  on public.brands for select
  to authenticated
  using (true);

drop policy if exists "Only admins can manage brands" on public.brands;
create policy "Only admins can manage brands"
  on public.brands for all
  to authenticated
  using (exists (select 1 from public.profiles where id = auth.uid() and is_admin = true))
  with check (exists (select 1 from public.profiles where id = auth.uid() and is_admin = true));

-- ---------------------------------------------------------------------
-- 5) Client assignments v2 (role + optional brand scope)
-- ---------------------------------------------------------------------
do $$
begin
  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public'
      and table_name = 'client_assignments'
      and column_name = 'profile_id'
  ) and not exists (
    select 1 from information_schema.columns
    where table_schema = 'public'
      and table_name = 'client_assignments'
      and column_name = 'team_member_id'
  ) then
    alter table public.client_assignments rename column profile_id to team_member_id;
  end if;
end;
$$;

alter table public.client_assignments
  add column if not exists brand_id uuid references public.brands(id),
  add column if not exists role_id uuid references public.agency_roles(id) on delete restrict;

-- Replace membership semantics: existing rows get a default role.
do $$
declare
  default_role_id uuid;
begin
  select id into default_role_id
  from public.agency_roles
  where slug = 'brand_manager'
  limit 1;

  if default_role_id is null then
    raise exception 'agency_roles missing seed role: brand_manager';
  end if;

  update public.client_assignments
  set role_id = default_role_id
  where role_id is null;
end;
$$;

alter table public.client_assignments
  alter column role_id set not null;

-- Ensure correct FK behavior for team member id (cascade deletes).
alter table public.client_assignments
  drop constraint if exists client_assignments_profile_id_fkey;

alter table public.client_assignments
  drop constraint if exists client_assignments_team_member_id_fkey;

alter table public.client_assignments
  add constraint client_assignments_team_member_id_fkey
  foreign key (team_member_id) references public.profiles(id) on delete cascade;

-- Drop old uniqueness constraint and indexes.
alter table public.client_assignments
  drop constraint if exists unique_client_profile;

drop index if exists idx_client_assignments_composite;
drop index if exists idx_client_assignments_profile;
drop index if exists idx_client_assignments_client;

-- Indexes for common query patterns.
create index if not exists idx_assignments_client
  on public.client_assignments(client_id);

create index if not exists idx_assignments_member
  on public.client_assignments(team_member_id);

create index if not exists idx_assignments_brand
  on public.client_assignments(brand_id);

create index if not exists idx_assignments_role
  on public.client_assignments(role_id);

create index if not exists idx_assignments_member_client
  on public.client_assignments(team_member_id, client_id);

create index if not exists idx_assignments_client_role
  on public.client_assignments(client_id, role_id);

-- Enforce uniqueness correctly with nullable brand_id (partial unique indexes).
create unique index if not exists idx_assignments_unique_brand_scope
  on public.client_assignments (client_id, brand_id, team_member_id, role_id)
  where brand_id is not null;

create unique index if not exists idx_assignments_unique_client_scope
  on public.client_assignments (client_id, team_member_id, role_id)
  where brand_id is null;

-- RLS: admin-only manage; authenticated read.
alter table public.client_assignments enable row level security;

drop policy if exists "Users can view their own assignments" on public.client_assignments;
drop policy if exists "Admins can create assignments" on public.client_assignments;
drop policy if exists "Admins can delete assignments" on public.client_assignments;

drop policy if exists "Authenticated users can view assignments" on public.client_assignments;
create policy "Authenticated users can view assignments"
  on public.client_assignments for select
  to authenticated
  using (true);

drop policy if exists "Only admins can manage assignments" on public.client_assignments;
create policy "Only admins can manage assignments"
  on public.client_assignments for all
  to authenticated
  using (exists (select 1 from public.profiles where id = auth.uid() and is_admin = true))
  with check (exists (select 1 from public.profiles where id = auth.uid() and is_admin = true));

-- ---------------------------------------------------------------------
-- 6) bench_status sync trigger (insert/delete)
-- ---------------------------------------------------------------------
create or replace function public.sync_bench_status()
returns trigger
language plpgsql
security definer
set search_path to 'public'
as $$
declare
  member_id uuid;
  has_assignments boolean;
  desired_status text;
begin
  if TG_OP = 'DELETE' then
    member_id := OLD.team_member_id;
  else
    member_id := NEW.team_member_id;
  end if;

  select exists(
    select 1 from public.client_assignments
    where team_member_id = member_id
  ) into has_assignments;

  desired_status := case when has_assignments then 'assigned' else 'available' end;

  update public.profiles
  set bench_status = desired_status,
      updated_at = now()
  where id = member_id
    and bench_status is distinct from desired_status;

  if TG_OP = 'DELETE' then
    return OLD;
  end if;
  return NEW;
end;
$$;

drop trigger if exists sync_bench_status_on_assignment_change on public.client_assignments;
create trigger sync_bench_status_on_assignment_change
  after insert or delete on public.client_assignments
  for each row execute function public.sync_bench_status();

-- Backfill bench_status after introducing the derived column.
update public.profiles p
set bench_status = case
  when exists (select 1 from public.client_assignments ca where ca.team_member_id = p.id) then 'assigned'
  else 'available'
end
where p.bench_status is distinct from case
  when exists (select 1 from public.client_assignments ca where ca.team_member_id = p.id) then 'assigned'
  else 'available'
end;

-- ---------------------------------------------------------------------
-- 7) Update auth signup/link trigger function (ghost merge)
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
  select id into ghost_profile_id
  from public.profiles
  where lower(email) = lower(new.email)
    and auth_user_id is null
  limit 1;

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

  if ghost_profile_id is not null and ghost_profile_id != new.id then
    update public.client_assignments
      set team_member_id = new.id
      where team_member_id = ghost_profile_id;

    update public.client_assignments
      set assigned_by = new.id
      where assigned_by = ghost_profile_id;

    update public.profiles canonical
    set
      full_name = coalesce(canonical.full_name, ghost.full_name),
      display_name = coalesce(canonical.display_name, ghost.display_name),
      avatar_url = coalesce(canonical.avatar_url, ghost.avatar_url),
      clickup_user_id = coalesce(canonical.clickup_user_id, ghost.clickup_user_id),
      slack_user_id = coalesce(canonical.slack_user_id, ghost.slack_user_id),
      employment_status = coalesce(canonical.employment_status, ghost.employment_status),
      allowed_tools = case
        when canonical.allowed_tools = '{}'::text[] then ghost.allowed_tools
        else canonical.allowed_tools
      end,
      is_admin = canonical.is_admin or ghost.is_admin,
      role = case
        when canonical.role = 'member'::team_role and ghost.role = 'admin'::team_role then ghost.role
        else canonical.role
      end,
      updated_at = now()
    from public.profiles ghost
    where canonical.id = new.id
      and ghost.id = ghost_profile_id;

    delete from public.profiles
      where id = ghost_profile_id;
  end if;

  return new;
end;
$$;
