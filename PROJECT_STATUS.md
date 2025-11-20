# Project Status — Agency OS

_Last updated: 2025-11-19_

## How to Use This File
- Skim **Quick Recap**, **Recent Accomplishments**, and **Next Priorities** before coding.
- Update the date and add a brief note under **Recent Accomplishments** when you finish a session.
- Keep the **Documentation Map** aligned with the contents of `docs/` so we always know where deeper specs live.
- Whenever we add or modify a service/app, update `docs/10_systems_overview.md` so the systems inventory matches reality.
- For backend work: activate the FastAPI virtual env via `source backend-core/.venv/bin/activate`; deactivate with `deactivate`. Install deps using `python3 -m venv backend-core/.venv && source backend-core/.venv/bin/activate && python3 -m pip install -r backend-core/requirements.txt`.
- Export Supabase vars before starting uvicorn (these match Render env group values):
  ```
  export SUPABASE_JWT_SECRET="******"
  export SUPABASE_URL="https://iqkmygvncovwdxagewal.supabase.co"
  export SUPABASE_SERVICE_ROLE="******"
  export ENABLE_USAGE_LOGGING=1
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
  ```

## Quick Recap
Agency OS consolidates internal tools (Ngram, The Operator, Amazon Composer, Creative Brief) behind a shared Next.js frontend, FastAPI backend, and Supabase auth stack deployed on Render. Supabase handles SSO (Google) plus the shared database, while the worker service manages nightly syncs and other heavy jobs.

## Recent Accomplishments
- **2025-11-19** – Drafted and documented Composer Slice 2 (Keyword Pipeline) implementation plan: aligned schema/types with keyword pool state machine, manual overrides, and new API surface so we can begin Slice 2 build-out.
- **2025-11-19** – Wrapped Composer Slice 1 polish: added key-attribute highlight grid, persisted `highlight_attributes` JSON (schema + types), introduced keyword grouping override spec, and documented/testing updates (82 passing Vitest suites). Ready to start Slice 2 planning.
- **2025-11-19** – Hardened Composer Slice 1 Surface 4 with shared `serverUtils` helpers, Supabase route-client mocks, and full Vitest coverage for the groups/assign/unassign APIs plus the `useSkuGroups` hook (82 tests passing locally via `npm run test:run`).
- **2025-11-19** – Completed Composer Slice 1 Surface 4 (Content Strategy): StrategyToggle, SkuGroupsBuilder, GroupCard, UnassignedSkuList, and ContentStrategyStep components; full SKU groups API (GET/POST groups, PATCH/DELETE group, assign/unassign variants); `useSkuGroups` hook with optimistic updates. Slice 1 is now feature-complete.
- **2025-11-18** – Migrated the frontend to `@supabase/ssr`, fixed the async cookies regression, and aligned the Composer fallback org (`DEFAULT_COMPOSER_ORG_ID = e9368435-…`). Documented the rule that Supabase users must carry the same `org_id` metadata; legacy Composer rows were updated so existing projects resurface in the dashboard.
- **2025-11-17** – Finished Composer Slice 1 Surface 3 (Product Info): full autosave meta forms, FAQ editor, SKU intake (inline edits, CSV import/merge, org-scoped APIs), CSV parser, and SKU validation/persistence so projects can resume from the wizard.
- **2025-11-16** – Brought Composer Slice 1 Surface 1+2 online: dashboard list/create, wizard frame with autosave shell, GET/PATCH detail API, Supabase default org fallback, and new Supabase client helper (`createPagesBrowserClient`). Ready to plug Product Info & Strategy UIs into the shell.
- **2025-11-15** – Landed Composer schema + tenancy work: created all `composer_*` tables in Supabase, enforced RLS with org-scoped policies (`docs/composer/01_schema_tenancy.md`), and published the canonical TypeScript types (`docs/composer/02_types_canonical.md` + `/lib/composer/types.ts`) so the frontend/backed/AI layers share the same model.
- **2025-11-14** – Rebuilt the Composer PRD (v1.6) and captured the corresponding end-to-end implementation plan (`docs/06_composer_implementation_plan.md`) so future work can follow defined slices/workstreams without ambiguity.
- **2025-11-13** – Migrated the N-Gram Processor into the new stack: FastAPI backend (`backend-core/app/routers/ngram.py` + services) with Supabase usage logging, plus a refreshed `/ngram` Next.js page and home screen shortcut. Local Supabase env + venv instructions captured in this doc for future sessions.
- **2025-11-13** – Added Supabase-aware Next.js middleware to guard `/ngram`, ensuring logged-out users are redirected to the login screen before hitting protected pages.

## Next Priorities
- Begin Composer Slice 2 (Keyword Pipeline): implement Keyword Upload, Keyword Cleanup, and Grouping Plan surfaces with associated APIs and hooks.
- Deploy backend-core + refreshed frontend to Render, validate env vars (usage logging, Supabase secrets) and ensure `/ngram` works end-to-end in production.
- Scope the Operator Milestone 1 UI shell so it can host the chat + context panes described in `docs/02_the_operator_prd.md`, even if data is mocked at first.

## Documentation Map (Quick Reference)
- `docs/00_agency_os_architecture.md` — High-level blueprint for the Render services, Supabase auth setup, and domain migration strategy. Start here for infra questions or when onboarding collaborators.
- `docs/01_ngram_migration.md` — Detailed checklist for splitting the legacy Ngram processor into the new frontend/backed pattern (dependencies, routers, CORS). Use when working on `/ngram`.
- `docs/02_the_operator_prd.md` — Product + technical spec for The Operator AI assistant (M1). Covers UX flows, agent responsibilities, and data model expectations.
- `docs/03_admin_settings_prd.md` — Admin Configurator requirements outlining roles/clients mapping UI and the supporting API contract plus schema changes.
- `docs/04_amazon_composer_prd.md` — Amazon listing generation workflow (input wizard, AI draft, review links, exports) and backend chaining details.
- `docs/05_creative_brief_prd.md` — Creative Brief tool spec focusing on asset ingestion, AI tagging, storyboard editor, and storage constraints.
- `docs/10_systems_overview.md` — Running list of every service, its repo path, Render deployment, and shared dependencies. Update this table whenever new tools or env vars are introduced.

## Render Deployment Map
- **Services (Render Project: “Ecomlabs Agency OS”)**
  - `frontend-web` — Node/Next.js service deployed from `/frontend-web` (Render region: Virginia). Hosts the dashboard at `tools.ecomlabs.ca`.
  - `backend-core` — Python FastAPI service deployed from `/backend-core` (Virginia). Provides APIs, agent orchestration, and communicates with Supabase.
  - `worker-sync` — Python background worker deployed from `/worker-sync` (Virginia). Handles nightly syncs and long-running jobs.
  - *Note:* Screenshot shows recent deploys failed; verify build logs before the next release so we catch configuration drift early.
- **Env Group: `agency-os-env-var`**
  - Shared across the services above so every deployment receives consistent secrets.
  - Contains: `CLICKUP_API_TOKEN`, Google OAuth client ID/secret, `MAX_UPLOAD_MB`, `NEXT_PUBLIC_BACKEND_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, OpenAI keys/model selectors, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_JWT_SECRET`.
  - Keep Render as the source of truth; mirror critical values into local `.env.local` files as needed for development.

---
_Remember: keep this document short and actionable—link to the PRDs for deep dives instead of duplicating their content._
