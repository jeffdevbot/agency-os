# Monthly P&L Resume Prompt

Continue Monthly P&L work in `/Users/jeff/code/agency-os`.

Read first, in this order:

1. `docs/monthly_pnl_handoff.md`
2. `docs/monthly_pnl_implementation_plan.md`
3. `AGENTS.md`

Current reality:

1. US Amazon P&L is live and validated for Whoosh US across Jan-Dec 2025 on
   validation profile `c8e854cf-b989-4e3f-8cf4-58a43507c67a`.
2. Preserve the validated November import
   `0626222a-dc9c-4be5-a2ba-9de27b093494` and December import
   `c84cade9-6633-427f-b4b0-2371d0aca344`.
3. SKU-based COGS is live; do not revert to month-lump COGS entry.
4. WBR is a separate shipped product and not Monthly P&L scope.
5. CA transaction upload support is live and validated on real profiles:
   - Whoosh CA profile `a5faca8a-4225-4115-8510-0e6b185ee86c` is active for
     `2026-01-01` through `2026-02-01`.
   - Distex CA profile `faf4307d-80d7-4fa0-8a85-e8b805110860` is active for
     `2024-01-01` through `2026-02-01`.
6. Active CA month slices currently have `unmapped_amount = 0`.
7. CA mapping migrations already live:
   - `20260317150607_seed_monthly_pnl_ca_mapping_rules.sql`
   - `20260317154748_add_monthly_pnl_fulfilment_removal_prefix_rule.sql`
   - `20260317161435_add_monthly_pnl_ca_label_variants.sql`
8. Async import progress/heartbeat UX is live, and SKU-based COGS now supports
   CSV export/import in the settings card.
9. `Other expenses` is now live in Monthly P&L settings:
   - manual monthly `FBM Fulfillment Fees`
   - manual monthly `Agency Fees`
   - show/hide toggles
   - CSV export/import
10. Live migration `20260317165228_add_monthly_pnl_other_expenses.sql` is
    already applied in Supabase.
11. Excel export is live, with `Dollars` and `% of Revenue` tabs.
12. Payout rows are live at the bottom of the report, sourced from
    `non_pnl_transfer`.
13. Current P&L UI/workbook formatting uses accounting-style negatives with
    brackets, and the UI now shows whole-number display values.

Primary goal:

1. Work on Monthly P&L and explore the remaining implementation-plan items with
   the user to decide what should come next.

Focus:

1. Review the current shipped Monthly P&L state first.
2. Review the remaining items in `docs/monthly_pnl_implementation_plan.md` and
   discuss with the user what the next highest-value Monthly P&L work should be.
3. Preserve validated Whoosh US and the currently active CA imports unless the
   user explicitly wants to replace them.
4. Prefer focused, low-risk follow-up work over broad refactors.
5. Keep Windsor settlement work out of scope unless it becomes the explicit
   next product goal.

Constraints:

1. Do not disturb the validated Whoosh US 2025 state unless explicitly asked.
2. Leave unrelated dirty files alone.
3. Prefer focused parser/mapping changes over broad refactors.
