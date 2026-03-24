-- =====================================================================
-- MIGRATION: Add US Monthly P&L inventory-credit rules for SAFE-T and Debt
-- Purpose:
--   Match the validated manual US workbook treatment for seller SAFE-T
--   reimbursements and Debt rows observed on live Lifestyle US imports.
-- =====================================================================

INSERT INTO public.monthly_pnl_mapping_rules (
  marketplace_code,
  source_type,
  match_spec,
  match_operator,
  target_bucket,
  priority
)
VALUES
  (
    'US',
    'amazon_transaction_upload',
    '{"type": "SAFE-T reimbursement"}'::jsonb,
    'exact_fields',
    'fba_inventory_credit',
    20
  ),
  (
    'US',
    'amazon_transaction_upload',
    '{"type": "Debt"}'::jsonb,
    'exact_fields',
    'fba_inventory_credit',
    20
  )
ON CONFLICT DO NOTHING;
