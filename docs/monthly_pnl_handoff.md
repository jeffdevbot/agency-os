# Monthly P&L Handoff

_Last updated: 2026-03-16 (ET)_

This is the current restart point for Monthly P&L after the December/November
validation work, the `/reports` UX separation cleanup, and the first backfill
push into earlier 2025 months.

## Current reality

1. December 2025 validation is complete on the validation profile and should
   not be casually replaced.
2. Validation/backfill profile:
   - `c8e854cf-b989-4e3f-8cf4-58a43507c67a`
3. Active validated December import:
   - import `c84cade9-6633-427f-b4b0-2371d0aca344`
   - source filename `dec2025data-olderfile.csv`
   - created `2026-03-16 15:34:59+00`
   - finished `2026-03-16 15:35:41+00`
4. November 2025 now imports successfully after the duplicate-ledger fix, and
   the user validated November to the penny.
5. The `/reports` frontend now treats WBR and Monthly P&L as separate sibling
   reporting surfaces. Monthly P&L defaults to the last `3` completed months,
   uses a header month-range picker, and hides upload/provenance in a subtle
   settings panel.
6. When no COGS exists in the visible months, the UI now uses
   `Contribution Profit` and `Contribution Margin (%)` instead of showing the
   old missing-COGS warning.
7. Supabase has been upgraded from Free to Pro, but Monthly P&L is still slow
   enough that query-shape and request-lifecycle problems remain more important
   than pricing-tier assumptions.
8. On 2026-03-16, the real wide-range report bottleneck was identified live:
   a later migration had overwritten the faster `active_months` RPC with an
   older `EXISTS` version, so the report path still scanned the raw ledger.
9. On 2026-03-16, live migration
   `20260316213000_add_monthly_pnl_import_month_bucket_totals.sql` was applied.
   It backfilled `monthly_pnl_import_month_bucket_totals` and rewired
   `pnl_report_bucket_totals(...)` to read those precomputed month totals.
10. On the validation profile, the exact wide range
    `2025-01-01` through `2026-02-01` now executes at about `4.5 ms` at the
    function boundary instead of roughly `7.3 s`.
11. On 2026-03-16, live migration
    `20260316224500_claim_monthly_pnl_pending_imports.sql` was applied. It
    adds `pnl_claim_pending_imports(...)`, which atomically claims queued async
    imports with `FOR UPDATE SKIP LOCKED` and flips them from `pending` to
    `running` in one query.
12. The backend report service now runs its independent totals/warnings reads
    concurrently and no longer falls back to paginated raw-ledger aggregation.
    If both the summary table and RPC fail, the report now errors fast instead
    of silently degrading into a long scan.
13. The frontend upload flow now keeps queued imports in a visible
    "processing in background" state and polls import status every `5` seconds
    until the import leaves `pending` / `running`, then refreshes the report.
14. On 2026-03-16, live migration
    `20260316232000_cleanup_validation_profile_stranded_monthly_pnl_state.sql`
    deactivated the orphaned Jan/Apr/May 2025 active slices on the validation
    profile and marked the stranded retry import
    `0fe50885-fce4-48ec-afa6-a9dce5cef716` as `error`.
15. On 2026-03-16, inspection of the real `nov-2025.csv` export confirmed the
    Amazon transaction file includes a native `quantity` column and real
    multi-unit rows. Refund rows also include quantity.
16. The earlier month-total COGS entry experiment is not the right workflow
    for this product and should not be continued. The correct v2 direction is:
    fixed unit cost per SKU, with Monthly P&L COGS calculated from sold units
    in the transaction feed.
17. Repo migration
    `20260317001000_add_monthly_pnl_sku_cogs_and_unit_summaries.sql` now exists
    to create:
    - `monthly_pnl_import_month_sku_units`
    - `monthly_pnl_sku_cogs`
    It also backfills sold-unit summaries from existing raw transaction rows.
18. Current code now parses `quantity` during transaction import, writes
    per-import-month SKU unit summaries, exposes SKU-level COGS settings
    endpoints/UI, and computes report COGS as `net units sold * fixed SKU
    unit cost`.
19. This SKU-level COGS path is not live until the new migration is applied and
    the updated backend/frontend are deployed.

## Validated and active state

### Validated months that should be preserved

1. `2025-11-01`
   - active import `0626222a-dc9c-4be5-a2ba-9de27b093494`
   - source `nov-2025.csv`
   - import status `success`
2. `2025-12-01`
   - active import `c84cade9-6633-427f-b4b0-2371d0aca344`
   - source `dec2025data-olderfile.csv`
   - import status `success`

### Important note about the active December data

The currently active older-file December import was uploaded before the final
edge-case importer changes were fully deployed. To avoid forcing another manual
upload, the live active import was corrected in place on 2026-03-16 for two
residual items:

1. `FBA Removal Order: Disposal Fee` moved from `unmapped` to
   `fba_removal_order_fees`
2. one `Refund / other = 3.60` was folded into the existing `refunds` ledger row

That means:

1. the active December data is correct now
2. it should still be preserved unless the user explicitly wants a replacement

### Current active month coverage on the validation/backfill profile

As of the latest live check after the cleanup migration, the active month
slices are:

1. `2025-07-01`
   - active import `5aa0f621-e9d7-4129-9f11-5b6597910eaa`
   - import status `success`
2. `2025-08-01`
   - active import `73eb37c5-6001-4699-82a1-e8de8f8cd861`
   - import status `success`
3. `2025-09-01`
   - active import `276cde82-45ca-48a4-a8f0-f15e8b54e3e2`
   - import status `success`
4. `2025-10-01`
   - active import `16468c3d-8a56-4eb2-8124-5e1b53a9168b`
   - import status `success`
5. `2025-11-01`
   - active import `0626222a-dc9c-4be5-a2ba-9de27b093494`
   - import status `success`
6. `2025-12-01`
   - active import `c84cade9-6633-427f-b4b0-2371d0aca344`
   - import status `success`

### Current inactive / partial months

1. `2025-02-01`
   - import `65d24015-7602-49f2-8c7f-2b9f29bab56a`
   - import month status `error`
   - not active
2. `2025-01-01`
   - import `65d24015-7602-49f2-8c7f-2b9f29bab56a`
   - import month status still `success`, but explicitly deactivated on
     `2026-03-16` because it came from a failed multi-month import
   - not active
3. `2025-03-01`
   - no imported month slice yet
4. `2025-04-01`
   - import `0fe50885-fce4-48ec-afa6-a9dce5cef716`
   - import month status still `success`, but explicitly deactivated on
     `2026-03-16` because the retry import was stranded
   - not active
5. `2025-05-01`
   - older import `37b0af74-0e7f-411a-b6aa-1c82b5cd827a`
   - import month status still `success`, but explicitly deactivated on
     `2026-03-16` because the parent import is `error`
   - newer retry import `0fe50885-fce4-48ec-afa6-a9dce5cef716`
   - retry month status changed from `pending` to `error` on `2026-03-16`
   - not active
6. `2025-06-01`
   - import `37b0af74-0e7f-411a-b6aa-1c82b5cd827a`
   - import month status `error`
   - not active
7. `2026-01-01`
   - older stale carryover slice exists on a historical December import
   - not active
8. `2026-02-01`
   - no imported month slice yet

## 2026-03-16 validation-profile cleanup

These live state changes were applied intentionally and should be preserved:

1. Deactivated `2025-01-01` active slice from failed import
   `65d24015-7602-49f2-8c7f-2b9f29bab56a`
2. Deactivated `2025-04-01` active slice from stranded retry import
   `0fe50885-fce4-48ec-afa6-a9dce5cef716`
3. Deactivated `2025-05-01` active slice from failed import
   `37b0af74-0e7f-411a-b6aa-1c82b5cd827a`
4. Changed retry May slice on import `0fe50885-fce4-48ec-afa6-a9dce5cef716`
   from `pending` to `error`
5. Changed import `0fe50885-fce4-48ec-afa6-a9dce5cef716` from `running` to
   `error`
6. Confirmed validated November import `0626222a-dc9c-4be5-a2ba-9de27b093494`
   remains active
7. Confirmed validated December import `c84cade9-6633-427f-b4b0-2371d0aca344`
   remains active

## What was confirmed

### 1. The report page does not re-parse uploaded CSVs

Uploads parse once during `POST /transaction-upload` and persist:

1. raw rows into `monthly_pnl_raw_rows`
2. normalized facts into `monthly_pnl_ledger_entries`
3. month activation in `monthly_pnl_import_months`

The report path reads persisted ledger/import tables only.

### 2. The December workbook reconciliation issue was mostly source drift

The newer download `/Users/jeff/Downloads/2025DecMonthlyUnifiedTransaction.csv`
and the older download used by the manual workbook do not represent the same
December settlement coverage.

Important consequence:

1. The newer file can be internally correct but still disagree with the manual
   workbook because Amazon shifted settlement-period inclusion between download
   dates.
2. Importing the older source file immediately moved the system totals onto the
   manual workbook numbers.

### 3. November exposed a real importer bug that is now fixed

Some Amazon rows can populate more than one source amount column that maps into
the same report bucket on the same raw row.

Old behavior:

1. emitted multiple ledger rows with the same
   `(import_id, source_row_index, ledger_bucket)`
2. hit the unique constraint and surfaced a generic frontend import failure

Fixed behavior:

1. coalesce same-bucket ledger rows per raw source row before insert
2. preserve the correct summed amount while avoiding duplicate-key failures

### 4. The main remaining import problem is request lifecycle, not CSV parsing

Single-month uploads are working. Multi-month uploads are not reliable yet
because the current transaction import runs synchronously inside one long HTTP
request.

Observed live behavior:

1. `jan-mar2025-whoosh-us.csv` created import
   `65d24015-7602-49f2-8c7f-2b9f29bab56a`, activated January, then stranded
   February and never reached March before the request died
2. `apr-june2025-whoosh-us.csv` created import
   `37b0af74-0e7f-411a-b6aa-1c82b5cd827a`, activated April and May, errored on
   June, and was later marked `error`
3. a retry of that same file created import
   `0fe50885-fce4-48ec-afa6-a9dce5cef716`, activated April again, left a new
   May slice as `pending`, and is still showing `running`
4. the frontend surfaced `Failed to fetch` during these longer uploads

Inference:

1. this is a crash-safety / timeout problem in the synchronous import flow
2. the correct product fix is an async/background import path with status
   polling, not continued reliance on long blocking requests

### 5. The real report bottleneck was repeated aggregation from raw ledger rows

The wide-range failure was not caused by the mixed early-2025 active/error
month state alone.

What was found live:

1. the current validation profile has about `1.5M` ledger rows across active
   and historical imports
2. the live `pnl_report_bucket_totals(...)` function had been overwritten by
   the later `optimize_monthly_pnl_report_rpc_exists` migration
3. that version still planned as a near-full ledger scan and took about
   `7.3 s` for `2025-01-01` through `2026-02-01`
4. the durable fix was to materialize per-import-month bucket totals once and
   read those on the report path instead of regrouping raw ledger facts on
   every request

Live state after the fix:

1. `monthly_pnl_import_month_bucket_totals` now has `437` backfilled rows for
   the validation profile
2. `pnl_report_bucket_totals(...)` now reads that table and the same wide range
   executes in about `4.5 ms`
3. this preserves the validated November/December active imports because it is
   a derived-summary change only

## Current open blockers

### 1. The original wide-range failure root cause has been fixed at the DB layer

The earlier failure for
`filter_mode=range&start_month=2025-01-01&end_month=2026-02-01` is now
understood.

1. the bad path was an outdated RPC definition, not just "Supabase tier"
2. the live DB now uses precomputed import-month bucket totals instead
3. current deployed backend code should benefit immediately because it already
   calls `pnl_report_bucket_totals(...)`
4. one remaining follow-up is to verify the full HTTP route in production after
   this migration rather than only at the SQL function boundary

### 2. Monthly P&L page load still needs backend deploy + real UX verification

The main DB bottleneck is now addressed, but the end-to-end page still needs to
be rechecked after the backend/frontend deploy that uses the queued import flow
and summary-table-first report code.

Remaining likely contributors:

1. currently deployed backend still contains the old heavy ledger fallback path
   if the RPC ever errors
2. the route still resolves client/profile before report fetch on first paint
3. the live page has not yet been manually timed again after the new DB summary
   table landed

### 3. Multi-month upload support is not productized yet

The user wants to backfill multiple months at a time. Right now that is not
trustworthy enough to recommend.

Code now prepared locally:

1. upload endpoint now stages the source file to Supabase Storage and queues the
   import instead of trying to finish inside one request
2. new worker code processes queued async imports through `worker-sync`
3. import processing now writes `monthly_pnl_import_month_bucket_totals` during
   execution so future reports stay fast

Still required:

1. deploy `backend-core` and `worker-sync`
2. verify the full authenticated `/admin/pnl/.../report` route in production
   after deploy rather than only SQL-level timings
3. manually exercise the queued-upload UI in production and confirm the
   polling banner transitions cleanly through `pending` / `running` / terminal
   states
4. resume backfilling missing early-2025 months with the async worker flow
   instead of the old synchronous request path

## December 2025 final numbers

These remain the current validated December totals on the active older-file
import:

1. `total_gross_revenue = 339,770.20`
2. `total_refunds = -11,314.14`
3. `total_net_revenue = 328,456.06`
4. `total_expenses = -173,735.13`

These match the manual workbook target values to rounding/penny level.

## Live migrations now applied

These Monthly P&L migrations are live in Supabase:

1. `20260315200000_monthly_pnl_phase1_foundation.sql`
2. `20260316173000_allow_monthly_pnl_reimport_same_sha.sql`
3. `20260316190000_add_monthly_pnl_vine_fee_mapping.sql`
4. `20260316191000_add_monthly_pnl_report_bucket_totals_rpc.sql`
5. `20260316194500_optimize_monthly_pnl_report_rpc_active_months.sql`
6. `20260316195500_fix_monthly_pnl_removal_and_refund_other_mapping.sql`
7. `20260316203000_add_monthly_pnl_manual_model_rules.sql`
8. `20260316173000_optimize_monthly_pnl_report_rpc_exists.sql`
9. `20260316213000_add_monthly_pnl_import_month_bucket_totals.sql`
10. `20260316224500_claim_monthly_pnl_pending_imports.sql`
11. `20260316232000_cleanup_validation_profile_stranded_monthly_pnl_state.sql`

## Relevant commits now on `main`

1. `fcd0f9e` - align Monthly P&L with manual workbook mappings
2. `676851d` - optimize Monthly P&L report RPC for active months
3. `586c5a9` - map remaining Monthly P&L workbook edge cases
4. `a4559cc` - clarify report surfaces and split P&L screen
5. `3fecb54` - refine Monthly P&L report UX
6. `6e5e55a` - coalesce duplicate P&L ledger buckets
7. `76499f6` - harden Monthly P&L import retries
8. `8bf2a7f` - pulse Monthly P&L upload button
9. `e42f8c1` - speed up Monthly P&L report RPC
10. `1bb81c5` - harden Monthly P&L page transient errors

## Important constraints

1. Do not replace the active December import on the validation profile unless
   the user explicitly wants to change the validated source basis.
2. Do not redo December 2025 from scratch unless explicitly asked.
3. Preserve the successful November and December validation state.
4. Treat WBR as a separate shipped reporting product. Monthly P&L is its own
   `/reports/.../pnl` surface, not WBR follow-on scope.
5. Leave unrelated dirty files alone:
   - `docs/db/schema_master.md`
   - `scripts/db/generate-schema-master.sh`
   - `supabase/.temp/*`

## Recommended next-session plan

1. Deploy `backend-core` and `worker-sync` so the atomic worker-claim path and
   fast-fail/concurrent report code are live
2. Verify the authenticated production report route for
   `start_month=2025-01-01&end_month=2026-02-01` after deploy
3. Run a real queued multi-month upload in production and watch the new polling
   UX through completion
4. Backfill the missing early-2025 months using the async worker path
5. Measure first-paint/page-load again after deploy and decide whether any
   remaining latency is frontend orchestration rather than database time

## Where the code lives

1. [transaction_import.py](/Users/jeff/code/agency-os/backend-core/app/services/pnl/transaction_import.py)
2. [report.py](/Users/jeff/code/agency-os/backend-core/app/services/pnl/report.py)
3. [profiles.py](/Users/jeff/code/agency-os/backend-core/app/services/pnl/profiles.py)
4. [pnl.py](/Users/jeff/code/agency-os/backend-core/app/routers/pnl.py)
5. [test_pnl_transaction_import.py](/Users/jeff/code/agency-os/backend-core/tests/test_pnl_transaction_import.py)
6. [test_pnl_report.py](/Users/jeff/code/agency-os/backend-core/tests/test_pnl_report.py)
