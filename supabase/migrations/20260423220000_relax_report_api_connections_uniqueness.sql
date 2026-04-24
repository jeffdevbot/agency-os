-- =====================================================================
-- MIGRATION: Relax report_api_connections uniqueness (Option B)
-- Allow multiple external accounts per (client, provider) via partial
-- unique indexes. Retains a "one pending row per (client,provider)"
-- invariant for rows with NULL external_account_id. Code adaptation
-- to upsert/select paths lands in a follow-up slice.
-- =====================================================================

DROP INDEX IF EXISTS public.uq_report_api_connections_client_provider;

CREATE UNIQUE INDEX IF NOT EXISTS uq_report_api_connections_client_provider_account
  ON public.report_api_connections (client_id, provider, external_account_id)
  WHERE external_account_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_report_api_connections_client_provider_null_account
  ON public.report_api_connections (client_id, provider)
  WHERE external_account_id IS NULL;
