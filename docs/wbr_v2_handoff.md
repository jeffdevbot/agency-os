# WBR v2 Handoff

_Last updated: 2026-03-13 (EST)_

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

## Live database state

These migrations were created and applied to the live Supabase project:

1. `20260312000001_wbr_profiles_and_rows.sql`
2. `20260312000002_wbr_imports_and_mappings.sql`
3. `20260312000003_wbr_sync_runs_and_fact_tables.sql`

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

## Current user-facing routes

Primary navigation shape:

1. `/reports`
2. `/reports/[clientSlug]`
3. `/reports/[clientSlug]/[marketplaceCode]/wbr`
4. `/reports/[clientSlug]/[marketplaceCode]/wbr/settings`
5. `/reports/[clientSlug]/[marketplaceCode]/wbr/sync`

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
2. Run daily refresh from the sync screen.
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
7. `backend-core/app/services/wbr/section1_report.py`

### Frontend report routes

1. `frontend-web/src/app/reports/_components/WbrSection1ReportScreen.tsx`
2. `frontend-web/src/app/reports/_components/WbrSection1MetricTable.tsx`
3. `frontend-web/src/app/reports/_components/WbrSyncScreen.tsx`
4. `frontend-web/src/app/reports/_components/ResolvedWbrSettingsRoute.tsx`
5. `frontend-web/src/app/reports/_lib/useResolvedWbrProfile.ts`
6. `frontend-web/src/app/reports/_lib/useWbrSection1Report.ts`
7. `frontend-web/src/app/reports/_lib/useWbrSync.ts`
8. `frontend-web/src/app/reports/wbr/_lib/wbrApi.ts`
9. `frontend-web/src/app/reports/wbr/_lib/wbrSection1Api.ts`
10. `frontend-web/src/app/reports/wbr/[profileId]/WbrProfileWorkspace.tsx`

## Important product assumptions currently locked

1. One WBR profile per client per marketplace.
2. Windsor is still the business-data source for Section 1.
3. Amazon Ads API will be the ads-data source later.
4. Pacvue export is the grouping source for campaigns.
5. Pacvue tags define leaf rows after removing the goal suffix.
6. Parent rows are manual and optional.
7. Child ASIN maps to exactly one leaf row in v1.
8. Week start is per profile and supports `sunday` or `monday`.
9. Listings import is snapshot replacement, not enrichment/merge.
10. Re-importing the correct Windsor/manual listings snapshot fixes a bad import by replacing the active catalog.

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

The next session should start with UI improvements on the new WBR report route, not with more schema work.

Recommended order:

1. Improve WBR report presentation on `/reports/[clientSlug]/[marketplaceCode]/wbr`
   - cleaner layout
   - better table spacing/typography
   - clearer hierarchy for parents vs leaves
   - stronger weekly-header presentation
   - tighter QA/status presentation
2. Validate Whoosh US Section 1 against the manual Excel WBR.
3. Add source-vs-report reconciliation helpers if totals are off.
4. After Section 1 is trustworthy, start Amazon Ads ingest for Section 2.

## Tests last run

1. `backend-core/.venv/bin/pytest backend-core/tests/test_wbr_windsor_business_sync.py backend-core/tests/test_wbr_section1_report.py backend-core/tests/test_wbr_profiles_service.py backend-core/tests/test_wbr_router.py backend-core/tests/test_wbr_pacvue_imports.py backend-core/tests/test_wbr_listing_imports.py backend-core/tests/test_wbr_asin_mappings.py`
   - `73 passed`
2. `npm -C frontend-web run typecheck`
   - passed
3. `npm -C frontend-web run test:run -- src/app/reports/reports-nav.test.ts`
   - passed

## Non-WBR local changes intentionally not part of the shipped WBR commits

These files may still be dirty locally and should not be confused with WBR product work:

1. `docs/db/schema_master.md`
2. `scripts/db/generate-schema-master.sh`
3. `supabase/.temp/cli-latest`
