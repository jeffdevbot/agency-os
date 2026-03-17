# Monthly P&L Implementation Plan

_Last updated: 2026-03-16 (ET)_

> Status: Monthly P&L v1 is shipped. The backfill-first import pipeline,
> standalone `/reports/.../pnl` surface, provenance/settings UI, workbook-aligned
> transaction mapping, async/background imports with worker-based processing,
> pre-computed bucket summary table, concurrent report queries, and frontend
> import polling are all live. Phases 1, 2, and 4 from the original build order
> below are complete. Phase 3 (COGS) is now defined as fixed unit cost per SKU
> with sold quantities derived from the transaction import. The SKU-based COGS
> code path, schema migration, report integration, missing-COGS warnings, and
> settings UI are now implemented in the repo and pushed to `main`. What remains
> is product/user verification of the end-to-end UX and the calculated results
> against real client data before calling the workflow fully validated. Phase 5
> (Windsor) is next. See "v2 roadmap" at the bottom for the planned feature
> sequence.

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
4. Optional SKU-based COGS management flow
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
5. `COGS` is external to Amazon and should be managed separately from Amazon
   transaction imports. In v2 that means one fixed unit cost per SKU, with sold
   quantity derived from imported transaction rows.
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

### Source C: COGS management

Separate source managed by the agency.

Expected to be optional because not every client has COGS ready at all times.
Current implementation direction is fixed unit cost per SKU, not a month-lump
COGS upload.

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

## Database model (shipped)

All tables below are live. Created in
`20260315200000_monthly_pnl_phase1_foundation.sql` unless noted otherwise.
Table 8 was added post-ship for report performance.

### 1. `monthly_pnl_profiles`

One P&L configuration per client + marketplace.

Columns:

1. `id uuid primary key default gen_random_uuid()`
2. `client_id uuid not null references public.agency_clients(id) on delete restrict`
3. `marketplace_code text not null`
4. `currency_code text not null default 'USD'`
5. `status text not null default 'draft'` — check: `draft`, `active`, `archived`
6. `notes text`
7. `created_by uuid references public.profiles(id)`
8. `updated_by uuid references public.profiles(id)`
9. `created_at timestamptz not null default now()`
10. `updated_at timestamptz not null default now()`

Constraints/indexes:

1. unique index on `(client_id, marketplace_code)`

### 2. `monthly_pnl_imports`

Tracks uploaded files and automated source pulls. Also serves as the job
record for async/background imports.

Columns:

1. `id uuid primary key default gen_random_uuid()`
2. `profile_id uuid not null references monthly_pnl_profiles(id) on delete cascade`
3. `source_type text not null` — check: `amazon_transaction_upload`, `windsor_settlement`, `cogs_upload`
4. `period_start date`
5. `period_end date`
6. `source_filename text`
7. `storage_path text`
8. `source_file_sha256 text`
9. `import_scope text` — check: `single_month`, `multi_month`, `full_year`
10. `supersedes_import_id uuid references monthly_pnl_imports(id) on delete set null`
11. `import_status text not null default 'pending'` — check: `pending`, `running`, `success`, `error`
12. `row_count integer not null default 0` — check: `>= 0`
13. `error_message text`
14. `raw_meta jsonb not null default '{}'`
15. `initiated_by uuid references public.profiles(id)`
16. `started_at timestamptz`
17. `finished_at timestamptz`
18. `created_at timestamptz not null default now()`
19. `updated_at timestamptz not null default now()`

Constraints/indexes:

1. unique index on `(profile_id, source_type, source_file_sha256)` where `import_status = 'running'` — allows re-upload of the same file after success
2. index on `(profile_id, source_type, period_start, period_end)`
3. index on `(profile_id, import_status)`

Notes:

1. `source_file_sha256` blocks duplicate concurrent uploads but allows re-imports.
2. `started_at` / `finished_at` track async job lifecycle.
3. `raw_meta` stores the `async_import_v1` flag for queued imports.
4. Activation happens at the month-slice level, not the whole-file import level.

### 3. `monthly_pnl_import_months`

Month-level slices emitted from one import. The atomic-swap control surface
for report-visible months.

Columns:

1. `id uuid primary key default gen_random_uuid()`
2. `profile_id uuid not null references monthly_pnl_profiles(id) on delete cascade`
3. `import_id uuid not null references monthly_pnl_imports(id) on delete cascade`
4. `source_type text not null` — check: `amazon_transaction_upload`, `windsor_settlement`, `cogs_upload`
5. `entry_month date not null`
6. `import_status text not null default 'pending'` — check: `pending`, `running`, `success`, `error`
7. `is_active boolean not null default false`
8. `supersedes_import_month_id uuid references monthly_pnl_import_months(id) on delete set null`
9. `raw_row_count integer not null default 0` — check: `>= 0`
10. `ledger_row_count integer not null default 0` — check: `>= 0`
11. `mapped_amount numeric(18,2) not null default 0`
12. `unmapped_amount numeric(18,2) not null default 0`
13. `created_at timestamptz not null default now()`
14. `updated_at timestamptz not null default now()`

Constraints/indexes:

1. unique index on `(import_id, entry_month)`
2. unique index on `(profile_id, source_type, entry_month)` where `is_active = true`
3. index on `(profile_id, source_type, entry_month, import_status)`

Notes:

1. The report service resolves months through active import months, not directly
   from imports.
2. Only one import month can be active per profile + source_type + entry_month.

### 4. `monthly_pnl_raw_rows`

Raw parsed source rows preserved for audit/debugging.

Columns:

1. `id uuid primary key default gen_random_uuid()`
2. `import_id uuid not null references monthly_pnl_imports(id) on delete cascade`
3. `profile_id uuid not null references monthly_pnl_profiles(id) on delete cascade`
4. `import_month_id uuid references monthly_pnl_import_months(id) on delete set null`
5. `source_type text not null` — check: `amazon_transaction_upload`, `windsor_settlement`, `cogs_upload`
6. `row_index integer not null` — check: `>= 0`
7. `posted_at timestamptz`
8. `order_id text`
9. `sku text`
10. `raw_type text`
11. `raw_description text`
12. `release_at timestamptz`
13. `raw_payload jsonb not null default '{}'`
14. `created_at timestamptz not null default now()`
15. `updated_at timestamptz not null default now()`

Constraints/indexes:

1. unique index on `(import_id, row_index)`
2. index on `(profile_id, import_id)`
3. index on `(import_id, posted_at)`
4. index on `(import_id, release_at)`

### 5. `monthly_pnl_ledger_entries`

Canonical normalized ledger rows. The report reads from these (via the summary
table or RPC aggregation).

Columns:

1. `id uuid primary key default gen_random_uuid()`
2. `profile_id uuid not null references monthly_pnl_profiles(id) on delete cascade`
3. `import_id uuid not null references monthly_pnl_imports(id) on delete cascade`
4. `import_month_id uuid references monthly_pnl_import_months(id) on delete set null`
5. `entry_month date not null`
6. `posted_at timestamptz`
7. `order_id text`
8. `sku text`
9. `source_type text not null` — check: `amazon_transaction_upload`, `windsor_settlement`, `cogs_upload`
10. `source_subtype text`
11. `raw_type text`
12. `raw_description text`
13. `ledger_bucket text not null`
14. `amount numeric(18,2) not null`
15. `currency_code text not null default 'USD'`
16. `is_mapped boolean not null default false`
17. `mapping_rule_id uuid references monthly_pnl_mapping_rules(id) on delete set null`
18. `source_row_index integer`
19. `raw_payload jsonb not null default '{}'`
20. `created_at timestamptz not null default now()`
21. `updated_at timestamptz not null default now()`

#### Ledger buckets (canonical)

Revenue:

1. `product_sales`
2. `shipping_credits`
3. `gift_wrap_credits`
4. `promotional_rebate_refunds`
5. `fba_liquidation_proceeds`

Refunds:

1. `refunds`
2. `fba_inventory_credit`
3. `shipping_credit_refunds`
4. `gift_wrap_credit_refunds`
5. `promotional_rebates`
6. `a_to_z_guarantee_claims`
7. `chargebacks`

Expenses:

1. `referral_fees`
2. `fba_fees`
3. `other_transaction_fees`
4. `fba_monthly_storage_fees`
5. `fba_long_term_storage_fees`
6. `fba_removal_order_fees`
7. `subscription_fees`
8. `inbound_placement_and_defect_fees`
9. `inbound_shipping_and_duties`
10. `liquidation_fees`
11. `promotions_fees`
12. `advertising`

Stored but excluded from report totals:

1. `non_pnl_transfer` — cash movement / disbursements (excluded from P&L, used for disbursements tab)
2. `unmapped` — rows that did not match any mapping rule
3. `marketplace_withheld_tax` — pass-through tax, not a P&L item

Constraints/indexes:

1. unique index on `(import_id, source_row_index, ledger_bucket)` where `source_row_index is not null`
2. index on `(profile_id, entry_month, ledger_bucket)`
3. index on `(profile_id, entry_month, is_mapped)`
4. index on `(profile_id, source_type, entry_month)`
5. index on `(import_month_id, entry_month, ledger_bucket)` — added in `20260316194500` for RPC optimization

### 6. `monthly_pnl_mapping_rules`

Deterministic mapping rules from raw row patterns to canonical ledger buckets.
Profile-specific rules always win before priority is considered.

Columns:

1. `id uuid primary key default gen_random_uuid()`
2. `profile_id uuid references monthly_pnl_profiles(id) on delete cascade` — null for global default rules
3. `marketplace_code text not null default 'US'`
4. `source_type text not null` — check: `amazon_transaction_upload`, `windsor_settlement`
5. `match_spec jsonb not null default '{}'`
6. `match_operator text not null default 'exact_fields'` — check: `exact_fields`, `contains`, `starts_with`, `regex`
7. `target_bucket text not null`
8. `priority integer not null default 100`
9. `active boolean not null default true`
10. `created_at timestamptz not null default now()`
11. `updated_at timestamptz not null default now()`

Example rule:

1. `source_type = 'amazon_transaction_upload'`
2. `match_spec = {"type": "Service Fee", "description": "Cost of Advertising"}`
3. `match_operator = 'exact_fields'`
4. `target_bucket = 'advertising'`

Constraints/indexes:

1. index on `(source_type, marketplace_code, active, priority)` — for rule lookup
2. index on `(profile_id)` where `profile_id is not null` — for profile-specific rules
3. unique index on `(marketplace_code, source_type, match_spec, match_operator)` where `profile_id is null` — for global seed rules

Notes:

1. 36+ global seed rules are shipped across the Phase 1 migration and follow-up
   migrations (`20260316190000`, `20260316195500`, `20260316203000`).
2. All seed rules are for `source_type = 'amazon_transaction_upload'`. Windsor
   settlement rules will need to be seeded when that source is implemented.
3. The mapping layer is dual: Order/Refund rows use column-based expansion
   (each CSV amount column maps to a bucket), while all other row types use
   rule-based matching against `match_spec`.

### 7. `monthly_pnl_cogs_monthly`

Historical/month-lump COGS table from the earlier design. It is no longer the
active recommended path for v2 and is effectively superseded by the SKU-based
tables below.

Columns:

1. `id uuid primary key default gen_random_uuid()`
2. `profile_id uuid not null references monthly_pnl_profiles(id) on delete cascade`
3. `entry_month date not null`
4. `sku text`
5. `asin text`
6. `amount numeric(18,2) not null`
7. `currency_code text not null default 'USD'`
8. `source_import_id uuid references monthly_pnl_imports(id) on delete set null`
9. `created_at timestamptz not null default now()`
10. `updated_at timestamptz not null default now()`

Constraints/indexes:

1. unique index on `(profile_id, entry_month, coalesce(sku, ''), coalesce(asin, ''))`

### 8. `monthly_pnl_import_month_bucket_totals`

Pre-computed per-month bucket totals for report performance. Populated at
import time and backfilled for historical data.

Added in `20260316213000_add_monthly_pnl_import_month_bucket_totals.sql`.

Columns:

1. `id uuid primary key default gen_random_uuid()`
2. `profile_id uuid not null references monthly_pnl_profiles(id) on delete cascade`
3. `import_id uuid not null references monthly_pnl_imports(id) on delete cascade`
4. `import_month_id uuid not null references monthly_pnl_import_months(id) on delete cascade`
5. `entry_month date not null`
6. `ledger_bucket text not null`
7. `amount numeric(18,2) not null default 0`
8. `created_at timestamptz not null default now()`
9. `updated_at timestamptz not null default now()`

Constraints/indexes:

1. unique index on `(import_month_id, ledger_bucket)`
2. index on `(profile_id, entry_month, import_month_id)`

Notes:

1. The report service reads this table first for bucket totals. Falls back to
   the `pnl_report_bucket_totals()` RPC if the table query fails.
2. Rows are inserted during `_insert_bucket_totals()` in `transaction_import.py`
   when each month slice is activated.

### 9. `monthly_pnl_import_month_sku_units`

Derived per-import-month sold unit summaries by SKU. Added in
`20260317001000_add_monthly_pnl_sku_cogs_and_unit_summaries.sql`.

Columns:

1. `id uuid primary key default gen_random_uuid()`
2. `import_id uuid not null references monthly_pnl_imports(id) on delete cascade`
3. `import_month_id uuid not null references monthly_pnl_import_months(id) on delete cascade`
4. `profile_id uuid not null references monthly_pnl_profiles(id) on delete cascade`
5. `entry_month date not null`
6. `sku text not null`
7. `net_units integer not null`
8. `order_row_count integer not null default 0`
9. `refund_row_count integer not null default 0`
10. `created_at timestamptz not null default now()`
11. `updated_at timestamptz not null default now()`

Constraints/indexes:

1. unique index on `(import_month_id, sku)`
2. index on `(profile_id, entry_month, import_month_id)`

Notes:

1. Populated at import time from Amazon transaction rows.
2. Backfilled for historical imported CSV data.
3. This is the basis for computed monthly COGS in the report.

### 10. `monthly_pnl_sku_cogs`

Current fixed unit cost per SKU for each profile. Added in
`20260317001000_add_monthly_pnl_sku_cogs_and_unit_summaries.sql`.

Columns:

1. `id uuid primary key default gen_random_uuid()`
2. `profile_id uuid not null references monthly_pnl_profiles(id) on delete cascade`
3. `sku text not null`
4. `asin text`
5. `unit_cost numeric(18,4) not null`
6. `currency_code text not null default 'USD'`
7. `notes text`
8. `created_at timestamptz not null default now()`
9. `updated_at timestamptz not null default now()`

Constraints/indexes:

1. unique index on `(profile_id, sku)`
2. index on `(profile_id)`

Notes:

1. One current cost per SKU in v2.
2. No effective-date accounting, FIFO, or LIFO in the current design.

## Raw-source normalization rules

### A. Monthly Unified Transaction Report normalization (shipped)

Each source row can yield multiple ledger rows. The importer uses a dual
approach:

1. **Column-based expansion** for Order and Refund rows: each CSV amount
   column (`product sales`, `shipping credits`, `fba fees`, etc.) maps to a
   ledger bucket via `COLUMN_BUCKET_MAP`. Refund rows remap revenue columns
   to their refund-side buckets (e.g. `product_sales` → `refunds`,
   `shipping_credits` → `shipping_credit_refunds`).
2. **Rule-based matching** for all other row types (Service Fee, FBA Inventory
   Fee, Transfer, Adjustment, etc.): the row's `type` and `description` are
   matched against `monthly_pnl_mapping_rules` using `match_spec` /
   `match_operator`. Matched rows roll all amount columns into the single
   rule-determined bucket.
3. **Special handling** for Liquidations: `product_sales` →
   `fba_liquidation_proceeds`, `other_transaction_fees` → `liquidation_fees`.
4. **Same-bucket coalescing**: if a single raw row emits multiple ledger
   entries into the same bucket, they are coalesced (summed) before insert to
   avoid unique-constraint violations.

### B. Windsor settlement normalization (not yet implemented)

For Windsor settlement rows, each source row usually produces one ledger row.

Windsor settlement fields: `posted_date`, `transaction_type`, `amount_type`,
`amount_description`, `amount`, `order_id`, `sku`, `total_amount`.

Mapping will be based on:

1. `transaction_type`
2. `amount_type`
3. `amount_description`

See "Ensuring consistent mapping across sources" below.

### C. Transfers and payouts (shipped)

Rows representing cash movement are stored as `non_pnl_transfer` and excluded
from P&L totals. Matched by mapping rules against Transfer-type rows and payout
descriptions like `To your account ending in ...`.

### Ensuring consistent mapping across sources

Both CSV uploads and future Windsor settlement must produce the same ledger
buckets for the same economic events. The mapping rules table already
supports `source_type` scoping, so each source gets its own rules that target
the shared canonical buckets.

When Windsor settlement is implemented:

1. Seed `windsor_settlement` rules in a migration, one rule per bucket, using
   Windsor's `transaction_type` / `amount_type` / `amount_description` as
   `match_spec` fields.
2. Validate by importing the same month from both sources and comparing bucket
   totals. Any delta indicates a mapping gap.
3. The report service does not need to change — it reads from
   `monthly_pnl_import_month_bucket_totals` regardless of source type.
4. If both sources exist for the same month, a source precedence rule is
   needed. Recommended: Windsor wins for recent months (last 3), CSV wins for
   historical. The precedence should be configurable per profile.

## US P&L row mapping

### Revenue section

1. `product_sales` — SHIPPED
   - CSV: `product sales` column on Order rows
   - Windsor: `ItemPrice / Principal`
2. `shipping_credits` — SHIPPED
   - CSV: `shipping credits` column on Order rows
   - Windsor: `ItemPrice / Shipping`
3. `gift_wrap_credits` — SHIPPED
   - CSV: `gift wrap credits` column on Order rows
   - Windsor: dedicated gift-wrap descriptions if present
4. `promotional_rebate_refunds` — SHIPPED
   - CSV: positive rebate-related adjustment/refund lines
   - Windsor: promotion-related positive reversal descriptions
5. `fba_liquidation_proceeds` — SHIPPED
   - CSV: `product_sales` column on Liquidations rows

### Refund section

1. `refunds` — SHIPPED
   - CSV: negative `product sales` on Refund rows
   - Windsor: `Refund` transaction rows against principal
2. `fba_inventory_credit` — SHIPPED
   - CSV: `Adjustment / FBA Inventory Reimbursement - *` via rule
   - Windsor: `FBA Inventory Reimbursement / *`
3. `shipping_credit_refunds` — SHIPPED
   - CSV: negative `shipping credits` on Refund rows
   - Windsor: refund shipping rows
4. `gift_wrap_credit_refunds` — SHIPPED
   - CSV: negative `gift wrap credits` on Refund rows
   - Windsor: map when observed
5. `promotional_rebates` — SHIPPED
   - CSV: `promotional rebates` column
   - Windsor: `Promotion / Principal|Shipping`
6. `a_to_z_guarantee_claims` — SHIPPED
   - CSV: `A-to-z Guarantee Claim` via rule
   - Windsor: map when observed
7. `chargebacks` — SHIPPED
   - CSV: `Chargeback Refund` via rule
   - Windsor: map when observed

### Expense section

1. `referral_fees` — SHIPPED
   - CSV: `selling fees` column (renamed to `referral_fees` in `COLUMN_BUCKET_MAP`)
   - Windsor: `ItemFees / Commission`
2. `fba_fees` — SHIPPED
   - CSV: `fba fees` column, plus `Fee Adjustment` via rule
   - Windsor: `ItemFees / FBAPerUnitFulfillmentFee`
3. `other_transaction_fees` — SHIPPED
   - CSV: `other transaction fees` column, plus `FBA Transaction fees` via rule
   - Windsor: `SalesTaxServiceFee`, `ShippingChargeback`, `RefundCommission`
4. `fba_monthly_storage_fees` — SHIPPED
   - CSV: `FBA Inventory Fee / FBA storage fee`, `Capacity Reservation Fee` via rules
   - Windsor: `other-transaction / Storage Fee`
5. `fba_long_term_storage_fees` — SHIPPED
   - CSV: `FBA Inventory Fee / FBA Long-Term Storage Fee` via rule
   - Windsor: `other-transaction / StorageRenewalBilling`
6. `fba_removal_order_fees` — SHIPPED
   - CSV: `FBA Removal Order*`, `FBA Disposal Fee` via `starts_with` rules
   - Windsor: `other-transaction / RemovalComplete`, `DisposalComplete`
7. `subscription_fees` — SHIPPED
   - CSV: `Service Fee / Subscription` via rule
   - Windsor: `other-transaction / Subscription Fee`
8. `inbound_placement_and_defect_fees` — SHIPPED
   - CSV: `FBA Inbound Placement Service Fee`, `Inbound Defect Fee`,
     `Unplanned Service Charge` via rules
   - Windsor: `other-transaction / FBA Inbound Placement Service Fee`
9. `inbound_shipping_and_duties` — SHIPPED
   - CSV: `Shipping Services`, `FBA International Freight...` via rules
   - Windsor: map when observed
10. `liquidation_fees` — SHIPPED
    - CSV: `other_transaction_fees` column on Liquidations rows
    - Windsor: map when observed
11. `promotions_fees` — SHIPPED
    - CSV: `Amazon Fees`, `Coupon Redemption Fee`, `Vine Enrollment Fee`,
      `Price Discount`, `Deal` via rules
    - Windsor: `Coupon Participation Fee`, `Coupon Performance Based Fee`
12. `advertising` — SHIPPED
    - CSV: `Service Fee / Cost of Advertising`, `Refund for Advertiser` via rules
    - Windsor: `Cost of Advertising / TransactionTotalAmount`

### Derived rows (shipped)

Computed in the report service, not stored as source facts:

1. `Total Gross Revenue` — sum of revenue buckets
2. `Total Refunds` — sum of refund buckets
3. `Total Net Revenue` — revenue + refunds
4. `Gross Profit` — net revenue minus COGS (or `Contribution Profit` when COGS absent)
5. `Total Expenses` — sum of expense buckets
6. `Net Earnings` — gross profit + expenses

## UI plan

### Reporting home — SHIPPED

Amazon P&L appears as a report card alongside WBR on the client marketplace
page.

### Main route — SHIPPED

`/reports/[clientSlug]/[marketplaceCode]/pnl`

### Main screen — SHIPPED

1. Header with month-range picker (in header actions area)
2. P&L table with all revenue / refund / expense rows
3. Upload / import history in a subtle settings panel
4. Background import polling with visible processing banner
5. Contribution Profit / Contribution Margin framing when COGS absent
6. Header now emphasizes account + marketplace and uses the `Amazon P&L`
   product name in the UI

### Filters — SHIPPED

1. `Last 3 Months` (default)
2. `Last 12 Months`
3. `Last Year` (previous calendar year)
4. `YTD`
5. Explicit month range
6. COGS toggle not yet built (see v2-4)

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

### COGS workflow

1. Derive sold quantity by month + SKU from imported Amazon transaction rows.
2. Let admins enter one current `unit_cost` per sold SKU in settings.
3. Compute monthly COGS as `net units sold * unit_cost`.
4. Show Gross Profit from the available SKU coverage and warn when sold SKUs
   are missing a configured cost.

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

## Recommended build order (v1)

> Phases 1, 2, and 4 are complete. Phase 3 is now implemented in the repo as a
> SKU-based COGS workflow but still needs user verification against real client
> data. Windsor, CA expansion, and the remaining enhancements are tracked in the
> **v2 roadmap** section below.

### Phase 1: Foundation — SHIPPED

1. Add P&L profile/import/ledger/mapping tables
2. Add transaction report upload backend
3. Add normalized ledger expansion
4. Add unmapped QA output

### Phase 2: First usable report — SHIPPED (except Excel export)

1. Add Monthly P&L route
2. Add month filters
3. Render derived rows
4. ~~Add Excel export~~ — moved to v2 roadmap item 7

### Phase 3: COGS — IMPLEMENTED IN REPO, USER VERIFICATION PENDING

Implemented shape:

1. parse and persist sold quantity by import month + SKU from Amazon transaction uploads
2. store one current fixed `unit_cost` per SKU per profile
3. compute monthly COGS from `net units sold * unit_cost`
4. fold COGS into Gross Profit / Net Earnings
5. show missing-COGS warnings with SKU detail
6. expose a settings workflow for entering/editing SKU unit costs

Still pending before calling this validated:

1. user verification of the settings UX on real data
2. user verification that computed COGS totals reconcile to expectation for live client months
3. decision on whether any CSV import/export helper is needed later for bulk SKU cost entry

### Phase 4: Validation — SHIPPED

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

## v2 roadmap

Planned feature sequence after v1 shipped state.

Recommended ordering principle:

1. ship low-risk report improvements first
2. complete the core finance model before internal add-ons
3. validate Windsor as the second ingestion path before polishing exports
4. defer comparison/reporting layers until the underlying data model is richer
   and stable

### v2-0: Totals column toggle — LOW difficulty

Add an optional "Total" column after the last month column that sums each row
across all visible months. Toggled on/off from the report header, similar to
how toggles work in the WBR. Default off so the table stays compact.

Frontend-only. No backend changes, no new queries — the data is already in the
response. Just sum each row's month values client-side when the toggle is on.

### v2-1: Percent-of-revenue view — LOW difficulty

Frontend-only display mode. Each expense and refund line shows
`[amount] / [Total Net Revenue]` as a percentage for that month. Revenue rows
and totals stay as dollar amounts. Gross Profit row shows margin %.

UI: add report tabs similar to WBR section tabs. Suggested tab names:
`Dollars` and `% of Revenue` (or `$` and `%`). Same report, different lens.

No backend changes, no new tables, no new queries.

### v2-2: COGS entry workflow — MEDIUM difficulty

Current status: implemented in the repo and pushed to `main`, but still pending
manual product/user verification before it should be called fully validated.

The implemented v2 COGS model is:

1. one current fixed `unit_cost` per SKU
2. sold quantity derived from Monthly P&L transaction imports
3. monthly COGS computed as `net units sold * unit_cost`

Recommended data model:

1. `monthly_pnl_import_month_sku_units`
   - derived at import time from raw transaction rows
   - versioned by `import_month_id`
   - stores net sold/refunded units per month + SKU
2. `monthly_pnl_sku_cogs`
   - one current unit cost per profile + SKU
   - no effective-date accounting in v2

Implementation shape:

1. Settings screen: list sold SKUs for the visible report range, with one unit
   cost input per SKU.
2. The SKU list is derived from active imported transaction data, not manually
   maintained.
3. Partial COGS is fine. If a client has provided COGS for 10 of 15 sold SKUs,
   the report should still show Gross Profit using the available data and flag
   which SKUs are missing.
4. No effective-month pricing, FIFO, or LIFO in v2. Cost changes simply update
   the current SKU unit cost going forward until the product needs deeper
   accounting behavior.

What is done:

1. importer parses `quantity` and stores derived month+SKU unit summaries
2. report computes monthly COGS from those summaries plus `monthly_pnl_sku_cogs`
3. settings UI loads sold SKUs for the visible range and saves unit costs
4. warning banner calls out sold SKUs missing configured COGS

What still needs verification:

1. confirm the settings UX feels workable with a real client SKU list
2. confirm reported COGS/Gross Profit values against live expected numbers
3. decide whether bulk SKU cost entry needs a CSV helper in a later pass

### v2-3: Windsor settlement backfill — MEDIUM difficulty

Reuse existing Windsor OAuth and sync infrastructure from WBR. The settlement
feed is a different API shape from the business/ads feeds — not a copy-paste.

1. Settings panel: connect Windsor settlement as a source for this P&L profile.
2. Backfill trigger: pull last 3 months of settlement data.
3. Normalizer: map Windsor `transaction_type` / `amount_type` /
   `amount_description` into existing ledger buckets (mappings already spec'd
   in "Source B" section above).
4. Month activation using existing `monthly_pnl_import_months` pattern.
5. Validate Windsor-sourced months against uploaded CSV months before trusting.
6. Source precedence rule needed: when both Windsor and CSV data exist for the
   same month, which wins? Recommend Windsor for recent months, CSV for
   historical.

### v2-4: Windsor weekly auto-refresh — LOW-MEDIUM difficulty

Depends on v2-3 being validated.

1. Add `windsor_settlement` source type to worker-sync loop.
2. Per-profile toggle in settings: "Auto-refresh from Windsor" on/off.
3. Weekly job pulls latest settlement window and upserts into ledger.
4. Follow WBR nightly refresh pattern for job orchestration.

### v2-5: Agency Fees — LOW difficulty

Optional per-month agency management fee entry.

1. New table `monthly_pnl_agency_fees` (profile_id, entry_month, amount,
   notes, timestamps). One row per profile per month.
2. Settings toggle: "Show Agency Fees" on/off per profile.
3. Entry UI in settings area: list of active months with an amount input next
   to each. Pre-populate month list from active import months.
4. Report integration: when toggled on, add "Agency Fees" as the last expense
   line item. Flows into Total Expenses and Net Earnings automatically.

### v2-6: Disbursements tab — LOW-MEDIUM difficulty

The importer already maps Transfer / payout rows to the `non_pnl_transfer`
ledger bucket. This data is saved but excluded from the P&L totals (correctly).

1. Add a third report tab (after `$` and `%`): `Disbursements`.
2. Query `monthly_pnl_ledger_entries` where
   `ledger_bucket = 'non_pnl_transfer'`, grouped by month.
3. Show monthly disbursement totals, optionally broken out by settlement ID if
   captured in raw data.
4. No new tables needed. Lightweight backend endpoint or filter on existing
   report query.

Important gate:

1. verify that `non_pnl_transfer` rows capture what the manual process shows
   for disbursements before shipping
2. do not treat this as a pure UI task until that reconciliation is proven

### v2-7: Export to XLSX — LOW-MEDIUM difficulty

Follow the WBR Excel export pattern. By this point the report includes all
core views and major optional rows, so the export captures the complete
picture without forcing early churn in workbook structure.

1. Multi-sheet workbook: one sheet per report tab (Dollars, % of Revenue,
   Disbursements).
2. Include COGS and Agency Fees rows when enabled.
3. Match the on-screen formatting (bold totals, section grouping, month
   columns).

### v2-8: Annual / year-over-year comparison — MEDIUM-HIGH difficulty

Requires 12+ months of clean data to be useful. Design TBD.

Initial suggestion: start with a YoY comparison table, not charts.

1. Columns: metric name, current year YTD, prior year same period, delta (%).
2. Metrics: Net Revenue, Total Refunds, Gross Profit, Total Expenses, Net
   Earnings, plus top expense lines.
3. Handle months with no prior-year data gracefully (show N/A, not zero).
4. Charts can follow once the useful metrics are identified from table usage.
5. Comparison basis options: same months last year, trailing 12 vs prior 12,
   or quarter-over-quarter.

## Recommended build order (v2)

Recommended execution order from here:

1. `v2-0` Totals column toggle
2. `v2-1` Percent-of-revenue view
3. `v2-2` COGS entry workflow
4. `v2-3` Windsor settlement backfill
5. `v2-4` Windsor weekly auto-refresh
6. `v2-5` Agency Fees
7. `v2-6` Disbursements tab
8. `v2-7` Export to XLSX
9. `v2-8` Annual / year-over-year comparison

Why this order:

1. start with two low-risk display wins that improve usability immediately
2. complete the core profitability model before layering on internal agency
   economics
3. validate Windsor as the second ingestion path before spending time on export
   polish
4. defer disbursements until the `non_pnl_transfer` mapping is reconciled
5. leave YoY analysis last because it depends on a richer, stable dataset and a
   settled report surface

## Recommendation

Build the P&L system as a normalized finance-ledger tool, not a one-off report.

That gives us:

1. reliable backfill now
2. validation against existing manual reports
3. Windsor automation later without redesign
4. room for CA and other countries after the US mapping is stable
