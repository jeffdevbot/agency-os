-- =====================================================================
-- MIGRATION: Fix Monthly P&L removal-order matching edge cases
-- Purpose:
--   The manual workbook groups Amazon descriptions like
--   "FBA Removal Order: Disposal Fee" under FBA removal order fees.
--   Our exact-match seed was too narrow, so broaden it to starts_with.
-- =====================================================================

DELETE FROM public.monthly_pnl_mapping_rules
WHERE profile_id IS NULL
  AND marketplace_code = 'US'
  AND source_type = 'amazon_transaction_upload'
  AND match_operator = 'exact_fields'
  AND match_spec = '{"type": "FBA Inventory Fee", "description": "FBA Removal Order"}'::jsonb
  AND target_bucket = 'fba_removal_order_fees';

INSERT INTO public.monthly_pnl_mapping_rules
  (marketplace_code, source_type, match_spec, match_operator, target_bucket, priority)
VALUES
  ('US', 'amazon_transaction_upload',
   '{"type": "FBA Inventory Fee", "description": "FBA Removal Order"}',
   'starts_with', 'fba_removal_order_fees', 10)
ON CONFLICT DO NOTHING;
