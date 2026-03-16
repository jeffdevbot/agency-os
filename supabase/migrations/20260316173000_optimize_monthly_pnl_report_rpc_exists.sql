-- =====================================================================
-- MIGRATION: Optimize Monthly P&L report RPC for wider month ranges
-- Purpose:
--   Keep the P&L report RPC under PostgREST statement timeouts on
--   broader ranges like "Last 12 Months". The prior function shape
--   could still time out even with active-month filtering.
-- =====================================================================

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
    le.entry_month,
    le.ledger_bucket,
    SUM(le.amount) AS amount
  FROM public.monthly_pnl_ledger_entries AS le
  WHERE le.profile_id = p_profile_id
    AND le.entry_month >= p_start_month
    AND le.entry_month <= p_end_month
    AND EXISTS (
      SELECT 1
      FROM public.monthly_pnl_import_months AS im
      WHERE im.id = le.import_month_id
        AND im.profile_id = p_profile_id
        AND im.is_active = true
        AND im.entry_month >= p_start_month
        AND im.entry_month <= p_end_month
    )
  GROUP BY le.entry_month, le.ledger_bucket
  ORDER BY le.entry_month, le.ledger_bucket;
$function$;
