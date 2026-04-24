-- =====================================================================
-- MIGRATION: Create wbr_business_asin_daily__compare
-- Purpose:
--   Shadow table for A/B validation of the direct SP-API business
--   ingestion pipeline (Pass 3 Slice 3d). Writes from
--   SpApiBusinessCompareService land here and get diffed against the
--   Windsor-fed primary table wbr_business_asin_daily.
--
-- Shape: identical columns + CHECK constraints + unique/secondary
--   indexes as the primary table. Differences:
--     - sync_run_id is a plain uuid (no FK, no validation trigger) —
--       compare writes are not tied to wbr_sync_runs.
--     - No validate_wbr_business_sync_run trigger (that one enforces
--       source_type='windsor_business'; doesn't apply to SP-API A/B).
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.wbr_business_asin_daily__compare (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.wbr_profiles(id) ON DELETE CASCADE,
  sync_run_id uuid,
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

COMMENT ON TABLE public.wbr_business_asin_daily__compare
  IS 'Shadow table for A/B validation of direct SP-API business ingestion vs Windsor. Not read by reports; diffed against wbr_business_asin_daily.';

CREATE UNIQUE INDEX IF NOT EXISTS uq_wbr_business_asin_daily_compare_profile_date_asin
  ON public.wbr_business_asin_daily__compare(profile_id, report_date, child_asin);

CREATE INDEX IF NOT EXISTS idx_wbr_business_asin_daily_compare_profile_date
  ON public.wbr_business_asin_daily__compare(profile_id, report_date DESC);

CREATE INDEX IF NOT EXISTS idx_wbr_business_asin_daily_compare_profile_asin_date
  ON public.wbr_business_asin_daily__compare(profile_id, child_asin, report_date DESC);

DROP TRIGGER IF EXISTS update_wbr_business_asin_daily_compare_updated_at
  ON public.wbr_business_asin_daily__compare;
CREATE TRIGGER update_wbr_business_asin_daily_compare_updated_at
  BEFORE UPDATE ON public.wbr_business_asin_daily__compare
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.wbr_business_asin_daily__compare ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view WBR business ASIN daily compare"
  ON public.wbr_business_asin_daily__compare;
CREATE POLICY "Admins can view WBR business ASIN daily compare"
  ON public.wbr_business_asin_daily__compare FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage WBR business ASIN daily compare"
  ON public.wbr_business_asin_daily__compare;
CREATE POLICY "Admins can manage WBR business ASIN daily compare"
  ON public.wbr_business_asin_daily__compare FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));
