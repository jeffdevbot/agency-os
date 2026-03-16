# Monthly P&L Handoff

_Last updated: 2026-03-16 (ET)_

This is the fast restart point for the current Monthly P&L build.

## Current shipped state

Relevant commits on `main`:

1. `ad00d56` - `Refine monthly P&L implementation plan`
2. `f3c1ca2` - `Add Monthly P&L Phase 1: foundation schema, import pipeline, and admin API`
3. `d515075` - `Add Monthly P&L Phase 2: report service, API endpoint, and frontend`
4. `8680066` - `Fix P&L Phase 2: COGS schema, refund section, month filters, range UI`
5. `16e830e` - `Add P&L onboarding and upload UI`
6. `5a794b5` - `Fix Amazon transaction timestamp parsing`
7. `165ad01` - `Paginate P&L ledger report queries`
8. `b5b5d1f` - `Fix monthly P&L month assignment and reimport flow`
9. `f4acff1` - `Handle legacy P&L reimport unique index`

## Live database / migration state

Monthly P&L foundation migration was applied live:

1. `20260315200000_monthly_pnl_phase1_foundation.sql`

Follow-up migration exists in repo but may or may not be applied live:

1. `20260316173000_allow_monthly_pnl_reimport_same_sha.sql`

Important:

1. `f4acff1` added a backend fallback so same-file reimport should still work even if the follow-up unique-index migration was not applied yet.
2. The migration is still the correct schema state and should be applied eventually.

## Current user-facing routes

1. `/reports/[clientSlug]`
2. `/reports/[clientSlug]/[marketplaceCode]/pnl`

Admin/backend routes:

1. `GET /admin/pnl/profiles?client_id=<uuid>`
2. `POST /admin/pnl/profiles`
3. `GET /admin/pnl/profiles/{profile_id}`
4. `GET /admin/pnl/profiles/{profile_id}/imports`
5. `GET /admin/pnl/profiles/{profile_id}/imports/{import_id}`
6. `GET /admin/pnl/profiles/{profile_id}/import-months`
7. `POST /admin/pnl/profiles/{profile_id}/transaction-upload`
8. `GET /admin/pnl/profiles/{profile_id}/report`

## What works on paper / in tests

### Foundation

1. `monthly_pnl_profiles`, `monthly_pnl_imports`, `monthly_pnl_import_months`, `monthly_pnl_raw_rows`, `monthly_pnl_ledger_entries`, `monthly_pnl_mapping_rules`, and `monthly_pnl_cogs_monthly` all exist in the schema plan and initial migration.
2. Admin profile creation and P&L page onboarding flow were added.
3. CSV parsing handles:
   - UTF-8 BOM
   - UTF-16
   - comma/tab delimiter sniffing
   - Amazon timestamps like `Dec 1, 2025 12:04:11 AM PST`
4. Upload import pipeline:
   - parses raw rows
   - expands ledger entries
   - creates month slices
   - activates month slices
5. Report endpoint aggregates active ledger entries and renders the P&L UI.

### Important fixes already landed

1. Ledger query pagination bug was fixed in `165ad01`.
   - Before that fix, the report only summed the first PostgREST page and produced tiny obviously wrong values.
2. Canonical month assignment was switched in `b5b5d1f` from:
   - `Transaction Release Date first`
   to:
   - `date/time first, release date fallback`
3. Same-file reimport/supersede flow was added in `b5b5d1f`.
4. Legacy unique-index compatibility fallback was added in `f4acff1`.

## Real live validation status

This is **not** fully working yet in production.

### Actual user session outcome

Using the real file:

1. `/Users/jeff/Downloads/2025DecMonthlyUnifiedTransaction.csv`

Observed:

1. Initial upload eventually ran.
2. Report values were wrong.
3. A bad `Jan 2026` column appeared even though the file is a December 2025 transaction export.
4. Same-file reupload originally failed with:
   - `This file has already been imported (import ...)`
5. After the reimport/supersede fixes were pushed, the next live symptom became:
   - `Transaction import failed`
   - backend log: `POST /admin/pnl/profiles/{profile_id}/transaction-upload HTTP/1.1" 500`
6. After refresh, the user saw:
   - `Failed to list P&L profiles`
   even though the visible backend log snippet showed `GET /admin/pnl/profiles?... 200`

### Why the bad January column existed

Before `b5b5d1f`, importer month assignment used `Transaction Release Date` first.

That caused December file rows to spill into `2026-01-01` month slices.

That behavior reproduced the live bad January values almost exactly.

### Why January is probably still showing

The stale `Jan 2026` month slice will remain visible until a successful replacement import supersedes/deactivates it.

If reupload fails, the old bad active month slice remains active.

## Real file observations

From the actual December file:

1. It is structurally valid.
2. It has a UTF-8 BOM but that is harmless.
3. The numeric fields are normal numeric strings, not weird Excel coercions.
4. The main format issue was the timestamp suffix like `PST`.

Important reconciliation note:

1. Under `date/time` month logic, the file should align much better with the manual December P&L.
2. Under `release date` month logic, it creates the bad January carryover.

## Known remaining open issues

### 1. Live `transaction-upload` still returns 500

Most recent symptom:

1. `POST /admin/pnl/profiles/c8e854cf-b989-4e3f-8cf4-58a43507c67a/transaction-upload HTTP/1.1" 500`

Most likely causes to verify first:

1. Latest backend deploy from `f4acff1` was not yet live when the user tested.
2. The fallback path in `f4acff1` is not the failing path; some other PostgREST/database error is occurring during import.
3. There is a second DB constraint failure after the import insert retry.

### 2. Stale active January month slice remains visible

This is likely just a consequence of the failed replacement import.

If not, inspect `monthly_pnl_import_months` for active stale rows after the next successful retry.

### 3. `Failed to list P&L profiles` after refresh

This needs investigation.

The visible user-provided log snippet showed:

1. `GET /admin/pnl/profiles?... 200`

So the frontend may be:

1. surfacing a stale/generic error
2. failing on response parsing
3. racing against another request and mapping the wrong error to the page
4. or the relevant failing request was not included in the log snippet

## What the numbers should roughly be

Manual December 2025 target from the agency spreadsheet screenshot:

1. Product sales: `332,515.8`
2. Shipping credits: `7,087.5`
3. Gift wrap credits: `35.9`
4. Promotional rebate refunds: `131.1`
5. Total gross revenue: `339,770.2`
6. Refunds: `-4,889.9`
7. FBA inventory credit: `386.2`
8. Shipping credit refunds: `-128.8`
9. Promotional rebates: `-6,681.6`
10. Total refunds: `-11,314.1`
11. Net revenue: `328,456.1`
12. COGS: `37,026.1`
13. Gross profit: `291,429.9`
14. Referral fees: `-48,954.0`
15. FBA fees: `-95,183.8`
16. Other transaction fees: `0.1`
17. FBA monthly storage fees: `-4,125.3`
18. FBA long-term storage fees: `-44.2`
19. FBA removal order fees: `-112.3`
20. Subscription fees: `-16.9`
21. Inbound placement & defect fees: `-3,451.9`
22. Promotions fees: `-645.0`
23. Advertising: `-21,201.8`
24. Total expenses: `-173,735.1`
25. Net earnings: `117,694.8`

## Where the code lives

Backend:

1. `backend-core/app/services/pnl/transaction_import.py`
2. `backend-core/app/services/pnl/report.py`
3. `backend-core/app/services/pnl/profiles.py`
4. `backend-core/app/routers/pnl.py`

Frontend:

1. `frontend-web/src/app/reports/_components/PnlReportScreen.tsx`
2. `frontend-web/src/app/reports/_components/ClientReportsHub.tsx`
3. `frontend-web/src/app/reports/pnl/_lib/pnlApi.ts`
4. `frontend-web/src/app/reports/pnl/_lib/useResolvedPnlProfile.ts`

Tests:

1. `backend-core/tests/test_pnl_transaction_import.py`
2. `backend-core/tests/test_pnl_report.py`
3. `backend-core/tests/test_pnl_router.py`

## First debugging steps for the next session

1. Confirm the latest backend commit deployed on Render:
   - `f4acff1`
2. Reproduce the upload with the real December file.
3. Capture the full backend exception/trace for the `500` on:
   - `POST /admin/pnl/profiles/{profile_id}/transaction-upload`
4. Inspect live DB rows for this profile:
   - `monthly_pnl_imports`
   - `monthly_pnl_import_months`
5. Confirm whether active Jan 2026 rows are still tied to the old import.
6. If the replacement import still fails, patch the exact failing DB/service path rather than guessing.
7. Once upload succeeds, compare the rendered December report against the manual spreadsheet and fix remaining mapping/model deltas.

## Useful live SQL checks

Replace profile id as needed. Current Whoosh US P&L profile seen in logs:

1. `c8e854cf-b989-4e3f-8cf4-58a43507c67a`

Check imports:

```sql
select
  id,
  source_filename,
  source_file_sha256,
  import_status,
  supersedes_import_id,
  period_start,
  period_end,
  row_count,
  error_message,
  created_at,
  finished_at
from public.monthly_pnl_imports
where profile_id = 'c8e854cf-b989-4e3f-8cf4-58a43507c67a'
order by created_at desc;
```

Check month slices:

```sql
select
  id,
  import_id,
  entry_month,
  import_status,
  is_active,
  raw_row_count,
  ledger_row_count,
  mapped_amount,
  unmapped_amount,
  created_at
from public.monthly_pnl_import_months
where profile_id = 'c8e854cf-b989-4e3f-8cf4-58a43507c67a'
order by entry_month desc, created_at desc;
```

Check current active report months:

```sql
select
  entry_month,
  import_id,
  import_status,
  is_active
from public.monthly_pnl_import_months
where profile_id = 'c8e854cf-b989-4e3f-8cf4-58a43507c67a'
  and is_active = true
order by entry_month desc;
```

## Current bottom line

The project is **past the schema/prototype stage** but **not yet production-correct**.

The next session should focus on:

1. getting the replacement import to succeed live
2. clearing the stale January month slice through that successful supersede flow
3. reconciling December totals against the manual spreadsheet

