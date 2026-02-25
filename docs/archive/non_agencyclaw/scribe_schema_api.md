# Scribe — Schema & API Reference (Canonical)

_Status (2025-11-28, EST): Stage A/B/C backend routes and Stage C UI are live; attribute preferences are stored/passed but the overrides UI is minimal and slated for polish._

Scribe canonical schema and endpoints for Stages A–C. Use this as the single source of truth for field names, statuses, and routes.

---

## 1) Project Statuses
- `draft`
- `stage_a_approved`
- `stage_b_approved` (Stage B complete; unlocks Stage C)
- `stage_c_approved` (Stage C complete; final approval)
- `approved` (final state, after Stage C)
- `archived`
- Unapprove paths: `stage_b_approved → stage_a_approved` (unapprove-topics); `stage_c_approved → stage_b_approved` (unapprove-copy).

## 1.1 Project Locale
- Column: `scribe_projects.locale` (text, NOT NULL, default `en-US`)
- Allowed values: `en-US`, `en-CA`, `en-GB`, `en-AU`, `fr-CA`, `fr-FR`, `es-MX`, `es-ES`, `de-DE`, `it-IT`, `pt-BR`, `nl-NL`
- Purpose: BCP 47 locale used to steer Stage B/C generation prompts.

---

## 2) Tables (Core Fields)

### `scribe_projects`
- `id` (uuid, pk), `created_by` (fk profiles.id, owner scope), `name`, `locale` (BCP 47, NOT NULL, default `en-US`), `category`, `sub_category`, `status`, timestamps.
- RLS: `created_by = auth.uid()`.

### `scribe_skus`
- `id` (uuid, pk), `project_id` fk, `sku_code`, `asin`, `product_name`, `brand_tone`, `target_audience`, `words_to_avoid` text[], `supplied_content`, `attribute_preferences` jsonb, timestamps.
- `attribute_preferences`: Optional. Shape: `{ mode?: "auto"|"overrides", rules?: Record<string, { sections: ("title"|"bullets"|"description"|"backend_keywords")[] }> }`. Defaults to auto mode when null. Controls how variant attributes are used in Stage C copy generation.
- RLS: project owner only.

### `scribe_variant_attributes`
- `id` (uuid, pk), `project_id` fk, `name`, `slug`, timestamps.

### `scribe_sku_variant_values`
- `id` (uuid, pk), `project_id` fk, `sku_id` fk, `variant_attribute_id` fk, `value`, timestamps.

### `scribe_keywords`
- `id` (uuid, pk), `project_id` fk, `sku_id` fk (NOT NULL), `keyword`, `source`, `priority`, timestamps.
- Limit: max 10 per SKU.

### `scribe_customer_questions`
- `id` (uuid, pk), `project_id` fk, `sku_id` fk (NOT NULL), `question`, `source`, timestamps.

### `scribe_topics`
- `id` (uuid, pk), `project_id` fk, `sku_id` fk (NOT NULL), `topic_index` (1..8), `title`, `description`, `generated_by`, `approved` (bool, default false), `approved_at`, timestamps.
- Stage B stores up to 8 topics per SKU; only `approved = true` (max 5) feed Stage C.
- RLS: owner scope via project (`project_id IN (SELECT id FROM scribe_projects WHERE created_by = auth.uid())`).
- Description format: Stage B prompt returns a 3-bullet string (newline-separated, prefixed with "• "); frontend renders as a bullet list.

### `scribe_generated_content` (Stage C)
- `id` (uuid, pk), `project_id` fk, `sku_id` fk, `version` int, `title`, `bullets` jsonb (5 items), `description`, `backend_keywords`, `model_used`, `prompt_version`, `approved` bool, `approved_at`, timestamps.
- Constraints (enforce in code/db): exactly 5 bullets; title length cap (e.g., ~200 chars); backend_keywords byte cap (249 bytes).
- Gates are enforced in API/job logic: project must be `stage_b_approved` and each target SKU must have 5 approved topics before generating copy.
- Note: Attribute usage preferences are stored on `scribe_skus.attribute_preferences`, not here.

---

## 3) API Endpoints (Paths/Verbs)

### Projects & Stage A (active)
- `GET /projects`
- `POST /projects`
- `GET /projects/:id`
- `PATCH /projects/:id` (metadata/status)
- `POST /projects/:id/archive`
- `POST /projects/:id/restore`
- `POST /projects/:id/approve-stage-a`
- `POST /projects/:id/unapprove-stage-a`

### SKUs & Stage A child data
- `GET /projects/:id/skus`
- `POST /projects/:id/skus`
- `PATCH /projects/:id/skus/:sku_id`
- `DELETE /projects/:id/skus/:sku_id`
- `POST /projects/:id/skus/:sku_id/copy-from/:source_sku_id`
- Variant attrs: `GET/POST/PATCH/DELETE /projects/:id/variant-attributes`, `GET /projects/:id/variant-attributes/:attr_id/values`, `PATCH /projects/:id/skus/:sku_id/variant-values/:attr_id`
- Keywords: `GET /projects/:id/keywords[?skuId=...]`, `POST /projects/:id/keywords`, `DELETE /projects/:id/keywords/:keyword_id`
- Questions: `GET /projects/:id/questions[?skuId=...]`, `POST /projects/:id/questions`, `DELETE /projects/:id/questions/:question_id`
- Import/Export: `GET /projects/:id/export` (CSV), `POST /projects/:id/import` (CSV)

### Stage B — Topics (deferred, model finalized)
- Generate: `POST /projects/:id/generate-topics` (all SKUs or provided SKU IDs), `GET /jobs/:id`
- Per-SKU regenerate: `POST /projects/:id/skus/:sku_id/regenerate-topics`
- List: `GET /projects/:id/topics?skuId=...`
- Edit/reorder/approve: `PATCH /projects/:id/topics/:topic_id` (title, description, topic_index, approved)
- Approve Stage B: `POST /projects/:id/approve-topics` (requires 5 approved topics per SKU; sets `stage_b_approved`)
- Unapprove Stage B: `POST /projects/:id/unapprove-topics` (allowed only when `stage_b_approved`; sets `stage_a_approved`; does not delete topics)

### Stage C — Copy Generation (deferred)
- Generate: `POST /projects/:id/generate-copy` (sample/all), `GET /jobs/:id`
  - Preconditions: project status `stage_b_approved`; each target SKU has 5 approved topics.
  - Request body: `{ skuIds?: ["<uuid>", ...], mode?: "all"|"sample" }` (omitting skuIds = all SKUs).
  - Response: `{ jobId: "<uuid>" }`
- Regenerate: `POST /projects/:id/skus/:sku_id/regenerate-copy` — default full regenerate; optional `{ sections?: ["title","bullets","description","backend_keywords"] }` if section-scoped regenerate is enabled.
- Approve Stage C: `POST /projects/:id/approve-copy` (requires generated content per SKU; sets `stage_c_approved`)
- Unapprove Stage C: `POST /projects/:id/unapprove-copy` (allowed only when `stage_c_approved`; sets `stage_b_approved`; does not delete copy)

---

## 4) Stage-Specific Logic (Canonical)
- Stage A approval sets `stage_a_approved`; archived is read-only.
- Stage B topics: store up to 8 per SKU; only approved topics (max 5, ordered by topic_index) are used by Stage C.
- Stage C must select topics via: `SELECT * FROM scribe_topics WHERE project_id = ? AND sku_id = ? AND approved = true ORDER BY topic_index LIMIT 5`.
- Stage B job payload (canonical): `{ "projectId": "<uuid>", "skuIds": ["<uuid>", ...] | null, "jobType": "topics", "options": {} }`; null/omitted `skuIds` = all SKUs in project.

---

## 5) Token Usage Telemetry (Canonical)
- Track token usage by tool (`scribe`), user, and project for generation jobs.
- Preferred table (add if absent): `scribe_usage_logs`
  - Fields: `id` (uuid pk), `tool` text (`'scribe'`), `project_id` fk, `user_id` fk (`profiles.id`), `job_id` fk (`scribe_generation_jobs.id`, nullable), `sku_id` fk (`scribe_skus.id`, nullable), `prompt_tokens` int, `completion_tokens` int, `total_tokens` int, `model` text, `created_at` timestamptz default now().
  - RLS: owner scope via project (`project_id IN (SELECT id FROM scribe_projects WHERE created_by = auth.uid())`); allow insert/select to owner only.
  - Insert one row per LLM call (topics or copy).
- If this table does not exist, run the migration below.

**Migration (if needed):**
```sql
CREATE TABLE IF NOT EXISTS scribe_usage_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tool text NOT NULL,
  project_id uuid NOT NULL REFERENCES scribe_projects(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  job_id uuid REFERENCES scribe_generation_jobs(id) ON DELETE SET NULL,
  sku_id uuid REFERENCES scribe_skus(id) ON DELETE SET NULL,
  prompt_tokens int,
  completion_tokens int,
  total_tokens int,
  model text,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- RLS
ALTER TABLE scribe_usage_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY scribe_usage_logs_owner_select ON scribe_usage_logs
  FOR SELECT USING (project_id IN (SELECT id FROM scribe_projects WHERE created_by = auth.uid()));
CREATE POLICY scribe_usage_logs_owner_insert ON scribe_usage_logs
  FOR INSERT WITH CHECK (project_id IN (SELECT id FROM scribe_projects WHERE created_by = auth.uid()));
```

---

## 6) Known Inconsistencies to Fix
- None currently flagged. Keep this doc authoritative for schema/API/status names.
