# Ecomlabs Tools (formerly “Agency OS”)

Ecomlabs Tools is the internal platform that consolidates our ad analytics, SOP ops, content creation, and creative briefing into a single authenticated dashboard at `tools.ecomlabs.ca`. The `docs/` folder captures the architecture, PRDs, and migration plans that guide the implementation. “Agency OS” was the internal codename; use “Ecomlabs Tools” in user-facing copy.

## Documentation map

### Core Architecture
- `docs/00_agency_os_architecture.md` — master architecture: Render services (`frontend-web`, `backend-core`, `worker-sync`), Supabase auth, and the migration path off of `ngram.ecomlabs.ca`. Notes the “Agency OS” codename but current branding is Ecomlabs Tools.
- `docs/01_ngram_migration.md` — the "Split and Lift" plan for porting the existing Ngram analyzer into the Ecomlabs Tools frontend/backend pattern.

### Shipped Tools (Web UI)
- **N-Gram Processor** — `/ngram` (two-step flow: generate workbook, then upload filled workbook to download a formatted negatives summary).
- **N-PAT (Negative Product Attribute Targeting)** — `/npat` (ASIN-only inverse of N-Gram with Helium10 enrichment). Specs: `docs/03_npat_prd.md`, plan: `docs/03_npat_plan.md`.
- **AdScope** — `/adscope` (Amazon Ads audit workspace: upload Bulk + STR; views + chat). Specs: `docs/20_adscope_prd.md`, schema: `docs/21_adscope_schema.md`.
- **Scribe** — `/scribe` (Amazon listing copy generation: project → SKUs → topics → copy). Current specs live under `docs/scribe_lite/`.
- **Root Keyword Analysis** — `/root-keywords` (4-week hierarchical campaign rollup). Specs: `docs/18_root_keyword_analysis_prd.md`, plan: `docs/19_root_keyword_analysis_plan.md`.
- **Command Center (MVP)** — `/command-center` (admin-only; clients → brands → role slots; team roster; Ghost Profiles merge-on-login). Specs: `docs/07_command_center_prd.md`, API: `docs/07_command_center_schema_api.md`.
- **Debrief (MVP)** — `/debrief` (admin-only; sync Meet “Notes by Gemini” into Supabase; manually extract tasks; edit/remove; send to ClickUp once IDs are mapped). Specs: `docs/debrief_prd.md`, plan: `docs/debrief_implementation_plan.md`.

### Shipped Services (Internal / No UI)
- **ClickUp Service (backend-core)** — shared backend integration layer for ClickUp API calls (task creation + future sync). Routes live under `backend-core/app/routers/clickup.py`. Spec: `docs/08_clickup_service_prd.md`.

### In Flight / Upcoming
- **AgencyClaw** — Slack assistant for agency operations (task creation, weekly status, command-center skills, SOP-grounded drafting). Specs: `docs/23_agencyclaw_prd.md`, implementation: `docs/24_agencyclaw_implementation_plan.md`, tracker: `docs/25_agencyclaw_execution_tracker.md`.
- More tools planned; follow the docs folder for new PRDs and plans as they land.

### Other Specs
- `docs/05_creative_brief_prd.md` — Creative Brief tool that maps Composer copy + uploaded assets into designer-ready storyboards.
- `docs/11_usage_events_schema.md` — Usage + token logging schema reference (token usage lives in `ai_token_usage` for Scribe, AdScope, Debrief).

### Deprecated
- `docs/04_amazon_composer_prd.md` — **[DEPRECATED]** Amazon listing composer. **Replaced by Scribe.** Code will be removed after Scribe stabilizes.
- `docs/02_the_operator_prd.md` — **[DEPRECATED]** The Operator concept PRD (superseded by Debrief + ClickUp Service).

Each doc includes the UX, backend contracts, and Supabase schema changes needed for its domain. Treat them as living specs; update them before or alongside any code changes that affect scope or interfaces.

## Next steps for contributors

1. Read the architecture overview to internalize the Render + Supabase stack and auth flow.
2. Pick the relevant PRD for the feature you plan to build and translate its requirements into issues/tasks.
3. Keep docs and implementation in lockstep—when APIs, data models, or flows change, edit the corresponding doc so future contributors have a single source of truth.

## Service Architecture

| Service | Type | Purpose |
|---------|------|---------|
| `frontend-web` | Next.js | Web UI at tools.ecomlabs.ca |
| `backend-core` | FastAPI | API endpoints, integrations |
| `worker-sync` | Background | Render background worker (planned; no code in this repo yet) |

All services are deployed on Render. See `docs/00_agency_os_architecture.md` for details.

## AgencyClaw (Slack Assistant)

AgencyClaw is the successor to the legacy Vara/Playbook bot and is now the active Slack runtime for operations workflows.

**Primary docs:** `docs/23_agencyclaw_prd.md`, `docs/24_agencyclaw_implementation_plan.md`, `docs/25_agencyclaw_execution_tracker.md`.

**Key integration points:**
- Slack API (events + interactions) → `backend-core` (TBD; add a `backend-core/app/routers/slack.py` router)
- SOP sync from ClickUp Docs → `worker-sync/` (TBD; Render service exists but code is not in this repo yet)
- Session storage → Supabase `playbook_slack_sessions` table (legacy table name retained)
- AI chat → OpenAI (`OPENAI_API_KEY`, models: gpt-4o / gpt-4o-mini)
- Task creation → existing `backend-core/app/services/clickup.py`

**Existing schema (no migration needed):**
- `profiles.slack_user_id` — links Slack users to profiles
- `profiles.clickup_user_id` — for task assignment
- `brands.clickup_space_id` / `clickup_list_id` — where to create tasks
- `ai_token_usage` — token logging (use `tool='agencyclaw'` + stage labels)

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
