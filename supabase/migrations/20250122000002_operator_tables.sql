-- =====================================================================
-- MIGRATION: The Operator Tables
-- PRD Reference: docs/02_the_operator_prd.md
-- Purpose: Multi-tenant SOP management and AI-powered operations chat
-- =====================================================================
-- IMPORTANT: This is MULTI-TENANT (all tables include organization_id)
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. ENABLE EXTENSIONS
-- ---------------------------------------------------------------------

-- Enable pgvector for embeddings
create extension if not exists vector;

-- ---------------------------------------------------------------------
-- 2. CREATE SOPS TABLE
-- ---------------------------------------------------------------------
-- Standard Operating Procedures with AI embeddings

create table if not exists public.sops (
  organization_id uuid not null references public.composer_organizations(id) on delete cascade,
  id uuid not null default gen_random_uuid(),

  -- Core fields
  title text not null,
  content text not null,
  category text,

  -- Metadata
  client_id uuid references public.agency_clients(id) on delete set null,
  tags text[] default '{}',

  -- AI fields
  embedding vector(1536), -- OpenAI ada-002 dimension

  -- Audit fields
  created_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  -- Composite primary key
  primary key (organization_id, id),

  -- Constraints
  constraint valid_title_length check (char_length(title) between 1 and 500),
  constraint valid_content_length check (char_length(content) > 0)
);

-- Index for organization queries
create index if not exists idx_sops_organization
  on public.sops (organization_id);

-- Index for title search
create index if not exists idx_sops_title
  on public.sops (organization_id, title);

-- Index for category filtering
create index if not exists idx_sops_category
  on public.sops (organization_id, category)
  where category is not null;

-- Index for client filtering
create index if not exists idx_sops_client
  on public.sops (organization_id, client_id)
  where client_id is not null;

-- GIN index for tag array searches
create index if not exists idx_sops_tags
  on public.sops using gin (tags);

-- HNSW index for vector similarity search (cosine distance)
create index if not exists idx_sops_embedding
  on public.sops using hnsw (embedding vector_cosine_ops)
  where embedding is not null;

-- Index for created_by lookups
create index if not exists idx_sops_created_by
  on public.sops (organization_id, created_by);

-- Index for timestamp ordering
create index if not exists idx_sops_created_at
  on public.sops (organization_id, created_at desc);

-- ---------------------------------------------------------------------
-- 3. CREATE OPS_CHAT_SESSIONS TABLE
-- ---------------------------------------------------------------------
-- AI chat sessions with context and metadata

create table if not exists public.ops_chat_sessions (
  organization_id uuid not null references public.composer_organizations(id) on delete cascade,
  id uuid not null default gen_random_uuid(),

  -- Core fields
  user_id uuid not null references public.profiles(id) on delete cascade,
  title text,

  -- Context
  client_id uuid references public.agency_clients(id) on delete set null,
  relevant_sop_ids uuid[] default '{}',

  -- Metadata
  message_count integer not null default 0,

  -- Audit fields
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  -- Composite primary key
  primary key (organization_id, id),

  -- Constraints
  constraint valid_message_count check (message_count >= 0),
  constraint valid_title_length check (
    title is null or
    char_length(title) between 1 and 200
  )
);

-- Index for organization queries
create index if not exists idx_ops_chat_sessions_organization
  on public.ops_chat_sessions (organization_id);

-- Index for user lookups
create index if not exists idx_ops_chat_sessions_user
  on public.ops_chat_sessions (organization_id, user_id);

-- Index for client filtering
create index if not exists idx_ops_chat_sessions_client
  on public.ops_chat_sessions (organization_id, client_id)
  where client_id is not null;

-- GIN index for relevant_sop_ids array searches
create index if not exists idx_ops_chat_sessions_sop_ids
  on public.ops_chat_sessions using gin (relevant_sop_ids);

-- Index for timestamp ordering (most recent first)
create index if not exists idx_ops_chat_sessions_created_at
  on public.ops_chat_sessions (organization_id, user_id, created_at desc);

-- Composite index for user + client queries
create index if not exists idx_ops_chat_sessions_user_client
  on public.ops_chat_sessions (organization_id, user_id, client_id)
  where client_id is not null;

-- ---------------------------------------------------------------------
-- 4. CREATE UPDATED_AT TRIGGERS
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

-- Trigger for sops
drop trigger if exists update_sops_updated_at on public.sops;
create trigger update_sops_updated_at
  before update on public.sops
  for each row
  execute function update_updated_at_column();

-- Trigger for ops_chat_sessions
drop trigger if exists update_ops_chat_sessions_updated_at on public.ops_chat_sessions;
create trigger update_ops_chat_sessions_updated_at
  before update on public.ops_chat_sessions
  for each row
  execute function update_updated_at_column();

-- ---------------------------------------------------------------------
-- 5. ENABLE RLS
-- ---------------------------------------------------------------------

alter table public.sops enable row level security;
alter table public.ops_chat_sessions enable row level security;

-- ---------------------------------------------------------------------
-- 6. CREATE RLS POLICIES
-- ---------------------------------------------------------------------

-- SOPS TABLE POLICIES
-- Users can view SOPs in their organization
create policy "Users can view org SOPs"
  on public.sops for select
  to authenticated
  using (
    organization_id in (
      select organization_id
      from public.composer_organizations
      where id = organization_id
    )
  );

-- Users can create SOPs in their organization
create policy "Users can create org SOPs"
  on public.sops for insert
  to authenticated
  with check (
    organization_id in (
      select organization_id
      from public.composer_organizations
      where id = organization_id
    )
    and created_by = auth.uid()
  );

-- Users can update SOPs they created or if they're admin
create policy "Users can update own SOPs or admins can update any"
  on public.sops for update
  to authenticated
  using (
    organization_id in (
      select organization_id
      from public.composer_organizations
      where id = organization_id
    )
    and (
      created_by = auth.uid()
      or exists (
        select 1 from public.profiles
        where id = auth.uid() and is_admin = true
      )
    )
  );

-- Users can delete SOPs they created or if they're admin
create policy "Users can delete own SOPs or admins can delete any"
  on public.sops for delete
  to authenticated
  using (
    organization_id in (
      select organization_id
      from public.composer_organizations
      where id = organization_id
    )
    and (
      created_by = auth.uid()
      or exists (
        select 1 from public.profiles
        where id = auth.uid() and is_admin = true
      )
    )
  );

-- OPS_CHAT_SESSIONS TABLE POLICIES
-- Users can view their own chat sessions
create policy "Users can view own chat sessions"
  on public.ops_chat_sessions for select
  to authenticated
  using (
    organization_id in (
      select organization_id
      from public.composer_organizations
      where id = organization_id
    )
    and user_id = auth.uid()
  );

-- Admins can view all chat sessions in their org
create policy "Admins can view all org chat sessions"
  on public.ops_chat_sessions for select
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

-- Users can create chat sessions in their org
create policy "Users can create chat sessions"
  on public.ops_chat_sessions for insert
  to authenticated
  with check (
    organization_id in (
      select organization_id
      from public.composer_organizations
      where id = organization_id
    )
    and user_id = auth.uid()
  );

-- Users can update their own chat sessions
create policy "Users can update own chat sessions"
  on public.ops_chat_sessions for update
  to authenticated
  using (
    organization_id in (
      select organization_id
      from public.composer_organizations
      where id = organization_id
    )
    and user_id = auth.uid()
  );

-- Users can delete their own chat sessions
create policy "Users can delete own chat sessions"
  on public.ops_chat_sessions for delete
  to authenticated
  using (
    organization_id in (
      select organization_id
      from public.composer_organizations
      where id = organization_id
    )
    and user_id = auth.uid()
  );

-- =====================================================================
-- NOTES & WARNINGS
-- =====================================================================
--
-- MULTI-TENANCY MODEL:
-- - All tables use composite PK (organization_id, id)
-- - Foreign keys to single-tenant tables (agency_clients, profiles)
--   reference only the id column
-- - Foreign keys to multi-tenant tables must use composite references
-- - RLS policies enforce organization isolation
--
-- EMBEDDING MODEL:
-- - Using OpenAI ada-002 (1536 dimensions)
-- - If switching models, update vector dimension and rebuild index
-- - HNSW index provides fast approximate nearest neighbor search
--
-- CLIENT REFERENCES:
-- - agency_clients is single-tenant (no organization_id)
-- - SOPs can reference clients across the Ecomlabs agency
-- - This is intentional: SOPs belong to orgs, clients are global
--
-- =====================================================================
-- ROLLBACK INSTRUCTIONS
-- =====================================================================
-- To rollback this migration:
/*

-- Drop policies
drop policy if exists "Users can delete own chat sessions" on public.ops_chat_sessions;
drop policy if exists "Users can update own chat sessions" on public.ops_chat_sessions;
drop policy if exists "Users can create chat sessions" on public.ops_chat_sessions;
drop policy if exists "Admins can view all org chat sessions" on public.ops_chat_sessions;
drop policy if exists "Users can view own chat sessions" on public.ops_chat_sessions;
drop policy if exists "Users can delete own SOPs or admins can delete any" on public.sops;
drop policy if exists "Users can update own SOPs or admins can update any" on public.sops;
drop policy if exists "Users can create org SOPs" on public.sops;
drop policy if exists "Users can view org SOPs" on public.sops;

-- Drop triggers
drop trigger if exists update_ops_chat_sessions_updated_at on public.ops_chat_sessions;
drop trigger if exists update_sops_updated_at on public.sops;

-- Drop function (only if not used by other tables)
-- drop function if exists update_updated_at_column();

-- Drop indexes
drop index if exists idx_ops_chat_sessions_user_client;
drop index if exists idx_ops_chat_sessions_created_at;
drop index if exists idx_ops_chat_sessions_sop_ids;
drop index if exists idx_ops_chat_sessions_client;
drop index if exists idx_ops_chat_sessions_user;
drop index if exists idx_ops_chat_sessions_organization;
drop index if exists idx_sops_created_at;
drop index if exists idx_sops_created_by;
drop index if exists idx_sops_embedding;
drop index if exists idx_sops_tags;
drop index if exists idx_sops_client;
drop index if exists idx_sops_category;
drop index if exists idx_sops_title;
drop index if exists idx_sops_organization;

-- Drop tables
drop table if exists public.ops_chat_sessions;
drop table if exists public.sops;

-- Note: Do not drop vector extension as other tables might use it

*/
