# Systems Overview

This document tracks every application, service, and long-running worker in Agency OS along with where their code lives, how they deploy, and the shared dependencies they rely on. Update this file whenever a new tool is added or an existing one changes shape so the architecture stays discoverable.

## Services

| Name          | Repo Path        | Render Service | Stack / Runtime | Primary Responsibilities | Notes |
| ------------- | ---------------- | -------------- | ---------------- | ------------------------ | ----- |
| Frontend Web  | `/frontend-web`  | `frontend-web` | Next.js (Node)   | UI shell, Supabase auth flows, tool-specific pages (`/ngram`, `/ops`, etc.), static asset hosting. | Uses `NEXT_PUBLIC_*` vars from Render env group and `.env.local`. |
| Backend Core  | `/backend-core`  | `backend-core` | FastAPI (Python) | API endpoints, agent orchestration, Supabase/Postgres access, ClickUp integration. | Includes shared Supabase auth middleware + usage logging helper. |
| Worker Sync   | `/worker-sync`*  | `worker-sync`  | Python worker    | Nightly ClickUp sync, SOP batch processing, any task needing long runtimes. | *Planned folder to align with Render background worker. |

## Shared Infrastructure

- **Supabase** — Auth, Postgres (clients, profiles, SOPs), storage buckets, pgvector.
- **Render Env Group `agency-os-env-var`** — Houses Supabase secrets, Google OAuth credentials, ClickUp token, OpenAI keys, etc. Keep this group the single source of truth; replicate locally only what you need in `.env.local`.
- **External APIs** — ClickUp, OpenAI (primary + fallback models), Google OAuth.

## Update Checklist

When adding or modifying a service:
1. Add/adjust the row in the table above with repo path, Render service name, and purpose.
2. Note any new environment variables and ensure they’re stored inside the Render env group.
3. Reference related PRDs or docs (e.g., `docs/01_ngram_migration.md` for `/ngram`) so contributors know where to dig deeper.

Keeping this file up to date prevents “tribal knowledge” from drifting and keeps render deployments + local dev environments consistent.
