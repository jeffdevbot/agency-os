-- =====================================================================
-- MIGRATION: AgencyClaw skill registry + role rename to Customer Success Lead
-- Purpose:
--   1) Introduce DB-backed skill metadata/policy/logging tables.
--   2) Rename legacy role slug `brand_manager` -> `customer_success_lead`.
-- Notes:
--   - Skill logic remains implemented in code. DB tables store metadata/policy/audit.
--   - Role migration preserves existing assignment links.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) Rename role slug: brand_manager -> customer_success_lead
-- ---------------------------------------------------------------------
DO $$
DECLARE
  bm_id uuid;
  csl_id uuid;
BEGIN
  SELECT id INTO bm_id
  FROM public.agency_roles
  WHERE slug = 'brand_manager'
  LIMIT 1;

  SELECT id INTO csl_id
  FROM public.agency_roles
  WHERE slug = 'customer_success_lead'
  LIMIT 1;

  -- Case A: legacy exists, new slug missing -> rename in-place (preserves role_id references)
  IF bm_id IS NOT NULL AND csl_id IS NULL THEN
    UPDATE public.agency_roles
    SET slug = 'customer_success_lead',
        name = 'Customer Success Lead'
    WHERE id = bm_id;

  -- Case B: both exist -> move assignments to new role, then remove legacy role
  ELSIF bm_id IS NOT NULL AND csl_id IS NOT NULL AND bm_id <> csl_id THEN
    UPDATE public.client_assignments
    SET role_id = csl_id
    WHERE role_id = bm_id;

    DELETE FROM public.agency_roles
    WHERE id = bm_id;

  -- Case C: neither exists -> seed new role
  ELSIF bm_id IS NULL AND csl_id IS NULL THEN
    INSERT INTO public.agency_roles (slug, name)
    VALUES ('customer_success_lead', 'Customer Success Lead')
    ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name;

  -- Case D: new role exists -> normalize display name
  ELSIF csl_id IS NOT NULL THEN
    UPDATE public.agency_roles
    SET name = 'Customer Success Lead'
    WHERE id = csl_id;
  END IF;
END;
$$;

-- ---------------------------------------------------------------------
-- 2) Skill catalog
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.skill_catalog (
  id text PRIMARY KEY,
  name text NOT NULL,
  description text NOT NULL DEFAULT '',
  owner_service text NOT NULL,
  input_schema jsonb NOT NULL DEFAULT '{}'::jsonb,
  output_schema jsonb NOT NULL DEFAULT '{}'::jsonb,
  implemented_in_code boolean NOT NULL DEFAULT true,
  enabled_default boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_skill_catalog_owner_service
  ON public.skill_catalog(owner_service);

CREATE INDEX IF NOT EXISTS idx_skill_catalog_enabled_default
  ON public.skill_catalog(enabled_default);

-- ---------------------------------------------------------------------
-- 3) Skill policy overrides (global/client/team)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.skill_policy_overrides (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  skill_id text NOT NULL REFERENCES public.skill_catalog(id) ON DELETE CASCADE,
  scope_type text NOT NULL CHECK (scope_type IN ('global', 'client', 'team')),
  scope_id uuid,
  enabled boolean,
  min_role_tier text CHECK (min_role_tier IN ('member', 'admin', 'super_admin')),
  requires_confirmation boolean,
  allowed_channels text[] NOT NULL DEFAULT '{}'::text[],
  max_calls_per_hour integer CHECK (max_calls_per_hour IS NULL OR max_calls_per_hour >= 0),
  created_by uuid REFERENCES public.profiles(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT skill_policy_scope_consistency CHECK (
    (scope_type = 'global' AND scope_id IS NULL) OR
    (scope_type IN ('client', 'team') AND scope_id IS NOT NULL)
  )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_skill_policy_unique_global
  ON public.skill_policy_overrides(skill_id, scope_type)
  WHERE scope_type = 'global' AND scope_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_skill_policy_unique_scoped
  ON public.skill_policy_overrides(skill_id, scope_type, scope_id)
  WHERE scope_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_skill_policy_scope_lookup
  ON public.skill_policy_overrides(scope_type, scope_id);

-- ---------------------------------------------------------------------
-- 4) Skill invocation log (idempotency + audit)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.skill_invocation_log (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  idempotency_key text NOT NULL UNIQUE,
  skill_id text NOT NULL REFERENCES public.skill_catalog(id) ON DELETE RESTRICT,
  actor_profile_id uuid REFERENCES public.profiles(id),
  status text NOT NULL CHECK (status IN ('pending', 'success', 'failed', 'duplicate')),
  request_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  response_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_skill_invocation_skill_created
  ON public.skill_invocation_log(skill_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_skill_invocation_actor_created
  ON public.skill_invocation_log(actor_profile_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_skill_invocation_status_created
  ON public.skill_invocation_log(status, created_at DESC);

-- ---------------------------------------------------------------------
-- 5) updated_at triggers
-- ---------------------------------------------------------------------
DROP TRIGGER IF EXISTS update_skill_catalog_updated_at ON public.skill_catalog;
CREATE TRIGGER update_skill_catalog_updated_at
  BEFORE UPDATE ON public.skill_catalog
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_skill_policy_overrides_updated_at ON public.skill_policy_overrides;
CREATE TRIGGER update_skill_policy_overrides_updated_at
  BEFORE UPDATE ON public.skill_policy_overrides
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_skill_invocation_log_updated_at ON public.skill_invocation_log;
CREATE TRIGGER update_skill_invocation_log_updated_at
  BEFORE UPDATE ON public.skill_invocation_log
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ---------------------------------------------------------------------
-- 6) RLS + policies
-- ---------------------------------------------------------------------
ALTER TABLE public.skill_catalog ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.skill_policy_overrides ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.skill_invocation_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Authenticated users can view skill catalog" ON public.skill_catalog;
CREATE POLICY "Authenticated users can view skill catalog"
  ON public.skill_catalog FOR SELECT TO authenticated
  USING (true);

DROP POLICY IF EXISTS "Only admins can manage skill catalog" ON public.skill_catalog;
CREATE POLICY "Only admins can manage skill catalog"
  ON public.skill_catalog FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Only admins can view skill policies" ON public.skill_policy_overrides;
CREATE POLICY "Only admins can view skill policies"
  ON public.skill_policy_overrides FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Only admins can manage skill policies" ON public.skill_policy_overrides;
CREATE POLICY "Only admins can manage skill policies"
  ON public.skill_policy_overrides FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Only admins can view skill invocation log" ON public.skill_invocation_log;
CREATE POLICY "Only admins can view skill invocation log"
  ON public.skill_invocation_log FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Only admins can manage skill invocation log" ON public.skill_invocation_log;
CREATE POLICY "Only admins can manage skill invocation log"
  ON public.skill_invocation_log FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

-- ---------------------------------------------------------------------
-- 7) Seed default skill catalog entries (upsert)
-- ---------------------------------------------------------------------
INSERT INTO public.skill_catalog (id, name, description, owner_service, implemented_in_code, enabled_default)
VALUES
  ('ngram_process', 'N-Gram Process', 'Generate n-gram workbook from uploaded STR.', 'inspector', true, true),
  ('ngram_collect', 'N-Gram Collect', 'Collect negatives workbook output from completed n-gram file.', 'inspector', true, true),
  ('npat_process', 'N-PAT Process', 'Generate N-PAT workbook from uploaded STR.', 'inspector', true, true),
  ('npat_collect', 'N-PAT Collect', 'Collect negatives workbook output from completed N-PAT file.', 'inspector', true, true),
  ('adscope_audit', 'AdScope Audit', 'Run AdScope bulk + STR audit.', 'inspector', true, true),
  ('root_process', 'Root Keywords Process', 'Run root-keyword campaign hierarchy analysis.', 'inspector', true, true),
  ('scribe_generate', 'Scribe Generate', 'Generate listing copy/topics.', 'relay', true, true),
  ('debrief_extract', 'Debrief Extract', 'Extract tasks from meeting notes.', 'orchestrator', true, true),
  ('debrief_send_to_clickup', 'Debrief Send To ClickUp', 'Create ClickUp tasks from extracted debrief tasks.', 'relay', true, true),
  ('cc_client_lookup', 'Client Lookup', 'Lookup clients and brands for command resolution.', 'orchestrator', true, true),
  ('cc_role_lookup', 'Role Lookup', 'Lookup assignable team role slugs.', 'orchestrator', true, true),
  ('cc_resolve_scope', 'Resolve Scope', 'Resolve client/brand references into canonical IDs.', 'orchestrator', true, true),
  ('cc_org_chart_ascii', 'Org Chart ASCII', 'Render client/brand role assignments as ASCII chart.', 'orchestrator', true, true),
  ('cc_assignment_upsert', 'Assignment Upsert', 'Assign or replace assignee for a role slot.', 'orchestrator', true, true),
  ('cc_assignment_remove', 'Assignment Remove', 'Clear assignee from a role slot.', 'orchestrator', true, true),
  ('cc_assignment_audit_log', 'Assignment Audit Log', 'Record assignment changes with actor + before/after.', 'audit', true, true)
ON CONFLICT (id) DO UPDATE
SET
  name = EXCLUDED.name,
  description = EXCLUDED.description,
  owner_service = EXCLUDED.owner_service,
  implemented_in_code = EXCLUDED.implemented_in_code,
  enabled_default = EXCLUDED.enabled_default;
