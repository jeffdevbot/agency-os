# Product Requirement Document: The Operator (M1)

## 1. Executive Summary
**The Operator** is an internal AI agent designed to be the "Central Nervous System" of the agency. It provides a natural language interface to query project status (via ClickUp) and a robust mechanism to extract intellectual property (IP) by "canonizing" executed tasks into reusable SOP templates.

**Milestone 1 (MVP)** Focus:
1.  **Read-Only Visibility:** Querying ClickUp for status updates without logging into ClickUp.
2.  **SOP Canonization:** Ingesting a specific ClickUp task, stripping client-specific data, and saving it as a generic template.

## 2. User Experience & Workflow

### 2.1 The Interface
The UI is a split-screen "Command Center" (`tools.ecomlabs.ca/ops`):
* **Left Pane (Chat):** A conversational thread with the "Orchestrator" agent.
* **Right Pane (Context Board):** A dynamic, visual display that changes based on context.
    * *Default:* A Mini-Kanban board showing the active client's task status.
    * *SOP Mode:* A "Diff View" showing the raw task vs. the neutralized SOP template for approval.

### 2.2 Core User Stories
1.  **Status Check:**
    * *User:* Selects "Client A" from a dropdown. Asks: "What is stuck in review?"
    * *System:* Fetches live data from ClickUp, summarizes it in chat ("There are 3 tasks in review..."), and updates the Right Pane to show those specific cards.
2.  **SOP Canonization (The "Matrix" Upload):**
    * *User:* Pastes a ClickUp Task URL into chat. Says: "Make this the canonical Keyword Research SOP."
    * *System:* Scrapes the task, uses AI to identifying client-specific variables (Brand Name, ASIN), replaces them with `{{slots}}`, and presents a preview.
    * *User:* Reviews the diff, edits the name, and clicks "Commit to Library."
3.  **SOP Retrieval:**
    * *User:* Asks "Do we have an SOP for Promotion Setup?"
    * *System:* Searches the vector database and returns the best match with a link to the template.

---

## 3. Technical Architecture

### 3.1 System Components (Render)
We adhere to the **Agency OS** architecture:
* **Frontend (`frontend-web`):** Next.js + ShadcnUI. Handles the Split Screen state and Markdown rendering.
* **Backend (`backend-core`):** Python FastAPI. Hosts the Agents.
* **Database:** Supabase (PostgreSQL + pgvector).

### 3.2 The Agent Swarm (Backend)
The backend uses a "Router-Solver" pattern to keep costs low and accuracy high.

#### A. The Chat Orchestrator (Router)
* **Model:** GPT-4o-mini (Fast/Cheap).
* **Role:** Maintains conversation history (summary + last 10 turns). Classifies intent into: `FETCH_STATUS`, `CANONIZE_SOP`, `FIND_SOP`, or `CHIT_CHAT`.

#### B. The ClickUp Fetcher (Solver)
* **Model:** None (Deterministic Code).
* **Role:** Interacts with ClickUp API.
* **Logic:**
    * Maps `client_id` (Supabase) $\to$ `space_id` (ClickUp).
    * Fetches Lists/Tasks.
    * Filters by Status (Open, Ready, In Progress, Review, Complete).
    * Returns a compressed JSON object to the Frontend for the Kanban board.

#### C. The SOP Librarian (Solver)
* **Model:** GPT-4o (High Intelligence).
* **Role:** "Neutralizes" raw tasks into templates.
* **Logic:**
    1.  **Ingest:** Fetch Task Title, Description, Checklists, and Subtasks.
    2.  **Neutralize:** Identify proper nouns (Client Names, Competitors, Cities) and regex patterns (ASINs, URLs). Replace with `{{variable_name}}`.
    3.  **Structure:** Format into the Standard SOP JSON Schema.
    4.  **Diff:** Generate a "Before/After" view for the user.

---

## 4. Data Model (Supabase)

### 4.1 Core Entities
```sql
-- Maps Agency OS Clients to ClickUp
create table public.clients (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  clickup_space_id text, -- The Space ID in ClickUp
  clickup_folder_id text -- Optional, if client is just a folder
);

-- The SOP Library
create table public.sops (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null, -- e.g., 'keyword-research-master'
  name text not null,
  version int default 1,
  scope text check (scope in ('canonical', 'client-specific')),
  client_id uuid references public.clients, -- Null if canonical
  content jsonb not null, -- The full template structure
  variables text[], -- Detected slots: ['asin', 'competitor_name']
  embedding vector(1536), -- For semantic search
  created_at timestamptz default now()
);
4.2 Chat Memory
SQL

create table public.ops_chat_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users,
  client_context_id uuid references public.clients, -- Which client is active?
  summary text, -- "Rolling summary" of the conversation
  last_active timestamptz
);
5. ClickUp Integration Strategy (M1)
Auth:

We will use a Personal API Token (belonging to the Admin/Owner) stored in Render Environment Variables (CLICKUP_API_TOKEN).

Future: Upgrade to OAuth if we open this tool to non-admins.

Sync Strategy:

Live Fetch: When a user asks for status, we hit the ClickUp API in real-time (cached for 5 mins).

Nightly Sync (Worker): A background job scans ClickUp to map new Spaces/Lists to our clients table so the dropdown selector stays current.

6. API Interface (Internal)
The backend-core (Python) exposes these endpoints to the frontend-web (Next.js):

Chat & Status
POST /api/ops/chat: Sends user message, returns agent text response + context_pane_data (JSON for the board).

GET /api/ops/clients: Returns list of clients for the dropdown.

SOP Operations
POST /api/ops/sops/preview:

Input: { clickup_task_url: string }

Output: { original: json, neutralized: json, diff_summary: string }

POST /api/ops/sops/commit:

Input: { neutralized_data: json, slug: string, aliases: string[] }

Action: Saves to Supabase sops table.

7. Success Criteria (M1)
Admin Usage: Jeff can log in, select a client, and see a Kanban board of that client's active tasks without opening ClickUp.

Canonization: Jeff can paste a link to a "finished" task, review the AI's proposed template, and save it as a "Canonical SOP."

Search: Asking "Do we have an SOP for X?" retrieves the newly saved SOP.
