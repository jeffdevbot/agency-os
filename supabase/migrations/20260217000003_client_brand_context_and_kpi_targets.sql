-- =====================================================================
-- MIGRATION: Client/Brand context fields + marketplace KPI targets
-- Purpose:
--   1) Add structured context fields for agency_clients/brands.
--   2) Add per-marketplace KPI target table with monthly/annual periods.
--
-- Target examples supported:
--   - TACOS target for US marketplace in Jan 2026
--   - ACOS target for CA marketplace in Feb 2026
--   - Annual sales target for 2026 per marketplace
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) Context fields for natural-language profile updates
-- ---------------------------------------------------------------------
ALTER TABLE public.agency_clients
  ADD COLUMN IF NOT EXISTS context_summary text,
  ADD COLUMN IF NOT EXISTS target_audience text,
  ADD COLUMN IF NOT EXISTS positioning_notes text;

ALTER TABLE public.brands
  ADD COLUMN IF NOT EXISTS context_summary text,
  ADD COLUMN IF NOT EXISTS target_audience text,
  ADD COLUMN IF NOT EXISTS positioning_notes text;

-- ---------------------------------------------------------------------
-- 2) Marketplace KPI targets (TACOS/ACOS + sales target)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.brand_market_kpi_targets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

  brand_id uuid NOT NULL REFERENCES public.brands(id) ON DELETE CASCADE,

  -- Required marketplace scope for all KPI targets.
  marketplace_code text NOT NULL,

  -- Period model:
  -- monthly => period_start = first day of month (e.g. 2026-01-01)
  -- annual  => period_start = Jan 1 of year (e.g. 2026-01-01)
  period_granularity text NOT NULL CHECK (period_granularity IN ('monthly', 'annual')),
  period_start date NOT NULL,

  -- Optional KPI targets
  tacos_target_pct numeric(6,2),
  acos_target_pct numeric(6,2),

  -- Optional sales target
  sales_target numeric(14,2),
  sales_currency text,

  notes text,
  active boolean NOT NULL DEFAULT true,

  created_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  updated_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT brand_market_kpi_targets_marketplace_upper_chk
    CHECK (marketplace_code = upper(marketplace_code)),

  CONSTRAINT brand_market_kpi_targets_tacos_range_chk
    CHECK (tacos_target_pct IS NULL OR (tacos_target_pct >= 0 AND tacos_target_pct <= 100)),

  CONSTRAINT brand_market_kpi_targets_acos_range_chk
    CHECK (acos_target_pct IS NULL OR (acos_target_pct >= 0 AND acos_target_pct <= 100)),

  CONSTRAINT brand_market_kpi_targets_sales_nonnegative_chk
    CHECK (sales_target IS NULL OR sales_target >= 0),

  CONSTRAINT brand_market_kpi_targets_currency_chk
    CHECK (sales_currency IS NULL OR sales_currency ~ '^[A-Z]{3}$'),

  CONSTRAINT brand_market_kpi_targets_sales_currency_required_chk
    CHECK (sales_target IS NULL OR sales_currency IS NOT NULL),

  CONSTRAINT brand_market_kpi_targets_at_least_one_metric_chk
    CHECK (
      tacos_target_pct IS NOT NULL
      OR acos_target_pct IS NOT NULL
      OR sales_target IS NOT NULL
    ),

  CONSTRAINT brand_market_kpi_targets_period_start_chk
    CHECK (
      (period_granularity = 'monthly' AND extract(day from period_start) = 1)
      OR
      (
        period_granularity = 'annual'
        AND extract(month from period_start) = 1
        AND extract(day from period_start) = 1
      )
    )
);

-- Prevent duplicate active targets for same scope/period
CREATE UNIQUE INDEX IF NOT EXISTS idx_brand_market_kpi_targets_unique_active_scope
  ON public.brand_market_kpi_targets (
    brand_id,
    marketplace_code,
    period_granularity,
    period_start
  )
  WHERE active = true;

CREATE INDEX IF NOT EXISTS idx_brand_market_kpi_targets_brand_period
  ON public.brand_market_kpi_targets (brand_id, period_start DESC);

CREATE INDEX IF NOT EXISTS idx_brand_market_kpi_targets_market_period
  ON public.brand_market_kpi_targets (marketplace_code, period_start DESC);

CREATE INDEX IF NOT EXISTS idx_brand_market_kpi_targets_active
  ON public.brand_market_kpi_targets (active)
  WHERE active = true;

-- ---------------------------------------------------------------------
-- 3) updated_at trigger
-- ---------------------------------------------------------------------
DROP TRIGGER IF EXISTS update_brand_market_kpi_targets_updated_at ON public.brand_market_kpi_targets;
CREATE TRIGGER update_brand_market_kpi_targets_updated_at
  BEFORE UPDATE ON public.brand_market_kpi_targets
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ---------------------------------------------------------------------
-- 4) RLS + policies
-- ---------------------------------------------------------------------
ALTER TABLE public.brand_market_kpi_targets ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Authenticated users can view brand market KPI targets" ON public.brand_market_kpi_targets;
CREATE POLICY "Authenticated users can view brand market KPI targets"
  ON public.brand_market_kpi_targets FOR SELECT TO authenticated
  USING (true);

DROP POLICY IF EXISTS "Only admins can manage brand market KPI targets" ON public.brand_market_kpi_targets;
CREATE POLICY "Only admins can manage brand market KPI targets"
  ON public.brand_market_kpi_targets FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));
