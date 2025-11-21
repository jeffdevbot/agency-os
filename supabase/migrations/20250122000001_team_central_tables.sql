-- =====================================================================
-- MIGRATION: Team Central Tables
-- PRD Reference: docs/07_team_central_prd.md
-- Purpose: Single-tenant team management and client tracking for Ecomlabs
-- =====================================================================
-- IMPORTANT: This is a SINGLE-TENANT system (no organization_id columns)
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. CREATE ENUMS
-- ---------------------------------------------------------------------

-- Team role enum for flexible RBAC
create type team_role as enum (
  'admin',
  'member',
  'viewer'
);

-- ---------------------------------------------------------------------
-- 2. CREATE OR ENHANCE PROFILES TABLE
-- ---------------------------------------------------------------------
-- NOTE: profiles table may not exist yet, so create it first

-- Create profiles table if it doesn't exist
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  full_name text
);

-- Add is_admin flag (for backward compatibility and performance)
alter table public.profiles
  add column if not exists is_admin boolean not null default false;

-- Add display_name for UI
alter table public.profiles
  add column if not exists display_name text;

-- Add team role for RBAC
alter table public.profiles
  add column if not exists role team_role not null default 'member';

-- Add avatar URL
alter table public.profiles
  add column if not exists avatar_url text;

-- Add timestamps if not exist
alter table public.profiles
  add column if not exists created_at timestamptz not null default now();

alter table public.profiles
  add column if not exists updated_at timestamptz not null default now();

-- Create partial index for admin lookups (performance optimization)
create index if not exists idx_profiles_is_admin
  on public.profiles (is_admin)
  where is_admin = true;

-- Create index for role-based queries
create index if not exists idx_profiles_role
  on public.profiles (role);

-- ---------------------------------------------------------------------
-- 3. CREATE TEAM_MEMBERS_PENDING TABLE
-- ---------------------------------------------------------------------
-- Handles invited users who haven't signed up yet

create table if not exists public.team_members_pending (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  role team_role not null default 'member',
  invited_by uuid not null references public.profiles(id) on delete restrict,
  invited_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '7 days'),

  -- Constraints
  constraint valid_email check (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

-- Index for email lookups
create index if not exists idx_team_members_pending_email
  on public.team_members_pending (email);

-- Index for expiration cleanup
create index if not exists idx_team_members_pending_expires
  on public.team_members_pending (expires_at);

-- ---------------------------------------------------------------------
-- 4. CREATE AGENCY_CLIENTS TABLE
-- ---------------------------------------------------------------------
-- NOTE: This is different from composer's client_profiles table
-- This tracks clients we work FOR, not clients within Composer projects

create table if not exists public.agency_clients (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  company_name text,
  email text,
  phone text,
  status text not null default 'active',
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  -- Constraints
  constraint valid_status check (status in ('active', 'inactive', 'archived')),
  constraint valid_client_email check (
    email is null or
    email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
  )
);

-- Index for name searches
create index if not exists idx_agency_clients_name
  on public.agency_clients (name);

-- Index for status filtering
create index if not exists idx_agency_clients_status
  on public.agency_clients (status);

-- Index for email lookups
create index if not exists idx_agency_clients_email
  on public.agency_clients (email)
  where email is not null;

-- ---------------------------------------------------------------------
-- 5. CREATE CLIENT_ASSIGNMENTS TABLE
-- ---------------------------------------------------------------------
-- Links team members to clients they work with

create table if not exists public.client_assignments (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.agency_clients(id) on delete restrict,
  profile_id uuid not null references public.profiles(id) on delete restrict,
  assigned_at timestamptz not null default now(),
  assigned_by uuid references public.profiles(id) on delete set null,

  -- Composite unique constraint: one assignment per client-profile pair
  constraint unique_client_profile unique (client_id, profile_id)
);

-- Index for client lookups (find all team members for a client)
create index if not exists idx_client_assignments_client
  on public.client_assignments (client_id);

-- Index for profile lookups (find all clients for a team member)
create index if not exists idx_client_assignments_profile
  on public.client_assignments (profile_id);

-- Composite index for the unique constraint
create index if not exists idx_client_assignments_composite
  on public.client_assignments (client_id, profile_id);

-- ---------------------------------------------------------------------
-- 6. CREATE AUTO-LINK TRIGGER FOR PENDING INVITES
-- ---------------------------------------------------------------------
-- When a user signs up with an invited email, auto-promote them

create or replace function handle_new_user_from_invite()
returns trigger
language plpgsql
security definer
as $$
declare
  v_pending record;
begin
  -- Check if this email was invited
  select * into v_pending
  from public.team_members_pending
  where email = new.email
    and expires_at > now()
  limit 1;

  if found then
    -- Update the new profile with invited role
    update public.profiles
    set role = v_pending.role,
        is_admin = (v_pending.role = 'admin')
    where id = new.id;

    -- Delete the pending invite
    delete from public.team_members_pending
    where id = v_pending.id;
  end if;

  return new;
end;
$$;

-- Trigger fires after profile is created
drop trigger if exists on_auth_user_created_link_invite on public.profiles;
create trigger on_auth_user_created_link_invite
  after insert on public.profiles
  for each row
  execute function handle_new_user_from_invite();

-- ---------------------------------------------------------------------
-- 7. CREATE UPDATED_AT TRIGGERS
-- ---------------------------------------------------------------------

create or replace function update_updated_at_column()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- Trigger for profiles
drop trigger if exists update_profiles_updated_at on public.profiles;
create trigger update_profiles_updated_at
  before update on public.profiles
  for each row
  execute function update_updated_at_column();

-- Trigger for agency_clients
drop trigger if exists update_agency_clients_updated_at on public.agency_clients;
create trigger update_agency_clients_updated_at
  before update on public.agency_clients
  for each row
  execute function update_updated_at_column();

-- ---------------------------------------------------------------------
-- 8. ENABLE RLS
-- ---------------------------------------------------------------------

alter table public.profiles enable row level security;
alter table public.team_members_pending enable row level security;
alter table public.agency_clients enable row level security;
alter table public.client_assignments enable row level security;

-- ---------------------------------------------------------------------
-- 9. CREATE RLS POLICIES
-- ---------------------------------------------------------------------

-- PROFILES TABLE POLICIES
-- All authenticated users can read all profiles
create policy "Users can view all profiles"
  on public.profiles for select
  to authenticated
  using (true);

-- Users can update their own profile
create policy "Users can update own profile"
  on public.profiles for update
  to authenticated
  using (auth.uid() = id)
  with check (auth.uid() = id);

-- Only admins can update other profiles
create policy "Admins can update any profile"
  on public.profiles for update
  to authenticated
  using (
    exists (
      select 1 from public.profiles
      where id = auth.uid() and is_admin = true
    )
  );

-- TEAM_MEMBERS_PENDING POLICIES
-- Only admins can view pending invites
create policy "Admins can view pending invites"
  on public.team_members_pending for select
  to authenticated
  using (
    exists (
      select 1 from public.profiles
      where id = auth.uid() and is_admin = true
    )
  );

-- Only admins can create pending invites
create policy "Admins can create pending invites"
  on public.team_members_pending for insert
  to authenticated
  with check (
    exists (
      select 1 from public.profiles
      where id = auth.uid() and is_admin = true
    )
  );

-- Only admins can delete pending invites
create policy "Admins can delete pending invites"
  on public.team_members_pending for delete
  to authenticated
  using (
    exists (
      select 1 from public.profiles
      where id = auth.uid() and is_admin = true
    )
  );

-- AGENCY_CLIENTS POLICIES
-- All authenticated users can view clients
create policy "Authenticated users can view clients"
  on public.agency_clients for select
  to authenticated
  using (true);

-- Only admins can insert clients
create policy "Admins can insert clients"
  on public.agency_clients for insert
  to authenticated
  with check (
    exists (
      select 1 from public.profiles
      where id = auth.uid() and is_admin = true
    )
  );

-- Only admins can update clients
create policy "Admins can update clients"
  on public.agency_clients for update
  to authenticated
  using (
    exists (
      select 1 from public.profiles
      where id = auth.uid() and is_admin = true
    )
  );

-- Only admins can delete clients
create policy "Admins can delete clients"
  on public.agency_clients for delete
  to authenticated
  using (
    exists (
      select 1 from public.profiles
      where id = auth.uid() and is_admin = true
    )
  );

-- CLIENT_ASSIGNMENTS POLICIES
-- Users can view assignments they're part of
create policy "Users can view their own assignments"
  on public.client_assignments for select
  to authenticated
  using (
    profile_id = auth.uid() or
    exists (
      select 1 from public.profiles
      where id = auth.uid() and is_admin = true
    )
  );

-- Only admins can create assignments
create policy "Admins can create assignments"
  on public.client_assignments for insert
  to authenticated
  with check (
    exists (
      select 1 from public.profiles
      where id = auth.uid() and is_admin = true
    )
  );

-- Only admins can delete assignments
create policy "Admins can delete assignments"
  on public.client_assignments for delete
  to authenticated
  using (
    exists (
      select 1 from public.profiles
      where id = auth.uid() and is_admin = true
    )
  );

-- =====================================================================
-- ROLLBACK INSTRUCTIONS
-- =====================================================================
-- To rollback this migration:
/*

-- Drop policies
drop policy if exists "Admins can delete assignments" on public.client_assignments;
drop policy if exists "Admins can create assignments" on public.client_assignments;
drop policy if exists "Users can view their own assignments" on public.client_assignments;
drop policy if exists "Admins can delete clients" on public.agency_clients;
drop policy if exists "Admins can update clients" on public.agency_clients;
drop policy if exists "Admins can insert clients" on public.agency_clients;
drop policy if exists "Authenticated users can view clients" on public.agency_clients;
drop policy if exists "Admins can delete pending invites" on public.team_members_pending;
drop policy if exists "Admins can create pending invites" on public.team_members_pending;
drop policy if exists "Admins can view pending invites" on public.team_members_pending;
drop policy if exists "Admins can update any profile" on public.profiles;
drop policy if exists "Users can update own profile" on public.profiles;
drop policy if exists "Users can view all profiles" on public.profiles;

-- Drop triggers
drop trigger if exists update_agency_clients_updated_at on public.agency_clients;
drop trigger if exists update_profiles_updated_at on public.profiles;
drop trigger if exists on_auth_user_created_link_invite on public.profiles;

-- Drop functions
drop function if exists handle_new_user_from_invite();
drop function if exists update_updated_at_column();

-- Drop indexes
drop index if exists idx_client_assignments_composite;
drop index if exists idx_client_assignments_profile;
drop index if exists idx_client_assignments_client;
drop index if exists idx_agency_clients_email;
drop index if exists idx_agency_clients_status;
drop index if exists idx_agency_clients_name;
drop index if exists idx_team_members_pending_expires;
drop index if exists idx_team_members_pending_email;
drop index if exists idx_profiles_role;
drop index if exists idx_profiles_is_admin;

-- Drop tables
drop table if exists public.client_assignments;
drop table if exists public.agency_clients;
drop table if exists public.team_members_pending;

-- Remove columns from profiles (be careful - may break existing data)
alter table public.profiles drop column if exists updated_at;
alter table public.profiles drop column if exists created_at;
alter table public.profiles drop column if exists avatar_url;
alter table public.profiles drop column if exists role;
alter table public.profiles drop column if exists display_name;
alter table public.profiles drop column if exists is_admin;

-- Drop type
drop type if exists team_role;

*/
