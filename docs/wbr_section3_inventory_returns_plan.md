# WBR Section 3 Inventory + Returns Plan

_Drafted: 2026-03-14 (ET)_

This document defines the intended WBR v2 Section 3 implementation for
inventory and returns. The goal is to match the partner's existing manual WBR
format as closely as possible for v1, even where the display buckets are more
business-friendly than Amazon-canonical.

## Goal

Ship the last WBR section using Windsor-backed SP/FBA data so the generated WBR
matches the current manual spreadsheet layout closely enough that the manual
process can be retired.

For v1:

1. optimize for parity with the partner's current WBR
2. keep the existing WBR row tree and ASIN mapping model
3. keep Windsor setup and nightly sync ergonomics unchanged for operators
4. avoid inventing a new taxonomic model for inventory states

## User-facing section contract

Section 3 should render the following per WBR row:

1. `Instock`
2. `Working`
3. `Reserved + FC Transfer`
4. `Receiving + Intransit`
5. `Weeks of Stock`
6. Returns for the prior 2 completed weeks
7. `Return %`

Parent rows should remain sums of child rows only, consistent with Sections 1
and 2.

## Source queries

Section 3 requires three Windsor-backed feeds.

### 1. AFN inventory feed

Purpose:

- provide Amazon inventory state quantities such as reserved and inbound state

Current known useful fields:

- `fba_myi_unsuppressed_inventory_data__asin`
- `fba_myi_unsuppressed_inventory_data__sku`
- `fba_myi_unsuppressed_inventory_data__afn_fulfillable_quantity`
- `fba_myi_unsuppressed_inventory_data__afn_inbound_working_quantity`
- `fba_myi_unsuppressed_inventory_data__afn_inbound_shipped_quantity`
- `fba_myi_unsuppressed_inventory_data__afn_inbound_receiving_quantity`
- `fba_myi_unsuppressed_inventory_data__afn_reserved_quantity`
- `fba_myi_unsuppressed_inventory_data__afn_reserved_future_supply`
- `fba_myi_unsuppressed_inventory_data__product_name`

### 2. Restock recommendations feed

Purpose:

- provide the partner-facing buckets for available, working, FC transfer,
  receiving, shipped/intransit

Current known useful fields:

- `restock_inventory_recommendations_report__asin`
- `restock_inventory_recommendations_report__merchant_sku`
- `restock_inventory_recommendations_report__available`
- `restock_inventory_recommendations_report__working`
- `restock_inventory_recommendations_report__fc_transfer`
- `restock_inventory_recommendations_report__fc_processing`
- `restock_inventory_recommendations_report__receiving`
- `restock_inventory_recommendations_report__shipped`
- `restock_inventory_recommendations_report__inbound`
- `restock_inventory_recommendations_report__units_sold_last_30_days`
- `restock_inventory_recommendations_report__product_name`
- `restock_inventory_recommendations_report__condition`
- `restock_inventory_recommendations_report__fulfilled_by`

### 3. Returns feed

Purpose:

- provide return-event data for the prior 2 completed weeks

Current known useful fields:

- `fba_fulfillment_customer_returns_data__asin`
- `fba_fulfillment_customer_returns_data__sku`
- `fba_fulfillment_customer_returns_data__quantity`
- `fba_fulfillment_customer_returns_data__return_date`
- `fba_fulfillment_customer_returns_data__product_name`

## Mapping key

The current WBR implementation is most reliable on child ASIN, not SKU.

Why:

1. Section 1 business facts are stored and aggregated by `child_asin`
2. row mapping is already modeled through `wbr_asin_row_map.child_asin`
3. listing imports and active catalog state are already deduped by child ASIN
4. Section 1 report rollups already join facts to rows through child ASIN

Therefore:

1. use `child_asin` / `asin` as the canonical Section 3 mapping key
2. keep SKU/FNSKU as QA/debug aids only
3. if multiple source rows exist for the same ASIN, aggregate them into one
   ASIN-level Section 3 fact before row rollup

## V1 display buckets

The v1 display should follow the partner's manual WBR, not Amazon's canonical
state naming.

### Inventory columns

#### `Instock`

Use:

- `restock_inventory_recommendations_report__available`

#### `Working`

Use:

- `restock_inventory_recommendations_report__working`

#### `Reserved + FC Transfer`

Use:

- `fba_myi_unsuppressed_inventory_data__afn_reserved_quantity`
- `restock_inventory_recommendations_report__fc_transfer`
- `restock_inventory_recommendations_report__fc_processing`

Formula:

- `reserved_plus_fc_transfer = reserved_quantity + fc_transfer + fc_processing`

#### `Receiving + Intransit`

Use:

- `restock_inventory_recommendations_report__receiving`
- `restock_inventory_recommendations_report__shipped`

Formula:

- `receiving_plus_intransit = receiving + shipped`

## Weeks of Stock formula

V1 should follow the partner's formula exactly.

Formula:

- `Weeks of Stock = (Instock + Reserved + FC Transfer + Receiving + Intransit) / average weekly unit sales over the last 4 completed weeks`

Expanded:

- numerator = `instock + reserved_plus_fc_transfer + receiving_plus_intransit`
- denominator = average weekly `unit_sales` from Section 1 over the last 4
  completed weeks

Rules:

1. exclude `Working` from the WOS numerator
2. use completed weeks only, not the current in-progress week
3. if the denominator is `0`, return `null` / blank instead of divide-by-zero
4. preserve decimal precision in computation and round only for display

## Returns formula

Returns should intentionally use a different time window than the standard
4-week WBR sections.

Display:

1. completed week `-1`
2. completed week `-2`
3. `Return %`

Formula:

- `Return % = average returns over the last 2 completed weeks / average unit sales over the last 2 completed weeks`

Rules:

1. returns are summed from return-event quantity by completed week
2. denominator uses Section 1 unit sales over the same 2 completed weeks
3. if 2-week average unit sales is `0`, return `null` / blank
4. percentages over `100%` are allowed when low-volume SKUs have delayed returns

## Data model recommendation

Do not overload `wbr_business_asin_daily` with inventory or returns fields.

Use separate tables with separate grains.

### 1. `wbr_inventory_asin_snapshots`

Recommended grain:

- one row per `profile_id + snapshot_date + child_asin`

Suggested columns:

- `id uuid primary key default gen_random_uuid()`
- `profile_id uuid not null references public.wbr_profiles(id) on delete cascade`
- `sync_run_id uuid references public.wbr_sync_runs(id) on delete set null`
- `snapshot_date date not null`
- `child_asin text not null`
- `instock integer not null default 0`
- `working integer not null default 0`
- `reserved_quantity integer not null default 0`
- `fc_transfer integer not null default 0`
- `fc_processing integer not null default 0`
- `reserved_plus_fc_transfer integer not null default 0`
- `receiving integer not null default 0`
- `intransit integer not null default 0`
- `receiving_plus_intransit integer not null default 0`
- `source_row_count integer not null default 0`
- `source_payload jsonb not null default '{}'::jsonb`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Suggested uniqueness:

- `(profile_id, snapshot_date, child_asin)`

### 2. `wbr_returns_asin_daily`

Recommended grain:

- one row per `profile_id + return_date + child_asin`

Suggested columns:

- `id uuid primary key default gen_random_uuid()`
- `profile_id uuid not null references public.wbr_profiles(id) on delete cascade`
- `sync_run_id uuid references public.wbr_sync_runs(id) on delete set null`
- `return_date date not null`
- `child_asin text not null`
- `return_units integer not null default 0`
- `source_row_count integer not null default 0`
- `source_payload jsonb not null default '{}'::jsonb`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Suggested uniqueness:

- `(profile_id, return_date, child_asin)`

## Sync architecture recommendation

Do not create a new operator-facing setup or schedule system for Section 3.

Reuse:

1. the existing `windsor_account_id`
2. the existing SP-API/Windsor sync surfaces
3. the existing nightly Windsor toggle
4. the existing `worker-sync` schedule

But internally, keep Section 3 ingestion separate from Section 1 ingestion.

Recommended shape:

1. existing Windsor daily refresh/backfill remains the umbrella action
2. Section 1 business facts stay in `WindsorBusinessSyncService`
3. add dedicated Section 3 sync helpers/services for:
   - inventory snapshot refresh
   - returns refresh
4. call those Section 3 sync steps from the Windsor daily/manual refresh flow

This gives one Windsor integration and one nightly toggle, but multiple
internally clean fact pipelines.

## Sync behavior details

### Inventory refresh

Inventory is snapshot-like, not historical daily business data.

Recommendation:

1. refresh inventory during manual Windsor refresh and nightly Windsor refresh
2. store only the latest snapshot date per refresh
3. replace the snapshot for that `profile_id + snapshot_date`
4. no separate historical backfill UI is needed for inventory in v1

### Returns refresh

Recommendation:

1. refresh returns during manual Windsor refresh and nightly Windsor refresh
2. fetch a rolling window wide enough to cover the last 2 completed weeks with
   margin, for example 21 to 28 days
3. replace that rolling window in `wbr_returns_asin_daily`

## Aggregation rules

### General

1. normalize ASINs to uppercase
2. treat ASIN as the canonical identity
3. preserve raw rows in `source_payload` for QA/debug

### Inventory duplicate handling

The sample restock export already shows multiple rows for the same ASIN.

V1 recommendation:

1. filter to `condition = 'New'`
2. for restock rows, prefer `fulfilled_by = 'Amazon'` when present
3. aggregate quantitative fields by ASIN after filtering
4. preserve `source_row_count`
5. add QA/debug counters for duplicate source rows per ASIN

This should be validated against the partner's manual sheet during
implementation. If a simple sum overcounts on real data, adjust the duplicate
resolution rule before broad rollout.

### Returns aggregation

1. sum `quantity` by `return_date + child_asin`
2. convert timestamps to local report dates before bucketing if needed
3. keep raw return events available in `source_payload`

## Report-building recommendation

Add a dedicated backend report builder for Section 3, parallel to
`section1_report.py` and `section2_report.py`.

Recommended output shape:

1. same ordered row tree as Sections 1 and 2
2. same completed-week bucket logic used by the profile's `week_start_day`
3. per-row payload including:
   - `instock`
   - `working`
   - `reserved_plus_fc_transfer`
   - `receiving_plus_intransit`
   - `weeks_of_stock`
   - `returns_week_1`
   - `returns_week_2`
   - `return_rate`
4. parent rows are sums of child rows only

## Suggested implementation files

### Backend

1. new migration for Section 3 tables
2. `backend-core/app/services/wbr/windsor_inventory_sync.py`
3. `backend-core/app/services/wbr/windsor_returns_sync.py`
4. `backend-core/app/services/wbr/section3_report.py`
5. targeted updates in:
   - `backend-core/app/services/wbr/windsor_business_sync.py`
   - `backend-core/app/services/wbr/nightly_sync.py`
   - `backend-core/app/routers/wbr.py`

### Frontend

1. add Section 3 table component(s) under `frontend-web/src/app/reports/_components/`
2. add report hook if needed under `frontend-web/src/app/reports/_lib/`
3. wire the main WBR route to render Section 3 after Sections 1 and 2

## Acceptance criteria for v1

1. Section 3 numbers match the partner's manual WBR for the validation account
2. row rollups still follow the current ASIN-to-row mapping model
3. Windsor manual refresh refreshes Section 3 data
4. Windsor nightly refresh refreshes Section 3 data
5. no extra setup screen or extra nightly toggle is introduced
6. WOS uses the agreed numerator and the last 4 completed weeks of unit sales
7. Return % uses the last 2 completed weeks only

## Open questions to resolve during implementation

1. exact duplicate-row behavior for restock inventory rows by ASIN
2. whether returns timestamps need timezone conversion before date bucketing in
   the Windsor payload as returned in production
3. whether inventory snapshot date should be derived from source payload date or
   simply the local refresh date when Windsor does not expose an explicit report
   date
