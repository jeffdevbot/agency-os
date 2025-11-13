# Ngram Tool Migration Strategy

## 1. Executive Summary
**Objective:** Migrate the existing Ngram Processor from its standalone repository to the unified **Agency OS** Render project.
**Strategy:** "Split and Lift." We will decouple the monolithic design (HTML served by Python) into the standard Agency OS pattern:
* **Frontend:** A Next.js/React page (`tools.ecomlabs.ca/ngram`) handling the UI and Auth.
* **Backend:** A Python endpoint (`api.ecomlabs.ca/ngram/process`) handling the heavy Pandas logic.

## 2. Architecture Changes

### Current State (Legacy)
* **Repo:** `jeffdevbot/ngram`
* **Type:** Monolithic FastAPI (Serves both HTML UI and JSON API).
* **Auth:** Vanilla JS (`auth.js`) manually handling Supabase JWTs.
* **Hosting:** Render Web Service (Standalone).

### Future State (Agency OS)
* **Frontend Host:** `frontend-web` Service (Next.js).
* **Backend Host:** `backend-core` Service (FastAPI).
* **Auth:** Standardized `@supabase/auth-helpers-nextjs` (Frontend) passes JWT to Backend via `Authorization: Bearer`.

---

## 3. Backend Migration (Python)

**Goal:** Move the logic from `app/main.py` into the new `backend-core` service.

### Step 3.1: Dependency Merge
Add these legacy requirements to the `backend-core` `requirements.txt`:
```txt
pandas>=2.2.2
numpy>=1.26.4
openpyxl>=3.1.2
xlsxwriter>=3.2.0
python-multipart==0.0.9  # Required for File Uploads
psutil>=5.9              # For memory logging (optional but good)
