# Monthly P&L Handoff

_Last updated: 2026-03-16 (ET)_

This is the fast restart point for the current Monthly P&L build.

## Current status after the latest debugging session

This is the actual state as of the end of the March 16 session:

1. Real production re-import of `/Users/jeff/Downloads/2025DecMonthlyUnifiedTransaction.csv` succeeded.
2. Profile under test:
   - `c8e854cf-b989-4e3f-8cf4-58a43507c67a`
3. Successful replacement import:
   - `c18a2d89-bd83-4662-86d2-d59afec26e53`
   - created `2026-03-16 13:24:31+00`
   - finished `2026-03-16 13:25:47+00`
4. The stale bad import month slices are no longer active.
   - Active month set is now only `2025-12-01`
   - Old `2026-01-01` slice from the bad import is inactive
5. The earlier upload failures were real duplicate-SHA DB failures on the old unique index state.
6. The remaining production problem is now the report path, not the upload path.
   - `GET /admin/pnl/profiles/{profile_id}/report` works but is too slow live
   - direct measurement against production took about `92s` for Dec 2025
   - local report build against live data with the old row-by-row path took about `42s`
7. Local code changes were made but are not deployed yet.
8. New local migrations were added but are not applied live yet:
   - `20260316190000_add_monthly_pnl_vine_fee_mapping.sql`
   - `20260316191000_add_monthly_pnl_report_bucket_totals_rpc.sql`
9. Focused backend tests pass locally:
   - `backend-core/tests/test_pnl_report.py`
   - `backend-core/tests/test_pnl_transaction_import.py`
   - result: `67 passed`

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

This follow-up migration now appears effectively live because same-SHA successful
re-imports are now possible while prior successful imports still exist:

1. `20260316173000_allow_monthly_pnl_reimport_same_sha.sql`

Important:

1. Earlier failed re-import attempts on March 16 still show the old duplicate-SHA DB error in `monthly_pnl_imports.error_message`.
2. Later successful re-imports with the same SHA prove the live DB no longer blocks them the old way.
3. Two newer migrations exist locally but are not applied live yet:
   - `20260316190000_add_monthly_pnl_vine_fee_mapping.sql`
   - `20260316191000_add_monthly_pnl_report_bucket_totals_rpc.sql`

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

This is still **not fully production-correct**, but the state is materially
better than at the start of the session.

### Actual user session outcome

Using the real file:

1. `/Users/jeff/Downloads/2025DecMonthlyUnifiedTransaction.csv`

Observed across the full debugging sequence:

1. Initial upload ran but produced wrong values.
2. A bad `Jan 2026` column appeared because the old importer used release date first.
3. Same-file reupload originally failed on duplicate SHA handling.
4. Multiple March 16 reupload attempts then failed with duplicate key errors on:
   - `uq_monthly_pnl_imports_profile_source_sha256`
5. Production replacement import later succeeded:
   - `7462325a-c020-4a63-a382-1ccfc422fa36`
6. A second real production replacement import also succeeded:
   - `c18a2d89-bd83-4662-86d2-d59afec26e53`
7. The bad January slice is now inactive.
8. The next live blocker is the report path being too slow.
9. Production `GET /report` can return eventually, but it is not safe at current latency.

### Why the bad January column existed

Before `b5b5d1f`, importer month assignment used `Transaction Release Date` first.

That caused December file rows to spill into `2026-01-01` month slices.

That behavior reproduced the live bad January values almost exactly.

### Why January is no longer showing

The successful replacement import superseded the bad old import and deactivated
its month slices.

Current active slice state for the validation profile:

1. `2025-12-01` active on import `c18a2d89-bd83-4662-86d2-d59afec26e53`
2. `2026-01-01` inactive on old import `32ca51f6-5939-43f9-bf60-224e0eb24c52`

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

### 1. Report endpoint is too slow live

What was confirmed:

1. Direct production call to:
   - `GET /admin/pnl/profiles/{profile_id}/report?filter_mode=range&start_month=2025-12-01&end_month=2025-12-01`
   completed in about `92s`
2. Local report build against live Supabase data with the current deployed logic took about `42s`
3. Root cause is the report service paging through every ledger row for active months instead of aggregating server-side

Local fix prepared:

1. Added RPC-first aggregation path in:
   - `backend-core/app/services/pnl/report.py`
2. Added migration:
   - `20260316191000_add_monthly_pnl_report_bucket_totals_rpc.sql`
3. The service falls back to the older row-fetch path if the RPC is unavailable

### 2. December reconciliation is still not fully aligned

Important current findings:

1. Live production report before the local undeployed fix showed:
   - `marketplace_withheld_tax` as an expense, overstating expenses by about `23,491.38`
2. Local fix removes `marketplace_withheld_tax` from expense lines because it behaves like pass-through tax for this file
3. Local fix also adds:
   - `promotions_fees`
   - `Amazon Fees / Vine Enrollment Fee -> promotions_fees`
4. Even after those changes, December still does not fully match the agency manual spreadsheet

Post-fix expected December deltas versus the manual spreadsheet are roughly:

1. `product_sales`: `+1,734.53`
2. `shipping_credits`: `+35.16`
3. `total_net_revenue`: `+1,723.90`
4. `referral_fees`: `-258.68`
5. `fba_fees`: `-375.21`
6. `promotions_fees`: still `+245.00` lighter than manual
7. `total_expenses` excluding withheld tax: `-388.91`
8. `COGS` is still missing entirely in-system, so bottom-line reconciliation cannot finish yet

### 3. Supabase MCP auth is complete, but this chat session is stale

What was confirmed:

1. `codex mcp login supabase --enable rmcp_client` succeeded
2. This current chat still sees stale MCP worker state and returns:
   - `Auth required`
3. The next fresh chat should be used to test Supabase MCP first

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

1. Start in a fresh chat and test Supabase MCP immediately.
2. Read:
   - `docs/monthly_pnl_handoff.md`
   - `docs/monthly_pnl_resume_prompt.md`
   - `docs/monthly_pnl_implementation_plan.md`
3. Confirm local uncommitted P&L changes still match:
   - `backend-core/app/services/pnl/report.py`
   - `backend-core/tests/test_pnl_report.py`
   - `backend-core/tests/test_pnl_transaction_import.py`
   - `supabase/migrations/20260316190000_add_monthly_pnl_vine_fee_mapping.sql`
   - `supabase/migrations/20260316191000_add_monthly_pnl_report_bucket_totals_rpc.sql`
4. Apply the two new P&L migrations live.
5. Deploy the backend with the RPC-based report aggregation change.
6. Re-test live `GET /report` latency for Dec 2025.
7. Re-run December reconciliation against the manual spreadsheet.
8. Investigate the remaining `~1.7k` net revenue delta and `~245` promotions-fee delta.

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

The project is **past the import-recovery stage**.

What is already true:

1. real live re-import succeeded
2. stale January carryover is gone
3. import supersede flow works live for the validation profile

What is still left:

1. ship the report performance fix
2. apply the Vine/promotions mapping improvement live
3. continue December reconciliation
4. load COGS if the goal is to finish full net-earnings parity
