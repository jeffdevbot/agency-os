-- =====================================================================
-- MIGRATION: Search term daily facts
-- Purpose:
--   Add the Phase 1 STR fact table, a nightly auto-sync flag on WBR profiles,
--   and the new sync_run source_type used by the Amazon Ads search-term sync.
-- =====================================================================

ALTER TABLE public.wbr_profiles
  ADD COLUMN IF NOT EXISTS search_term_auto_sync_enabled boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.wbr_profiles.search_term_auto_sync_enabled
  IS 'When true, worker-sync runs the nightly Amazon Ads search-term trailing-window refresh for this profile.';

DO $$
DECLARE
  v_constraint_name text;
BEGIN
  FOR v_constraint_name IN
    SELECT c.conname
    FROM pg_constraint c
    JOIN pg_attribute a
      ON a.attrelid = c.conrelid
     AND a.attnum = ANY (c.conkey)
    WHERE c.conrelid = 'public.wbr_sync_runs'::regclass
      AND c.contype = 'c'
      AND a.attname = 'source_type'
  LOOP
    EXECUTE format(
      'ALTER TABLE public.wbr_sync_runs DROP CONSTRAINT %I',
      v_constraint_name
    );
  END LOOP;
END
$$;

ALTER TABLE public.wbr_sync_runs
  ADD CONSTRAINT wbr_sync_runs_source_type_check
  CHECK (
    source_type IN (
      'windsor_business',
      'windsor_inventory',
      'windsor_returns',
      'amazon_ads',
      'amazon_ads_search_terms',
      'pacvue_import',
      'listing_import'
    )
  );

CREATE TABLE IF NOT EXISTS public.search_term_daily_facts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.wbr_profiles(id) ON DELETE CASCADE,
  sync_run_id uuid REFERENCES public.wbr_sync_runs(id) ON DELETE SET NULL,
  report_date date NOT NULL,
  campaign_type text NOT NULL,
  campaign_id text,
  campaign_name text NOT NULL,
  campaign_name_head text,
  campaign_name_parts jsonb NOT NULL DEFAULT '[]'::jsonb,
  ad_group_id text,
  ad_group_name text,
  search_term text NOT NULL,
  match_type text,
  impressions integer NOT NULL DEFAULT 0 CHECK (impressions >= 0),
  clicks integer NOT NULL DEFAULT 0 CHECK (clicks >= 0),
  spend numeric(14,2) NOT NULL DEFAULT 0 CHECK (spend >= 0),
  orders integer NOT NULL DEFAULT 0 CHECK (orders >= 0),
  sales numeric(14,2) NOT NULL DEFAULT 0 CHECK (sales >= 0),
  currency_code text,
  source_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_search_term_daily_facts_profile_day_type_campaign_term_match
  ON public.search_term_daily_facts(
    profile_id,
    report_date,
    campaign_type,
    COALESCE(campaign_id, ''),
    campaign_name,
    search_term,
    COALESCE(match_type, '')
  );

CREATE INDEX IF NOT EXISTS idx_search_term_daily_facts_profile_date
  ON public.search_term_daily_facts(profile_id, report_date DESC);

CREATE INDEX IF NOT EXISTS idx_search_term_daily_facts_profile_type_date
  ON public.search_term_daily_facts(profile_id, campaign_type, report_date DESC);

CREATE INDEX IF NOT EXISTS idx_search_term_daily_facts_profile_search_term
  ON public.search_term_daily_facts(profile_id, search_term);

CREATE INDEX IF NOT EXISTS idx_search_term_daily_facts_profile_campaign_name
  ON public.search_term_daily_facts(profile_id, campaign_name);

DROP TRIGGER IF EXISTS update_search_term_daily_facts_updated_at ON public.search_term_daily_facts;
CREATE TRIGGER update_search_term_daily_facts_updated_at
  BEFORE UPDATE ON public.search_term_daily_facts
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.search_term_daily_facts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view search term daily facts" ON public.search_term_daily_facts;
CREATE POLICY "Admins can view search term daily facts"
  ON public.search_term_daily_facts FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage search term daily facts" ON public.search_term_daily_facts;
CREATE POLICY "Admins can manage search term daily facts"
  ON public.search_term_daily_facts FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

CREATE OR REPLACE FUNCTION public.validate_search_term_fact_sync_run()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_run_profile_id uuid;
  v_run_source_type text;
BEGIN
  IF NEW.sync_run_id IS NULL THEN
    RETURN NEW;
  END IF;

  SELECT profile_id, source_type
  INTO v_run_profile_id, v_run_source_type
  FROM public.wbr_sync_runs
  WHERE id = NEW.sync_run_id;

  IF v_run_profile_id IS NULL THEN
    RAISE EXCEPTION 'WBR sync run % was not found', NEW.sync_run_id;
  END IF;

  IF v_run_profile_id <> NEW.profile_id THEN
    RAISE EXCEPTION 'Search-term fact sync_run_id must belong to the same WBR profile';
  END IF;

  IF v_run_source_type <> 'amazon_ads_search_terms' THEN
    RAISE EXCEPTION 'Search-term fact sync_run_id must reference source_type = amazon_ads_search_terms';
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS validate_search_term_fact_sync_run ON public.search_term_daily_facts;
CREATE TRIGGER validate_search_term_fact_sync_run
  BEFORE INSERT OR UPDATE ON public.search_term_daily_facts
  FOR EACH ROW EXECUTE FUNCTION public.validate_search_term_fact_sync_run();
