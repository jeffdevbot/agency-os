-- =====================================================================
-- MIGRATION: Harden STR fact ad-product metadata
-- Purpose:
--   Ensure search_term_daily_facts always preserves the first-class
--   ad_product / report_type_id metadata added in the per-product STR
--   foundation work.
--
-- Why:
--   Fresh SP fact rows inserted on 2026-03-27 were observed with
--   ad_product/report_type_id = NULL even though the parent sync run and
--   source_payload carried the values. This migration:
--     1. backfills any existing null rows from source_payload or sync runs
--     2. adds a BEFORE INSERT/UPDATE trigger so future rows self-heal
-- =====================================================================

UPDATE public.search_term_daily_facts AS f
SET
  ad_product = COALESCE(
    NULLIF(f.ad_product, ''),
    NULLIF(f.source_payload ->> '__ad_product', ''),
    NULLIF(r.ad_product, '')
  ),
  report_type_id = COALESCE(
    NULLIF(f.report_type_id, ''),
    NULLIF(f.source_payload ->> '__report_type_id', ''),
    NULLIF(r.report_type_id, '')
  )
FROM public.wbr_sync_runs AS r
WHERE f.sync_run_id = r.id
  AND (
    f.ad_product IS NULL
    OR f.ad_product = ''
    OR f.report_type_id IS NULL
    OR f.report_type_id = ''
  );

UPDATE public.search_term_daily_facts AS f
SET
  ad_product = COALESCE(
    NULLIF(f.ad_product, ''),
    NULLIF(f.source_payload ->> '__ad_product', '')
  ),
  report_type_id = COALESCE(
    NULLIF(f.report_type_id, ''),
    NULLIF(f.source_payload ->> '__report_type_id', '')
  )
WHERE f.sync_run_id IS NULL
  AND (
    f.ad_product IS NULL
    OR f.ad_product = ''
    OR f.report_type_id IS NULL
    OR f.report_type_id = ''
  );

CREATE OR REPLACE FUNCTION public.populate_search_term_fact_report_metadata()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  run_ad_product text;
  run_report_type_id text;
BEGIN
  IF NEW.sync_run_id IS NOT NULL THEN
    SELECT
      NULLIF(ad_product, ''),
      NULLIF(report_type_id, '')
    INTO run_ad_product, run_report_type_id
    FROM public.wbr_sync_runs
    WHERE id = NEW.sync_run_id;
  END IF;

  NEW.ad_product := COALESCE(
    NULLIF(NEW.ad_product, ''),
    NULLIF(NEW.source_payload ->> '__ad_product', ''),
    run_ad_product
  );

  NEW.report_type_id := COALESCE(
    NULLIF(NEW.report_type_id, ''),
    NULLIF(NEW.source_payload ->> '__report_type_id', ''),
    run_report_type_id
  );

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS populate_search_term_fact_report_metadata
  ON public.search_term_daily_facts;

CREATE TRIGGER populate_search_term_fact_report_metadata
  BEFORE INSERT OR UPDATE ON public.search_term_daily_facts
  FOR EACH ROW
  EXECUTE FUNCTION public.populate_search_term_fact_report_metadata();
