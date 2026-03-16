-- =====================================================================
-- MIGRATION: Align Monthly P&L seed rules with manual workbook mappings
-- Purpose:
--   Replace the broad FBA Inventory fallback and add the type/description
--   mappings needed to mirror the agency manual model more closely.
-- =====================================================================

DELETE FROM public.monthly_pnl_mapping_rules
WHERE profile_id IS NULL
  AND marketplace_code = 'US'
  AND source_type = 'amazon_transaction_upload'
  AND match_operator = 'exact_fields'
  AND match_spec = '{"type": "FBA Inventory Fee"}'::jsonb
  AND target_bucket = 'fba_removal_order_fees';

INSERT INTO public.monthly_pnl_mapping_rules
  (marketplace_code, source_type, match_spec, match_operator, target_bucket, priority)
VALUES
  ('US', 'amazon_transaction_upload',
   '{"type": "Amazon Fees"}',
   'exact_fields', 'promotions_fees', 30),
  ('US', 'amazon_transaction_upload',
   '{"type": "Service Fee", "description": "Coupon Redemption Fee"}',
   'exact_fields', 'promotions_fees', 10),
  ('US', 'amazon_transaction_upload',
   '{"type": "Service Fee", "description": "Vine Enrollment Fee"}',
   'exact_fields', 'promotions_fees', 10),
  ('US', 'amazon_transaction_upload',
   '{"description": "Price Discount"}',
   'starts_with', 'promotions_fees', 10),
  ('US', 'amazon_transaction_upload',
   '{"description": "Deal"}',
   'starts_with', 'promotions_fees', 10),
  ('US', 'amazon_transaction_upload',
   '{"type": "Service Fee", "description": "Refund for Advertiser"}',
   'exact_fields', 'advertising', 10),
  ('US', 'amazon_transaction_upload',
   '{"type": "Fee Adjustment"}',
   'exact_fields', 'fba_fees', 20),
  ('US', 'amazon_transaction_upload',
   '{"type": "FBA Transaction fees"}',
   'exact_fields', 'other_transaction_fees', 20),
  ('US', 'amazon_transaction_upload',
   '{"type": "Service Fee", "description": "Inbound Defect Fee"}',
   'exact_fields', 'inbound_placement_and_defect_fees', 10),
  ('US', 'amazon_transaction_upload',
   '{"type": "Service Fee", "description": "Unplanned Service Charge"}',
   'exact_fields', 'inbound_placement_and_defect_fees', 10),
  ('US', 'amazon_transaction_upload',
   '{"type": "Shipping Services"}',
   'exact_fields', 'inbound_shipping_and_duties', 20),
  ('US', 'amazon_transaction_upload',
   '{"type": "Service Fee", "description": "FBA International Freight Shipping Charge"}',
   'exact_fields', 'inbound_shipping_and_duties', 10),
  ('US', 'amazon_transaction_upload',
   '{"type": "Service Fee", "description": "FBA International Freight Duties and Taxes Charge"}',
   'exact_fields', 'inbound_shipping_and_duties', 10),
  ('US', 'amazon_transaction_upload',
   '{"type": "FBA Inventory Fee", "description": "Capacity Reservation Fee"}',
   'exact_fields', 'fba_monthly_storage_fees', 10),
  ('US', 'amazon_transaction_upload',
   '{"type": "FBA Inventory Fee", "description": "FBA Removal Order"}',
   'exact_fields', 'fba_removal_order_fees', 10),
  ('US', 'amazon_transaction_upload',
   '{"type": "FBA Inventory Fee", "description": "Fulfilment by Amazon removal order"}',
   'exact_fields', 'fba_removal_order_fees', 10),
  ('US', 'amazon_transaction_upload',
   '{"type": "FBA Inventory Fee", "description": "FBA Disposal Fee"}',
   'exact_fields', 'fba_removal_order_fees', 10),
  ('US', 'amazon_transaction_upload',
   '{"type": "FBA Inventory Fee", "description": "FBA Amazon-Partnered Carrier Shipment Fee"}',
   'exact_fields', 'inbound_shipping_and_duties', 10),
  ('US', 'amazon_transaction_upload',
   '{"type": "A-to-z Guarantee Claim"}',
   'exact_fields', 'a_to_z_guarantee_claims', 20),
  ('US', 'amazon_transaction_upload',
   '{"type": "Chargeback Refund"}',
   'exact_fields', 'chargebacks', 20)
ON CONFLICT DO NOTHING;
