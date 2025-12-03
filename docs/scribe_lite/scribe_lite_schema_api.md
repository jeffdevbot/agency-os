# Scribe Lite — Canonical Schema & API Reference

**Purpose:** This document serves as the source of truth for the Scribe Lite data model and API contract. All implementation should strictly adhere to these definitions to ensure consistency and prevent "reinventing the wheel."

---

## 1. Database Schema (Supabase)

All tables are in the `public` schema. RLS is enabled and enforces `created_by = auth.uid()` via the parent `scribe_projects` table.

### 1.1 Projects (`scribe_projects`)
Metadata for a Scribe project.
- `id` (uuid, PK)
- `created_by` (uuid, FK to profiles)
- `name` (text)
- `locale` (text, e.g., 'en-US')
- `status` (text: 'draft', 'stage_a_approved', 'stage_b_approved', 'stage_c_approved', 'approved', 'archived')
- `category` (text, nullable)
- `sub_category` (text, nullable)
- `created_at`, `updated_at` (timestamptz)

### 1.2 SKUs (`scribe_skus`)
Per-SKU product data.
- `id` (uuid, PK)
- `project_id` (uuid, FK to scribe_projects)
- `sku_code` (text)
- `asin` (text, nullable)
- `product_name` (text, nullable)
- `brand_tone` (text, nullable)
- `target_audience` (text, nullable)
- `supplied_content` (text, nullable)
- `words_to_avoid` (text[], default '{}')
- `attribute_preferences` (jsonb, nullable) — *Stores Stage C attribute usage rules*
- `sort_order` (int)

### 1.3 Variant Attributes
Dynamic columns for SKUs (e.g., Color, Size).
**`scribe_variant_attributes`**
- `id` (uuid, PK)
- `project_id` (uuid, FK)
- `name` (text)
- `slug` (text)
- `sort_order` (int)

**`scribe_sku_variant_values`**
- `id` (uuid, PK)
- `sku_id` (uuid, FK)
- `attribute_id` (uuid, FK)
- `value` (text)
- *Unique constraint on (sku_id, attribute_id)*

### 1.4 Inputs (Per-SKU)
**`scribe_keywords`**
- `id` (uuid, PK)
- `project_id` (uuid, FK)
- `sku_id` (uuid, FK, NOT NULL)
- `keyword` (text)
- `priority` (int)

**`scribe_customer_questions`**
- `id` (uuid, PK)
- `project_id` (uuid, FK)
- `sku_id` (uuid, FK, NOT NULL)
- `question` (text)

### 1.5 Topics (Stage B) (`scribe_topics`)
Generated topic candidates.
- `id` (uuid, PK)
- `project_id` (uuid, FK)
- `sku_id` (uuid, FK, NOT NULL)
- `topic_index` (smallint)
- `title` (text)
- `description` (text)
- `approved` (boolean, default false)
- `generated_by` (text, e.g., 'llm')

### 1.6 Generated Content (Stage C) (`scribe_generated_content`)
Final Amazon listing copy.
- `id` (uuid, PK)
- `project_id` (uuid, FK)
- `sku_id` (uuid, FK, NOT NULL)
- `version` (int)
- `title` (text)
- `bullets` (jsonb array of strings)
- `description` (text)
- `backend_keywords` (text)
- `approved` (boolean, default false)
- `model_used` (text)
- `prompt_version` (text)

### 1.7 Jobs (`scribe_generation_jobs`)
Async job tracking for long-running LLM tasks.
- `id` (uuid, PK)
- `project_id` (uuid, FK)
- `job_type` (text: 'topics', 'copy')
- `status` (text: 'queued', 'running', 'succeeded', 'failed')
- `payload` (jsonb)
- `error_message` (text)

---

## 2. API Endpoints

All endpoints are prefixed with `/api/scribe`.

### 2.1 Projects
- `GET /projects` — List projects (paginated).
- `POST /projects` — Create project. Payload: `{ name, locale, category, subCategory }`.
- `GET /projects/:id` — Get project details.
- `PATCH /projects/:id` — Update project metadata.
- `POST /projects/:id/archive` — Archive project.
- `POST /projects/:id/restore` — Restore project.

### 2.2 SKUs (Stage A)
- `GET /projects/:id/skus` — List all SKUs.
- `POST /projects/:id/skus` — Create SKU.
- `PATCH /projects/:id/skus/:skuId` — Update SKU fields.
- `DELETE /projects/:id/skus/:skuId` — Delete SKU.
- `POST /projects/:id/skus/:skuId/copy-from/:sourceSkuId` — Copy data from another SKU.

### 2.3 Inputs (Stage A)
- `GET /projects/:id/keywords` — List keywords.
- `POST /projects/:id/keywords` — Create keyword. Payload: `{ skuId, keyword }`.
- `DELETE /projects/:id/keywords?id=:id` — Delete keyword.
- `GET /projects/:id/questions` — List questions.
- `POST /projects/:id/questions` — Create question. Payload: `{ skuId, question }`.
- `DELETE /projects/:id/questions?id=:id` — Delete question.
- `GET /projects/:id/variant-attributes` — List attributes.
- `POST /projects/:id/variant-attributes` — Create attribute.
- `POST /projects/:id/variant-attributes/:attrId/values` — Set variant value. Payload: `{ skuId, value }`.

### 2.4 Topics (Stage B)
- `POST /projects/:id/generate-topics` — Trigger generation job. Payload: `{ skuIds?: [] }`. Returns `{ jobId }`.
- `GET /projects/:id/topics` — List topics.
- `PATCH /projects/:id/topics/:topicId` — Update topic (e.g., approve).
- `POST /projects/:id/approve-topics` — Approve Stage B (gate: 5 approved topics/SKU).

### 2.5 Copy (Stage C)
- `POST /projects/:id/generate-copy` — Trigger generation job. Payload: `{ skuIds?: [], mode: 'all'|'sample' }`. Returns `{ jobId }`.
- `GET /projects/:id/generated-content/:skuId` — Get content for SKU.
- `PATCH /projects/:id/generated-content/:skuId` — Edit content.
- `POST /projects/:id/approve-copy` — Approve Stage C.

### 2.6 Jobs
- `GET /jobs/:id` — Poll job status. Returns `{ status, error_message, payload }`.
