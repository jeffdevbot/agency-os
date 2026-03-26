# Current Handoffs

_Last updated: 2026-03-25 (ET)_

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
