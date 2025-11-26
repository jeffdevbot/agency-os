# Scribe Implementation Plan — Sliced Delivery (v2.0)

## Overview
Sliced rollout for Scribe with RLS-safe APIs, UI, and job-backed generation. Follows owner-scoped model (`created_by = auth.uid()`), archived projects read-only, consistent error envelope.

**Current scope:** Stage A per-SKU-only model is active. Stages B/C (topics and copy generation) are deferred/disabled until the redesigned flow is ready.

**Key Change in v2.0:** Stage A now uses a **per-SKU-only model** with no shared defaults or overrides. All data is explicit and per-SKU, with "Copy from SKU" as the reusability mechanism.

---

## Slice 1 — Project Shell & RLS Smoke

### API
- `GET /projects` (pagination/sort defaults), `POST /projects`, `GET /projects/:id`, `PATCH /projects/:id` (metadata/status), `POST /projects/:id/archive`, `POST /projects/:id/restore`.
- Enforce owner scope; allowed statuses for now: `draft`, `stage_a_approved`, `archived`. Future statuses are reserved (see Future Stages) and are not reachable until Stage B/C return.
- Valid transitions (current release): `draft → stage_a_approved → archived`, plus `archived → draft|stage_a_approved` on restore.
- Invalid status transitions return 409/validation_error; archived projects read-only (403 on writes).

### Frontend
- Project list with pagination/sort; create form; detail view with archive/restore buttons; status badges.

### Test
- Two-user RLS isolation; archive write-block; status transition guard; pagination/sort defaults honored.

---

## Slice 2 — Product Data (Stage A) — Per-SKU Model

### API

#### 2.1 SKUs (Per-SKU Fields Only)
- `GET /projects/:id/skus` — List all SKUs with scalar fields: `sku_code`, `asin`, `product_name`, `brand_tone`, `target_audience`, `words_to_avoid` (array), `supplied_content`.
- `POST /projects/:id/skus` — Create new SKU with all scalar fields.
- `PATCH /projects/:id/skus/:sku_id` — Update scalar fields inline (e.g., brand tone, target audience, supplied content).
- `DELETE /projects/:id/skus/:sku_id` — Delete SKU.
- **Remove:** `brand_tone_default`, `target_audience_default`, `supplied_content_default`, `words_to_avoid_default` from `scribe_projects`.
- **Remove:** `brand_tone_override`, `target_audience_override`, etc. from `scribe_skus` (use plain field names: `brand_tone`, `target_audience`).
- **Remove:** `keywords_mode`, `questions_mode`, `topics_mode` from `scribe_projects`.
- Enforce max 50 SKUs/project.

#### 2.2 Variant Attributes/Values
- `GET /projects/:id/variant-attributes` — List attributes.
- `POST /projects/:id/variant-attributes` — Create attribute.
- `PATCH /projects/:id/variant-attributes/:attr_id` — Update attribute name/slug.
- `DELETE /projects/:id/variant-attributes/:attr_id` — Delete attribute.
- `GET /projects/:id/variant-attributes/:attr_id/values` — List values for attribute.
- `PATCH /projects/:id/skus/:sku_id/variant-values/:attr_id` — Set value for SKU+attribute pair.

#### 2.3 Keywords (Per-SKU Only)
- `GET /projects/:id/keywords` — List all keywords for project (returns `sku_id` for each).
- `GET /projects/:id/keywords?skuId=<uuid>` — Filter keywords by SKU.
- `POST /projects/:id/keywords` — Create keyword (requires `sku_id` in body, never null).
- `DELETE /projects/:id/keywords/:keyword_id` — Delete keyword.
- **Remove:** Support for `sku_id = null` (shared keywords).
- **Enforce:** Max 10 keywords per SKU.
- **Migration:** Fan out any existing `sku_id = null` keywords to all SKUs in the project (see §2.8).

#### 2.4 Customer Questions (Per-SKU Only)
- `GET /projects/:id/questions` — List all questions for project (returns `sku_id` for each).
- `GET /projects/:id/questions?skuId=<uuid>` — Filter questions by SKU.
- `POST /projects/:id/questions` — Create question (requires `sku_id` in body, never null).
- `DELETE /projects/:id/questions/:question_id` — Delete question.
- **Remove:** Support for `sku_id = null` (shared questions).
- **Migration:** Fan out any existing `sku_id = null` questions to all SKUs in the project (see §2.8).

#### 2.5 Copy from SKU
- `POST /projects/:id/skus/:sku_id/copy-from/:source_sku_id` — Copy all data from source SKU to target SKU.
  - **Scalar fields:** `brand_tone`, `target_audience`, `supplied_content`, `words_to_avoid` (array).
  - **Multi-value:** Duplicate rows in `scribe_keywords` and `scribe_customer_questions` with new `sku_id`.
  - **Variant values:** Copy all `scribe_sku_variant_values` rows from source to target.
  - **Result:** Target SKU has independent, identical values (no live link).

#### 2.6 Stage A Approval
- `POST /projects/:id/approve-stage-a` — Approve Stage A; transition status to `stage_a_approved`.
- `POST /projects/:id/unapprove-stage-a` — Revert to `draft` for edits (blocked if archived).
- **Validation:**
  - At least one SKU exists.
  - Each SKU has `sku_code` and `product_name`.
  - Max 10 keywords per SKU enforced.
- Stage B/C are deferred; approval simply locks Stage A data until those stages are re-enabled.

#### 2.7 CSV Import/Export (Per-SKU Format)

**Export:**
- `GET /projects/:id/export` — Returns `text/csv` with one row per SKU (no multi-row variant). Serves as the download template.
- Columns: `sku_code`, `asin`, `product_name`, `brand_tone`, `target_audience`, `supplied_content`, `words_to_avoid` (pipe-separated), variant attributes, `keywords` (pipe-separated), `questions` (pipe-separated), Stage C fields (title, bullets, description, backend keywords — reserved/empty for now).

**Import:**
- `POST /projects/:id/import` — Accepts `multipart/form-data` with CSV file.
- Parse CSV and upsert SKUs by `sku_code`: create if missing; patch scalar fields + words_to_avoid if present; replace keywords/questions with file contents for that SKU.
- Split multi-value fields (keywords, questions, words to avoid) on `|`; create keyword/question rows and map `words_to_avoid` items into the array column.
- Validate: max 10 keywords per SKU, required fields present.
- Return summary: `{created: 5, updated: 3, errors: [...]}` 

#### 2.8 Migration (Fan-out Shared Keywords/Questions)

**Only needed for legacy data.** If you’re already on the per-SKU-only model with no `sku_id = null` rows or shared/default columns, skip this step.

**One-time migration script** to convert existing `sku_id = null` records to per-SKU records:

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

-- Remove old columns from scribe_projects
ALTER TABLE scribe_projects DROP COLUMN IF EXISTS brand_tone_default;
ALTER TABLE scribe_projects DROP COLUMN IF EXISTS target_audience_default;
ALTER TABLE scribe_projects DROP COLUMN IF EXISTS words_to_avoid_default;
ALTER TABLE scribe_projects DROP COLUMN IF EXISTS supplied_content_default;
ALTER TABLE scribe_projects DROP COLUMN IF EXISTS keywords_mode;
ALTER TABLE scribe_projects DROP COLUMN IF EXISTS questions_mode;
ALTER TABLE scribe_projects DROP COLUMN IF EXISTS topics_mode;

-- Rename columns in scribe_skus (remove _override suffix)
ALTER TABLE scribe_skus RENAME COLUMN brand_tone_override TO brand_tone;
ALTER TABLE scribe_skus RENAME COLUMN target_audience_override TO target_audience;
ALTER TABLE scribe_skus RENAME COLUMN words_to_avoid_override TO words_to_avoid;
ALTER TABLE scribe_skus RENAME COLUMN supplied_content_override TO supplied_content;

-- Add NOT NULL constraint to sku_id in keywords/questions
ALTER TABLE scribe_keywords ALTER COLUMN sku_id SET NOT NULL;
ALTER TABLE scribe_customer_questions ALTER COLUMN sku_id SET NOT NULL;
```

**Run this migration before deploying v2.0 frontend.**

---

### Frontend

#### 2.9 Stage A Grid (Grouped-Row Layout, No Modals)

**Layout:**
- Excel-style grouped-row grid where each SKU is a block of rows.
- **Primary row:** All scalar fields (`sku_code`, `asin`, `product_name`, `brand_tone`, `target_audience`, `supplied_content`, variant attribute values).
- **Child rows:** One row per multi-value item (each `words_to_avoid`, `keyword`, `question`) indented under the SKU. Inline add rows are always visible; no modals, chips, or side panels.
- **CSV alignment:** Pipe-separated cells map directly to the child rows; no multi-row CSV variant.

**Include ASCII wireframe in the doc:**
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

**Toolbar:**
- [Add SKU] [Import CSV] [Export CSV] [Add Attribute]

**Scalar Field Editing:**
- Inline editing for all scalar fields on the primary row (brand tone, target audience, supplied content).
- Autosave on blur or Enter.
- No shared defaults, overrides, legends, or "Apply to All" — reuse is only via Copy-from-SKU.

**Multi-Value Field Editing:**
- One indented child row per item (words_to_avoid, keywords, questions) with inline edit/delete.
- Inline add row always present per multi-value section (type → Enter/blur to save).
- No modals, chips, legends, or side panels.
- Max 10 keywords per SKU enforced (show count/limit inline).
- `words_to_avoid` UI uses child rows; frontend concatenates them into the array before PATCH.

**Variant Attributes:**
- Dynamic columns for each attribute.
- Inline editing per SKU.

**Remove:**
- Mode dropdown (e.g., "Mode: Shared / Per SKU") — no longer needed.
- Shared keyword/question management modals — all data is per-SKU.

#### 2.10 Copy from SKU Feature

**UI:**
- Each SKU primary row (except the first) shows a "Copy from…" dropdown or button.
- Dropdown lists all existing SKUs in the project.

**Action:**
- User selects source SKU `S` to copy into target SKU `T`.
- Frontend calls `POST /projects/:id/skus/:sku_id/copy-from/:source_sku_id`.
- All scalar fields, multi-value lists, and variant values are duplicated.
- Show success toast: "Data copied from [SKU code]".

**Result:**
- Target SKU has independent, identical values (one-time clone, no linkage).
- User can then edit target SKU as needed.

#### 2.11 Stage A Review & Approve

**Review Screen:**
- Summary table showing all SKUs with key fields.
- Show counts for keywords, questions, words to avoid per SKU.
- Show variant attributes and values.

**Approve Button:**
- "APPROVE & CONTINUE" → status changes to `stage_a_approved`.
- Stage B/C are deferred; approval locks Stage A until those stages are re-enabled.

---

### Test
- Limits (50 SKUs, 10 keywords/SKU); RLS on child writes.
- Stage A approval flow to `stage_a_approved`; SKU CRUD; per-SKU keyword/question creation.
- Copy from SKU: all data duplicated correctly; no live link.
- CSV import/export: multi-value fields encoded/decoded correctly; `words_to_avoid` child rows map to array.
- Variant attributes: dynamic columns; per-SKU values saved.
- **Remove tests for:** Shared/per-SKU modes, mode toggles, shared keywords/questions, inherited values, dot legends.
- **Add test for:** Migration script (fan-out shared to per-SKU).

---

## Slice 3 — Topics Generation (Stage B)

> Deferred. When enabled, topics are per-SKU only (no shared topics).

### API
- `POST /projects/:id/generate-topics` (per-SKU only) returns job_id; `GET /jobs/:id` for status.
- Topics CRUD (edit text, reorder topic_index) per SKU; approve topics endpoint (when re-enabled) advances to the Stage B completion status (reserved).
- Preconditions (when enabled): Stage A must be approved; reject (409/validation_error) otherwise.

### Backend
- Per-SKU LLM call: generate exactly 5 topics for each SKU using only that SKU’s data (keywords, customer questions, brand tone, target audience, supplied content, variant attributes, words to avoid).
- Persist 5 rows per SKU in `scribe_topics` with `sku_id` set; job runner updates job status/error.

### Frontend
- Per-SKU topics table (`| SKU | Topic 1..5 |`) with inline edit, reorder, and regenerate per SKU; loading copy remains humorous.
- Approval (when enabled) advances to the Stage B completion status (reserved).

### Test (when enabled)
- Job lifecycle; per-SKU topic persistence; exactly 5 topics per SKU; approval transitions to Stage B completion; RLS respected.

---

## Slice 4 — Copy Generation (Stage C)

> Deferred. When enabled, all generated content is per-SKU only.

### API
- `POST /projects/:id/generate-copy` (sample vs all SKUs) returns job_id; `GET /jobs/:id` shared.
- Per-SKU regeneration endpoints for sections (title, bullets, description, backend keywords); bump `scribe_generated_content.version`.
- Generated content CRUD/edit; approve copy endpoint (when enabled) advances to Stage C completion and final approval statuses (reserved).
- Enforce limits: Title length, backend byte limit, exactly 5 bullets per SKU.
- Preconditions (when enabled): topics must be approved; reject requests otherwise (409/validation_error).

### Backend
- Per-SKU generation uses only that SKU’s topics (5), keywords, customer questions, brand tone, target audience, supplied content, variant attributes, words to avoid. No shared/merged fields.
- Store per-SKU output in `scribe_generated_content`; job runner updates status/error.

### Frontend
- Per-SKU review table with inline edit/regenerate for Title, Bullets (5), Description, Backend Keywords.
- CSV export includes all Stage C fields per SKU only (no shared columns).
- Approval (when enabled) advances to Stage C completion (reserved).

### Test (when enabled)
- Job lifecycle; per-SKU content persistence; version increment on regenerate; approval guard; limits enforced; CSV per-SKU correctness.

---

## Slice 5 — Export & Polish

### API
- `GET /projects/:id/export` returns text/csv of all SKUs; reads allowed for archived.

### Frontend
- Export buttons; archive view toggle; polish UX.

### Ops
- Docs updates, monitoring/logging for jobs; optional admin bypass flag.

### Test
- Export correctness (per-SKU format with pipe-separated multi-value fields); archived read-only; pagination/sorting defaults; job telemetry visible if added.

---

## Cross-Cutting

### Standards
- Standard error envelope; shared job polling client.
- Rate limits/LLM keys wiring; feature flags if needed.
- Telemetry/usage logging (optional after core flows stable).

### Concurrency Safety
- Use optimistic locking on mutable rows (topics, generated_content) via `updated_at`/version check; reject on conflict (409) to prevent clobber during parallel edits/regenerations.

### UI Consistency
- Primary actions (Create/Generate/Approve) use the shared CTA style from the homepage (rounded-2xl, primary blue, shadowed hover state).

---

## Migration Checklist

**Before deploying v2.0:**

1. **Run migration script** (§2.8) to fan out shared keywords/questions to all SKUs.
2. **Drop columns** from `scribe_projects`: `brand_tone_default`, `target_audience_default`, `words_to_avoid_default`, `supplied_content_default`, `keywords_mode`, `questions_mode`, `topics_mode`.
3. **Rename columns** in `scribe_skus`: `brand_tone_override` → `brand_tone`, etc.
4. **Add NOT NULL constraint** to `scribe_keywords.sku_id` and `scribe_customer_questions.sku_id`.
5. **Test migration** on staging environment with real data.
6. **Update API** to require `sku_id` in keywords/questions POST requests (reject if null).
7. **Deploy frontend** with new per-SKU UI (no mode toggles, no shared management modals).

---

## Removed Features (v1 → v2)

**Frontend:**
- Mode dropdown for keywords/questions/words to avoid ("Mode: Shared / Per SKU").
- "Set shared" header links for brand tone, target audience, supplied content.
- Dot legend for inherited vs overridden values.
- Shared keyword/question management modals or side panels for multi-value fields.
- Chip inputs/modals for keywords/questions/words_to_avoid.
- "Apply to All" toggle for scalar fields.

**Backend:**
- `brand_tone_default`, `target_audience_default`, etc. in `scribe_projects`.
- `brand_tone_override`, `target_audience_override`, etc. in `scribe_skus`.
- `keywords_mode`, `questions_mode`, `topics_mode` in `scribe_projects`.
- Support for `sku_id = null` in `scribe_keywords` and `scribe_customer_questions`.

**API:**
- Endpoints that created/read shared keywords/questions (`sku_id = null`).
- "Apply to All" semantics in PATCH requests.

---

## New Features (v2)

**Frontend:**
- Grouped-row Stage A layout: primary row for scalars; indented child rows for each multi-value item; inline add rows (no modals/chips).
- Per-SKU-only data entry (no shared defaults/overrides/modes/legends).
- "Copy from SKU" dropdown/button to duplicate data between SKUs (one-time clone).
- `words_to_avoid` edited as child rows; frontend aggregates to array before PATCH.

**Backend:**
- Per-SKU-only data model (all keywords/questions have `sku_id`).
- `POST /projects/:id/skus/:sku_id/copy-from/:source_sku_id` endpoint.
- Migration script to fan out shared data to per-SKU.

**CSV:**
- Simple, explicit format: one row per SKU, pipe-separated multi-value fields that map to child rows.
- No ambiguity: what you see is what you get.

---

## Future Stages (Reserved Statuses)

- When Stage B returns, topic approval will advance projects to `topics_generated`.
- When Stage C returns, copy approval will advance to `copy_generated`, and final approval to `approved`.
- These statuses are reserved and not reachable in the current Stage A–only release.

---

**End of Implementation Plan v2.0**
