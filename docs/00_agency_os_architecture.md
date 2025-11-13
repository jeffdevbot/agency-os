# Agency OS: Master Architecture & Strategy

## 1. Executive Summary
**Agency OS** (`tools.ecomlabs.ca`) is a unified internal platform designed to consolidate our agency's operational tools. It replaces standalone subdomains (like `ngram.ecomlabs.ca`) with a central dashboard, single sign-on (SSO), and role-based access control.

The goal is to move from "scripts and spreadsheets" to "integrated software" that streamlines:
1.  Ad Data Analysis (Ngram).
2.  Project Management & SOPs (The Operator).
3.  Content Creation (Amazon Composer).
4.  Creative Briefing (Creative Brief Tool).

## 2. Domain & Migration Strategy

### The Shift
* **Current State:** `ngram.ecomlabs.ca` (Hosted on Render).
* **Future State:** `tools.ecomlabs.ca` (Hosted on Vercel).
* **Migration Path:**
    1.  Launch `tools.ecomlabs.ca`.
    2.  Port the Ngram tool frontend to the new repo.
    3.  Set up a 301 Redirect on `ngram.ecomlabs.ca` $\to$ `tools.ecomlabs.ca/ngram`.

### Tech Stack
* **Frontend:** Next.js (React) deployed on Vercel.
* **Backend/Database:** Supabase (PostgreSQL, Auth, Vector DB, Edge Functions).
* **Authentication:** Supabase Auth (Google OAuth provider).
* **Compute (Ngram/Python):**
    * *Option A:* Port Python logic to Vercel Serverless Functions (Python runtime).
    * *Option B:* Keep the heavy Python processing on Render as a microservice API, but serve the UI from Vercel. (Decision TBD based on legacy code review).

---

## 3. Infrastructure Setup (Step-by-Step)

**Context:** We are using a single Supabase project to handle auth for *all* tools. This avoids users needing to log in separately for Ngram vs. Composer.

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
* **Function:** Ingests Search Term Reports, processes n-grams, outputs Excel.
* **Access:** Media Buyers (Advertising Specialists).
* **Key Requirement:** Must maintain the current secure upload/download flow.

### 🕶 Tool 2: The Operator (New)
* **Function:** AI-driven interface for ClickUp and SOP management.
* **Core Features:**
    * **Chat Orchestrator:** Natural language query for project status.
    * **SOP Librarian:** Auto-generalizes tasks into canonical SOPs.
    * **ClickUp Fetcher:** Deterministic task creation/assignment.
* **Backend:** Requires OpenAI (GPT-4o/mini) API key + ClickUp API Token.

### ✍️ Tool 3: Amazon Composer (New)
* **Function:** Listing generation and approval workflow.
* **Core Features:**
    * Input form (SKU data).
    * "Secret Link" sharing for client approval (no login required for clients).
    * Flat file export upon approval.

### 🎨 Tool 4: Creative Brief (New)
* **Function:** Generates image/asset briefs based on copy.
* **Core Features:**
    * Ingests copy from Tool #3.
    * Outputs text overlay/staging instructions for designers.

---

## 5. Database Schema Strategy (High Level)
We will use a single Postgres database. The backbone is the link between Supabase Auth and our custom Roles.

* **`auth.users`**: Managed by Supabase.
* **`public.profiles`**: Extends users. Contains `role` (Admin, Brand Manager, etc.) and `clickup_user_id`.
* **`public.clients`**: Database of agency clients with their ClickUp Space IDs.
* **`public.sops`**: Vector store for the SOP Librarian.
