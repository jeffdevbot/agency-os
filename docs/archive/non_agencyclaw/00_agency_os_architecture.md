# Ecomlabs Tools: Master Architecture & Strategy (formerly “Agency OS”)

## 1. Executive Summary
**Ecomlabs Tools** (`tools.ecomlabs.ca`) is the unified internal platform that consolidates our operational tools. It replaces standalone subdomains (like `ngram.ecomlabs.ca`) with a central dashboard, single sign-on (SSO), and role-based access control. “Agency OS” was the internal codename; use Ecomlabs Tools in user-facing copy.

The goal is to move from "scripts and spreadsheets" to "integrated software" that streamlines:
1.  Ad Data Analysis (Ngram).
2.  Meeting follow-ups & task capture (Debrief).
3.  Content Creation (Scribe — replacing the deprecated Amazon Composer).
4.  Creative Briefing (Creative Brief Tool).

## 2. Domain & Migration Strategy

### The Shift
* **Current State:** `ngram.ecomlabs.ca` (Hosted on Render).
* **Future State:** `tools.ecomlabs.ca` (Hosted on Render).
* **Infrastructure Choice:** We are standardizing on **Render** for all services. This allows us to run long-running background processes (Nightly Syncs) and heavy compute jobs (Ngram processing) without hitting the timeout/size limits typical of Vercel Serverless.

### The Render Service Architecture
We will run three distinct services within the same Render Project:

1.  **Frontend Service (`frontend-web`)**
    * **Type:** Web Service (Node.js).
    * **Tech:** Next.js (React).
    * **Role:** Serves the Dashboard UI, handles Supabase Auth redirects, and proxies API requests.
    * **Domain:** `tools.ecomlabs.ca`.

2.  **Backend Service (`backend-core`)**
    * **Type:** Web Service (Python).
    * **Tech:** FastAPI.
    * **Role:** The heavy lifter. Runs the Ngram processing logic, Chat Orchestrator (LLM routing), and content generation backends (Scribe). Amazon Composer is deprecated and will be removed once Scribe is live.
    * **Domain:** Internal private networking (accessible only by Frontend) OR `api.ecomlabs.ca` (if public access is needed).

3.  **Worker Service (`worker-sync`)**
    * **Type:** Background Worker.
    * **Tech:** Python.
    * **Role:** Runs offline jobs that don't need a UI.
        * Nightly ClickUp Sync (updates Client/Task DB).
        * SOP Generalizer (AI batch processing).

### Migration Path
1.  **Deploy Frontend:** Launch the Next.js shell on Render at `tools.ecomlabs.ca`.
2.  **Deploy Backend:** Port the existing Ngram logic (`app/main.py`) to the new Python service.
3.  **Redirect:** Set up a 301 Redirect on `ngram.ecomlabs.ca` $\to$ `tools.ecomlabs.ca/ngram`.

---

## 3. Infrastructure Setup (Step-by-Step)

**Context:** We are using a single Supabase project to handle auth for *all* tools. This avoids users needing to log in separately for Ngram vs. Scribe (Composer is legacy/deprecated).

### A. Google Cloud Console (The "Annoying Part")
*Goal: Get a Client ID and Client Secret to give to Supabase.*

1.  Go to [console.cloud.google.com](https://console.cloud.google.com/).
2.  **Create New Project:** Name it `AgencyOS-Internal`.
3.  **OAuth Consent Screen:**
    * Go to **APIs & Services > OAuth consent screen**.
    * **User Type:** Choose **Internal** (This restricts login to users within your Google Workspace Organization, adding a layer of security).
    * **App Info:** Name it "EcomLabs Tools". Add your support email.
    * **Scopes:** Add `.../auth/userinfo.email` and `.../auth/userinfo.profile`.
    * **Save.**
4.  **Credentials:**
    * Go to **APIs & Services > Credentials**.
    * Click **+ Create Credentials** > **OAuth client ID**.
    * **Application Type:** Web application.
    * **Name:** `Supabase Auth`.
    * **Authorized JavaScript Origins:**
        * `https://tools.ecomlabs.ca`
        * `http://localhost:3000` (Crucial for local dev).
    * **Authorized Redirect URIs:** (You need your Supabase URL for this).
        * *Format:* `https://<your-supabase-project-id>.supabase.co/auth/v1/callback`
        * *To find this:* Go to Supabase Dashboard > Settings > API > URL.
    * **Click Create.**
    * **COPY THE CLIENT ID AND CLIENT SECRET.**

### B. Supabase Setup
1.  Go to Supabase Dashboard > Authentication > Providers.
2.  Select **Google**.
3.  **Enable** Google.
4.  Paste the **Client ID** and **Client Secret** from the step above.
5.  **Skip nonce checks:** Toggle this ON (usually required for standard OAuth flows to avoid errors).
6.  Click **Save**.

### C. URL Configuration (Supabase)
1.  Go to Supabase Dashboard > Authentication > URL Configuration.
2.  **Site URL:** Set this to your production URL: `https://tools.ecomlabs.ca`
3.  **Redirect URLs:** Add the following:
    * `http://localhost:3000/**`
    * `https://tools.ecomlabs.ca/**`

---

## 4. Tool Suite Overview

### 🛠 Tool 1: The Ngram Analyzer (Migration)
* **Host:** `backend-core` (Python).
* **Function:** Ingests Search Term Reports (up to 40MB), processes n-grams using Pandas, streams Excel output.
* **Access:** Media Buyers (Advertising Specialists).
* **Why Render?** Avoids Vercel's 4.5MB body limit and 10s timeout limits for heavy file processing.

### 🕶 Tool 2: The Operator (Deprecated)
* **Host:**
    * **API:** `backend-core` (Chat Orchestrator, ClickUp Fetcher).
    * **Background:** `worker-sync` (Nightly Sync, SOP Generalizer).
* **Function:** Originally an AI-driven interface for ClickUp and SOP management.
* **Core Features:**
    * **Chat Orchestrator:** Natural language query for project status.
    * **SOP Librarian:** Auto-generalizes tasks into canonical SOPs.
    * **ClickUp Fetcher:** Deterministic task creation/assignment.
* **Backend:** Requires OpenAI (GPT-4o/mini) API key + ClickUp API Token.
* **Status:** Deprecated — this scope evolved into Debrief (`/debrief`) for meeting-note ingestion + task extraction and review.

### ✍️ Tool 3: Scribe (New; replaces Amazon Composer)
* **Host:** `frontend-web` (UI) + `backend-core` (Logic).
* **Function:** Successor to Amazon Composer with a simplified listing/content generation workflow. Composer is deprecated and frozen; Scribe will own future listing work.
* **Core Features (to be defined in Scribe PRD):**
    * Lean input + review flow for Amazon content.
    * Client-friendly sharing/review.
    * Export pathways (flat file/CSV) aligned to the simpler scope.
* **Spec:** See `docs/12_scribe_prd.md` for the full PRD.

### 🎨 Tool 4: Creative Brief (New)
* **Function:** Generates image/asset briefs based on copy.
* **Core Features:**
    * Ingests copy from Tool #3.
    * Outputs text overlay/staging instructions for designers.

---

## 5. Database Schema Strategy (High Level)
We will use a single Postgres database (Supabase). The backbone is the link between Supabase Auth and our custom Roles.

* **`auth.users`**: Managed by Supabase.
* **`public.profiles`**: Extends users. Contains `role` (Admin, Brand Manager, etc.) and `clickup_user_id`.
* **`public.clients`**: Database of agency clients with their ClickUp Space IDs.
* **`public.sops`**: Vector store for the SOP Librarian.
