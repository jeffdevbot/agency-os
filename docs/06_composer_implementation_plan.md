# Composer Implementation Plan

_Source PRD: `docs/04_amazon_composer_prd.md` (v1.6)_
_Last updated: 2025-11-20_

## Pillars

### 1. Project System & Autosave
- Debounced save + LocalStorage fallback.
- Resume dashboard with milestones; version snapshots at approval checkpoints.

### 2. SKU Intake & Strategy
- CSV/paste/manual entry with dynamic attributes.
- Required strategy selection (`Variations` vs `Distinct Products`) to seed SKU groups.

### 3. Keyword Pipeline
- Dual pools (titles vs bullets) per SKU group when distinct.
- Cleaning approval (dedupe, blacklist, banned terms).
- Grouping plan suggestions + overrides with approval.

### 4. Themes → Sample → Bulk
- Theme selection (pick 5) per group.
- AI sample generation + editing + approval.
- Bulk per-SKU generation with diagnostics (length, keywords, banned words).

### 5. Backend Keywords, Multilingual, Review & Export
- Backend keyword builder per SKU.
- Locale-aware translations or fresh generation with approvals.
- Client review portal, comments, approval tracking.
- Export hub (Amazon flat file, master CSV, PDF, JSON, copy buttons).

## Frontend Surfaces

### 1. Project Dashboard (New/Resume)
_List projects, status badges, “New Project” CTA._

- **Purpose:** Entry to Composer; view projects and resume/create.
- **State:** `projects[]` with `id`, `project_name`, `client_name`, `marketplaces[]`, `category`, `strategy_type`, `active_step`, `updated_at`, derived status.
- **Layout:** Header (title + “New Project”), optional filters, project table (name, client, marketplaces chips, category, strategy badge, status badge, last updated, Resume button).
- **Actions:** “New Project” → Product Info step (POST /composer/projects lazily). “Resume” → load wizard with selected project.
- **APIs:** `GET /composer/projects`, `POST /composer/projects`.

### 2. Wizard Frame
_Persistent context (project meta, stepper, autosave indicator)._

- **Purpose:** Shell for a single project; holds header, autosave state, and embeds active screen.
- **State:** `project` meta, `activeStep`, `steps[]` (label/id/status), `savingState` (`idle`/`saving`/`error`), `mode` (`variations`/`distinct`).
- **Layout:** Top bar (project name, client, marketplaces, category + autosave indicator/last saved). Horizontal stepper aligning the 12 major steps (Product Info → Export). Content area renders the current screen component. Bottom nav with Previous/Next, gated by validation.
- **Actions:** Step navigation, autosave dispatch on child changes, updates `active_step`.
- **APIs:** `GET /composer/projects/:id`, `PATCH /composer/projects/:id` (meta + active_step).

### 3. Product Info
_SKU table w/ CSV import, attribute fields, marketplace selector._

- **Purpose:** Capture project basics, SKU list, attributes, brand rules, supplied info, FAQ.
- **State:** `project` meta (name, client, marketplaces, category), `variants[]` (sku, asin, attrs), inferred attributes, `brandTone`, `whatNotToSay[]`, `suppliedInfo`, `faq[]`.
- **Layout:** Basics form (name, client, marketplaces chips, category dropdown). SKU table with CSV template download, upload zone, paste-from-spreadsheet, editable rows + dynamic columns, add-row CTA. Attribute summary listing detected columns with toggles + custom attribute adder. Brand/compliance section (tone textarea, banned terms tags). Supplied info (URLs list + large textarea). FAQ repeater.
- **Actions:** Upload/edit SKUs, define attributes, input brand notes/FAQ, proceed to Strategy (autosave).
- **APIs:** `PATCH /composer/projects/:id` (meta + brand fields), `POST /composer/projects/:id/variants/import`, `PATCH /composer/projects/:id/variants`.
- **Status:** ✅ **Completed** (Nov 17, 2025) – autosave meta + FAQ + SKU intake (inline editing, CSV merge, conflict handling) live in production wizard. Ready for Surfaces 4+.

### 4. Content Strategy Selection
_Variation vs distinct toggle, SKU group builder._

- **Purpose:** Force the user to declare strategy (single variation family vs distinct products) and, if distinct, define SKU groups.
- **State:** `strategy_type`, `skuGroups[]`, `variants[]` with group assignments.
- **Layout:** Strategy radio options with explanatory copy. Distinct-mode group builder (unassigned SKUs list + group panels with drag/drop assignment, rename/delete, Add Group). Scope summary callout showing SKU counts/groups.
- **Actions:** Choose strategy, manage groups, assign SKUs, continue.
- **APIs:** `GET/POST /composer/projects/:id/groups`, `PATCH/DELETE /composer/projects/:id/groups/:groupId`, `POST /composer/projects/:id/groups/:groupId/assign`, `POST /composer/projects/:id/variants/unassign`.
- **Status:** **Completed** (Nov 19, 2025) – StrategyToggle, SkuGroupsBuilder, GroupCard, UnassignedSkuList, ContentStrategyStep components implemented; full SKU groups API with useSkuGroups hook. Slice 1 is now feature-complete.

### 5. Keyword Upload
_Per-pool inputs, group tabs, raw preview._

- **Purpose:** Collect raw keyword pools (description/bullets + titles) per project or per SKU group.
- **State:** `mode`, current scope (project or `groupId`), `keywordPools` with `pool_type` + `rawKeywords[]`.
- **Layout:** Scope selector (distinct mode) to switch groups. For each pool (Description/Bullets, Titles): CSV upload (template link), paste textarea, manual add input, raw preview list (dedupe preview). Info banner that cleaning happens next.
- **Actions:** Upload/paste/add keywords, continue to Cleanup.
- **APIs:** `POST /composer/projects/:id/keyword-pools`, `PATCH /composer/keyword-pools/:id`.
- **Status:** Backend pool CRUD/upload APIs delivered (Nov 20, 2025) with case-insensitive merge/dedupe, CSV parsing, state reset on upload, and validation (min 5, max 5000). Frontend upload UI still pending.

### 6. Keyword Cleanup
_Removal diff, restore controls, approval button._

- **Purpose:** Run dedupe/ban filters, surface diffs, and require approval for each keyword pool.
- **State:** per pool: `rawKeywords[]`, `cleanedKeywords[]`, `removedKeywords[]` w/ reason, `whatNotToSay[]`, approval flag, cleaning options (remove colors/sizes).
- **Layout:** Two panels (Description/Bullets + Titles). Each shows stats (raw vs cleaned counts, removal breakdown), cleaned list with inline remove/edit, removable keywords drawer (with reasons + restore). Config toggles to include/exclude color/size terms; re-run cleaning when toggled. Approval checkbox + “Approve & Continue.”
- **Actions:** Review cleaned keywords, restore/remove entries, approve pool(s).
- **APIs:** `POST /composer/keyword-pools/:id/clean`, `PATCH /composer/keyword-pools/:id` (cleaned/removed), `PATCH /composer/projects/:id` (mark keyword_cleaned milestone).

### 7. Grouping Plan / Preview
_Suggested grouping view, overrides, approval._

- **Purpose:** Configure how keywords are grouped (single/per SKU/per attribute/custom) and approve AI-generated groupings.
- **State:** Attributes + counts, per-pool `groupingConfig` (`basis`, `attribute_name`, `group_count`, `phrases_per_group`), resulting `keywordGroups[]`.
- **Layout:** Scope selector (if distinct). For Description/Bullets and Titles: dropdown to choose basis (single, per SKU, attribute-specific options, custom), group count input (when custom), phrases-per-group setting, helper copy showing resulting group count. Preview panel listing each group label + phrases. Buttons to re-run grouping when config changes and to approve.
- **Actions:** Adjust grouping settings, run AI grouping, approve plan.
- **APIs:** `POST /composer/keyword-pools/:id/grouping-plan`, `GET /composer/keyword-pools/:id/keyword-groups`, `PATCH /composer/projects/:id` (grouping approved flag).
- **Manual Overrides:** After preview, users can drag phrases into different groups, remove them, or add custom groups. Overrides are saved via `POST /composer/keyword-pools/:id/group-overrides`, can be reset, and the preview reflects the merged AI + manual view before approval.

### 8. Themes Selector
_AI suggestions, pick 5, per-group context._

- **Purpose:** Choose five guiding themes/topics per scope from AI suggestions.
- **State:** `mode`, scope (project or group), `suggestedTopics[]`, `selectedTopics[5]` with title/explanation/order.
- **Layout:** Scope banner. Suggested topics list with selection/edit controls. Selected panel showing exactly five entries, editable + draggable to set order. Optional helper drawers showing key phrases / FAQ / supplied info context. Buttons to regenerate suggestions and save/approve.
- **Actions:** Select/edit five topics per scope, approve.
- **APIs:** `POST /composer/projects/:id/themes/suggest`, `PATCH /composer/projects/:id/themes`, `PATCH /composer/projects/:id` (themes approved flag).

### 9. Sample Editor
_RTE with regenerate + approve._

- **Purpose:** Generate/edit/approve a “golden sample” that defines tone/structure before bulk runs.
- **State:** mode/scope, representative SKU context, `sampleContent` (title, bullets, description).
- **Layout:** Scope banner with sample SKU metadata; read-only summary of themes, tone, keywords. Editor area for title, bullet list (with counters), and description textarea/RTE. Controls to regenerate sample, reset to latest AI output, and approve to unlock bulk.
- **Actions:** Edit sample, regenerate, approve.
- **APIs:** `POST /composer/projects/:id/sample/generate`, `PATCH /composer/projects/:id/sample`, `PATCH /composer/projects/:id` (sample approved flag).

### 10. Bulk Editor
_Spreadsheet view per SKU, violation badges, regenerate per row/group._

- **Purpose:** Review/edit generated copy per SKU, fix violations, approve bulk output.
- **State:** `variants[]` with generated title/bullets/description + validation flags (`too_long`, `banned_term`, `duplicate`, etc.).
- **Layout:** Scope banner with filters (all vs issues, optional marketplace). Grid listing SKU, attribute summary, field status icons, overall status, Edit/Regenerate actions. Row detail drawer/modal provides full text with counters/highlights plus inline regenerate buttons per field.
- **Actions:** Inspect flagged SKUs, edit or re-run AI per field, optionally bulk regenerate problematic ones, approve scope once satisfied.
- **APIs:** `POST /composer/projects/:id/bulk/generate`, `PATCH /composer/variants/:id/content`, `POST /composer/variants/:id/content/regenerate`, `PATCH /composer/projects/:id` (bulk approved).

### 11. Backend Keywords
_Text builder with byte counter, approvals._

- **Purpose:** Build/edit backend keyword strings per SKU and ensure they meet length rules before approval.
- **State:** per SKU `backendKeywordsString`, length (chars/bytes), flags (`over_limit`, `needs_review`).
- **Layout:** Scope summary showing limit (e.g., 249 chars). Table listing SKU, attribute summary, truncated keywords preview, length counter, status, Edit/Regenerate buttons. Row editor provides full string input with live length counter plus Trim/Regenerate/Save controls.
- **Actions:** Review and fix entries, run trimming/regeneration, approve all.
- **APIs:** `POST /composer/projects/:id/backend-keywords/generate`, `PATCH /composer/variants/:id/backend-keywords`, `PATCH /composer/projects/:id` (backend keywords approved).

### 12. Multilingual Output
_Locale tabs, translation vs fresh toggle, approvals._

- **Purpose:** Produce localized content per requested locale (translate vs fresh) and secure approvals.
- **State:** `locales[]`, per locale/SKU content (title/bullets/description), locale mode (`translate`/`fresh`), validation flags.
- **Layout:** Locale tabs with settings panel (choose translation mode). Within each locale, bulk-style grid listing SKUs and field statuses, filter for issues, row editor with locale-specific counters/warnings. Per-locale approval CTA.
- **Actions:** Select locale mode, edit/regenerate localized copy, approve each locale.
- **APIs:** `POST /composer/projects/:id/locales/:locale/generate`, `PATCH /composer/variants/:id/content?locale=xx-YY`, `PATCH /composer/projects/:id/locales/:locale` (approval flag).

### 13. Client Review
_Share-link management, preview, comment thread._

- **Purpose:** Provide a read-only client portal with comments + approve/reject, and let admins manage the link.
- **State:** Latest approved content per SKU/locale, share link config (`public_url`, enabled flag), `comments[]`, client approval status.
- **Layout:** Internal controls to enable/disable link and copy URL. Client preview pane with header (brand, product family, marketplaces), variant selector, locale tabs, title/bullets/description (backend keywords optionally hidden). Comment thread visible to both sides. Client action buttons for Approve All / Request Changes (with required note).
- **Actions:** Internal users toggle link, monitor comments; clients approve/reject with feedback.
- **APIs:** `PATCH /composer/projects/:id/share-link`, `GET /composer/projects/share/:token`, `POST /composer/projects/:id/comments`, `PATCH /composer/projects/:id` (client approval status).

### 14. Export Hub
_Buttons & copy utilities; surfaces last-approved version info._

- **Purpose:** Export all approved content with clear versioning context.
- **State:** Project approval status, latest version timestamp, export options (flat file per marketplace, master CSV, JSON), last export metadata.
- **Layout:** Summary section (“Exporting Project X”, approval status, version timestamp). Export cards for each format: Amazon flat file (per marketplace buttons), Master CSV, JSON, optional copy-to-clipboard utilities. Optional export history list for future iteration.
- **Actions:** Trigger downloads while referencing latest approved version.
- **APIs:** `GET /composer/projects/:id/export/flatfile?marketplace=XX`, `GET /composer/projects/:id/export/master-csv`, `GET /composer/projects/:id/export/json`, optional `POST /composer/projects/:id/export/log`.

## Backend / API Workstreams
### Phasing
- **Phase 1 – Foundations:** Workstreams 1–3 (Schema, Autosave, SKU Intake).
- **Phase 2 – Keywords & Core Content:** Workstreams 4–6 (Keywords, Theme/Sample/Bulk, Backend Keywords).
- **Phase 3 – Localization & Client-Facing:** Workstreams 7–8 (Localization, Client Review + Export).
- **Phase 4 – Infra & Hardening:** Workstream 9 (Infra/Observability + polish).

Within each phase, tickets below can run in parallel once dependencies are met.

### 1. Schema & Migrations
Goal: Supabase/Postgres ready with Composer entities.
1.1 **Design ERD** — capture entities/relations (`projects`, `sku_variants`, `sku_groups`, `keyword_pools`, `keyword_groups`, `topics`, `generated_content`, `backend_keywords`, `locales`, `client_reviews`, `project_versions`) and document FKs.
1.2 **Projects + Versions tables** — create `projects` (id, user_id, client_name, project_name, marketplaces[], category, strategy_type, active_step, status, timestamps) and `project_versions` (project_id, step, snapshot JSON, created_at).
1.3 **SKU / grouping tables** — `sku_variants` (project_id, group_id nullable, sku, asin, parent_sku, attributes JSONB) + `sku_groups` (project_id, name, description).
1.4 **Keyword tables** — `keyword_pools` (project_id, group_id nullable, pool_type, raw_keywords JSONB, cleaned_keywords JSONB, metadata) + `keyword_groups` (keyword_pool_id, group_index, label, phrases JSONB).
1.5 **Topics & generated content** — `topics` (project_id, group_id nullable, title, explanation, order_index) + `generated_content` (project_id, sku_variant_id, locale, content_type, body, source, version, timestamps).
1.6 **Backend keyword & locale tables** — `backend_keywords` (project_id, sku_variant_id, locale, keywords_string, length, flags) + `locales` (project_id, locale_code, mode, approved_at, settings).
1.7 **Client review tables** — `client_reviews` (project_id, token, enabled, status, approved_at, created_at) + `comments` (project_id, author_type, body, created_at).
1.8 **Indexes & constraints** — add FKs, indexes on project_id/sku_variant_id/locale_code, enums/NOT NULLs to enforce integrity.
Dependencies: none.

### 2. Project Autosave Service
Goal: CRUD + autosave + version snapshots.
2.1 **Project CRUD endpoints** — `GET /composer/projects`, `GET /composer/projects/:id`, `POST /composer/projects`, `PATCH /composer/projects/:id` (meta, active_step, status).
2.2 **Autosave pattern** — support frequent PATCHes of partial payloads (brand tone, banned terms, etc.) with debounced writes from frontend.
2.3 **Version snapshots** — endpoint/helper to snapshot project state (`POST /composer/projects/:id/versions`) after milestone approvals into `project_versions`.
2.4 **LocalStorage replay (optional)** — `POST /composer/projects/:id/recover-from-local` to accept client backups and merge.
Dependencies: Schema 1.x.

### 3. SKU Intake Service
Goal: Intake/normalize SKUs and persist strategy/groups.
3.1 **CSV parsing & validation** — `POST /composer/projects/:id/variants/import` to accept CSV/TSV, validate required columns, map rest to attributes.
3.2 **Attribute normalization** — canonicalize known attributes (color, size, etc.) while supporting arbitrary custom keys (store per variant JSONB).
3.3 **Manual SKU CRUD** — `PATCH /composer/projects/:id/variants` for inline edits, `POST` to add, `DELETE /composer/variants/:id` to remove.
3.4 **Strategy + groups** — `PATCH /composer/projects/:id` for `strategy_type`, plus `POST/PATCH/DELETE /composer/projects/:id/groups` to create/rename/assign SKUs.
3.5 **Derived metrics helpers** — service to calculate counts (SKUs, groups, attribute distincts) for UI hints.
Dependencies: Schema 1.x, Project CRUD 2.1.

### 4. Keyword Services
Goal: Ingest, clean, group keywords per pool/scope.
4.1 **Keyword pool ingest** — `POST /composer/projects/:id/keyword-pools` (pool_type, scope, raw keywords via CSV/text) with `PATCH /composer/keyword-pools/:id` for updates.
4.2 **Keyword cleaning routine** — dedupe, remove banned/brand/competitor terms, optional color/size stripping via `POST /composer/keyword-pools/:id/clean` storing cleaned + removed metadata.
4.3 **Cleaning audit diff** — persist removed keywords + reason; `GET /composer/keyword-pools/:id` returns raw vs cleaned vs removed.
4.4 **Grouping plan config** — `POST /composer/keyword-pools/:id/grouping-plan` to store basis/attribute/group_count/phrases_per_group in metadata.
4.5 **Keyword grouping AI worker** — GPT-4.1-mini-high maps cleaned keywords to groups; saves into `keyword_groups` when triggered from 4.4.
4.6 **Manual overrides storage** — `composer_keyword_group_overrides` captures user adjustments (move/add/remove phrases, custom labels) so we can merge AI output + overrides.
4.7 **Groups query endpoint** — `GET /composer/keyword-pools/:id/groups` returns base groups + overrides + diff metadata for the UI.
Dependencies: Schema 1.x, SKU attributes 3.x, Project CRUD 2.x.

### 5. Theme / Sample / Bulk Generators
Goal: Orchestrate AI for themes, sample copy, and bulk content.
5.1 **Theme suggestion orchestrator** — `POST /composer/projects/:id/themes/suggest` (scope-aware) aggregates cleaned keywords, FAQ, supplied info, category, tone; `PATCH /composer/projects/:id/themes` saves final five.
5.2 **Sample content generator** — `POST /composer/projects/:id/sample/generate` (scope + topics + representative SKU) calling GPT-5.1, storing `generated_content` sample rows.
5.3 **Sample edit/approval** — `PATCH /composer/projects/:id/sample` to accept manual edits (mark `source="manual"`) and flag sample approved.
5.4 **Bulk content generator** — `POST /composer/projects/:id/bulk/generate` iterating SKUs with topics, keyword groups, attributes, sample hints; writes per-SKU `generated_content`.
5.5 **Content validation & flags** — post-process length limits, banned terms, duplicates; add metadata flags.
5.6 **Bulk edit/regenerate endpoints** — `PATCH /composer/variants/:id/content` for manual edits; `POST /composer/variants/:id/content/regenerate` for targeted reruns.
5.7 **Bulk approval state** — `PATCH /composer/projects/:id` to mark bulk approved (and optional per-SKU approval flags).
Dependencies: Workstreams 1–4, OpenAI infra (9.x).

### 6. Backend Keyword Builder
Goal: Generate backend search-term strings per SKU using unused keywords.
6.1 **Backend keyword generation** — `POST /composer/projects/:id/backend-keywords/generate` gathers unused keywords per SKU, filters banned terms, calls LLM to compress into limit, writes `backend_keywords`.
6.2 **Length enforcement helper** — utilities to compute char/byte limits per locale and trim/compress (LLM or deterministic) when over threshold.
6.3 **Edit/regenerate endpoints** — `PATCH /composer/variants/:id/backend-keywords` for manual edits and `POST /composer/variants/:id/backend-keywords/regenerate` for targeted reruns.
6.4 **Approval state** — `PATCH /composer/projects/:id` toggles backend keywords approval per scope.
Dependencies: Workstreams 4–5 (keyword pools + visible copy), Amazon limit config.

### 7. Localization Engine
Goal: Translate or freshly generate localized listings with validations + approvals.
7.1 **Locales config API** — `PATCH /composer/projects/:id/locales` to set desired locales + mode (translate/fresh) stored in `locales`.
7.2 **Translation generator** — `POST /composer/projects/:id/locales/:locale/generate?mode=translate` uses approved English content and locale instructions for high-quality translations.
7.3 **Fresh localized generator** — same endpoint with `mode=fresh` to request native copy (future localized keyword inputs optional).
7.4 **Locale-specific validation** — enforce byte/punctuation rules; store flags in `generated_content.metadata.locale_flags`.
7.5 **Localized edit/regenerate** — `PATCH /composer/variants/:id/content?locale=xx-YY` and `POST /composer/variants/:id/content/regenerate?locale=xx-YY`.
7.6 **Locale approval** — `PATCH /composer/projects/:id/locales/:locale` to mark approved.
Dependencies: Workstreams 5–6 (needs base English copy, backend keywords optional).

### 8. Client Review + Export APIs
Goal: Shareable client link + export of approved content.
8.1 **Share link config** — `POST /composer/projects/:id/share-link` creates token (client_reviews row); `PATCH /composer/projects/:id/share-link` enables/disables.
8.2 **Client view endpoint** — `GET /composer/projects/share/:token` returns read-only content for last approved version (per SKU/locale).
8.3 **Comments API** — `GET/POST /composer/projects/:id/comments` storing author type, text, optional SKU reference; enforce auth/token rules.
8.4 **Client approval status** — `PATCH /composer/projects/:id/client-status` with `approved` or `changes_requested` plus optional comment.
8.5 **Export generators** — `GET /composer/projects/:id/export/flatfile?marketplace=US`, `.../master-csv`, `.../json` building Amazon-ready files.
8.6 **Export log (optional)** — `POST /composer/projects/:id/export/log` capturing who exported + when.
Dependencies: Workstreams 1–7 (approved content ready).

### 9. Infra & Observability
Goal: Secure, monitor, and control costs.
9.1 **OpenAI key management** — centralized LLM wrapper with env-stored keys, model selection, retries, timeouts.
9.2 **Rate limiting & queues** — enforce per-user/project quotas on heavy endpoints; queue long-running jobs if needed.
9.3 **Usage logging** — extend `usage_events` to capture project_id, action, tokens, latency for every LLM call.
9.4 **Job monitoring** — job table/queue for async tasks with status (`pending/running/success/error`) + `GET /composer/jobs/:id`.
9.5 **Error handling & alerts** — centralized logger + alerting (Sentry etc.) on repeated failures.

## Tracking / Tasks
- [x] Pillar 1 — Project system & autosave (Slice 1 complete)
- [x] Pillar 2 — SKU intake & strategy (Slice 1 complete)
- [ ] Pillar 3 — Keyword pipeline
- [ ] Pillar 4 — Themes → Sample → Bulk
- [ ] Pillar 5 — Backend keywords, multilingual, review & export
- [x] Frontend surfaces 1–4 (Slice 1 complete)
- [ ] Frontend surfaces 5–14
- [x] Backend workstreams 1–3 (Slice 1 complete)
- [ ] Backend workstreams 4–9

## Delivery Slices
### 🧩 Slice 1 — Project Shell & Intake (MVP Skeleton) — **COMPLETED (Nov 19, 2025)**
- **Goal:** "I can create a Composer project, enter product info, and come back later to resume it."
- **Screens:** Project Dashboard, Wizard Frame, Product Info, Content Strategy Selection.
- **Working functionality:** create/list/resume projects; autosave for meta (name, client, marketplaces, category), SKU table, attributes, brand tone/what-not-to-say, supplied info, FAQ; persist strategy selection; create/manage groups for distinct strategy.
- **Implementation:** All four surfaces delivered. See `docs/composer/slice_01_implementation_plan.md` for detailed API routes, components, and hooks.

### 🧩 Slice 2 — Keyword Pipeline (Upload → Clean → Group)
- **Goal:** “Given my SKUs and strategy, I can upload keywords, clean them, and group them in a controllable, auditable way.”
- **Screens:** Keyword Upload, Keyword Cleanup, Grouping Plan / Preview.
- **Working functionality:** per-scope keyword pools (variation vs distinct), CSV/paste/manual ingest, cleaning (dedupe, banned/brand/competitor, optional color/size) with review + restore, grouping configuration (single/per SKU/per attribute/custom) + AI grouping + approval.
- **Backend dependencies:** Slice 1 foundations plus Workstream 4 (keyword pool ingest, cleaning metadata, grouping config + GPT worker, groups query). Delivers approved keyword groups ready for downstream content generation.

### 🧩 Slice 3 — Themes → Sample → Bulk (Core Content Engine)
- **Goal:** “From my keywords and product info, I can define themes, approve a sample, and generate/edit bulk content for all SKUs.”
- **Screens:** Themes Selector, Sample Editor, Bulk Editor.
- **Working functionality:** AI-suggested themes per scope with approval; sample generation/edit/regenerate/approve; bulk per-SKU generation with flags (length, banned, duplicate) plus edit/regenerate flows ending in bulk approval.
- **Backend dependencies:** Slices 1–2 plus Workstream 5 (theme/sampling/bulk orchestrators, validation flags, edit/regenerate endpoints, approval flags). Unlocks an internally usable English content engine.

### 🧩 Slice 4 — Backend Keywords
- **Goal:** “For each SKU, I can generate backend search terms from leftover keywords and stay within limits.”
- **Screens:** Backend Keywords.
- **Working functionality:** Track used keywords, propose backend strings with byte/char counters, allow trim/regenerate/edit, record approvals per scope.
- **Backend dependencies:** Slices 1–3 plus Workstream 6 (backend keyword generator, length enforcement helpers, edit/regenerate endpoints, approval flags). After this slice, English listings (visible + backend) are export-ready.

### 🧩 Slice 5 — Multilingual Output
- **Goal:** “Extend approved content into multiple locales via translation or fresh generation and approve each locale.”
- **Screens:** Multilingual Output.
- **Working functionality:** Configure locales + modes, generate per-locale titles/bullets/descriptions, validate locale rules, edit/regenerate, approve per locale.
- **Backend dependencies:** Slices 1–4 plus Workstream 7 (locales config, translation/fresh generators, locale validations, edit/regenerate endpoints, approval flags). Enables multi-country delivery from one project.

### 🧩 Slice 6 — Client Review & Export
- **Goal:** “Share a client-facing link, gather feedback/approval, and export everything cleanly.”
- **Screens:** Client Review, Export Hub.
- **Working functionality:** Client link toggle + tokenized URL, read-only content view per SKU/locale, comment thread, approve/request changes UX; export hub showing latest approved version with downloads (flat file per marketplace, master CSV, JSON, optional history).
- **Backend dependencies:** Slices 1–5 plus Workstream 8 (share links, client view endpoint, comments API, approval toggle, export generators). Completes the external-facing workflow.

### 🧩 Slice 7 — Infra & Observability (Cross-cutting)
- **Goal:** “Keep the system stable, cost-aware, and debuggable as load grows.”
- **Screens:** None (applies platform-wide).
- **Working functionality:** Centralized LLM wrapper + key management, rate limiting/queues for heavy tasks, `usage_events` logging, job monitoring, error logging/alerts.
- **Backend dependencies:** Workstream 9. Start minimal observability alongside Slice 2/3 and harden through later slices.

## Technical Spikes
### Spike 1 — CSV Import & Dynamic Attribute Detection
- **Goal/Questions:** Validate UX for CSV/paste flows, attribute detection/mapping, storing unknown columns safely.
- **POC:** Product Info sandbox page that accepts CSV upload + paste, displays parsed rows, infers canonical attributes (color/size/age_range) with rename/toggle controls.
- **Deliverables:** `parseCsvToVariants` + `inferAttributes` utilities, notes on edge cases/UX, informs Slice 1 (Product Info + Strategy).

### Spike 2 — AI Orchestration Pattern (Grouping + Sample)
- **Goal/Questions:** Establish reusable LLM orchestration pipeline (prompt building, schema validation, logging) for grouping/themes/sample flows.
- **POC:** “Composer AI Lab” server module using a mock project to run keyword grouping, theme suggestions, sample generation through a shared `callLLM` wrapper.
- **Deliverables:** `aiOrchestrator.ts` with wrapper + `groupKeywords/suggestThemes/generateSample`, “AI Contracts” doc for inputs/outputs/models. Supports Slices 2–3.

### Spike 3 — Locale & Amazon Validation Rules
- **Goal/Questions:** Centralize per-locale content rules (length, banned terms, quirks) for reuse.
- **POC:** `validateListingField({ locale, contentType, text })` library + unit tests covering over-length, banned words, clean cases; include char vs byte handling.
- **Deliverables:** Validation module + tests powering flags in Bulk Editor, Backend Keywords, Multilingual Output.

### Spike 4 — CSV Export & Flat File Mapping
- **Goal/Questions:** Map internal model to Amazon flat files per marketplace, prove exports are ingestible.
- **POC:** `buildFlatFileCsv(project, marketplace)` producing basic Amazon-like CSV; provide fixture sample.
- **Deliverables:** `exportFlatFile.ts`, sample CSV, informs Slice 6 Export Hub.

### Spike 5 — Client Review Portal Link + Auth Flow
- **Goal/Questions:** Design secure share links with token-based read-only access and basic approvals.
- **POC:** Token-based preview route backed by minimal `client_reviews` data, enable/disable toggle, approve button.
- **Deliverables:** Token helpers, preview page, notes on additional guardrails; underpins Slice 6 Client Review.

**Suggested order:** Spike 1 → 2 → 3 → 4 → 5 to unlock slices sequentially and reduce rework.
