# Debrief - Meeting Notes to ClickUp Tasks

## Product Requirements Document (PRD)

**Version:** 1.1
**Product Area:** Agency OS → Debrief
**Status:** Draft
**Route:** `tools.ecomlabs.ca/debrief`

**Dependencies:**
- [Command Center](./07_command_center_prd.md) — Team members, clients, brands, roles, ClickUp mappings

---

## 1. Problem Statement

After client meetings, action items get lost—or there's a delay between the meeting and getting them to the team to start working on. Gemini generates meeting notes with "Suggested next steps," but these sit in Google Drive untouched. Tasks don't make it into ClickUp, work falls through the cracks, and there's no systematic way to track what was promised.

---

## 2. Solution Overview

**Debrief** automatically ingests meeting notes from Google Meet, extracts actionable tasks for our team, and provides a review interface.

**Note:** ClickUp task creation is intentionally deferred to a later phase. Debrief MVP focuses on ingest → extract → review → save approved tasks, so nothing gets lost while ClickUp integration is still pending.

**Flow:**
1. Google Meet generates notes via Gemini → saved to Drive
2. Debrief syncs notes from Drive (manual trigger)
3. LLM extracts tasks, identifies brand, suggests assignee
4. User reviews/edits tasks in Debrief UI
5. Approved tasks saved in Debrief (later: pushed to ClickUp via API)

---

## 3. External Dependencies

### Command Center (Required)
Debrief uses Command Center for:
- **Team members** (`profiles` table with `clickup_user_id`)
- **Role assignments** (`client_assignments` table)
- **Role-based task routing** (e.g., "catalog update" → Catalog Specialist)
- **Clients** (`agency_clients` table)
- **Brands** (`brands` table with `clickup_space_id` / `clickup_list_id` for task routing)
- **Product keywords** for brand detection in meeting notes

---

## 4. Data Model

### 4.1 Meeting Notes

```sql
create type meeting_note_status as enum ('pending', 'processing', 'ready', 'processed', 'dismissed', 'failed');

create table public.debrief_meeting_notes (
  id uuid primary key default gen_random_uuid(),
  google_doc_id text unique not null,
  google_doc_url text not null,
  title text not null,
  meeting_date timestamptz,
  owner_email text not null,
  raw_content text,
  summary_content text,
  suggested_client_id uuid references public.agency_clients(id),
  status meeting_note_status default 'pending',
  extraction_error text,
  dismissed_by uuid references public.profiles(id),
  dismissed_at timestamptz,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Indexes
create index idx_meeting_notes_status on public.debrief_meeting_notes(status);
create index idx_meeting_notes_owner on public.debrief_meeting_notes(owner_email);
create index idx_meeting_notes_date on public.debrief_meeting_notes(meeting_date desc);

-- RLS
alter table public.debrief_meeting_notes enable row level security;

create policy "Authenticated users can view meeting notes"
  on public.debrief_meeting_notes for select to authenticated using (true);

create policy "Only admins can manage meeting notes"
  on public.debrief_meeting_notes for all to authenticated
  using (exists (select 1 from public.profiles where id = auth.uid() and is_admin = true))
  with check (exists (select 1 from public.profiles where id = auth.uid() and is_admin = true));
```

**Status Flow:**
- `pending` → Initial state after sync
- `processing` → LLM extraction in progress
- `ready` → Tasks extracted, awaiting review
- `processed` → Tasks sent to ClickUp
- `dismissed` → User dismissed (duplicate or not needed)
- `failed` → Extraction failed (see `extraction_error`)

### 4.2 Extracted Tasks

```sql
create type extracted_task_status as enum ('pending', 'approved', 'rejected', 'created', 'failed');

create table public.debrief_extracted_tasks (
  id uuid primary key default gen_random_uuid(),
  meeting_note_id uuid not null references public.debrief_meeting_notes(id) on delete cascade,
  raw_text text not null,
  title text not null,
  description text,
  suggested_brand_id uuid references public.brands(id),
  suggested_assignee_id uuid references public.profiles(id),
  suggested_assignee_role text,
  status extracted_task_status default 'pending',
  clickup_task_id text,
  clickup_error text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Indexes
create index idx_tasks_meeting on public.debrief_extracted_tasks(meeting_note_id);
create index idx_tasks_status on public.debrief_extracted_tasks(status);
create index idx_tasks_brand on public.debrief_extracted_tasks(suggested_brand_id);

-- RLS (same pattern)
alter table public.debrief_extracted_tasks enable row level security;

create policy "Authenticated users can view tasks"
  on public.debrief_extracted_tasks for select to authenticated using (true);

create policy "Only admins can manage tasks"
  on public.debrief_extracted_tasks for all to authenticated
  using (exists (select 1 from public.profiles where id = auth.uid() and is_admin = true))
  with check (exists (select 1 from public.profiles where id = auth.uid() and is_admin = true));
```

---

## 5. Google Drive Integration

### Authentication Method
**Domain-wide delegation** via Google Workspace service account.

### Setup Requirements
1. Create service account in Google Cloud Console
2. Enable Google Drive API
3. Grant domain-wide delegation in Workspace Admin
4. Scope: `https://www.googleapis.com/auth/drive.readonly`

### Configuration
```env
GOOGLE_SERVICE_ACCOUNT_EMAIL=debrief@project.iam.gserviceaccount.com
GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n..."
GOOGLE_DELEGATED_USERS=jeff@ecomlabs.ca,anshuman@ecomlabs.ca
```

### Sync Logic
1. Impersonate each delegated user
2. Search for files in "Meet Recordings" folder
3. Filter: modified since last sync, filename contains "Notes by Gemini"
4. Extract Summary + Suggested next steps sections
5. Deduplicate by `google_doc_id`

### Error Handling
- Token refresh: Auto-refresh via service account
- Permission revoked: Log error, skip user, continue
- Rate limits: Exponential backoff (max 5 retries)

---

## 6. Task Extraction (LLM)

### Input
```
Meeting: "SB Supply | Weekly Strategy - 2025/12/11"
Client: SB Supply (matched from title)
Brands: Whoosh (keywords: simulator, wipes), Ranqer (keywords: charger), Lifemate (keywords: pet)
Team Members: Jeff, Anshuman, Sarah, Mike (internal only)

Summary:
[Gemini summary content]

Suggested Next Steps:
[Gemini suggested actions]
```

### Output (JSON)
```json
{
  "tasks": [
    {
      "raw_text": "Anshuman will run a negative keyword audit for the Whoosh simulator campaigns",
      "title": "Run negative keyword audit for Whoosh simulator campaigns",
      "description": "Review search term reports and identify non-converting queries to add as negatives.",
      "brand": "Whoosh",
      "assignee_hint": "Anshuman",
      "task_type": "ppc_audit"
    }
  ]
}
```

### Assignment Logic
1. LLM identifies task type (catalog, ppc, reporting, etc.)
2. System maps task type to role (e.g., ppc_audit → PPC Strategist)
3. System looks up role assignment for brand's client via Command Center
4. Falls back to mentioned name if no role match
5. User can override in UI

### Failure Handling
- LLM timeout: Retry once, then mark meeting as `failed`
- Invalid JSON: Log raw response, mark as `failed`
- User can manually retry failed meetings

---

## 7. UI Screens

### 7.1 Debrief Dashboard

**Route:** `/debrief`

```
┌─────────────────────────────────────────────────────┐
│  Debrief                          [Sync Notes]      │
│  Turn meeting notes into ClickUp tasks              │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  Ready for Review (3)                               │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │  SB Supply | Weekly Strategy - Dec 11       │   │
│  │  5 tasks · Client: SB Supply (auto)         │   │
│  │  [Review Tasks →]              [Dismiss]    │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │  Acme Corp | Q4 Planning - Dec 10           │   │
│  │  3 tasks · Client: Acme Corp (auto)         │   │
│  │  [Review Tasks →]              [Dismiss]    │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  Recently Processed (5)                    [See All]│
│                                                     │
│  Dec 11 · SB Supply · 4 tasks created               │
│  Dec 10 · Brand X · 2 tasks created                 │
│  Dec 9 · Client Y · Dismissed by Jeff               │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  Failed (1)                              [See All]  │
│                                                     │
│  Dec 8 · Meeting XYZ · Extraction failed [Retry]    │
└─────────────────────────────────────────────────────┘
```

### 7.2 Task Review

**Route:** `/debrief/meetings/[meetingId]`

```
┌─────────────────────────────────────────────────────┐
│  ← Back to Debrief                                  │
│                                                     │
│  SB Supply | Weekly Strategy - Dec 11               │
│  [View Original Notes ↗]                            │
│                                                     │
│  Client: [SB Supply ▼]  (editable dropdown)         │
└─────────────────────────────────────────────────────┘

┌─────────────────── TASKS (5) ───────────────────────┐
│                      [Approve All] [Reject All]     │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │  ☐ Run negative keyword audit for Whoosh    │   │
│  │                                              │   │
│  │  Brand: [Whoosh ▼]                          │   │
│  │  Assignee: [Anshuman ▼] (PPC Strategist)    │   │
│  │                                              │   │
│  │  Description:                                │   │
│  │  [Review search term reports and identify   ]│   │
│  │  [non-converting queries to add as negatives]│   │
│  │                                              │   │
│  │           [Approve ✓]    [Reject ✗]         │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │  ☐ Update Ranqer Pro 2 listing images       │   │
│  │  ...                                         │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  [Dismiss Meeting]          [Send to ClickUp (3)]   │
└─────────────────────────────────────────────────────┘
```

---

## 8. ClickUp Integration

**Phase 4 (Later):** This section describes the ClickUp integration once it’s implemented. Debrief MVP ships without pushing tasks into ClickUp.

### Task Creation
Uses shared ClickUp Service (see Command Center PRD Section 8.1.1).

```typescript
// For each approved task:
const brand = await getBrand(task.suggested_brand_id);
const assignee = await getProfile(task.suggested_assignee_id);

await clickupService.createTask({
  list_id: brand.clickup_list_id, // preferred; if null, ClickUp Service resolves a default list from the brand's space
  name: task.title,
  description: buildDescription(task, meeting),
  assignees: assignee?.clickup_user_id ? [assignee.clickup_user_id] : [],
});
```

### Task Description Template
```markdown
## Task
{task.description}

## Context
- Meeting: {meeting.title}
- Date: {meeting.meeting_date}
- [View Meeting Notes]({meeting.google_doc_url})

---
Created by Debrief
```

### Error Handling
- API error: Store in `clickup_error`, set status to `failed`
- Invalid Space ID: Log error, skip task, notify user
- User can retry failed tasks individually

---

## 9. API Surface

### Meeting Notes

- `POST /api/debrief/sync` — Trigger Google Drive sync
- `GET /api/debrief/meetings` — List meetings by status
- `GET /api/debrief/meetings/:id` — Get meeting with tasks
- `POST /api/debrief/meetings/:id/extract` — Retry LLM extraction
- `POST /api/debrief/meetings/:id/dismiss` — Dismiss meeting

### Tasks

- `PATCH /api/debrief/tasks/:id` — Update task (title, description, brand, assignee)
- `POST /api/debrief/tasks/:id/approve` — Approve task
- `POST /api/debrief/tasks/:id/reject` — Reject task
- `POST /api/debrief/meetings/:id/send-to-clickup` — Send approved tasks (Phase 4)

### Bulk Actions

- `POST /api/debrief/meetings/:id/approve-all` — Approve all pending tasks
- `POST /api/debrief/meetings/:id/reject-all` — Reject all pending tasks

---

## 10. Token Usage

```typescript
await logUsage({
  tool: "debrief",
  userId: user.id,
  meetingId: meeting.id,
  promptTokens: result.tokensIn,
  completionTokens: result.tokensOut,
  model: result.model,
  meta: {
    task_count: tasks.length,
    client_id: meeting.suggested_client_id
  }
});
```

---

## 11. Decisions (Resolved)

1. **Meeting frequency:** ~Weekly → Manual sync trigger (no aggressive polling)
2. **Multi-brand meetings:** Tasks route to specific brand's Space based on product mentions
3. **Task assignment:** "Anshuman will..." means "Ecomlabs will..." → role-based lookup, pre-select, allow override
4. **Historical backfill:** Start fresh, don't process old notes
5. **Duplicate meetings:** Both attendees get same notes → "Dismiss Meeting" button

---

## 12. Implementation Stages

### Stage 1: Dependencies
- [ ] Command Center shipped with `profiles.clickup_user_id` and `brands.clickup_space_id` / `brands.clickup_list_id` (manual entry is acceptable until ClickUp sync exists)

### Stage 2: Google Drive Integration
- [ ] Service account setup
- [ ] Domain-wide delegation
- [ ] Sync endpoint
- [ ] Meeting notes table + UI

### Stage 3: Task Extraction
- [ ] LLM prompt engineering
- [ ] Brand detection via keywords
- [ ] Assignee suggestion via role mapping
- [ ] Extracted tasks table + UI

### Stage 4: ClickUp Integration
- [ ] Send to ClickUp endpoint
- [ ] Task creation with description template
- [ ] Error handling + retry

### Stage 5: Polish
- [ ] Bulk actions
- [ ] Activity history
- [ ] Email notifications (future)

---

## 13. Future Roadmap

### SOP Matching & Enrichment
- Sync SOP templates from ClickUp → Supabase
- Generate embeddings for semantic search
- When creating task, find matching SOP
- Include SOP link/content in ClickUp task description

### Gmail Draft Integration
- After task approval, button to draft client email
- Opens Gmail compose with follow-up summary

### Slack Notifications
- Webhook when tasks are ready for review
- Posts to #debrief or DMs assignees

---

## 14. Success Metrics

- Time from meeting end → tasks in ClickUp backlog
- % of meeting action items that make it into ClickUp (vs. getting lost)
- User adoption: Are Jeff + Anshuman actually using Debrief weekly?
