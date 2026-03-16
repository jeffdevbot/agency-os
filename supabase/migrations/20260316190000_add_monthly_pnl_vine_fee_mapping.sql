-- =====================================================================
-- MIGRATION: Seed Monthly P&L mapping for Amazon Vine enrollment fees
-- Purpose:
--   Reclassify Amazon Fees / Vine Enrollment Fee into promotions fees
--   so the Monthly P&L report aligns more closely with the manual model.
-- =====================================================================

INSERT INTO public.monthly_pnl_mapping_rules
  (marketplace_code, source_type, match_spec, match_operator, target_bucket, priority)
VALUES
  ('US', 'amazon_transaction_upload',
   '{"type": "Amazon Fees", "description": "Vine Enrollment Fee"}',
   'exact_fields', 'promotions_fees', 10)
ON CONFLICT DO NOTHING;
