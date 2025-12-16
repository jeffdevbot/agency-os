# Ecomlabs Tools (formerly “Agency OS”)

Ecomlabs Tools is the internal platform that consolidates our ad analytics, SOP ops, content creation, and creative briefing into a single authenticated dashboard at `tools.ecomlabs.ca`. The `docs/` folder captures the architecture, PRDs, and migration plans that guide the implementation. “Agency OS” was the internal codename; use “Ecomlabs Tools” in user-facing copy.

## Documentation map

### Core Architecture
- `docs/00_agency_os_architecture.md` — master architecture: Render services (`frontend-web`, `backend-core`, `worker-sync`), Supabase auth, and the migration path off of `ngram.ecomlabs.ca`. Notes the “Agency OS” codename but current branding is Ecomlabs Tools.
- `docs/01_ngram_migration.md` — the "Split and Lift" plan for porting the existing Ngram analyzer into the Ecomlabs Tools frontend/backend pattern.

### Shipped Tools
- N-Gram Processor — `/ngram` (two-step flow: generate workbook, then upload filled workbook to download a formatted negatives summary).
- N-PAT (Negative Product Attribute Targeting) — `/npat` (ASIN-only inverse of N-Gram with Helium10 enrichment). Specs: `docs/03_npat_prd.md`, plan: `docs/03_npat_plan.md`.
- Root Keyword Analysis — `/root-keywords` (4-week hierarchical campaign rollup). Specs: `docs/18_root_keyword_analysis_prd.md`, plan: `docs/19_root_keyword_analysis_plan.md`.
- Command Center (MVP) — `/command-center` (admin-only; clients → brands → role slots; team roster; Ghost Profiles merge-on-login). Specs: `docs/07_command_center_prd.md`, API: `docs/07_command_center_schema_api.md`.
- Debrief (MVP) — `/debrief` (admin-only sync/extract; sync Meet “Notes by Gemini” into Supabase; manually extract tasks for review; ClickUp deferred). Specs: `docs/debrief_prd.md`, plan: `docs/debrief_implementation_plan.md`.

### In Flight / Upcoming
- Scribe — ready but not released to the team yet (Amazon copy generation). Current PRDs live under `docs/scribe_lite/`.
- ClickUp Service — shared integration layer for ClickUp task creation/sync (Debrief will use this in a later phase). Spec: `docs/08_clickup_service_prd.md`.
- More tools planned; follow the docs folder for new PRDs and plans as they land.

### Other Specs
- `docs/02_the_operator_prd.md` — PRD for The Operator, the AI-driven ClickUp command center and SOP canonization workflow.
- `docs/05_creative_brief_prd.md` — Creative Brief tool that maps Composer copy + uploaded assets into designer-ready storyboards.
- `docs/11_usage_events_schema.md` — Usage + token logging schema reference (used by Scribe; Debrief token logging is next).

### Deprecated
- `docs/04_amazon_composer_prd.md` — **[DEPRECATED]** Amazon listing composer. **Replaced by Scribe.** Code will be removed after Scribe stabilizes.

Each doc includes the UX, backend contracts, and Supabase schema changes needed for its domain. Treat them as living specs; update them before or alongside any code changes that affect scope or interfaces.

## Next steps for contributors

1. Read the architecture overview to internalize the Render + Supabase stack and auth flow.
2. Pick the relevant PRD for the feature you plan to build and translate its requirements into issues/tasks.
3. Keep docs and implementation in lockstep—when APIs, data models, or flows change, edit the corresponding doc so future contributors have a single source of truth.

## Local quickstarts

### Debrief (Google Drive ingestion)
- Configure (local): `frontend-web/.env.local` with `GOOGLE_SERVICE_ACCOUNT_JSON`, `GOOGLE_IMPERSONATION_EMAIL`, `GOOGLE_MEET_FOLDER_ID`.
- Smoke test Drive access: `npm -C frontend-web run debrief:list-drive`.
