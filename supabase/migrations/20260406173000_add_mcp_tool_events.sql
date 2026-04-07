-- =====================================================================
-- MIGRATION: mcp_tool_events
-- Purpose:
--   - Persist Claude / MCP tool usage in a queryable table
--   - Track adoption, success/error rates, and basic target metadata
-- Notes:
--   - Intended for service-role inserts from the backend MCP wrapper layer
--   - Read access is restricted to admins
-- =====================================================================

create table if not exists public.mcp_tool_events (
  id uuid primary key default gen_random_uuid(),
  occurred_at timestamptz not null default now(),
  tool_name text not null,
  status text not null check (status in ('success', 'error')),
  duration_ms integer,
  user_id uuid,
  user_email text,
  surface text not null default 'claude_mcp',
  connector_name text not null default 'Ecomlabs Tools',
  is_mutation boolean not null default false,
  meta jsonb not null default '{}'::jsonb
);

create index if not exists idx_mcp_tool_events_occurred_at
  on public.mcp_tool_events (occurred_at desc);

create index if not exists idx_mcp_tool_events_tool_occurred_at
  on public.mcp_tool_events (tool_name, occurred_at desc);

create index if not exists idx_mcp_tool_events_user_occurred_at
  on public.mcp_tool_events (user_id, occurred_at desc);

create index if not exists idx_mcp_tool_events_status_occurred_at
  on public.mcp_tool_events (status, occurred_at desc);

alter table public.mcp_tool_events enable row level security;

drop policy if exists "Admins can view MCP tool events" on public.mcp_tool_events;
create policy "Admins can view MCP tool events"
  on public.mcp_tool_events for select to authenticated
  using (exists (select 1 from public.profiles where id = auth.uid() and is_admin = true));
