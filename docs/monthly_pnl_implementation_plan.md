# Monthly P&L Implementation Plan

_Last updated: 2026-03-16 (ET)_

> Status: Monthly P&L v1 is partially shipped. The backfill-first import
> pipeline, standalone `/reports/.../pnl` surface, provenance/settings UI, and
> workbook-aligned transaction mapping are live. This document is still useful
> as design/reference context, but some sections remain forward-looking for
> work that is not done yet, especially COGS workflow, async/background import
> execution for multi-month uploads, and the remaining report-speed/productization
> follow-ons.

This document defines the recommended implementation plan for a new
client-facing `Monthly P&L` report in Ecomlabs Tools.

The intent is to automate the agency's second major recurring reporting flow
after the WBR:

1. `Weekly Business Review` for operational performance
2. `Monthly P&L` for accounting-style profitability review

The plan below assumes a deliberate rollout order:

1. Backfill-first from uploaded Amazon transaction files
2. Validate against existing manual Excel P&Ls
3. Add Windsor settlement ingestion for recent periods
4. Expand country handling after US is stable

## Scope and non-goals

### v1 scope

1. `US` marketplace only
2. One client-facing Monthly P&L report page under Reporting
3. Historical backfill via uploaded `Monthly Unified Transaction Report` CSVs
4. Optional COGS upload flow
5. Month-based filtering:
   - `YTD`
   - `Last X months`
   - explicit month range
6. Excel export of the rendered P&L
7. Full QA visibility for unmapped or ambiguous transaction rows
8. Support large historical upload files, including year-sized transaction exports

### explicitly out of scope for v1

1. Canada or other marketplaces
2. Direct SP-API finance integration
3. Fully automated Windsor ingestion as the only source
4. Multi-currency normalization
5. Bookkeeping-grade GL integration

## Key decisions

1. The report is accounting-style and should use `posted/released financial dates`, not order dates.
2. The first version should be built from uploaded files, not from Windsor.
3. The report engine should operate on a normalized internal ledger, not directly on raw CSV columns.
4. Windsor settlement ingestion should be added later as another source into the same normalized ledger.
5. `COGS` is external to Amazon and should be handled in a separate upload/import flow.
6. The system must preserve raw-source provenance and expose unmapped rows rather than silently dropping money.
7. Large uploaded transaction files should be accepted once, stored once, and processed asynchronously.
8. Imports should normalize and version data at the month level even when the uploaded file spans many months.
9. Financial amounts must use fixed-precision numeric storage, not floating-point types.
10. Month replacement must be atomic from the report's point of view.
11. The canonical v1 month basis should be pinned before implementation rather than deferred.

## Why backfill-first is the right approach

The uploaded `Monthly Unified Transaction Report` is currently the most stable
source for validation because:

1. It already powers the manual process the team trusts.
2. It pre-splits many finance fields into direct columns such as:
   - `product sales`
   - `shipping credits`
   - `gift wrap credits`
   - `promotional rebates`
   - `selling fees`
   - `fba fees`
   - `other transaction fees`
   - `other`
3. It includes billed advertising charges under `Service Fee / Cost of Advertising`.
4. It avoids immediate dependency on Windsor settlement performance and its current 90-day window.
5. Historical transaction files can span a full year, which is useful for rapid backfill if the import pipeline is month-aware.

Once the P&L logic is validated against manual spreadsheets, Windsor can be
added as a recent-period source feeding the same ledger.

## Source model

### Source A: Monthly Unified Transaction Report upload

Primary v1 source.

Observed useful columns from the Whoosh US sample:

1. `date/time`
2. `settlement id`
3. `type`
4. `order id`
5. `sku`
6. `description`
7. `product sales`
8. `product sales tax`
9. `shipping credits`
10. `shipping credits tax`
11. `gift wrap credits`
12. `giftwrap credits tax`
13. `promotional rebates`
14. `promotional rebates tax`
15. `marketplace withheld tax`
16. `selling fees`
17. `fba fees`
18. `other transaction fees`
19. `other`
20. `total`
21. `Transaction Status`
22. `Transaction Release Date`

This is sufficient to build a strong first P&L.

### Source B: Windsor settlement report

Future source for recent automation.

Observed Windsor settlement fields:

1. `posted_date`
2. `transaction_type`
3. `amount_type`
4. `amount_description`
5. `amount`
6. `order_id`
7. `sku`
8. `total_amount`

Notes:

1. Windsor settlement appears available for this US account.
2. Windsor currently appears limited to the last `90 days`.
3. Windsor settlement is slower/heavier than the current WBR feeds.
4. Windsor should not become the first implementation path.

### Source C: COGS upload

Separate source managed by the agency.

Expected to be optional because not every client has COGS ready at all times.

## Report model

The Monthly P&L should not depend on any single raw-source schema.

Instead:

1. Raw files are imported into a `raw import` table.
2. Each import materializes one or more `month slices` that can be activated independently.
3. Raw rows are normalized into a canonical `pnl_ledger_entries` table.
4. Ledger entries are mapped to `pnl categories`.
5. The report UI sums categories into the displayed P&L rows.

This gives us:

1. one reporting engine
2. multiple source inputs
3. strong auditability
4. future Windsor/direct-SP-API flexibility

## Proposed database model

### 1. `monthly_pnl_profiles`

One P&L configuration per client + marketplace.

Suggested fields:

1. `id`
2. `client_id uuid not null references public.agency_clients(id) on delete restrict`
3. `marketplace_code`
4. `currency_code`
5. `status` (`draft`, `active`, `archived`)
6. `notes`
7. timestamps

Constraints/indexes:

1. unique index on `(client_id, marketplace_code)` for active profiles

### 2. `monthly_pnl_imports`

Tracks uploaded files or automated source pulls.

Suggested fields:

1. `id`
2. `profile_id`
3. `source_type`
   - `amazon_transaction_upload`
   - `windsor_settlement`
   - `cogs_upload`
4. `period_start`
5. `period_end`
6. `source_filename`
7. `storage_path`
8. `source_file_sha256`
9. `import_scope`
   - `single_month`
   - `multi_month`
   - `full_year`
10. `supersedes_import_id nullable`
11. `import_status`
12. `row_count`
13. `error_message`
14. `raw_meta jsonb`
15. timestamps

Constraints/indexes:

1. unique index on `(profile_id, source_type, source_file_sha256)`
2. index on `(profile_id, source_type, period_start, period_end)`
3. index on `(profile_id, import_status)`

Notes:

1. `source_file_sha256` is the duplicate-upload guard.
2. Activation should happen at the month-slice level, not the whole-file import level.

### 3. `monthly_pnl_import_months`

Tracks month-level slices emitted from one file import or automated source pull.

Suggested fields:

1. `id`
2. `profile_id`
3. `import_id`
4. `source_type`
5. `entry_month`
6. `import_status`
7. `is_active boolean not null default false`
8. `supersedes_import_month_id nullable`
9. `raw_row_count`
10. `ledger_row_count`
11. `mapped_amount numeric(18,2) not null default 0`
12. `unmapped_amount numeric(18,2) not null default 0`
13. timestamps

Constraints/indexes:

1. unique index on `(import_id, entry_month)`
2. unique index on `(profile_id, source_type, entry_month)` where `is_active = true`
3. index on `(profile_id, source_type, entry_month, import_status)`

Notes:

1. This table is the atomic-swap control surface for report-visible months.
2. The report service should resolve months through active `monthly_pnl_import_months`, not directly from imports.

### 4. `monthly_pnl_raw_rows`

Stores the raw parsed source row for audit/debugging.

Suggested fields:

1. `id`
2. `import_id`
3. `profile_id`
4. `import_month_id nullable`
5. `source_type`
6. `row_index`
7. `posted_at`
8. `order_id`
9. `sku`
10. `raw_type`
11. `raw_description`
12. `release_at`
13. `raw_payload jsonb`
14. timestamps

Constraints/indexes:

1. unique index on `(import_id, row_index)`
2. index on `(profile_id, import_id)`
3. index on `(import_id, posted_at)`
4. index on `(import_id, release_at)`

Notes:

1. `row_index` uniqueness prevents duplicate raw-row ingestion within one import retry path.
2. `profile_id` should be denormalized onto raw rows for RLS consistency and efficient profile-scoped QA queries.

### 5. `monthly_pnl_ledger_entries`

Canonical normalized ledger rows used for the report.

Suggested fields:

1. `id`
2. `profile_id`
3. `import_id`
4. `import_month_id nullable`
5. `entry_month` (`date`, normalized to first day of month)
6. `posted_at`
7. `order_id`
8. `sku`
9. `source_type`
10. `source_subtype`
11. `raw_type`
12. `raw_description`
13. `ledger_bucket`
14. `amount numeric(18,2) not null`
15. `currency_code`
16. `is_mapped boolean`
17. `mapping_rule_id nullable`
18. `source_row_index nullable`
19. `raw_payload jsonb`
20. timestamps

`ledger_bucket` should be the canonical internal category, for example:

1. `product_sales`
2. `shipping_credits`
3. `gift_wrap_credits`
4. `promotional_rebates`
5. `refunds`
6. `fba_inventory_credit`
7. `shipping_credit_refunds`
8. `gift_wrap_credit_refunds`
9. `promotional_rebate_refunds`
10. `referral_fees`
11. `fba_fees`
12. `other_transaction_fees`
13. `fba_monthly_storage_fees`
14. `fba_long_term_storage_fees`
15. `fba_removal_order_fees`
16. `subscription_fees`
17. `inbound_placement_and_defect_fees`
18. `inbound_shipping_and_duties`
19. `liquidation_fees`
20. `advertising`
21. `marketplace_withheld_tax`
22. `non_pnl_transfer`
23. `unmapped`

Constraints/indexes:

1. unique index on `(import_id, source_row_index, ledger_bucket, amount, coalesce(order_id, ''), coalesce(sku, ''))`
2. index on `(profile_id, entry_month, ledger_bucket)`
3. index on `(profile_id, entry_month, is_mapped)`
4. index on `(profile_id, source_type, entry_month)`

Notes:

1. The uniqueness rule is meant to block duplicate ledger expansion during retries.
2. The exact dedupe key can be adjusted during implementation, but v1 must not allow silent month doubling from import retries.
3. During implementation, prefer a stable source-row-based uniqueness rule over amount-included dedupe where the source identity is reliable.

### 6. `monthly_pnl_mapping_rules`

Deterministic mapping rules from raw row patterns to canonical ledger buckets.

Suggested fields:

1. `id`
2. `profile_id nullable`
   - null for global default rules
3. `marketplace_code`
4. `source_type`
5. `match_spec jsonb`
6. `match_operator`
7. `match_value`
8. `target_bucket`
9. `priority`
10. `active`
11. timestamps

Example rule:

1. `source_type = amazon_transaction_upload`
2. `match_spec = {"type":"Service Fee","description":"Cost of Advertising"}`
3. `match_operator = exact_fields`
4. `match_value = null`
5. `target_bucket = advertising`

Notes:

1. The mapping rule should not depend on a pipe-delimited freeform string like `type|description`.
2. Use structured matching so implementation mistakes do not silently unmap money.
3. If both a global rule and a profile-specific rule match, the profile-specific rule should always win before priority is considered.

### 7. `monthly_pnl_cogs_monthly`

Optional COGS source.

Suggested fields:

1. `id`
2. `profile_id`
3. `entry_month`
4. `sku nullable`
5. `asin nullable`
6. `amount numeric(18,2) not null`
7. `currency_code`
8. `source_import_id`
9. timestamps

v1 can support client-month total COGS without SKU granularity if needed.

Constraints/indexes:

1. unique index on `(profile_id, entry_month, coalesce(sku, ''), coalesce(asin, ''))`

## Raw-source normalization rules

### A. Monthly Unified Transaction Report normalization

For transaction-report uploads, each source row can yield multiple ledger rows.

Example:

One raw Amazon row may generate:

1. `product_sales`
2. `shipping_credits`
3. `gift_wrap_credits`
4. `promotional_rebates`
5. `marketplace_withheld_tax`
6. `referral_fees`
7. `fba_fees`
8. `other_transaction_fees`
9. `other`-mapped fee rows

This is preferable to preserving the source row as one indivisible record,
because the P&L is bucket-based, not row-based.

### B. Windsor settlement normalization

For Windsor settlement rows, each source row usually produces one ledger row.

Mapping is based on:

1. `transaction_type`
2. `amount_type`
3. `amount_description`

### C. Transfers and payouts

Rows representing cash movement only must be stored but excluded from P&L.

Example:

1. `Transfer`
2. payout rows like `To your account ending in ...`

These should map to `non_pnl_transfer`.

## Initial US P&L row mapping

### Revenue section

1. `Product sales`
   - transaction upload:
     - `product sales`
   - Windsor settlement:
     - `ItemPrice / Principal`
2. `Shipping credits`
   - transaction upload:
     - `shipping credits`
   - Windsor settlement:
     - `ItemPrice / Shipping`
3. `Gift wrap credits`
   - transaction upload:
     - `gift wrap credits`
   - Windsor settlement:
     - likely dedicated gift-wrap descriptions if present
4. `Promotional rebate refunds`
   - transaction upload:
     - positive rebate-related adjustment/refund lines as found
   - Windsor settlement:
     - promotion-related positive reversal descriptions
5. `FBA liquidation proceeds`
   - map once observed
6. `Amazon Shipping Reimbursement Adj`
   - map once observed

### Refund section

1. `Refunds`
   - transaction upload:
     - negative `product sales` on `Refund` rows
   - Windsor settlement:
     - `Refund` transaction rows against principal
2. `FBA inventory credit`
   - transaction upload:
     - `Adjustment / FBA Inventory Reimbursement - *`
   - Windsor settlement:
     - `FBA Inventory Reimbursement / *`
3. `Shipping credit refunds`
   - transaction upload:
     - negative `shipping credits` on refund rows
   - Windsor settlement:
     - refund shipping rows
4. `Gift wrap credits refunds`
   - map when observed
5. `Promotional rebates`
   - transaction upload:
     - `promotional rebates`
   - Windsor settlement:
     - `Promotion / Principal|Shipping`
6. `A-to-z Guarantee claims`
   - map when observed
7. `Chargebacks`
   - map when observed

### Expense section

1. `Referral fees`
   - transaction upload:
     - `selling fees`
   - Windsor settlement:
     - `ItemFees / Commission`
2. `FBA fees`
   - transaction upload:
     - `fba fees`
   - Windsor settlement:
     - `ItemFees / FBAPerUnitFulfillmentFee`
3. `Other transaction fees`
   - transaction upload:
     - `other transaction fees`
   - Windsor settlement:
     - `SalesTaxServiceFee`
     - `ShippingChargeback`
     - `RefundCommission`
     - other non-FBA/non-referral fee descriptions
4. `FBA monthly storage fees`
   - transaction upload:
     - `FBA Inventory Fee / FBA storage fee`
   - Windsor settlement:
     - `other-transaction / Storage Fee`
5. `FBA long-term storage fees`
   - transaction upload:
     - `FBA Inventory Fee / FBA Long-Term Storage Fee`
   - Windsor settlement:
     - `other-transaction / StorageRenewalBilling` or explicit long-term storage descriptions
6. `FBA removal order fees`
   - transaction upload:
     - `FBA Inventory Fee / FBA Removal Order: Disposal Fee`
   - Windsor settlement:
     - `other-transaction / RemovalComplete`
     - `other-transaction / DisposalComplete`
7. `Subscription fees`
   - transaction upload:
     - `Service Fee / Subscription`
   - Windsor settlement:
     - `other-transaction / Subscription Fee`
8. `Inbound placement & defect fees`
   - transaction upload:
     - `Service Fee / FBA Inbound Placement Service Fee`
   - Windsor settlement:
     - `other-transaction / FBA Inbound Placement Service Fee`
9. `Inbound shipping fees & duties`
   - map only if observed in source
10. `Liquidation fees`
   - map when observed
11. `Promotions fees`
   - transaction upload:
     - coupon participation/performance fees if kept separate
   - Windsor settlement:
     - `Coupon Participation Fee`
     - `Coupon Performance Based Fee`
12. `Advertising`
   - transaction upload:
     - `Service Fee / Cost of Advertising`
   - Windsor settlement:
     - `Cost of Advertising / TransactionTotalAmount`

### Derived rows

These should not be stored as source facts:

1. `Total Gross Revenue`
2. `Total Refunds`
3. `Total Net Revenue`
4. `Gross Profit`
5. `Total Expenses`
6. `Net Earnings`

They should be computed in the report service.

## UI plan

### Reporting home

Add a new report card:

1. `Monthly P&L`

### Main route

Recommended route shape:

1. `/reports/[clientSlug]/[marketplaceCode]/pnl`

### Main screen

Sections:

1. Header / filters
2. Source freshness / upload status
3. P&L table
4. Unmapped warnings
5. Export actions

### Filters

v1 filters:

1. `YTD`
2. `Last 3 / 6 / 12 months`
3. explicit month range
4. `Include COGS` on/off if missing

### Supporting screens

1. `Uploads`
   - upload transaction reports
   - upload COGS
2. `QA`
   - unmapped rows
   - totals by source
   - import warnings
   - duplicate-file rejection or supersession visibility
3. `Settings`
   - optional client-specific mapping overrides later

## Import pipeline

### Transaction upload pipeline

1. Upload CSV
2. Stream the raw file to storage/backend rather than reading the whole payload into memory at once
3. Detect header row and validate schema
4. Create `monthly_pnl_imports`
5. Persist the import as a background job, not a long blocking request
6. Determine each row's canonical `entry_month` using the pinned financial date rule
7. Create/update `monthly_pnl_import_months` slices for the months present in the file
8. Parse raw rows into `monthly_pnl_raw_rows`
9. Expand rows into normalized `monthly_pnl_ledger_entries`
10. Apply mapping rules
11. Flag unmapped entries
12. Recompute month-slice aggregates
13. Atomically activate completed month slices so the UI can show which months were loaded from one file

#### file storage

The original uploaded file should be preserved so we can reprocess older data after mapping-rule changes.

Recommended storage design:

1. Supabase Storage bucket dedicated to finance/reporting imports
2. path convention:
   - `monthly-pnl/{profile_id}/{source_type}/{import_id}/{original_filename}`
3. store the bucket path on `monthly_pnl_imports.storage_path`
4. compute and store `source_file_sha256` during upload
5. bucket creation should be scripted in repo, not handled as an undocumented manual setup step

#### import behavior for large files

The system should allow a user to upload a year-sized transaction file once,
then process it into month-level slices internally.

Recommended behavior:

1. upload unit: one CSV file that may cover multiple months
2. processing unit: month
3. reporting unit: month

Benefits:

1. easier retries for a single bad month
2. easier replacement of corrected month data later
3. simpler QA and reconciliation
4. lower memory pressure during import

#### replacement and versioning rules

For `amazon_transaction_upload`:

1. if an import contains months not yet present for the profile, insert them
2. if an import contains months already present for the profile, replace or supersede those months cleanly
3. preserve old import metadata for auditability even if month-level report data is superseded

The report service should always resolve to the latest active `monthly_pnl_import_months` slice for a given profile/month/source class.

#### atomic month replacement

Naive delete-then-insert is not acceptable.

The implementation should use one of these patterns:

1. import into staging rows/imports first, then atomically mark the new import/month slice active
2. insert the new month slice fully, then supersede the old active month slice in one transaction
3. use a report query that only reads `is_active = true` month slices and only flips active status once the replacement month is complete

The important contract is:

1. the report must never temporarily show `$0` because a month was deleted before replacement finished
2. the report must never read partial month data from a still-running import

#### canonical month assignment

For the uploaded Monthly Unified Transaction Report:

1. use `Transaction Release Date` as the canonical month basis for v1 when present
2. if `Transaction Release Date` is blank, fall back to `date/time`
3. persist both values on raw rows so future reprocessing remains possible
4. document this clearly in the UI and validation notes because it affects reconciliation against manual spreadsheets

### COGS upload pipeline

1. Upload month-based COGS file
2. Validate month/client/marketplace
3. Store by month and optional SKU/ASIN
4. Recompute gross profit / net earnings

### Windsor pipeline (future)

1. Query settlement extract for recent window
2. Normalize into same `monthly_pnl_ledger_entries`
3. Run the same mapping layer
4. Merge with existing months using source precedence rules

## QA requirements

These are mandatory.

1. No money should disappear silently.
2. Every import must show:
   - raw row count
   - normalized ledger row count
   - mapped amount
   - unmapped amount
3. Report screen should warn when:
   - COGS missing
   - unmapped rows present
   - months incomplete
4. Every rendered P&L row must be drillable back to source lines.
5. Duplicate uploads of the exact same file should be blocked or explicitly treated as a superseding reprocess, never silently double-loaded.

## RLS and access control

These tables contain client-scoped financial data and must ship with RLS from day one.

Recommended v1 policy shape:

1. admin users can view/manage all Monthly P&L profiles, imports, raw rows, ledger entries, mappings, and COGS rows
2. future client-facing access should be profile/client-scoped, not global

Minimum requirement:

1. every new P&L table gets RLS enabled
2. every table gets explicit policies, following the same standard used by WBR tables
3. child-table policies should resolve access through `monthly_pnl_profiles -> agency_clients`, not rely on ad hoc client identifiers on each row
4. every mutable table should also get the standard `updated_at` trigger pattern used by WBR tables

## Known risks and edge cases

1. `US first only`
   - CA will likely have different labels and tax treatment.
2. `Gift wrap / liquidation / claims / chargebacks`
   - may not appear in every sample month
   - mapping must remain extensible
3. `Transfers`
   - must not pollute P&L
4. `Marketplace withheld tax`
   - presentation rule must be consistent across months
5. `Posted date vs release date`
   - v1 should use `Transaction Release Date` when present; the implementation should not defer this choice
6. `Source drift`
   - Amazon file schemas and Windsor labels may change

## Recommended build order

### Phase 1: Foundation

1. Add P&L profile/import/ledger/mapping tables
2. Add transaction report upload backend
3. Add normalized ledger expansion
4. Add unmapped QA output

### Phase 2: First usable report

1. Add Monthly P&L route
2. Add month filters
3. Render derived rows
4. Add Excel export

### Phase 3: COGS

1. Add COGS import
2. Fold COGS into gross profit / net earnings
3. Add missing-COGS warnings

### Phase 4: Validation

1. Reconcile multiple months against manual agency spreadsheets
2. Harden mappings for observed edge labels
3. Add QA tools for unmapped amounts

### Phase 5: Windsor settlement automation

1. Add Windsor settlement import path for recent periods
2. Normalize to same ledger
3. Compare Windsor months vs uploaded months
4. Only then promote Windsor to the primary recent-period source

### Phase 6: CA expansion

1. Add CA marketplace profile support
2. Introduce marketplace-specific mapping packs
3. Validate tax and fee-label differences

## Recommendation

Build the P&L system as a normalized finance-ledger tool, not a one-off report.

That gives us:

1. reliable backfill now
2. validation against existing manual reports
3. Windsor automation later without redesign
4. room for CA and other countries after the US mapping is stable
