-- =====================================================================
-- MIGRATION: usage_events tool + meta
-- Purpose:
--   - Add `tool` to enable clean per-tool metrics queries
--   - Add `meta` to safely store tool-specific metrics without schema churn
-- =====================================================================

alter table public.usage_events
  add column if not exists tool text;

alter table public.usage_events
  add column if not exists meta jsonb not null default '{}'::jsonb;

create index if not exists idx_usage_events_tool_occurred_at
  on public.usage_events (tool, occurred_at desc);

