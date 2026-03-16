-- =====================================================================
-- MIGRATION: Optimize Monthly P&L report RPC for active-month queries
-- Purpose:
--   Prevent report aggregation from sequentially scanning every historical
--   ledger row for a profile. Reports only read active month slices, so
--   index and query by import_month_id directly.
-- =====================================================================

CREATE INDEX IF NOT EXISTS idx_monthly_pnl_ledger_import_month_entry_bucket
  ON public.monthly_pnl_ledger_entries(import_month_id, entry_month, ledger_bucket);

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
  WITH active_months AS (
    SELECT id
    FROM public.monthly_pnl_import_months
    WHERE profile_id = p_profile_id
      AND is_active = true
      AND entry_month >= p_start_month
      AND entry_month <= p_end_month
  )
  SELECT
    le.entry_month,
    le.ledger_bucket,
    SUM(le.amount) AS amount
  FROM public.monthly_pnl_ledger_entries AS le
  INNER JOIN active_months AS am
    ON am.id = le.import_month_id
  GROUP BY le.entry_month, le.ledger_bucket
  ORDER BY le.entry_month, le.ledger_bucket;
$function$;
