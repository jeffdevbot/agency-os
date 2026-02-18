-- =====================================================================
-- MIGRATION: Add composite index for C4B duplicate-check performance
-- Purpose:
--   The check_duplicate() query filters agent_tasks on source_reference
--   with a created_at >= cutoff window. This index covers that access
--   pattern to avoid sequential scans as the table grows.
-- =====================================================================

CREATE INDEX IF NOT EXISTS idx_agent_tasks_source_ref_created
  ON public.agent_tasks(source_reference, created_at DESC)
  WHERE source_reference IS NOT NULL;
