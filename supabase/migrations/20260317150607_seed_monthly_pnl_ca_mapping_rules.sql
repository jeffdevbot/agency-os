-- =====================================================================
-- MIGRATION: Seed Monthly P&L CA global mapping rules
-- Purpose:
--   CA transaction uploads use the same rule model as US, but marketplace-
--   scoped lookups mean CA profiles currently load no global mapping rules.
--   Copy the shipped US amazon transaction rules into CA without changing
--   the validated US rule set.
-- =====================================================================

INSERT INTO public.monthly_pnl_mapping_rules (
  profile_id,
  marketplace_code,
  source_type,
  match_spec,
  match_operator,
  target_bucket,
  priority,
  active
)
SELECT
  NULL,
  'CA',
  source_type,
  match_spec,
  match_operator,
  target_bucket,
  priority,
  active
FROM public.monthly_pnl_mapping_rules
WHERE profile_id IS NULL
  AND marketplace_code = 'US'
  AND source_type = 'amazon_transaction_upload'
ON CONFLICT DO NOTHING;
