Continue Monthly P&L work in `agency-os`.

Read first:

1. `docs/monthly_pnl_handoff.md`
2. `docs/monthly_pnl_implementation_plan.md`
3. `PROJECT_STATUS.md`
4. `AGENTS.md`

Current reality as of March 16, 2026:

1. The December 2025 validation run is now effectively complete for the
   validation profile.
2. Validation profile:
   - `c8e854cf-b989-4e3f-8cf4-58a43507c67a`
3. Active December import is the older export used by the manual workbook:
   - import `c84cade9-6633-427f-b4b0-2371d0aca344`
   - source filename `dec2025data-olderfile.csv`
4. The stale bad `Jan 2026` carryover is gone.
5. The December UI unmapped warning is gone.
6. December report totals now match the manual workbook at report level:
   - `total_gross_revenue = 339770.20`
   - `total_refunds = -11314.14`
   - `total_net_revenue = 328456.06`
   - `total_expenses = -173735.13`
7. The major live report latency issue was fixed at the database layer by
   optimizing the `pnl_report_bucket_totals` RPC to read active month IDs first.
8. The remaining work is no longer December debugging. It is productization:
   COGS, provenance, source-drift UX, and broader validation.

Important context:

1. The newer file `/Users/jeff/Downloads/2025DecMonthlyUnifiedTransaction.csv`
   and the older workbook source do not reconcile because Amazon shifted
   settlement coverage between download dates.
2. Do not casually replace the active December import on the validation profile
   unless the user explicitly wants that.
3. The current active December data was corrected in place on 2026-03-16 for
   two residual rows after the older-file import:
   - `FBA Removal Order: Disposal Fee` -> `fba_removal_order_fees`
   - one `Refund / other = 3.60` folded into `refunds`
4. Future imports should produce the same result automatically once Render is
   serving the latest backend commits.

Relevant recent commits:

1. `280b3af` - backend report fixes and earlier December improvements
2. `fcd0f9e` - align Monthly P&L with manual workbook mappings
3. `676851d` - optimize Monthly P&L report RPC for active months
4. `586c5a9` - map remaining Monthly P&L workbook edge cases

Relevant live migrations:

1. `20260316190000_add_monthly_pnl_vine_fee_mapping.sql`
2. `20260316191000_add_monthly_pnl_report_bucket_totals_rpc.sql`
3. `20260316203000_add_monthly_pnl_manual_model_rules.sql`
4. `20260316194500_optimize_monthly_pnl_report_rpc_active_months.sql`
5. `20260316195500_fix_monthly_pnl_removal_and_refund_other_mapping.sql`

Suggested next-session task order:

1. Confirm the latest backend deploy is serving the importer/report fixes if any
   new live import testing will be done.
2. Add or design the Monthly P&L COGS path so gross profit / net earnings can
   reconcile, not just the revenue and expense sections.
3. Add import provenance to the UI:
   active filename, import timestamp, maybe import ID.
4. Decide how to communicate Amazon source-drift behavior in product/UI/docs.
5. Validate another month or profile to make sure the workbook-aligned mappings
   generalize beyond this one December case.

Deliverable expectation for the next session:

1. Do not redo December 2025 from scratch.
2. Preserve the validated live December state unless the user explicitly asks
   to replace it.
3. Move Monthly P&L from one-off debugging toward an operable workflow.
