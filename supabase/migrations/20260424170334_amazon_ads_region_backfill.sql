-- Slice 3.5a-region: Backfill Amazon Ads rows to region_code='NA' and enforce NOT NULL.
-- Context: Amazon Ads connections were created before region was modeled (OAuth state
-- didn't carry region, upsert didn't write region_code, API helper was hardcoded to
-- advertising-api.amazon.com). All existing Ads rows therefore ran through the NA
-- endpoint. This migration backfills them explicitly and enforces NOT NULL so future
-- rows must carry region. Slice 3a's partial unique indexes on (client_id, provider)
-- and (client_id, provider, external_account_id) do not reference region_code, so
-- NOT NULL does not alter their semantics.

UPDATE public.report_api_connections
SET region_code = 'NA'
WHERE provider = 'amazon_ads'
  AND region_code IS NULL;

ALTER TABLE public.report_api_connections
  ALTER COLUMN region_code SET NOT NULL;
