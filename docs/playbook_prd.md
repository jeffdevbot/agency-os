# Playbook - AI-Powered Work Planning for Brand Managers

## Product Requirements Document (PRD)

**Version:** 2.0
**Product Area:** Agency OS → Playbook
**Status:** Draft
**Interface:** Slack Bot (DM mode)
**Bot Name:** Vara

> **v2.0 Architecture Shift:** Playbook now runs as a Slack bot ("Vara") rather than a custom web UI. Chat happens in Slack (where the team already works), editing happens in ClickUp (which is already a great editor). We don't reinvent the wheel.

**Relationship:**
- **Playbook** = the product (what we're building)
- **Vara** = the Slack bot (how users interact with it)
- This PRD describes requirements; see `docs/vara_implementation_guide.md` for technical implementation tasks

**Dependencies:**
- [Command Center](./07_command_center_prd.md) — Clients, brands, team assignments, ClickUp mappings
- [Debrief](./debrief_prd.md) — Meeting notes ingestion (Playbook can import from Debrief)
- **Slack API** — Bot messaging, Block Kit for approvals, DM conversations
- **ClickUp API** — Read docs (playbook knowledge), read tasks (recent activity), create tasks (outputs)
- **ClickUp MCP** (optional) — For exploratory queries that don't map to known workflows
- **BM Playbook Doc** — See [ClickUp Knowledge Sources](#clickup-knowledge-sources) below

---

## 1. Problem Statement

Brand Managers are the routing layer between **inputs** (data observations, client meetings, scheduled optimizations) and **outputs** (work tasks for Strategists and Specialists). Today this translation happens entirely in the BM's head using tribal knowledge and experience.

**Current pain points:**
- **Tribal knowledge is undocumented** — The "playbook" of what outputs to create from what inputs exists only in experienced BMs' heads
- **Manual task creation is slow** — After every meeting or data review, BMs manually create ClickUp tasks, often copying SOPs or writing from scratch
- **Context switching** — BMs jump between meeting notes, data sources, ClickUp, and team knowledge to decide what needs doing
- **Inconsistency** — Different BMs may create different outputs from the same inputs
- **Onboarding friction** — New BMs must learn the playbook through osmosis

**The opportunity:**
Codify the BM playbook into an AI system that:
1. Accepts any input type (observations, meeting notes, scheduled triggers)
2. Suggests appropriate task outputs based on domain knowledge
3. Routes tasks to the right roles/people
4. Allows human review and refinement before pushing to ClickUp

---

## 2. Solution Overview

**Playbook** is a Slack bot that helps Brand Managers create ClickUp tasks through natural conversation. It uses cached SOP knowledge to generate task drafts, presents them for approval via Slack's Block Kit, and pushes approved tasks directly to ClickUp.

**Core Workflow (One Task at a Time):**
```
┌─────────────────────────────────────────────────────────────────┐
│                      SLACK DM CONVERSATION                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  User: "Create an n-gram task for Home Gifts USA"              │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Bot: Here's the task I'll create:                         │ │
│  │                                                            │ │
│  │ **N-Gram Optimization**                                   │ │
│  │ Brand: Home Gifts USA | Marketplace: US                   │ │
│  │ Assignee: PPC Specialist (backlog)                        │ │
│  │                                                            │ │
│  │ [Preview in full...]                                      │ │
│  │                                                            │ │
│  │ [✓ Approve]  [✗ Reject]  [Edit in ClickUp]               │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  User: clicks [✓ Approve]                                      │
│                                                                 │
│  Bot: ✅ Created: https://app.clickup.com/t/86dzhmdzc          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Key Design Principles:**
- **Human-in-the-loop:** AI suggests, human approves. Nothing goes to ClickUp without explicit approval.
- **One task at a time:** Simpler flow, less fragile than batch operations.
- **Don't reinvent the wheel:** Slack for chat, ClickUp for editing. We just connect them.
- **SOP fidelity:** Task descriptions come directly from cached SOPs, not AI interpretation.

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         SLACK BOT                               │
│            (DM mode, Block Kit UI for approvals)                │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                        ┌─────▼─────┐
                        │ Classifier │  ← Determines request type
                        └─────┬─────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
     DETERMINISTIC       SOP LOOKUP          EXPLORATORY
     (Task Create)       (Reference)         (Gated MCP)
          │                   │                   │
          ▼                   ▼                   ▼
     Our API +           Supabase            ClickUp MCP
     SOP Templates       Knowledge           (user consents)
          │                   │                   │
          └─────────────┬─────┴───────────────────┘
                        ▼
                 Slack Response
            (text, buttons, links)
```

### 3.1 Request Classification

The classifier determines how to handle each user message:

| Classification | Example | Handler | Token Cost |
|----------------|---------|---------|------------|
| `TASK_CREATE` | "Create n-gram task for Brand X" | Deterministic API + SOP | Low |
| `SOP_LOOKUP` | "What's the n-gram process?" | Cached knowledge | Low |
| `TASK_QUERY` | "What's being worked on for Client X?" | Gated MCP | High |
| `GENERAL` | Open-ended questions | Gated MCP | High |

### 3.2 Gated MCP Access

For exploratory queries that don't map to known workflows, Playbook can use the ClickUp MCP. This is **gated** because MCP calls are token-expensive.

```
User: "What tasks are overdue for Whoosh?"

Bot: "This requires searching ClickUp, which uses more resources.
      [Continue] [Cancel]"

User: clicks [Continue]

Bot: [Uses ClickUp MCP to query tasks]
     "Found 3 overdue tasks for Whoosh: ..."
```

### 3.3 Why This Architecture

- **Slack is where the team works** — No new UI to learn, mobile access built-in
- **ClickUp is already a great editor** — Don't rebuild task editing
- **SOPs cached locally** — Fast, cheap access to process knowledge
- **MCP for flexibility** — Handle edge cases without hardcoding every workflow

### 3.4 Infrastructure Decisions

#### Slack User → Profile Mapping

When a user DMs Vara, Slack sends their Slack user ID (e.g., `U12345678`). We map this to Agency OS profiles:

```sql
-- Add to profiles table
ALTER TABLE profiles ADD COLUMN slack_user_id text UNIQUE;

-- Set manually for MVP (just Jeff)
UPDATE profiles SET slack_user_id = 'UXXXXXXXX' WHERE email = 'jeff@...';
```

Bot receives message → looks up `profiles` by `slack_user_id` → knows which user is talking.

#### Session Storage

Conversations are stored in Supabase with 30-minute timeout:

```sql
CREATE TABLE playbook_slack_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slack_user_id text NOT NULL,
  profile_id uuid REFERENCES profiles(id),
  active_client_id uuid REFERENCES agency_clients(id),
  context jsonb DEFAULT '{}',  -- brand, last task type, etc.
  last_message_at timestamptz DEFAULT now(),
  created_at timestamptz DEFAULT now()
);

CREATE INDEX idx_slack_sessions_user ON playbook_slack_sessions(slack_user_id);
CREATE INDEX idx_slack_sessions_active ON playbook_slack_sessions(last_message_at);
```

On each message:
1. Find session: `WHERE slack_user_id = ? AND last_message_at > now() - interval '30 minutes'`
2. If found: update `last_message_at`, use stored context
3. If not found: create new session

#### Credentials & Security

| Credential | Storage | Access |
|------------|---------|--------|
| `SLACK_BOT_TOKEN` | Render env var | Server-side only |
| `SLACK_SIGNING_SECRET` | Render env var | Server-side only |
| `CLICKUP_API_TOKEN` | Render env var | Server-side only |
| `SUPABASE_SERVICE_ROLE_KEY` | Render env var | Server-side only |

- Vara uses **service role key** to query Supabase (bypasses RLS for trusted backend)
- ClickUp API token is a single service token (not per-user OAuth)
- All secrets are server-side only, never exposed to client

#### AI API

Vara uses OpenAI for chat and intent classification:
- Primary model: `gpt-4o` (env: `OPENAI_MODEL_PRIMARY`)
- Fallback: `gpt-4o-mini` (env: `OPENAI_MODEL_FALLBACK`)
- API key: `OPENAI_API_KEY` (already configured in Render)

#### Token Logging

All AI calls are logged with `stage` for cost tracking:

```typescript
await logUsage({
  tool: "playbook",
  stage: "chat",  // or "mcp" for exploratory queries
  userId: user.id,
  // ... token counts
});
```

---

## 4. Input Types

### 4.1 Manual Observations (MVP)

**Format:** Free-form text
**Examples:**
- "ACOS up 5% week-over-week on the Pro 2 campaigns"
- "Client mentioned they want to launch in Germany Q2"
- "Conversion rate dipped on the main listing, might need image refresh"
- "Need to run the bi-weekly n-gram optimization"

**UI:** Multi-line text input with placeholder suggestions

### 4.2 Debrief Meeting Import

**Format:** Structured meeting notes from Debrief
**Behavior:**
- Soft auto-link: New Debrief meetings for the selected brand show as a notification badge
- One-click import into current session
- Meeting summary + extracted context becomes input

**UI:** "1 new meeting available" badge, expandable preview, "Import" button

### 4.3 Scheduled Optimizations (System-Generated)

**Format:** System-generated reminders based on optimization schedules
**Examples:**
- "N-gram optimization due (last run: 14 days ago)"
- "Monthly P&L review due (last run: 32 days ago)"
- "Bi-weekly bid adjustment due (last run: 15 days ago)"

**Data Source:** `playbook_optimization_schedules` table (see Data Model)

**UI:** Collapsible section showing what's due, one-click to add as input

### 4.4 ClickUp Recent Activity (Context)

**Format:** Summary of recent tasks for the brand
**Purpose:** Help AI understand what's already been done (avoid duplicates, build on recent work)
**Examples:**
- "Last week: 3 n-gram tasks completed, 2 listing updates in progress"
- "Recent: Bid adjustments on Brand campaigns (completed 3 days ago)"

**Data Source:** ClickUp API → `GET /list/{list_id}/task` with recent filter

**UI:** Read-only context panel, refreshable

### 4.5 Cross-Client Reference (On Request)

**Format:** Task details from another client's space
**Use Case:** "We just did this task for Client Y, can you review it and see if it applies here?"
**Behavior:**
- BM provides task URL or searches by keyword
- System fetches task details from ClickUp
- AI analyzes applicability to current brand

**UI:** "Reference another task" input, AI analysis in chat

---

## 5. Playbook Knowledge

### 5.1 Knowledge Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│                    PLAYBOOK KNOWLEDGE LAYERS                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Layer 1: BM Playbook Document                                  │
│  ─────────────────────────────────────────                      │
│  • Master document listing task types and decision trees        │
│  • Lives in ClickUp (easy to edit, version controlled)          │
│  • Synced to Supabase on demand (cached for AI context)         │
│  • Example: "When ACOS spikes >10%, run n-gram + check bids"    │
│                                                                 │
│  Layer 2: SOP Documents (Linked)                                │
│  ─────────────────────────────────────────                      │
│  • Detailed SOPs referenced in the playbook                     │
│  • Fetched on-demand when creating specific task types          │
│  • Example: "N-Gram SOP" linked from playbook entry             │
│                                                                 │
│  Layer 3: Task Type Definitions                                 │
│  ─────────────────────────────────────────                      │
│  • Structured data: task type → default role → template         │
│  • Stored in Supabase for fast lookup                           │
│  • Example: "n_gram_optimization" → PPC Specialist → template   │
│                                                                 │
│  Layer 4: Brand-Specific Context                                │
│  ─────────────────────────────────────────                      │
│  • From Command Center: team assignments, keywords, markets     │
│  • Recent activity from ClickUp                                 │
│  • Optimization schedules                                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 ClickUp Docs Integration

**Reading the Playbook Doc:**
- Admin configures the ClickUp Doc ID for the BM Playbook in settings
- System uses ClickUp Docs API: `GET /doc/{doc_id}/pages`
- Content returned in markdown format
- Cached in Supabase with manual "Refresh" trigger

**Why ClickUp for the Playbook?**
- BMs can edit it directly in ClickUp (familiar UI)
- Version history built-in
- Links to SOPs work naturally
- No need to build a custom editor

**Sync Strategy:**
- On-demand sync (admin clicks "Refresh Playbook")
- Cached content used for AI context
- Last sync timestamp shown in UI

### 5.3 Task Type Registry

Structured definitions for common task types:

```sql
-- See Data Model section for full schema
playbook_task_types (
  slug: "n_gram_optimization",
  name: "N-Gram Optimization",
  default_role: "ppc_specialist",  -- FK to agency_roles
  description_template: "Run n-gram analysis for {brand} campaigns...",
  estimated_hours: 2,
  sop_doc_id: "abc123"  -- Optional ClickUp Doc ID
)
```

**Usage:**
- When AI suggests a task, it references task types
- Templates provide consistent task descriptions
- Default role enables auto-routing

### 5.4 ClickUp Knowledge Sources {#clickup-knowledge-sources}

These are the authoritative ClickUp documents that feed the Playbook AI system. Both are **living documents** that will continue to expand over time.

#### Brand Manager Playbook (Cross-Client)

| Field | Value |
|-------|-------|
| **Doc ID** | `18m2dn-4177` |
| **Main Page ID** | `18m2dn-1337` |
| **URL** | https://app.clickup.com/42600885/docs/18m2dn-4177 |
| **Purpose** | Master decision tree for BMs: input types → categories → owners → task templates |

**Key Sections:**
- Section 0: How to Use This Playbook
- Section 1: Choose the Client Path (New vs Existing)
- Section 2: New Client Path (workstreams, owners, task templates)
- Section 3: Existing Client Path (data signals, requests, recurring work)
- Section 4: Inputs → Categories → Owners (routing rules)
- Section 5: Task Creation Standards (naming, assignees, required fields)
- Section 6: Maintenance & Improvement

**Sub-pages:**
- `18m2dn-1357` — New Client Onboarding & Strategy Roadmap (Template)

#### SOP Library

| Field | Value |
|-------|-------|
| **Doc ID** | `18m2dn-4257` |
| **Main Page ID** | `18m2dn-1437` |
| **URL** | https://app.clickup.com/42600885/docs/18m2dn-4257 |
| **Purpose** | Central index of all SOPs with links to detailed SOP docs |

**Categories:**
- PPC (Weekly, Bi-Weekly, Monthly optimizations, Keyword Master Template)
- Account Health & Hygiene
- Catalog & Inventory
- Brand Management & Onboarding

**Linked SOP Docs (examples):**
- `18m2dn-4377` — PPC - Advertising Optimizations - Weekly
- `18m2dn-4417` — PPC - Advertising Optimizations - Bi-Weekly
- `18m2dn-4397` — PPC - Advertising Optimizations - Monthly
- `18m2dn-4457` — Account Health & Hygiene - Bi-Weekly
- `18m2dn-4477` — FBA Restock Request SOP

#### Complete Doc & Page ID Reference

This table provides quick lookup for all known ClickUp doc and page IDs. **Page IDs are required to fetch content via API.**

| Doc Name | Doc ID | Page ID | Notes |
|----------|--------|---------|-------|
| **Brand Manager Playbook** | `18m2dn-4177` | `18m2dn-1337` | Master decision tree |
| ↳ New Client Template | `18m2dn-4177` | `18m2dn-1357` | Onboarding subpage |
| **SOP Library** | `18m2dn-4257` | `18m2dn-1437` | Index of all SOPs |
| **PPC - Weekly** | `18m2dn-4377` | *TBD* | Weekly optimizations |
| **PPC - Bi-Weekly** | `18m2dn-4417` | `18m2dn-1997` | Contains NGram SOP |
| **PPC - Monthly** | `18m2dn-4397` | *TBD* | Monthly optimizations |
| **PPC - Keyword Master** | `18m2dn-4437` | *TBD* | Keyword template |
| **Account Health - Bi-Weekly** | `18m2dn-4457` | *TBD* | Health & hygiene |
| **FBA Restock SOP** | `18m2dn-4477` | *TBD* | Inventory |
| **Portfolio Budgets - Weekly** | `18m2dn-4497` | *TBD* | Budget management |

*Update this table as new page IDs are discovered. To find a page ID, open the doc in ClickUp and extract from the URL: `https://app.clickup.com/WORKSPACE/docs/DOC_ID/PAGE_ID`*

#### API Access Notes

**ClickUp Docs API v3:**
- Workspace ID: `42600885`
- Auth: Personal API token (from ClickUp Settings → Apps → API Token)
- Endpoint pattern: `GET /api/v3/workspaces/{workspace_id}/docs/{doc_id}/pages/{page_id}`

**Important:** ClickUp Docs 3.0 separates docs from pages:
- A **Doc** is a container (metadata only via API)
- A **Page** contains the actual content
- URL format: `https://app.clickup.com/WORKSPACE/docs/DOC_ID/PAGE_ID`
- To fetch content, you need the **page ID**, not just the doc ID

**CLI Tool:** Use `scripts/fetch-clickup-doc.ts` to fetch docs:
```bash
npx ts-node scripts/fetch-clickup-doc.ts list                    # List all docs
npx ts-node scripts/fetch-clickup-doc.ts 18m2dn-4177             # Fetch doc info
npx ts-node scripts/fetch-clickup-doc.ts 18m2dn-4177/18m2dn-1337 # Fetch specific page
```

#### ClickUp Tasks API v2

**Endpoint:** `POST /api/v2/list/{list_id}/task` (create) | `PUT /api/v2/task/{task_id}` (update)

**Supported Task Fields:**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | string | ✅ | Task title |
| `markdown_description` | string | ✅ | Markdown description (renders formatted in ClickUp UI) |
| `status` | string | ✅ | Must match list status (default: "backlog") |
| `assignees` | number[] | ❌ | Array of ClickUp user IDs |
| `parent` | string | ❌ | Parent task ID (for subtasks) |
| `due_date` | number | ❌ | Unix timestamp in milliseconds |
| `start_date` | number | ❌ | Unix timestamp in milliseconds |
| `priority` | number | ❌ | 1=Urgent, 2=High, 3=Normal, 4=Low |
| `tags` | string[] | ❌ | Array of tag names (e.g., "PPC", "Bi-Weekly") |
| `notify_all` | boolean | ❌ | Notify assignees on creation (default: true) |

**Not used:** `time_estimate`, `custom_fields`, `links_to`, `checklist`

**Assignee updates** use a special format:
```json
{ "assignees": { "add": [54809463], "rem": [] } }
```

**CLI Tool:** Use `scripts/clickup-tasks.ts` for task operations:
```bash
npx ts-node scripts/clickup-tasks.ts lists <space_id>           # List all lists
npx ts-node scripts/clickup-tasks.ts create <list_id> <name>    # Create task
npx ts-node scripts/clickup-tasks.ts subtask <parent_id> <name> # Create subtask
npx ts-node scripts/clickup-tasks.ts update <task_id> <name>    # Update task
npx ts-node scripts/clickup-tasks.ts assign <task_id> <user_id> # Assign task
```

**Test Space:** `90100444966` (Home Gifts USA) | **Test List:** `901002557304`

---

## 6. AI Analysis & Suggestions

### 6.1 Context Management Strategy

Playbook uses **session-scoped context** with tiered loading to manage token usage effectively.

#### Context Scope

| Scope | What AI Sees | Rationale |
|-------|--------------|-----------|
| **Current session** | Full chat history | Needed for coherent conversation |
| **Previous sessions** | Nothing by default | Sessions are self-contained (like Claude Code) |
| **On-demand** | Explicit request only | BM can ask "what did we do last time?" |

**Why session-scoped?**
- Each session is a discrete "work planning" unit with a beginning (inputs) and end (push to ClickUp)
- The *output* of old sessions is the ClickUp tasks, which we surface via "Recent ClickUp Activity"
- Chat history becomes less relevant once tasks are created

**Session summaries (future):** Store AI-generated 1-2 sentence summary per session for history view.

#### Context Layers (Token Budget)

```
┌─────────────────────────────────────────────────────────────────┐
│                    CONTEXT LAYERS                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ALWAYS LOADED (base context for every AI call)                │
│  ──────────────────────────────────────────────                │
│  • System prompt (role, output format)          ~500 tokens    │
│  • BM Playbook doc (cached)                     ~2-4k tokens   │
│  • Task type definitions                        ~500 tokens    │
│  • Brand context (name, keywords, team)         ~200 tokens    │
│  • Current session inputs                       ~500-1k tokens │
│                                                                 │
│  LOADED PER-SESSION                                            │
│  ──────────────────────────────────────────────                │
│  • Session chat history (current session)       variable       │
│  • Recent ClickUp tasks (last 14 days, summary) ~500 tokens    │
│  • Scheduled optimizations due                  ~200 tokens    │
│                                                                 │
│  LOADED ON-DEMAND (only when referenced)                       │
│  ──────────────────────────────────────────────                │
│  • SOP doc content (when creating specific task type)          │
│  • Cross-client task details (when BM asks)                    │
│  • Historical session summary (if explicitly requested)        │
│                                                                 │
│  Base context: ~4-6k tokens                                    │
│  With chat history: ~8-15k tokens typical                      │
│  Max with on-demand: ~20-25k tokens                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Chat history management:**
- Keep last ~10-15 messages in full
- If session runs long, summarize earlier messages
- Most sessions complete in 5-15 exchanges

### 6.2 Context Assembly

When BM provides inputs, the system assembles context for the AI:

```
SYSTEM CONTEXT:
- BM Playbook document (cached markdown)
- Task type definitions with templates
- Brand info: {name}, {keywords}, {marketplaces}
- Team assignments: {role → person} from Command Center
- Recent ClickUp activity: {last 14 days of tasks}
- Scheduled optimizations: {what's due}

USER INPUT:
- Manual observations: "{free text}"
- Meeting notes: "{imported from Debrief}"
- Scheduled items selected: "{list}"
```

```typescript
// Context assembly example
async function buildContext(session: Session): Promise<AIContext> {
  const [playbook, taskTypes, brand, recentTasks, schedules] = await Promise.all([
    getPlaybookDoc(),           // cached, ~3k tokens
    getTaskTypes(),             // small, ~500 tokens
    getBrandContext(session.brand_id),
    getRecentClickUpTasks(session.brand_id, { days: 14 }),
    getDueSchedules(session.brand_id),
  ]);

  const sessionInputs = await getSessionInputs(session.id);
  const chatHistory = await getChatHistory(session.id, { limit: 15 });

  return assemblePrompt({
    playbook, taskTypes, brand, recentTasks,
    schedules, sessionInputs, chatHistory
  });
}
```

### 6.3 Suggestion Format

AI returns structured suggestions:

```json
{
  "suggestions": [
    {
      "id": "sug_001",
      "task_type": "n_gram_optimization",
      "title": "Run n-gram optimization for Pro 2 campaigns",
      "description": "Review search term reports for the last 14 days...",
      "reasoning": "ACOS up 5% suggests non-converting search terms need negation",
      "suggested_role": "ppc_specialist",
      "priority": "high",
      "related_input": "ACOS up 5% observation"
    },
    {
      "id": "sug_002",
      "task_type": "bid_adjustment",
      "title": "Adjust bids on top 10 campaigns by ACOS",
      "description": "Review and adjust bids on campaigns with ACOS >30%...",
      "reasoning": "Follow-up to n-gram to optimize spend efficiency",
      "suggested_role": "ppc_specialist",
      "priority": "medium",
      "related_input": "ACOS up 5% observation"
    }
  ],
  "questions": [
    "Should I also suggest a listing review? The conversion rate dip could indicate image/copy issues."
  ]
}
```

### 6.4 Routing Logic

Task routing uses Command Center data:

1. AI suggests a role (e.g., `ppc_specialist`)
2. System looks up brand-level assignment for that role
3. If no brand-level, falls back to client-level assignment
4. Task is pre-populated with the assigned person's info

**MVP Simplification:** Tasks go to the brand's ClickUp backlog without assignee. Team member assignment deferred to later phase.

---

## 7. Slack Interface

### 7.1 Task Creation Flow (One at a Time)

```
┌─────────────────────────────────────────────────────────────────┐
│  SLACK DM: @playbook                                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  You: Create an n-gram task for Home Gifts USA                 │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  📋 *N-Gram Optimization*                                  │ │
│  │                                                            │ │
│  │  *Brand:* Home Gifts USA                                  │ │
│  │  *Marketplace:* US                                        │ │
│  │  *Assignee:* PPC Specialist (backlog)                     │ │
│  │                                                            │ │
│  │  _Standardize how N-Gram-based search term analysis..._   │ │
│  │                                                            │ │
│  │  ┌──────────┐ ┌──────────┐ ┌────────────────┐            │ │
│  │  │ ✓ Approve│ │ ✗ Reject │ │ Edit in ClickUp│            │ │
│  │  └──────────┘ └──────────┘ └────────────────┘            │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  You: [clicks ✓ Approve]                                       │
│                                                                 │
│  Bot: ✅ Created: https://app.clickup.com/t/86dzhmdzc          │
│       Task is in Home Gifts USA backlog.                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Edit in ClickUp Flow

When user needs to modify a task before approval:

```
┌─────────────────────────────────────────────────────────────────┐
│  You: [clicks "Edit in ClickUp"]                               │
│                                                                 │
│  Bot: 📝 Draft created: https://app.clickup.com/t/86dztemp     │
│       Edit it in ClickUp, then come back and tell me when      │
│       you're done.                                              │
│                                                                 │
│  You: done                                                      │
│                                                                 │
│  Bot: ✅ Task finalized in ClickUp.                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 7.3 Conversational Refinement

```
┌─────────────────────────────────────────────────────────────────┐
│  You: Create an n-gram task for Home Gifts USA                 │
│                                                                 │
│  Bot: [shows task preview with buttons]                        │
│                                                                 │
│  You: Actually make it for the Pro 2 campaigns specifically    │
│                                                                 │
│  Bot: Updated. Here's the revised task:                        │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  📋 *N-Gram Optimization - Pro 2 Campaigns*               │ │
│  │  ...                                                       │ │
│  │  [✓ Approve] [✗ Reject] [Edit in ClickUp]                 │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 7.4 Exploratory Query (Gated MCP)

```
┌─────────────────────────────────────────────────────────────────┐
│  You: What tasks are overdue for Whoosh?                       │
│                                                                 │
│  Bot: This requires searching ClickUp, which uses more         │
│       resources.                                                │
│                                                                 │
│       ┌────────────┐ ┌──────────┐                              │
│       │ Continue   │ │ Cancel   │                              │
│       └────────────┘ └──────────┘                              │
│                                                                 │
│  You: [clicks Continue]                                        │
│                                                                 │
│  Bot: Found 3 overdue tasks for Whoosh:                        │
│       • "Update Pro 2 listings" (5 days overdue)               │
│       • "Monthly P&L review" (2 days overdue)                  │
│       • "Competitor analysis Q1" (1 day overdue)               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 7.5 Block Kit Structure

Task preview uses Slack Block Kit:

```json
{
  "blocks": [
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "📋 *N-Gram Optimization*\n\n*Brand:* Home Gifts USA\n*Marketplace:* US\n*Assignee:* PPC Specialist (backlog)"
      }
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "_Standardize how N-Gram-based search term analysis is used to identify and apply Negative Exact (NE) and Negative Phrase (NP) keywords..._"
      }
    },
    {
      "type": "actions",
      "elements": [
        {
          "type": "button",
          "text": { "type": "plain_text", "text": "✓ Approve" },
          "style": "primary",
          "action_id": "approve_task",
          "value": "task_123"
        },
        {
          "type": "button",
          "text": { "type": "plain_text", "text": "✗ Reject" },
          "style": "danger",
          "action_id": "reject_task",
          "value": "task_123"
        },
        {
          "type": "button",
          "text": { "type": "plain_text", "text": "Edit in ClickUp" },
          "action_id": "edit_in_clickup",
          "value": "task_123"
        }
      ]
    }
  ]
}
```

### 7.6 Session Start Flow

When user wants to work on a specific client, bot gathers context upfront:

```
┌─────────────────────────────────────────────────────────────────┐
│  User: Let's work on some tasks for SB Supply                  │
│                                                                 │
│  Bot: 🔍 Setting up session for *SB Supply*...                 │
│                                                                 │
│       ✅ ClickUp space: configured (Whoosh Space)              │
│       ✅ 2 brands: Whoosh, Pro Line                            │
│       📋 1 recent meeting found:                               │
│          • "SB Supply Weekly - Jan 27" (3 tasks ready)         │
│                                                                 │
│       How would you like to proceed?                           │
│                                                                 │
│       [Process Meeting] [Create Task] [Just Chat]              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Session setup performs:**
1. Resolve client name → client ID (fuzzy match)
2. Fetch brands for that client from Command Center
3. Verify ClickUp space/list IDs are configured
4. Check Debrief for recent meetings (status = `ready`)
5. Present summary with action options

**Session context persists:**
- Bot remembers active client for follow-up messages
- No need to repeat client name for each task
- Context expires after 30 min inactivity

### 7.7 Debrief Meeting Integration

Two ways to access Debrief meetings:

**A. Browse meetings (pull):**
```
User: What meetings are ready?

Bot: 📋 *Recent meetings with tasks:*

     1. SB Supply Weekly - Jan 27
        3 tasks · Whoosh, Pro 2
        [Select]

     2. Home Gifts Monthly - Jan 25
        2 tasks · Home Gifts USA
        [Select]
```

**B. Via session start (contextual):**
```
User: Let's work on SB Supply

Bot: [session setup]
     📋 1 recent meeting found...
     [Process Meeting] [Create Task] [Just Chat]

User: [clicks Process Meeting]

Bot: *SB Supply Weekly - Jan 27* has 3 tasks.
     Showing task 1 of 3:

     [task preview with Approve/Skip/Edit buttons]
```

**Task approval uses existing Debrief API:**
- `GET /api/debrief/meetings?status=ready` — list meetings
- `GET /api/debrief/meetings/:id` — get meeting with tasks
- `POST /api/debrief/tasks/:id/send-to-clickup` — create in ClickUp

**One task at a time flow:**
1. Bot shows task 1 of N with Approve/Skip/Edit buttons
2. Approve → calls send-to-clickup → shows success → advances to next
3. Skip → advances to next (task stays in Debrief as pending)
4. Edit in ClickUp → creates draft, returns link, user edits, then confirms
5. After last task: "All done! 2 created, 1 skipped."

---

## 8. Data Model

> **MVP Note:** The Slack bot MVP uses a simpler data model. The `playbook_slack_sessions` table (Section 3.4) handles session state. The tables below are reference designs for future phases when we need richer session history, scheduled optimizations, and multi-step workflows.

### 8.1 Core Tables

#### `playbook_sessions`

```sql
create type playbook_session_status as enum ('draft', 'pushed', 'abandoned');

create table public.playbook_sessions (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references public.brands(id) on delete restrict,
  created_by uuid not null references public.profiles(id),
  status playbook_session_status default 'draft',

  -- Summary for history view
  input_summary text,  -- AI-generated summary of inputs
  task_count_pushed int default 0,

  -- Timestamps
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  pushed_at timestamptz,

  -- Metadata
  debrief_meeting_ids uuid[] default '{}'  -- Meetings imported into this session
);

-- Indexes
create index idx_playbook_sessions_brand on public.playbook_sessions(brand_id);
create index idx_playbook_sessions_created_by on public.playbook_sessions(created_by);
create index idx_playbook_sessions_status on public.playbook_sessions(status);
create index idx_playbook_sessions_created on public.playbook_sessions(created_at desc);

-- RLS
alter table public.playbook_sessions enable row level security;

create policy "Users can view their own sessions"
  on public.playbook_sessions for select to authenticated
  using (created_by = auth.uid());

create policy "Users can manage their own sessions"
  on public.playbook_sessions for all to authenticated
  using (created_by = auth.uid())
  with check (created_by = auth.uid());

create policy "Admins can view all sessions"
  on public.playbook_sessions for select to authenticated
  using (exists (select 1 from public.profiles where id = auth.uid() and is_admin = true));
```

#### `playbook_session_inputs`

```sql
create type playbook_input_type as enum ('observation', 'meeting', 'scheduled', 'reference');

create table public.playbook_session_inputs (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.playbook_sessions(id) on delete cascade,
  input_type playbook_input_type not null,
  content text not null,

  -- Source references
  debrief_meeting_id uuid references public.debrief_meeting_notes(id),
  schedule_id uuid references public.playbook_optimization_schedules(id),
  clickup_task_url text,  -- For cross-client references

  created_at timestamptz default now()
);

-- Indexes
create index idx_session_inputs_session on public.playbook_session_inputs(session_id);
create index idx_session_inputs_type on public.playbook_session_inputs(input_type);

-- RLS (inherits from session)
alter table public.playbook_session_inputs enable row level security;

create policy "Users can manage inputs for their sessions"
  on public.playbook_session_inputs for all to authenticated
  using (exists (
    select 1 from public.playbook_sessions
    where id = session_id and created_by = auth.uid()
  ));
```

#### `playbook_suggested_tasks`

```sql
create type playbook_task_status as enum ('pending', 'approved', 'rejected', 'pushed', 'failed');

create table public.playbook_suggested_tasks (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.playbook_sessions(id) on delete cascade,

  -- Task content
  title text not null,
  description text,
  task_type_slug text,  -- References playbook_task_types.slug

  -- Routing
  suggested_role_id uuid references public.agency_roles(id),

  -- AI reasoning (for transparency)
  reasoning text,
  related_input_id uuid references public.playbook_session_inputs(id),

  -- Status
  status playbook_task_status default 'pending',
  rejection_reason text,

  -- ClickUp result
  clickup_task_id text,
  clickup_task_url text,
  clickup_error text,

  -- Ordering
  display_order int default 0,

  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Indexes
create index idx_suggested_tasks_session on public.playbook_suggested_tasks(session_id);
create index idx_suggested_tasks_status on public.playbook_suggested_tasks(status);

-- RLS (inherits from session)
alter table public.playbook_suggested_tasks enable row level security;

create policy "Users can manage tasks for their sessions"
  on public.playbook_suggested_tasks for all to authenticated
  using (exists (
    select 1 from public.playbook_sessions
    where id = session_id and created_by = auth.uid()
  ));
```

#### `playbook_session_messages`

```sql
create table public.playbook_session_messages (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.playbook_sessions(id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content text not null,

  -- For assistant messages, track what changed
  tasks_added uuid[] default '{}',
  tasks_modified uuid[] default '{}',

  created_at timestamptz default now()
);

-- Index for chronological retrieval
create index idx_session_messages_session on public.playbook_session_messages(session_id, created_at);

-- RLS (inherits from session)
alter table public.playbook_session_messages enable row level security;

create policy "Users can manage messages for their sessions"
  on public.playbook_session_messages for all to authenticated
  using (exists (
    select 1 from public.playbook_sessions
    where id = session_id and created_by = auth.uid()
  ));
```

### 8.2 Playbook Knowledge Tables

#### `playbook_task_types`

```sql
create table public.playbook_task_types (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null,
  name text not null,
  description text,

  -- Default routing
  default_role_id uuid references public.agency_roles(id),

  -- Template for task description
  description_template text,

  -- Optional SOP link
  sop_clickup_doc_id text,

  -- Metadata
  estimated_hours decimal(4,1),
  category text,  -- 'ppc', 'catalog', 'reporting', 'strategy'

  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Seed with common task types
insert into public.playbook_task_types (slug, name, category, description_template) values
  ('n_gram_optimization', 'N-Gram Optimization', 'ppc',
   'Run n-gram analysis for {brand} campaigns. Review search term reports for the last 14 days and identify non-converting queries to add as negative keywords.'),
  ('bid_adjustment', 'Bid Adjustment', 'ppc',
   'Review and adjust bids for {brand} campaigns based on current performance metrics.'),
  ('listing_update', 'Listing Update', 'catalog',
   'Update Amazon listing content for {product}. See attached requirements.'),
  ('keyword_research', 'Keyword Research', 'catalog',
   'Conduct keyword research for {brand} products to identify new ranking opportunities.'),
  ('search_term_audit', 'Search Term Audit', 'ppc',
   'Audit search terms across {brand} campaigns to identify cannibalization and optimization opportunities.'),
  ('monthly_report', 'Monthly Report', 'reporting',
   'Prepare monthly performance report for {brand}.'),
  ('competitor_analysis', 'Competitor Analysis', 'strategy',
   'Analyze competitor positioning and pricing for {brand} in {marketplace}.');

-- RLS
alter table public.playbook_task_types enable row level security;

create policy "All authenticated users can view task types"
  on public.playbook_task_types for select to authenticated using (true);

create policy "Only admins can manage task types"
  on public.playbook_task_types for all to authenticated
  using (exists (select 1 from public.profiles where id = auth.uid() and is_admin = true))
  with check (exists (select 1 from public.profiles where id = auth.uid() and is_admin = true));
```

#### `playbook_optimization_schedules`

```sql
create table public.playbook_optimization_schedules (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references public.brands(id) on delete cascade,
  task_type_id uuid not null references public.playbook_task_types(id),

  -- Schedule
  frequency_days int not null,  -- e.g., 14 for bi-weekly

  -- Tracking
  last_completed_at timestamptz,
  last_session_id uuid references public.playbook_sessions(id),

  -- Computed (can be a generated column or updated by trigger)
  next_due_at timestamptz generated always as (
    coalesce(last_completed_at, created_at) + (frequency_days || ' days')::interval
  ) stored,

  is_active boolean default true,
  notes text,

  created_at timestamptz default now(),
  updated_at timestamptz default now(),

  unique (brand_id, task_type_id)
);

-- Index for "what's due" queries
create index idx_schedules_due on public.playbook_optimization_schedules(next_due_at)
  where is_active = true;
create index idx_schedules_brand on public.playbook_optimization_schedules(brand_id);

-- RLS
alter table public.playbook_optimization_schedules enable row level security;

create policy "Authenticated users can view schedules"
  on public.playbook_optimization_schedules for select to authenticated using (true);

create policy "Only admins can manage schedules"
  on public.playbook_optimization_schedules for all to authenticated
  using (exists (select 1 from public.profiles where id = auth.uid() and is_admin = true))
  with check (exists (select 1 from public.profiles where id = auth.uid() and is_admin = true));
```

#### `playbook_knowledge_cache`

```sql
create table public.playbook_knowledge_cache (
  id uuid primary key default gen_random_uuid(),
  doc_type text not null,  -- 'bm_playbook', 'sop'
  clickup_doc_id text unique not null,
  title text,
  content_markdown text,

  -- Sync tracking
  last_synced_at timestamptz default now(),
  synced_by uuid references public.profiles(id),

  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Index for doc lookup
create index idx_knowledge_cache_doc on public.playbook_knowledge_cache(clickup_doc_id);
create index idx_knowledge_cache_type on public.playbook_knowledge_cache(doc_type);

-- RLS
alter table public.playbook_knowledge_cache enable row level security;

create policy "Authenticated users can view knowledge cache"
  on public.playbook_knowledge_cache for select to authenticated using (true);

create policy "Only admins can manage knowledge cache"
  on public.playbook_knowledge_cache for all to authenticated
  using (exists (select 1 from public.profiles where id = auth.uid() and is_admin = true))
  with check (exists (select 1 from public.profiles where id = auth.uid() and is_admin = true));
```

---

## 9. API Surface

### Sessions

- `POST /api/playbook/sessions` — Create new session
  - Body: `{ brand_id }`
  - Returns: `{ session: Session }`

- `GET /api/playbook/sessions` — List user's sessions
  - Query: `?status=draft&brand_id=xxx`
  - Returns: `{ sessions: Session[] }`

- `GET /api/playbook/sessions/:id` — Get session with inputs, tasks, messages
  - Returns: `{ session, inputs, tasks, messages }`

- `PATCH /api/playbook/sessions/:id` — Update session (e.g., abandon)
  - Body: `{ status: 'abandoned' }`
  - Returns: `{ session }`

- `POST /api/playbook/sessions/:id/push` — Push approved tasks to ClickUp
  - Returns: `{ session, results: { task_id, clickup_task_id, success }[] }`

### Inputs

- `POST /api/playbook/sessions/:id/inputs` — Add input
  - Body: `{ input_type, content, debrief_meeting_id?, ... }`
  - Returns: `{ input }`

- `DELETE /api/playbook/sessions/:id/inputs/:inputId` — Remove input
  - Returns: `{ success }`

### Tasks

- `POST /api/playbook/sessions/:id/analyze` — Trigger AI analysis
  - Returns: `{ suggestions: Task[] }`

- `PATCH /api/playbook/sessions/:id/tasks/:taskId` — Update task
  - Body: `{ title?, description?, status?, suggested_role_id?, rejection_reason? }`
  - Returns: `{ task }`

- `POST /api/playbook/sessions/:id/tasks/:taskId/approve` — Approve task
  - Returns: `{ task }`

- `POST /api/playbook/sessions/:id/tasks/:taskId/reject` — Reject task
  - Body: `{ reason? }`
  - Returns: `{ task }`

### Chat

- `POST /api/playbook/sessions/:id/chat` — Send message, get AI response
  - Body: `{ message }`
  - Returns: `{ response, tasks_added?, tasks_modified? }`

### Knowledge

- `POST /api/playbook/knowledge/sync` — Sync playbook doc from ClickUp
  - Body: `{ clickup_doc_id }`
  - Returns: `{ doc: KnowledgeCache }`

- `GET /api/playbook/knowledge` — List cached knowledge docs
  - Returns: `{ docs: KnowledgeCache[] }`

### Schedules

- `GET /api/playbook/schedules` — List optimization schedules
  - Query: `?brand_id=xxx&due=true`
  - Returns: `{ schedules: Schedule[] }`

- `POST /api/playbook/schedules` — Create schedule
  - Body: `{ brand_id, task_type_id, frequency_days }`
  - Returns: `{ schedule }`

- `PATCH /api/playbook/schedules/:id` — Update schedule
  - Body: `{ frequency_days?, is_active?, last_completed_at? }`
  - Returns: `{ schedule }`

---

## 10. ClickUp Integration

### 10.1 Reading Docs (Playbook Knowledge)

**Endpoint:** `GET /doc/{doc_id}/pages`
**Purpose:** Fetch the BM Playbook document content

```typescript
async function syncPlaybookDoc(docId: string): Promise<void> {
  const response = await clickupApi.get(`/doc/${docId}/pages`);

  // ClickUp returns pages with content in markdown format
  const pages = response.pages;
  const combinedContent = pages
    .map(p => `# ${p.name}\n\n${p.content}`)
    .join('\n\n---\n\n');

  await supabase
    .from('playbook_knowledge_cache')
    .upsert({
      clickup_doc_id: docId,
      doc_type: 'bm_playbook',
      title: response.name,
      content_markdown: combinedContent,
      last_synced_at: new Date(),
    });
}
```

### 10.2 Reading Tasks (Recent Activity)

**Endpoint:** `GET /list/{list_id}/task`
**Purpose:** Fetch recent tasks for context

```typescript
async function getRecentTasks(listId: string): Promise<ClickUpTask[]> {
  const twoWeeksAgo = Date.now() - (14 * 24 * 60 * 60 * 1000);

  const response = await clickupApi.get(`/list/${listId}/task`, {
    params: {
      date_updated_gt: twoWeeksAgo,
      order_by: 'updated',
      reverse: true,
      subtasks: true,
    }
  });

  return response.tasks;
}
```

### 10.3 Creating Tasks (Push)

**Endpoint:** `POST /list/{list_id}/task`
**Purpose:** Create tasks from approved suggestions

```typescript
async function pushTaskToClickUp(
  task: PlaybookSuggestedTask,
  brand: Brand
): Promise<{ id: string; url: string }> {
  const listId = brand.clickup_list_id;

  if (!listId) {
    throw new Error(`Brand ${brand.name} has no ClickUp list configured`);
  }

  const response = await clickupApi.post(`/list/${listId}/task`, {
    name: task.title,
    description: buildTaskDescription(task),
    // Note: No assignees in MVP (backlog mode)
    // priority: mapPriority(task.priority),
  });

  return { id: response.id, url: response.url };
}

function buildTaskDescription(task: PlaybookSuggestedTask): string {
  let description = task.description || '';

  if (task.reasoning) {
    description += `\n\n## Context\n${task.reasoning}`;
  }

  description += `\n\n---\nCreated by Playbook`;

  return description;
}
```

---

## 11. Token Usage

Playbook uses the shared `ai_token_usage` table and `logUsage` helper from `@/lib/ai/usageLogger.ts`.

### Usage Pattern

```typescript
import { logUsage } from "@/lib/ai/usageLogger";

// After AI analysis
await logUsage({
  tool: "playbook",
  stage: "analyze",  // or "chat", "refine"
  userId: user.id,
  promptTokens: result.tokensIn,
  completionTokens: result.tokensOut,
  totalTokens: result.tokensTotal,
  model: result.model,
  meta: {
    session_id: session.id,
    brand_id: session.brand_id,
    input_count: inputs.length,
    suggestion_count: suggestions?.length,
  }
});

// After chat message
await logUsage({
  tool: "playbook",
  stage: "chat",
  userId: user.id,
  promptTokens: result.tokensIn,
  completionTokens: result.tokensOut,
  totalTokens: result.tokensTotal,
  model: result.model,
  meta: {
    session_id: session.id,
    brand_id: session.brand_id,
    message_count: chatHistory.length,
    tasks_added: tasksAdded?.length ?? 0,
    tasks_modified: tasksModified?.length ?? 0,
  }
});
```

### Stage Values

| Stage | When Used |
|-------|-----------|
| `analyze` | Initial AI analysis of inputs → suggestions |
| `chat` | Follow-up chat messages and refinements |
| `refine` | Re-analysis after input changes |
| `mcp` | Gated MCP queries (exploratory, higher cost) |

### Storage

Uses existing `ai_token_usage` table (no new columns needed):
- `tool`: "playbook"
- `stage`: Analysis stage (see above)
- `user_id`: Who triggered the AI call
- `prompt_tokens`, `completion_tokens`, `total_tokens`: Token counts
- `model`: Model used (e.g., "gpt-4o-mini")
- `meta`: Session and brand context as JSONB

---

## 12. Slack Bot Components

### 12.1 Slack App Configuration

- **App Name:** Vara
- **Bot Display Name:** Vara
- **Bot Scopes Required:**
  - `chat:write` — Send messages
  - `im:history` — Read DM history
  - `im:write` — Send DMs
  - `users:read` — Look up user info
- **Event Subscriptions:**
  - `message.im` — DM messages to the bot
  - `app_mention` — @playbook mentions (future: channel mode)
- **Interactivity:** Enable for Block Kit button callbacks

### 12.2 Message Types

| Type | When | Block Kit |
|------|------|-----------|
| Task Preview | After user requests task creation | Section + Actions (Approve/Reject/Edit) |
| MCP Gate | Before exploratory query | Section + Actions (Continue/Cancel) |
| Success | After task created | Section with link |
| Error | On failure | Section with error details |

### 12.3 Admin Functions (CLI/Backend)

Admin functions are handled via CLI scripts or backend endpoints, not a web UI:
- **SOP Sync:** `worker-sync` service (scheduled) or manual via CLI
- **Knowledge Cache:** View via Supabase dashboard or backend query
- **Task Types:** Seed via migration, update via Supabase dashboard

All user-facing interaction happens in Slack. No web UI is planned for MVP.

---

## 13. Implementation Stages

> **Implementation Guide:** See `docs/vara_implementation_guide.md` for detailed technical tasks with code snippets. The guide is designed for parallel work by multiple developers/agents.

### Stage 1: Sync Engine (Foundation)

Get SOP knowledge from ClickUp into Supabase. This is the foundation everything else depends on.

- [ ] Database migration: `playbook_knowledge_cache` table
- [ ] Scheduled job to sync ClickUp docs → Supabase
- [ ] Manual sync trigger via CLI/admin
- [ ] Store: doc ID, page ID, content markdown, last synced timestamp
- [ ] Start with: BM Playbook + Bi-Weekly PPC SOP (N-Gram)

### Stage 2: Slack Bot Scaffold

Basic Slack bot that can receive DMs and respond.

- [ ] Create Slack app with required scopes
- [ ] Set up event subscription for `message.im`
- [ ] Basic echo handler (receive message, respond)
- [ ] Deploy bot endpoint (can be Next.js API route or separate service)
- [ ] Test: DM the bot, get a response

### Stage 3: One Deterministic Flow

End-to-end: "Create n-gram task for Brand X" → task in ClickUp.

- [ ] Intent classifier (simple: regex or small prompt)
- [ ] Fetch SOP content from knowledge cache
- [ ] Generate task preview with brand context
- [ ] Block Kit message with Approve/Reject/Edit buttons
- [ ] Handle button callbacks
- [ ] On Approve: create task via ClickUp API, return link
- [ ] On Edit: create draft task, return ClickUp link

### Stage 4: Expand Task Types

Add more SOPs and task types.

- [ ] Database: `playbook_task_types` table
- [ ] Sync more SOPs (Weekly, Monthly, Account Health, etc.)
- [ ] Map task type slugs to SOP doc/page IDs
- [ ] Classifier recognizes multiple task types
- [ ] Admin UI for managing task types

### Stage 5: Session Context & Debrief Integration

Session start flow + Debrief meeting processing.

- [ ] Session start: "Let's work on Client X"
  - [ ] Resolve client name → client ID (fuzzy match)
  - [ ] Fetch brands from Command Center
  - [ ] Verify ClickUp space/list configured
  - [ ] Check Debrief for recent meetings (status = ready)
  - [ ] Show summary with [Process Meeting] [Create Task] [Just Chat]
- [ ] Browse meetings: "What meetings are ready?"
  - [ ] Call `GET /api/debrief/meetings?status=ready`
  - [ ] Show list with Select buttons
- [ ] Process meeting tasks one-at-a-time
  - [ ] Fetch tasks via `GET /api/debrief/meetings/:id`
  - [ ] Show task 1 of N with Approve/Skip/Edit
  - [ ] On Approve: call `POST /api/debrief/tasks/:id/send-to-clickup`
  - [ ] Advance through all tasks
- [ ] Session context persistence (30 min timeout)

### Stage 6: Gated MCP for Exploratory Queries

Handle queries that don't map to known workflows.

- [ ] Integrate ClickUp MCP
- [ ] Classifier detects exploratory queries
- [ ] Show "This requires more resources" gate
- [ ] Handle Continue/Cancel button callbacks
- [ ] Execute MCP query, return results

### Stage 7: Polish & Expand

- [ ] Token usage logging (including `stage: 'mcp'` for MCP queries)
- [ ] Error handling and retry logic
- [ ] Session history in Supabase

---

## 14. Success Metrics

- **Time to task creation:** How long from meeting end → tasks in ClickUp?
- **Tasks per session:** Average number of tasks created per Playbook session
- **Adoption:** % of client meetings that result in a Playbook session
- **Approval rate:** % of AI suggestions that get approved (quality signal)
- **Session completion:** % of started sessions that get pushed (not abandoned)

---

## 15. Decisions Made

### v1.0 Decisions (Original)
1. ✅ **Playbook storage:** ClickUp Docs (easy to edit), cached in Supabase
2. ✅ **Task assignment:** MVP creates tasks in backlog without assignees
3. ✅ **Token logging:** Use existing `ai_token_usage` table with `meta` JSONB for session/brand context
4. ✅ **Knowledge sources:** BM Playbook (`18m2dn-4177`) + SOP Library (`18m2dn-4257`) — living docs in ClickUp
5. ✅ **ClickUp Task fields:** name, `markdown_description`, status, assignees, parent, due_date, start_date, priority, tags, notify_all

### v2.0 Decisions (Architecture Shift)
6. ✅ **Interface:** Slack bot "Vara" (DM mode) instead of custom web UI
7. ✅ **Task flow:** One task at a time (simpler, less fragile than batch)
8. ✅ **Editing:** Use ClickUp directly (don't rebuild an editor)
9. ✅ **Chat:** Use Slack (don't rebuild chat)
10. ✅ **Request routing:** Classifier determines deterministic vs MCP path
11. ✅ **MCP access:** Gated with user consent, logged as `stage: 'mcp'`
12. ✅ **SOP fidelity:** Task descriptions come directly from cached SOPs, not AI interpretation
13. ✅ **Sync Engine:** Foundation layer — SOPs synced to Supabase for fast, cheap access
14. ✅ **Debrief integration:** Re-use existing Debrief APIs (meetings, tasks, send-to-clickup)
15. ✅ **Session context:** Stored in `playbook_slack_sessions` table, 30 min timeout

### v2.0 Infrastructure Decisions (Red Team Resolved)
16. ✅ **Slack user mapping:** `profiles.slack_user_id` column, set manually for MVP
17. ✅ **Session storage:** `playbook_slack_sessions` table in Supabase (see Section 3.4)
18. ✅ **ClickUp credentials:** Service token in Render env var (`CLICKUP_API_TOKEN`), server-side only
19. ✅ **Bot execution context:** Uses `SUPABASE_SERVICE_ROLE_KEY` (bypasses RLS, trusted backend)
20. ✅ **Scheduled reminders:** Deferred to future phase (not MVP)

---

## 16. Open Questions

1. ~~**Playbook Doc ID:** Which ClickUp doc will be the master BM Playbook?~~ ✅ Resolved: `18m2dn-4177`
2. **Initial task types:** Extract from BM Playbook doc (Section 2 workstreams + SOP Library)
3. ~~**Optimization schedules:** Extract from SOP Library~~ ✅ Deferred to future phase

---

## 17. Future Enhancements

### Phase 2: Team Assignment
- Add assignee selection to Slack approval flow
- Pull team assignments from Command Center
- Auto-suggest assignee based on role + brand assignment

### Phase 3: Channel Mode
- Enable @playbook mentions in team channels (not just DM)
- Multi-user conversations about task creation
- Thread-based approval workflows

### Phase 4: Proactive Notifications
- Scheduled optimization reminders in Slack
- Weekly digest of pending items per brand
- "You haven't run n-gram for Brand X in 16 days"

### Phase 5: Learning & Improvement
- Track which suggestions get approved vs rejected
- Use patterns to improve AI suggestions over time
- "This worked well for similar brands" insights

### Phase 6: Batch Mode (If Needed)
- Process Debrief meeting → suggest multiple tasks
- Slack modal for reviewing/approving batch
- Only add if one-at-a-time proves insufficient

---

**End of PRD**
