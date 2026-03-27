-- =====================================================================
-- MIGRATION: STR ad-product foundation
-- Purpose:
--   Prepare Search Term Automation for per-ad-product operational lanes
--   without changing the current live Sponsored Products behaviour.
--
--   Adds:
--   - separate nightly-sync flags for future SB / SD lanes
--   - first-class ad_product / report_type_id metadata on sync runs
--   - first-class ad_product / report_type_id metadata on stored STR facts
--
--   Existing SP data is backfilled so the new columns are immediately
--   queryable for current validated runs.
-- =====================================================================

ALTER TABLE public.wbr_profiles
  ADD COLUMN IF NOT EXISTS search_term_sb_auto_sync_enabled boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS search_term_sd_auto_sync_enabled boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.wbr_profiles.search_term_auto_sync_enabled
  IS 'When true, worker-sync runs the nightly Sponsored Products Amazon Ads search-term trailing-window refresh for this profile.';
COMMENT ON COLUMN public.wbr_profiles.search_term_sb_auto_sync_enabled
  IS 'Reserved for future Sponsored Brands search-term nightly refresh once the native report contract is validated.';
COMMENT ON COLUMN public.wbr_profiles.search_term_sd_auto_sync_enabled
  IS 'Reserved for future Sponsored Display-adjacent nightly refresh once the native report contract is validated.';

ALTER TABLE public.wbr_sync_runs
  ADD COLUMN IF NOT EXISTS ad_product text,
  ADD COLUMN IF NOT EXISTS report_type_id text;

COMMENT ON COLUMN public.wbr_sync_runs.ad_product
  IS 'Amazon Ads ad product for this sync run when applicable, e.g. SPONSORED_PRODUCTS.';
COMMENT ON COLUMN public.wbr_sync_runs.report_type_id
  IS 'Amazon Ads reportTypeId for this sync run when applicable, e.g. spSearchTerm.';

UPDATE public.wbr_sync_runs
SET
  ad_product = COALESCE(
    public.wbr_sync_runs.ad_product,
    public.wbr_sync_runs.request_meta ->> 'ad_product',
    public.wbr_sync_runs.request_meta -> 'report_definitions' -> 0 ->> 'ad_product',
    public.wbr_sync_runs.request_meta -> 'report_jobs' -> 0 ->> 'ad_product',
    CASE
      WHEN public.wbr_sync_runs.source_type = 'amazon_ads_search_terms' THEN 'SPONSORED_PRODUCTS'
      ELSE NULL
    END
  ),
  report_type_id = COALESCE(
    public.wbr_sync_runs.report_type_id,
    public.wbr_sync_runs.request_meta ->> 'report_type_id',
    public.wbr_sync_runs.request_meta -> 'report_definitions' -> 0 ->> 'report_type_id',
    public.wbr_sync_runs.request_meta -> 'report_jobs' -> 0 ->> 'report_type_id',
    CASE
      WHEN public.wbr_sync_runs.source_type = 'amazon_ads_search_terms' THEN 'spSearchTerm'
      ELSE NULL
    END
  )
WHERE public.wbr_sync_runs.source_type = 'amazon_ads_search_terms'
  AND (
    public.wbr_sync_runs.ad_product IS NULL
    OR public.wbr_sync_runs.report_type_id IS NULL
  );

CREATE INDEX IF NOT EXISTS idx_wbr_sync_runs_profile_source_ad_product_created
  ON public.wbr_sync_runs(profile_id, source_type, ad_product, created_at DESC);

ALTER TABLE public.search_term_daily_facts
  ADD COLUMN IF NOT EXISTS ad_product text,
  ADD COLUMN IF NOT EXISTS report_type_id text;

COMMENT ON COLUMN public.search_term_daily_facts.ad_product
  IS 'Amazon Ads ad product for the source fact row, e.g. SPONSORED_PRODUCTS.';
COMMENT ON COLUMN public.search_term_daily_facts.report_type_id
  IS 'Amazon Ads reportTypeId that produced the fact row, e.g. spSearchTerm.';

UPDATE public.search_term_daily_facts AS f
SET
  ad_product = COALESCE(
    f.ad_product,
    f.source_payload ->> '__ad_product',
    r.ad_product,
    CASE
      WHEN f.campaign_type = 'sponsored_products' THEN 'SPONSORED_PRODUCTS'
      ELSE NULL
    END
  ),
  report_type_id = COALESCE(
    f.report_type_id,
    f.source_payload ->> '__report_type_id',
    r.report_type_id,
    CASE
      WHEN f.campaign_type = 'sponsored_products' THEN 'spSearchTerm'
      ELSE NULL
    END
  )
FROM public.wbr_sync_runs AS r
WHERE f.sync_run_id = r.id
  AND (
    f.ad_product IS NULL
    OR f.report_type_id IS NULL
  );

UPDATE public.search_term_daily_facts AS f
SET
  ad_product = COALESCE(
    f.ad_product,
    CASE
      WHEN f.campaign_type = 'sponsored_products' THEN 'SPONSORED_PRODUCTS'
      ELSE NULL
    END
  ),
  report_type_id = COALESCE(
    f.report_type_id,
    CASE
      WHEN f.campaign_type = 'sponsored_products' THEN 'spSearchTerm'
      ELSE NULL
    END
  )
WHERE f.sync_run_id IS NULL
  AND (
    f.ad_product IS NULL
    OR f.report_type_id IS NULL
  );

CREATE INDEX IF NOT EXISTS idx_search_term_daily_facts_profile_ad_product_date
  ON public.search_term_daily_facts(profile_id, ad_product, report_date DESC);
