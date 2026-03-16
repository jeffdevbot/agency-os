# WBR v2 Handoff

_Last updated: 2026-03-15 (ET)_

This file is the fast restart point for the current WBR v2 build.

## Current shipped state

Commits on `main` relevant to the current WBR v2 slice:

1. `d88bce0` - `Ship WBR v2 profile management foundation`
2. `5921dc0` - `Add WBR row deactivate and permanent delete actions`
3. `4246368` - `Add WBR Pacvue import workflow`
4. `13ed955` - `Add WBR listings import workflow`
5. `dd60460` - `Add WBR ASIN mapping workspace`
6. `16c5f13` - `Add Windsor listings import for WBR`
7. `3194e49` - `Restructure reports navigation around client routes`
8. `48fbdc2` - `Add WBR Section 1 sync and report screens`
9. `608a759` - `Add WBR Section 2 ads report`
10. `c433561` - `Add TACoS and ads mapping QA`
11. `6cc13e8` - `Paginate Section 2 report fact queries`
12. `9f0e602` - `Add sponsored brands and display sync`
13. `a4ec019` - `Add WBR nightly sync worker and toggles`
14. `4068a97` - `Increase Amazon Ads polling window`
15. `f6a4c58` - `Fix Amazon Ads brand and display columns`
16. `55ee467` - `Auto-activate nightly sync profiles`
17. `d225ba8` - `Refactor WBR Amazon Ads sync to queued worker flow`
18. `11343ba` - `Add WBR Section 3 inventory and returns reporting`
19. `33af744` - `Update WBR docs and fix Section 3 sync run types`
20. `2662eda` - `Add section tabs to WBR report`
21. `cfbcde9` - `Add WBR Excel export`
22. `a39e85c` - `Add Section 1 trend charts to WBR`
23. `f56bed7` - `Add WBR ad charts and total toggle`
24. `9a38a38` - `Align WBR section 3 table header styling`

## Live database state

These migrations were created and applied to the live Supabase project:

1. `20260312000001_wbr_profiles_and_rows.sql`
2. `20260312000002_wbr_imports_and_mappings.sql`
3. `20260312000003_wbr_sync_runs_and_fact_tables.sql`
4. `20260313000001_wbr_amazon_ads_connections.sql`
5. `20260313000002_wbr_ads_campaign_daily_campaign_type_unique.sql`
6. `20260313000003_wbr_profile_auto_sync_flags.sql`
7. `20260314000001_wbr_inventory_and_returns_tables.sql`
8. `20260315100000_expand_wbr_sync_run_source_types_for_section3.sql`

Core live tables in use now:

1. `wbr_profiles`
2. `wbr_rows`
3. `wbr_pacvue_import_batches`
4. `wbr_pacvue_campaign_map`
5. `wbr_listing_import_batches`
6. `wbr_profile_child_asins`
7. `wbr_asin_row_map`
8. `wbr_sync_runs`
9. `wbr_business_asin_daily`
10. `wbr_ads_campaign_daily`
11. `wbr_amazon_ads_connections`
12. `wbr_inventory_asin_snapshots`
13. `wbr_returns_asin_daily`

## Current user-facing routes

Primary navigation shape:

1. `/reports`
2. `/reports/[clientSlug]`
3. `/reports/[clientSlug]/[marketplaceCode]/wbr`
4. `/reports/[clientSlug]/[marketplaceCode]/wbr/settings`
5. `/reports/[clientSlug]/[marketplaceCode]/wbr/sync`
6. `/reports/[clientSlug]/[marketplaceCode]/wbr/sync/sp-api`
7. `/reports/[clientSlug]/[marketplaceCode]/wbr/sync/ads-api`

Compatibility/admin routes still present:

1. `/reports/wbr`
2. `/reports/wbr/setup`
3. `/reports/wbr/[profileId]`
   - redirects into the new client/marketplace settings route

## What works right now

### WBR profile/settings layer

1. Create one WBR profile per client + marketplace.
2. Edit profile integrations on the settings page:
   - `windsor_account_id`
   - `amazon_ads_profile_id`
   - `amazon_ads_account_id`
3. Create parent and leaf rows manually.
4. Edit row label, parent, sort order, and active state.
5. Deactivate rows.
6. Permanently delete rows when safe.

### Row delete behavior

Permanent delete is blocked when:

1. a parent row still has child rows
2. a row still has active ASIN mappings
3. a row still has active Pacvue campaign mappings

### Pacvue/campaign setup

1. Upload Pacvue workbook.
2. Auto-detect header row, even with metadata rows above it.
3. Parse `Name` + `CampaignTagNames`.
4. Create/reactivate leaf rows from normalized Pacvue tags.
5. Store campaign mappings in `wbr_pacvue_campaign_map`.

### Listings/ASIN setup

1. Import listings from Windsor using the profile’s `windsor_account_id`.
2. Upload Amazon All Listings manually as fallback.
3. Both imports replace the active child-ASIN snapshot for that profile.
4. Map child ASINs to leaf rows in the UI.
5. Bulk round-trip ASIN mappings via CSV:
   - export
   - edit `row_label`
   - re-import the same CSV

### Section 1 sync/report

1. Run Windsor business-data backfill from the sync screen.
2. Run manual refresh from the sync screen.
3. Sync writes normalized daily child-ASIN facts into `wbr_business_asin_daily`.
4. Report route renders the first live Section 1 tables:
   - Page Views
   - Unit Sales
   - Sales
   - Conversion Rate
5. Parent rows roll up child leaves.
6. Report QA counters show:
   - active rows
   - mapped ASINs
   - unmapped ASINs with activity
   - fact rows in window

### Amazon Ads sync/report

1. Connect a WBR profile to Amazon Ads via OAuth and store the refresh token in `wbr_amazon_ads_connections`.
2. Discover advertiser profiles and save `amazon_ads_profile_id` + `amazon_ads_account_id` onto the WBR profile.
3. Run Amazon Ads backfill from the Ads sync screen.
4. Run manual refresh from the Ads sync screen.
5. Ads sync currently pulls:
   - Sponsored Products
   - Sponsored Brands
   - Sponsored Display
6. Manual Ads backfills and manual Ads refreshes now enqueue Amazon report jobs immediately instead of waiting synchronously for report completion in the request.
7. `worker-sync` polls queued report jobs, downloads completed reports, and finalizes the sync runs in the background.
8. Ads sync screen run history now surfaces queued/polling/finalized progress from `wbr_sync_runs.request_meta`.
9. Sync writes normalized daily campaign facts into `wbr_ads_campaign_daily`.
10. Facts preserve `campaign_type`, so future split reporting by ad product is possible without changing storage again.
11. The main WBR route renders Section 2 metrics:
   - Impressions
   - Clicks
   - CTR
   - Ad Spend
   - CPC
   - Ad Orders
   - Ad Conversion Rate
   - Ad Sales
   - ACoS
   - TACoS
12. The Ads sync screen also shows admin-only Pacvue mapping QA for the current 4-week WBR window.

### Section 3 inventory + returns

1. Windsor manual refresh and nightly Windsor refresh now also run Section 3 inventory and returns ingestion under the same Windsor setup/toggle.
2. Inventory snapshots are stored in `wbr_inventory_asin_snapshots`.
3. Returns facts are stored in `wbr_returns_asin_daily`.
4. Section 3 sync runs are logged as:
   - `windsor_inventory`
   - `windsor_returns`
5. The main WBR route now renders Section 3:
   - Instock
   - Working
   - Reserved / FC Transfer
   - Receiving / Intransit
   - Weeks of Stock
   - prior 2 completed weeks of returns
   - Return %
6. Section 3 is now showing real data on the validation account after the live follow-up migration that expanded `wbr_sync_runs.source_type`.

### Main report UX

1. The WBR report is now tabbed rather than stacked:
   - `Traffic + Sales`
   - `Advertising`
   - `Inventory + Returns`
2. Only one section renders at a time in both horizontal and stacked layouts.
3. The report now supports Excel export from the main page:
   - server-side `.xlsx`
   - 3 sheets
   - horizontal layout
   - frozen first column
4. Section 1 now supports inline trend charts for:
   - Page Views
   - Unit Sales
   - Conversion Rate
   - Sales
5. Section 2 now supports inline trend charts for:
   - Impressions
   - Clicks
   - CTR
   - Ad Spend
   - CPC
   - Ad Orders
   - Ad Conversion Rate
   - Ad Sales
   - ACoS
   - TACoS
6. Chart behavior:
   - click metric header to open/close
   - one open chart at a time per section
   - row overlays toggle from the `Style` cell
   - `Total` series is now toggleable
7. Section 3 does not currently have charts because the live payload exposes one inventory snapshot plus two returns weeks, not a true multi-week inventory trend series.

### Nightly sync automation

1. `worker-sync` is now implemented in-repo and deployed as the Render background worker.
2. Nightly toggles exist separately for:
   - SP-API / Windsor business refresh
   - Ads API refresh
3. The same worker now also advances pending queued Amazon Ads report jobs outside the nightly schedule window.
4. Nightly sync runs as `daily_refresh` and writes its outcomes into `wbr_sync_runs`.
5. The worker currently scans only `status = 'active'` WBR profiles.
6. Enabling either nightly toggle now auto-promotes a `draft` profile to `active`.

## Current backend routes

### Profile/row admin

1. `GET /admin/wbr/profiles?client_id=<uuid>`
2. `POST /admin/wbr/profiles`
3. `GET /admin/wbr/profiles/{profile_id}`
4. `PATCH /admin/wbr/profiles/{profile_id}`
5. `GET /admin/wbr/profiles/{profile_id}/rows`
6. `POST /admin/wbr/profiles/{profile_id}/rows`
7. `PATCH /admin/wbr/rows/{row_id}`
8. `DELETE /admin/wbr/rows/{row_id}`

### Pacvue

1. `GET /admin/wbr/profiles/{profile_id}/pacvue/import-batches`
2. `POST /admin/wbr/profiles/{profile_id}/pacvue/import`

### Listings

1. `GET /admin/wbr/profiles/{profile_id}/listings/import-batches`
2. `POST /admin/wbr/profiles/{profile_id}/listings/import`
3. `POST /admin/wbr/profiles/{profile_id}/listings/import-windsor`

### ASIN mapping

1. `GET /admin/wbr/profiles/{profile_id}/child-asins`
2. `GET /admin/wbr/profiles/{profile_id}/child-asins/mapping-export`
3. `POST /admin/wbr/profiles/{profile_id}/child-asins/mapping-import`
4. `PUT /admin/wbr/profiles/{profile_id}/child-asins/{child_asin}/mapping`

### Section 1 sync/report

1. `GET /admin/wbr/profiles/{profile_id}/sync-runs?source_type=windsor_business`
2. `POST /admin/wbr/profiles/{profile_id}/sync-runs/windsor-business/backfill`
3. `POST /admin/wbr/profiles/{profile_id}/sync-runs/windsor-business/daily-refresh`
4. `GET /admin/wbr/profiles/{profile_id}/section1-report?weeks=4`

## Repo hardening follow-ups

Recent repo-only hardening landed after the initial Section 3 rollout:

1. `list_sync_runs` no longer routes all source types through `WindsorBusinessSyncService`.
2. The router now uses a small generic `WBRSyncRunService`, so sync-run listing stays source-agnostic for:
   - `windsor_business`
   - `windsor_inventory`
   - `windsor_returns`
   - `amazon_ads`
   - `pacvue_import`
   - `listing_import`
3. A follow-up migration exists in repo to harden Section 3 sync constraints:
   - dynamically replace the `wbr_sync_runs.source_type` CHECK without relying on the original auto-generated constraint name
   - add `sync_run_id` validator triggers for `wbr_inventory_asin_snapshots` and `wbr_returns_asin_daily`
4. If a future environment is initialized from migrations only, that hardening migration should be applied as part of WBR setup.

### Amazon Ads + Section 2

1. `POST /admin/wbr/profiles/{profile_id}/amazon-ads/connect`
2. `GET /admin/wbr/profiles/{profile_id}/amazon-ads/connection`
3. `GET /admin/wbr/profiles/{profile_id}/amazon-ads/profiles`
4. `POST /admin/wbr/profiles/{profile_id}/amazon-ads/select-profile`
5. `POST /admin/wbr/profiles/{profile_id}/sync-runs/amazon-ads/backfill`
6. `POST /admin/wbr/profiles/{profile_id}/sync-runs/amazon-ads/daily-refresh`
7. `GET /admin/wbr/profiles/{profile_id}/section2-report?weeks=4`
8. `GET /admin/wbr/profiles/{profile_id}/section3-report?weeks=4`
9. `GET /admin/wbr/profiles/{profile_id}/workbook-export?weeks=4&hide_empty_rows=true&newest_first=true`

## Key files the next session should read first

### Product/state docs

1. `docs/wbr_v2_handoff.md`
2. `docs/wbr_v2_schema_plan.md`
3. `docs/wbr_v2_prototype_plan.md`
4. `PROJECT_STATUS.md`

### Backend

1. `backend-core/app/routers/wbr.py`
2. `backend-core/app/services/wbr/profiles.py`
3. `backend-core/app/services/wbr/pacvue_imports.py`
4. `backend-core/app/services/wbr/listing_imports.py`
5. `backend-core/app/services/wbr/asin_mappings.py`
6. `backend-core/app/services/wbr/windsor_business_sync.py`
7. `backend-core/app/services/wbr/windsor_inventory_sync.py`
8. `backend-core/app/services/wbr/windsor_returns_sync.py`
9. `backend-core/app/services/wbr/amazon_ads_auth.py`
10. `backend-core/app/services/wbr/amazon_ads_sync.py`
11. `backend-core/app/services/wbr/section1_report.py`
12. `backend-core/app/services/wbr/section2_report.py`
13. `backend-core/app/services/wbr/section3_report.py`
14. `backend-core/app/services/wbr/nightly_sync.py`

### Frontend report routes

1. `frontend-web/src/app/reports/_components/WbrSection1ReportScreen.tsx`
2. `frontend-web/src/app/reports/_components/WbrReportSectionTabs.tsx`
3. `frontend-web/src/app/reports/_components/WbrTrafficSalesPane.tsx`
4. `frontend-web/src/app/reports/_components/WbrAdvertisingPane.tsx`
5. `frontend-web/src/app/reports/_components/WbrInventoryReturnsPane.tsx`
6. `frontend-web/src/app/reports/_components/WbrTrendChart.tsx`
7. `frontend-web/src/app/reports/_components/useWbrChartState.ts`
8. `frontend-web/src/app/reports/_components/WbrSection1MetricTable.tsx`
9. `frontend-web/src/app/reports/_components/WbrSection2MetricTable.tsx`
10. `frontend-web/src/app/reports/_components/WbrSection2HorizontalTable.tsx`
11. `frontend-web/src/app/reports/_components/WbrSection3Table.tsx`
12. `frontend-web/src/app/reports/_components/WbrSyncScreen.tsx`
13. `frontend-web/src/app/reports/_components/WbrAdsSyncScreen.tsx`
14. `frontend-web/src/app/reports/_components/ResolvedWbrSettingsRoute.tsx`
15. `frontend-web/src/app/reports/_lib/useResolvedWbrProfile.ts`
16. `frontend-web/src/app/reports/_lib/useWbrSection1Report.ts`
17. `frontend-web/src/app/reports/_lib/useWbrSection2Report.ts`
18. `frontend-web/src/app/reports/_lib/useWbrSection3Report.ts`
19. `frontend-web/src/app/reports/_lib/useWbrWorkbookExport.ts`
20. `frontend-web/src/app/reports/_lib/useWbrSync.ts`
21. `frontend-web/src/app/reports/_lib/useWbrAdsSync.ts`
22. `frontend-web/src/app/reports/wbr/_lib/wbrApi.ts`
23. `frontend-web/src/app/reports/wbr/_lib/wbrSection1Api.ts`
24. `frontend-web/src/app/reports/wbr/_lib/wbrAmazonAdsApi.ts`
25. `frontend-web/src/app/reports/wbr/[profileId]/WbrProfileWorkspace.tsx`

## Important product assumptions currently locked

1. One WBR profile per client per marketplace.
2. Windsor is still the business-data source for Section 1.
3. Amazon Ads API is now the live ads-data source for Section 2.
4. Pacvue export is the grouping source for campaigns.
5. Pacvue tags define leaf rows after removing the goal suffix.
6. Parent rows are manual and optional.
7. Child ASIN maps to exactly one leaf row in v1.
8. Week start is per profile and supports `sunday` or `monday`.
9. Listings import is snapshot replacement, not enrichment/merge.
10. Re-importing the correct Windsor/manual listings snapshot fixes a bad import by replacing the active catalog.
11. Nightly worker sync only runs for `active` profiles, but enabling either nightly toggle will now auto-promote `draft -> active`.
12. Ads storage preserves `campaign_type` so Section 2 can later be split by Sponsored Products / Brands / Display.

## Intentional leftovers

These old backend pieces still exist and were intentionally not removed yet:

1. `backend-core/app/routers/admin.py`
   - old `/admin/wbr/section1/*` endpoints still live
2. `backend-core/app/services/wbr/windsor_section1_ingest.py`
   - still used by the old Section 1 endpoints

Reason:

1. they do not conflict with the new v2 routes
2. they should be removed only after the v2 Section 1 path is clearly the source of truth

## Recommended next implementation order

The next session should treat WBR v2 as a live end-to-end reporting path, not a Section 1-only prototype.

Recommended order:

1. Verify the first real nightly `daily_refresh` runs for both Windsor and Amazon Ads on an `active` profile.
2. Tighten worker observability:
   - cleaner per-cycle logging
   - optional skipped-profile reasons
   - easier diagnosis from `wbr_sync_runs`
3. Validate SB/SD contribution and decide whether Section 2 needs split views by `campaign_type`.
4. Continue report/UI polish only after the sync path is operationally trustworthy.

## Tests last run

1. `backend-core/.venv/bin/pytest backend-core/tests/test_wbr_nightly_sync.py backend-core/tests/test_wbr_router.py backend-core/tests/test_wbr_profiles_service.py backend-core/tests/test_wbr_windsor_business_sync.py backend-core/tests/test_wbr_amazon_ads_sync.py`
   - `55 passed`
2. `backend-core/.venv/bin/pytest backend-core/tests/test_wbr_profiles_service.py backend-core/tests/test_wbr_router.py`
   - `44 passed`
3. `npm -C frontend-web run typecheck`
   - passed

## Non-WBR local changes intentionally not part of the shipped WBR commits

These files may still be dirty locally and should not be confused with WBR product work:

1. `docs/db/schema_master.md`
2. `scripts/db/generate-schema-master.sh`
3. `supabase/.temp/cli-latest`
