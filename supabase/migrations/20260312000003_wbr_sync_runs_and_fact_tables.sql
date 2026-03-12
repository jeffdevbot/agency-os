-- =====================================================================
-- MIGRATION: WBR sync runs and fact tables (v2 foundation)
-- Purpose:
--   Add generic sync-run logging plus daily Windsor business facts and
--   daily Amazon Ads campaign facts for WBR.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) Generic WBR sync runs
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.wbr_sync_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.wbr_profiles(id) ON DELETE CASCADE,
  source_type text NOT NULL
    CHECK (source_type IN ('windsor_business', 'amazon_ads', 'pacvue_import', 'listing_import')),
  job_type text NOT NULL
    CHECK (job_type IN ('backfill', 'daily_refresh', 'manual_rerun', 'import')),
  date_from date,
  date_to date,
  status text NOT NULL DEFAULT 'running'
    CHECK (status IN ('running', 'success', 'error')),
  rows_fetched integer NOT NULL DEFAULT 0 CHECK (rows_fetched >= 0),
  rows_loaded integer NOT NULL DEFAULT 0 CHECK (rows_loaded >= 0),
  request_meta jsonb NOT NULL DEFAULT '{}'::jsonb,
  error_message text,
  initiated_by uuid REFERENCES public.profiles(id),
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_wbr_sync_runs_profile_source_created
  ON public.wbr_sync_runs(profile_id, source_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_wbr_sync_runs_status_created
  ON public.wbr_sync_runs(status, created_at DESC);

DROP TRIGGER IF EXISTS update_wbr_sync_runs_updated_at ON public.wbr_sync_runs;
CREATE TRIGGER update_wbr_sync_runs_updated_at
  BEFORE UPDATE ON public.wbr_sync_runs
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.wbr_sync_runs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view WBR sync runs" ON public.wbr_sync_runs;
CREATE POLICY "Admins can view WBR sync runs"
  ON public.wbr_sync_runs FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage WBR sync runs" ON public.wbr_sync_runs;
CREATE POLICY "Admins can manage WBR sync runs"
  ON public.wbr_sync_runs FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

-- ---------------------------------------------------------------------
-- 2) Daily Windsor business facts at child-ASIN grain
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.wbr_business_asin_daily (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.wbr_profiles(id) ON DELETE CASCADE,
  sync_run_id uuid REFERENCES public.wbr_sync_runs(id) ON DELETE SET NULL,
  report_date date NOT NULL,
  child_asin text NOT NULL,
  parent_asin text,
  currency_code text NOT NULL,
  page_views bigint NOT NULL DEFAULT 0 CHECK (page_views >= 0),
  unit_sales bigint NOT NULL DEFAULT 0 CHECK (unit_sales >= 0),
  sales numeric(18, 2) NOT NULL DEFAULT 0,
  source_row_count integer NOT NULL DEFAULT 0 CHECK (source_row_count >= 0),
  source_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_wbr_business_asin_daily_profile_date_asin
  ON public.wbr_business_asin_daily(profile_id, report_date, child_asin);

CREATE INDEX IF NOT EXISTS idx_wbr_business_asin_daily_profile_date
  ON public.wbr_business_asin_daily(profile_id, report_date DESC);

CREATE INDEX IF NOT EXISTS idx_wbr_business_asin_daily_profile_asin_date
  ON public.wbr_business_asin_daily(profile_id, child_asin, report_date DESC);

DROP TRIGGER IF EXISTS update_wbr_business_asin_daily_updated_at ON public.wbr_business_asin_daily;
CREATE TRIGGER update_wbr_business_asin_daily_updated_at
  BEFORE UPDATE ON public.wbr_business_asin_daily
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.wbr_business_asin_daily ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view WBR business ASIN daily" ON public.wbr_business_asin_daily;
CREATE POLICY "Admins can view WBR business ASIN daily"
  ON public.wbr_business_asin_daily FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage WBR business ASIN daily" ON public.wbr_business_asin_daily;
CREATE POLICY "Admins can manage WBR business ASIN daily"
  ON public.wbr_business_asin_daily FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

-- ---------------------------------------------------------------------
-- 3) Daily Amazon Ads campaign facts
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.wbr_ads_campaign_daily (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.wbr_profiles(id) ON DELETE CASCADE,
  sync_run_id uuid REFERENCES public.wbr_sync_runs(id) ON DELETE SET NULL,
  report_date date NOT NULL,
  campaign_id text,
  campaign_name text NOT NULL,
  campaign_type text,
  impressions bigint NOT NULL DEFAULT 0 CHECK (impressions >= 0),
  clicks bigint NOT NULL DEFAULT 0 CHECK (clicks >= 0),
  spend numeric(18, 2) NOT NULL DEFAULT 0,
  orders bigint NOT NULL DEFAULT 0 CHECK (orders >= 0),
  sales numeric(18, 2) NOT NULL DEFAULT 0,
  currency_code text,
  source_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_wbr_ads_campaign_daily_profile_date_campaign
  ON public.wbr_ads_campaign_daily(profile_id, report_date, campaign_name);

CREATE INDEX IF NOT EXISTS idx_wbr_ads_campaign_daily_profile_date
  ON public.wbr_ads_campaign_daily(profile_id, report_date DESC);

CREATE INDEX IF NOT EXISTS idx_wbr_ads_campaign_daily_profile_campaign_name
  ON public.wbr_ads_campaign_daily(profile_id, campaign_name);

CREATE INDEX IF NOT EXISTS idx_wbr_ads_campaign_daily_profile_campaign_id
  ON public.wbr_ads_campaign_daily(profile_id, campaign_id)
  WHERE campaign_id IS NOT NULL;

DROP TRIGGER IF EXISTS update_wbr_ads_campaign_daily_updated_at ON public.wbr_ads_campaign_daily;
CREATE TRIGGER update_wbr_ads_campaign_daily_updated_at
  BEFORE UPDATE ON public.wbr_ads_campaign_daily
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.wbr_ads_campaign_daily ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view WBR ads campaign daily" ON public.wbr_ads_campaign_daily;
CREATE POLICY "Admins can view WBR ads campaign daily"
  ON public.wbr_ads_campaign_daily FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage WBR ads campaign daily" ON public.wbr_ads_campaign_daily;
CREATE POLICY "Admins can manage WBR ads campaign daily"
  ON public.wbr_ads_campaign_daily FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

-- ---------------------------------------------------------------------
-- 4) Fact-table sync-run validation helpers
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.wbr_validate_business_sync_run()
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
    RAISE EXCEPTION 'Business fact sync_run_id must belong to the same WBR profile';
  END IF;

  IF v_run_source_type <> 'windsor_business' THEN
    RAISE EXCEPTION 'Business fact sync_run_id must reference source_type = windsor_business';
  END IF;

  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.wbr_validate_ads_sync_run()
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
    RAISE EXCEPTION 'Ads fact sync_run_id must belong to the same WBR profile';
  END IF;

  IF v_run_source_type <> 'amazon_ads' THEN
    RAISE EXCEPTION 'Ads fact sync_run_id must reference source_type = amazon_ads';
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS validate_wbr_business_sync_run ON public.wbr_business_asin_daily;
CREATE TRIGGER validate_wbr_business_sync_run
  BEFORE INSERT OR UPDATE ON public.wbr_business_asin_daily
  FOR EACH ROW EXECUTE FUNCTION public.wbr_validate_business_sync_run();

DROP TRIGGER IF EXISTS validate_wbr_ads_sync_run ON public.wbr_ads_campaign_daily;
CREATE TRIGGER validate_wbr_ads_sync_run
  BEFORE INSERT OR UPDATE ON public.wbr_ads_campaign_daily
  FOR EACH ROW EXECUTE FUNCTION public.wbr_validate_ads_sync_run();
