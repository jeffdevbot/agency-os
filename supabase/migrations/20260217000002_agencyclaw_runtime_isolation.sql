-- =====================================================================
-- MIGRATION: AgencyClaw runtime isolation + durable Slack idempotency
-- Purpose:
--   1) Add durable Slack dedupe receipts for events/interactions.
--   2) Add run envelope table to isolate interactive/heartbeat/ingestion contexts.
-- Notes:
--   - These tables are runtime metadata and audit state.
--   - Service-role writes bypass RLS; admin policies allow dashboard visibility.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) Durable Slack event receipts (idempotency across retries/restarts)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.slack_event_receipts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_key text NOT NULL UNIQUE,
  event_source text NOT NULL CHECK (event_source IN ('events', 'interactions')),
  slack_event_id text,
  event_type text,
  status text NOT NULL DEFAULT 'processing'
    CHECK (status IN ('processing', 'processed', 'ignored', 'failed', 'duplicate')),
  error_message text,
  request_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  response_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  received_at timestamptz NOT NULL DEFAULT now(),
  processed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_slack_event_receipts_status_received
  ON public.slack_event_receipts(status, received_at DESC);

CREATE INDEX IF NOT EXISTS idx_slack_event_receipts_event_source_received
  ON public.slack_event_receipts(event_source, received_at DESC);

CREATE INDEX IF NOT EXISTS idx_slack_event_receipts_slack_event_id
  ON public.slack_event_receipts(slack_event_id)
  WHERE slack_event_id IS NOT NULL;

-- ---------------------------------------------------------------------
-- 2) Agent runs (run_type/run_key context isolation + parent/child lineage)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.agent_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_type text NOT NULL CHECK (run_type IN ('interactive', 'heartbeat', 'ingestion', 'child')),
  run_key text NOT NULL,
  status text NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),

  parent_run_id uuid REFERENCES public.agent_runs(id) ON DELETE SET NULL,
  actor_profile_id uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  client_id uuid REFERENCES public.agency_clients(id) ON DELETE SET NULL,
  skill_id text REFERENCES public.skill_catalog(id) ON DELETE SET NULL,

  channel_id text,
  thread_ts text,
  source text,

  input_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  output_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  error_message text,

  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Lookup and auditing indexes
CREATE INDEX IF NOT EXISTS idx_agent_runs_type_key_created
  ON public.agent_runs(run_type, run_key, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_runs_status_created
  ON public.agent_runs(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_runs_parent
  ON public.agent_runs(parent_run_id)
  WHERE parent_run_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_agent_runs_actor_created
  ON public.agent_runs(actor_profile_id, created_at DESC)
  WHERE actor_profile_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_agent_runs_client_created
  ON public.agent_runs(client_id, created_at DESC)
  WHERE client_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_agent_runs_skill_created
  ON public.agent_runs(skill_id, created_at DESC)
  WHERE skill_id IS NOT NULL;

-- Helpful for "one running run for same scope" checks.
CREATE INDEX IF NOT EXISTS idx_agent_runs_active_scope
  ON public.agent_runs(run_type, run_key, created_at DESC)
  WHERE status IN ('queued', 'running');

-- ---------------------------------------------------------------------
-- 3) updated_at triggers
-- ---------------------------------------------------------------------
DROP TRIGGER IF EXISTS update_slack_event_receipts_updated_at ON public.slack_event_receipts;
CREATE TRIGGER update_slack_event_receipts_updated_at
  BEFORE UPDATE ON public.slack_event_receipts
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_agent_runs_updated_at ON public.agent_runs;
CREATE TRIGGER update_agent_runs_updated_at
  BEFORE UPDATE ON public.agent_runs
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ---------------------------------------------------------------------
-- 4) RLS + policies
-- ---------------------------------------------------------------------
ALTER TABLE public.slack_event_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_runs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Only admins can view slack event receipts" ON public.slack_event_receipts;
CREATE POLICY "Only admins can view slack event receipts"
  ON public.slack_event_receipts FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Only admins can manage slack event receipts" ON public.slack_event_receipts;
CREATE POLICY "Only admins can manage slack event receipts"
  ON public.slack_event_receipts FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Only admins can view agent runs" ON public.agent_runs;
CREATE POLICY "Only admins can view agent runs"
  ON public.agent_runs FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Only admins can manage agent runs" ON public.agent_runs;
CREATE POLICY "Only admins can manage agent runs"
  ON public.agent_runs FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

-- ---------------------------------------------------------------------
-- 5) Retention helpers (optional cleanup jobs)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.cleanup_old_slack_event_receipts(p_days integer DEFAULT 30)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
  deleted_count integer;
BEGIN
  DELETE FROM public.slack_event_receipts
  WHERE received_at < now() - make_interval(days => p_days);

  GET DIAGNOSTICS deleted_count = ROW_COUNT;
  RETURN deleted_count;
END;
$$;

GRANT EXECUTE ON FUNCTION public.cleanup_old_slack_event_receipts(integer) TO service_role;

CREATE OR REPLACE FUNCTION public.cleanup_old_agent_runs(p_days integer DEFAULT 90)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
  deleted_count integer;
BEGIN
  DELETE FROM public.agent_runs
  WHERE created_at < now() - make_interval(days => p_days)
    AND status IN ('succeeded', 'failed', 'cancelled');

  GET DIAGNOSTICS deleted_count = ROW_COUNT;
  RETURN deleted_count;
END;
$$;

GRANT EXECUTE ON FUNCTION public.cleanup_old_agent_runs(integer) TO service_role;
