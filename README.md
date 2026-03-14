# Ecomlabs Tools (formerly “Agency OS”)

Ecomlabs Tools is the internal platform that consolidates our ad analytics, SOP ops, content creation, and creative briefing into a single authenticated dashboard at `tools.ecomlabs.ca`. The `docs/` folder captures the architecture, PRDs, and migration plans that guide the implementation. “Agency OS” was the internal codename; use “Ecomlabs Tools” in user-facing copy.

## Documentation map

### Core Architecture
- `docs/archive/non_agencyclaw/00_agency_os_architecture.md` — master architecture: Render services (`frontend-web`, `backend-core`, `worker-sync`), Supabase auth, and the migration path off of `ngram.ecomlabs.ca`. Notes the “Agency OS” codename but current branding is Ecomlabs Tools.
- `docs/archive/non_agencyclaw/01_ngram_migration.md` — the "Split and Lift" plan for porting the existing Ngram analyzer into the Ecomlabs Tools frontend/backend pattern.

### Shipped Tools (Web UI)
- **N-Gram Processor** — `/ngram` (two-step flow: generate workbook, then upload filled workbook to download a formatted negatives summary).
- **N-PAT (Negative Product Attribute Targeting)** — `/npat` (ASIN-only inverse of N-Gram with Helium10 enrichment). Specs: `docs/archive/non_agencyclaw/03_npat_prd.md`, plan: `docs/archive/non_agencyclaw/03_npat_plan.md`.
- **AdScope** — `/adscope` (Amazon Ads audit workspace: upload Bulk + STR; views + chat). Specs: `docs/archive/non_agencyclaw/20_adscope_prd.md`; Amazon export file reference: `docs/archive/non_agencyclaw/21_adscope_schema.md`; live DB schema: `docs/db/schema_master.md`.
- **Scribe** — `/scribe` (Amazon listing copy generation: project → SKUs → topics → copy). Current specs live under `docs/archive/non_agencyclaw/scribe_lite/`.
- **Root Keyword Analysis** — `/root-keywords` (4-week hierarchical campaign rollup). Specs: `docs/archive/non_agencyclaw/18_root_keyword_analysis_prd.md`, plan: `docs/archive/non_agencyclaw/19_root_keyword_analysis_plan.md`.
- **Reports (WBR v2)** — `/reports` (client/marketplace WBR workspace with Section 1 Windsor sync/reporting, Section 2 Amazon Ads sync/reporting, sync QA, and nightly refresh controls). Current state docs: `docs/wbr_v2_handoff.md`, `docs/wbr_v2_schema_plan.md`; Windsor ops runbook: `docs/windsor_wbr_ingestion_runbook.md`.
- **Command Center (MVP)** — `/command-center` (admin-only; clients → brands → role slots; team roster; Ghost Profiles merge-on-login). Specs: `docs/archive/non_agencyclaw/07_command_center_prd.md`, API: `docs/archive/non_agencyclaw/07_command_center_schema_api.md`, live DB schema: `docs/db/schema_master.md`.
- **Debrief (MVP)** — `/debrief` (admin-only; sync Meet “Notes by Gemini” into Supabase; manually extract tasks; edit/remove; send to ClickUp once IDs are mapped). Specs: `docs/archive/non_agencyclaw/debrief_prd.md`, plan: `docs/archive/non_agencyclaw/debrief_implementation_plan.md`.

### Shipped Services (Internal / No UI)
- **ClickUp Service (backend-core)** — shared backend integration layer for ClickUp API calls (task creation + future sync). Routes live under `backend-core/app/routers/clickup.py`. Spec: `docs/archive/non_agencyclaw/08_clickup_service_prd.md`.

### In Flight / Upcoming
- **The Claw** — Slack assistant reboot for agency operations. Current plan/docs: `docs/theclaw/current/01_theclaw_reboot_implementation_plan.md`, `docs/theclaw/current/02_theclaw_architecture.md`.
- **Historical docs (non-The-Claw)** — archived at `docs/archive/non_agencyclaw/` (index: `docs/archive/non_agencyclaw/README.md`).
- More tools planned; follow the docs folder for new PRDs and plans as they land.

### Database Schema
- `docs/db/schema_master.md` — Canonical live Supabase schema snapshot (generated).
- `docs/db/README.md` — Schema docs policy + regeneration workflow.

### Dev Operations
- `docs/mcp_setup.md` — MCP workspace setup and verification (Supabase MCP server config, read-only connectivity checks, and `401 Unauthorized` re-auth recovery).
- `docs/windsor_wbr_ingestion_runbook.md` — Windsor Section 1 ingestion operations for WBR (account scoping, date windows, sync behavior, and batching strategy).
- `docs/wbr_v2_handoff.md` — Current WBR v2 shipped state, routes, migrations, and restart context.
- `docs/wbr_v2_schema_plan.md` — WBR schema plan annotated with current implementation status, live migrations, and follow-on schema notes.

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
| `worker-sync` | Background | Render background worker for nightly WBR refresh jobs and future long-running sync work |

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
