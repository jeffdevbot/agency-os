-- Map blank-description "FBA Inventory Fee" rows with FBA-prefixed order IDs
-- (inbound shipment carrier charges) into inbound_shipping_and_duties.
-- Priority 50 ensures specific description-based rules (priority 10) fire first.

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
    'US',
    'amazon_transaction_upload',
    '{"type": "FBA Inventory Fee", "order_id": "FBA"}'::jsonb,
    'starts_with',
    'inbound_shipping_and_duties',
    50,
    true
  )
ON CONFLICT DO NOTHING;
