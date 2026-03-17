-- Add fixed SKU COGS and per-import-month SKU unit summaries for Monthly P&L.

-- ---------------------------------------------------------------------
-- 1) Monthly P&L sold units by import month + SKU
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.monthly_pnl_import_month_sku_units (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  import_id uuid NOT NULL REFERENCES public.monthly_pnl_imports(id) ON DELETE CASCADE,
  import_month_id uuid NOT NULL REFERENCES public.monthly_pnl_import_months(id) ON DELETE CASCADE,
  profile_id uuid NOT NULL REFERENCES public.monthly_pnl_profiles(id) ON DELETE CASCADE,
  entry_month date NOT NULL,
  sku text NOT NULL,
  net_units integer NOT NULL,
  order_row_count integer NOT NULL DEFAULT 0,
  refund_row_count integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_monthly_pnl_import_month_sku_units_month_sku
  ON public.monthly_pnl_import_month_sku_units(import_month_id, sku);

CREATE INDEX IF NOT EXISTS idx_monthly_pnl_import_month_sku_units_profile_month
  ON public.monthly_pnl_import_month_sku_units(profile_id, entry_month, import_month_id);

DROP TRIGGER IF EXISTS update_monthly_pnl_import_month_sku_units_updated_at
  ON public.monthly_pnl_import_month_sku_units;
CREATE TRIGGER update_monthly_pnl_import_month_sku_units_updated_at
  BEFORE UPDATE ON public.monthly_pnl_import_month_sku_units
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.monthly_pnl_import_month_sku_units ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view P&L import month SKU units"
  ON public.monthly_pnl_import_month_sku_units;
CREATE POLICY "Admins can view P&L import month SKU units"
  ON public.monthly_pnl_import_month_sku_units FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage P&L import month SKU units"
  ON public.monthly_pnl_import_month_sku_units;
CREATE POLICY "Admins can manage P&L import month SKU units"
  ON public.monthly_pnl_import_month_sku_units FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

-- ---------------------------------------------------------------------
-- 2) Monthly P&L fixed unit cost per SKU
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.monthly_pnl_sku_cogs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.monthly_pnl_profiles(id) ON DELETE CASCADE,
  sku text NOT NULL,
  asin text,
  unit_cost numeric(18, 4) NOT NULL,
  currency_code text NOT NULL DEFAULT 'USD',
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_monthly_pnl_sku_cogs_profile_sku
  ON public.monthly_pnl_sku_cogs(profile_id, sku);

CREATE INDEX IF NOT EXISTS idx_monthly_pnl_sku_cogs_profile
  ON public.monthly_pnl_sku_cogs(profile_id);

DROP TRIGGER IF EXISTS update_monthly_pnl_sku_cogs_updated_at
  ON public.monthly_pnl_sku_cogs;
CREATE TRIGGER update_monthly_pnl_sku_cogs_updated_at
  BEFORE UPDATE ON public.monthly_pnl_sku_cogs
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.monthly_pnl_sku_cogs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view P&L SKU COGS"
  ON public.monthly_pnl_sku_cogs;
CREATE POLICY "Admins can view P&L SKU COGS"
  ON public.monthly_pnl_sku_cogs FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage P&L SKU COGS"
  ON public.monthly_pnl_sku_cogs;
CREATE POLICY "Admins can manage P&L SKU COGS"
  ON public.monthly_pnl_sku_cogs FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

-- ---------------------------------------------------------------------
-- 3) Backfill sold units from existing raw rows
-- ---------------------------------------------------------------------
WITH parsed_rows AS (
  SELECT
    rr.import_id,
    rr.import_month_id,
    rr.profile_id,
    im.entry_month,
    btrim(COALESCE(rr.sku, '')) AS sku,
    lower(COALESCE(rr.raw_type, '')) AS raw_type,
    CASE
      WHEN replace(btrim(COALESCE(payload_fields.quantity_text, '')), ',', '') ~ '^-?\d+$'
        THEN replace(btrim(COALESCE(payload_fields.quantity_text, '')), ',', '')::integer
      ELSE 0
    END AS quantity,
    CASE
      WHEN replace(btrim(COALESCE(payload_fields.product_sales_text, '')), ',', '') ~ '^-?\d+(\.\d+)?$'
        THEN replace(btrim(COALESCE(payload_fields.product_sales_text, '')), ',', '')::numeric
      ELSE 0::numeric
    END AS product_sales
  FROM public.monthly_pnl_raw_rows AS rr
  JOIN public.monthly_pnl_import_months AS im
    ON im.id = rr.import_month_id
  LEFT JOIN LATERAL (
    SELECT
      max(
        CASE
          WHEN regexp_replace(lower(key), '[^a-z0-9/]+', '', 'g') IN ('quantity', 'qty')
            THEN value
          ELSE NULL
        END
      ) AS quantity_text,
      max(
        CASE
          WHEN regexp_replace(lower(key), '[^a-z0-9/]+', '', 'g') = 'productsales'
            THEN value
          ELSE NULL
        END
      ) AS product_sales_text
    FROM jsonb_each_text(COALESCE(rr.raw_payload, '{}'::jsonb))
  ) AS payload_fields ON TRUE
  WHERE rr.source_type = 'amazon_transaction_upload'
),
signed_rows AS (
  SELECT
    import_id,
    import_month_id,
    profile_id,
    entry_month,
    sku,
    CASE
      WHEN sku <> '' AND quantity > 0 AND raw_type = 'order' AND product_sales > 0
        THEN quantity
      WHEN sku <> '' AND quantity > 0 AND raw_type = 'refund' AND product_sales < 0
        THEN -quantity
      ELSE 0
    END AS signed_units,
    CASE
      WHEN sku <> '' AND quantity > 0 AND raw_type = 'order' AND product_sales > 0
        THEN 1
      ELSE 0
    END AS order_row_count,
    CASE
      WHEN sku <> '' AND quantity > 0 AND raw_type = 'refund' AND product_sales < 0
        THEN 1
      ELSE 0
    END AS refund_row_count
  FROM parsed_rows
),
aggregated AS (
  SELECT
    import_id,
    import_month_id,
    profile_id,
    entry_month,
    sku,
    SUM(signed_units)::integer AS net_units,
    SUM(order_row_count)::integer AS order_row_count,
    SUM(refund_row_count)::integer AS refund_row_count
  FROM signed_rows
  WHERE signed_units <> 0
  GROUP BY 1, 2, 3, 4, 5
)
INSERT INTO public.monthly_pnl_import_month_sku_units (
  import_id,
  import_month_id,
  profile_id,
  entry_month,
  sku,
  net_units,
  order_row_count,
  refund_row_count
)
SELECT
  import_id,
  import_month_id,
  profile_id,
  entry_month,
  sku,
  net_units,
  order_row_count,
  refund_row_count
FROM aggregated
ON CONFLICT (import_month_id, sku) DO UPDATE
SET
  net_units = EXCLUDED.net_units,
  order_row_count = EXCLUDED.order_row_count,
  refund_row_count = EXCLUDED.refund_row_count,
  updated_at = now();
