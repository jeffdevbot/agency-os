-- =====================================================================
-- MIGRATION: ClickUp Service Tables
-- PRD Reference: docs/08_clickup_service_prd.md
-- Purpose: Multi-tenant ClickUp integration with caching and sync
-- =====================================================================
-- IMPORTANT: This is MULTI-TENANT (all tables include organization_id)
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. ENABLE EXTENSIONS
-- ---------------------------------------------------------------------

-- Enable pgcrypto for token encryption (if not already enabled)
create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------
-- 2. CREATE CLICKUP_API_CREDENTIALS TABLE
-- ---------------------------------------------------------------------
-- Stores encrypted API tokens per organization

create table if not exists public.clickup_api_credentials (
  organization_id uuid not null references public.composer_organizations(id) on delete cascade,
  id uuid not null default gen_random_uuid(),

  -- Credentials
  api_token_encrypted text not null,

  -- Metadata
  configured_by uuid not null references public.profiles(id) on delete restrict,
  configured_at timestamptz not null default now(),
  last_verified_at timestamptz,
  is_valid boolean not null default true,

  -- Audit
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  -- Composite primary key
  primary key (organization_id, id),

  -- Only one active credential per org
  constraint unique_org_credential unique (organization_id)
);

-- Index for organization lookups
create index if not exists idx_clickup_credentials_organization
  on public.clickup_api_credentials (organization_id);

-- Index for validity checks
create index if not exists idx_clickup_credentials_valid
  on public.clickup_api_credentials (organization_id, is_valid);

-- ---------------------------------------------------------------------
-- 3. CREATE CLICKUP_SPACES_CACHE TABLE
-- ---------------------------------------------------------------------
-- Caches ClickUp workspaces and spaces

create table if not exists public.clickup_spaces_cache (
  organization_id uuid not null references public.composer_organizations(id) on delete cascade,
  id text not null, -- ClickUp space ID (string)

  -- Core fields
  name text not null,

  -- Hierarchy
  team_id text not null, -- ClickUp team/workspace ID

  -- Cache metadata
  cached_at timestamptz not null default now(),
  cache_expires_at timestamptz not null default (now() + interval '1 hour'),

  -- Composite primary key
  primary key (organization_id, id),

  -- Constraints
  constraint valid_name_length check (char_length(name) > 0)
);

-- Index for organization queries
create index if not exists idx_clickup_spaces_organization
  on public.clickup_spaces_cache (organization_id);

-- Index for team queries
create index if not exists idx_clickup_spaces_team
  on public.clickup_spaces_cache (organization_id, team_id);

-- Index for cache expiration cleanup
create index if not exists idx_clickup_spaces_cache_expires
  on public.clickup_spaces_cache (cache_expires_at);

-- ---------------------------------------------------------------------
-- 4. CREATE CLICKUP_USERS_CACHE TABLE
-- ---------------------------------------------------------------------
-- Caches ClickUp team members

create table if not exists public.clickup_users_cache (
  organization_id uuid not null references public.composer_organizations(id) on delete cascade,
  id integer not null, -- ClickUp user ID (integer)

  -- Core fields
  username text not null,
  email text,

  -- Display info
  initials text,
  profile_picture text,

  -- Cache metadata
  cached_at timestamptz not null default now(),
  cache_expires_at timestamptz not null default (now() + interval '24 hours'),

  -- Composite primary key
  primary key (organization_id, id),

  -- Constraints
  constraint valid_username_length check (char_length(username) > 0)
);

-- Index for organization queries
create index if not exists idx_clickup_users_organization
  on public.clickup_users_cache (organization_id);

-- Index for username searches
create index if not exists idx_clickup_users_username
  on public.clickup_users_cache (organization_id, username);

-- Index for email lookups
create index if not exists idx_clickup_users_email
  on public.clickup_users_cache (organization_id, email)
  where email is not null;

-- Index for cache expiration cleanup
create index if not exists idx_clickup_users_cache_expires
  on public.clickup_users_cache (cache_expires_at);

-- ---------------------------------------------------------------------
-- 5. CREATE CLICKUP_TASKS_CACHE TABLE
-- ---------------------------------------------------------------------
-- Caches ClickUp tasks with full metadata

create table if not exists public.clickup_tasks_cache (
  organization_id uuid not null references public.composer_organizations(id) on delete cascade,
  id text not null, -- ClickUp task ID (string)

  -- Core fields
  name text not null,
  description text,
  status text not null,

  -- Hierarchy
  space_id text not null,
  folder_id text,
  list_id text not null,

  -- Assignment
  assignees integer[] default '{}', -- Array of ClickUp user IDs

  -- Dates
  date_created timestamptz,
  date_updated timestamptz,
  date_closed timestamptz,
  due_date timestamptz,
  start_date timestamptz,

  -- Metadata
  priority integer,
  tags text[] default '{}',
  url text,

  -- Cache metadata
  cached_at timestamptz not null default now(),
  cache_expires_at timestamptz not null default (now() + interval '5 minutes'),

  -- Composite primary key
  primary key (organization_id, id),

  -- Constraints
  constraint valid_name_length check (char_length(name) > 0),
  constraint valid_priority check (priority is null or priority between 1 and 4)
);

-- Index for organization queries
create index if not exists idx_clickup_tasks_organization
  on public.clickup_tasks_cache (organization_id);

-- Index for space queries
create index if not exists idx_clickup_tasks_space
  on public.clickup_tasks_cache (organization_id, space_id);

-- Index for list queries
create index if not exists idx_clickup_tasks_list
  on public.clickup_tasks_cache (organization_id, list_id);

-- Index for status filtering
create index if not exists idx_clickup_tasks_status
  on public.clickup_tasks_cache (organization_id, status);

-- GIN index for assignees array searches
create index if not exists idx_clickup_tasks_assignees
  on public.clickup_tasks_cache using gin (assignees);

-- GIN index for tags array searches
create index if not exists idx_clickup_tasks_tags
  on public.clickup_tasks_cache using gin (tags);

-- Index for due date ordering
create index if not exists idx_clickup_tasks_due_date
  on public.clickup_tasks_cache (organization_id, due_date)
  where due_date is not null;

-- Index for cache expiration cleanup
create index if not exists idx_clickup_tasks_cache_expires
  on public.clickup_tasks_cache (cache_expires_at);

-- Composite index for space + status queries
create index if not exists idx_clickup_tasks_space_status
  on public.clickup_tasks_cache (organization_id, space_id, status);

-- ---------------------------------------------------------------------
-- 6. CREATE CLICKUP_SYNC_STATUS TABLE
-- ---------------------------------------------------------------------
-- Tracks sync operations and health

create table if not exists public.clickup_sync_status (
  organization_id uuid not null references public.composer_organizations(id) on delete cascade,
  id uuid not null default gen_random_uuid(),

  -- Sync metadata
  entity_type text not null, -- 'spaces', 'users', 'tasks'
  last_sync_at timestamptz not null default now(),
  last_sync_success boolean not null default true,
  last_sync_error text,
  records_synced integer not null default 0,

  -- Audit
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  -- Composite primary key
  primary key (organization_id, id),

  -- One status row per org per entity type
  constraint unique_org_entity unique (organization_id, entity_type),

  -- Constraints
  constraint valid_entity_type check (
    entity_type in ('spaces', 'users', 'tasks')
  ),
  constraint valid_records_synced check (records_synced >= 0)
);

-- Index for organization queries
create index if not exists idx_clickup_sync_organization
  on public.clickup_sync_status (organization_id);

-- Index for entity type queries
create index if not exists idx_clickup_sync_entity
  on public.clickup_sync_status (organization_id, entity_type);

-- Index for health monitoring (failed syncs)
create index if not exists idx_clickup_sync_failures
  on public.clickup_sync_status (organization_id, last_sync_success, last_sync_at)
  where last_sync_success = false;

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

-- Trigger for clickup_api_credentials
drop trigger if exists update_clickup_credentials_updated_at on public.clickup_api_credentials;
create trigger update_clickup_credentials_updated_at
  before update on public.clickup_api_credentials
  for each row
  execute function update_updated_at_column();

-- Trigger for clickup_sync_status
drop trigger if exists update_clickup_sync_updated_at on public.clickup_sync_status;
create trigger update_clickup_sync_updated_at
  before update on public.clickup_sync_status
  for each row
  execute function update_updated_at_column();

-- ---------------------------------------------------------------------
-- 8. ENABLE RLS
-- ---------------------------------------------------------------------

alter table public.clickup_api_credentials enable row level security;
alter table public.clickup_spaces_cache enable row level security;
alter table public.clickup_users_cache enable row level security;
alter table public.clickup_tasks_cache enable row level security;
alter table public.clickup_sync_status enable row level security;

-- ---------------------------------------------------------------------
-- 9. CREATE RLS POLICIES
-- ---------------------------------------------------------------------

-- CLICKUP_API_CREDENTIALS POLICIES
-- Only admins can view credentials
create policy "Admins can view credentials"
  on public.clickup_api_credentials for select
  to authenticated
  using (
    organization_id in (
      select organization_id
      from public.composer_organizations
      where id = organization_id
    )
    and exists (
      select 1 from public.profiles
      where id = auth.uid() and is_admin = true
    )
  );

-- Only admins can insert credentials
create policy "Admins can insert credentials"
  on public.clickup_api_credentials for insert
  to authenticated
  with check (
    organization_id in (
      select organization_id
      from public.composer_organizations
      where id = organization_id
    )
    and exists (
      select 1 from public.profiles
      where id = auth.uid() and is_admin = true
    )
    and configured_by = auth.uid()
  );

-- Only admins can update credentials
create policy "Admins can update credentials"
  on public.clickup_api_credentials for update
  to authenticated
  using (
    organization_id in (
      select organization_id
      from public.composer_organizations
      where id = organization_id
    )
    and exists (
      select 1 from public.profiles
      where id = auth.uid() and is_admin = true
    )
  );

-- Only admins can delete credentials
create policy "Admins can delete credentials"
  on public.clickup_api_credentials for delete
  to authenticated
  using (
    organization_id in (
      select organization_id
      from public.composer_organizations
      where id = organization_id
    )
    and exists (
      select 1 from public.profiles
      where id = auth.uid() and is_admin = true
    )
  );

-- CACHE TABLES POLICIES (spaces, users, tasks)
-- Service role can write (sync operations)
create policy "Service role can manage spaces cache"
  on public.clickup_spaces_cache for all
  to authenticated
  using (
    auth.uid() = '00000000-0000-0000-0000-000000000000'::uuid
    or organization_id in (
      select organization_id
      from public.composer_organizations
      where id = organization_id
    )
  );

create policy "Service role can manage users cache"
  on public.clickup_users_cache for all
  to authenticated
  using (
    auth.uid() = '00000000-0000-0000-0000-000000000000'::uuid
    or organization_id in (
      select organization_id
      from public.composer_organizations
      where id = organization_id
    )
  );

create policy "Service role can manage tasks cache"
  on public.clickup_tasks_cache for all
  to authenticated
  using (
    auth.uid() = '00000000-0000-0000-0000-000000000000'::uuid
    or organization_id in (
      select organization_id
      from public.composer_organizations
      where id = organization_id
    )
  );

-- Users can read cache in their organization
create policy "Users can read spaces cache"
  on public.clickup_spaces_cache for select
  to authenticated
  using (
    organization_id in (
      select organization_id
      from public.composer_organizations
      where id = organization_id
    )
  );

create policy "Users can read users cache"
  on public.clickup_users_cache for select
  to authenticated
  using (
    organization_id in (
      select organization_id
      from public.composer_organizations
      where id = organization_id
    )
  );

create policy "Users can read tasks cache"
  on public.clickup_tasks_cache for select
  to authenticated
  using (
    organization_id in (
      select organization_id
      from public.composer_organizations
      where id = organization_id
    )
  );

-- CLICKUP_SYNC_STATUS POLICIES
-- Service role can manage sync status
create policy "Service role can manage sync status"
  on public.clickup_sync_status for all
  to authenticated
  using (
    auth.uid() = '00000000-0000-0000-0000-000000000000'::uuid
    or organization_id in (
      select organization_id
      from public.composer_organizations
      where id = organization_id
    )
  );

-- Users can read sync status
create policy "Users can read sync status"
  on public.clickup_sync_status for select
  to authenticated
  using (
    organization_id in (
      select organization_id
      from public.composer_organizations
      where id = organization_id
    )
  );

-- =====================================================================
-- NOTES & WARNINGS
-- =====================================================================
--
-- API TOKEN ENCRYPTION:
-- - api_token_encrypted should be encrypted using pgcrypto or Supabase Vault
-- - Example encryption: pgp_sym_encrypt(token, vault_secret)
-- - Example decryption: pgp_sym_decrypt(api_token_encrypted, vault_secret)
-- - Consider using Supabase Vault for production key management
--
-- CACHE TTL:
-- - Spaces: 1 hour (stable data)
-- - Users: 24 hours (rarely changes)
-- - Tasks: 5 minutes (frequently updated)
-- - Adjust based on API rate limits and freshness requirements
--
-- SERVICE ROLE:
-- - Service role UUID check may need adjustment based on deployment
-- - Alternative: use a dedicated service account with specific role
--
-- CLEANUP JOBS:
-- - Implement periodic cleanup of expired cache entries
-- - Monitor cache_expires_at indexes for efficient cleanup queries
--
-- =====================================================================
-- ROLLBACK INSTRUCTIONS
-- =====================================================================
-- To rollback this migration:
/*

-- Drop policies
drop policy if exists "Users can read sync status" on public.clickup_sync_status;
drop policy if exists "Service role can manage sync status" on public.clickup_sync_status;
drop policy if exists "Users can read tasks cache" on public.clickup_tasks_cache;
drop policy if exists "Users can read users cache" on public.clickup_users_cache;
drop policy if exists "Users can read spaces cache" on public.clickup_spaces_cache;
drop policy if exists "Service role can manage tasks cache" on public.clickup_tasks_cache;
drop policy if exists "Service role can manage users cache" on public.clickup_users_cache;
drop policy if exists "Service role can manage spaces cache" on public.clickup_spaces_cache;
drop policy if exists "Admins can delete credentials" on public.clickup_api_credentials;
drop policy if exists "Admins can update credentials" on public.clickup_api_credentials;
drop policy if exists "Admins can insert credentials" on public.clickup_api_credentials;
drop policy if exists "Admins can view credentials" on public.clickup_api_credentials;

-- Drop triggers
drop trigger if exists update_clickup_sync_updated_at on public.clickup_sync_status;
drop trigger if exists update_clickup_credentials_updated_at on public.clickup_api_credentials;

-- Drop function (only if not used by other tables)
-- drop function if exists update_updated_at_column();

-- Drop indexes
drop index if exists idx_clickup_sync_failures;
drop index if exists idx_clickup_sync_entity;
drop index if exists idx_clickup_sync_organization;
drop index if exists idx_clickup_tasks_space_status;
drop index if exists idx_clickup_tasks_cache_expires;
drop index if exists idx_clickup_tasks_due_date;
drop index if exists idx_clickup_tasks_tags;
drop index if exists idx_clickup_tasks_assignees;
drop index if exists idx_clickup_tasks_status;
drop index if exists idx_clickup_tasks_list;
drop index if exists idx_clickup_tasks_space;
drop index if exists idx_clickup_tasks_organization;
drop index if exists idx_clickup_users_cache_expires;
drop index if exists idx_clickup_users_email;
drop index if exists idx_clickup_users_username;
drop index if exists idx_clickup_users_organization;
drop index if exists idx_clickup_spaces_cache_expires;
drop index if exists idx_clickup_spaces_team;
drop index if exists idx_clickup_spaces_organization;
drop index if exists idx_clickup_credentials_valid;
drop index if exists idx_clickup_credentials_organization;

-- Drop tables
drop table if exists public.clickup_sync_status;
drop table if exists public.clickup_tasks_cache;
drop table if exists public.clickup_users_cache;
drop table if exists public.clickup_spaces_cache;
drop table if exists public.clickup_api_credentials;

-- Note: Do not drop pgcrypto extension as other tables might use it

*/
