-- =====================================================================
-- MIGRATION: WBR Amazon Ads OAuth connections
-- Purpose:
--   Securely store LWA refresh tokens for Amazon Ads API access,
--   separate from wbr_profiles to prevent accidental token leakage
--   through profile API responses.
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.wbr_amazon_ads_connections (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.wbr_profiles(id) ON DELETE CASCADE,
  amazon_ads_refresh_token text NOT NULL,
  lwa_account_hint text,
  connected_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT wbr_amazon_ads_connections_profile_id_key UNIQUE (profile_id)
);

COMMENT ON TABLE public.wbr_amazon_ads_connections
  IS 'Stores LWA refresh tokens for Amazon Ads API access. One row per WBR profile.';

COMMENT ON COLUMN public.wbr_amazon_ads_connections.amazon_ads_refresh_token
  IS 'LWA refresh token obtained via OAuth authorization code grant. Does not expire.';

COMMENT ON COLUMN public.wbr_amazon_ads_connections.lwa_account_hint
  IS 'Optional display hint (e.g. email) from the LWA token response for debugging.';

-- updated_at trigger
DROP TRIGGER IF EXISTS update_wbr_amazon_ads_connections_updated_at
  ON public.wbr_amazon_ads_connections;
CREATE TRIGGER update_wbr_amazon_ads_connections_updated_at
  BEFORE UPDATE ON public.wbr_amazon_ads_connections
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- RLS
ALTER TABLE public.wbr_amazon_ads_connections ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view WBR Amazon Ads connections"
  ON public.wbr_amazon_ads_connections;
CREATE POLICY "Admins can view WBR Amazon Ads connections"
  ON public.wbr_amazon_ads_connections FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage WBR Amazon Ads connections"
  ON public.wbr_amazon_ads_connections;
CREATE POLICY "Admins can manage WBR Amazon Ads connections"
  ON public.wbr_amazon_ads_connections FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));
