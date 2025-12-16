# New AI Chat Prompt — Debrief Token Usage Logging (and next Debrief steps)

You are joining an existing repo (`agency-os`) that already shipped **Command Center** and a **Debrief MVP**.

## What’s already working (high-level)

### Command Center (MVP)
- `/command-center` is an **admin-only** tool for managing:
  - Clients → Brands (brands have `amazon_marketplaces text[]`)
  - Team members via **Ghost Profiles** (pre-create users by email; they merge on first Google login)
  - Brand-level role-slot assignments (org-chart style)

### Debrief (MVP)
- `/debrief` syncs Google Meet “Notes by Gemini” Google Docs from a configured Drive folder into Supabase (`debrief_meeting_notes`).
- Meetings are viewable at `/debrief/meetings/[meetingId]`.
- **Task extraction is manual** (button per meeting) to avoid wasting tokens on non-action meetings (e.g. interviews).
- ClickUp integration is deferred.

## Key docs to read first (in this order)
1) `docs/00_agency_os_architecture.md` (services + auth model)
2) `docs/07_command_center_prd.md`
3) `docs/07_command_center_schema_api.md`
4) `docs/debrief_prd.md`
5) `docs/debrief_implementation_plan.md`
6) `docs/08_clickup_service_prd.md` (future phase)
7) `docs/11_usage_events_schema.md` (logging schema reference)

## Relevant code + migrations (jump points)

### Debrief database
- `supabase/migrations/20251215000004_debrief_core.sql` (creates `debrief_meeting_notes`, `debrief_extracted_tasks` + RLS)

### Debrief routes
- Sync: `frontend-web/src/app/api/debrief/sync/route.ts`
- List meetings: `frontend-web/src/app/api/debrief/meetings/route.ts`
- Get meeting: `frontend-web/src/app/api/debrief/meetings/[meetingId]/route.ts`
- Extract tasks: `frontend-web/src/app/api/debrief/meetings/[meetingId]/extract/route.ts`

### Token logging helper (already exists, not currently used by Debrief)
- `frontend-web/src/lib/ai/usageLogger.ts` (best-effort insert into `ai_token_usage`)

## The bug/oversight to fix in this session

Debrief calls OpenAI (during extraction) but does **not** log usage in `ai_token_usage`.

### Goal
Add **reliable, best-effort** token usage logging for Debrief extraction (and optionally summaries) using the existing `logUsage()` helper.

### Scope (must-haves)
1) In `POST /api/debrief/meetings/[meetingId]/extract`, after a successful OpenAI response:
   - Call `logUsage()` with:
     - `tool`: `debrief`
     - `stage`: something like `extract`
     - `userId`: the authenticated admin’s `auth.uid()`
     - `model`, `promptTokens`, `completionTokens`, `totalTokens`
     - `meta`: include `meeting_note_id`, `google_doc_id`, and `replace` flag if used
2) If extraction fails after the OpenAI call returns (e.g. parse error), still log usage (tokens were spent).
3) Do not throw if logging fails (logger is best-effort by design).

### Nice-to-haves (optional)
- Also log Debrief “sync” operations as higher-level events:
  - Either to `ai_token_usage` with `tool=debrief`, `stage=sync` (token counts null), or to `usage_events` if that’s the direction the project wants.
  - Capture meta: `folder_id`, `limit`, `files_scanned`, `notes_upserted`, `elapsed_ms`.

## Acceptance criteria
- Running extraction for a meeting creates (at least) one row in `ai_token_usage` with the correct `tool`, `stage`, `user_id`, and token/model fields.
- Extraction behavior remains unchanged (still manual; still idempotent unless `replace=1`).
- No secrets are logged in `meta` (no raw document text, no service account JSON, no access tokens).

## Helpful context / decisions already made
- Brand-level assignments are the source of truth; client-wide assignments exist in schema but are not used in the UX.
- Debrief extraction tries to focus on “Suggested Next Steps” sections when present, otherwise uses the whole doc text.
- The repo uses Supabase Auth (Google SSO); server-side route handlers should use verified user identity (`supabase.auth.getUser()`).

