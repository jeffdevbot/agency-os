-- =====================================================================
-- MIGRATION: WBR ads campaign daily campaign type uniqueness
-- Purpose:
--   Preserve Sponsored Products, Sponsored Brands, and Sponsored Display
--   facts separately even when campaign names overlap on the same date.
-- =====================================================================

update public.wbr_ads_campaign_daily
set campaign_type = 'sponsored_products'
where campaign_type is null;

alter table public.wbr_ads_campaign_daily
  alter column campaign_type set default 'sponsored_products';

alter table public.wbr_ads_campaign_daily
  alter column campaign_type set not null;

drop index if exists public.uq_wbr_ads_campaign_daily_profile_date_campaign;

create unique index if not exists uq_wbr_ads_campaign_daily_profile_date_type_campaign
  on public.wbr_ads_campaign_daily(profile_id, report_date, campaign_type, campaign_name);

create index if not exists idx_wbr_ads_campaign_daily_profile_type_date
  on public.wbr_ads_campaign_daily(profile_id, campaign_type, report_date desc);
