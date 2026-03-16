# Windsor WBR Section 1 Ingestion Runbook

> Broader WBR state and restart context live in `docs/wbr_v2_handoff.md`,
> `docs/wbr_v2_schema_plan.md`, and
> `docs/archive/session_prompts/wbr_v2_prototype_plan.md`. This
> runbook is intentionally narrower: it documents the live Windsor-based
> Section 1 ingestion path only.

## Scope

This runbook covers the current WBR Section 1 source flow:

1. Windsor seller-business sync for daily child-ASIN facts.
2. Windsor merchant-listings import for optional catalog bootstrap.
3. Sync execution from the client-first WBR routes.

This runbook does not define Section 2. Ads reporting is now sourced from the
Amazon Ads API, not Windsor.

## Current live architecture

WBR business-data ingest is now profile-centric, not client-id flat.

Current live shape:

1. One WBR profile per client and marketplace in `wbr_profiles`.
2. Windsor account scoping is stored on `wbr_profiles.windsor_account_id`.
3. Daily business facts land in `wbr_business_asin_daily`.
4. Sync execution history lands in `wbr_sync_runs` with `source_type = 'windsor_business'`.
5. Section 1 report rollups happen in `backend-core/app/services/wbr/section1_report.py`.

Primary user routes:

1. `/reports/[clientSlug]/[marketplaceCode]/wbr`
2. `/reports/[clientSlug]/[marketplaceCode]/wbr/settings`
3. `/reports/[clientSlug]/[marketplaceCode]/wbr/sync`
4. `/reports/[clientSlug]/[marketplaceCode]/wbr/sync/sp-api`

Primary backend routes:

1. `POST /admin/wbr/profiles/{profile_id}/listings/import-windsor`
2. `GET /admin/wbr/profiles/{profile_id}/sync-runs?source_type=windsor_business`
3. `POST /admin/wbr/profiles/{profile_id}/sync-runs/windsor-business/backfill`
4. `POST /admin/wbr/profiles/{profile_id}/sync-runs/windsor-business/daily-refresh`
5. `GET /admin/wbr/profiles/{profile_id}/section1-report?weeks=4`

## Windsor report presets in use

### Report A: Merchant Listings Snapshot

- Data source: `Amazon Seller Central`
- Report preset: `get_merchant_listings_all_data`
- Purpose: optional listings bootstrap for child-ASIN catalog import
- Current app usage: `Listings import from Windsor`

Current requested Windsor fields include:

- `account_id`
- `marketplace_country`
- `merchant_listings_all_data__asin1`
- `merchant_listings_all_data__asin2`
- `merchant_listings_all_data__product_id`
- `merchant_listings_all_data__product_id_type`
- `merchant_listings_all_data__seller_sku`
- `merchant_listings_all_data__item_name`
- `merchant_listings_all_data__fulfillment_channel`
- `merchant_listings_all_data__zshop_category1`

The importer accepts Windsor rows directly and also supports fallback file
uploads (`.txt`, `.tsv`, `.csv`, `.xlsx`, `.xlsm`) on the settings page.

### Report B: Sales and Traffic by ASIN

- Data source: `Amazon Seller Central`
- Report preset: `get_sales_and_traffic_report_by_asin`
- Purpose: primary Section 1 metric source
- Current app usage: Windsor business sync service

Required Windsor fields:

- `account_id`
- `date`
- `sales_and_traffic_report_by_date__childasin`
- `sales_and_traffic_report_by_date__parentasin`
- `sales_and_traffic_report_by_date__salesbyasin_orderedproductsales_amount`
- `sales_and_traffic_report_by_date__salesbyasin_orderedproductsales_currencycode`
- `sales_and_traffic_report_by_date__salesbyasin_unitsordered`
- `sales_and_traffic_report_by_date__trafficbyasin_pageviews`

Metric mapping:

- `page_views` = `trafficbyasin_pageviews`
- `unit_sales` = `salesbyasin_unitsordered`
- `sales` = `salesbyasin_orderedproductsales_amount`
- `conversion_rate` = `unit_sales / page_views`

## Onboarding flow for Section 1

1. Create the WBR profile.
2. Save `windsor_account_id` on the profile in WBR Settings.
3. Import listings from Windsor or upload a listings file.
4. Map child ASINs to WBR leaf rows.
5. Run Windsor backfill from the SP-API sync screen.
6. Validate Section 1 output on the main WBR report route.
7. Optionally enable nightly SP-API sync for the profile.

The system does not group by `group_label`. Business facts roll up through:

`child_asin -> wbr_asin_row_map -> wbr_rows`

## Sync behavior

### Backfill

- Triggered from `/reports/[clientSlug]/[marketplaceCode]/wbr/sync/sp-api`
- Calls `POST /admin/wbr/profiles/{profile_id}/sync-runs/windsor-business/backfill`
- Accepts:
  - `date_from`
  - `date_to`
  - `chunk_days`
- Backend default chunk size: `7` days
- Each chunk creates its own `wbr_sync_runs` row

### Daily refresh

- Triggered manually from the same sync screen or nightly by `worker-sync`
- Calls `POST /admin/wbr/profiles/{profile_id}/sync-runs/windsor-business/daily-refresh`
- Rewrites the trailing `daily_rewrite_days` window for the profile
- Default trailing window: `14` days unless overridden on the profile

### Nightly automation

- Controlled by `wbr_profiles.sp_api_auto_sync_enabled`
- Only `active` profiles are scanned by `worker-sync`
- Enabling the nightly toggle on a `draft` profile auto-promotes the profile to
  `active`

## Section 1 report behavior

Section 1 is rendered from the synced fact table plus active ASIN mappings.

Current report rules:

1. The report shows previous full weeks only; the current in-progress week is excluded.
2. Week boundaries follow `wbr_profiles.week_start_day` and support `sunday` or `monday`.
3. Parent rows are sums of child leaf rows.
4. Unmapped ASIN activity is excluded from row totals and counted in report QA.

Current Section 1 metrics:

1. Page Views
2. Unit Sales
3. Sales
4. Conversion Rate

## Query behavior and source handling

Current Windsor business sync behavior in code:

1. Requests are account-scoped via `select_accounts=<windsor_account_id>`.
2. Requests use explicit `date_from` and `date_to`.
3. Response payloads may be JSON or CSV; the sync service supports both.
4. Recent windows are rewritten, not append-only merged.
5. Currency defaults are inferred from account suffix if the source omits it.

Example request shape:

```text
https://connectors.windsor.ai/amazon_sp?api_key=***&select_accounts=<account_id>&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&fields=...
```

## Operational guidance

1. Prefer account-scoped pulls for safety and predictable row counts.
2. Use chunked backfills for larger historical ranges; do not send oversized date windows unless necessary.
3. Re-run recent windows instead of relying on append-only logic; Windsor source data can restate.
4. If Section 1 totals look low, inspect ASIN mapping coverage before suspecting the sync itself.
5. If sync row counts spike, check for account-scope mistakes or Windsor field-shape changes.

## Known caveats

1. Windsor response shape can vary between JSON and CSV depending on source behavior.
2. Merchant listings can be incomplete for some catalog metadata; manual file import remains a supported fallback.
3. Very large date ranges should still be chunked even if Windsor appears responsive.
4. The old `/admin/wbr/section1/*` routes and `/reports/wbr/[clientId]` flow are legacy and should not be used as the reference path for current WBR behavior.
