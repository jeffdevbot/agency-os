-- =====================================================================
-- MIGRATION: WBR scope exclusions
-- Purpose:
--   Allow operators to explicitly exclude out-of-scope ASINs and campaigns
--   from WBR totals and unmapped-QA noise for managed-subset clients.
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.wbr_asin_exclusions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.wbr_profiles(id) ON DELETE CASCADE,
  child_asin text NOT NULL,
  exclusion_source text NOT NULL DEFAULT 'manual'
    CHECK (exclusion_source IN ('manual', 'imported')),
  exclusion_reason text,
  active boolean NOT NULL DEFAULT true,
  created_by uuid REFERENCES public.profiles(id),
  updated_by uuid REFERENCES public.profiles(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_wbr_asin_exclusions_profile_child_active
  ON public.wbr_asin_exclusions(profile_id, child_asin)
  WHERE active = true;

CREATE INDEX IF NOT EXISTS idx_wbr_asin_exclusions_profile_created
  ON public.wbr_asin_exclusions(profile_id, created_at DESC);

DROP TRIGGER IF EXISTS update_wbr_asin_exclusions_updated_at ON public.wbr_asin_exclusions;
CREATE TRIGGER update_wbr_asin_exclusions_updated_at
  BEFORE UPDATE ON public.wbr_asin_exclusions
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.wbr_asin_exclusions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view WBR ASIN exclusions" ON public.wbr_asin_exclusions;
CREATE POLICY "Admins can view WBR ASIN exclusions"
  ON public.wbr_asin_exclusions FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage WBR ASIN exclusions" ON public.wbr_asin_exclusions;
CREATE POLICY "Admins can manage WBR ASIN exclusions"
  ON public.wbr_asin_exclusions FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

CREATE TABLE IF NOT EXISTS public.wbr_campaign_exclusions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.wbr_profiles(id) ON DELETE CASCADE,
  campaign_name text NOT NULL,
  exclusion_source text NOT NULL DEFAULT 'manual'
    CHECK (exclusion_source IN ('manual', 'imported')),
  exclusion_reason text,
  active boolean NOT NULL DEFAULT true,
  created_by uuid REFERENCES public.profiles(id),
  updated_by uuid REFERENCES public.profiles(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_wbr_campaign_exclusions_profile_campaign_active
  ON public.wbr_campaign_exclusions(profile_id, campaign_name)
  WHERE active = true;

CREATE INDEX IF NOT EXISTS idx_wbr_campaign_exclusions_profile_created
  ON public.wbr_campaign_exclusions(profile_id, created_at DESC);

DROP TRIGGER IF EXISTS update_wbr_campaign_exclusions_updated_at ON public.wbr_campaign_exclusions;
CREATE TRIGGER update_wbr_campaign_exclusions_updated_at
  BEFORE UPDATE ON public.wbr_campaign_exclusions
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.wbr_campaign_exclusions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view WBR campaign exclusions" ON public.wbr_campaign_exclusions;
CREATE POLICY "Admins can view WBR campaign exclusions"
  ON public.wbr_campaign_exclusions FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage WBR campaign exclusions" ON public.wbr_campaign_exclusions;
CREATE POLICY "Admins can manage WBR campaign exclusions"
  ON public.wbr_campaign_exclusions FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));
