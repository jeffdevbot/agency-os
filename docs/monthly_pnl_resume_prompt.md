Continue the Monthly P&L debugging work in `agency-os`.

Read first:

1. `docs/monthly_pnl_handoff.md`
2. `docs/monthly_pnl_resume_prompt.md`
3. `docs/monthly_pnl_implementation_plan.md`
4. `PROJECT_STATUS.md`
5. `AGENTS.md`

Current reality:

1. Monthly P&L foundation, import pipeline, report service, and frontend route are built.
2. Real production re-import of the December file has already succeeded.
3. The stale bad `Jan 2026` carryover is already gone.
4. The key remaining live blocker is the report path and the remaining December reconciliation gaps.
5. The key real file is:
   - `/Users/jeff/Downloads/2025DecMonthlyUnifiedTransaction.csv`
6. Manual December 2025 numbers are in the handoff doc and should be the reconciliation target.

Important context:

1. Validation profile:
   - `c8e854cf-b989-4e3f-8cf4-58a43507c67a`
2. Latest successful live replacement import:
   - `c18a2d89-bd83-4662-86d2-d59afec26e53`
3. Local undeployed fixes now exist for:
   - report aggregation via RPC instead of paging every ledger row
   - excluding `marketplace_withheld_tax` from report expenses
   - mapping `Amazon Fees / Vine Enrollment Fee` to `promotions_fees`
4. New local migrations exist but are not applied live yet:
   - `20260316190000_add_monthly_pnl_vine_fee_mapping.sql`
   - `20260316191000_add_monthly_pnl_report_bucket_totals_rpc.sql`
5. Focused backend tests pass locally:
   - `67 passed`
6. Supabase MCP OAuth login succeeded, but the previous chat session stayed stale; start by testing Supabase MCP in this new chat.

Your task:

1. Test Supabase MCP first in this fresh chat and use it for live DB checks if available.
2. Get up to speed fast from the handoff doc.
3. Verify the local uncommitted P&L changes still match the handoff.
4. Apply the two new P&L migrations live.
5. Deploy the backend report fix.
6. Re-test live December 2025 report latency and correctness.
7. Reconcile December numbers further against the manual spreadsheet.

Guidelines:

1. Prioritize correctness over speed.
2. Do not overbuild new features.
3. Keep changes focused on Monthly P&L.
4. Use the real transaction file behavior and live SQL state as the source of truth.
5. Add/update tests for any code you change.

Expected deliverable for this session:

1. confirm Supabase MCP works in the new chat
2. apply the two pending Monthly P&L migrations live
3. deploy the backend report fix
4. get the live Dec 2025 report to return fast enough to be usable
5. December report materially closer to the manual spreadsheet
6. concise summary of:
   - root cause
   - code changes
   - migrations if any
   - residual mismatches still to reconcile
