-- Mirror the FBA-prefixed inbound carrier catch-all rule for CA.
-- This maps blank-description "FBA Inventory Fee" rows with order IDs like
-- FBA18ZSZFHQX into inbound_shipping_and_duties for CA transaction imports.

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
VALUES
  (
    NULL,
    'CA',
    'amazon_transaction_upload',
    '{"type": "FBA Inventory Fee", "order_id": "FBA"}'::jsonb,
    'starts_with',
    'inbound_shipping_and_duties',
    50,
    true
  )
ON CONFLICT DO NOTHING;
