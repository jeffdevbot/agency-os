# Vara Slack Bot - Implementation Guide

> This document provides standalone implementation tasks for building Vara, the AI-powered Slack bot for Playbook. Each phase can be worked on independently by different agents.

**Related Documents:**
- [Playbook PRD](./playbook_prd.md) - Full product requirements
- Backend service patterns: `backend-core/app/services/`
- Existing Slack patterns: None (greenfield)

**Existing Schema (already in Supabase - no migration needed):**
- `profiles.slack_user_id` - Links Slack users to profiles
- `profiles.clickup_user_id` - For ClickUp task assignment
- `brands.clickup_space_id` / `brands.clickup_list_id` - Where to create tasks
- `agency_clients` - Client list for session picker
- `ai_token_usage` - Token logging table (use `meta->>'stage' = 'playbook'`)
- `debrief_meeting_notes` / `debrief_extracted_tasks` - For Debrief integration

**AI API:**
- Uses OpenAI (NOT Anthropic/Claude)
- Primary model: `gpt-4o` (env: `OPENAI_MODEL_PRIMARY`)
- Fallback: `gpt-4o-mini` (env: `OPENAI_MODEL_FALLBACK`)
- Key: `OPENAI_API_KEY`

---

## Phase 2: Bot Endpoint (Echo Test) ✅

**Status:** Code complete, pending deploy/test

**Goal:** Create the Slack event handler that receives DMs and echoes them back.

**Owner:** Backend developer
**Dependencies:** Phase 1 (Slack app created) ✅
**Estimated scope:** ~150 lines of code

### Context

Slack sends HTTP POST requests to our endpoint when events occur. We need to:
1. Verify the request signature using `SLACK_SIGNING_SECRET`
2. Handle the URL verification challenge (Slack sends this to verify our endpoint)
3. Receive `message.im` events and respond

### Files to Create

```
backend-core/app/api/routes/slack.py      # FastAPI route handler
backend-core/app/services/slack.py        # Slack service (signature verification, API calls)
```

### Environment Variables Required

Add to Render environment:
```
SLACK_BOT_TOKEN=xoxb-...        # From OAuth & Permissions
SLACK_SIGNING_SECRET=...        # From Basic Information → App Credentials
```

### Implementation Details

**1. Signature Verification (`services/slack.py`)**

```python
import hashlib
import hmac
import time

def verify_slack_signature(
    signing_secret: str,
    timestamp: str,
    body: bytes,
    signature: str,
) -> bool:
    """Verify request came from Slack."""
    # Reject requests older than 5 minutes
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False

    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    my_signature = "v0=" + hmac.new(
        signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(my_signature, signature)
```

**2. Route Handler (`api/routes/slack.py`)**

```python
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import httpx

router = APIRouter(prefix="/slack", tags=["slack"])

@router.post("/events")
async def slack_events(request: Request):
    body = await request.body()

    # Verify signature
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if not verify_slack_signature(SIGNING_SECRET, timestamp, body, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()

    # Handle URL verification challenge
    if payload.get("type") == "url_verification":
        return JSONResponse({"challenge": payload["challenge"]})

    # Handle message events
    if payload.get("type") == "event_callback":
        event = payload.get("event", {})
        if event.get("type") == "message" and not event.get("bot_id"):
            # Echo the message back
            await send_slack_message(
                channel=event["channel"],
                text=f"Echo: {event.get('text', '')}"
            )

    return JSONResponse({"ok": True})
```

**3. Send Message Helper**

```python
async def send_slack_message(channel: str, text: str, blocks: list | None = None):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {BOT_TOKEN}"},
            json={
                "channel": channel,
                "text": text,
                "blocks": blocks,
            }
        )
        return response.json()
```

### Testing

1. Deploy to Render
2. Update Slack app's Event Subscriptions URL to `https://tools.ecomlabs.ca/api/slack/events`
3. Slack will verify the endpoint automatically
4. DM Vara - it should echo your message back

### Success Criteria

- [ ] Slack URL verification passes
- [ ] DM to Vara echoes the message back
- [ ] Bot ignores its own messages (no infinite loop)

---

## Phase 3: Session Management & Client Resolution

**Goal:** Create session storage and resolve which client the user wants to work on.

**Owner:** Backend developer
**Dependencies:** Phase 2 completed
**Estimated scope:** ~200 lines of code

### Context

When a user DMs Vara, we need to:
1. Look up their profile using their Slack user ID
2. Check if they have an active session
3. If no active client, ask them to pick one
4. Store the session in Supabase

### Database Migration

Create migration file: `supabase/migrations/YYYYMMDDHHMMSS_create_playbook_sessions.sql`

```sql
-- Session storage for Vara Slack bot
CREATE TABLE playbook_slack_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slack_user_id text NOT NULL,
  profile_id uuid REFERENCES profiles(id),
  active_client_id uuid REFERENCES agency_clients(id),
  context jsonb DEFAULT '{}',
  last_message_at timestamptz DEFAULT now(),
  created_at timestamptz DEFAULT now()
);

-- Index for fast lookup by Slack user
CREATE INDEX idx_playbook_sessions_slack_user ON playbook_slack_sessions(slack_user_id);

-- Function to clean up stale sessions (>30 min inactive)
CREATE OR REPLACE FUNCTION cleanup_stale_playbook_sessions()
RETURNS void AS $$
BEGIN
  DELETE FROM playbook_slack_sessions
  WHERE last_message_at < now() - interval '30 minutes';
END;
$$ LANGUAGE plpgsql;
```

### Files to Create/Modify

```
backend-core/app/services/playbook_session.py   # Session management
backend-core/app/api/routes/slack.py            # Update to use sessions
```

### Implementation Details

**1. Session Service (`services/playbook_session.py`)**

```python
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

@dataclass
class PlaybookSession:
    id: UUID
    slack_user_id: str
    profile_id: Optional[UUID]
    active_client_id: Optional[UUID]
    context: dict
    last_message_at: datetime

class PlaybookSessionService:
    def __init__(self, supabase_client):
        self.db = supabase_client

    async def get_or_create_session(self, slack_user_id: str) -> PlaybookSession:
        """Get active session or create new one."""
        # Look for existing session < 30 min old
        result = await self.db.table("playbook_slack_sessions") \
            .select("*") \
            .eq("slack_user_id", slack_user_id) \
            .gt("last_message_at", datetime.utcnow() - timedelta(minutes=30)) \
            .single() \
            .execute()

        if result.data:
            return PlaybookSession(**result.data)

        # Create new session
        # First, look up profile by slack_user_id
        profile = await self.db.table("profiles") \
            .select("id") \
            .eq("slack_user_id", slack_user_id) \
            .single() \
            .execute()

        new_session = await self.db.table("playbook_slack_sessions") \
            .insert({
                "slack_user_id": slack_user_id,
                "profile_id": profile.data["id"] if profile.data else None,
            }) \
            .execute()

        return PlaybookSession(**new_session.data[0])

    async def set_active_client(self, session_id: UUID, client_id: UUID):
        """Set the active client for a session."""
        await self.db.table("playbook_slack_sessions") \
            .update({"active_client_id": str(client_id), "last_message_at": "now()"}) \
            .eq("id", str(session_id)) \
            .execute()

    async def touch_session(self, session_id: UUID):
        """Update last_message_at to keep session alive."""
        await self.db.table("playbook_slack_sessions") \
            .update({"last_message_at": "now()"}) \
            .eq("id", str(session_id)) \
            .execute()
```

**2. Client Selection Flow**

When no active client, send Block Kit message:

```python
async def send_client_picker(channel: str, clients: list[dict]):
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "Which client are you working on today?"}
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": client["name"]},
                    "action_id": f"select_client_{client['id']}",
                    "value": str(client["id"])
                }
                for client in clients[:10]  # Slack limit
            ]
        }
    ]
    await send_slack_message(channel, "Select a client", blocks)
```

### Reference Files

- Profiles table: Check `supabase/migrations/` for `profiles` schema
- Agency clients: Check for `agency_clients` table structure
- Existing Supabase patterns: `backend-core/app/core/supabase.py`

### Testing

1. Run migration locally: `supabase db push`
2. Manually add your `slack_user_id` to your profile in Supabase
3. DM Vara - should ask you to pick a client
4. Click a client button - session should update

### Success Criteria

- [ ] Session created on first DM
- [ ] Profile linked via slack_user_id
- [ ] Client picker shown when no active client
- [ ] Session persists across messages (within 30 min)
- [ ] Session expires after 30 min inactivity

---

## Phase 4: SOP Sync Engine ✅

**Status:** Code complete, pending deploy/test

**Goal:** Sync ClickUp SOP documents to Supabase for fast retrieval.

**Owner:** Backend developer
**Dependencies:** None (can run in parallel with Phase 2-3)
**Estimated scope:** ~250 lines of code
**Service:** Implemented in `backend-core` as `/admin/sync-sops` endpoint (can move to `worker-sync` later for scheduled runs)

### Context

SOPs live in ClickUp Docs. We need to:
1. Fetch SOPs from ClickUp using their v3 API
2. Store them in Supabase with metadata
3. Run as a scheduled job (daily) or on-demand

**Note:** The `worker-sync` service exists on Render but has no code yet. This is a good opportunity to set it up as a Python service similar to `backend-core` but for background jobs.

### ClickUp Doc Reference

From the PRD, known SOP documents:

| Doc Name | Doc ID | Page ID | Content |
|----------|--------|---------|---------|
| Playbook | `18m2dn-4417` | `18m2dn-1997` | N-gram SOP |
| Playbook | `18m2dn-4417` | (other pages) | Other SOPs |

API endpoint: `GET https://api.clickup.com/api/v3/workspaces/{workspace_id}/docs/{doc_id}/pages/{page_id}`

### Database Migration

Create: `supabase/migrations/YYYYMMDDHHMMSS_create_playbook_sops.sql`

```sql
-- SOP content cache
CREATE TABLE playbook_sops (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clickup_doc_id text NOT NULL,
  clickup_page_id text NOT NULL,
  name text NOT NULL,
  content_md text,
  category text,  -- 'ngram', 'seo', 'creative', etc.
  last_synced_at timestamptz DEFAULT now(),
  created_at timestamptz DEFAULT now(),

  UNIQUE(clickup_doc_id, clickup_page_id)
);

CREATE INDEX idx_playbook_sops_category ON playbook_sops(category);
```

### Files to Create

```
worker-sync/                              # New service directory
worker-sync/requirements.txt              # httpx, supabase-py
worker-sync/main.py                       # Entry point
worker-sync/services/sop_sync.py          # Sync logic
backend-core/app/api/routes/admin.py      # Manual sync trigger (optional)
```

**Alternative:** If you prefer to keep it in `backend-core` for now, create `backend-core/app/services/sop_sync.py` and add a FastAPI BackgroundTasks trigger or a `/admin/sync-sops` endpoint.

### Implementation Details

**1. SOP Sync Service (`services/sop_sync.py`)**

```python
import httpx
from typing import Optional

class SOPSyncService:
    WORKSPACE_ID = "42600885"  # From PRD

    # Known SOP pages to sync
    SOP_PAGES = [
        {"doc_id": "18m2dn-4417", "page_id": "18m2dn-1997", "category": "ngram"},
        # Add more as discovered
    ]

    def __init__(self, clickup_token: str, supabase_client):
        self.token = clickup_token
        self.db = supabase_client

    async def fetch_page(self, doc_id: str, page_id: str) -> dict:
        """Fetch a single page from ClickUp."""
        url = f"https://api.clickup.com/api/v3/workspaces/{self.WORKSPACE_ID}/docs/{doc_id}/pages/{page_id}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": self.token,
                    "Content-Type": "application/json"
                }
            )
            response.raise_for_status()
            return response.json()

    async def sync_all_sops(self):
        """Sync all known SOP pages to Supabase."""
        for sop in self.SOP_PAGES:
            try:
                page = await self.fetch_page(sop["doc_id"], sop["page_id"])

                await self.db.table("playbook_sops").upsert({
                    "clickup_doc_id": sop["doc_id"],
                    "clickup_page_id": sop["page_id"],
                    "name": page.get("name", "Untitled"),
                    "content_md": page.get("content", ""),
                    "category": sop["category"],
                    "last_synced_at": "now()"
                }).execute()

                print(f"Synced: {page.get('name')}")
            except Exception as e:
                print(f"Failed to sync {sop['doc_id']}/{sop['page_id']}: {e}")

    async def get_sop_by_category(self, category: str) -> Optional[dict]:
        """Get SOP content by category."""
        result = await self.db.table("playbook_sops") \
            .select("*") \
            .eq("category", category) \
            .single() \
            .execute()
        return result.data
```

### Reference Files

- ClickUp API script: `scripts/fetch-clickup-doc.ts` - Shows v3 API usage
- ClickUp service: `backend-core/app/services/clickup.py` - Shows auth patterns

### Environment Variables

Uses existing:
```
CLICKUP_API_TOKEN=pk_...
CLICKUP_TEAM_ID=42600885
```

### Testing

1. Run sync manually: Create a test script or admin endpoint
2. Check Supabase for `playbook_sops` data
3. Verify content_md matches ClickUp doc

### Success Criteria

- [ ] N-gram SOP synced to Supabase
- [ ] Content includes Loom links, Google Sheet links
- [ ] Sync is idempotent (can run multiple times)
- [ ] Error handling for API failures

---

## Phase 5: Deterministic Task Flow (N-gram)

**Goal:** Implement the first complete workflow - creating an N-gram research task.

**Owner:** Backend developer
**Dependencies:** Phase 2, 3, 4 completed
**Estimated scope:** ~300 lines of code

### Context

When a user says "start ngram for [client]", Vara should:
1. Fetch the n-gram SOP from Supabase
2. Create a ClickUp task with the SOP as the description
3. Assign it to the user
4. Return the task link

### Message Classification

Simple keyword matching for MVP:

```python
def classify_message(text: str) -> tuple[str, dict]:
    """Classify user message into intent and params."""
    text_lower = text.lower().strip()

    if any(kw in text_lower for kw in ["ngram", "n-gram", "keyword research"]):
        return ("create_ngram_task", {})

    if text_lower.startswith("switch to ") or text_lower.startswith("work on "):
        client_name = text_lower.split(" ", 2)[-1]
        return ("switch_client", {"client_name": client_name})

    # Default: exploratory (future: send to MCP)
    return ("exploratory", {})
```

### Implementation Details

**1. Update Slack Event Handler**

```python
@router.post("/events")
async def slack_events(request: Request):
    # ... signature verification ...

    if payload.get("type") == "event_callback":
        event = payload.get("event", {})
        if event.get("type") == "message" and not event.get("bot_id"):
            await handle_dm(event)

    return JSONResponse({"ok": True})

async def handle_dm(event: dict):
    slack_user_id = event["user"]
    channel = event["channel"]
    text = event.get("text", "")

    # Get or create session
    session = await session_service.get_or_create_session(slack_user_id)

    # Check if we have an active client
    if not session.active_client_id:
        await send_client_picker(channel, await get_user_clients(session.profile_id))
        return

    # Classify the message
    intent, params = classify_message(text)

    if intent == "create_ngram_task":
        await create_ngram_task(channel, session)
    elif intent == "switch_client":
        await handle_switch_client(channel, session, params["client_name"])
    else:
        await send_slack_message(channel, "I'm not sure what you need. Try: 'start ngram research'")
```

**2. N-gram Task Creation**

```python
async def create_ngram_task(channel: str, session: PlaybookSession):
    # Get client info
    client = await get_client_by_id(session.active_client_id)

    # Get SOP content
    sop = await sop_service.get_sop_by_category("ngram")
    if not sop:
        await send_slack_message(channel, "Error: N-gram SOP not found. Please contact admin.")
        return

    # Get user's ClickUp ID (stored in profile)
    profile = await get_profile(session.profile_id)
    clickup_user_id = profile.get("clickup_user_id")

    # Create task via existing ClickUp service
    task = await clickup_service.create_task_in_space(
        space_id=client["clickup_space_id"],
        name=f"N-gram Research: {client['name']}",
        description_md=sop["content_md"],
        assignee_ids=[clickup_user_id] if clickup_user_id else None,
    )

    # Send confirmation
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Task created!*\n<{task.url}|N-gram Research: {client['name']}>"
            }
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Assigned to you in {client['name']}'s space"}
            ]
        }
    ]
    await send_slack_message(channel, "Task created!", blocks)
```

### Reference Files

- ClickUp task creation: `backend-core/app/services/clickup.py` - `create_task_in_space()`
- Task creation API: `backend-core/app/api/routes/clickup.py` - Shows request/response patterns

### Data Requirements

**Already in schema (no migration needed):**
- `profiles.slack_user_id` - For session lookup
- `profiles.clickup_user_id` - For task assignment
- `brands.clickup_space_id` - Where to create tasks (on brands, not clients)

**Manual setup required:**
- Populate `slack_user_id` in profiles for test users (get from Slack admin or `/whois` command)

### Testing

1. Ensure your profile has `slack_user_id` and `clickup_user_id`
2. Ensure test client has `clickup_space_id`
3. DM Vara: "start ngram research"
4. Verify task created in ClickUp with proper formatting

### Success Criteria

- [ ] "start ngram" creates task in correct space
- [ ] Task description is the full SOP with links
- [ ] Task is assigned to the requesting user
- [ ] Confirmation message includes clickable link
- [ ] Error handling for missing data

---

## Phase 6: Interactions Handler (Button Clicks)

**Goal:** Handle Block Kit button interactions (client selection, approvals).

**Owner:** Backend developer
**Dependencies:** Phase 3 completed
**Estimated scope:** ~100 lines of code

### Context

When users click buttons in Slack messages, Slack sends a POST to our interactions endpoint.

### Files to Create/Modify

```
backend-core/app/api/routes/slack.py   # Add interactions endpoint
```

### Implementation Details

```python
@router.post("/interactions")
async def slack_interactions(request: Request):
    body = await request.body()

    # Verify signature (same as events)
    # ...

    # Slack sends form-encoded payload
    form_data = await request.form()
    payload = json.loads(form_data.get("payload", "{}"))

    action_type = payload.get("type")

    if action_type == "block_actions":
        actions = payload.get("actions", [])
        for action in actions:
            action_id = action.get("action_id", "")

            if action_id.startswith("select_client_"):
                client_id = action.get("value")
                user_id = payload["user"]["id"]

                # Update session
                session = await session_service.get_or_create_session(user_id)
                await session_service.set_active_client(session.id, client_id)

                # Get client name for confirmation
                client = await get_client_by_id(client_id)

                # Update the original message
                await update_slack_message(
                    channel=payload["channel"]["id"],
                    ts=payload["message"]["ts"],
                    text=f"Working on: {client['name']}",
                    blocks=[{
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"Now working on *{client['name']}*. What would you like to do?"}
                    }]
                )

    return JSONResponse({"ok": True})

async def update_slack_message(channel: str, ts: str, text: str, blocks: list):
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://slack.com/api/chat.update",
            headers={"Authorization": f"Bearer {BOT_TOKEN}"},
            json={"channel": channel, "ts": ts, "text": text, "blocks": blocks}
        )
```

### Success Criteria

- [ ] Client selection buttons work
- [ ] Original message updates after selection
- [ ] Session correctly stores selected client

---

## Phase 7: Debrief Integration

**Goal:** Allow users to query recent meetings and pull action items.

**Owner:** Backend developer
**Dependencies:** Phase 5 completed
**Estimated scope:** ~200 lines of code

### Context

Debrief stores meeting transcripts and extracts action items. Users should be able to:
1. Ask "what meetings did I have this week?"
2. See a list with buttons
3. Click to see action items
4. Create tasks from action items

### Existing Schema (from `20251215000004_debrief_core.sql`)

```sql
-- Meetings
debrief_meeting_notes (
  id, google_doc_id, title, meeting_date, owner_email,
  raw_content, summary_content, suggested_client_id, status
)

-- Extracted tasks from meetings
debrief_extracted_tasks (
  id, meeting_note_id, raw_text, title, description,
  suggested_brand_id, suggested_assignee_id, status,
  clickup_task_id  -- populated when sent to ClickUp
)
```

### Reference Files

Look for existing Debrief APIs:
```
backend-core/app/api/routes/           # Check for debrief routes
frontend-web/src/app/debrief/          # UI shows how data is fetched
supabase/migrations/20251215000004_debrief_core.sql  # Schema
```

### Implementation Details

**1. Add Intent Recognition**

```python
def classify_message(text: str) -> tuple[str, dict]:
    # ... existing patterns ...

    if any(kw in text_lower for kw in ["meeting", "meetings", "debrief"]):
        return ("list_meetings", {})

    # ...
```

**2. Meeting List Flow**

```python
async def handle_list_meetings(channel: str, session: PlaybookSession, supabase):
    # Get user's email from profile
    profile = await supabase.table("profiles").select("email").eq("id", str(session.profile_id)).single().execute()
    user_email = profile.data["email"]

    # Get recent meetings where user is owner
    result = await supabase.table("debrief_meeting_notes") \
        .select("id, title, meeting_date, status") \
        .eq("owner_email", user_email) \
        .in_("status", ["ready", "processed"]) \
        .order("meeting_date", desc=True) \
        .limit(5) \
        .execute()

    meetings = result.data
    if not meetings:
        await send_slack_message(channel, "No recent meetings found.")
        return

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": "*Recent meetings:*"}}
    ]

    for meeting in meetings:
        date_str = meeting["meeting_date"][:10] if meeting["meeting_date"] else "Unknown date"
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{meeting['title']}*\n{date_str}"
            },
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "View Tasks"},
                "action_id": f"view_meeting_{meeting['id']}",
                "value": str(meeting["id"])
            }
        })

    await send_slack_message(channel, "Recent meetings", blocks)
```

**3. Meeting Action Items**

```python
async def handle_view_meeting(channel: str, meeting_id: str, supabase):
    # Get meeting
    meeting_result = await supabase.table("debrief_meeting_notes") \
        .select("id, title") \
        .eq("id", meeting_id) \
        .single() \
        .execute()
    meeting = meeting_result.data

    # Get extracted tasks (action items)
    tasks_result = await supabase.table("debrief_extracted_tasks") \
        .select("id, title, description, status, clickup_task_id") \
        .eq("meeting_note_id", meeting_id) \
        .execute()
    tasks = tasks_result.data

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{meeting['title']}*"}}
    ]

    for task in tasks:
        # Skip if already created in ClickUp
        if task.get("clickup_task_id"):
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"~{task['title']}~ (already in ClickUp)"}
            })
        else:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"• {task['title']}"},
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Create Task"},
                    "action_id": f"create_task_from_debrief_{task['id']}",
                    "value": str(task["id"])
                }
            })

    if not tasks:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "_No action items extracted from this meeting._"}
        })

    await send_slack_message(channel, "Meeting details", blocks)
```

### Success Criteria

- [ ] "show my meetings" lists recent meetings from `debrief_meeting_notes`
- [ ] Clicking meeting shows extracted tasks from `debrief_extracted_tasks`
- [ ] "Create Task" button creates ClickUp task via existing service
- [ ] Updates `clickup_task_id` in `debrief_extracted_tasks` after creation
- [ ] Task includes meeting context in description

---

## Phase 8: AI Chat (Exploratory Queries)

**Goal:** Route non-deterministic queries through OpenAI with token logging.

**Owner:** Backend developer
**Dependencies:** Phases 2-5 completed
**Estimated scope:** ~300 lines of code

### Context

When the intent classifier returns "exploratory", we send the query to OpenAI. This is "gated" because:
1. We log all tokens used (for cost tracking)
2. We can throttle/limit usage per user
3. We might require approval for expensive queries

### Token Logging

Use the existing `ai_token_usage` table with `meta` for stage tracking:

```python
from supabase import create_client

async def log_tokens(
    supabase,
    user_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    stage: str = "playbook",
    extra_meta: dict = None
):
    await supabase.table("ai_token_usage").insert({
        "user_id": user_id,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "meta": {
            "stage": stage,
            "source": "vara",
            **(extra_meta or {})
        }
    }).execute()
```

### Reference Files

Look for existing OpenAI patterns:
```
frontend-web/src/lib/openai/           # If exists - check for patterns
backend-core/app/services/             # Check for any AI service
```

### Implementation Details

**1. OpenAI Service (`services/openai_chat.py`)**

```python
import openai
import os

class OpenAIChatService:
    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.model = os.environ.get("OPENAI_MODEL_PRIMARY", "gpt-4o")
        self.fallback_model = os.environ.get("OPENAI_MODEL_FALLBACK", "gpt-4o-mini")

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str = None,
        max_tokens: int = 1024
    ) -> tuple[str, dict]:
        """Returns (response_text, usage_dict)"""
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                max_tokens=max_tokens
            )
        except openai.RateLimitError:
            # Fallback to smaller model
            response = await self.client.chat.completions.create(
                model=self.fallback_model,
                messages=full_messages,
                max_tokens=max_tokens
            )

        return (
            response.choices[0].message.content,
            {
                "model": response.model,
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            }
        )
```

**2. System Prompt for Vara**

```python
VARA_SYSTEM_PROMPT = """You are Vara, an AI assistant for Brand Managers at Ecomlabs.
You help with:
- Creating tasks in ClickUp based on SOPs
- Answering questions about client work
- Summarizing meeting notes

Current context:
- Client: {client_name}
- User: {user_name}

Keep responses concise and actionable. If you can help create a specific task, offer to do so."""
```

### Success Criteria

- [ ] Exploratory queries sent to OpenAI
- [ ] Responses formatted nicely in Slack
- [ ] All tokens logged to `ai_token_usage` with `meta.stage = 'playbook'`
- [ ] Fallback to gpt-4o-mini on rate limit
- [ ] Error handling for API failures

---

## Environment Variables Summary

All required for full implementation:

```bash
# Slack (Phase 2) - NEW, add to Render
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...

# ClickUp (existing in Render)
CLICKUP_API_TOKEN=pk_...
CLICKUP_TEAM_ID=42600885

# Supabase (existing in Render)
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...

# OpenAI (existing in Render - check if already set)
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL_PRIMARY=gpt-4o
OPENAI_MODEL_FALLBACK=gpt-4o-mini
```

---

## Recommended Execution Order

1. **Phase 4** (SOP Sync) - ✅ DONE (pending deploy/test)
2. **Phase 2** (Echo Bot) - ✅ DONE (pending deploy/test)
3. **Phase 3** (Sessions) - Needed before task creation
4. **Phase 6** (Interactions) - Needed for button clicks
5. **Phase 5** (N-gram Flow) - First complete workflow
6. **Phase 7** (Debrief) - Enhancement
7. **Phase 8** (MCP) - Advanced feature

Phases 2+3+6 can be combined into one PR. Phase 4 is independent and can be a separate PR.

---

## Implementation Progress

| Phase | Status | Files |
|-------|--------|-------|
| Phase 1 (Slack App) | ✅ Done | Slack admin config |
| Phase 2 (Echo Bot) | ✅ Done | `services/slack.py`, `api/routes/slack.py` |
| Phase 3 (Sessions) | ✅ Done | `services/playbook_session.py` |
| Phase 4 (SOP Sync) | ✅ Done | `services/sop_sync.py` (tested: N-gram SOP 7481 chars synced) |
| Phase 5 (N-gram Flow) | ✅ Done | `api/routes/slack.py` (deterministic flow) |
| Phase 6 (Interactions) | ✅ Done | `api/routes/slack.py`, `services/slack.py` |
| Phase 7 (Debrief) | 🔲 Not started | |
| Phase 8 (AI Chat) | 🔲 Not started | |

---

## Vara 2.0: Architecture Revision

> **Status:** Planning complete, implementation pending
> **Date:** 2025-01-31

### The Problem with Phases 1-6

The original implementation created a **keyword dispatcher**, not an AI assistant:

```
Current: User says "ngram" → Hardcoded function → Verbatim SOP copied to task
```

This adds zero value over a button click. The AI should:
1. Understand natural language (not just keywords)
2. Gather context through conversation
3. **Personalize** the SOP with client specifics and user input
4. Present drafts for approval and refinement

### Gap Analysis

| PRD Feature | Phases 1-6 Built | Gap |
|-------------|------------------|-----|
| Natural conversation | Keyword matching only | ❌ Missing AI brain |
| Task preview + Approve/Reject/Edit | Immediate creation | ❌ No approval flow |
| Conversational refinement | None | ❌ No conversation state |
| AI enrichment (SOP + user context) | Verbatim SOP copy | ❌ No personalization |
| Chat history in session | Just client_id | ❌ No message storage |
| "What's the n-gram process?" | Not recognized | ❌ No SOP lookup |
| Gated MCP for ClickUp queries | None | ❌ Phase 8 not started |

**Core issue:** Even for a simple n-gram task, the system just copies the SOP. It can't:
- Ask "Which campaigns should I focus on?"
- Incorporate user's observation ("healthy chocolate terms not converting")
- Generate a task description that's specific to this situation

### Vara 2.0 Architecture

**New flow:** Every message → AI with tools → Response/Action

```
┌─────────────────────────────────────────────────────────────────┐
│                         EVERY MESSAGE                           │
└─────────────────────────────────────┬───────────────────────────┘
                                      │
                                      ▼
                        ┌─────────────────────────┐
                        │    OpenAI API           │
                        │  (system prompt + tools)│
                        └─────────────┬───────────┘
                                      │
         ┌────────────┬───────────────┼───────────────┬────────────┐
         ▼            ▼               ▼               ▼            ▼
    switch_client  lookup_sop   create_task_draft  query_clickup  respond
         │            │               │               │            │
         ▼            ▼               ▼               ▼            ▼
    Update session  Return SOP    Store draft +   MCP query    Text reply
                    content       show preview     (gated)
```

### System Prompt

```python
VARA_SYSTEM_PROMPT = """You are Vara, an AI assistant for Brand Managers at Ecomlabs.

## Your Role
Help BMs create well-structured ClickUp tasks based on SOPs. You don't just copy SOPs -
you adapt them with client-specific context and user input.

## Current Session
- User: {user_name} ({user_email})
- Active Client: {client_name} (or "none selected")
- Recent tasks for this client: {recent_tasks_summary}

## Available Tools
1. switch_client(client_name) - Change which client you're working on
2. lookup_sop(category) - Get SOP template (ngram, content_audit, etc.)
3. list_sops() - Show available SOP categories
4. create_task_draft(title, description, sop_category) - Create draft for approval
5. query_clickup(question) - Search ClickUp for tasks/info (ask before using - costs tokens)

## Task Creation Flow
When user wants to create a task:
1. Identify which SOP applies (or if it's ad-hoc)
2. Ask 1-2 clarifying questions to personalize:
   - What specific campaigns/products?
   - Any observations that triggered this?
   - Timeline/priority?
3. Use lookup_sop() to get the methodology
4. Create a draft that ADAPTS the SOP with:
   - Client name and specifics
   - User's answers to clarifying questions
   - Concrete action items (not generic placeholders)
5. Call create_task_draft() to show preview for approval

## Important Rules
- Never create tasks without user approval
- Keep the SOP structure/checklist intact, but personalize the details
- If no client selected, ask them to pick one first
- Be concise - this is Slack, not email
"""
```

### Tool Definitions

```python
VARA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "switch_client",
            "description": "Change which client the user is working on",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_name": {
                        "type": "string",
                        "description": "Name of the client to switch to"
                    }
                },
                "required": ["client_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_sop",
            "description": "Get SOP template content by category or alias. Accepts exact category names (e.g., 'ngram') or natural language aliases (e.g., 'keyword research', 'negative keywords'). Use this to understand the methodology before creating a task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "SOP category or alias (e.g., 'ngram', 'keyword research', 'negative keywords')"
                    }
                },
                "required": ["category"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_sops",
            "description": "List all available SOP categories",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_task_draft",
            "description": "Create a draft task for user approval. Call AFTER gathering context and adapting the SOP.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Task title (include client/brand name)"
                    },
                    "description": {
                        "type": "string",
                        "description": "Full task description - personalized SOP content with client specifics"
                    },
                    "sop_category": {
                        "type": "string",
                        "description": "Which SOP this is based on (or 'adhoc' for custom tasks)"
                    }
                },
                "required": ["title", "description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_clickup_task",
            "description": "Create a task in ClickUp. Only call AFTER user approves the draft via button click.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Task title"
                    },
                    "description": {
                        "type": "string",
                        "description": "Task description in markdown"
                    },
                    "list_id": {
                        "type": "string",
                        "description": "ClickUp list ID (uses client's default if not provided)"
                    }
                },
                "required": ["title", "description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_tasks",
            "description": "Get recent tasks for the active client. Use to provide context about what's already been done.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look back (default: 14)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum tasks to return (default: 10)"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_clickup",
            "description": "Search ClickUp for task information. Only use when user explicitly asks about existing tasks. This is expensive - the system will ask for confirmation before enabling this tool.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'overdue tasks', 'n-gram tasks from last week')"
                    },
                    "client_id": {
                        "type": "string",
                        "description": "Client ID to scope the search (uses active client if not provided)"
                    }
                },
                "required": ["query"]
            }
        }
    }
]
```

### Tool Constants

These constants define which tools are available in each path:

```python
# services/vara/tools.py

# Tier 1: Free tools (no API calls, just local operations)
TIER_1_TOOLS = [
    "switch_client",      # Update session state
    "lookup_sop",         # Read from Supabase cache
    "list_sops",          # Read from Supabase cache
    "create_task_draft",  # Store draft in session context
]

# Tier 2: Moderate tools (direct ClickUp API calls)
TIER_2_TOOLS = [
    "create_clickup_task",  # POST /list/{id}/task
    "get_recent_tasks",     # GET /list/{id}/task with filters
]

# Tier 3: Expensive tools (search/aggregation, high token usage)
TIER_3_TOOLS = [
    "query_clickup",  # Search across spaces, requires processing results
]

# Standard path: Tier 1 + Tier 2 (always available)
STANDARD_TOOLS = TIER_1_TOOLS + TIER_2_TOOLS

# All tools: includes gated Tier 3 (only after user confirms)
ALL_TOOLS = STANDARD_TOOLS + TIER_3_TOOLS

def get_tool_definitions(tools: list[str]) -> list[dict]:
    """Filter VARA_TOOLS to only include specified tool names."""
    return [t for t in VARA_TOOLS if t["function"]["name"] in tools]
```

### query_clickup Implementation

The `query_clickup` tool uses the **direct ClickUp API** (not the MCP server, which requires OAuth 2.1):

```python
# services/vara/tools.py

async def handle_query_clickup(args: dict, session, services: dict) -> str:
    """
    Search ClickUp for tasks matching the query.

    Uses direct ClickUp API v2:
    - GET /team/{team_id}/task with search parameters
    - Filters by space_id if client has ClickUp space configured
    """
    query = args.get("query", "").strip()
    if not query:
        return "No search query provided."

    client_id = args.get("client_id") or session.active_client_id
    if not client_id:
        return "No client selected. Please switch to a client first."

    # Get client's ClickUp space
    destination = services["sessions"].get_brand_destination_for_client(client_id)
    if not destination or not destination.get("clickup_space_id"):
        return "This client doesn't have a ClickUp space configured."

    clickup = services["clickup"]
    space_id = destination["clickup_space_id"]

    # Search tasks in the space
    # Note: ClickUp search is limited - we fetch recent tasks and filter
    try:
        tasks = await clickup.get_tasks_in_space(
            space_id=space_id,
            include_closed=False,
            order_by="updated",
            limit=50,
        )
    except Exception as e:
        return f"Failed to search ClickUp: {e}"

    if not tasks:
        return f"No tasks found in this client's space."

    # Format results for AI to process
    results = []
    for task in tasks[:20]:  # Limit to avoid token bloat
        status = task.get("status", {}).get("status", "unknown")
        due = task.get("due_date")
        due_str = f" (due: {due})" if due else ""
        results.append(f"- {task['name']} [{status}]{due_str}")

    return f"Found {len(tasks)} tasks. Top results:\n" + "\n".join(results)
```

**Future enhancement:** For richer search capabilities, integrate with [ClickUp's MCP server](https://developer.clickup.com/docs/connect-an-ai-assistant-to-clickups-mcp-server) which supports OAuth 2.1 with PKCE and provides orchestration, reporting, and advanced search features.

### Tier 2 Tool Implementations

**create_clickup_task** - Called after user approves a draft:

```python
async def handle_create_clickup_task(args: dict, session, services: dict) -> str:
    """Create task in ClickUp after user approval."""
    title = args.get("title", "").strip()
    description = args.get("description", "")

    if not title:
        return "Task title is required."

    client_id = session.active_client_id
    if not client_id:
        return "No client selected."

    destination = services["sessions"].get_brand_destination_for_client(client_id)
    if not destination or not destination.get("clickup_space_id"):
        return "Client doesn't have ClickUp configured."

    list_id = args.get("list_id") or destination.get("clickup_list_id")
    space_id = destination["clickup_space_id"]

    clickup = services["clickup"]
    try:
        task = await clickup.create_task_in_space(
            space_id=space_id,
            name=title,
            description_md=description,
            override_list_id=list_id,
        )
        return f"Task created: {task.url}"
    except Exception as e:
        return f"Failed to create task: {e}"
```

**get_recent_tasks** - Provides context about recent work:

```python
async def handle_get_recent_tasks(args: dict, session, services: dict) -> str:
    """Get recent tasks for context."""
    client_id = session.active_client_id
    if not client_id:
        return "No client selected."

    destination = services["sessions"].get_brand_destination_for_client(client_id)
    if not destination or not destination.get("clickup_space_id"):
        return "Client doesn't have ClickUp configured."

    days = args.get("days", 14)
    limit = args.get("limit", 10)

    clickup = services["clickup"]
    try:
        tasks = await clickup.get_tasks_in_space(
            space_id=destination["clickup_space_id"],
            days_back=days,
            limit=limit,
        )
    except Exception as e:
        return f"Failed to fetch tasks: {e}"

    if not tasks:
        return "No recent tasks found for this client."

    results = []
    for task in tasks:
        status = task.get("status", {}).get("status", "unknown")
        results.append(f"- {task['name']} [{status}]")

    return f"Recent tasks ({len(tasks)}):\n" + "\n".join(results)
```

**Note on task creation flow:** The AI typically uses `create_task_draft` to store a draft, which triggers a Slack preview with Approve/Edit/Cancel buttons. When the user clicks Approve, the button handler calls `create_clickup_task` directly (not the AI). The AI only calls `create_clickup_task` if explicitly instructed to skip the approval flow.

### SOP Mapping via Database Aliases

**Problem:** The SOP lookup relies on exact category matches (e.g., `category="ngram"`). If someone says "do keyword research" or "n-gram optimization", the AI might call `lookup_sop("keyword research")` which won't find the SOP stored as `category="ngram"`.

**Solution:** Store aliases directly in the `playbook_sops` table as a `text[]` column. Each SOP has a canonical `category` (e.g., "ngram") plus an array of `aliases` (e.g., `["n-gram", "keyword research", "negative keywords"]`).

**Database schema (already implemented):**

```sql
-- Migration: 20250201000001_playbook_sops_aliases.sql
ALTER TABLE public.playbook_sops
ADD COLUMN IF NOT EXISTS aliases text[] DEFAULT '{}';

-- GIN index for efficient array containment queries
CREATE INDEX IF NOT EXISTS idx_playbook_sops_aliases
  ON public.playbook_sops USING GIN (aliases);
```

**Seed data example:**

```sql
-- Migration: 20250201000002_seed_playbook_sops.sql
INSERT INTO public.playbook_sops (clickup_doc_id, clickup_page_id, category, name, aliases)
VALUES (
  '18m2dn-4417', '18m2dn-1997', 'ngram',
  'NGram Optimization SOP',
  ARRAY['n-gram', 'ngram', 'n-gram research', 'ngram research', 'keyword research',
        'n-gram optimization', 'ngram optimization', 'search term analysis',
        'search term optimization', 'negative keyword', 'negative keywords']
)
ON CONFLICT (clickup_doc_id, clickup_page_id) DO UPDATE SET
  category = EXCLUDED.category,
  name = EXCLUDED.name,
  aliases = EXCLUDED.aliases;
```

**Lookup implementation (in `services/sop_sync.py`):**

```python
async def get_sop_by_category_or_alias(self, query: str) -> dict[str, Any] | None:
    """
    Get SOP by category or alias.

    First tries exact category match, then falls back to alias lookup.
    This is the primary method for AI tool lookups.
    """
    # Try exact category first
    sop = await self.get_sop_by_category(query)
    if sop:
        return sop

    # Fall back to alias lookup (uses PostgreSQL array contains)
    return await self.get_sop_by_alias(query)

def _get_sop_by_alias_sync(self, alias: str) -> dict[str, Any] | None:
    """Get SOP by alias (sync version). Uses PostgreSQL array contains."""
    alias = (alias or "").strip().lower()
    if not alias:
        return None

    # PostgreSQL array contains: aliases @> ARRAY['keyword research']
    response = (
        self.db.table("playbook_sops")
        .select("*")
        .filter("aliases", "cs", f"{{{alias}}}")
        .limit(1)
        .execute()
    )
    rows = response.data if isinstance(response.data, list) else []
    return rows[0] if rows and isinstance(rows[0], dict) else None
```

**Using in `handle_lookup_sop`:**

```python
# services/vara/tools.py

async def handle_lookup_sop(args: dict, session, services: dict) -> str:
    """Fetch SOP content by category or alias."""
    query = args.get("category", "").strip()

    # Single call handles both exact category match and alias lookup
    sop = await services["sop"].get_sop_by_category_or_alias(query)

    if not sop:
        available = await services["sop"].list_categories()
        return f"No SOP found for: {query}. Available: {', '.join(available)}"

    return sop.get("content_md", "")
```

**Why database-driven is better:**

| Approach | Problem |
|----------|---------|
| Let AI figure it out | AI hallucinates categories or fails silently |
| Hardcoded Python dict | Must redeploy to add aliases |
| Fuzzy string matching | Unpredictable, might match wrong SOP |
| **Database aliases** | No redeploy needed, edit in Supabase, queryable |

**Maintenance:** When adding or updating SOP aliases, edit directly in Supabase (or add a new seed migration). No code changes required.

### Conversation Flow Example

```
User: I need to do ngram research for Mid-Day Squares

Vara: [internally calls lookup_sop("ngram")]
      Great, I'll help you create an N-gram optimization task for Mid-Day Squares.

      A few quick questions:
      1. Which campaigns should I focus on? (all, specific product lines, etc.)
      2. Any specific search terms or patterns you've noticed that triggered this?

User: Focus on the chocolate bar campaigns. I noticed a lot of spend on
      "healthy chocolate" terms that aren't converting.

Vara: [calls create_task_draft() with personalized content]

      ┌─────────────────────────────────────────────────────────────┐
      │ 📋 *N-gram Optimization: Mid-Day Squares - Chocolate Bars*  │
      │                                                              │
      │ *Focus:* Chocolate bar campaigns                            │
      │ *Trigger:* High spend on "healthy chocolate" terms          │
      │                                                              │
      │ ## Objective                                                 │
      │ Identify and negate non-converting search terms, with        │
      │ specific attention to "healthy chocolate" variations.        │
      │                                                              │
      │ ## Checklist                                                 │
      │ - [ ] Pull search term report (last 14 days)                │
      │ - [ ] Filter for "healthy chocolate" terms - check CVR      │
      │ - [ ] Identify other high-spend, low-CVR terms              │
      │ - [ ] Add negatives (NE for exact, NP for broad patterns)   │
      │ - [ ] Document in Keyword Master Sheet                      │
      │                                                              │
      │ [✓ Approve]  [Edit in ClickUp]  [Cancel]                    │
      └─────────────────────────────────────────────────────────────┘

User: Looks good, approve it

Vara: [creates task in ClickUp via existing service]
      ✅ Created: N-gram Optimization: Mid-Day Squares - Chocolate Bars
      https://app.clickup.com/t/xyz
      Assigned to you in the Mid-Day Squares space.
```

### What to Keep vs Rewrite

| Component | Keep | Rewrite | Notes |
|-----------|------|---------|-------|
| `services/playbook_session.py` | ✅ | 🔄 | Add message history methods |
| `services/sop_sync.py` | ✅ | | Already working |
| `services/clickup.py` | ✅ | | Task creation works |
| `services/slack.py` | ✅ | | post_message, update_message work |
| `api/routes/slack.py` | | 🔄 | Replace `_handle_dm_event` with AI flow |
| `_classify_message()` | | ❌ | Delete - AI handles intent |
| Button handlers | ✅ | 🔄 | Add Approve/Edit/Cancel for drafts |

### Modular Architecture

**Problem with current structure:** `api/routes/slack.py` is 364 lines and mixes HTTP handling with business logic. This makes it hard to test, maintain, and extend.

**Principle:** Routes handle HTTP only. Services handle business logic. Each module has one job.

```
backend-core/app/
├── api/routes/
│   └── slack.py                    # ONLY HTTP handling (~80 LOC)
│                                   # Parse request → call service → return response
│
├── services/
│   ├── slack.py                    # Slack API client (keep as-is)
│   ├── playbook_session.py         # Session CRUD (keep, add message methods)
│   ├── sop_sync.py                 # SOP fetching + alias lookup
│   │                               # get_sop_by_category_or_alias()
│   ├── clickup.py                  # ClickUp API (keep as-is)
│   │
│   └── vara/                       # NEW: Vara AI module
│       ├── __init__.py             # Exports VaraService
│       ├── service.py              # Main orchestrator (~150 LOC)
│       │                           # handle_message() → AI loop → response
│       ├── ai_client.py            # OpenAI wrapper (~100 LOC)
│       │                           # chat(), handle_tool_calls()
│       ├── tools.py                # Tool definitions + handlers (~200 LOC)
│       │                           # TOOL_DEFINITIONS, execute_tool()
│       └── prompts.py              # System prompts (~50 LOC)
│                                   # VARA_SYSTEM_PROMPT, build_context()
```

**Module responsibilities:**

| Module | Responsibility | Why Separate |
|--------|---------------|--------------|
| `routes/slack.py` | HTTP parsing, signature verification, response formatting | Thin layer, easy to test |
| `vara/service.py` | Conversation orchestration, tool loop | Core business logic |
| `vara/ai_client.py` | OpenAI API calls, retries, fallbacks | Swap models without touching logic |
| `vara/tools.py` | Tool JSON schemas + execution handlers | Add tools without touching AI code |
| `vara/prompts.py` | System prompt templates, context building | Non-engineers can edit prompts |
| `sop_sync.py` | SOP fetching + alias lookup | Database-driven, no redeploy to add aliases |

**Example: Thin route handler**

```python
# api/routes/slack.py - delegates ALL logic to service
@router.post("/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    _verify_request_or_401(signing_secret, request, body)
    payload = _parse_json(body)

    if payload.get("type") == "url_verification":
        return JSONResponse({"challenge": payload["challenge"]})

    if payload.get("type") == "event_callback":
        event = payload.get("event", {})
        if _is_user_dm(event):
            # ALL business logic delegated to VaraService
            background_tasks.add_task(
                vara_service.handle_message,
                slack_user_id=event["user"],
                channel=event["channel"],
                text=event.get("text", ""),
            )

    return JSONResponse({"ok": True})
```

**Example: VaraService orchestration**

```python
# services/vara/service.py
class VaraService:
    def __init__(
        self,
        ai_client: VaraAIClient,
        session_service: PlaybookSessionService,
        slack_service: SlackService,
        sop_service: SOPSyncService,
        clickup_service: ClickUpService,
    ):
        self.ai = ai_client
        self.sessions = session_service
        self.slack = slack_service
        self.sop = sop_service
        self.clickup = clickup_service

    async def handle_message(self, slack_user_id: str, channel: str, text: str):
        # 1. Get/create session
        session = self.sessions.get_or_create_session(slack_user_id)

        # 2. Build context for AI
        context = build_context(session)
        messages = context.get("messages", []) + [{"role": "user", "content": text}]

        # 3. AI conversation loop (handles tool calls)
        response = await self.ai.chat(messages=messages, tools=TOOL_DEFINITIONS)

        while response.tool_calls:
            tool_results = await self._execute_tools(response.tool_calls, session)
            response = await self.ai.continue_with_tools(messages, tool_results)

        # 4. Handle special responses (task draft → show preview)
        if session.context.get("pending_draft"):
            await self._send_task_preview(channel, session)
        else:
            await self.slack.post_message(channel=channel, text=response.content)

        # 5. Save message history
        self.sessions.append_message(session.id, "user", text)
        self.sessions.append_message(session.id, "assistant", response.content)

    async def _execute_tools(self, tool_calls: list, session) -> list:
        """Execute tool calls and return results."""
        results = []
        for call in tool_calls:
            result = await execute_tool(
                name=call.function.name,
                args=json.loads(call.function.arguments),
                session=session,
                services={
                    "sop": self.sop,
                    "clickup": self.clickup,
                    "sessions": self.sessions,
                }
            )
            results.append({"tool_call_id": call.id, "output": result})
        return results
```

**Example: Tool definitions and handlers**

```python
# services/vara/tools.py

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_sop",
            "description": "Get SOP template by category",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"}
                },
                "required": ["category"]
            }
        }
    },
    # ... other tools
]

async def execute_tool(name: str, args: dict, session, services: dict) -> str:
    """Route tool call to appropriate handler."""
    handlers = {
        "switch_client": handle_switch_client,
        "lookup_sop": handle_lookup_sop,
        "list_sops": handle_list_sops,
        "create_task_draft": handle_create_task_draft,
        "query_clickup": handle_query_clickup,
    }

    handler = handlers.get(name)
    if not handler:
        return f"Unknown tool: {name}"

    return await handler(args, session, services)

async def handle_lookup_sop(args: dict, session, services: dict) -> str:
    """Fetch SOP content by category or alias."""
    query = args.get("category", "").strip()
    # Uses get_sop_by_category_or_alias which checks exact category first,
    # then falls back to alias lookup in the database
    sop = await services["sop"].get_sop_by_category_or_alias(query)
    if not sop:
        available = await services["sop"].list_categories()
        return f"No SOP found for: {query}. Available: {', '.join(available)}"
    return sop.get("content_md", "")

async def handle_create_task_draft(args: dict, session, services: dict) -> str:
    """Store draft in session for user approval."""
    services["sessions"].update_context(session.id, {
        "pending_draft": {
            "title": args.get("title"),
            "description": args.get("description"),
            "sop_category": args.get("sop_category"),
        }
    })
    return "Draft created. Showing preview to user for approval."

# ... other handlers
```

### Session Context Schema

Expand the `context` JSONB field in `playbook_slack_sessions`:

```python
context = {
    "messages": [  # Last 10-15 messages for AI context
        {"role": "user", "content": "I need to do ngram..."},
        {"role": "assistant", "content": "Great, I'll help..."},
    ],
    "pending_draft": {  # Task awaiting approval
        "title": "N-gram Optimization: Mid-Day Squares",
        "description": "...",
        "sop_category": "ngram",
    },
    "gathered_context": {  # User's answers to clarifying questions
        "campaigns": "chocolate bar campaigns",
        "trigger": "healthy chocolate terms not converting",
    }
}
```

### Implementation Phases (Revised)

| Phase | Module | Description | Scope |
|-------|--------|-------------|-------|
| **2.1** | `vara/prompts.py` | System prompt + context builder | ~50 LOC |
| **2.2** | `vara/tools.py` | Tool definitions (JSON schemas) | ~80 LOC |
| **2.3** | `vara/ai_client.py` | OpenAI wrapper with tool loop | ~120 LOC |
| **2.4** | `vara/tools.py` | Tool handlers (execute_tool, handlers) | ~150 LOC |
| **2.5** | `vara/service.py` | VaraService orchestrator | ~150 LOC |
| **2.6** | `playbook_session.py` | Add `append_message()`, `get_messages()` | ~40 LOC |
| **2.7** | `routes/slack.py` | Slim down to HTTP-only, delegate to VaraService | ~-200 LOC |
| **2.8** | `routes/slack.py` | Approve/Edit/Cancel button handlers | ~60 LOC |
| **2.9** | `vara/ai_client.py` | Token logging for all AI calls | ~30 LOC |

**Note:** SOP alias resolution is handled by `sop_sync.py` (already implemented via `get_sop_by_category_or_alias()`). No separate mapping module needed.

**Total new code:** ~680 LOC
**Code removed:** ~200 LOC (business logic moved from routes to services)
**Net change:** ~480 LOC

### File Creation Order

Recommended order to minimize integration issues:

```
1. vara/__init__.py          # Empty, just makes it a package
2. vara/prompts.py           # No dependencies
3. vara/tools.py             # Tool definitions (no handlers yet)
4. vara/ai_client.py         # OpenAI wrapper
5. vara/tools.py             # Add handlers (uses sop_sync.get_sop_by_category_or_alias)
6. vara/service.py           # Wire everything together
7. playbook_session.py       # Add message history methods
8. routes/slack.py           # Refactor to use VaraService
```

**Note:** SOP alias lookup is already implemented in `services/sop_sync.py` via `get_sop_by_category_or_alias()`. No separate mapping module needed—aliases are stored in the database.

### Testing Strategy

Each module can be tested independently:

| Module | Test Approach |
|--------|---------------|
| `prompts.py` | Unit test `build_context()` with mock session |
| `tools.py` | Unit test each handler with mock services |
| `ai_client.py` | Mock OpenAI, test tool loop logic |
| `service.py` | Integration test with mocked dependencies |
| `routes/slack.py` | HTTP tests with mocked VaraService |

### Environment Variables

Existing (already configured):
```
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL_PRIMARY=gpt-4o
OPENAI_MODEL_FALLBACK=gpt-4o-mini
```

### Token Budget

| Operation | Estimated Tokens | Cost (GPT-4o) |
|-----------|------------------|---------------|
| Base context (system prompt + session) | ~1,500 | - |
| SOP lookup (returned to AI) | ~2,000 | - |
| User message + response | ~500 | - |
| **Per conversation turn** | ~4,000 | ~$0.04 |
| **Task creation (3-4 turns)** | ~15,000 | ~$0.15 |

Compare to current implementation: $0.00 (but zero value-add)

### Tool Tiers & Cost Control

To manage token costs, tools are organized into tiers based on expense:

| Tier | Tools | Cost | When Available |
|------|-------|------|----------------|
| **Tier 1 (Free)** | `switch_client`, `lookup_sop`, `list_sops`, `create_task_draft` | ~0 tokens | Always |
| **Tier 2 (Moderate)** | `create_clickup_task`, `get_recent_tasks` | ~500-1k tokens | Always |
| **Tier 3 (Expensive)** | `query_clickup` (MCP) | ~2-5k tokens | Gated - requires user confirmation |

**Key insight:** Cost control happens through **tool availability**, not AI routing. The AI doesn't decide which "lane" to use—we control which tools it can see.

### Two-Path Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER MESSAGE                             │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │     Pre-check: Is this  │
                    │   an exploratory query? │
                    └─────────────┬───────────┘
                                  │
              ┌───────────────────┴───────────────────┐
              │ NO                                    │ YES
              ▼                                       ▼
    ┌─────────────────────┐             ┌─────────────────────────┐
    │   STANDARD PATH     │             │   EXPLORATORY PATH      │
    │                     │             │   (Gated)               │
    │ Tools: Tier 1 + 2   │             │                         │
    │ - switch_client     │             │ Bot: "This requires     │
    │ - lookup_sop        │             │ searching ClickUp..."   │
    │ - list_sops         │             │                         │
    │ - create_task_draft │             │ [Continue] [Cancel]     │
    │ - create_clickup_task│            │                         │
    │ - get_recent_tasks  │             │ If Continue:            │
    │                     │             │ Tools: Tier 1 + 2 + 3   │
    │ AI handles naturally│             │ - query_clickup (MCP)   │
    └─────────────────────┘             └─────────────────────────┘
```

### Pre-check Function

Simple pattern matching to detect exploratory queries before calling the AI:

```python
# services/vara/routing.py

import re

EXPLORATORY_PATTERNS = [
    r"\bwhat('s| is| are)\b.*\b(tasks?|work|overdue|pending|done)\b",
    r"\bshow me\b.*\b(tasks?|work|what)\b",
    r"\bhow many\b.*\b(tasks?|things)\b",
    r"\blist\b.*\b(tasks?|overdue|pending)\b",
    r"\bfind\b.*\b(tasks?|work)\b",
    r"\bsearch\b",
    r"\bwhat did (we|i|you)\b",
    r"\bwhat have\b",
]

def is_exploratory_query(text: str) -> bool:
    """
    Detect if message needs MCP access (expensive).

    Returns True for queries like:
    - "What tasks are overdue for Whoosh?"
    - "Show me what's being worked on"
    - "Find the n-gram task from last week"

    Returns False for:
    - "Create an n-gram task"
    - "Switch to Home Gifts USA"
    - "Start keyword research"
    """
    text_lower = text.lower().strip()

    # Quick exit for obvious task creation intents
    if any(kw in text_lower for kw in ["create", "start", "make", "do", "run"]):
        return False

    # Check for exploratory patterns
    for pattern in EXPLORATORY_PATTERNS:
        if re.search(pattern, text_lower):
            return True

    return False
```

### Gating Flow for MCP

When pre-check detects an exploratory query:

```python
# services/vara/service.py

async def handle_message(self, slack_user_id: str, channel: str, text: str):
    session = self.sessions.get_or_create_session(slack_user_id)

    # Check if this needs MCP access
    if is_exploratory_query(text):
        # Store the query for later execution
        self.sessions.update_context(session.id, {
            "pending_mcp_query": text
        })

        # Send gating message
        await self.slack.post_message(
            channel=channel,
            text="This requires searching ClickUp, which uses more resources.",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "This requires searching ClickUp, which uses more resources.\n\nWould you like to continue?"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Continue"},
                            "style": "primary",
                            "action_id": "mcp_continue",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Cancel"},
                            "action_id": "mcp_cancel",
                        }
                    ]
                }
            ]
        )
        return

    # Standard path - AI with Tier 1+2 tools only
    await self._run_ai_with_tools(
        session=session,
        channel=channel,
        text=text,
        tool_names=STANDARD_TOOLS,  # switch_client, lookup_sop, list_sops,
                                     # create_task_draft, create_clickup_task, get_recent_tasks
    )

async def handle_mcp_continue(self, session, channel: str):
    """Called when user clicks Continue on exploratory query gate."""
    pending_query = session.context.get("pending_mcp_query")
    if not pending_query:
        return

    # Clear the pending query
    self.sessions.update_context(session.id, {"pending_mcp_query": None})

    # Run AI with ALL tools including query_clickup
    await self._run_ai_with_tools(
        session=session,
        channel=channel,
        text=pending_query,
        tool_names=ALL_TOOLS,  # Includes query_clickup (Tier 3)
    )

async def _run_ai_with_tools(self, session, channel: str, text: str, tool_names: list[str]):
    """Run AI conversation with specified tools available."""
    from .tools import get_tool_definitions, execute_tool

    # Get tool definitions for the specified tools
    tools = get_tool_definitions(tool_names)

    # Build context and run AI
    context = build_context(session)
    messages = context.get("messages", []) + [{"role": "user", "content": text}]

    response = await self.ai.chat(messages=messages, tools=tools)

    # Handle tool calls in a loop
    while response.tool_calls:
        tool_results = await self._execute_tools(response.tool_calls, session)
        response = await self.ai.continue_with_tools(messages, tool_results)

    # Send response and save history
    if session.context.get("pending_draft"):
        await self._send_task_preview(channel, session)
    else:
        await self.slack.post_message(channel=channel, text=response.content)

    self.sessions.append_message(session.id, "user", text)
    self.sessions.append_message(session.id, "assistant", response.content)
```

### Session Context & Chat Memory

**How sessions work:**

Sessions are defined by a 30-minute inactivity timeout. The `playbook_slack_sessions` table tracks:
- `slack_user_id` — Who this session belongs to
- `active_client_id` — Which client they're working on
- `context` — JSONB field for conversation state
- `last_message_at` — For timeout calculation

**Chat memory within a session:**

The `context` JSONB field stores the conversation history:

```python
context = {
    "messages": [
        {"role": "user", "content": "I need to do ngram for Mid-Day Squares", "ts": "2025-01-31T10:00:00Z"},
        {"role": "assistant", "content": "Great, I'll help you...", "ts": "2025-01-31T10:00:05Z"},
        {"role": "user", "content": "Focus on chocolate bars", "ts": "2025-01-31T10:00:30Z"},
        # ... more messages
    ],
    "pending_draft": {...},  # Task awaiting approval
    "pending_mcp_query": null,  # Query awaiting MCP gate approval
}
```

**Managing context size:**

| Strategy | Implementation |
|----------|----------------|
| **Keep recent messages** | Last 10-15 messages in full |
| **Summarize old messages** | If session runs long (>15 messages), summarize earlier ones |
| **Token budget** | Target ~4k tokens for messages (within 8k total context) |
| **Session timeout** | After 30 min inactivity, start fresh (old context not needed) |

**Adding message history methods to PlaybookSessionService:**

```python
# services/playbook_session.py (additions)

MAX_MESSAGES = 15

def append_message(self, session_id: str, role: str, content: str) -> None:
    """Add a message to session chat history."""
    session_id = (session_id or "").strip()
    if not session_id or not content:
        return

    # Fetch current context
    response = (
        self.db.table("playbook_slack_sessions")
        .select("context")
        .eq("id", session_id)
        .limit(1)
        .execute()
    )
    rows = response.data if isinstance(response.data, list) else []
    context = rows[0].get("context") if rows else {}
    if not isinstance(context, dict):
        context = {}

    messages = context.get("messages", [])
    if not isinstance(messages, list):
        messages = []

    # Add new message
    messages.append({
        "role": role,
        "content": content,
        "ts": _utc_now_iso(),
    })

    # Trim to max messages (keep most recent)
    if len(messages) > MAX_MESSAGES:
        messages = messages[-MAX_MESSAGES:]

    context["messages"] = messages

    self.db.table("playbook_slack_sessions").update({
        "context": context,
        "last_message_at": _utc_now_iso()
    }).eq("id", session_id).execute()

def get_messages(self, session_id: str) -> list[dict]:
    """Get chat history for AI context."""
    session_id = (session_id or "").strip()
    if not session_id:
        return []

    response = (
        self.db.table("playbook_slack_sessions")
        .select("context")
        .eq("id", session_id)
        .limit(1)
        .execute()
    )
    rows = response.data if isinstance(response.data, list) else []
    if not rows:
        return []

    context = rows[0].get("context")
    if not isinstance(context, dict):
        return []

    messages = context.get("messages", [])
    return messages if isinstance(messages, list) else []
```

**Why this approach works:**

1. **30-minute sessions are short** — Most sessions complete in 5-15 exchanges
2. **Context stays small** — 10-15 messages ≈ 2-4k tokens (well under limits)
3. **No cross-session memory needed** — The *output* of old sessions is the ClickUp tasks, which we surface via "recent tasks"
4. **Fresh starts are fine** — Like Claude Code, each session is self-contained
