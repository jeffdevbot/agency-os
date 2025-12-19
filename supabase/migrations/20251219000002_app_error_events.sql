-- =====================================================================
-- MIGRATION: app_error_events (minimal centralized error log)
-- Purpose:
--   - Persist server-side errors in a queryable table for admin support
-- Notes:
--   - Intended for service-role inserts (RLS bypass); admin-only reads
--   - Use `meta` for arbitrary context (route params, ids, stack, etc.)
-- =====================================================================

create table if not exists public.app_error_events (
  id uuid primary key default gen_random_uuid(),
  occurred_at timestamptz not null default now(),
  tool text,
  severity text not null default 'error',
  message text not null,
  route text,
  method text,
  status_code integer,
  request_id text,
  user_id uuid,
  user_email text,
  meta jsonb not null default '{}'::jsonb
);

create index if not exists idx_app_error_events_occurred_at
  on public.app_error_events (occurred_at desc);

create index if not exists idx_app_error_events_tool_occurred_at
  on public.app_error_events (tool, occurred_at desc);

create index if not exists idx_app_error_events_user_occurred_at
  on public.app_error_events (user_id, occurred_at desc);

alter table public.app_error_events enable row level security;

drop policy if exists "Admins can view error events" on public.app_error_events;
create policy "Admins can view error events"
  on public.app_error_events for select to authenticated
  using (exists (select 1 from public.profiles where id = auth.uid() and is_admin = true));

