# AGENTS.md

> Context and instructions for AI coding agents working on Ecomlabs Tools (internal codename: Agency OS).

## Project overview

Ecomlabs Tools is an internal platform for an Amazon/e-commerce marketing agency. It consolidates ad analytics, content creation, and ops tools into a single authenticated dashboard at `tools.ecomlabs.ca`.

**Stack:**
- **Frontend:** Next.js 14 + Tailwind CSS + TypeScript (`frontend-web/`)
- **Backend:** FastAPI + Python (`backend-core/`)
- **Database/Auth:** Supabase (Google SSO, PostgreSQL with RLS)
- **Deployment:** Render (Virginia region)

## Project structure

```
agency-os/
├── frontend-web/          # Next.js dashboard
│   ├── src/app/           # App router pages
│   │   ├── ngram/         # N-Gram Processor
│   │   ├── npat/          # N-PAT (ASIN negatives)
│   │   ├── adscope/       # Amazon Ads audit workspace
│   │   ├── scribe/        # Amazon listing copy generator
│   │   ├── root-keywords/ # Campaign rollup analysis
│   │   ├── command-center/# Admin: clients, brands, team
│   │   ├── debrief/       # Meeting notes → tasks
│   │   └── api/           # Next.js API routes
│   └── src/lib/           # Shared utilities, hooks, AI helpers
├── backend-core/          # FastAPI backend
│   ├── app/routers/       # API endpoints (ngram, npat, adscope, root, clickup)
│   └── app/services/      # Business logic per tool
├── worker-sync/           # Background jobs (nightly syncs)
├── supabase/migrations/   # Database migrations (timestamped SQL)
├── docs/                  # PRDs and specs (may be outdated; code is the spec)
└── project_status.md      # Changelog of recent work
```

## Tools in production

| Tool | Route | What it does |
|------|-------|--------------|
| **N-Gram Processor** | `/ngram` | Upload Amazon STR → get workbook → upload filled → download negatives summary |
| **N-PAT** | `/npat` | ASIN-only inverse of N-Gram with Helium10 enrichment |
| **AdScope** | `/adscope` | Upload Bulk + STR files → 13+ precomputed views + AI chat |
| **Scribe** | `/scribe` | Wizard: SKU inputs → AI topics → AI copy generation → CSV export |
| **Root Keywords** | `/root-keywords` | 4-week hierarchical campaign rollup → Excel workbook |
| **Command Center** | `/command-center` | Admin-only: clients → brands → role assignments, team roster |
| **Debrief** | `/debrief` | Admin-only: sync Google Meet notes → extract tasks |

## Local development

### Frontend (Next.js)

```bash
cd frontend-web
npm install
npm run dev          # starts on http://localhost:3000
```

Requires `.env.local` with Supabase keys. Copy from Render env group or ask a teammate.

### Backend (FastAPI)

```bash
# Create and activate virtual environment
python3 -m venv backend-core/.venv
source backend-core/.venv/bin/activate

# Install dependencies
pip install -r backend-core/requirements.txt

# Export required env vars (get values from Render env group)
export SUPABASE_URL="https://iqkmygvncovwdxagewal.supabase.co"
export SUPABASE_SERVICE_ROLE="<from-render>"
export SUPABASE_JWT_SECRET="<from-render>"
export OPENAI_API_KEY="<from-render>"
export ENABLE_USAGE_LOGGING=1

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

To deactivate the venv later: `deactivate`

### Running both together

Frontend calls backend at `NEXT_PUBLIC_BACKEND_URL`. For local dev, set this to `http://localhost:8000` in `.env.local`.

## Testing

### Frontend tests (Vitest)

```bash
cd frontend-web
npm run test:run              # run all tests once
npm run test                  # watch mode
npm run test:run -- -t "pattern"  # run specific tests
```

### Backend tests (pytest)

```bash
source backend-core/.venv/bin/activate
pytest backend-core/         # run all backend tests
pytest backend-core/tests/test_ngram_analytics.py  # specific file
```

### Before committing

```bash
# Frontend: lint + type check + tests
npm -C frontend-web run lint
npm -C frontend-web run build   # catches type errors
npm -C frontend-web run test:run

# Backend
pytest backend-core/
```

## Code conventions

### General

- **Code is the spec.** The `docs/` folder has PRDs but they may be outdated. Trust the implementation.
- **Keep changes focused.** Don't refactor unrelated code or add features beyond the task.
- **No approval needed for test changes.** Add or update tests for code you change.

### Frontend

- Pages live in `frontend-web/src/app/<tool>/page.tsx`
- API routes live in `frontend-web/src/app/api/<tool>/route.ts`
- Shared components: `frontend-web/src/components/`
- Tool-specific components: `frontend-web/src/app/<tool>/components/`
- AI/LLM utilities: `frontend-web/src/lib/ai/` (includes `usageLogger.ts` for token tracking)

### Backend

- Each tool has a router in `backend-core/app/routers/<tool>.py`
- Business logic in `backend-core/app/services/<tool>/`
- All endpoints require auth via `user=Depends(require_user)`
- File uploads stream in chunks with 40MB cap (`MAX_UPLOAD_MB`)
- Log AI usage via `usage_logger` for token tracking

### Database

- Migrations go in `supabase/migrations/` with timestamp prefix: `YYYYMMDDHHMMSS_description.sql`
- Use RLS policies for row-level security
- Token/AI usage logs go to `ai_token_usage` table

### Auth patterns

- Server-side: use `supabase.auth.getUser()` (verified) not `getSession()` (unverified)
- Client-side: `getSession()` is fine for initial checks
- Admin-only routes check `profile.team_role === 'admin'`

## Deployment

**Render services:**
- `frontend-web` → `tools.ecomlabs.ca`
- `backend-core` → API server
- `worker-sync` → background jobs

**Env group:** `agency-os-env-var` (shared across all services)

Key env vars: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `OPENAI_API_KEY`, `OPENAI_MODEL_PRIMARY`, `OPENAI_MODEL_FALLBACK`, `NEXT_PUBLIC_BACKEND_URL`

Deploys trigger automatically on push to main. Check Render dashboard for build logs if deploys fail.

## Deprecated code

- **Composer** (`frontend-web/src/app/composer/`) — Replaced by Scribe. Code remains but is frozen.
- **The Operator** — Replaced by Debrief.

Legacy code in `_legacy_v1` folders or `docs/archive/` can be ignored.

## Gotchas

- **Supabase auth deadlock:** Never use `async` in `onAuthStateChange` callbacks or call `getUser()` inside them. See commit `b754d01` for the fix.
- **CSV parsing:** Use auto-detect for delimiter (tab vs comma). Always quote fields properly (RFC 4180).
- **React state closures:** When updating state and making API calls, read state *before* `setState` to avoid stale closures.
- **Supabase upsert:** Avoid `onConflict` parameter—use manual check-then-update-or-insert instead.

## Changelog

See [project_status.md](project_status.md) for recent accomplishments and history.
