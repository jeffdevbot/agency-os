# 🧵 Scribe — Product Requirements Document (PRD)

**Version:** 2.0
**Updated:** 2025-11-28 (EST)
**Owner:** Internal Tools (Ecomlabs)
**Purpose:** Automate Amazon copywriting workflow (titles, bullets, descriptions, backend keywords) in a structured, step-by-step tool. Replaces ad-hoc Word/ChatGPT flows with a consistent, compliant, SEO-ready, multi-SKU workflow.

---

## 1. 🎯 Product Summary
Scribe is an internal web application that helps Ecomlabs employees produce high-quality Amazon product listing content. It replaces the current workflow of Word docs + ChatGPT pasting with a structured wizard that ensures consistency, compliance, SEO performance, faster output, and scales from 3 SKUs to 25 SKUs equally well.

---

## 2. 👤 User Roles & Permissions
- **Internal Users (Authenticated)**
  - Must log in with Supabase Auth.
  - Can create, view, edit, archive, and restore their own projects.
  - Cannot see other users' projects.
- **Admin (Optional, Future)**
  - See all projects.
  - Force-archive or delete.

---

## 3. 🏠 Landing Page / Project List
- **Active Projects:** Scrollable list of active (non-archived) projects created by the logged-in user. Columns: Project Name, Category, Sub-category, Locale (e.g., en-US, fr-CA), Last Updated, Status (Draft, Topics Ready, Copy Ready, Approved, Archived). Actions: OPEN, ARCHIVE.
- **Archived Projects:** Hidden behind "View Archive." Archived projects cannot be edited but can be restored (delete optional/future).

---

## 4. 🔄 Scribe Workflow Overview (3 Stages)
Each project moves through these stages; each step must be explicitly approved before advancing:
1. **Stage A: Product Data** — enter product and SKU details, including locale selection for AI generation.
2. **Stage B: Topic Ideas** — Scribe proposes up to 8 question-first topics per SKU using the project's locale; the user selects and orders 5 that will feed copy.
3. **Stage C: Amazon Content Generation** — Scribe generates titles, bullets, descriptions, backend keywords per SKU in the project's locale. **Status (2025-11-28, EST): shipped backend + UI; attribute prefs UI is minimal and will be polished.**

---

## 5. 🟦 Stage A — Product Data (Per-SKU Model)

### 5.1 Design Philosophy

**All data in Stage A is per-SKU.** There are no "shared defaults" or "override" concepts. Every SKU owns 100% of its own data.

**Why this model?**
- **Simpler mental model:** No hidden inheritance or override state to track.
- **Better CSV compatibility:** Import/export is explicit and straightforward.
- **No ambiguity:** What you see in the UI is exactly what's stored in the database.

**Reusability:** Users can still quickly copy data between SKUs using the "Copy from SKU" feature (see §5.5), but this is a one-time duplication, not a live link.

---

### 5.2 Step A1 — Create New Project
- **Inputs:** Project Name, Locale (dropdown: en-US, en-CA, en-GB, en-AU, fr-CA, fr-FR, es-MX, es-ES, de-DE, it-IT, pt-BR, nl-NL), Category, Sub-Category.
- **Locale Behavior:** Selected at project creation only (immutable); controls language/dialect for AI-generated content in Stages B & C. Uses BCP 47 locale codes (e.g., en-US for American English, en-GB for British English, fr-CA for Canadian French).
- **Action:** Save immediately to `scribe_projects` with `status = 'draft'`.

---

### 5.3 Step A2 — Enter SKU Data (Spreadsheet-Style Grid)

#### 5.3.1 Grid Layout (Grouped Rows, No Modals)

Think of Stage A as an **Excel-style grouped-row grid** where each SKU is represented by **one block of rows**:

- **Primary row:** All scalar fields live here (`sku_code`, `asin`, `product_name`, `brand_tone`, `target_audience`, `supplied_content`, variant attribute values).
- **Child rows:** One row per multi-value item beneath the SKU (each `words_to_avoid`, each `keyword`, each `question`). Add-item rows appear inline; no modals, chips, or side panels.
- **Add rows inline:** Users type directly into the inline add row under each multi-value section; pressing Enter or blur saves.
- **CSV alignment:** This flattened structure maps cleanly to CSV (pipe-separated multi-value cells) with no hidden state.

Include the ASCII wireframe below in the UI spec:

```
+---------------------------------------------------------------------------------------------+
| SKU       | ASIN       | Product Name                   | Brand Tone      | Target Audience |
|                                                                                             |
| Words to Avoid        | Supplied Content (textarea on main row)          | Keywords        |
| Questions             | Variant Attr 1 | Variant Attr 2 | ...                               |
+---------------------------------------------------------------------------------------------+

Primary SKU row
──────────────────────────────────────────────────────────────────────────────────────────────
MHCP-CHI-01 | BOFN13GKF | MiHIGH Cold Plunge Chiller | Technical & precise | 30yo tech bros
Supplied content: "Take the plunge..."

Child rows for multi-value fields (indented)
──────────────────────────────────────────────────────────────────────────────────────────────
    words_to_avoid: weakness
    words_to_avoid: injury
    words_to_avoid: ice bath

    keyword: cold plunge
    keyword: cold tub
    keyword: ice bath

    question: Does it maintain temperature?
    question: What's the power consumption?
    [+ add question]

Next SKU row
──────────────────────────────────────────────────────────────────────────────────────────────
MHCP-TUB-01 | BOFN138PV1 | MiHIGH Cold Plunge Tub (Black) | Technical & precise | 30yo tech bros
[Copy from: MHCP-CHI-01]
```

*No shared/default/override modes exist. No legends, no mode dropdowns, no “Set shared” buttons.*

---

#### 5.3.2 Scalar Fields (Per SKU)

Each SKU has its own values for:
- **SKU Code** (required, text)
- **ASIN** (optional, text)
- **Product Name** (required, text)
- **Brand Tone** (optional, text) — e.g., "Technical and precise"
- **Target Audience** (optional, text) — e.g., "30-year-old tech bros"
- **Supplied Content** (optional, textarea) — user-provided product description or key facts

**Editing:**
- Inline editing for all fields on the primary row.
- Autosave on blur or Enter.
- No shared defaults, overrides, legends, or "Apply to All" toggle — reuse only via "Copy from SKU" (§5.5).

---

#### 5.3.3 Multi-Value Fields (Per SKU, Inline Child Rows)

Each SKU has its own lists for:
- **Words to Avoid** — stored as `text[]` on the SKU; UI shows one child row per word. The frontend concatenates these rows into the array before PATCH.
- **Keywords** — max 10 per SKU; one child row per keyword in `scribe_keywords`.
- **Customer Questions** — unlimited; one child row per question in `scribe_customer_questions`.

**UI Behavior (no modals/chips/side panels):**
1. Each item renders as an indented child row under the SKU block.
2. An inline add row is always present for each multi-value section; typing + Enter/blur saves.
3. Editing and deletion happen inline on the child rows; the primary row may show counts but not editors for multi-value fields.

**Backend:**
- Keywords/questions are rows with `sku_id` (never null).
- `words_to_avoid` remains an array column on `scribe_skus`; the UI maps child rows to array elements.

---

#### 5.3.4 Variant Attributes (Dynamic Columns)

Projects can define custom variant attributes (e.g., "Color", "Size") via the "Add Attribute" button.

- Each attribute appears as a new column in the grid.
- Each SKU has its own value for each attribute (stored in `scribe_sku_variant_values`).
- Attributes are stored in `scribe_variant_attributes` (project-level).

---

### 5.4 Step A3 — CSV Import/Export

#### 5.4.1 CSV Export Format

**Single-row-per-SKU format:**

```csv
sku_code,asin,product_name,brand_tone,target_audience,supplied_content,words_to_avoid,keywords,questions,variant_attr_1,...
MHCP-CHI-01,BOFN13GKF,MiHIGH Cold Plunge Chiller,Technical and precise,30-year-old tech bros,"Take the plunge...","weakness|injury|ice bath","cold plunge|cold tub|ice bath|recovery","Does it maintain temperature?|What's the power consumption?",...
```

**Field encoding:**
- Multi-value fields (words to avoid, keywords, questions) are pipe-separated (`|`) within the cell; each pipe-separated item maps to one child row in the UI.
- No multi-row CSV variant is supported; the grid’s grouped-row UI maps directly to this single-row-per-SKU export.

#### 5.4.2 CSV Import

- User uploads CSV with columns matching export format.
- For each row:
  - Create or update SKU with all scalar fields.
  - Split multi-value fields on `|` and create rows in keywords/questions tables; map `words_to_avoid` items into the array column.
  - Validate: max 10 keywords per SKU, required fields present.
- Import is additive: new SKUs are added, existing SKUs are updated.

---

### 5.5 "Copy from SKU" Feature

**Purpose:** Quickly duplicate data from one SKU to another without manual retyping.

**UI:**
- Each SKU row (except the first) shows a "Copy from…" dropdown or button in the primary row.
- User selects a source SKU from the project's existing SKUs.

**Action:** When user selects source SKU `S` to copy into target SKU `T`:
1. Copy all scalar fields from `S` to `T`:
   - Brand tone
   - Target audience
   - Supplied content
   - Variant attribute values
2. Copy all multi-value lists from `S` to `T`:
   - Words to avoid (duplicate array)
   - Keywords (duplicate rows in `scribe_keywords`)
   - Questions (duplicate rows in `scribe_customer_questions`)

**Result:**
- Both SKUs now have independent, identical values (one-time clone, no linkage).
- Changes to `S` do not affect `T` going forward.
- User can then edit `T` as needed.

**Implementation:**
- Frontend convenience: fetch data from `S`, write to `T` via existing APIs.
- No special "link" or "shared" records are created.

---

### 5.6 End of Stage A — Review & Approve

**Review Screen:**
- Summary table showing all SKUs with key fields.
- Show counts for keywords, questions, words to avoid per SKU.
- Show variant attributes and values.

**Validation:**
- At least one SKU must exist.
- SKU code and product name are required for each SKU.
- Max 10 keywords per SKU enforced.

**Approve Button:**
- Click "APPROVE & CONTINUE" → status changes to `stage_a_approved`.
- Unapprove: optional control to revert to `draft` (e.g., to edit). Blocked if archived.
- Stage B/C are currently deferred; approval simply locks Stage A data until those stages are re-enabled.

---

## 6. 🟩 Stage B — Topic Ideas

> **Status:** Implemented; per-SKU-only topics with selection are live. Pending full test plan execution (see `docs/18_scribe_test_plan.md`).

**Step B1 — Generate Topic Candidates**
- Generate up to 8 candidate topics per SKU via an LLM.
- Question-first: primarily use that SKU’s customer questions; also incorporate product name, brand tone, target audience, variant attributes, supplied content, keywords, and words_to_avoid (no cross-SKU or shared data).
- Backend: per-SKU prompt; insert up to 8 rows into `scribe_topics` with `sku_id` set and `approved = false` by default; humorous loading state.

**Step B2 — Select & Order Topics**
- User selects and orders up to 5 topics per SKU; selected topics are marked `approved = true`.
- Stage B approval requires every SKU to have 5 selected topics; only selected topics (max 5 per SKU) feed Stage C copy generation.
- Unselected candidates remain in `scribe_topics` with `approved = false` and are ignored by Stage C.

**Stage B User Flow (when enabled)**
- Generate topics (per-project or per-SKU).
- Review up to 8 candidates per SKU in a simple list.
- Click to select/deselect topics (up to 5) and drag to reorder them.
- Once every SKU has 5 selected topics, approve Stage B to move to Stage C.

---

## 7. 🟥 Stage C — Amazon Listing Copy

> **Status:** Ready for implementation; per-SKU only; gated on Stage B approval (`stage_b_approved`).

### Step C0 — Entry
- Guard: if project is not `stage_b_approved`, show “Unlock Stage C after Stage B approval.”

### Step C1 — First-Time Landing (Empty State)
- Header: “Stage C: Amazon Listing Copy.”
- Explainer: Scribe will generate per SKU: Title, 5 Bullets, Description, Backend Search Terms.
- Actions:
  - **Generate All SKUs** (primary) — enqueue copy generation for all SKUs.
  - **Generate Sample (1 SKU)** (secondary) — enqueue for one SKU (default first SKU or selected).
- Amazon rules summary (enforced in prompt/validation):
  - Title: ≤ ~200 chars, no ALL CAPS/emojis/HTML.
  - Bullets: exactly 5; no HTML/emojis; no medical/prohibited claims; avoid attribute spam.
  - Description: plain text; safe claims only.
  - Backend Keywords: 249-byte limit; no ASINs/competitor brands; avoid repeating title/bullets.
- Empty state: “Ready to generate Amazon listings? Start with ‘Generate Sample’ to preview one SKU, or ‘Generate All’ to process all SKUs.”

### Step C2 — Review & Edit (After Generation)
- SKU selector/swatches: simple buttons per SKU; one active at a time; optional small status (Generated/Edited/Missing/Approved).
- Left panel (Editor for active SKU):
  - Title input + “Regenerate Title.”
  - Bullets (5 inputs) + “Regenerate Bullets.”
  - Description textarea + “Regenerate Description.”
  - Backend Keywords textarea with byte counter (249-byte limit) + “Regenerate Backend Keywords.”
  - Save (PATCH generated content; bump version).
  - Per-SKU approve toggle removed; project approval just requires generated content for all SKUs.
- Right panel (Mini Amazon PDP preview, read-only):
  - Shows Title, 5 bullets, Description, Backend Keywords (collapsible).
  - Updates after Save (no live binding needed); show brief “Generating…” / “Saving…” states.
- Attribute Usage (optional, small panel):
  - Toggle/link: “Attribute Usage ›”.
  - Mode: ( ) Let Scribe decide (default) / (•) Use my selections.
  - For each variant attribute (e.g., Color: Red; Size: Large; Material: Cotton), checkboxes: Title / Bullets / Description / Backend Keywords.
  - Store preferences lightweight per SKU (e.g., JSON on SKU) and pass to prompt; no heavy matrix/table.

### Step C3 — Approve Stage C
- Button: “Approve Stage C.”
- Guard: all SKUs have generated content; per-SKU approvals not required.
- On success: set project status to `stage_c_approved` (final `approved` remains reserved).

### Stage C Prompt (Output Shape)
```json
{
  "title": "...",
  "bullets": ["...", "...", "...", "...", "..."],
  "description": "...",
  "backend_keywords": "..."
}
```
- Inputs: product name, SKU/ASIN, brand tone, target audience, supplied content, variant attributes, 5 approved topics (title + 3 bullets each), keywords, questions, words_to_avoid, attribute usage prefs.
- Guardrails: exactly 5 bullets; title length cap; backend keyword 249-byte cap; Amazon-safe language; avoid forbidden words/claims; prompt_version stored per generation; regenerations use latest prompt unless locked per version.

### CSV
- Export includes Stage C fields per SKU (column order): `sku_code, asin, product_name, brand_tone, target_audience, supplied_content, words_to_avoid, [variant_attrs], keywords, questions, topics, title, bullet_1..5, description, backend_keywords`. No Stage C import in v1.

---

## 8. 🧩 Database Schema Plan (Supabase)

### 8.1 Design Philosophy

**All Stage A data is per-SKU.** There are no "shared defaults" or `sku_id = null` records for keywords/questions/words.

**Key changes from V1:**
- Removed `_default` fields from `scribe_projects` (no more shared defaults).
- Removed `_override` fields from `scribe_skus` (no more override concept).
- Removed `keywords_mode`, `questions_mode`, `topics_mode` from `scribe_projects`.
- `scribe_keywords` and `scribe_customer_questions` now require `sku_id` (never null).

---

### 8.2 `scribe_projects`

```sql
CREATE TABLE scribe_projects (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_by uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  name text NOT NULL,
  locale text NOT NULL DEFAULT 'en-US',
  category text,
  sub_category text,
  status text NOT NULL DEFAULT 'draft',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT scribe_projects_locale_check
    CHECK (locale IN ('en-US', 'en-CA', 'en-GB', 'en-AU', 'fr-CA', 'fr-FR',
                      'es-MX', 'es-ES', 'de-DE', 'it-IT', 'pt-BR', 'nl-NL'))
);
```

**Fields:**
- `id` — UUID primary key.
- `created_by` — Foreign key to `profiles.id` (owner).
- `name` — Project name.
- `locale` — BCP 47 locale code (e.g., `en-US`, `fr-CA`). Controls language/dialect for AI-generated content in Stages B & C. Immutable after project creation.
- `category` — Optional category (e.g., "Home & Garden").
- `sub_category` — Optional sub-category.
- `status` — `draft | stage_a_approved | archived` (future: see appendix).
- `created_at`, `updated_at` — Timestamps.

**RLS:** `created_by = auth.uid()`.

**Notes:**
- No `brand_tone_default`, `target_audience_default`, etc. — these are now per-SKU fields only.
- No `keywords_mode`, `questions_mode` — all data is per-SKU by default.
- Current active statuses: `draft`, `stage_a_approved`, `archived`. Future statuses for Stage B/C are reserved (see Future Stages appendix) and are not reachable now.

---

### 8.3 `scribe_skus`

```sql
CREATE TABLE scribe_skus (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES scribe_projects(id) ON DELETE CASCADE,
  sku_code text NOT NULL,
  asin text,
  product_name text,
  brand_tone text,
  target_audience text,
  words_to_avoid text[] NOT NULL DEFAULT '{}',
  supplied_content text,
  sort_order int,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
```

**Fields:**
- `id` — UUID primary key.
- `project_id` — Foreign key to `scribe_projects.id`.
- `sku_code` — SKU code (required).
- `asin` — Optional ASIN.
- `product_name` — Product name.
- `brand_tone` — Brand tone for this SKU (e.g., "Technical and precise").
- `target_audience` — Target audience for this SKU (e.g., "30-year-old tech bros").
- `words_to_avoid` — Array of words to avoid (stored directly on SKU).
- `supplied_content` — User-provided product description.
- `sort_order` — Display order in the grid.
- `created_at`, `updated_at` — Timestamps.

**RLS (all verbs):** `project_id IN (SELECT id FROM scribe_projects WHERE created_by = auth.uid())`.

**Notes:**
- No `_override` suffix — these are the primary fields.
- `words_to_avoid` is stored as an array directly on the SKU for simplicity.

---

### 8.4 Variant Attributes

**`scribe_variant_attributes`**

```sql
CREATE TABLE scribe_variant_attributes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES scribe_projects(id) ON DELETE CASCADE,
  name text NOT NULL,
  slug text NOT NULL,
  sort_order int,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
```

**Fields:**
- `id` — UUID primary key.
- `project_id` — Foreign key to `scribe_projects.id`.
- `name` — Attribute name (e.g., "Color").
- `slug` — URL-safe slug (e.g., "color").
- `sort_order` — Display order in grid columns.

**RLS (all verbs):** `project_id IN (SELECT id FROM scribe_projects WHERE created_by = auth.uid())`.

---

**`scribe_sku_variant_values`**

```sql
CREATE TABLE scribe_sku_variant_values (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  sku_id uuid NOT NULL REFERENCES scribe_skus(id) ON DELETE CASCADE,
  attribute_id uuid NOT NULL REFERENCES scribe_variant_attributes(id) ON DELETE CASCADE,
  value text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (sku_id, attribute_id)
);
```

**Fields:**
- `id` — UUID primary key.
- `sku_id` — Foreign key to `scribe_skus.id`.
- `attribute_id` — Foreign key to `scribe_variant_attributes.id`.
- `value` — The value for this SKU/attribute pair.

**RLS (all verbs):** Join via `sku_id → scribe_skus → project_id IN (SELECT id FROM scribe_projects WHERE created_by = auth.uid())`.

---

### 8.5 Keywords (Per-SKU Only)

**`scribe_keywords`**

```sql
CREATE TABLE scribe_keywords (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES scribe_projects(id) ON DELETE CASCADE,
  sku_id uuid NOT NULL REFERENCES scribe_skus(id) ON DELETE CASCADE,
  keyword text NOT NULL,
  source text,
  priority int,
  created_at timestamptz NOT NULL DEFAULT now()
);
```

**Fields:**
- `id` — UUID primary key.
- `project_id` — Foreign key to `scribe_projects.id`.
- `sku_id` — Foreign key to `scribe_skus.id` (**required, never null**).
- `keyword` — The keyword text.
- `source` — Optional source (e.g., "user", "ai", "csv").
- `priority` — Optional priority (for sorting).

**RLS (all verbs):** `project_id IN (SELECT id FROM scribe_projects WHERE created_by = auth.uid())`.

**Notes:**
- **No `sku_id = null` rows.** All keywords are per-SKU.
- Max 10 keywords per SKU (enforced in API).

---

### 8.6 Customer Questions (Per-SKU Only)

**`scribe_customer_questions`**

```sql
CREATE TABLE scribe_customer_questions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES scribe_projects(id) ON DELETE CASCADE,
  sku_id uuid NOT NULL REFERENCES scribe_skus(id) ON DELETE CASCADE,
  question text NOT NULL,
  source text,
  created_at timestamptz NOT NULL DEFAULT now()
);
```

**Fields:**
- `id` — UUID primary key.
- `project_id` — Foreign key to `scribe_projects.id`.
- `sku_id` — Foreign key to `scribe_skus.id` (**required, never null**).
- `question` — The question text.
- `source` — Optional source (e.g., "user", "ai", "csv").

**RLS (all verbs):** `project_id IN (SELECT id FROM scribe_projects WHERE created_by = auth.uid())`.

**Notes:**
- **No `sku_id = null` rows.** All questions are per-SKU.

---

### 8.7 Topics

**`scribe_topics`**

```sql
CREATE TABLE scribe_topics (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES scribe_projects(id) ON DELETE CASCADE,
  sku_id uuid NOT NULL REFERENCES scribe_skus(id) ON DELETE CASCADE,
  topic_index smallint NOT NULL,
  title text NOT NULL,
  description text,
  generated_by text,
  approved boolean NOT NULL DEFAULT false,
  approved_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
```

**Fields:**
- `id` — UUID primary key.
- `project_id` — Foreign key to `scribe_projects.id`.
- `sku_id` — Foreign key to `scribe_skus.id` (**required, never null**).
- `topic_index` — Topic number (1–8 stored; up to 5 approved feed Stage C).
- `title` — Topic title.
- `description` — Optional description.
- `generated_by` — `llm` or `human`.
- `approved` — Whether topic is approved.
- `approved_at` — Timestamp of approval.

**RLS (all verbs):** `project_id IN (SELECT id FROM scribe_projects WHERE created_by = auth.uid())`.

---

### 8.8 Generated Amazon Content

**`scribe_generated_content`**

```sql
CREATE TABLE scribe_generated_content (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES scribe_projects(id) ON DELETE CASCADE,
  sku_id uuid NOT NULL REFERENCES scribe_skus(id) ON DELETE CASCADE,
  version int NOT NULL DEFAULT 1,
  title text,
  bullets jsonb,
  description text,
  backend_keywords text,
  model_used text,
  prompt_version text,
  approved boolean NOT NULL DEFAULT false,
  approved_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
```

**Fields:**
- `id` — UUID primary key.
- `project_id` — Foreign key to `scribe_projects.id`.
- `sku_id` — Foreign key to `scribe_skus.id`.
- `version` — Version number (increments on regenerate).
- `title` — Generated product title.
- `bullets` — JSONB array of 5 bullet points.
- `description` — Generated product description.
- `backend_keywords` — Generated backend keywords.
- `model_used` — LLM model name.
- `prompt_version` — Prompt version identifier.
- `approved` — Whether copy is approved.
- `approved_at` — Timestamp of approval.

**RLS (all verbs):** `project_id IN (SELECT id FROM scribe_projects WHERE created_by = auth.uid())`.

---

### 8.9 (Optional) Long-running Jobs

**`scribe_generation_jobs`**

```sql
CREATE TABLE scribe_generation_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES scribe_projects(id) ON DELETE CASCADE,
  job_type text NOT NULL,
  status text NOT NULL DEFAULT 'queued',
  payload jsonb,
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);
```

**Fields:**
- `id` — UUID primary key.
- `project_id` — Foreign key to `scribe_projects.id`.
- `job_type` — `topics` or `copy`.
- `status` — `queued`, `running`, `succeeded`, `failed`.
- `payload` — JSONB payload (e.g., SKU IDs, options).
- `error_message` — Error message if failed.
- `created_at`, `completed_at` — Timestamps.

**RLS (all verbs):** `project_id IN (SELECT id FROM scribe_projects WHERE created_by = auth.uid())`.

---

### 8.10 Archived Project Enforcement

- **Archived projects are read-only.** Reads are allowed for view/export; writes are blocked (INSERT/UPDATE/DELETE) on projects and all child tables.
- **Preferred enforcement:** DB-level RLS guard on child tables to block writes when the parent project status is `archived`:
  - For tables with `project_id`: Add RLS check: `(SELECT status FROM scribe_projects WHERE id = project_id) != 'archived'`.
  - For tables with only `sku_id`: Join via `sku_id → scribe_skus → project_id` then apply the same status check.
- Apply this guard to all child tables (SKUs, variant attributes/values, keywords, questions, topics, generated_content, generation_jobs).

---

### 8.11 Deletes / Cascades

- Project deletes are discouraged; prefer archive.
- If deletes are allowed, use `ON DELETE CASCADE` on child tables to prevent orphans.
- Document the chosen approach when implementing migrations.

---

## 9. 🗂 Archiving Logic

- **Archive project:** Set `status = 'archived'`; hidden from main list; generated content preserved.
- **View Archive:** Button shows the user's archived projects only.
- **Restore project:** Set status back to previous active value (`draft` or `stage_a_approved`).
- **Delete:** Future hard-delete option.

---

## 10. 🚦 Project Status States

- `draft` — Stage A in progress; only status that allows editing.
- `stage_a_approved` — Stage A locked after approval; Stage B/C are currently disabled and cannot be progressed until re-enabled.
- `archived` — Hidden, read-only.

---

## 11. 📦 Outputs

**CSV Export (one row per SKU):**
- `sku_code`
- `asin`
- `product_name`
- `brand_tone`
- `target_audience`
- `supplied_content`
- `words_to_avoid` (pipe-separated: `word1|word2|word3`)
- Variant attributes (one column per attribute)
- `keywords` (pipe-separated: `kw1|kw2|kw3`)
- `questions` (pipe-separated or quoted list)
- `title` (Stage C, reserved; empty in current release)
- `bullet_1`–`bullet_5` (Stage C, reserved; empty in current release)
- `description` (Stage C, reserved; empty in current release)
- `backend_keywords` (Stage C, reserved; empty in current release)

---

## 12. 🌐 UI Style Note

- Follow the existing Agency OS CTA style (rounded-2xl, primary blue, shadowed hover state) for primary actions like Create/Generate/Approve across Scribe screens to keep consistency with the homepage.

---

## 13. 🌐 API Contract (Scaffolding Guide)

### 13.1 Auth & Ownership

- All routes are user-scoped: data is filtered via `scribe_projects.created_by = auth.uid()`, with child tables joined through `project_id`.
- Error envelope for auth/perm: `{"error": {"code": "unauthorized|forbidden", "message": "..."}}`.
- Admin bypass can be added later (future).

---

### 13.2 Project CRUD & Metadata

- `GET /projects` — Paginated, sorted (default: page=1, size=20, sort=updated_at desc) scoped to current user.
- `POST /projects` — Create.
- `GET /projects/:id` — Detail scoped to owner.
- `PATCH /projects/:id` — Update metadata/status.
- `POST /projects/:id/archive` — Mark archived (read-only).
- `POST /projects/:id/restore` — Restore from archived.
- Allowed status transitions (current): `draft ↔ stage_a_approved` (unapprove returns to draft), then `→ archived`, plus restores from archived back to `draft` or `stage_a_approved`. Future transitions for Stage B/C are reserved (see Future Stages appendix). Return 409/validation_error on invalid transitions.

---

### 13.3 Stage Approvals

- `POST /projects/:id/approve-stage-a` — Approve Stage A; transition to `stage_a_approved`.
- `POST /projects/:id/unapprove-stage-a` — Revert Stage A approval; transition back to `draft` (blocked if archived).
- Stage B/C approval routes are deferred/disabled until those stages are re-enabled (`approve-topics`, `approve-copy` return 409/validation_error if invoked).
- Each enforces the transition rules above.

---

### 13.4 Data Entry Endpoints

#### 13.4.1 SKUs

- `GET /projects/:id/skus` — List all SKUs for a project.
- `POST /projects/:id/skus` — Create a new SKU.
- `PATCH /projects/:id/skus/:sku_id` — Update SKU fields (scalar fields only).
- `DELETE /projects/:id/skus/:sku_id` — Delete a SKU.
- `POST /projects/:id/skus/:sku_id/copy-from/:source_sku_id` — Copy all data from source SKU to target SKU (see §5.5).

#### 13.4.2 Variant Attributes

- `GET /projects/:id/variant-attributes` — List all attributes.
- `POST /projects/:id/variant-attributes` — Create attribute.
- `PATCH /projects/:id/variant-attributes/:attr_id` — Update attribute name/slug.
- `DELETE /projects/:id/variant-attributes/:attr_id` — Delete attribute.

#### 13.4.3 Variant Values

- `GET /projects/:id/variant-attributes/:attr_id/values` — List all values for an attribute.
- `PATCH /projects/:id/skus/:sku_id/variant-values/:attr_id` — Set value for SKU+attribute pair.

#### 13.4.4 Keywords (Per-SKU Only)

- `GET /projects/:id/keywords` — List all keywords for project (includes `sku_id`).
- `GET /projects/:id/keywords?skuId=<uuid>` — Filter keywords by SKU.
- `POST /projects/:id/keywords` — Create keyword (requires `sku_id` in body, max 10 per SKU).
- `DELETE /projects/:id/keywords/:keyword_id` — Delete keyword.

#### 13.4.5 Customer Questions (Per-SKU Only)

- `GET /projects/:id/questions` — List all questions for project (includes `sku_id`).
- `GET /projects/:id/questions?skuId=<uuid>` — Filter questions by SKU.
- `POST /projects/:id/questions` — Create question (requires `sku_id` in body).
- `DELETE /projects/:id/questions/:question_id` — Delete question.

---

### 13.5 Generation Triggers (Async)

- `POST /projects/:id/generate-topics` — Generates per-SKU topics only (no shared topics). Returns `job_id`.
- `POST /projects/:id/generate-copy` — Supports sample (one SKU) vs all SKUs. Returns `job_id`.
- Job payload includes project_id, scope, and options; responses return job_id for polling.

---

### 13.6 Regeneration & Editing

- Per-SKU regeneration endpoints for topics or sections (title/bullets/description/backend keywords). Each returns updated content or a new job_id if async.
- Editing persisted via PATCH routes; `scribe_generated_content.version` increments on regenerate.

---

### 13.7 Job Status

- `GET /jobs/:id` — Fields: status, error_message, created_at, completed_at, payload summary. WebSockets/SSE out of scope for V1.

---

### 13.8 Archiving Enforcement

- Writes (project or child rows) return 403 if parent project `status = 'archived'`. Reads are allowed.
- Error envelope: `{"error": {"code": "forbidden", "message": "project archived"}}`.

---

### 13.9 CSV Import/Export

#### 13.9.1 Export / Template

- `GET /projects/:id/export` — Returns `text/csv` of all SKUs (also used as the template download).
- Format: One row per SKU, columns include:
  - `sku_code`, `asin`, `product_name`, `brand_tone`, `target_audience`, `supplied_content`
  - `words_to_avoid` (pipe-separated)
  - Variant attribute columns (one per attribute)
  - `keywords` (pipe-separated)
  - `questions` (pipe-separated)
  - `topics` (pipe-separated, approved topics only, ordered by topic_index, max 5)
  - Stage C fields: `title`, `bullet_1`–`bullet_5`, `description`, `backend_keywords`

#### 13.9.2 Import

- `POST /projects/:id/import` — Accepts `multipart/form-data` with CSV file.
- Upserts by `sku_code`: if the SKU exists in the project, scalar fields and words_to_avoid are patched; keywords/questions are replaced by the file contents. Otherwise, a new SKU is created.
- Splits multi-value fields (keywords, questions, words to avoid) on `|` and creates rows.
- Validates max 10 keywords per SKU, required fields present.
- Returns summary: `{created: 5, updated: 3, errors: [...]}`

---

### 13.10 Limits & Validation

- Max 50 SKUs per project.
- Max 10 keywords per SKU.
- Up to 8 topics stored per SKU; 5 selected topics required per SKU for Stage B approval and Stage C eligibility.
- Exactly 5 bullets per SKU.
- Title length limits and backend keyword byte limits enforced; return validation_error.
- Standard validation error envelope: `{"error": {"code": "validation_error", "message": "..."}}`.

---

### 13.11 Pagination & Sorting

- Defaults: `page=1`, `size=20`, `sort=updated_at desc` for project listing (and any content list if added).

---

## 14. 📝 Migration Notes

**Only needed for legacy data.** If you already run v2.0+ with per-SKU-only data, skip this section. Use these steps only when upgrading older projects that still have `sku_id = null` rows or shared/default columns.

**For existing projects with `sku_id = null` keywords/questions:**

If migrating from a previous version that supported shared keywords/questions (`sku_id = null`), run a one-time migration script:

1. For each project with `sku_id = null` keywords:
   - Option A: Fan out to all SKUs (duplicate the keyword for every SKU in the project).
   - Option B: Delete shared keywords (require user to re-enter).
   - **Recommended:** Option A (fan out) to preserve data.

2. Same for questions.

3. Update project table to remove `keywords_mode`, `questions_mode`, `brand_tone_default`, etc. columns.

4. Update SKU table to rename `brand_tone_override` → `brand_tone`, etc.

**Script pseudocode:**

```sql
-- Fan out shared keywords to all SKUs
INSERT INTO scribe_keywords (project_id, sku_id, keyword, source, priority, created_at)
SELECT
  k.project_id,
  s.id AS sku_id,
  k.keyword,
  k.source,
  k.priority,
  k.created_at
FROM scribe_keywords k
CROSS JOIN scribe_skus s
WHERE k.sku_id IS NULL
  AND s.project_id = k.project_id;

-- Delete old shared keywords
DELETE FROM scribe_keywords WHERE sku_id IS NULL;

-- Repeat for questions
INSERT INTO scribe_customer_questions (project_id, sku_id, question, source, created_at)
SELECT
  q.project_id,
  s.id AS sku_id,
  q.question,
  q.source,
  q.created_at
FROM scribe_customer_questions q
CROSS JOIN scribe_skus s
WHERE q.sku_id IS NULL
  AND s.project_id = q.project_id;

DELETE FROM scribe_customer_questions WHERE sku_id IS NULL;

-- Rename columns in scribe_skus (use ALTER TABLE RENAME COLUMN)
-- Drop columns from scribe_projects (brand_tone_default, keywords_mode, etc.)
```

---

## 15. 📚 Appendix: Why This Change?

**Previous Model:**
- Mixed "shared defaults + per-SKU overrides" with inheritance.
- Mode toggles for keywords/questions (shared vs per-SKU).
- Dot legend to indicate overrides vs inherited values.

**Problems:**
- Confusing mental model (hidden inheritance state).
- Ambiguous CSV import/export (what does empty cell mean?).
- Complex UI with multiple modes and legends.

**New Model:**
- All data is per-SKU (explicit, no inheritance).
- "Copy from SKU" for reusability (one-time duplication).
- Simpler UI (no modes, no legends).
- Clear CSV format (what you see is what you get).

**Result:**
- Easier to understand, implement, and maintain.
- Better CSV compatibility (no ambiguity).
- Users still get fast data entry via copy feature.

---

## 16. 🔮 Future Stages (Reserved Statuses)

- When Stage B is re-enabled, APPROVE TOPICS will advance projects to `stage_b_approved`.
- When Stage C is re-enabled, APPROVE COPY will advance projects to `stage_c_approved`, and final approval to `approved`.
- These statuses are reserved but not reachable in the current Stage A–only release.

---

**End of PRD v2.0**
