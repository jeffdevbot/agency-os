-- =====================================================================
-- MIGRATION: Add Monthly P&L import-month bucket totals
-- Purpose:
--   Precompute per-month bucket totals once at import time so report reads
--   no longer aggregate raw ledger rows on every request.
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.monthly_pnl_import_month_bucket_totals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.monthly_pnl_profiles(id) ON DELETE CASCADE,
  import_id uuid NOT NULL REFERENCES public.monthly_pnl_imports(id) ON DELETE CASCADE,
  import_month_id uuid NOT NULL REFERENCES public.monthly_pnl_import_months(id) ON DELETE CASCADE,
  entry_month date NOT NULL,
  ledger_bucket text NOT NULL,
  amount numeric(18,2) NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_monthly_pnl_import_month_bucket_totals_month_bucket
  ON public.monthly_pnl_import_month_bucket_totals(import_month_id, ledger_bucket);

CREATE INDEX IF NOT EXISTS idx_monthly_pnl_import_month_bucket_totals_profile_month
  ON public.monthly_pnl_import_month_bucket_totals(profile_id, entry_month, import_month_id);

DROP TRIGGER IF EXISTS update_monthly_pnl_import_month_bucket_totals_updated_at
  ON public.monthly_pnl_import_month_bucket_totals;
CREATE TRIGGER update_monthly_pnl_import_month_bucket_totals_updated_at
  BEFORE UPDATE ON public.monthly_pnl_import_month_bucket_totals
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.monthly_pnl_import_month_bucket_totals ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view P&L import month bucket totals"
  ON public.monthly_pnl_import_month_bucket_totals;
CREATE POLICY "Admins can view P&L import month bucket totals"
  ON public.monthly_pnl_import_month_bucket_totals FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage P&L import month bucket totals"
  ON public.monthly_pnl_import_month_bucket_totals;
CREATE POLICY "Admins can manage P&L import month bucket totals"
  ON public.monthly_pnl_import_month_bucket_totals FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

INSERT INTO public.monthly_pnl_import_month_bucket_totals (
  profile_id,
  import_id,
  import_month_id,
  entry_month,
  ledger_bucket,
  amount
)
SELECT
  le.profile_id,
  le.import_id,
  le.import_month_id,
  le.entry_month,
  le.ledger_bucket,
  SUM(le.amount) AS amount
FROM public.monthly_pnl_ledger_entries AS le
WHERE le.import_month_id IS NOT NULL
GROUP BY
  le.profile_id,
  le.import_id,
  le.import_month_id,
  le.entry_month,
  le.ledger_bucket
ON CONFLICT (import_month_id, ledger_bucket) DO UPDATE
SET
  profile_id = EXCLUDED.profile_id,
  import_id = EXCLUDED.import_id,
  entry_month = EXCLUDED.entry_month,
  amount = EXCLUDED.amount,
  updated_at = now();

CREATE OR REPLACE FUNCTION public.pnl_report_bucket_totals(
  p_profile_id uuid,
  p_start_month date,
  p_end_month date
)
RETURNS TABLE(entry_month date, ledger_bucket text, amount numeric)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
  SELECT
    bt.entry_month,
    bt.ledger_bucket,
    SUM(bt.amount) AS amount
  FROM public.monthly_pnl_import_month_bucket_totals AS bt
  INNER JOIN public.monthly_pnl_import_months AS im
    ON im.id = bt.import_month_id
  WHERE bt.profile_id = p_profile_id
    AND bt.entry_month >= p_start_month
    AND bt.entry_month <= p_end_month
    AND im.is_active = true
  GROUP BY bt.entry_month, bt.ledger_bucket
  ORDER BY bt.entry_month, bt.ledger_bucket;
$function$;

REVOKE ALL ON FUNCTION public.pnl_report_bucket_totals(uuid, date, date) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.pnl_report_bucket_totals(uuid, date, date) TO authenticated;
GRANT EXECUTE ON FUNCTION public.pnl_report_bucket_totals(uuid, date, date) TO service_role;
