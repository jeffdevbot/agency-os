-- =====================================================================
-- MIGRATION: Claim pending Monthly P&L async imports
-- Purpose:
--   Let worker processes atomically claim pending async imports using
--   FOR UPDATE SKIP LOCKED so multiple workers cannot process the same
--   import concurrently.
-- =====================================================================

CREATE OR REPLACE FUNCTION public.pnl_claim_pending_imports(
  p_limit integer DEFAULT 1
)
RETURNS SETOF public.monthly_pnl_imports
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
BEGIN
  RETURN QUERY
  WITH locked AS (
    SELECT mi.id
    FROM public.monthly_pnl_imports AS mi
    WHERE mi.source_type = 'amazon_transaction_upload'
      AND mi.import_status = 'pending'
      AND COALESCE((mi.raw_meta ->> 'async_import_v1')::boolean, false) = true
    ORDER BY mi.created_at
    FOR UPDATE SKIP LOCKED
    LIMIT GREATEST(COALESCE(p_limit, 1), 0)
  ),
  claimed AS (
    UPDATE public.monthly_pnl_imports AS mi
    SET
      import_status = 'running',
      started_at = COALESCE(mi.started_at, now()),
      error_message = NULL
    WHERE mi.id IN (SELECT id FROM locked)
    RETURNING mi.*
  )
  SELECT * FROM claimed ORDER BY created_at;
END;
$function$;

REVOKE ALL ON FUNCTION public.pnl_claim_pending_imports(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.pnl_claim_pending_imports(integer) TO authenticated;
GRANT EXECUTE ON FUNCTION public.pnl_claim_pending_imports(integer) TO service_role;
