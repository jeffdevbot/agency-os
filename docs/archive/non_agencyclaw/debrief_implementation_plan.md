# Debrief — Implementation Plan (Staged)

Status (2025-12-15): draft plan to implement `docs/debrief_prd.md` in small, verifiable slices.

## Stage 0 — Prereqs (Done / Confirm)
- Command Center shipped (clients, brands, team, assignments).
- Brand fields populated enough for routing:
  - `brands.product_keywords`
  - `brands.amazon_marketplaces` (optional for routing; required for Debrief marketplace awareness)
- Role routing available to Debrief:
  - `GET /api/command-center/debrief/brands`
  - `GET /api/command-center/debrief/routing?brandId=<uuid>`

## Stage 1 — Google Workspace “Impersonation” Setup (Drive access)

Goal: a server-side integration can read Google Meet notes/recordings from Drive without interactive OAuth.

Debrief PRD expects **domain-wide delegation** via a Google Workspace service account.

### 1.1 Create Google Cloud project + service account
1) Google Cloud Console → create/select a project (e.g. `agency-os-debrief`).
2) APIs & Services → enable:
   - Google Drive API
   - (Optional, recommended) Google Docs API (cleaner doc parsing)
3) IAM & Admin → Service Accounts → create `debrief-sync`.
4) Create a JSON key for the service account (download once; store securely).

### 1.2 Enable domain-wide delegation
1) In the service account settings, enable **Domain-wide delegation**.
2) Copy the service account **Client ID** (not the email).

### 1.3 Allow the service account in Google Admin Console
Requires Workspace admin permissions.
1) Admin Console → Security → Access and data control → API controls → Domain-wide delegation.
2) Add new:
   - Client ID: service account client ID
   - OAuth scopes (start minimal):
     - `https://www.googleapis.com/auth/drive.readonly`
     - (Optional if using Docs API) `https://www.googleapis.com/auth/documents.readonly`

### 1.4 Decide what to impersonate
- Pick a single Workspace user to impersonate (e.g. `jeff@ecomlabs.ca`) who has access to the target folder.
- Store as config: `GOOGLE_IMPERSONATION_EMAIL`.

### 1.5 Identify the Drive folder to read
- “Meet Recordings” folder (or where Gemini meeting notes land).
- Copy folder ID (the part after `folders/` in the URL).
- Store as config: `GOOGLE_MEET_FOLDER_ID`.

### 1.6 App configuration (no secrets in git)
Add env vars (format depends on how you deploy; examples):
- `GOOGLE_SERVICE_ACCOUNT_JSON` (stringified JSON or path to JSON file)
- `GOOGLE_IMPERSONATION_EMAIL`
- `GOOGLE_MEET_FOLDER_ID`

Verification step (manual):
- Run a server-side “list last 5 files in folder” script/endpoint and confirm it returns results.

## Stage 2 — Sync last X meeting notes/recordings into Supabase

Goal: a Debrief admin can click “Sync” and see the newest meetings in the UI.

### 2.1 Debrief tables (Supabase migrations)
Create:
- `public.debrief_meeting_notes` (from PRD section 4.1)
- `public.debrief_extracted_tasks` (from PRD section 4.2)

Start with minimal columns needed to render `/debrief`:
- meeting notes: `google_doc_id`, `google_doc_url`, `title`, `meeting_date`, `owner_email`, `raw_content`, `summary_content`, `status`
- tasks: `meeting_note_id`, `raw_text`, `title`, `description`, `suggested_brand_id`, `suggested_assignee_id`, `status`

### 2.2 Sync endpoint
Implement:
- `POST /api/debrief/sync`
  - reads last `X` files from the configured Drive folder
  - upserts into `debrief_meeting_notes` by `google_doc_id`
  - sets status `pending` for new items

Notes:
- If the folder contains Google Docs, fetch content via Docs API or Drive export.
- If the folder contains video recordings, store metadata first; transcription can be Stage 4+.

## Stage 3 — Debrief UI (“Recent meetings + tasks”)

Goal: the MVP UX from the PRD:
- `/debrief`: list “Ready for Review”, “Recently Processed”, “Failed”
- `/debrief/meetings/[meetingId]`: review tasks, edit brand/assignee, approve/reject

### 3.1 Routes
- `frontend-web/src/app/debrief/page.tsx` (dashboard + Sync button)
- `frontend-web/src/app/debrief/meetings/[meetingId]/page.tsx` (review screen)

### 3.2 API surface (MVP)
- `GET /api/debrief/meetings` (list)
- `GET /api/debrief/meetings/:id` (meeting + tasks)
- `POST /api/debrief/meetings/:id/extract` (kicks off extraction; can be synchronous at first)
- `PATCH /api/debrief/tasks/:id` (edit title/description/brand/assignee)
- `POST /api/debrief/tasks/:id/approve` + `POST /api/debrief/tasks/:id/reject`

## Stage 4 — Task Extraction + Routing (still no ClickUp)

Goal: generate tasks and pre-fill brand + assignee suggestions.

Inputs:
- Meeting note content (raw + summary/suggested next steps).
- Brand candidates + keywords: `GET /api/command-center/debrief/brands`
- Role routing for a brand: `GET /api/command-center/debrief/routing?brandId=<uuid>`

Outputs:
- Rows in `debrief_extracted_tasks` linked to the meeting note.

## Stage 5 — ClickUp (Later)

Debrief PRD explicitly defers ClickUp writes.
When you’re ready:
- Implement `POST /api/debrief/meetings/:id/send-to-clickup`
- Use the shared ClickUp service (`docs/08_clickup_service_prd.md`)
- Requires `brands.clickup_*` + `profiles.clickup_user_id` populated.

