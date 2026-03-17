-- Add CA-oriented label variants observed in live transaction exports so
-- coupon/redemption, Vine enrolment, and fulfilment prep fees map cleanly.

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
    '{"type": "Service Fee", "description": "Coupon Redemption Fee"}'::jsonb,
    'starts_with',
    'promotions_fees',
    10,
    true
  ),
  (
    NULL,
    'CA',
    'amazon_transaction_upload',
    '{"type": "Service Fee", "description": "Coupon Redemption Fee"}'::jsonb,
    'starts_with',
    'promotions_fees',
    10,
    true
  ),
  (
    NULL,
    'CA',
    'amazon_transaction_upload',
    '{"type": "Service Fee", "description": "Vine Enrolment Fee"}'::jsonb,
    'exact_fields',
    'promotions_fees',
    10,
    true
  ),
  (
    NULL,
    'CA',
    'amazon_transaction_upload',
    '{"type": "FBA Inventory Fee", "description": "Fulfilment by Amazon prep fee"}'::jsonb,
    'starts_with',
    'inbound_placement_and_defect_fees',
    10,
    true
  )
ON CONFLICT DO NOTHING;
