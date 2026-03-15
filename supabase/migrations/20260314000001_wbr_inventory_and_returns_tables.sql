-- =====================================================================
-- MIGRATION: WBR Section 3 – Inventory snapshots + Returns daily
-- Purpose:
--   Add fact tables for inventory (snapshot grain) and returns (daily
--   grain) so Section 3 of the WBR can render inventory health and
--   return-rate metrics alongside Sections 1 and 2.
-- =====================================================================

-- -----------------------------------------------------------------
-- 1. wbr_inventory_asin_snapshots
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.wbr_inventory_asin_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.wbr_profiles(id) ON DELETE CASCADE,
  sync_run_id uuid REFERENCES public.wbr_sync_runs(id) ON DELETE SET NULL,
  snapshot_date date NOT NULL,
  child_asin text NOT NULL,
  instock integer NOT NULL DEFAULT 0,
  working integer NOT NULL DEFAULT 0,
  reserved_quantity integer NOT NULL DEFAULT 0,
  fc_transfer integer NOT NULL DEFAULT 0,
  fc_processing integer NOT NULL DEFAULT 0,
  reserved_plus_fc_transfer integer NOT NULL DEFAULT 0,
  receiving integer NOT NULL DEFAULT 0,
  intransit integer NOT NULL DEFAULT 0,
  receiving_plus_intransit integer NOT NULL DEFAULT 0,
  source_row_count integer NOT NULL DEFAULT 0,
  source_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT wbr_inventory_asin_snapshots_unique
    UNIQUE (profile_id, snapshot_date, child_asin)
);

COMMENT ON TABLE public.wbr_inventory_asin_snapshots
  IS 'Point-in-time inventory quantities per child ASIN, sourced from Windsor AFN inventory + restock feeds.';

-- updated_at trigger
DROP TRIGGER IF EXISTS update_wbr_inventory_asin_snapshots_updated_at
  ON public.wbr_inventory_asin_snapshots;
CREATE TRIGGER update_wbr_inventory_asin_snapshots_updated_at
  BEFORE UPDATE ON public.wbr_inventory_asin_snapshots
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- RLS
ALTER TABLE public.wbr_inventory_asin_snapshots ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view WBR inventory snapshots"
  ON public.wbr_inventory_asin_snapshots;
CREATE POLICY "Admins can view WBR inventory snapshots"
  ON public.wbr_inventory_asin_snapshots FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage WBR inventory snapshots"
  ON public.wbr_inventory_asin_snapshots;
CREATE POLICY "Admins can manage WBR inventory snapshots"
  ON public.wbr_inventory_asin_snapshots FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

-- -----------------------------------------------------------------
-- 2. wbr_returns_asin_daily
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.wbr_returns_asin_daily (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.wbr_profiles(id) ON DELETE CASCADE,
  sync_run_id uuid REFERENCES public.wbr_sync_runs(id) ON DELETE SET NULL,
  return_date date NOT NULL,
  child_asin text NOT NULL,
  return_units integer NOT NULL DEFAULT 0,
  source_row_count integer NOT NULL DEFAULT 0,
  source_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT wbr_returns_asin_daily_unique
    UNIQUE (profile_id, return_date, child_asin)
);

COMMENT ON TABLE public.wbr_returns_asin_daily
  IS 'Daily return-event quantities per child ASIN, sourced from Windsor FBA customer returns feed.';

-- updated_at trigger
DROP TRIGGER IF EXISTS update_wbr_returns_asin_daily_updated_at
  ON public.wbr_returns_asin_daily;
CREATE TRIGGER update_wbr_returns_asin_daily_updated_at
  BEFORE UPDATE ON public.wbr_returns_asin_daily
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- RLS
ALTER TABLE public.wbr_returns_asin_daily ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view WBR returns daily"
  ON public.wbr_returns_asin_daily;
CREATE POLICY "Admins can view WBR returns daily"
  ON public.wbr_returns_asin_daily FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage WBR returns daily"
  ON public.wbr_returns_asin_daily;
CREATE POLICY "Admins can manage WBR returns daily"
  ON public.wbr_returns_asin_daily FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));
