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
```

### Step 3.2: API Router Setup

Create a new router file in the backend: `app/routers/ngram.py`.

Copy the `process_report` function (lines 270-420 in `main.py`).

Copy the helper functions:

* `read_backview_path` / `read_backview`
* `clean_numeric`
* `derive_category`
* `build_ngram`
* `make_unique_sheet_name`
* `color_for_category` (and `PALETTE`)

Refactor:

* Remove the `@app.get("/")` HTML endpoint (no longer needed).
* Update the route decorator to: `@router.post("/process")`.
* Ensure `verify_supabase_jwt` dependency is imported from the shared backend-core auth module.

### Step 3.3: Cross-Origin Resource Sharing (CORS)

In the backend-core main application file (`main.py`), ensure `tools.ecomlabs.ca` is whitelisted:

```python
origins = [
    "http://localhost:3000",
    "https://tools.ecomlabs.ca",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 4. Frontend Migration (React/Next.js)

Goal: Rebuild the UI using modern React components instead of the raw HTML string found in the old `main.py`.

### Step 4.1: Component Structure

Create a new page: `app/ngram/page.tsx` (assuming Next.js App Router).

Key UI elements to rebuild:

* **Upload Zone:** Use `react-dropzone` to replicate the drag-and-drop experience.
* **Auth Guard:** Wrap the page in a Supabase Auth Check (redirect to login if not authenticated).
* **Progress Indicator:** Replicate the "Analyzing N-Grams..." overlay using a React state (`isUploading`).

### Step 4.2: The Upload Logic (Replacement for `auth.js`)

Instead of `window.authorizedUpload`, use standard fetch inside the React component:

```ts
const handleUpload = async (file: File) => {
  // 1. Get the User's Session Token
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) return alert("Please log in");

  // 2. Construct Form Data
  const formData = new FormData();
  formData.append("file", file);

  // 3. Post to the Backend Service
  // Note: In production, this URL points to your Render Backend Service
  const response = await fetch("https://api-core.ecomlabs.ca/ngram/process", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${session.access_token}`,
    },
    body: formData,
  });

  if (!response.ok) throw new Error("Upload failed");

  // 4. Handle the Blob Response (Download)
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = file.name.replace(/\.\w+$/, "") + "_ngrams.xlsx";
  a.click();
};
```

## 5. Infrastructure & Environment Variables

### Backend Service (Render)

Set these environment variables in the backend-core service:

* `SUPABASE_URL`: (Same as legacy)
* `SUPABASE_JWT_SECRET`: (Same as legacy - Critical for Auth)
* `MAX_UPLOAD_MB`: `40` (Matches legacy constraint)

### Frontend Service (Render)

Set these environment variables in the frontend-web service:

* `NEXT_PUBLIC_SUPABASE_URL`: `https://iqkmygvncovwdxagewal.supabase.co`
* `NEXT_PUBLIC_SUPABASE_ANON_KEY`: (The public key from legacy `static/js/auth.js`)
* `NEXT_PUBLIC_BACKEND_URL`: The URL of your backend-core service.

## 6. Migration Checklist

* [ ] Init: Create agency-os monorepo.
* [ ] Backend: Scaffold backend-core (FastAPI).
* [ ] Code Port: Copy Ngram logic to backend-core.
* [ ] Frontend: Scaffold frontend-web (Next.js).
* [ ] UI Port: Build Ngram Upload Page in React.
* [ ] Integration Test: Run locally. Frontend (`localhost:3000`) uploads to Backend (`localhost:8000`).
* [ ] Deploy: Push to Render (2 services).
* [ ] DNS: Point `tools.ecomlabs.ca` to Render Frontend.
* [ ] Redirect: Add 301 Redirect on old `ngram.ecomlabs.ca`.
