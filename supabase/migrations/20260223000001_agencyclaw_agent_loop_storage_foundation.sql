-- =====================================================================
-- MIGRATION: AgencyClaw agent loop storage foundation (C17B)
-- Purpose:
--   Add schema-only storage tables for agent loop runs/messages/skill events.
-- Scope:
--   - Tables + indexes only
--   - No runtime wiring
--   - No new RLS/policy behavior in this chunk
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.agent_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL REFERENCES public.playbook_slack_sessions(id) ON DELETE CASCADE,
  parent_run_id uuid REFERENCES public.agent_runs(id) ON DELETE CASCADE,
  trace_id uuid NOT NULL DEFAULT gen_random_uuid(),
  run_type text NOT NULL CHECK (run_type IN ('main', 'planner')),
  status text NOT NULL CHECK (status IN ('running', 'completed', 'blocked', 'failed')),
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_session_started
  ON public.agent_runs(session_id, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_runs_trace
  ON public.agent_runs(trace_id);

CREATE TABLE IF NOT EXISTS public.agent_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL REFERENCES public.agent_runs(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'planner_report')),
  content jsonb NOT NULL,
  summary text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_messages_run_created
  ON public.agent_messages(run_id, created_at);

CREATE TABLE IF NOT EXISTS public.agent_skill_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL REFERENCES public.agent_runs(id) ON DELETE CASCADE,
  event_type text NOT NULL CHECK (event_type IN ('skill_call', 'skill_result')),
  skill_id text NOT NULL,
  payload jsonb NOT NULL,
  payload_summary text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_skill_events_run_created
  ON public.agent_skill_events(run_id, created_at);
