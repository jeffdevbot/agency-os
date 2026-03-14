# WBR v2 Prototype Plan

> The concrete database design for this plan lives in `docs/wbr_v2_schema_plan.md`.

This document defines the next WBR prototype beyond the original
Windsor-only Section 1 scaffold. It captures the target setup flow, data
model, ingest strategy, refresh cadence, and phased implementation plan that
drove the first client-ready rollout.

## Current implementation status

As of March 14, 2026:

1. WBR v2 migrations 1-6 are applied live, including Amazon Ads OAuth
   connections, Ads fact-table uniqueness hardening, and nightly auto-sync
   flags.
2. The profile setup flow is shipped:
   - `/reports/wbr`
   - `/reports/wbr/setup`
   - `/reports/wbr/[profileId]` as compatibility redirect
   - `/reports/[clientSlug]/[marketplaceCode]/wbr/settings` as the primary
     settings workspace
3. Pacvue import, listings import, ASIN mapping, Windsor listings import, row
   management, and row delete safeguards are shipped.
4. Section 1 Windsor sync/report and Section 2 Amazon Ads sync/report are
   shipped on the client-first report routes.
5. The sync UX is shipped under:
   - `/reports/[clientSlug]/[marketplaceCode]/wbr/sync`
   - `/reports/[clientSlug]/[marketplaceCode]/wbr/sync/sp-api`
   - `/reports/[clientSlug]/[marketplaceCode]/wbr/sync/ads-api`
6. `worker-sync` is implemented in-repo and runs nightly `daily_refresh` jobs
   for `active` profiles with per-profile source toggles.
7. The old Windsor-only `/admin/wbr/section1/*` backend remains as legacy
   compatibility surface and should not be treated as the primary WBR path.

The sections below still capture the design rationale that led to the shipped
implementation. Where they read like forward-looking rollout steps, treat them
as historical planning context rather than pending work.

## Why this doc exists

The existing `windsor_wbr_ingestion_runbook.md` is still useful, but it is narrowly about Windsor Section 1 ingest. The WBR prototype now needs a broader plan because the report depends on three distinct concerns:

1. Source ingestion from multiple systems.
2. A client-and-marketplace-specific reporting row model.
3. Ongoing QA for unmapped data and late-arriving updates.

## Current decisions

These decisions are now treated as the prototype contract unless changed explicitly.

1. One WBR profile is created per client per marketplace.
2. Windsor remains the source for business data such as page views, units, and sales.
3. Amazon Ads API becomes the source for campaign performance data.
4. Pacvue export remains the source of truth for campaign grouping metadata.
5. Campaigns are matched to Pacvue by exact `campaign_name`.
6. Pacvue tag parsing creates leaf rows by removing the final goal suffix.
7. Goal suffix is stored separately for future use but is not required in the first WBR renderer.
8. Parent rows are optional and manually configured.
9. ASIN mapping is child-ASIN-only in v1.
10. Each child ASIN maps to exactly one leaf row.
11. The row tree is shared across Sections 1 and 2.
12. Week start is configured per WBR profile. v1 should support `sunday` and `monday`.
13. Unmapped campaigns and unmapped ASINs are first-class QA outputs.

## Report model

The WBR is not primarily a data-ingest problem. It is a reporting-taxonomy problem.

The core reporting model is:

1. A WBR profile identifies the client + marketplace + week settings + source credentials/config.
2. A row tree defines what appears in the report.
3. Business facts roll up to leaf rows through `child_asin -> leaf row`.
4. Ad facts roll up to leaf rows through `campaign_name -> Pacvue tag -> leaf row`.
5. Parent rows are sums of child rows only.

This replaces the current flat `group_label` approach.

## Source systems

### 1. Windsor business data

Source purpose:

- Seller Central sales and traffic data at daily child ASIN grain.
- Potential listing/catalog metadata source if sufficient for onboarding.

Prototype usage:

- Ingest daily business facts.
- Optionally ingest listing metadata if the Windsor merchant listings report is clean enough.

### 2. Amazon Ads API

Source purpose:

- Daily campaign performance facts.

Prototype usage:

- Ingest campaign metrics by day.
- Use exact `campaign_name` for the Pacvue join.
- Treat unmatched campaign names as QA items.

### 3. Pacvue xlsx export

Source purpose:

- Campaign grouping metadata.
- Raw tag values used to derive WBR leaf rows.

Prototype usage:

- Operator uploads one marketplace/account-scoped export during setup and whenever mappings need refresh.
- Parse campaign name and tags.
- Derive normalized leaf row label from tag.
- Extract campaign goal suffix separately.

### 4. Listing/all-listings source

Source purpose:

- Full child ASIN inventory for onboarding and mapping.

Prototype usage:

- Preferred first pass: upload an all-listings-style file during setup.
- Alternative: if Windsor merchant listings is complete and stable, it can become the listings source later.

## Pacvue tag parsing contract

Example raw tag:

`QALO | QRNT Smart Ring / Def`

Prototype parsing behavior:

1. `raw_tag` = `QALO | QRNT Smart Ring / Def`
2. `leaf_row_label` = `QALO | QRNT Smart Ring`
3. `goal_code` = `Def`

Expected goal codes:

- `Perf`
- `Rsrch`
- `Comp`
- `Harv`
- `Def`
- `Rank`

If a tag does not match the expected suffix pattern, it should be flagged in import QA rather than guessed silently.

## Prototype data model

### 1. `wbr_profiles`

Purpose:

- One WBR config per client + marketplace.

Suggested fields:

- `id`
- `client_id`
- `marketplace_code`
- `display_name`
- `windsor_account_id`
- `amazon_ads_profile_id` or equivalent account identifiers
- `week_start_day` (`sunday` or `monday`)
- `status`
- `created_by`
- `updated_by`
- timestamps

Notes:

- Treat each marketplace separately even if the client has multiple markets.
- This keeps row definitions and source mappings isolated.

### 2. `wbr_rows`

Purpose:

- Store the report row tree.

Suggested fields:

- `id`
- `profile_id`
- `row_label`
- `row_kind` (`parent`, `leaf`)
- `parent_row_id` nullable
- `sort_order`
- `active`
- timestamps

Notes:

- Parent rows are optional.
- Leaf rows should initially be created from normalized Pacvue tags.
- Ordering should be operator-controlled. Dynamic sorting by sales/page views can be added later as a view option, but persisted row order is still needed.

### 3. `wbr_pacvue_campaign_map`

Purpose:

- Store uploaded Pacvue campaign/tag metadata.

Suggested fields:

- `id`
- `profile_id`
- `import_batch_id`
- `campaign_name`
- `raw_tag`
- `row_id`
- `leaf_row_label`
- `goal_code`
- `active`
- `raw_payload`
- timestamps

Notes:

- Exact `campaign_name` is the initial join key.
- Persist both the normalized row label and the resolved `row_id`.
- Keep import batches so operators can refresh mapping and inspect drift.

### 4. `wbr_asin_row_map`

Purpose:

- Manual mapping from child ASIN to leaf row.

Suggested fields:

- `id`
- `profile_id`
- `child_asin`
- `row_id`
- `source` (`manual`, `imported`, `suggested`)
- `active`
- timestamps

Notes:

- One child ASIN maps to exactly one leaf row in v1.
- Leave room to add parent-ASIN-based helpers later, but do not model parent ASIN as the source of truth yet.

### 5. `wbr_business_asin_daily`

Purpose:

- Daily business facts at child ASIN grain.

Suggested fields:

- `id`
- `profile_id`
- `report_date`
- `child_asin`
- `parent_asin`
- `currency_code`
- `page_views`
- `unit_sales`
- `sales`
- `source_row_count`
- `source_payload`
- timestamps

### 6. `wbr_ads_campaign_daily`

Purpose:

- Daily ad performance at campaign grain.

Suggested fields:

- `id`
- `profile_id`
- `report_date`
- `campaign_id` nullable
- `campaign_name`
- `impressions`
- `clicks`
- `spend`
- `orders`
- `sales`
- any other directly available campaign metrics
- `source_payload`
- timestamps

Notes:

- Even if `campaign_id` exists in Amazon Ads API, matching to Pacvue is still by `campaign_name` for now.
- Keep `campaign_id` anyway because it will matter later.

### 7. QA or helper views/tables

Needed early:

- `wbr_unmapped_campaigns`
- `wbr_unmapped_asins`
- `wbr_source_vs_report_totals`
- import/ingest run tables for Pacvue and Ads API in addition to Windsor

## Setup workflow

### New client + marketplace WBR setup

1. Create WBR profile.
2. Set marketplace and week start day.
3. Save Windsor account id.
4. Save Amazon Ads account/profile identifiers.
5. Upload Pacvue export for that marketplace.
6. Parse campaigns and tags.
7. Auto-create leaf rows from normalized tags.
8. Manually add parent rows if needed.
9. Assign leaf rows to parents if needed.
10. Upload listings source.
11. Review discovered child ASINs.
12. Map child ASINs to leaf rows.
13. Run historical backfill.
14. Review QA tables.
15. Open final WBR renderer.

Current app status against this workflow:

1. Steps 1 and 2 are now live.
2. Steps 3 and 4 are supported at the profile-config level.
3. Steps 5 through 15 are still planned work.

## Historical backfill and refresh policy

This needs to be explicit because both business and ads data restate after the initial load.

### Historical backfill

Prototype requirement:

- The operator must be able to ingest as much historical data as source systems allow during initial setup.
- The operator must also be able to rerun older windows later from the UI.

Recommended prototype behavior:

1. Initial setup supports a backfill start date.
2. The system runs chunked backfill jobs from that start date through the most recent closed day.
3. Chunk size should be source-specific.
4. Completed chunks should be tracked so restarts are safe.
5. Operators can rerun any historical date range manually.

Suggested chunking:

- Windsor business data: weekly or 28-day chunks depending on source reliability.
- Amazon Ads API: 7-day or 14-day chunks depending on rate limits and payload size.

### Ongoing refresh cadence

Recommended default:

- Daily scheduled refresh for all active WBR profiles.

This should not be append-only. It must rewrite recent windows.

### Why rewrite recent windows

#### Ads data

Ad data has both a reporting lag and attribution lag.

Given current assumptions:

- reporting lag: about 48 hours
- attribution lag: about 7 days

Prototype policy for ads:

- Daily job rewrites the last 14 days for each active WBR profile.

Reasoning:

- 14 days is enough to absorb the known 7-day attribution lag plus reporting delay with some safety.
- This is simple and robust for the prototype.

### Business data

Business data can also restate due to cancellations and related post-order changes.

Prototype policy for business data:

- Daily job rewrites the last 14 days by default.
- Allow the rewrite window to be widened later if needed per client.

Reasoning:

- The business restatement pattern is usually smaller than ads attribution drift, but it is not zero.
- A rolling 14-day rewrite keeps the prototype simple and keeps reported weeks materially accurate.

### Older data maintenance

Recommended prototype behavior:

1. Daily refresh handles only the rolling rewrite window.
2. A weekly maintenance job can optionally rewrite the prior 8 weeks as a safety pass.
3. Operators can trigger older reruns manually when investigating discrepancies.

## Rollup rules

### Section 1: business metrics

From `wbr_business_asin_daily`, join `child_asin -> leaf row`, then aggregate into weekly buckets per configured week start.

Metrics:

- `page_views`
- `unit_sales`
- `unit_conversions_pct = unit_sales / page_views`
- `sales`

### Section 2: ads metrics

From `wbr_ads_campaign_daily`, join `campaign_name -> Pacvue map -> leaf row`, then aggregate into weekly buckets per configured week start.

Metrics:

- `impressions`
- `clicks`
- `ctr_pct = clicks / impressions`
- `ad_spend`
- `cpc = ad_spend / clicks`
- `ad_orders`
- `ad_conversion_rate = ad_orders / clicks`
- `ad_sales`
- `acos_pct = ad_spend / ad_sales`
- `tacos_pct = ad_spend / business_sales`

### Parent row behavior

- Parents have no direct assignments in v1.
- Parent values are sums of child rows only.
- A leaf row can exist without a parent.

## QA requirements

QA is part of the product, not a nice-to-have.

Prototype QA views should include:

1. Unmapped campaigns from Ads API.
2. Unmapped child ASINs from listings/business facts.
3. Pacvue tag parse failures.
4. Source totals vs WBR totals by week.
5. Last successful ingest times per source.
6. Backfill progress and rerun status.

This replaces the current manual process of noticing totals are off after the fact.

## Renderer scope for the prototype

The first real renderer should support:

1. Shared row tree across Section 1 and Section 2.
2. Expandable parent rows.
3. Four-week rolling display.
4. Week headers showing explicit date ranges.
5. Total row.
6. Sunday or Monday week start according to profile config.

Inventory can remain out of scope for this prototype.

## Historical implementation order

### Phase 1: foundation

1. Add WBR profile model.
2. Add row tree tables.
3. Add Pacvue import tables.
4. Add child ASIN mapping tables.
5. Keep current Windsor logic isolated; do not try to stretch `group_label` further.

### Phase 2: onboarding workflow

1. Profile setup screen.
2. Pacvue xlsx upload and parse.
3. Leaf row generation.
4. Parent row editor.
5. Listings upload and child ASIN mapping.

### Phase 3: source ingestion

1. Windsor business ingest into new business fact tables.
2. Amazon Ads API ingest into new ad fact tables.
3. Historical backfill runner.
4. Rolling daily rewrite jobs.

### Phase 4: QA and renderer

1. Unmapped campaigns QA.
2. Unmapped ASINs QA.
3. Source-vs-report reconciliation.
4. Final WBR table with expandable parents.

## Historical prototype shortcuts

These shortcuts were acceptable in the first prototype plan. The shipped app no
longer follows every shortcut exactly, but they remain useful context for the
tradeoffs made during rollout.

1. Match Pacvue to Ads API by exact campaign name only.
2. Require one Pacvue export per marketplace/account during setup.
3. Keep leaf labels non-editable.
4. Use manual parent setup.
5. Use manual ASIN mapping UI rather than building auto-mapping logic first.
6. Support only Sunday and Monday week starts in the first pass.
7. Skip inventory until core business + ads sections are correct.

## Risks and mitigations

### Risk: campaign name drift

Issue:

- If campaign names change, Pacvue mapping can break.

Mitigation:

- Exact-match join for prototype.
- Unmapped campaigns QA table.
- Preserve import batches for inspection.
- Add alias handling later if drift becomes frequent.

### Risk: row-tree complexity expands quickly

Issue:

- Parent/child display logic can become the bottleneck.

Mitigation:

- Keep v1 parent rules simple: summed rollups only.
- Do not allow parent rows to have direct assignments.

### Risk: late-arriving data produces mismatched totals

Issue:

- Append-only ingest will drift from source truth.

Mitigation:

- Use rolling rewrite windows, not append-only sync.
- Keep manual rerun controls available in UI.

## Deferred items

These should not block the prototype:

1. Inventory sections.
2. Goal-based breakouts in the renderer.
3. Parent-ASIN-based bulk mapping helpers.
4. Campaign alias management UI.
5. Fully dynamic row sorting based on latest metric values.
6. Multi-marketplace rollup views.

## Prototype scope now supported

The shipped prototype now supports this end-to-end flow for one client and one
marketplace:

1. Create profile.
2. Upload Pacvue export.
3. Auto-generate leaf rows.
4. Add parents manually.
5. Import listings from file or Windsor.
6. Map child ASINs.
7. Backfill historical Windsor business data.
8. Backfill historical Amazon Ads campaign data.
9. Run manual or nightly rewrite syncs.
10. Validate sync history plus mapping QA.
11. Render a rolling 4-week WBR with shared rows across Sections 1 and 2.
