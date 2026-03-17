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
5. CA parser compatibility changes are already in code and pushed on `main`.
6. CA global mapping rules were seeded live via
   `20260317150607_seed_monthly_pnl_ca_mapping_rules.sql`.

Primary goal:

1. Validate one real CA Monthly P&L month end to end on a live CA profile.

Focus:

1. Confirm the target CA profile and upload path in the live app/DB.
2. Run a real CA transaction export through the live Monthly P&L importer.
3. Inspect import status, active month state, unmapped totals, and report
   output.
4. Identify any remaining CA-specific rows that still need mapping changes.
5. Keep any follow-up fixes narrow and low-risk to the validated US path.

Constraints:

1. Do not disturb the validated Whoosh US 2025 state unless explicitly asked.
2. Leave unrelated dirty files alone.
3. Prefer focused parser/mapping changes over broad refactors.
