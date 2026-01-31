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
