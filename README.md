# Ecomlabs Tools (formerly “Agency OS”)

Ecomlabs Tools is the internal platform that consolidates our ad analytics, SOP ops, content creation, and creative briefing into a single authenticated dashboard at `tools.ecomlabs.ca`. The `docs/` folder captures the architecture, PRDs, and migration plans that guide the implementation. “Agency OS” was the internal codename; use “Ecomlabs Tools” in user-facing copy.

## Current milestone

The Jeff-only Claude Pro remote MCP pilot is now live as a shared WBR +
Monthly P&L + ClickUp surface, and the ClickUp slice is now in real pilot
testing.

Current live outcome:
- Claude web can authenticate to the private `Agency OS` connector through Supabase OAuth.
- Claude can call the live shared reporting tool belt against Agency OS data:
  - `resolve_client`
  - `list_wbr_profiles`
  - `get_wbr_summary`
  - `draft_wbr_email`
  - `list_monthly_pnl_profiles`
  - `get_monthly_pnl_report`
  - `get_monthly_pnl_email_brief`
  - `draft_monthly_pnl_email`
  - `list_clickup_tasks`
  - `get_clickup_task`
  - `resolve_team_member`
  - `prepare_clickup_task`
  - `create_clickup_task`
  - `update_clickup_task`
- A compact Claude Project bundle now lives in `docs/claude_project/` so the pilot can use durable project instructions and narrow reference files instead of large planning docs, and that bundle now includes ClickUp guidance alongside WBR and Monthly P&L.
- WBR snapshot freshness is now tied to the sync lifecycle and backed by a stale-snapshot self-heal on read, so the Claude/The Claw path no longer depends on an old stored digest lingering after newer Windsor/Amazon Ads refreshes.
- Monthly P&L now supports:
  - read-only analysis in Claude
  - structured P&L email brief generation in Claude
  - persisted Monthly P&L email drafting in Claude
  - a shipped `Standard` / `YoY` web reporting mode with `% of Revenue`,
    dual-series charting, and YoY Excel export
- Monthly P&L YoY currently uses the shared backend comparison layer in the web
  app. Claude does not yet have a dedicated YoY MCP tool, but it can still do
  YoY reasoning with the existing P&L tool surface.
- ClickUp now supports:
  - mapped backlog task review in Claude
  - direct mapped task-link inspection in Claude
  - conversational assignee resolution in Claude
  - preview-before-create task flow in Claude
  - real ClickUp task creation in Claude
  - real ClickUp task editing in Claude

This does **not** replace The Claw in Slack. The current surface split is:
- **The Claw in Slack** for quick operational requests.
- **Claude.ai + Agency OS integration** for higher-capability WBR and analyst-style workflows.

## Documentation map

### Core Architecture
- `docs/archive/non_agencyclaw/00_agency_os_architecture.md` — master architecture: Render services (`frontend-web`, `backend-core`, `worker-sync`), Supabase auth, and the migration path off of `ngram.ecomlabs.ca`. Notes the “Agency OS” codename but current branding is Ecomlabs Tools.
- `docs/archive/non_agencyclaw/01_ngram_migration.md` — the "Split and Lift" plan for porting the existing Ngram analyzer into the Ecomlabs Tools frontend/backend pattern.

### Shipped Tools (Web UI)
- **N-Gram Processor** — `/ngram` (two-step flow: generate workbook, then upload filled workbook to download a formatted negatives summary).
- **N-Gram 2.0** — `/ngram-2` (Agency OS search-term workbook generation plus optional AI triage preview. Current direction is analyst-leverage review: `SAFE KEEP` / `LIKELY NEGATE` / `REVIEW` guidance with rationale, while analysts keep final `NE/NP` and gram decisions). Current docs: `docs/ngram_2_pure_prompt_pivot_plan.md`, `docs/ngram_2_ui_cleanup_plan.md`, `docs/ngram_2_ai_prefill_design.md`, `docs/search_term_automation_resume_prompt.md`.
- **N-PAT (Negative Product Attribute Targeting)** — `/npat` (ASIN-only inverse of N-Gram with Helium10 enrichment). Specs: `docs/archive/non_agencyclaw/03_npat_prd.md`, plan: `docs/archive/non_agencyclaw/03_npat_plan.md`.
- **AdScope** — `/adscope` (Amazon Ads audit workspace: upload Bulk + STR; views + chat). Specs: `docs/archive/non_agencyclaw/20_adscope_prd.md`; Amazon export file reference: `docs/archive/non_agencyclaw/21_adscope_schema.md`; live DB schema: `docs/db/schema_master.md`.
- **Scribe** — `/scribe` (Amazon listing copy generation: project → SKUs → topics → copy). Current specs live under `docs/archive/non_agencyclaw/scribe_lite/`.
- **Root Keyword Analysis** — `/root-keywords` (4-week hierarchical campaign rollup). Specs: `docs/archive/non_agencyclaw/18_root_keyword_analysis_prd.md`, plan: `docs/archive/non_agencyclaw/19_root_keyword_analysis_plan.md`.
- **WBR** — `/reports/[clientSlug]/[marketplaceCode]/wbr` (client/marketplace weekly business review workspace with live Section 1 Windsor business reporting, live Section 2 Amazon Ads reporting, live Section 3 inventory + returns reporting, section tabs, inline trend charts for Sections 1 and 2, Excel export, sync QA, nightly refresh controls, and queued/background Ads backfills via `worker-sync`). Current reference docs: `docs/wbr_v2_schema_plan.md` and `docs/windsor_wbr_ingestion_runbook.md`; historical shipped-state context: `docs/wbr_v2_handoff.md`; older WBR planning docs are archived.
- **Monthly P&L** — `/reports/[clientSlug]/[marketplaceCode]/pnl` finance reporting surface built from uploaded Amazon transaction reports, with a separate import pipeline, normalized ledger model, month-slice activation, active-import provenance, async/background processing, SKU-based COGS management, manual `Other expenses` rows for items such as `FBM Fulfillment Fees` and `Agency Fees`, dual-mode `% of Revenue` reporting, Excel export, payout visibility from transfer rows, and a shipped `Standard` / `YoY` mode backed by a shared comparison layer. Current live rollout covers validated Whoosh US 2025 plus live CA transaction-report profiles for Whoosh and Distex. Current state docs: `docs/monthly_pnl_handoff.md`, `docs/monthly_pnl_resume_prompt.md`, `docs/monthly_pnl_implementation_plan.md`, `docs/pnl_yoy_implementation_plan.md`; older one-off prompts are archived.
- **Command Center (MVP)** — `/command-center` (admin-only directory for clients, brands, role slots, team roster, Ghost Profiles merge-on-login, and links into the ClickUp admin/reporting surfaces). Specs: `docs/archive/non_agencyclaw/07_command_center_prd.md`, API: `docs/archive/non_agencyclaw/07_command_center_schema_api.md`, live DB schema: `docs/db/schema_master.md`.
- **Team Hours** — `/command-center/hours` (admin-only ClickUp time reporting with date-range filtering, Team Members / Clients views, search, stacked daily charts, unmapped user/space cleanup sections, deep links back into Command Center, and CSV export of the current view). Current implementation reference: `docs/team_hours_plan.md`.
- **Debrief (MVP)** — `/debrief` (admin-only; sync Meet “Notes by Gemini” into Supabase; manually extract tasks; edit/remove; send to ClickUp once IDs are mapped). Specs: `docs/archive/non_agencyclaw/debrief_prd.md`, plan: `docs/archive/non_agencyclaw/debrief_implementation_plan.md`.

### Shipped Services (Internal / No UI)
- **ClickUp Service (backend-core)** — shared backend integration layer for ClickUp API calls (task creation + future sync). Routes live under `backend-core/app/routers/clickup.py`. Spec: `docs/archive/non_agencyclaw/08_clickup_service_prd.md`.
- **Agency OS MCP (Jeff-only pilot)** — private remote MCP server mounted from `backend-core` and currently exposed to Claude Pro for shared WBR + Monthly P&L + ClickUp workflows. Current live tool belt: `resolve_client`, `list_wbr_profiles`, `get_wbr_summary`, `draft_wbr_email`, `list_monthly_pnl_profiles`, `get_monthly_pnl_report`, `get_monthly_pnl_email_brief`, `draft_monthly_pnl_email`, `list_clickup_tasks`, `get_clickup_task`, `resolve_team_member`, `prepare_clickup_task`, `create_clickup_task`, and `update_clickup_task`. WBR freshness is sync-backed and self-healing on read; Monthly P&L analysis, briefing, and drafting are live; ClickUp backlog review / task inspection / preview / create / edit are now live and in pilot testing. Primary docs: `docs/claude_primary_surface_plan.md`, `docs/agency_os_mcp_implementation_plan.md`, and the compact Claude Project bundle in `docs/claude_project/`.

### In Flight / Upcoming
- **The Claw** — Slack assistant reboot for agency operations. Current plan/docs: `docs/theclaw/current/01_theclaw_reboot_implementation_plan.md`, `docs/theclaw/current/02_theclaw_architecture.md`.
- **Historical docs (non-The-Claw)** — archived at `docs/archive/non_agencyclaw/` (index: `docs/archive/non_agencyclaw/README.md`).
- More tools planned; follow the docs folder for new PRDs and plans as they land.

### Database Schema
- `docs/db/schema_master.md` — Canonical live Supabase schema snapshot (generated).
- `docs/db/README.md` — Schema docs policy + regeneration workflow.

### Dev Operations
- `docs/current_handoffs.md` — single index for which handoff/restart docs are current versus historical/reference.
- `docs/mcp_setup.md` — MCP workspace setup and verification (Supabase MCP server config, read-only connectivity checks, and `401 Unauthorized` re-auth recovery).
- `docs/claude_project/` — compact Claude Project setup bundle for the live shared WBR + Monthly P&L + ClickUp Claude surface, including project instructions and narrow playbooks for upload into Claude Projects.
- `docs/windsor_wbr_ingestion_runbook.md` — Windsor Section 1 ingestion operations for WBR (account scoping, date windows, sync behavior, and batching strategy).
- `docs/wbr_v2_schema_plan.md` — WBR schema/reference plan annotated with current implementation status, live migrations, and the current sync-run/job-state notes.
- `docs/wbr_v2_handoff.md` — historical WBR shipped-state/debug reference; no longer the default restart doc now that WBR is stable for the moment.
- `docs/monthly_pnl_handoff.md` — Current Monthly P&L shipped/debugged state, including Claude P&L and YoY shipped status.
- `docs/monthly_pnl_resume_prompt.md` — Current restart prompt for a future Monthly P&L refinement/debugging session.
- `docs/monthly_pnl_implementation_plan.md` — Monthly P&L implementation plan and mapping/reconciliation reference, annotated with the currently shipped state.
- `docs/pnl_yoy_implementation_plan.md` — Implementation record for the shipped YoY comparison architecture.
- `docs/archive/session_prompts/` — Historical restart prompts that were useful during active build/debug sessions but are no longer the primary docs entrypoint.

### Other Specs
- `docs/archive/non_agencyclaw/05_creative_brief_prd.md` — Creative Brief tool that maps Composer copy + uploaded assets into designer-ready storyboards.

### Deprecated
- `docs/archive/non_agencyclaw/04_amazon_composer_prd.md` — **[DEPRECATED]** Amazon listing composer. **Replaced by Scribe.** Code will be removed after Scribe stabilizes.
- `docs/archive/non_agencyclaw/02_the_operator_prd.md` — **[DEPRECATED]** The Operator concept PRD (superseded by Debrief + ClickUp Service).

Each doc includes the UX and backend contracts for its domain. Use `docs/db/schema_master.md` as the canonical schema reference, and update docs before or alongside code changes that affect scope or interfaces.

## Next steps for contributors

1. Read the architecture overview to internalize the Render + Supabase stack and auth flow.
2. Pick the relevant PRD for the feature you plan to build and translate its requirements into issues/tasks.
3. Keep docs and implementation in lockstep—when APIs, data models, or flows change, edit the corresponding doc so future contributors have a single source of truth.

## Service Architecture

| Service | Type | Purpose |
|---------|------|---------|
| `frontend-web` | Next.js | Web UI at tools.ecomlabs.ca |
| `backend-core` | FastAPI | API endpoints, integrations |
| `worker-sync` | Background | Render background worker for nightly WBR refresh jobs plus long-running Monthly P&L async imports and future sync work |

All services are deployed on Render. See `docs/archive/non_agencyclaw/00_agency_os_architecture.md` for details.

## The Claw (Slack Assistant)

The Claw is the rebooted Slack assistant for agency operations.

Current state:
- Slack runtime is simplified and LLM-first.
- Focus is reliability and progressive skill rollout, starting with basic DM assistance.
- Legacy Slack runtime and test surface have been removed.

Current Slack entrypoints:
- `backend-core/app/api/routes/slack.py` (`/api/slack/events`, `/api/slack/interactions`)

Primary docs:
- `docs/theclaw/current/01_theclaw_reboot_implementation_plan.md`
- `docs/theclaw/current/02_theclaw_architecture.md`

## Local quickstarts

### Debrief (Google Drive ingestion)
- Configure (local): `frontend-web/.env.local` with `GOOGLE_SERVICE_ACCOUNT_JSON`, `GOOGLE_IMPERSONATION_EMAIL`, `GOOGLE_MEET_FOLDER_ID`.
- Smoke test Drive access: `npm -C frontend-web run debrief:list-drive`.

## UI / Design language (Ecomlabs Tools)

This repo’s UI uses Next.js + Tailwind with a consistent “clean SaaS” look:
- **Typography:** Geist Sans + Geist Mono (see `frontend-web/src/app/layout.tsx`).
- **Color:** primary blue accents (commonly `#0a6fd6` / `#0959ab`) over slate neutrals (`#0f172a`, `#4c576f`, `#e2e8f0`).
- **Layout:** light gradients for landing surfaces; white, rounded cards with soft shadows; generous padding and clear hierarchy.
- **Components:** pill/rounded buttons (`rounded-2xl`), large surface cards (`rounded-3xl bg-white/95 backdrop-blur shadow-[...]`), subtle borders, concise helper text.
