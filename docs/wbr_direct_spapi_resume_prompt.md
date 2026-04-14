# WBR Direct SP-API Replacement Resume Prompt

_Last updated: 2026-04-08 (ET)_

This prompt is the restart point for the next WBR reporting-integration
project.

Current direction:

1. **Do not** start by writing migration code.
2. Start with a planning session that maps the current Windsor-backed WBR
   surfaces to direct Amazon Seller API capabilities.
3. The goal is to replace Windsor for WBR as soon as it is safe to do so,
   because Windsor is a recurring cost.
4. Manual CSV-backed Monthly P&L is already working and is **not** the active
   priority for the next session.

Continue work in `/Users/jeff/code/agency-os`.

Read first, in this order:

1. `docs/current_handoffs.md`
2. `PROJECT_STATUS.md`
3. `docs/reports_api_access_and_spapi_plan.md`
4. `docs/windsor_wbr_ingestion_runbook.md`
5. `docs/wbr_v2_schema_plan.md`
6. `README.md`
7. `AGENTS.md`

Then inspect these code paths before proposing a plan:

1. `backend-core/app/services/reports/amazon_spapi_auth.py`
2. `backend-core/app/routers/report_api_access.py`
3. `backend-core/app/services/wbr/windsor_business_sync.py`
4. `backend-core/app/services/wbr/windsor_inventory_sync.py`
5. `backend-core/app/services/wbr/windsor_returns_sync.py`
6. `backend-core/app/services/wbr/listing_imports.py`
7. `backend-core/app/services/wbr/section1_report.py`
8. `backend-core/app/services/wbr/section3_report.py`
9. `frontend-web/src/app/reports/_components/WbrSyncScreen.tsx`
10. `frontend-web/src/app/reports/_components/ReportApiAccessScreen.tsx`

Current known reality from the latest production testing:

1. Direct Seller API OAuth is now working in production.
2. Shared token storage and refresh are working.
3. `Validate` succeeds via `getMarketplaceParticipations`.
4. The finance smoke test now returns real `listFinancialEventGroups` payout
   groups for a live seller account.
5. `listTransactions` filtered by `FINANCIAL_EVENT_GROUP_ID` still returned
   `0` rows for the tested groups, even after trying:
   - `RELEASED`
   - `DEFERRED_RELEASED`
   - `DEFERRED`
   - no status filter
6. That remaining transaction-correlation question is no longer an auth
   blocker and should not distract the next session away from WBR planning.

What Windsor currently owns inside WBR:

1. Section 1 business metrics sync
   - sales / traffic by ASIN facts
2. Listings bootstrap
   - merchant listings import for child-ASIN catalog setup
3. Section 3 inventory sync
   - AFN inventory + restock recommendation blend
4. Section 3 returns sync
   - FBA customer returns feed

What direct Amazon already owns:

1. Amazon Ads auth + reporting for WBR Section 2
2. Shared Seller API auth/token storage at the client level

Primary goal for the next session:

1. Produce a **phased migration plan** for replacing Windsor in WBR while
   preserving current user-facing WBR outputs.

The first session should answer these questions clearly:

1. Which current Windsor-backed WBR surfaces can be replaced directly from the
   Seller API with the least risk?
2. Which Seller API endpoints/reports best map to:
   - Section 1 business facts
   - listings bootstrap
   - inventory snapshots
   - returns facts
3. Which parts of the current WBR data model can stay unchanged if we swap the
   ingestion source under them?
4. What should be the migration order?
5. What temporary coexistence strategy should be used so WBR remains stable
   while Windsor is being removed?
6. Which gaps, permissions, or rate-limit questions need validation before
   implementation begins?

Recommended output for that next session:

1. A written migration plan in the repo, not just chat text.
2. A source-by-source table:
   - current Windsor input
   - candidate direct Amazon replacement
   - confidence level
   - migration risk
   - open questions
3. A proposed implementation sequence with the smallest safe first slice.

Non-goals for that first session:

1. Do not replace Monthly P&L CSV imports.
2. Do not try to complete full direct-P&L parity.
3. Do not start a broad WBR schema rewrite unless the current schema truly
   cannot support direct Seller API ingestion.
4. Do not remove Windsor from production in one pass.

Suggested opener for the next Codex session:

```text
Continue work in /Users/jeff/code/agency-os.

Today’s goal is to plan the Windsor replacement for WBR using our newly
working direct Amazon Seller API access. Do not start by coding the migration.
First, read:

1. docs/current_handoffs.md
2. PROJECT_STATUS.md
3. docs/wbr_direct_spapi_resume_prompt.md
4. docs/reports_api_access_and_spapi_plan.md
5. docs/windsor_wbr_ingestion_runbook.md
6. docs/wbr_v2_schema_plan.md
7. AGENTS.md

Then inspect the current Windsor-backed WBR services and the shared Seller API
auth/report-api-access code. Produce a phased migration plan for replacing
Windsor in WBR, starting with the safest/highest-value slice. Focus on Section
1 business data, listings bootstrap, inventory, and returns. Manual CSV-backed
Monthly P&L is stable and is not the priority for this session.
```
