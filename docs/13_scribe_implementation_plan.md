# Scribe Implementation Plan — Sliced Delivery (v2.0)

## Overview
Sliced rollout for Scribe with RLS-safe APIs, UI, and job-backed generation. Follows owner-scoped model (`created_by = auth.uid()`), archived projects read-only, consistent error envelope.

**Current scope:** Stage A/B/C are implemented. Stage C backend + UI shipped; attribute prefs UI is minimal and slated for polish. Stage B/C now support unapprove (status rollbacks only). Stage A locks editing once later stages are approved. Per-SKU-only model remains active.

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

## Slice 3 — Topics Generation & Selection (Stage B)

> Implemented and live; up to 8 per-SKU candidates with 5 approved feeding Stage C. Pending full test plan execution (see `docs/18_scribe_test_plan.md`).

### API
- `POST /projects/:id/generate-topics` — enqueue job for all SKUs (or provided SKU IDs) to generate up to 8 topics each; `GET /jobs/:id` for status. Preconditions: project status is at least `stage_a_approved`; otherwise 409/validation_error.
- `POST /projects/:id/skus/:sku_id/regenerate-topics` — optional per-SKU regenerate; same behavior as main generate.
- `GET /projects/:id/topics?skuId=...` — list topics for the SKU (up to 8) sorted by `topic_index`.
- `PATCH /projects/:id/topics/:topic_id` — edit `title`, `description`, `topic_index`, `approved`; reordering is by `topic_index`.
- `POST /projects/:id/approve-topics` — validate every SKU has at least 5 topics with `approved = true`; on success, update project status to Stage B completion status (`stage_b_approved`) to unlock Stage C/progress stepper.
- `POST /projects/:id/unapprove-topics` — allowed only when `stage_b_approved`; sets status back to `stage_a_approved` (no topic deletion).
- Validation: max 8 topics stored per SKU; at most 5 can be `approved = true`; approve-topics rejects if any SKU has fewer than 5 approved topics.

### Backend
- Job type `topics`: for each SKU, load Stage A data (SKU scalars, variant attributes/values, words_to_avoid, supplied_content, keywords max 10, questions), call LLM with a question-first prompt that clusters questions into themes and proposes up to 8 distinct topics; incorporate high-value keywords, brand tone, target audience where natural; avoid words_to_avoid. If a SKU has zero questions, still generate using supplied_content + keywords (may be generic).
- For each SKU: delete existing topics; insert up to 8 rows into `scribe_topics` with `topic_index` 1..N, `title`, `description`, `approved = false`, `generated_by = "llm"`, `sku_id` set. Mark job succeeded/failed; include per-SKU errors in job payload if any fail.
- Stage C must query only selected topics: `SELECT * FROM scribe_topics WHERE project_id = ? AND sku_id = ? AND approved = true ORDER BY topic_index LIMIT 5`.
- Job payload schema (canonical): `{ "projectId": "...", "skuIds": ["..."] | null, "jobType": "topics", "options": {} }`; `skuIds` omitted/null = all project SKUs.
- Prompt (standard): see `docs/16_scribe_stage_b_topics_slice.md` for the question-first 1–8 topics prompt (title + description with exactly three bullet sentences prefixed by "•", JSON-only). Ship a versioned prompt in code/config (e.g., `scribe_topics_prompt_v1`) and persist the `prompt_version` with each job/topics insert for traceability when prompts change.

### Frontend
- Per-SKU topics list (up to 8) with inline edit, select/deselect (toggles `approved`), drag-to-reorder (`topic_index`), and regenerate per SKU; humorous loading copy.
- Approval UI blocked until every SKU has 5 selected topics; selected topics are the only ones used by Stage C.
- Regenerate behavior: replaces all topics for that SKU (selections cleared).
- Routing: keep Stage A/B/C on the same page with tabs/panels; stepper clicks switch tabs (no new route) for now.

### Test (when enabled)
- Job lifecycle; per-SKU topic persistence (up to 8 rows); approve guard requiring 5 selected (`approved = true`) topics per SKU; RLS respected; reordering updates `topic_index`; regenerate replaces topics and clears approvals; server enforces max 5 approved.

**Dependencies & risks:** Requires Stage A data/status to be stable (`stage_a_approved`). If a SKU has zero questions, the LLM still generates topics using supplied_content + keywords, but results may be more generic.

**Partial failure handling (topics job):** If some SKUs fail generation, mark job as failed and include per-SKU errors in payload; frontend should surface failed SKUs and prompt regenerate for those SKUs. Approval is blocked until all SKUs have 5 approved topics.

---

## Slice 4 — Copy Generation (Stage C)

> Pending implementation; all generated content is per-SKU only and gated on Stage B approval.

### Micro-tasks
1) **API & Schema**
   - Implement `POST /projects/:id/generate-copy` (full regenerate only in v1), `POST /projects/:id/skus/:sku_id/regenerate-copy` (full regenerate; sections optional/deferred), `PATCH /projects/:id/generated-content/:sku_id`, `POST /projects/:id/approve-copy`.
   - Enforce gates: project status `stage_b_approved`; each target SKU has 5 approved topics.
   - Enforce limits: title length (~200), bullets=5, backend keywords 249 bytes; reject/validate accordingly.
   - Optional: add lightweight attribute preferences storage on SKU (JSON) if used by prompt.
2) **Job Runner (`job_type = "copy"`)**
   - Load inputs (5 approved topics ordered, keywords, questions, brand tone, target audience, supplied content, variant attrs/values, words_to_avoid, attribute prefs).
   - Call Stage C prompt; expect `{ title, bullets[5], description, backend_keywords, prompt_version, model/tokens }`.
   - Upsert `scribe_generated_content`; bump `version`; overwrite sections if enabled; bullets=5 and limits enforced.
   - Handle errors: per-SKU error payload; job fails if any fail; user retries via regenerate; fail fast on timeout/OpenAI error.
   - Log `scribe_usage_logs` per call (tool='scribe', project/user/job/sku, tokens/model/prompt_version).
3) **Prompt & Versioning**
   - Finalize Stage C prompt (amazon-safe rules, attribute defaults/overrides, 5 bullets, 249-byte backend keywords).
   - Set `prompt_version` (e.g., `scribe_stage_c_v1`), store per generation; regenerations use latest unless locked.
4) **Frontend**
   - Stage C tab/panel: empty state (Generate All/Sample, rules), SKU selector/swatches, editor (Title/Bullets/Description/Backend Keywords), Save (PATCH), full regenerate, version display, mini preview, approve button (requires content for all SKUs).
   - Attribute Usage mini-panel: toggle; mode auto vs user selections with per-attribute checkboxes; store prefs on SKU (lightweight) and pass to prompt.
   - Loading/error states: show brief generating/saving; surface per-SKU errors if generation fails.
5) **Tests**
   - API: guards (stage_b_approved, 5 topics), limits, approval gate, regenerate bumps version, CSV export fields.
   - Jobs: lifecycle success/fail/partial; per-SKU errors; fail fast on OpenAI/timeout; usage logs written.
   - UI smoke: empty state → generate → edit/save → regenerate (full) → approve gate; attribute prefs passed.
   - RLS: jobs/generated_content isolation; archived write-block.
   - Telemetry: verify `scribe_usage_logs` rows per copy generation call.
6) **Ops/Flags**
   - Feature-flag Stage C routes/UI.
   - Ensure env model settings reused; monitoring/logging for copy jobs.

### API
- `POST /projects/:id/generate-copy` — body `{ skuIds?: ["<uuid>", ...], mode?: "all"|"sample" }`; preconditions: project status `stage_b_approved` and each target SKU has 5 approved topics. Returns `{ jobId }`. `GET /jobs/:id` shared.
- `POST /projects/:id/skus/:sku_id/regenerate-copy` — body `{ sections?: ["title","bullets","description","backend_keywords"] }`; same preconditions; returns `{ jobId }`.
- `PATCH /projects/:id/generated-content/:sku_id` — edit content fields, enforce limits, bump `version`.
- `POST /projects/:id/approve-copy` — requires generated content per SKU (and optional per-SKU approved); sets status to `stage_c_approved`.
- `POST /projects/:id/unapprove-copy` — allowed only when `stage_c_approved`; sets status back to `stage_b_approved` (no data deletion).

### Backend
- Schema: `scribe_generated_content` includes `prompt_version`, `approved`, `approved_at`, `version`, `title`, `bullets` (jsonb, exactly 5), `description`, `backend_keywords`, `model_used`, timestamps; enforce title length (~200 chars), bullets=5, backend keyword byte cap (249 bytes).
- Attribute preferences: store lightweight per SKU (e.g., JSON on SKU) and pass to prompt; skip new table for v1. If later stored in generated_content, ensure RLS stays owner-scoped.
- Gates: API and job runner must re-check project status `stage_b_approved` and 5 approved topics per target SKU before enqueueing/processing copy jobs (cannot be enforced via DB CHECK).
- Job runner (`job_type = "copy"`): for each SKU, load inputs (5 approved topics ordered, keywords, questions, brand tone, target audience, supplied content, variant attrs/values, words_to_avoid, attribute-usage prefs). Call Stage C prompt; expect `{ title, bullets[5], description, backend_keywords, prompt_version, model/tokens }`. Upsert into `scribe_generated_content`; bump `version` on regenerate; allow section-scoped overwrite. Record per-SKU errors; if any fail, job = failed and approval stays blocked. Log `scribe_usage_logs` per call (tool='scribe', project/user/job/sku, tokens/model/prompt_version). Errors: single attempt; job marks failed on OpenAI/network error; user retries via regenerate. Timeouts should fail fast to avoid hung jobs.

### Prompt/Output
```json
{
  "title": "...",
  "bullets": ["...", "...", "...", "...", "..."],
  "description": "...",
  "backend_keywords": "..."
}
```
Inputs: product name, SKU/ASIN, brand tone, target audience, supplied content, variant attrs, 5 approved topics (title + 3 bullets each), keywords, questions, words_to_avoid, attribute-usage prefs (auto vs per-attribute section rules). Guardrails: 5 bullets exactly; title length limit; backend keyword byte limit (249 bytes); avoid forbidden words; ground on topics; smart defaults for attributes unless overrides specified; store `prompt_version` per generation.

Regeneration strategy: full LLM call by default; extract/overwrite only requested sections if section-scoped regenerations are enabled (optional). Default v1 can ship with full regenerate only to avoid drift; per-section regenerate is nice-to-have and can be deferred.

### Frontend
- Stage C tab/panel in `/scribe/[projectId]`:
  - Empty state: Generate All / Generate Sample buttons, Amazon rules summary, “No copy yet” message.
  - SKU selector/swatches: simple buttons per SKU; one active.
  - Left editor: Title, Bullets (5), Description, Backend Keywords; per-section regenerate; Save (PATCH); per-SKU approve toggle; show `version`.
  - Right preview: read-only “mini PDP” showing saved fields; updates on Save.
  - Attribute Usage mini-panel: toggle/link; mode auto vs user selections with per-attribute checkboxes for Title/Bullets/Description/Backend Keywords (lightweight storage on SKU, passed to prompt).
  - Approve Stage C button: validate all SKUs have generated content; set `stage_c_approved`.
- CSV export: include Stage C fields per SKU (title, bullet_1..5, description, backend_keywords); no Stage C import in v1.
- Feature flag: gate Stage C UI/routes until ready.

### Test (when enabled)
- API: generate-copy rejects if not `stage_b_approved` or SKUs missing 5 approved topics; job lifecycle success/fail/partial; regenerate bumps `version`; approve-copy guard; limits enforced.
- RLS: isolation on jobs/generated_content; archived write-block.
- UI smoke: generate → render copy → edit → regenerate (full by default) → approve gate; attribute-usage prefs passed to prompt.
- Telemetry: usage log per copy generation call.
- CSV export correctness for Stage C fields.

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

- When Stage B returns, topic approval will advance projects to `stage_b_approved`.
- When Stage C returns, copy approval will advance to `stage_c_approved`, and final approval to `approved`.
- These statuses are reserved and not reachable in the current Stage A–only release.

---

**End of Implementation Plan v2.0**
