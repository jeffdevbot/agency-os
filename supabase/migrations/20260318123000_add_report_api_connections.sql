-- =====================================================================
-- MIGRATION: Shared report API connections
-- Purpose:
--   Create a shared connection store for report-level external account auth.
--   Day one supports Amazon Ads and Amazon Seller API connections keyed by
--   client_id so WBR and Monthly P&L can consume shared credentials later.
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.report_api_connections (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id uuid NOT NULL REFERENCES public.agency_clients(id) ON DELETE RESTRICT,
  provider text NOT NULL
    CHECK (provider IN ('amazon_ads', 'amazon_spapi')),
  connection_status text NOT NULL DEFAULT 'connected'
    CHECK (connection_status IN ('connected', 'error', 'revoked')),
  external_account_id text,
  refresh_token text,
  region_code text
    CHECK (region_code IS NULL OR region_code IN ('NA', 'EU', 'FE')),
  access_meta jsonb NOT NULL DEFAULT '{}'::jsonb,
  connected_at timestamptz,
  last_validated_at timestamptz,
  last_error text,
  created_by uuid REFERENCES public.profiles(id),
  updated_by uuid REFERENCES public.profiles(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.report_api_connections
  IS 'Shared external API/report authorization state keyed to agency client.';

COMMENT ON COLUMN public.report_api_connections.refresh_token
  IS 'Provider refresh token stored as plaintext for now; encryption is a tracked follow-up.';

COMMENT ON COLUMN public.report_api_connections.access_meta
  IS 'Provider-specific metadata such as hints, legacy source markers, and validation details.';

CREATE UNIQUE INDEX IF NOT EXISTS uq_report_api_connections_client_provider
  ON public.report_api_connections(client_id, provider);

CREATE INDEX IF NOT EXISTS idx_report_api_connections_provider_status
  ON public.report_api_connections(provider, connection_status);

DROP TRIGGER IF EXISTS update_report_api_connections_updated_at
  ON public.report_api_connections;
CREATE TRIGGER update_report_api_connections_updated_at
  BEFORE UPDATE ON public.report_api_connections
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.report_api_connections ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view report API connections"
  ON public.report_api_connections;
CREATE POLICY "Admins can view report API connections"
  ON public.report_api_connections FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage report API connections"
  ON public.report_api_connections;
CREATE POLICY "Admins can manage report API connections"
  ON public.report_api_connections FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));
