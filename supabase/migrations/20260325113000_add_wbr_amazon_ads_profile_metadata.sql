alter table public.wbr_profiles
  add column if not exists amazon_ads_country_code text,
  add column if not exists amazon_ads_currency_code text,
  add column if not exists amazon_ads_marketplace_string_id text;

comment on column public.wbr_profiles.amazon_ads_country_code is
  'Amazon Ads advertiser profile countryCode captured when the profile is selected.';

comment on column public.wbr_profiles.amazon_ads_currency_code is
  'Amazon Ads advertiser profile currencyCode captured when the profile is selected.';

comment on column public.wbr_profiles.amazon_ads_marketplace_string_id is
  'Amazon Ads advertiser profile accountInfo.marketplaceStringId captured when the profile is selected.';
