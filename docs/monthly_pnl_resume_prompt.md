# Monthly P&L Resume Prompt

_Last updated: 2026-03-23 (ET)_

This prompt is no longer the default "active build" entrypoint. Monthly P&L,
Claude P&L, and the YoY web surface are now shipped. Use this prompt only when
returning to Monthly P&L for refinement, debugging, or the next adjacent
capability.

Continue Monthly P&L work in `/Users/jeff/code/agency-os`.

Read first, in this order:

1. `docs/current_handoffs.md`
2. `docs/monthly_pnl_handoff.md`
3. `docs/monthly_pnl_email_drafting_spec.md`
4. `docs/monthly_pnl_implementation_plan.md`
5. `docs/agency_os_mcp_implementation_plan.md`
6. `docs/claude_primary_surface_plan.md`
7. `docs/reports_api_access_and_spapi_plan.md`
8. `docs/monthly_pnl_windsor_reconciliation.md`
9. `AGENTS.md`

Current reality:

1. US Amazon P&L is live and validated for Whoosh US across Jan-Dec 2025 on
   validation profile `c8e854cf-b989-4e3f-8cf4-58a43507c67a`.
2. Preserve the validated November import
   `0626222a-dc9c-4be5-a2ba-9de27b093494` and December import
   `c84cade9-6633-427f-b4b0-2371d0aca344`.
3. SKU-based COGS is live; do not revert to month-lump COGS entry.
4. WBR is a separate shipped product and not Monthly P&L scope. The WBR Claude
   MCP pilot is working and hardened enough that Monthly P&L is now the most
   logical next Claude capability.
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
14. The current strategic direction is no longer “keep all auth/report-source
    work inside WBR or Windsor.” The reviewed plan is:
    - shared `Reports / API Access`
    - Amazon Ads connection management moved there
    - Amazon Seller API auth added there
    - P&L-first direct-SP-API follow-up after auth exists
15. `Reports / API Access` Passes 1-4 are now implemented and deployed:
    - shared `report_api_connections` storage is live
    - `/reports/api-access` is live
    - Amazon Ads connection visibility/launch moved there
    - Amazon Seller API auth/validate/finance-smoke scaffolding is live
16. Region-aware SP-API routing is implemented for `NA`, `EU`, and `FE`.
17. Connection health/status semantics are hardened:
    - shared connections only count as healthy when
      `connection_status = 'connected'`
    - WBR Amazon Ads falls back to legacy storage if a shared Ads connection is
      present but unhealthy
18. WBR Windsor flows and manual Monthly P&L CSV upload mode were not replaced
    by this work and should still be treated as the active stable paths.
19. The current blocker is Amazon app-side approval/configuration, not code:
    - seller auth reached Amazon successfully
    - draft auth required `AMAZON_SPAPI_DRAFT_APP=true`
    - Amazon then returned `MD9100`, indicating missing Login URI /
      Redirect URI config on the SP-API app
    - the user has applied for public app approval and paused work pending
      Amazon response
20. Render/frontend stability note:
    - frontend Node runtime is now pinned to `20.19.0`
    - repo files:
      - `frontend-web/package.json`
      - `frontend-web/.node-version`
21. Current review of the P&L codepath indicates the report already behaves
    like a curated monthly snapshot set:
    - `PNLReportService` reads persisted month-level import tables
    - only `monthly_pnl_import_months.is_active = true` slices are included
    - report totals are rebuilt at query time from persisted
      `monthly_pnl_import_month_bucket_totals`, SKU unit summaries, SKU COGS,
      and manual expense rows
22. The first read-only Claude/P&L MCP slice is now implemented in code:
    - shared client discovery lives in
      `backend-core/app/mcp/tools/clients.py`
    - `resolve_client` now resolves against Command Center client data and
      includes:
      - WBR marketplace coverage
      - Monthly P&L marketplace coverage
      - brands / ClickUp destination hints
      - team assignments
      - client context fields
    - P&L read-only MCP tools now include:
      - `list_monthly_pnl_profiles`
      - `get_monthly_pnl_report`
      - `get_monthly_pnl_email_brief`
    - P&L mutating MCP tool now includes:
      - `draft_monthly_pnl_email`
23. The intended product shape is still one shared Agency OS Claude Project
    that can use multiple Agency OS tool domains. Do not assume one separate
    Claude Project per report type.
24. The shared Claude Project bundle has now been extended locally for P&L:
    - `docs/claude_project/project_instructions.md`
    - `docs/claude_project/wbr_mcp_playbook.md`
    - `docs/claude_project/monthly_pnl_mcp_playbook.md`
25. Claude-side smoke testing is complete and currently green:
    - shared `resolve_client` works
    - WBR flows still work
    - P&L analysis works
    - P&L brief generation works
    - P&L draft generation works
26. Targeted regression coverage after the MCP/P&L changes is currently green:
    - `backend-core/tests/test_mcp_pilot.py`
    - `backend-core/tests/test_pnl_report.py`
    - `backend-core/tests/test_pnl_workbook.py`
27. The first P&L email-drafting design pass is now written in:
    - `docs/monthly_pnl_email_drafting_spec.md`
    It captures:
    - the extracted writing pattern from real manual P&L emails
    - the recommended Claude-facing preview/persisted tool contract
    - the exact data requirements, including conditional YoY handling
28. The first structured P&L email-brief layer is now implemented in code:
    - backend service:
      `backend-core/app/services/pnl/email_brief.py`
    - MCP tool:
      `get_monthly_pnl_email_brief`
    - current role:
      - read-only bridge between raw P&L analysis and future P&L email drafting
      - deterministic monthly brief with YoY/MoM fallback, snapshot metrics,
        driver candidates, verdict, and data-quality notes
29. The first persisted P&L email draft layer is now implemented on top of the
    brief:
    - services:
      - `backend-core/app/services/pnl/email_prompt.py`
      - `backend-core/app/services/pnl/email_drafts.py`
    - MCP tool:
      - `draft_monthly_pnl_email`
    - persistence migration:
      - `supabase/migrations/20260323170000_add_monthly_pnl_email_drafts.sql`

30. Monthly P&L YoY is now shipped as a real web product surface:
    - shared backend comparison layer:
      `backend-core/app/services/pnl/comparison.py`
    - thin YoY adapter:
      `backend-core/app/services/pnl/yoy_report.py`
    - YoY route:
      `GET /admin/pnl/profiles/{profile_id}/yoy-report`
    - frontend YoY mode:
      - `Standard` / `YoY` toggle
      - year selector
      - `% of Revenue` support in YoY
      - dashed prior-year chart series
      - YoY Excel export
31. Claude does not yet have a dedicated YoY MCP tool, and that is currently
    intentional:
    - Claude can already reason about YoY using existing P&L tools
    - the shared comparison layer is the future base if a thin YoY MCP tool is
      ever justified

Primary goal for a future return:

1. Treat Monthly P&L as shipped and start from refinement/debugging or the
   next adjacent capability, not from "build the first Claude/P&L slice."

Focus:

1. Review the current shipped Monthly P&L state first.
2. Review the remaining items in `docs/monthly_pnl_implementation_plan.md`,
   but frame the conversation around post-ship refinement or the next adjacent
   capability rather than first-slice build work.
3. Inspect the existing report path before adding persistence or wrappers:
   - `backend-core/app/services/pnl/report.py`
   - `backend-core/app/routers/pnl.py`
4. Preserve validated Whoosh US and the currently active CA imports unless the
   user explicitly wants to replace them.
5. Prefer focused, low-risk follow-up work over broad refactors.
6. Treat Windsor compare as a reconciliation/debug aid, not the long-term
   financial-source direction.
7. If the user pivots to direct Amazon SP-API financial integration, treat
   that as a separate P&L-first follow-up path rather than the assumed next
   step for Claude.
8. Do not fragment the Claude Project into separate per-report bundles unless
   there is a strong product reason. The current direction is one shared
   Agency OS Project with WBR and Monthly P&L guidance separated cleanly inside
   that bundle.
9. For Monthly P&L email drafting, do not reuse the old screenshot/OCR prompt
   shape. Use structured Agency OS report data as the source of truth and apply
   YoY only when prior-year comparables are actually available.

Constraints:

1. Do not disturb the validated Whoosh US 2025 state unless explicitly asked.
2. Leave unrelated dirty files alone.
3. Prefer focused parser/mapping changes over broad refactors.
4. Do not re-open architecture already validated in production unless real
   usage justifies it.

Current direct-Amazon notes:

1. Render env var naming chosen for SP-API work:
   - `AMAZON_SPAPI_LWA_CLIENT_ID`
   - `AMAZON_SPAPI_LWA_CLIENT_SECRET`
   - `AMAZON_SPAPI_APP_ID`
2. Temporary draft-app env used during testing:
   - `AMAZON_SPAPI_DRAFT_APP=true`
3. A seller-authorized refresh token is still required for Finances API calls.
4. For the current deployed auth flow, Amazon app config should include:
   - Login URI: `https://tools.ecomlabs.ca/reports/api-access`
   - Redirect URI: `https://backend-core-re6d.onrender.com/amazon-spapi/callback`
   - optional additional redirect URI:
     `https://backend-core-re6d.onrender.com/api/amazon-spapi/callback`
5. Long-term, refresh tokens should be stored per seller/profile in the
   database rather than as one global env var.
6. For a new build session, the reviewed source-of-truth design doc is:
   - `docs/reports_api_access_and_spapi_plan.md`

Docs currently known to be partially outdated for this new direction:

1. `docs/wbr_v2_handoff.md` (historical/reference)
2. `docs/wbr_v2_schema_plan.md`
3. `docs/db/schema_master.md`

Those docs still describe Amazon Ads auth/storage as WBR-owned and do not yet
reflect the shared `Reports / API Access` plan.
