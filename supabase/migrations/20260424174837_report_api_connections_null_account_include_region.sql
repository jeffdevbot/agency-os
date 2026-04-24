-- Follow-up to Slice 3.5a-region: widen the null-external-account partial unique
-- index on report_api_connections to include region_code. The prior index enforced
-- (client_id, provider) WHERE external_account_id IS NULL, which blocked a client
-- from having two connections for the same provider in different regions when
-- neither carries an external_account_id (today's Amazon Ads rows). Adding
-- region_code to the uniqueness key lets multi-region Ads connections coexist
-- while keeping the single-row-per-(client,provider,region) invariant.

DROP INDEX IF EXISTS public.uq_report_api_connections_client_provider_null_account;

CREATE UNIQUE INDEX uq_report_api_connections_client_provider_null_account
  ON public.report_api_connections (client_id, provider, region_code)
  WHERE (external_account_id IS NULL);
