-- =====================================================================
-- MIGRATION: search_term_campaign_scope
-- Purpose:
--   Add the campaign-product context table that links each WBR campaign
--   to its resolved child-ASIN scope.  This is the second dependency-phase
--   table from docs/search_term_automation_plan.md.
--
--   Rows are produced by rebuild_campaign_scope_for_profile() in the
--   campaign_scope service and represent a snapshot of what each campaign
--   was promoting at the time of the last rebuild.
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.search_term_campaign_scope (
  id                   uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id           uuid        NOT NULL REFERENCES public.wbr_profiles(id) ON DELETE CASCADE,
  campaign_name        text        NOT NULL,
  campaign_id          text,                          -- nullable; reserved for future Amazon Ads entity linkage
  source_type          text        NOT NULL DEFAULT 'pacvue_row_mapping',
  source_row_id        uuid        REFERENCES public.wbr_rows(id) ON DELETE SET NULL,
  resolved_row_ids     jsonb       NOT NULL DEFAULT '[]'::jsonb,  -- sorted uuid array
  resolved_child_asins jsonb       NOT NULL DEFAULT '[]'::jsonb,  -- sorted, deduped ASIN array
  active               boolean     NOT NULL DEFAULT true,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now()
);

-- Only one active scope row per campaign per profile
CREATE UNIQUE INDEX IF NOT EXISTS uq_search_term_campaign_scope_profile_campaign_active
  ON public.search_term_campaign_scope(profile_id, campaign_name)
  WHERE active = true;

CREATE INDEX IF NOT EXISTS idx_search_term_campaign_scope_profile
  ON public.search_term_campaign_scope(profile_id);

CREATE INDEX IF NOT EXISTS idx_search_term_campaign_scope_profile_active
  ON public.search_term_campaign_scope(profile_id, active);

CREATE OR REPLACE FUNCTION public.activate_search_term_campaign_scope(
  p_profile_id uuid,
  p_scope_ids uuid[]
)
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
  v_expected_count integer := COALESCE(array_length(p_scope_ids, 1), 0);
  v_activated_count integer := 0;
BEGIN
  IF v_expected_count = 0 THEN
    RETURN 0;
  END IF;

  UPDATE public.search_term_campaign_scope
  SET active = false
  WHERE profile_id = p_profile_id
    AND active = true;

  UPDATE public.search_term_campaign_scope
  SET active = true
  WHERE profile_id = p_profile_id
    AND id = ANY(p_scope_ids);

  GET DIAGNOSTICS v_activated_count = ROW_COUNT;

  IF v_activated_count <> v_expected_count THEN
    RAISE EXCEPTION
      'Expected to activate % campaign scope rows for profile %, activated %',
      v_expected_count,
      p_profile_id,
      v_activated_count;
  END IF;

  RETURN v_activated_count;
END;
$$;

-- Auto-update updated_at on every row change
DROP TRIGGER IF EXISTS update_search_term_campaign_scope_updated_at
  ON public.search_term_campaign_scope;
CREATE TRIGGER update_search_term_campaign_scope_updated_at
  BEFORE UPDATE ON public.search_term_campaign_scope
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- Row-level security: admin-only (matches all other WBR tables)
ALTER TABLE public.search_term_campaign_scope ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view search term campaign scope"
  ON public.search_term_campaign_scope;
CREATE POLICY "Admins can view search term campaign scope"
  ON public.search_term_campaign_scope FOR SELECT TO authenticated
  USING (EXISTS (
    SELECT 1 FROM public.profiles
    WHERE id = auth.uid() AND is_admin = true
  ));

DROP POLICY IF EXISTS "Admins can manage search term campaign scope"
  ON public.search_term_campaign_scope;
CREATE POLICY "Admins can manage search term campaign scope"
  ON public.search_term_campaign_scope FOR ALL TO authenticated
  USING (EXISTS (
    SELECT 1 FROM public.profiles
    WHERE id = auth.uid() AND is_admin = true
  ))
  WITH CHECK (EXISTS (
    SELECT 1 FROM public.profiles
    WHERE id = auth.uid() AND is_admin = true
  ));
