-- =====================================================================
-- MIGRATION: Expand WBR sync run source types for Section 3
-- Purpose:
--   Allow Section 3 Windsor inventory and returns sync runs to be
--   recorded in public.wbr_sync_runs.
-- =====================================================================

ALTER TABLE public.wbr_sync_runs
  DROP CONSTRAINT IF EXISTS wbr_sync_runs_source_type_check;

ALTER TABLE public.wbr_sync_runs
  ADD CONSTRAINT wbr_sync_runs_source_type_check
  CHECK (
    source_type IN (
      'windsor_business',
      'windsor_inventory',
      'windsor_returns',
      'amazon_ads',
      'pacvue_import',
      'listing_import'
    )
  );
