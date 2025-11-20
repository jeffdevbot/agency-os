# Schema & Tenancy — Micro-Spec

## Scope

This micro-spec defines the **database layer** for Composer:

- Multi-tenant model (organizations and projects)
- Core persistence entities (projects, SKUs, keywords, content, locales, review, exports, jobs)
- Token usage tracking for all LLM calls
- Deletion and cascading behavior
- Indexing patterns to support our primary queries

**In scope:**

- Tables, relationships, and constraints
- Tenancy model via `organization_id`
- High-level purpose of each table
- Deletion behavior (`ON DELETE CASCADE` vs soft delete)
- Token usage logging design

**Out of scope:**

- API routes
- RLS policies details
- Application-level business logic
- Detailed DDL syntax (lives in migrations)

---

## Data Shapes (Entities & Relationships)

> All Composer tables are **scoped by `organization_id`** to support multi-tenant SaaS and simple RLS.

### 1. Organizations & Projects

**`composer_organizations`**

- One row per paying org/agency/team.
- Columns: `id`, `name`, `plan`, `created_at`.
- Parent for all Composer data.

**`composer_projects`**

- One listing workflow / Composer project.
- Scoped by: `organization_id`, `created_by`.
- Key fields:
  - `client_name`, `project_name`
  - `marketplaces[]`, `category`
  - `strategy_type` (`variations` / `distinct`)
  - `active_step`, `status`
  - `highlight_attributes` JSONB (array of `{ key: string; surfaces: { title, bullets, description, backend_keywords } }` records)
  - Brand/compliance info: `brand_tone`, `what_not_to_say[]`, `supplied_info`, `faq`
  - `product_brief` JSON (target audience, use cases, differentiators, safety, certifications)
  - `last_saved_at`, `created_at`
- Relationships:
  - 1 → many: `composer_sku_variants`
  - 1 → many: `composer_sku_groups`
  - 1 → many: `composer_keyword_pools`
  - 1 → many: `composer_topics`
  - 1 → many: `composer_generated_content`
  - 1 → many: `composer_backend_keywords`
  - 1 → many: `composer_locales`
  - 1 → many: `composer_client_reviews`
  - 1 → many: `composer_comments`
  - 1 → many: `composer_exports`
  - 1 → many: `composer_jobs`
  - 1 → many: `composer_project_versions`
  - 1 → many: `composer_usage_events` (usually; nullable project_id allowed)

**`composer_project_versions`**

- Version snapshots at key milestones:
  - Keywords cleaned
  - Grouping approved
  - Themes approved
  - Sample approved
  - Bulk generated
  - Backend keywords generated
- Fields: `organization_id`, `project_id`, `step`, `snapshot`, `created_at`.

---

### 2. SKUs & Groups

**`composer_sku_groups`**

- Logical grouping of SKUs in **distinct products** mode.
- Linked to `project_id`.
- Fields: `name`, `description`, `sort_order`.

**`composer_sku_variants`**

- Individual SKUs (both variation and distinct).
- Fields:
  - `project_id`, `group_id` (nullable in variation mode)
  - `sku`, `asin`, `parent_sku`
  - `attributes` JSONB for dynamic columns
  - `notes`
- Constraint: unique per org/project: `(organization_id, project_id, sku)`.

---

### 3. Keyword Pools, Cleaning, Grouping

**`composer_keyword_pools`**

- Raw → cleaned → grouped pipeline per scope.
- Scope: `project_id` or (`project_id` + `group_id`).
- Fields:
  - `pool_type` (`body` for description/bullets, `titles`).
  - `status` (`empty` | `uploaded` | `cleaned` | `grouped`).
  - `raw_keywords` (JSONB `text[]`) — deduped ingest snapshot.
  - `raw_keywords_url` (optional S3 reference when uploads exceed inline limit).
  - `cleaned_keywords` (JSONB `text[]`).
  - `removed_keywords` (JSONB `[{ term, reason }]`).
  - `clean_settings` JSON (removeColors/sizes/brand/competitor flags).
  - `cleaned_at`, `grouped_at`.
  - `grouping_config` JSON (basis, attributeName, groupCount, phrasesPerGroup).
  - `approved_at` (grouping approval timestamp).
  - `created_at`.

**`composer_keyword_groups`**

- AI-generated grouping output.
- Fields:
  - `keyword_pool_id`
  - `group_index`, `label`
  - `phrases[]`
  - `metadata` JSON
- Manual overrides live in `composer_keyword_group_overrides` and are applied when querying final groups.

**`composer_keyword_group_overrides`**

- Captures user adjustments to keyword grouping.
- Fields:
  - `keyword_pool_id`
  - `source_group_id` (AI group being modified) nullable if new group
  - `phrase`
  - `action` (`move`, `remove`, `add`)
  - `target_group_label`, `target_group_index`
  - `created_at`

---

### 4. Themes, Samples, Bulk Content

**`composer_topics`**

- The 5 approved themes per scope (project or project+group).
- Fields:
  - `project_id`, optional `group_id`
  - `title`, `explanation`
  - `order_index` 0–4
  - `source` (`ai` / `manual`)
  - `approved_at`

**`composer_generated_content`**

- Current generated copy for titles, bullets, descriptions, and sample variants.
- Fields:
  - `project_id`, `sku_variant_id`
  - `locale` (default `en-US`)
  - `content_type` (`title`, `bullets`, `description`, `sample_title`, `sample_bullets`, `sample_description`)
  - `body`
  - `source` (`ai` / `manual`)
  - `version` (current version number; historical snapshots live in `composer_project_versions`)
  - `flags` JSON (length issues, banned terms, missing keywords, duplicates)
  - `approved_at`
- Constraint:
  - Unique current row per (org, project, sku_variant, locale, content_type).

---

### 5. Backend Keywords

**`composer_backend_keywords`**

- Backend search term string per SKU/locale.
- Fields:
  - `project_id`, `sku_variant_id`, `locale`
  - `keywords_string`, `length_chars`, `length_bytes`
  - `flags` JSON (over_limit, banned_terms, etc.)
  - `source`, `approved_at`
- Constraint:
  - Unique per (org, project, sku_variant, locale).

---

### 6. Localization

**`composer_locales`**

- Per-project locale config.
- Fields:
  - `locale_code` (e.g. `en-GB`, `de-DE`)
  - `mode` (`translate` / `fresh`)
  - `settings` (locale-specific tuning)
  - `approved_at`
- Constraint:
  - Unique per (org, project, locale_code).

Localized content rows themselves live in `composer_generated_content` and `composer_backend_keywords` with locale set accordingly.

---

### 7. Client Review & Comments

**`composer_client_reviews`**

- Shareable client review link + state.
- Fields:
  - `project_id`
  - `token` (unique)
  - `enabled` (link on/off)
  - `status` (`draft`, `shared`, `approved`, `changes_requested`)
  - `approved_at`

**`composer_comments`**

- Comment thread across internal users and clients.
- Fields:
  - `project_id`
  - `author_type` (`internal` / `client`)
  - `author_id` (optional, for internal users)
  - `author_name` (for display / clients)
  - `body`
  - Optional `sku_variant_id`, `locale`
  - `created_at`

---

### 8. Exports & Jobs

**`composer_exports`**

- Export history per project.
- Fields:
  - `project_id`
  - `format` (`flatfile`, `master_csv`, `json`, `pdf`)
  - Optional `marketplace`
  - `triggered_by` (user id)
  - `metadata` JSON (version timestamp, row count, etc.)
  - `created_at`

**`composer_jobs`**

- Async jobs for heavy LLM or exports.
- Fields:
  - `project_id`
  - `job_type` (`bulk_generate`, `locale_generate`, `export_flatfile`, etc.)
  - `status` (`pending`, `running`, `success`, `error`)
  - `payload` JSON
  - `result` JSON
  - `error_message`
  - `created_at`, `updated_at`

---

### 9. LLM Usage Tracking

**`composer_usage_events`**

- One row per **LLM call** triggered by Composer.
- Fields:
  - `organization_id`
  - `project_id` (nullable for org-level operations)
  - Optional `job_id`
  - `action` (e.g. `keyword_grouping`, `theme_suggestion`, `sample_generate`, `bulk_generate`, `backend_keywords`, `locale_generate`)
  - `model` (e.g. `gpt-5.1`, `gpt-4.1-mini-high`)
  - `tokens_in`, `tokens_out`, `tokens_total`
  - Optional `cost_usd`
  - `duration_ms`
  - `meta` JSON (locale, sku_count, pool_type, etc.)
  - `created_at`

This table is the backbone for cost analysis and optimization.

---

## Deletion & Cascade Behavior

- Every FK to `composer_organizations` and `composer_projects` uses **`ON DELETE CASCADE`** so:
  - Deleting an org deletes all its projects and child rows.
  - Deleting a project deletes all associated SKUs, keyword pools, topics, content, locales, comments, exports, jobs, usage events, etc.
- In production, we may prefer **soft delete** for orgs/projects and run controlled cleanup jobs, but the schema supports safe cascading.

---

## Indexing Rules

Key indexes (non-exhaustive):

- `composer_projects`
  - `(organization_id, created_by)`
  - `(organization_id, status)`
- `composer_sku_variants`
  - Unique `(organization_id, project_id, sku)`
  - `(organization_id, project_id, group_id)`
- `composer_generated_content`
  - Unique `(organization_id, project_id, sku_variant_id, locale, content_type)`
  - `(organization_id, project_id, locale)`
- `composer_backend_keywords`
  - Unique `(organization_id, project_id, sku_variant_id, locale)`
  - `(organization_id, project_id, locale)`
- `composer_locales`
  - Unique `(organization_id, project_id, locale_code)`
- `composer_keyword_pools`
  - `(organization_id, project_id, pool_type)`
  - `(organization_id, project_id, group_id)`
- `composer_topics`
  - `(organization_id, project_id, group_id, order_index)`
- `composer_client_reviews`
  - `(organization_id, project_id)`
- `composer_exports`
  - `(organization_id, project_id, format, created_at)`
- `composer_jobs`
  - `(organization_id, project_id, job_type, status)`
  - `(organization_id, status)`
- `composer_usage_events`
  - `(organization_id, created_at)`
  - `(organization_id, project_id, created_at)`
  - `(organization_id, action, created_at)`
  - `(organization_id, model, created_at)`

---

## Slice-Level Rules & Constraints

- All Composer tables must include `organization_id` as a first-class column.
- No table may be created under Composer without tenant scoping.
- `composer_projects` is the primary pivot for business logic, but child tables are **org-aware** for performant RLS and analytics.
- `composer_generated_content` and `composer_backend_keywords` store **current truth only**; history lives in `composer_project_versions`.
- All LLM calls **must** be logged to `composer_usage_events` via a centralized LLM wrapper.
- Supabase auth must always surface the user’s `org_id` claim. When it is missing (e.g., local development) the frontend/backend fall back to the shared Composer org `e9368435-9a8b-4b52-b610-7b3531b30412` (`DEFAULT_COMPOSER_ORG_ID`). Keep legacy data aligned with this ID or update user metadata accordingly so filters remain consistent.

---

## Acceptance Criteria

- All tables above exist in the database with correct FKs and `ON DELETE CASCADE` to orgs/projects.
- Indexes and uniqueness constraints are implemented as described.
- A project can be created, SKUs added, keywords ingested, and content generated without any schema changes.
- Deleting an org or project removes child data without orphans.
- Every LLM operation can be associated with a `composer_usage_events` row capturing model and token usage.

---

## /docs/composer Structure

```
/docs/composer/
  00_overview.md
  01_schema_tenancy.md          # (this micro-spec)
  02_types_canonical.md         # TS domain types for /lib/composer/types.ts
  03_ai_contracts.md            # Inputs/outputs for each AI call

  slice_01_shell_intake.md      # Project dashboard + wizard + Product Info + Strategy
  slice_02_keywords.md          # Upload → Clean → Group
  slice_03_themes_sample_bulk.md# Themes → Sample → Bulk
  slice_04_backend_keywords.md
  slice_05_multilingual.md
  slice_06_client_review_export.md
  slice_07_infra_observability.md

  domain_projects.md            # Optional: deep dive into project lifecycle
  domain_sku_variants.md        # Optional: deep dive into SKU modelling
  domain_localization.md        # Locale rules, validations, etc.
```

Pattern:

- `00_* / 01_* / 02_*` → global stuff (schema, types, AI contracts)
- `slice_*` → UX + API + state for each slice
- `domain_*` → deeper dives when a concept gets gnarly (SKUs, localization, etc.)
