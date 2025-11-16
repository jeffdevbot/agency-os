# Project Status — Agency OS

_Last updated: 2025-11-15_

## How to Use This File
- Skim **Quick Recap**, **Recent Accomplishments**, and **Next Priorities** before coding.
- Update the date and add a brief note under **Recent Accomplishments** when you finish a session.
- Keep the **Documentation Map** aligned with the contents of `docs/` so we always know where deeper specs live.

## Quick Recap
Agency OS consolidates internal tools (Ngram, The Operator, Amazon Composer, Creative Brief) behind a shared Next.js frontend, FastAPI backend, and Supabase auth stack deployed on Render. Supabase handles SSO (Google) plus the shared database, while the worker service manages nightly syncs and other heavy jobs.

## Recent Accomplishments
- **2025-11-15** – Fixed the Supabase browser client setup (`frontend-web/src/lib/supabaseClient.ts`) to statically read `NEXT_PUBLIC_*` env vars so Google login works again during local dev.

## Next Priorities
- Harden the authentication flow: verify protected routes, session handling, and middleware align with Supabase helper patterns before building new screens.
- Begin the Ngram migration outlined in `docs/01_ngram_migration.md`, starting with backend route extraction and setting up the `/ngram` frontend page.
- Scope the Operator Milestone 1 UI shell so it can host the chat + context panes described in `docs/02_the_operator_prd.md`, even if data is mocked at first.
- Capture any backend schema/config needs surfaced by the Admin Configurator or other PRDs so Supabase migrations do not lag behind UI progress.

## Documentation Map (Quick Reference)
- `docs/00_agency_os_architecture.md` — High-level blueprint for the Render services, Supabase auth setup, and domain migration strategy. Start here for infra questions or when onboarding collaborators.
- `docs/01_ngram_migration.md` — Detailed checklist for splitting the legacy Ngram processor into the new frontend/backed pattern (dependencies, routers, CORS). Use when working on `/ngram`.
- `docs/02_the_operator_prd.md` — Product + technical spec for The Operator AI assistant (M1). Covers UX flows, agent responsibilities, and data model expectations.
- `docs/03_admin_settings_prd.md` — Admin Configurator requirements outlining roles/clients mapping UI and the supporting API contract plus schema changes.
- `docs/04_amazon_composer_prd.md` — Amazon listing generation workflow (input wizard, AI draft, review links, exports) and backend chaining details.
- `docs/05_creative_brief_prd.md` — Creative Brief tool spec focusing on asset ingestion, AI tagging, storyboard editor, and storage constraints.

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
