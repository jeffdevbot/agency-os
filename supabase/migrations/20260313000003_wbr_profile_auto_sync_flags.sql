-- =====================================================================
-- MIGRATION: WBR profile auto-sync flags
-- Purpose:
--   Track whether nightly SP-API and Amazon Ads refreshes should run for
--   each WBR profile from the worker-sync background service.
-- =====================================================================

ALTER TABLE public.wbr_profiles
  ADD COLUMN IF NOT EXISTS sp_api_auto_sync_enabled boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS ads_api_auto_sync_enabled boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.wbr_profiles.sp_api_auto_sync_enabled
  IS 'When true, worker-sync runs the nightly Windsor/SP-API trailing-window refresh for this profile.';

COMMENT ON COLUMN public.wbr_profiles.ads_api_auto_sync_enabled
  IS 'When true, worker-sync runs the nightly Amazon Ads trailing-window refresh for this profile.';
