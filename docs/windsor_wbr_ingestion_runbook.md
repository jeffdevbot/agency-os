# Windsor Amazon SP Ingestion Runbook (WBR v1)

This document captures operational details for ingesting Windsor Amazon Seller Central (`amazon_sp`) data into Supabase for WBR.

## Scope

- Source: Windsor connector endpoint `https://connectors.windsor.ai/amazon_sp`
- Initial report shape: sales + traffic by ASIN with daily grain (`date`)
- Initial output target: rolling 4-week WBR summary with drilldown support
- Data tenancy model: shared tables with `client_id` scoping (do not create separate table versions per client).

## Windsor Report Source Setup (Current)

These are the exact Windsor presets currently used and how they are configured in the UI.

### Report A: Merchant Listings Snapshot

- Data source: `Amazon Seller Central`
- Report preset: `get_merchant_listings_all_data`
- Customization: add `account_id` field
- Purpose:
  - Pull SKU/product metadata (`seller_sku`, `product_id`, `product_id_type`, item name, status)
  - Support ASIN/SKU dimension and grouping workflows

### Report B: Sales and Traffic by ASIN (Primary WBR Section 1 Source)

- Data source: `Amazon Seller Central`
- Report preset: `get_sales_and_traffic_report_by_asin`
- Date control: set report range in Windsor (for example `last_7d`, `last_28d`, `last_180d` or explicit range)
- Customization: add `account_id` and `date` fields
- Purpose:
  - Primary metric source for Section 1 (`page_views`, `unit_sales`, `sales`) at daily ASIN grain

### Report C: Sponsored Products Campaigns (Section 2 Candidate Source)

- Data source: `Amazon Ads`
- Report preset: `sponsored_products_campaigns`
- Customization used in current test: add `date` and `datasource` fields
- Observed output (sample):
  - Includes campaign-level metrics (`impressions`, `clicks`, `spend`, attributed sales/conversions, `campaignid`, `campaign`)
  - Does not include portfolio fields in the tested export (`portfolio_id` / `portfolio_name` absent)
  - Does not include explicit ad account ID in the tested export

## New Client WBR Onboarding Workflow (Target UX)

Goal: onboard a new client by configuration, not custom code.

### Operator Steps

1. In Windsor, connect the client's source account(s) manually.
2. In our app, create a WBR profile for the client.
3. Add the relevant Windsor `account_id` values (and marketplace labels) to that profile.
4. Run initial backfill from our app (job generates account-scoped Windsor URLs automatically).
5. Review `UNMAPPED` ASINs and assign group labels.
6. Activate daily incremental sync.

### System Behavior

1. Store selected Windsor account IDs in config tables per client profile.
2. Build query URLs in code per account/date window (`select_accounts=...`), so users do not hand-build URLs repeatedly.
3. Execute per-account/per-window ingestion with retries and run logging.
4. Upsert into shared multi-tenant tables using `client_id` scoping.

### Configuration Notes

- Currency is marketplace-specific in v1 (no cross-currency conversion).
- Timezone can remain default in v1.
- One client can include multiple marketplaces/accounts under one WBR profile.

## WBR Output Contract (Current)

This section defines the report output first, so ingestion and schema decisions map to required business fields.

### Flexibility Requirement

- Row grouping is client-specific and must be configurable over time.
- Initial example client: Distex.
- Initial example groups: `THORINOX`, `NEW AIR`, `BRIKA`, `DISTEX`.
- Some accounts contain additional brands not included in WBR; reporting must support scoped inclusion by configured group set.

### Group Mapping Strategy (Recommended)

- Do not use product-name parsing as the source of truth for WBR grouping.
- Introduce a manual mapping layer: `account_id + child_asin -> group_label` (Brand/style/sub-category).
- Allow per-client custom grouping schemes so each client can choose its own row logic.
- Keep an `UNMAPPED` bucket for ASINs not yet tagged, and make this visible in QA views.
- Optional accelerator: auto-suggest group labels from item name/SKU prefixes, but require manual confirm/save.
- Portfolio-based grouping can be used as an optional input/bootstrap when available, but it should not be the only grouping source because non-advertised ASINs may not have portfolio context.

### Time Window Convention

- Rolling 4 weeks for Sections 1 and 2.
- Weekly columns are most-recent week first (left to right).
- Each week is represented by explicit date range headers.
- Include one summary `Total` row in addition to grouped rows.
- Week boundary (v1): Sunday-start weeks.
- Future option: Monday-start toggle can be added later at query/view layer; v1 stays fixed to Sunday-start for parity with current reporting.

### Section 1: Organic / Sales-Traffic Summary (v1 target)

Dimensions:

- `group_label` (initially Brand)

Metrics (4 weekly columns each):

- `page_views`
- `unit_sales`
- `unit_conversions_pct` = `unit_sales / page_views` (0 when divisor is 0)
- `sales`

Notes:

- `active_asins` is omitted from v1.
- MTD and YTD are intentionally omitted from v1 and will be delivered as separate views later.
- `sales` source for v1: ordered product sales (not shipped sales).
- `page_views` source for v1: total page views field (`trafficbyasin_pageviews` / equivalent), which already represents browser + mobile app views.

### Section 1 Field Mapping (Locked v1)

Source preset:

- Windsor Report B: `get_sales_and_traffic_report_by_asin`

Required source columns:

- `account_id`
- `date`
- `sales_and_traffic_report_by_date__childasin`
- `sales_and_traffic_report_by_date__parentasin`
- `sales_and_traffic_report_by_date__trafficbyasin_pageviews`
- `sales_and_traffic_report_by_date__salesbyasin_unitsordered`
- `sales_and_traffic_report_by_date__salesbyasin_orderedproductsales_amount`
- `sales_and_traffic_report_by_date__salesbyasin_orderedproductsales_currencycode`

Metric mapping:

- `page_views` = `SUM(sales_and_traffic_report_by_date__trafficbyasin_pageviews)`
- `unit_sales` = `SUM(sales_and_traffic_report_by_date__salesbyasin_unitsordered)`
- `sales` = `SUM(sales_and_traffic_report_by_date__salesbyasin_orderedproductsales_amount)`
- `unit_conversions_pct` = `unit_sales / page_views` (0 when divisor is 0)

Grouping for rows:

- Join source rows to internal mapping table (`account_id + child_asin -> group_label`).
- Aggregate by `group_label` and week bucket.
- Include `UNMAPPED` group for any missing mapping rows.

Weekly bucketing:

- Use source `date` as provided (date type).
- Build rolling 4 Sunday-start weeks.
- Display weeks most-recent first.

### Section 1 UI Behavior (Live v1 as of 2026-02-26)

- Route: `/reports/wbr/[clientId]`
- Backfill action calls: `POST /admin/wbr/section1/backfill-last-full-weeks`
- Weeks shown are always previous **full** Sunday-Saturday weeks only (current in-progress week is excluded).
- Table shows Section 1 weekly **totals** (across all mapped/unmapped groups) for validation.
- If one expected week has no source rows, UI still renders that week with `0` values (zero-filled gap), so `Weeks=4` always displays 4 rows.
- Backfill reruns are idempotent for the requested windows (range replace + re-aggregate), so rerunning the same weeks is safe.

### Section 2: Ads Summary

Dimensions:

- `group_label` (same grouping key as Section 1)

Metrics (4 weekly columns each):

- `impressions`
- `clicks`
- `ctr_pct` = `clicks / impressions` (0 when divisor is 0)
- `ad_spend`
- `cpc` = `ad_spend / clicks` (0 when divisor is 0)
- `ad_sales`
- `acos_pct` = `ad_spend / ad_sales` (0 when divisor is 0)
- `tacos_pct` = `ad_spend / sales` where `sales` is Section 1 total sales for same group/week (0 when divisor is 0)

Section 2 data-shaping note:

- If connector output lacks portfolio fields, ingest a separate campaign-to-portfolio mapping extract from Amazon Ads directly and join on campaign ID.
- Keep this mapping as a managed table with effective dating so historical joins remain stable when portfolio assignments change.

### Section 3: Inventory Snapshot

Dimensions:

- `group_label` (same grouping key)

Metrics (single current column per metric, not 4-week columns):

- `units_in_stock` (FBA total units)
- `working`
- `in_transit`
- `reserved_fc_transfer`
- `wos` = `(units_in_stock + reserved_fc_transfer) / avg(last_4_weeks_unit_sales)` (0 when divisor is 0)

### Section 4: Returns

- Deferred. Contract to be defined in a later iteration.

## Locked Decisions (as of 2026-02-25)

1. Weeks are Sunday-start for v1.
2. Section 1 sales metric uses ordered product sales.
3. Mixed-marketplace reporting remains marketplace-native (no FX conversion in v1; CAD stays CAD, USD stays USD).
4. `Total` row only sums included reporting groups (for example selected brands), not all account brands.
5. Number formatting should match current manual WBR conventions.

## Open Definitions

1. Returns section schema/formulas are pending.
2. First-pass UX for manual ASIN mapping is pending (likely Command Center admin surface).
3. Portfolio-to-group import behavior (one-way bootstrap vs continuous sync) is pending.

## Section 2 Source Roadmap

Near-term:

1. Keep Windsor as the source for Section 1 and Section 2 ad performance metrics.
2. Maintain a custom portfolio/campaign mapping table as fallback for grouping logic.

Long-term:

1. When direct Amazon Ads API access is approved, ingest Section 2 from Ads API directly.
2. Retire the manual portfolio mapping path if direct API payloads provide stable portfolio linkage for required joins.

## Sample Data Needed for Field Mapping

Do not paste large browser previews. Provide one exported file instead:

- Preferred: CSV export from Windsor query.
- Minimum window: last 1 day is enough to validate shape and field naming.
- Better for metric sanity checks: last 7 days.
- Scope: one account (`select_accounts=...`) to keep mapping and validation clean.

## Connector Behavior Observed

1. Each marketplace/account appears as a distinct connector account ID (example suffixes `-CA`, `-US`).
2. If `select_accounts` is not present, the query returns all currently selected accounts.
3. If `select_accounts=<account_id>` is present, the query is account-scoped.
4. Date windows can be controlled by:
   - preset mode (`date_preset=last_28d`, etc.), or
   - explicit range mode (`date_from=YYYY-MM-DD&date_to=YYYY-MM-DD`).

## Query Patterns

### All selected accounts (broad pull)

```text
https://connectors.windsor.ai/amazon_sp?api_key=***&date_preset=last_28d&fields=...
```

### Single account pull (recommended for production ingestion)

```text
https://connectors.windsor.ai/amazon_sp?api_key=***&date_preset=last_28d&fields=...&select_accounts=A1MY3C51FMRZ3Z-CA
```

### Explicit backfill window

```text
https://connectors.windsor.ai/amazon_sp?api_key=***&date_from=2025-08-29&date_to=2026-02-24&fields=...&select_accounts=A1MY3C51FMRZ3Z-CA
```

Use either `date_preset` or `date_from/date_to`, not both.

## Recommended Ingestion Strategy

1. Ingest per account ID, not all accounts in one request.
2. Backfill in windows (for example 30-day chunks) up to 180 days.
3. Nightly incremental should re-pull a short recent window (for example last 2-3 days) to absorb late updates.
4. Store raw payload rows first, then transform in Supabase (ELT) into typed fact tables.
5. Upsert idempotently using a natural key at daily grain:
   - `(account_id, date, child_asin)` plus marketplace discriminator if needed.

## Minimum Fields To Keep

Always keep:

- `account_id`
- `date`
- `sales_and_traffic_report_by_date__childasin`
- `sales_and_traffic_report_by_date__parentasin`

Recommended additions when available:

- account display name
- marketplace/country code
- currency code columns for monetary fields

## Operational Guardrails

1. Post-ingest assertion for account-scoped runs:
   - `COUNT(DISTINCT account_id) = 1`
2. Reject or quarantine rows with null `date` or null child ASIN.
3. Track per-run metadata:
   - requested account(s), date window, row count, duration, status, error.
4. Track row volume over time; spikes usually indicate account scope drift or field changes.

## Scaling Notes

Daily row count grows approximately with:

- `#accounts * #days * #child ASIN rows`

At larger scale, one-request-for-all-accounts becomes slower and harder to retry. Per-account batching is the default pattern.

## Immediate Next Steps

1. Lock Section 1 metric definitions and exact source-field mapping from Windsor fields.
2. Create ingestion run metadata table.
3. Create raw Windsor landing table.
4. Implement first per-account backfill job (single report shape).
5. Build first transformed daily fact table for Section 1 metrics.
6. Build first WBR Section 1 UI with 4-week columns and total row.
