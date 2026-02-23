-- =====================================================================
-- MIGRATION: AgencyClaw agent loop storage hardening (C17B follow-up)
-- Purpose:
--   Enable RLS on agent loop storage tables before runtime wiring lands.
-- Scope:
--   - RLS enablement only
--   - No row policies yet (deny-by-default for non-bypass roles)
--   - Service-role runtime remains unaffected
-- =====================================================================

DO $$
BEGIN
  IF to_regclass('public.agent_runs') IS NOT NULL THEN
    ALTER TABLE public.agent_runs ENABLE ROW LEVEL SECURITY;
  END IF;
  IF to_regclass('public.agent_messages') IS NOT NULL THEN
    ALTER TABLE public.agent_messages ENABLE ROW LEVEL SECURITY;
  END IF;
  IF to_regclass('public.agent_skill_events') IS NOT NULL THEN
    ALTER TABLE public.agent_skill_events ENABLE ROW LEVEL SECURITY;
  END IF;
END $$;
