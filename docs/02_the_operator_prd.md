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
