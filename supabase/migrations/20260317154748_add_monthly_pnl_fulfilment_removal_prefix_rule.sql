-- Add a starts_with rule for Amazon's "Fulfilment by Amazon removal order"
-- description variant so disposal-fee suffixes map into removal/disposal fees.

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
    '{"type": "FBA Inventory Fee", "description": "Fulfilment by Amazon removal order"}'::jsonb,
    'starts_with',
    'fba_removal_order_fees',
    10,
    true
  ),
  (
    NULL,
    'CA',
    'amazon_transaction_upload',
    '{"type": "FBA Inventory Fee", "description": "Fulfilment by Amazon removal order"}'::jsonb,
    'starts_with',
    'fba_removal_order_fees',
    10,
    true
  )
ON CONFLICT DO NOTHING;
