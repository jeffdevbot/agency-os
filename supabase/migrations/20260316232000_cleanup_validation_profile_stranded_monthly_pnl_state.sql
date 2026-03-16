-- =====================================================================
-- MIGRATION: Clean up stranded validation-profile Monthly P&L state
-- Purpose:
--   Deactivate orphaned active month slices left behind by failed
--   multi-month uploads on the validation profile and mark the stranded
--   retry import as error so reports and polling stop treating it as live.
-- =====================================================================

UPDATE public.monthly_pnl_import_months
SET
  is_active = false,
  updated_at = now()
WHERE profile_id = 'c8e854cf-b989-4e3f-8cf4-58a43507c67a'
  AND (
    (import_id = '65d24015-7602-49f2-8c7f-2b9f29bab56a' AND entry_month = DATE '2025-01-01')
    OR (import_id = '0fe50885-fce4-48ec-afa6-a9dce5cef716' AND entry_month = DATE '2025-04-01')
    OR (import_id = '37b0af74-0e7f-411a-b6aa-1c82b5cd827a' AND entry_month = DATE '2025-05-01')
  )
  AND is_active = true;

UPDATE public.monthly_pnl_import_months
SET
  import_status = 'error',
  updated_at = now()
WHERE profile_id = 'c8e854cf-b989-4e3f-8cf4-58a43507c67a'
  AND import_id = '0fe50885-fce4-48ec-afa6-a9dce5cef716'
  AND import_status IN ('pending', 'running');

UPDATE public.monthly_pnl_imports
SET
  import_status = 'error',
  error_message = 'Marked as error during 2026-03-16 validation cleanup after a retry import remained stuck in running state.',
  finished_at = COALESCE(finished_at, now()),
  updated_at = now()
WHERE profile_id = 'c8e854cf-b989-4e3f-8cf4-58a43507c67a'
  AND id = '0fe50885-fce4-48ec-afa6-a9dce5cef716'
  AND import_status = 'running';
