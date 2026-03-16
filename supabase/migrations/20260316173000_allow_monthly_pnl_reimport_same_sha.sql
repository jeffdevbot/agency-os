-- =====================================================================
-- MIGRATION: Allow Monthly P&L re-imports of the same transaction file
-- Purpose:
--   Permit operators to re-upload the same Amazon transaction report
--   after a successful import so corrected parser/mapping logic can
--   supersede prior month slices. Only a currently running import
--   should block the same file hash.
-- =====================================================================

DROP INDEX IF EXISTS public.uq_monthly_pnl_imports_profile_source_sha256;

CREATE UNIQUE INDEX uq_monthly_pnl_imports_profile_source_sha256
  ON public.monthly_pnl_imports(profile_id, source_type, source_file_sha256)
  WHERE source_file_sha256 IS NOT NULL
    AND import_status = 'running';
