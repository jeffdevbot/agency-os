-- =====================================================================
-- MIGRATION: AgencyClaw core runtime tables
-- Purpose:
--   1) Add missing core tables from PRD Section 8.2.
--   2) Add indexes, updated_at triggers, and admin RLS policies.
-- Tables:
--   - public.agent_events
--   - public.agent_tasks
--   - public.threshold_rules
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) Core tables
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.agent_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type text NOT NULL,
  client_id uuid REFERENCES public.agency_clients(id) ON DELETE SET NULL,
  employee_id uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  confidence_level text,
  sop_id uuid REFERENCES public.playbook_sops(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.agent_tasks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clickup_task_id text UNIQUE,
  client_id uuid REFERENCES public.agency_clients(id) ON DELETE SET NULL,
  assignee_id uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  source text NOT NULL,
  source_reference text,
  skill_invoked text,
  sprint_week date,
  status text NOT NULL DEFAULT 'pending',
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.threshold_rules (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  playbook text NOT NULL,
  client_id uuid REFERENCES public.agency_clients(id) ON DELETE CASCADE,
  metric text NOT NULL,
  condition text NOT NULL,
  threshold_value numeric NOT NULL,
  task_type text NOT NULL,
  assignee_role_slug text NOT NULL,
  task_template text NOT NULL,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- 2) Indexes
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_agent_events_client_created
  ON public.agent_events(client_id, created_at DESC)
  WHERE client_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_agent_events_employee_created
  ON public.agent_events(employee_id, created_at DESC)
  WHERE employee_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_agent_events_event_type_created
  ON public.agent_events(event_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_events_sop_created
  ON public.agent_events(sop_id, created_at DESC)
  WHERE sop_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_agent_tasks_client_created
  ON public.agent_tasks(client_id, created_at DESC)
  WHERE client_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_agent_tasks_assignee_created
  ON public.agent_tasks(assignee_id, created_at DESC)
  WHERE assignee_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_agent_tasks_status_updated
  ON public.agent_tasks(status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_tasks_sprint_week
  ON public.agent_tasks(sprint_week DESC)
  WHERE sprint_week IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_agent_tasks_skill_created
  ON public.agent_tasks(skill_invoked, created_at DESC)
  WHERE skill_invoked IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_threshold_rules_client_active
  ON public.threshold_rules(client_id, active)
  WHERE client_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_threshold_rules_playbook_active
  ON public.threshold_rules(playbook, active);

CREATE INDEX IF NOT EXISTS idx_threshold_rules_metric_active
  ON public.threshold_rules(metric, active);

-- ---------------------------------------------------------------------
-- 3) updated_at triggers
-- ---------------------------------------------------------------------
DROP TRIGGER IF EXISTS update_agent_tasks_updated_at ON public.agent_tasks;
CREATE TRIGGER update_agent_tasks_updated_at
  BEFORE UPDATE ON public.agent_tasks
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_threshold_rules_updated_at ON public.threshold_rules;
CREATE TRIGGER update_threshold_rules_updated_at
  BEFORE UPDATE ON public.threshold_rules
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ---------------------------------------------------------------------
-- 4) RLS + policies
-- ---------------------------------------------------------------------
ALTER TABLE public.agent_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.threshold_rules ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Only admins can view agent events" ON public.agent_events;
CREATE POLICY "Only admins can view agent events"
  ON public.agent_events FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Only admins can manage agent events" ON public.agent_events;
CREATE POLICY "Only admins can manage agent events"
  ON public.agent_events FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Only admins can view agent tasks" ON public.agent_tasks;
CREATE POLICY "Only admins can view agent tasks"
  ON public.agent_tasks FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Only admins can manage agent tasks" ON public.agent_tasks;
CREATE POLICY "Only admins can manage agent tasks"
  ON public.agent_tasks FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Only admins can view threshold rules" ON public.threshold_rules;
CREATE POLICY "Only admins can view threshold rules"
  ON public.threshold_rules FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Only admins can manage threshold rules" ON public.threshold_rules;
CREATE POLICY "Only admins can manage threshold rules"
  ON public.threshold_rules FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

