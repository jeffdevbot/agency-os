ALTER TABLE public.wbr_profile_child_asins
  ADD COLUMN IF NOT EXISTS item_description text,
  ADD COLUMN IF NOT EXISTS status text,
  ADD COLUMN IF NOT EXISTS price text,
  ADD COLUMN IF NOT EXISTS quantity text,
  ADD COLUMN IF NOT EXISTS merchant_shipping_group text,
  ADD COLUMN IF NOT EXISTS item_condition text;

UPDATE public.wbr_profile_child_asins
SET
  item_description = COALESCE(
    wbr_profile_child_asins.item_description,
    NULLIF(raw_payload->>'merchant_listings_all_data__item_description', '')
  ),
  status = COALESCE(
    wbr_profile_child_asins.status,
    NULLIF(raw_payload->>'merchant_listings_all_data__status', '')
  ),
  price = COALESCE(
    wbr_profile_child_asins.price,
    NULLIF(raw_payload->>'merchant_listings_all_data__price', '')
  ),
  quantity = COALESCE(
    wbr_profile_child_asins.quantity,
    NULLIF(raw_payload->>'merchant_listings_all_data__quantity', '')
  ),
  merchant_shipping_group = COALESCE(
    wbr_profile_child_asins.merchant_shipping_group,
    NULLIF(raw_payload->>'merchant_listings_all_data__merchant_shipping_group', '')
  ),
  item_condition = COALESCE(
    wbr_profile_child_asins.item_condition,
    NULLIF(raw_payload->>'merchant_listings_all_data__item_condition', '')
  )
WHERE raw_payload <> '{}'::jsonb;
