-- =====================================================================
-- MIGRATION: Add Monthly P&L bucket-total aggregation RPC
-- Purpose:
--   Aggregate active ledger entries server-side for report rendering so
--   the report endpoint does not need to page through every ledger row.
-- =====================================================================

CREATE OR REPLACE FUNCTION public.pnl_report_bucket_totals(
  p_profile_id uuid,
  p_start_month date,
  p_end_month date
) RETURNS TABLE (
  entry_month date,
  ledger_bucket text,
  amount numeric
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT
    le.entry_month,
    le.ledger_bucket,
    SUM(le.amount) AS amount
  FROM public.monthly_pnl_ledger_entries AS le
  INNER JOIN public.monthly_pnl_import_months AS im
    ON im.id = le.import_month_id
  WHERE le.profile_id = p_profile_id
    AND le.entry_month >= p_start_month
    AND le.entry_month <= p_end_month
    AND im.is_active = true
  GROUP BY le.entry_month, le.ledger_bucket
  ORDER BY le.entry_month, le.ledger_bucket;
$$;

REVOKE ALL ON FUNCTION public.pnl_report_bucket_totals(uuid, date, date) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.pnl_report_bucket_totals(uuid, date, date) TO authenticated;
GRANT EXECUTE ON FUNCTION public.pnl_report_bucket_totals(uuid, date, date) TO service_role;
