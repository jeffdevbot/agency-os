# Current Handoffs

_Last updated: 2026-03-27 (ET)_

Use this file to decide which restart/handoff docs are current versus merely
historical reference.

## Active next-session entrypoints

1. [Claude primary surface plan](/Users/jeff/code/agency-os/docs/claude_primary_surface_plan.md)
   - Current strategy doc for Claude vs The Claw and future MCP expansion.
2. [Agency OS MCP implementation plan](/Users/jeff/code/agency-os/docs/agency_os_mcp_implementation_plan.md)
   - Current implementation-planning reference for the shared Claude/MCP tool
     surface after WBR + Monthly P&L shipped.
3. [Reports API access and SP-API plan](/Users/jeff/code/agency-os/docs/reports_api_access_and_spapi_plan.md)
   - Current shared reporting auth/source-of-truth planning reference.
4. [PROJECT_STATUS.md](/Users/jeff/code/agency-os/PROJECT_STATUS.md)
   - Fastest high-level snapshot of what is already shipped.

## Current operational/reference docs

1. [WBR schema plan](/Users/jeff/code/agency-os/docs/wbr_v2_schema_plan.md)
   - Current schema/reference document for WBR v2.
2. [Windsor WBR ingestion runbook](/Users/jeff/code/agency-os/docs/windsor_wbr_ingestion_runbook.md)
   - Narrow operational runbook for Windsor Section 1 ingestion.
3. [Claude Project bundle](/Users/jeff/code/agency-os/docs/claude_project/README.md)
   - Current project instructions/files bundle for the live shared WBR +
     Monthly P&L + ClickUp Claude surface.
4. [Monthly P&L handoff](/Users/jeff/code/agency-os/docs/monthly_pnl_handoff.md)
   - Current shipped-state reference for Monthly P&L, Claude P&L, and YoY.
5. [Monthly P&L resume prompt](/Users/jeff/code/agency-os/docs/monthly_pnl_resume_prompt.md)
   - Current restart prompt if a future session returns specifically to
     Monthly P&L.
6. [Team Hours plan / current state](/Users/jeff/code/agency-os/docs/team_hours_plan.md)
   - Current implementation reference for the shipped Team Hours surface under
     Command Center.
7. [Forecasting v1 plan](/Users/jeff/code/agency-os/docs/forecasting_v1_plan.md)
   - Current planning document for the next forecasting surface under Reports.
8. [Claude ClickUp tools plan](/Users/jeff/code/agency-os/docs/claude_clickup_tools_plan.md)
   - Slice 0–4 implemented and live, plus follow-on `update_clickup_task`.
     Current shipped ClickUp MCP tools: `list_clickup_tasks`,
     `get_clickup_task`, `update_clickup_task`, `resolve_team_member`,
     `prepare_clickup_task`, `create_clickup_task`. `get_clickup_task` now
     scopes fetches to mapped Agency OS brand destinations (workspace guard).
     Open follow-ups: broader task update/close/move flows, idempotency.
9. [Opportunity backlog](/Users/jeff/code/agency-os/docs/opportunity_backlog.md)
   - Lightweight priority list for next product/platform opportunities.
10. [Supabase Python client upgrade plan](/Users/jeff/code/agency-os/docs/supabase_python_client_upgrade_plan.md)
   - Tonight-review reference for the backend Supabase dependency warning,
     upgrade scope, and the explicit non-goal of forcing Amazon Ads or Windsor
     re-auth.
11. [Search term automation plan](/Users/jeff/code/agency-os/docs/search_term_automation_plan.md)
   - Current phased planning doc for richer catalog context expansion plus the
     current STR implementation / AI review / direct Amazon writeback roadmap
     for the current N-Gram / N-PAT workflow.
12. [Claude tool budget plan](/Users/jeff/code/agency-os/docs/claude_tool_budget_plan.md)
   - Current sizing reference for the live MCP tool surface, Claude Project
     file bundle, and the recommended safe expansion budget for future analyst
     query tools.
13. [Claude analyst query tools plan](/Users/jeff/code/agency-os/docs/claude_analyst_query_tools_plan.md)
   - Current implementation-planning doc for the next read-only analyst-query
     MCP expansion beyond WBR / Monthly P&L / ClickUp.

## Current operational notes

1. Supabase MCP auth was re-established locally on 2026-03-23 (ET):
   - `codex mcp logout supabase`
   - `codex mcp login supabase`
   - `codex mcp list` recovered and now shows `supabase` with `Auth = OAuth`
   - if an existing Codex session still reports `Auth required` when using the
     Supabase MCP, treat that as stale session state and start a fresh Codex
     session before concluding the MCP is broken
2. Monthly P&L active debugging focus as of 2026-03-24 (ET):
   - next session should start with the remaining **US P&L unmapped
     transactions**
   - the current Monthly P&L handoff/prompt have been updated to reflect the
     recent Lifestyle CA inbound-carrier rule gap and the exact Supabase MCP
     caveat above
3. WBR Amazon Ads Lifestyle triage update as of 2026-03-25 (ET):
   - Lifestyle US remains the confirmed wrong-profile case that was fixed by
     re-selecting the correct advertiser profile
   - Lifestyle CA was rechecked against a March 16 Amazon campaign export, and
     the live DB matched the export exactly for both spend (`80.37 CAD`) and
     sales (`267.58 CAD`)
   - that dedicated triage thread is now historical/reference rather than the
     primary active WBR restart path
4. Supabase Python client warning follow-up as of 2026-03-26 (ET):
   - the current backend warning is from the older `supabase==2.6.0` Python
     dependency chain still pulling `gotrue`
   - the Claude MCP auth work this week was OAuth/JWKS compatibility, not a
     Python client migration
   - the tracked upgrade follow-up should not require mass re-auth of Amazon
     Ads or Windsor accounts because those credentials are stored in database
     rows
5. Search Term Automation current state as of 2026-03-27 (ET):
   - Stage 1 `Search Term Automation` controls are live on
     `/reports/client-data-access/[clientSlug]`
   - Stage 2 `Search Term Data` is live on
     `/reports/search-term-data/[clientSlug]`
   - STR ingestion was refactored away from inherited WBR campaign-sync
     assumptions and now uses an Amazon Ads-native contract for the verified
     `spSearchTerm` path
   - current supported scope is **Sponsored Products only**; SB / SD remain
     intentionally unverified / unsupported until their exact report contracts
     are confirmed
   - `search_term_daily_facts` now preserves `keyword_id`, `keyword`,
     `keyword_type`, and `targeting`
   - STR UI now auto-refreshes every 15 seconds while runs are in `running`
     state, mirroring the WBR Ads sync experience
   - post-worker-redeploy live validation is now confirmed on a real Whoosh US
     Sponsored Products backfill:
     - three successful chunks covering `2026-03-01` through `2026-03-26`
     - `search_term_daily_facts` loaded `10,436` SP rows with the expected
       keyword/targeting shape
     - a real Amazon Ads Sponsored Products search-term CSV for
       `2026-03-01` through `2026-03-10` matched the stored DB totals
       essentially exactly (`410,267` export impressions vs `410,261` in DB;
       clicks / spend / orders / sales matched)
   - do not compare STR facts to broader Sponsored Products Campaign Manager
     totals when validating impressions:
     - Amazon search-term exports appear to include only search terms that
       generated at least one click
     - broader SP console totals can therefore show materially higher
       impressions than STR facts while clicks / spend / sales still line up
   - legacy Pacvue "search term report" files can contain mixed `SP`, `SB`,
     and `SD` rows in one export:
     - that mixed Pacvue shape is useful for understanding the old workflow
     - it is **not** evidence that Amazon-native `SP`, `SB`, and `SD` use the
       same report family or should share one implementation contract
   - pre-worker-redeploy STR runs remain untrustworthy validation evidence
6. Supabase MCP local auth restart note:
   - if Supabase MCP tools are unavailable in a Codex session, run:
     `codex mcp logout supabase`
   - then:
     `codex mcp login supabase`
   - confirm with:
     `codex mcp list`
   - then start a fresh Codex session if the current one still behaves as if
     Supabase auth is missing

## Historical/reference docs

1. [WBR v2 handoff](/Users/jeff/code/agency-os/docs/wbr_v2_handoff.md)
   - Historical shipped-state/debug reference for WBR.
   - WBR is stable for now; this is no longer the primary restart doc.
2. [WBR Ads profile triage handoff](/Users/jeff/code/agency-os/docs/wbr_ads_profile_triage_handoff.md)
   - Historical/reference record for the resolved Lifestyle US/CA Amazon Ads
     triage thread, including the March 25 CA export-vs-DB validation.
3. [WBR Ads profile triage resume prompt](/Users/jeff/code/agency-os/docs/wbr_ads_profile_triage_resume_prompt.md)
   - Historical restart prompt for that resolved triage thread if a new
     discrepancy appears later.
4. [PnL YoY implementation plan](/Users/jeff/code/agency-os/docs/pnl_yoy_implementation_plan.md)
   - Historical implementation record for the now-shipped YoY architecture.
5. [Archived session prompts](/Users/jeff/code/agency-os/docs/archive/session_prompts)
   - Historical prompts from active build/debug phases.
6. [Older archived non-The-Claw docs](/Users/jeff/code/agency-os/docs/archive/non_agencyclaw/README.md)
   - Historical product/build docs no longer meant to be the active entrypoint.

## Rule of thumb

1. Treat code as the canonical current state.
2. Use handoff docs only when they add operational context, validation notes,
   or restart guidance that code alone does not show.
3. When a workstream becomes stable, demote its handoff docs into historical or
   reference status instead of treating them as evergreen restart docs.
