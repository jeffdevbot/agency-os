# Monthly P&L Handoff

_Last updated: 2026-03-24 (ET)_

## Current debugging focus

The next Monthly P&L session should start from live debugging, not broad
feature planning.

Current priority:

1. Investigate remaining **US Monthly P&L unmapped transactions** on the real
   client profiles the user is reviewing now.
2. Use live Supabase data first so the next session can inspect the exact
   `monthly_pnl_import_months`, `monthly_pnl_ledger_entries`, and any related
   mapping-rule rows before making assumptions.
3. Treat the recent CA unmapped issue as already diagnosed:
   - Lifestyle CA profile:
     `6b4c8a33-db09-4ed7-b5f5-902c663051b3`
   - affected warning months before the fix:
     `2025-06-01`, `2025-07-01`, `2025-08-01`
   - unmapped rows were all `FBA Inventory Fee` with `order_id` values
     starting with `FBA`
   - those represent partnered-carrier inbound FBA charges and should map to
     `inbound_shipping_and_duties`
   - the root cause was marketplace scoping: the catch-all
     `order_id starts_with FBA` rule existed for `US` only
   - repo migration now exists:
     `supabase/migrations/20260324163000_add_monthly_pnl_ca_fba_inbound_carrier_rule.sql`
   - pushed commit:
     `15fcae6` (`Add CA FBA inbound carrier P&L rule`)
4. If the user wants the CA warning fully cleared, the relevant source files
   need to be re-imported after that rule:
   - `2025Apr1-2025Jun30CustomTransaction.csv`
   - `2025Jul1-2025Sep30CustomTransaction.csv`
5. Important operational note for the next session:
   - Supabase MCP auth may still look stale inside an existing Codex chat even
     after `codex mcp login supabase` succeeds in the terminal
   - if MCP tool calls still return `Auth required`, do **not** waste time
     debating the config; start a fresh Codex session
   - `codex mcp get supabase` / `codex mcp list` only show config, not a live
     authenticated tool round-trip

## New session note

This handoff should now be read as a shipped-state reference, not an active
"still building the first slice" plan.

For a fresh session, read this document for shipped-state context, then also
read:

1. [current_handoffs.md](/Users/jeff/code/agency-os/docs/current_handoffs.md)
2. [reports_api_access_and_spapi_plan.md](/Users/jeff/code/agency-os/docs/reports_api_access_and_spapi_plan.md)
3. [monthly_pnl_windsor_reconciliation.md](/Users/jeff/code/agency-os/docs/monthly_pnl_windsor_reconciliation.md)

Current strategic direction:

1. Monthly P&L remains live and validated from CSV uploads.
2. Windsor compare work is now best understood as a reconciliation/debug path,
   not the long-term source-of-truth path for Amazon financial data.
3. The longer-term architecture direction is still:
   - shared `Reports / API Access`
   - move Amazon Ads connection management there
   - add Amazon Seller API auth there
   - use that shared Seller API connection for a P&L-first direct-SP-API path
4. `non_pnl_transfer` remains the clearest reason to validate direct Amazon
   payment/disbursement access.
5. The reviewed direction for Claude/P&L is now implemented rather than
   speculative:
   - one shared Agency OS Claude Project
   - shared `resolve_client`
   - read-only P&L analysis
   - structured P&L brief generation
   - persisted P&L email drafting
   - no separate Claude Project per report type
6. Current code review indicates Monthly P&L likely does **not** need a
   separate snapshot layer for that first Claude slice, because the report is
   already built from persisted active month slices and precomputed month
   totals:
   - `monthly_pnl_import_months.is_active = true`
   - `monthly_pnl_import_month_bucket_totals`
   - `monthly_pnl_import_month_sku_units`
   - `monthly_pnl_sku_cogs`
   The current report path already behaves like a curated month-level
   snapshot set.

Current implementation state on that direction:

1. Passes 1-4 of the shared `Reports / API Access` plan are now implemented.
2. Shared `report_api_connections` storage is live in production.
3. `/reports/api-access` is live as an admin surface for:
   - Amazon Ads shared connection visibility / launch
   - Amazon Seller API shared connection visibility / launch
   - SP-API validation
   - SP-API finance smoke testing
4. Region-aware SP-API routing is implemented across auth, persistence,
   validation, and finance smoke-test calls for `NA`, `EU`, and `FE`.
5. Shared connection health handling is hardened:
   - only `connection_status = 'connected'` is treated as healthy
   - `error` / `revoked` are surfaced distinctly
   - WBR Ads lookup falls back to legacy storage if the shared Ads row is not
     healthy
6. WBR Windsor-backed behavior and manual Monthly P&L CSV upload mode remain
   the active stable paths and were not replaced.
7. Current blocker is now Amazon app-side approval/configuration, not product
   code:
   - auth first failed with `MD1000` until draft-app mode was enabled
   - draft testing now uses `AMAZON_SPAPI_DRAFT_APP=true`
   - auth then failed with `MD9100`, indicating missing SP-API app Login URI /
     Redirect URI configuration
   - the user has applied for public app approval and paused work pending
     Amazon response
8. Required Amazon app URIs for the currently deployed callback shape:
   - Login URI: `https://tools.ecomlabs.ca/reports/api-access`
   - Redirect URI: `https://backend-core-re6d.onrender.com/amazon-spapi/callback`
   - optional secondary redirect URI:
     `https://backend-core-re6d.onrender.com/api/amazon-spapi/callback`
9. During this work, the frontend Render service hit a broken default Node
   image on `22.16.0`; the repo now pins frontend Node to `20.19.0`.
10. The first read-only Monthly P&L MCP slice is now implemented in code:
    - shared client discovery now lives in
      `backend-core/app/mcp/tools/clients.py`
    - `resolve_client` is now a shared Command Center resolver rather than a
      WBR-owned resolver
    - `resolve_client` now includes:
      - WBR marketplace coverage
      - Monthly P&L marketplace coverage
      - brands / ClickUp destination hints
      - team assignments
      - client context fields
    - P&L read-only MCP tools now include:
      - `list_monthly_pnl_profiles`
      - `get_monthly_pnl_report`
      - `get_monthly_pnl_email_brief`
    - P&L mutating draft tool now includes:
      - `draft_monthly_pnl_email`
11. Current Claude Project state:
    - `docs/claude_project/project_instructions.md` now covers both WBR and
      Monthly P&L
    - `docs/claude_project/wbr_mcp_playbook.md` now assumes the shared
      `resolve_client` contract
    - `docs/claude_project/monthly_pnl_mcp_playbook.md` now covers live P&L
      analysis, brief, and draft workflows
    - live Claude smoke tests for WBR and Monthly P&L are green
12. Targeted regression coverage after those MCP changes is green:
    - `backend-core/tests/test_mcp_pilot.py`
    - `backend-core/tests/test_pnl_report.py`
    - `backend-core/tests/test_pnl_workbook.py`
13. The first clean Monthly P&L email-drafting spec now exists in
    `docs/monthly_pnl_email_drafting_spec.md`.
    It captures:
    - the extracted writing pattern from real manual P&L emails
    - a proposed Claude-facing preview/persisted email tool contract
    - the exact data requirements for reliable drafting, including conditional
      YoY / MoM fallback rules
14. The structured Monthly P&L email-brief layer is now implemented and live:
    - backend service:
      `backend-core/app/services/pnl/email_brief.py`
    - MCP wrapper/tool:
      `backend-core/app/mcp/tools/pnl.py`
      `get_monthly_pnl_email_brief`
    - current role:
      - read-only bridge between `get_monthly_pnl_report` and
        `draft_monthly_pnl_email`
      - deterministic marketplace-level snapshot metrics, driver candidates,
        verdicts, and data-quality notes for a selected client/month
15. The persisted Monthly P&L draft layer is now implemented and live:
    - services:
      - `backend-core/app/services/pnl/email_prompt.py`
      - `backend-core/app/services/pnl/email_drafts.py`
    - persistence migration:
      - `supabase/migrations/20260323170000_add_monthly_pnl_email_drafts.sql`
    - MCP tool:
      - `draft_monthly_pnl_email`
    - shape:
      - the draft tool uses the structured brief internally
      - normal user-facing workflow stays simple:
        inspect with `get_monthly_pnl_report` or draft directly with
        `draft_monthly_pnl_email`
16. Monthly P&L YoY is now shipped in the web product:
    - shared comparison layer:
      `backend-core/app/services/pnl/comparison.py`
    - YoY adapter:
      `backend-core/app/services/pnl/yoy_report.py`
    - frontend YoY mode:
      - `Standard` / `YoY` toggle
      - year selector
      - `% of Revenue` support in YoY
      - dashed prior-year chart series
      - YoY Excel export
17. Claude does not have a dedicated YoY MCP tool, and that is currently the
    intended state:
    - the web app has a true YoY route/view
    - Claude can still do YoY reasoning with existing P&L tools
    - if a dedicated YoY tool is ever needed, it should sit on the shared
      comparison layer instead of duplicating rules again

Docs currently known to be partially outdated for the new direction:

1. `docs/wbr_v2_handoff.md` (historical/reference)
2. older archived planning docs outside the current handoff set

The previously stale `docs/wbr_v2_schema_plan.md` and `docs/db/schema_master.md`
have now been refreshed and should be treated as current again.

This is the current restart point for Monthly P&L after the US v1 validation
push, the Jan-Dec 2025 Whoosh US backfill, the SKU-based COGS rollout, the CA
parser/mapping rollout, the first live CA validations, the Excel export/payout
follow-up work, and the latest import/UI hardening work.

## P&L email drafting direction

The older screenshot/OCR-based prompt is no longer the right product model for
Agency OS.

The current recommended direction is:

1. draft Monthly P&L emails from canonical Agency OS report data
2. use YoY only when a same-month prior-year comparison and YTD prior-year
   window are actually available
3. fall back cleanly to MoM or omit unsupported comparisons when YoY is not
   available
4. keep the structured Monthly P&L email brief layer as the canonical
   drafting-prep layer
5. keep `draft_monthly_pnl_email` thin on top of that brief instead of jumping
   straight from raw `get_monthly_pnl_report` output to a draft

See `docs/monthly_pnl_email_drafting_spec.md` for the concrete writing pattern,
tool contract, and data requirements.

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
   `20260316182035_add_monthly_pnl_import_month_bucket_totals.sql` was applied.
   It backfilled `monthly_pnl_import_month_bucket_totals` and rewired
   `pnl_report_bucket_totals(...)` to read those precomputed month totals.
9. On the validation profile, the exact wide range
    `2025-01-01` through `2026-02-01` now executes at about `4.5 ms` at the
    function boundary instead of roughly `7.3 s`.
10. On 2026-03-16, live migration
    `20260316184041_claim_monthly_pnl_pending_imports.sql` was applied. It
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
    `20260316184040_cleanup_validation_profile_stranded_monthly_pnl_state.sql`
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
    `20260317023402_add_monthly_pnl_sku_cogs_and_unit_summaries.sql` was
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
23. On 2026-03-17, live migration
    `20260317154748_add_monthly_pnl_fulfilment_removal_prefix_rule.sql` was
    applied to map `Fulfilment by Amazon removal order: disposal fee` into
    `fba_removal_order_fees` for `US` and `CA`.
24. On 2026-03-17, live migration
    `20260317161435_add_monthly_pnl_ca_label_variants.sql` was applied to map
    observed CA label variants:
    - `Coupon Redemption Fee...`
    - `Vine Enrolment Fee`
    - `Fulfilment by Amazon prep fee...`
25. Whoosh CA Monthly P&L is now live and manually validated for
    `2026-01-01` through `2026-02-01` on profile
    `a5faca8a-4225-4115-8510-0e6b185ee86c`.
26. Distex CA Monthly P&L is now live with active backfill coverage from
    `2024-01-01` through `2026-02-01` on profile
    `faf4307d-80d7-4fa0-8a85-e8b805110860`.
27. That earlier "CA fully clean" state is no longer the right blanket
    assumption. A later real-client pass exposed an additional CA mapping gap:
    `FBA Inventory Fee` rows with `order_id` values starting with `FBA`
    (partnered-carrier inbound charges). That gap is now fixed in the rule
    set, but warning cleanup still depends on re-importing the affected CA
    source files.
28. The async import path now stores progress/heartbeat metadata, marks failed
    background imports as `error` instead of leaving them stranded in
    `running`, and the UI surfaces queued/running progress instead of a silent
    wait.
29. The SKU-based COGS settings workflow now includes a collapsed SKU list plus
    CSV export/import round-trip support, with CSV import acting as an
    authoritative rewrite of the currently loaded SKU set.
30. The `/reports` hub Monthly P&L card no longer shows a hardcoded currency
    label, because the product does not perform currency normalization.
31. On 2026-03-17, live migration
    `20260317165228_add_monthly_pnl_other_expenses.sql` was applied. It added
    manual per-month expense storage plus per-profile visibility toggles for
    non-Amazon Monthly P&L rows.
32. The Monthly P&L settings panel now includes `Other expenses`, with:
    - manual monthly `FBM Fulfillment Fees`
    - manual monthly `Agency Fees`
    - show/hide toggles for each row
    - CSV export/import round-trip for the visible months
33. Enabled `Other expenses` rows now flow into `Total Expenses` and
    `Net Earnings` without changing Amazon ingest or mapping behavior.
34. The Amazon P&L header now includes Excel export. The workbook mirrors the
    selected report window and totals visibility, with a `Dollars` tab and a
    `% of Revenue` tab using the same report builder logic as the UI.
35. P&L workbook export now derives currency from marketplace, uses
    accounting-style negative formats with brackets instead of red minus
    formatting, and names files as
    `account-marketplace-pnl-start-end.xlsx`.
36. The shared `/reports` shell and P&L table spacing were widened/tightened so
    full-year views fit more cleanly on common desktop screens, while smaller
    screens simply scroll horizontally.
37. P&L presentation now uses accounting-style brackets for negative values and
    whole-number display in the UI. In `% of Revenue`, the refund band from
    `Product Refunds` through `Total Refunds & Adjustments` uses
    `Total Gross Revenue` as the denominator; lower rows continue to use
    `Total Net Revenue`.
38. The report now appends `Payout ($)` and `Payout (%)` after
    `Contribution Profit` / `Contribution Margin (%)`, with payout sourced from
    the existing `non_pnl_transfer` ledger bucket and payout percent calculated
    against `Total Net Revenue`.

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

### Live CA month coverage now active

Whoosh CA:

1. `2026-01-01`
   - active import `f3b15c0f-c4b0-4915-9749-9bf434fcf032`
   - source `2026JanMonthlyTransaction.csv`
   - import status `success`
2. `2026-02-01`
   - active import `9df00715-d894-4a8c-a177-16610cb7be7c`
   - source `2026Feb1-2026Feb28CustomTransaction.csv`
   - import status `success`

Distex CA:

1. `2024-01-01` through `2024-06-01`
   - active import `2a6e1270-0615-4694-9738-d468ed4bbf11`
   - source `2024Jan1-2024Jun30CustomTransaction.csv`
   - import status `success`
2. `2024-07-01` through `2024-12-01`
   - active import `e202dd84-63f9-4926-bab8-f04ed2c3ff0e`
   - source `2024Jul1-2024Dec31CustomTransaction.csv`
   - import status `success`
3. `2025-01-01` through `2025-06-01`
   - active import `4ba6e484-d27f-4b3c-863c-a3c459731c31`
   - source `2025Jan1-2025Jun30CustomTransaction.csv`
   - import status `success`
4. `2025-07-01` through `2025-11-01`
   - active import `4272361c-c96b-4923-a0e7-1d63b5a61e6c`
   - source `2025Jul1-2025Nov30CustomTransaction.csv`
   - import status `success`
5. `2025-12-01` through `2026-02-01`
   - active import `cd307d91-99f6-40b9-8526-09568898d9eb`
   - source `2025Dec1-2026Feb28CustomTransaction.csv`
   - import status `success`

Do not assume CA currently reports zero active unmapped months on every live
profile. The later Lifestyle CA review exposed the inbound-carrier rule gap
described above.

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

## Current open area

### CA validation is mostly complete; current focus shifts to live unmapped debugging

The previous CA parser-discovery and live-validation tranche is done:

1. wide-range performance is fixed
2. async imports are live with visible progress
3. 2025 Whoosh US coverage is active Jan through Dec
4. SKU-based COGS is live and now has CSV round-trip support
5. manual `Other expenses` are now live for `FBM Fulfillment Fees` and
   `Agency Fees`
6. Whoosh CA and Distex CA are live on real uploaded transaction reports
7. Lifestyle CA exposed one additional real-world rule gap for
   `FBA Inventory Fee` rows with `order_id` prefixed by `FBA`; that rule is
   now fixed for `CA`, but the user still needs re-import coverage if they
   want those historical warning months cleared

The next work should be chosen intentionally rather than treated as broad new
feature work. The immediate next bucket is live unmapped debugging on the US
side, prioritized with the user. After that, the likely buckets are:

1. confirm the exact remaining US unmapped rows from live Supabase data before
   proposing new mapping rules
2. broader client/marketplace backfill as the user requests it
3. narrow mapping additions if future uploads expose new real-world labels
4. low-risk report/operator additions such as disbursement reconciliation,
   remaining export polish, or drillback/provenance improvements
5. operator workflow/product decisions now that COGS, payouts, and manual
   other-expense tooling exist in the settings surface
6. Windsor settlement ingestion only if/when that automation path becomes the
   next explicit priority

## December 2025 final numbers

These remain the current validated December totals on the active older-file
import:

1. `total_gross_revenue = 339,770.20`
2. `total_refunds = -11,314.14`
3. `total_net_revenue = 328,456.06`
4. `total_expenses = -173,735.13`

These match the manual workbook target values to rounding/penny level.

## Live migrations now applied

Repo migration files currently relevant to the live Monthly P&L state:

1. `20260315200000_monthly_pnl_phase1_foundation.sql`
2. `20260316173000_allow_monthly_pnl_reimport_same_sha.sql`
3. `20260316173000_optimize_monthly_pnl_report_rpc_exists.sql`
4. `20260316190000_add_monthly_pnl_vine_fee_mapping.sql`
5. `20260316191000_add_monthly_pnl_report_bucket_totals_rpc.sql`
6. `20260316194500_optimize_monthly_pnl_report_rpc_active_months.sql`
7. `20260316195500_fix_monthly_pnl_removal_and_refund_other_mapping.sql`
8. `20260316203000_add_monthly_pnl_manual_model_rules.sql`
9. `20260316213000_add_monthly_pnl_import_month_bucket_totals.sql`
10. `20260316224500_claim_monthly_pnl_pending_imports.sql`
11. `20260316232000_cleanup_validation_profile_stranded_monthly_pnl_state.sql`
12. `20260317001000_add_monthly_pnl_sku_cogs_and_unit_summaries.sql`
13. `20260317150607_seed_monthly_pnl_ca_mapping_rules.sql`
14. `20260317154748_add_monthly_pnl_fulfilment_removal_prefix_rule.sql`
15. `20260317161435_add_monthly_pnl_ca_label_variants.sql`
16. `20260317165228_add_monthly_pnl_other_expenses.sql`
17. `20260318123000_add_report_api_connections.sql`
18. `20260319120000_add_monthly_pnl_fba_inbound_carrier_rule.sql`
19. `20260323170000_add_monthly_pnl_email_drafts.sql`

## Important constraints

1. Do not replace the active December import on the validation profile unless
   the user explicitly wants to change the validated source basis.
2. Do not redo December 2025 from scratch unless explicitly asked.
3. Preserve the successful November and December validation state.
4. Preserve the current active CA imports unless the user explicitly wants a
   replacement or broader backfill.
5. Treat WBR as a separate shipped reporting product. Monthly P&L is its own
   `/reports/.../pnl` surface, not WBR follow-on scope.
6. Leave unrelated dirty files alone:
   - `docs/db/schema_master.md`
   - `scripts/db/generate-schema-master.sh`
   - `supabase/.temp/*`

## Recommended next-session plan

1. Treat the next session as a current-state Monthly P&L product/runtime
   session, not as a first-slice MCP design session.
2. Reuse the existing persisted report model first:
   - `backend-core/app/services/pnl/report.py`
   - `backend-core/app/routers/pnl.py`
3. Treat the current MCP surface as already live:
   - `resolve_client`
   - `list_monthly_pnl_profiles`
   - `get_monthly_pnl_report`
   - `get_monthly_pnl_email_brief`
   - `draft_monthly_pnl_email`
4. Do **not** introduce a separate P&L snapshot layer unless a concrete product
   need appears (for example, frozen client-facing monthly digests or
   “what did we send last month?” auditability).
5. Preserve the validated Whoosh US and currently active CA import state unless
   the user explicitly wants to replace it.
6. Keep direct Amazon SP-API financial ingestion as a separate longer-term
   track, not the blocker for the current CSV-backed/MCP-backed product.

## Next-session prompt

Use this prompt to restart the next Monthly P&L / Claude expansion session:

> Continue Agency OS Monthly P&L work in `/Users/jeff/code/agency-os`.
>
> The WBR and Monthly P&L Claude/MCP surfaces are now both live. The next
> likely session goal is to extend or refine the current Monthly P&L surface,
> not to design the first slice from scratch.
>
> Read first, in this order:
> 1. `docs/monthly_pnl_handoff.md`
> 2. `docs/monthly_pnl_resume_prompt.md`
> 3. `docs/monthly_pnl_implementation_plan.md`
> 4. `docs/agency_os_mcp_implementation_plan.md`
> 5. `docs/claude_primary_surface_plan.md`
> 6. `AGENTS.md`
>
> Current reality:
> - US Amazon P&L is live and validated for Whoosh US across Jan-Dec 2025 on
>   validation profile `c8e854cf-b989-4e3f-8cf4-58a43507c67a`.
> - Preserve the validated November import
>   `0626222a-dc9c-4be5-a2ba-9de27b093494` and December import
>   `c84cade9-6633-427f-b4b0-2371d0aca344`.
> - CA transaction upload support is live and validated on real profiles:
>   Whoosh CA (`2026-01` through `2026-02`) and Distex CA (`2024-01` through
>   `2026-02`).
> - SKU-based COGS is live; do not revert to month-lump COGS entry.
> - `Other expenses`, Excel export, payout rows, and async import progress are
>   already live.
> - Shared `report_api_connections` is live, but direct Amazon SP-API finance
>   ingestion is still pending Amazon-side approval/configuration.
> - The structured P&L brief and persisted draft layers are already live
>   through the MCP surface.
> - YoY is already live in the web product through the shared comparison layer.
> - Direct Amazon SP-API finance access is still a longer-term path pending
>   Amazon-side approval/configuration; do not assume it is available for the
>   next slice.
> - Current code review suggests Monthly P&L already behaves like a curated
>   monthly snapshot set because the report reads persisted active month slices
>   and precomputed month totals, not live upstream calls.
>
> Primary goal:
> - Improve or extend the current Monthly P&L surface without redoing already
>   shipped MCP/reporting architecture.
>
> Focus:
> 1. Review the shipped Monthly P&L state first.
> 2. Inspect the current report path and existing data model before inventing
>    new persistence.
> 3. Reuse the existing P&L MCP/report services before adding any new tool.
> 4. Prefer reusing `PNLReportService` over building a separate P&L snapshot
>    layer unless a concrete product need appears.
> 5. Preserve validated Whoosh US and active CA imports unless explicitly asked
>    to replace them.
>
> Constraints:
> - Do not disturb the validated Whoosh US 2025 state unless explicitly asked.
> - Leave unrelated dirty files alone.
> - Prefer focused, low-risk follow-up work over broad importer refactors.
> - Treat WBR as stable reference context, not as the next build target.

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
