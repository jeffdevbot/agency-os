# Agency OS

Agency OS is a unified internal platform for EcomLabs that consolidates scattered tooling—ad analytics, SOP ops, content creation, and creative briefing—into a single authenticated dashboard at `tools.ecomlabs.ca`. The current repo is documentation-first: the `docs/` folder captures the architecture, PRDs, and migration plans that guide the upcoming implementation. Start here before writing code so new services land in the correct Render/Supabase topology.

## Documentation map

- `docs/00_agency_os_architecture.md` — master architecture: Render services (`frontend-web`, `backend-core`, `worker-sync`), Supabase auth, and the migration path off of `ngram.ecomlabs.ca`.
- `docs/01_ngram_migration.md` — the “Split and Lift” plan for porting the existing Ngram analyzer into the Agency OS frontend/backend pattern.
- `docs/02_the_operator_prd.md` — PRD for The Operator, the AI-driven ClickUp command center and SOP canonization workflow.
- `docs/03_admin_settings_prd.md` — Admin-only configurator that manages users, clients, ClickUp spaces, and staffing assignments (RBAC backbone for the rest of the OS).
- `docs/04_amazon_composer_prd.md` — Amazon listing composer with client-facing approval links and flat-file exports.
- `docs/05_creative_brief_prd.md` — Creative Brief tool that maps Composer copy + uploaded assets into designer-ready storyboards.

Each doc includes the UX, backend contracts, and Supabase schema changes needed for its domain. Treat them as living specs; update them before or alongside any code changes that affect scope or interfaces.

## Next steps for contributors

1. Read the architecture overview to internalize the Render + Supabase stack and auth flow.
2. Pick the relevant PRD for the feature you plan to build and translate its requirements into issues/tasks.
3. Keep docs and implementation in lockstep—when APIs, data models, or flows change, edit the corresponding doc so future contributors have a single source of truth.
