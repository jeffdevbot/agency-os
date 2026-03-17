# Monthly P&L Handoff

_Last updated: 2026-03-17 (ET)_

This is the current restart point for Monthly P&L after the US v1 validation
push, the Jan-Dec 2025 Whoosh US backfill, the SKU-based COGS rollout, and the
latest WBR hardening work.

## Current reality

1. Whoosh US Amazon P&L is now validated across all of `2025-01-01` through
   `2025-12-01` on the validation/backfill profile.
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
7. On 2026-03-16, the real wide-range report bottleneck was identified live:
   a later migration had overwritten the faster `active_months` RPC with an
   older `EXISTS` version, so the report path still scanned the raw ledger.
8. On 2026-03-16, live migration
   `20260316213000_add_monthly_pnl_import_month_bucket_totals.sql` was applied.
   It backfilled `monthly_pnl_import_month_bucket_totals` and rewired
   `pnl_report_bucket_totals(...)` to read those precomputed month totals.
9. On the validation profile, the exact wide range
    `2025-01-01` through `2026-02-01` now executes at about `4.5 ms` at the
    function boundary instead of roughly `7.3 s`.
10. On 2026-03-16, live migration
    `20260316224500_claim_monthly_pnl_pending_imports.sql` was applied. It
    adds `pnl_claim_pending_imports(...)`, which atomically claims queued async
    imports with `FOR UPDATE SKIP LOCKED` and flips them from `pending` to
    `running` in one query.
11. The backend report service now runs its independent totals/warnings reads
    concurrently and no longer falls back to paginated raw-ledger aggregation.
    If both the summary table and RPC fail, the report now errors fast instead
    of silently degrading into a long scan.
12. The frontend upload flow now keeps queued imports in a visible
    "processing in background" state and polls import status every `5` seconds
    until the import leaves `pending` / `running`, then refreshes the report.
13. On 2026-03-16, live migration
    `20260316232000_cleanup_validation_profile_stranded_monthly_pnl_state.sql`
    deactivated the orphaned Jan/Apr/May 2025 active slices on the validation
    profile and marked the stranded retry import
    `0fe50885-fce4-48ec-afa6-a9dce5cef716` as `error`.
14. On 2026-03-16, inspection of the real `nov-2025.csv` export confirmed the
    Amazon transaction file includes a native `quantity` column and real
    multi-unit rows. Refund rows also include quantity.
15. The earlier month-total COGS entry experiment is not the right workflow
    for this product and should not be continued. The correct v2 direction is:
    fixed unit cost per SKU, with Monthly P&L COGS calculated from sold units
    in the transaction feed.
16. Current code now parses `quantity` during transaction import, writes
    per-import-month SKU unit summaries, exposes SKU-level COGS settings
    endpoints/UI, and computes report COGS as `net units sold * fixed SKU
    unit cost`.
17. On 2026-03-17, migration
    `20260317001000_add_monthly_pnl_sku_cogs_and_unit_summaries.sql` was
    applied live, and the SKU-based COGS path is now deployed.
18. The user manually entered several SKU costs on the validation profile and
    confirmed that COGS now appears correctly in the Amazon P&L.
19. The Amazon P&L report now supports `Dollars` vs `% of Revenue`, a totals
    toggle, import-history pagination, and a header-driven month-range picker.
20. On 2026-03-17, CA transaction compatibility work landed in code:
    - parser support for CA `a.m./p.m.` timestamps
    - case-insensitive exact-field rule matching for CA label drift such as
      `Cost of advertising` and `Amazon fees`
    - explicit visibility for CA-only `Regulatory fee` and
      `Tax on regulatory fee` amount columns via `unmapped`
21. The focused CA importer coverage is green in the backend suite, and the
    real `2026Feb1-2026Feb28CustomTransaction.csv` sample now parses locally as
    a single `2026-02-01` month with `5,441` rows.
22. On 2026-03-17, live migration
    `20260317150607_seed_monthly_pnl_ca_mapping_rules.sql` was applied. It
    seeded global `CA` `amazon_transaction_upload` mapping rules from the
    shipped `US` rule pack without altering validated US imports.
23. The next Monthly P&L product goal is no longer CA parser discovery. The
    immediate next tranche is validating one real CA month end to end on a live
    CA profile/report path.

## Validated and active state

### Validated months that should be preserved

All of Whoosh US `2025-01-01` through `2025-12-01` is now validated, but the
two months that should be treated as especially sensitive/locked are:

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

The current known active/validated Whoosh US month coverage is:

1. `2025-01-01`, `2025-02-01`, `2025-03-01`
   - active import `61ddfe20-1fcb-4f0d-82aa-498e0493e352`
   - source `jan-mar2025-whoosh-us.csv`
   - import status `success`
2. `2025-04-01`, `2025-05-01`, `2025-06-01`
   - active import `43860acf-b705-4fee-85e4-fc8a6e0cab00`
   - source `apr-june2025-whoosh-us.csv`
   - import status `success`
3. `2025-07-01`
   - active import `5aa0f621-e9d7-4129-9f11-5b6597910eaa`
   - import status `success`
4. `2025-08-01`
   - active import `73eb37c5-6001-4699-82a1-e8de8f8cd861`
   - import status `success`
5. `2025-09-01`
   - active import `276cde82-45ca-48a4-a8f0-f15e8b54e3e2`
   - import status `success`
6. `2025-10-01`
   - active import `16468c3d-8a56-4eb2-8124-5e1b53a9168b`
   - import status `success`
7. `2025-11-01`
   - active import `0626222a-dc9c-4be5-a2ba-9de27b093494`
   - source `nov-2025.csv`
   - import status `success`
8. `2025-12-01`
   - active import `c84cade9-6633-427f-b4b0-2371d0aca344`
   - source `dec2025data-olderfile.csv`
   - import status `success`

### Current missing / not-yet-loaded months

1. `2026-01-01`
   - no current validated Whoosh US month slice intended for the report
2. `2026-02-01`
   - no current validated Whoosh US month slice intended for the report

## Historical note on the 2026-03-16 cleanup

Earlier stranded Jan/Apr/May 2025 partial-import state on the validation
profile was cleaned up on 2026-03-16 and should stay cleaned up. That history
matters only as provenance; it is no longer the active product problem.

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

### 4. The real report bottleneck was repeated aggregation from raw ledger rows

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

## Current open blocker

### Live CA profile validation is the next real tranche

The parser/rule-compatibility tranche is now done in code and the CA mapping
seed is live:

1. wide-range performance is fixed
2. async imports are live
3. 2025 Whoosh US coverage is active Jan through Dec
4. SKU-based COGS is live and has basic real-user validation
5. CA parser compatibility and CA global rule seeding are now landed

The immediate next problem is live CA validation.

Likely work required:

1. create or confirm the target CA Monthly P&L profile in the app
2. run a real CA transaction upload through the live import flow
3. inspect the resulting import month, unmapped totals, and report output
4. decide whether any remaining CA-specific rows need bucket mapping changes or
   should remain intentionally `unmapped`
5. verify that the report math and COGS behavior on the CA profile are sensible

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
2. `20260316140918_add_monthly_pnl_vine_fee_mapping.sql`
3. `20260316140932_add_monthly_pnl_report_bucket_totals_rpc.sql`
4. `20260316150635_add_monthly_pnl_manual_model_rules.sql`
5. `20260316154023_optimize_monthly_pnl_report_rpc_active_months.sql`
6. `20260316154945_fix_monthly_pnl_removal_and_refund_other_mapping.sql`
7. `20260316172805_optimize_monthly_pnl_report_rpc_exists.sql`
8. `20260316182035_add_monthly_pnl_import_month_bucket_totals.sql`
9. `20260316184040_cleanup_validation_profile_stranded_monthly_pnl_state.sql`
10. `20260316184041_claim_monthly_pnl_pending_imports.sql`
11. `20260317023402_add_monthly_pnl_sku_cogs_and_unit_summaries.sql`
12. `20260317150607_seed_monthly_pnl_ca_mapping_rules.sql`

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

1. Confirm the target CA profile and marketplace context in the live app/DB.
2. Upload one real CA transaction export through the live Monthly P&L flow.
3. Inspect the created import/import-month rows, active month state, and any
   unmapped totals on that CA profile.
4. Compare the rendered CA report output against expectation for that month.
5. If residual CA-specific rows remain ambiguous, add the narrowest possible
   mapping changes and rerun validation.

## Next-session prompt

Use this prompt to restart the next Monthly P&L session:

> Continue Monthly P&L work in `/Users/jeff/code/agency-os`.
>
> Read first, in this order:
> 1. `docs/monthly_pnl_handoff.md`
> 2. `docs/monthly_pnl_implementation_plan.md`
> 3. `AGENTS.md`
>
> Current reality:
> - US Amazon P&L is live and validated for Whoosh US across Jan-Dec 2025 on
>   validation profile `c8e854cf-b989-4e3f-8cf4-58a43507c67a`.
> - Preserve the validated November import
>   `0626222a-dc9c-4be5-a2ba-9de27b093494` and December import
>   `c84cade9-6633-427f-b4b0-2371d0aca344`.
> - SKU-based COGS is live; do not revert to month-lump COGS entry.
> - WBR is a separate shipped product and not Monthly P&L scope.
> - CA parser compatibility changes are already in code and pushed on `main`.
> - CA global mapping rules were seeded live via
>   `20260317150607_seed_monthly_pnl_ca_mapping_rules.sql`.
>
> Primary goal:
> - Validate one real CA Monthly P&L month end to end on a live CA profile.
>
> Focus:
> 1. Confirm the target CA profile and upload path.
> 2. Run a real CA transaction export through the live Monthly P&L importer.
> 3. Inspect import status, active month state, unmapped totals, and report
>    output.
> 4. Identify any remaining CA-specific rows that still need mapping changes.
> 5. Keep any follow-up fixes narrow and low-risk to the validated US path.
>
> Constraints:
> - Do not disturb the validated Whoosh US 2025 state unless explicitly asked.
> - Leave unrelated dirty files alone.
> - Prefer focused parser/mapping changes over broad refactors.

## Where the code lives

1. [transaction_import.py](/Users/jeff/code/agency-os/backend-core/app/services/pnl/transaction_import.py)
2. [transaction_import_csv.py](/Users/jeff/code/agency-os/backend-core/app/services/pnl/transaction_import_csv.py)
3. [transaction_import_ledger.py](/Users/jeff/code/agency-os/backend-core/app/services/pnl/transaction_import_ledger.py)
4. [transaction_import_store.py](/Users/jeff/code/agency-os/backend-core/app/services/pnl/transaction_import_store.py)
5. [transaction_import_models.py](/Users/jeff/code/agency-os/backend-core/app/services/pnl/transaction_import_models.py)
6. [sku_units.py](/Users/jeff/code/agency-os/backend-core/app/services/pnl/sku_units.py)
7. [report.py](/Users/jeff/code/agency-os/backend-core/app/services/pnl/report.py)
8. [profiles.py](/Users/jeff/code/agency-os/backend-core/app/services/pnl/profiles.py)
9. [pnl.py](/Users/jeff/code/agency-os/backend-core/app/routers/pnl.py)
10. [test_pnl_transaction_import.py](/Users/jeff/code/agency-os/backend-core/tests/test_pnl_transaction_import.py)
11. [test_pnl_report.py](/Users/jeff/code/agency-os/backend-core/tests/test_pnl_report.py)
