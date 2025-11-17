# Composer Implementation Plan

_Source PRD: `docs/04_amazon_composer_prd.md` (v1.6)_

## Pillars
1. **Project System & Autosave**
   - Debounced save + LocalStorage fallback.
   - Resume dashboard with milestones; version snapshots at approval checkpoints.
2. **SKU Intake & Strategy**
   - CSV/paste/manual entry with dynamic attributes.
   - Required strategy selection (`Variations` vs `Distinct Products`) to seed SKU groups.
3. **Keyword Pipeline**
   - Dual pools (titles vs bullets) per SKU group when distinct.
   - Cleaning approval (dedupe, blacklist, banned terms).
   - Grouping plan suggestions + overrides with approval.
4. **Themes → Sample → Bulk**
   - Theme selection (pick 5) per group.
   - AI sample generation + editing + approval.
   - Bulk per-SKU generation with diagnostics (length, keywords, banned words).
5. **Backend Keywords, Multilingual, Review & Export**
   - Backend keyword builder per SKU.
   - Locale-aware translations or fresh generation with approvals.
   - Client review portal, comments, approval tracking.
   - Export hub (Amazon flat file, master CSV, PDF, JSON, copy buttons).

## Frontend Surfaces
1. **Project Dashboard (New/Resume)** — list projects, status badges, “New Project” CTA.  
   **Purpose:** Entry to Composer; view projects and resume/create.  
   **State:** `projects[]` with `id`, `project_name`, `client_name`, `marketplaces[]`, `category`, `strategy_type`, `active_step`, `updated_at`, derived status.  
   **Layout:** Header (title + “New Project”), optional filters, project table (name, client, marketplaces chips, category, strategy badge, status badge, last updated, Resume button).  
   **Actions:** “New Project” → Product Info step (POST /composer/projects lazily). “Resume” → load wizard with selected project.  
   **APIs:** `GET /composer/projects`, `POST /composer/projects`.
2. **Wizard Frame** — persistent context (project meta, stepper, autosave indicator).  
   **Purpose:** Shell for a single project; holds header, autosave state, and embeds active screen.  
   **State:** `project` meta, `activeStep`, `steps[]` (label/id/status), `savingState` (`idle`/`saving`/`error`), `mode` (`variations`/`distinct`).  
   **Layout:** Top bar (project name, client, marketplaces, category + autosave indicator/last saved). Horizontal stepper aligning the 12 major steps (Product Info → Export). Content area renders the current screen component. Bottom nav with Previous/Next, gated by validation.  
   **Actions:** Step navigation, autosave dispatch on child changes, updates `active_step`.  
   **APIs:** `GET /composer/projects/:id`, `PATCH /composer/projects/:id` (meta + active_step).
3. **Product Info** — SKU table w/ CSV import, attribute fields, marketplace selector.  
   **Purpose:** Capture project basics, SKU list, attributes, brand rules, supplied info, FAQ.  
   **State:** `project` meta (name, client, marketplaces, category), `variants[]` (sku, asin, attrs), inferred attributes, `brandTone`, `whatNotToSay[]`, `suppliedInfo`, `faq[]`.  
   **Layout:** Basics form (name, client, marketplaces chips, category dropdown). SKU table with CSV template download, upload zone, paste-from-spreadsheet, editable rows + dynamic columns, add-row CTA. Attribute summary listing detected columns with toggles + custom attribute adder. Brand/compliance section (tone textarea, banned terms tags). Supplied info (URLs list + large textarea). FAQ repeater.  
   **Actions:** Upload/edit SKUs, define attributes, input brand notes/FAQ, proceed to Strategy (autosave).  
   **APIs:** `PATCH /composer/projects/:id` (meta + brand fields), `POST /composer/projects/:id/variants/import`, `PATCH /composer/projects/:id/variants`.
4. **Content Strategy Selection** — variation vs distinct toggle, SKU group builder.  
   **Purpose:** Force the user to declare strategy (single variation family vs distinct products) and, if distinct, define SKU groups.  
   **State:** `strategy_type`, `skuGroups[]`, `variants[]` with group assignments.  
   **Layout:** Strategy radio options with explanatory copy. Distinct-mode group builder (unassigned SKUs list + group panels with drag/drop assignment, rename/delete, Add Group). Scope summary callout showing SKU counts/groups.  
   **Actions:** Choose strategy, manage groups, assign SKUs, continue.  
   **APIs:** `PATCH /composer/projects/:id` (strategy_type), `POST/PATCH/DELETE /composer/projects/:id/groups`.
5. **Keyword Upload** — per-pool inputs, group tabs, raw preview.  
   **Purpose:** Collect raw keyword pools (description/bullets + titles) per project or per SKU group.  
   **State:** `mode`, current scope (project or `groupId`), `keywordPools` with `pool_type` + `rawKeywords[]`.  
   **Layout:** Scope selector (distinct mode) to switch groups. For each pool (Description/Bullets, Titles): CSV upload (template link), paste textarea, manual add input, raw preview list (dedupe preview). Info banner that cleaning happens next.  
   **Actions:** Upload/paste/add keywords, continue to Cleanup.  
   **APIs:** `POST /composer/projects/:id/keyword-pools`, `PATCH /composer/keyword-pools/:id`.
6. **Keyword Cleanup** — removal diff, restore controls, approval button.  
   **Purpose:** Run dedupe/ban filters, surface diffs, and require approval for each keyword pool.  
   **State:** per pool: `rawKeywords[]`, `cleanedKeywords[]`, `removedKeywords[]` w/ reason, `whatNotToSay[]`, approval flag, cleaning options (remove colors/sizes).  
   **Layout:** Two panels (Description/Bullets + Titles). Each shows stats (raw vs cleaned counts, removal breakdown), cleaned list with inline remove/edit, removable keywords drawer (with reasons + restore). Config toggles to include/exclude color/size terms; re-run cleaning when toggled. Approval checkbox + “Approve & Continue.”  
   **Actions:** Review cleaned keywords, restore/remove entries, approve pool(s).  
   **APIs:** `POST /composer/keyword-pools/:id/clean`, `PATCH /composer/keyword-pools/:id` (cleaned/removed), `PATCH /composer/projects/:id` (mark keyword_cleaned milestone).
7. **Grouping Plan / Preview** — suggested grouping view, overrides, approval.  
   **Purpose:** Configure how keywords are grouped (single/per SKU/per attribute/custom) and approve AI-generated groupings.  
   **State:** Attributes + counts, per-pool `groupingConfig` (`basis`, `attribute_name`, `group_count`, `phrases_per_group`), resulting `keywordGroups[]`.  
   **Layout:** Scope selector (if distinct). For Description/Bullets and Titles: dropdown to choose basis (single, per SKU, attribute-specific options, custom), group count input (when custom), phrases-per-group setting, helper copy showing resulting group count. Preview panel listing each group label + phrases. Buttons to re-run grouping when config changes and to approve.  
   **Actions:** Adjust grouping settings, run AI grouping, approve plan.  
   **APIs:** `POST /composer/keyword-pools/:id/grouping-plan`, `GET /composer/keyword-pools/:id/keyword-groups`, `PATCH /composer/projects/:id` (grouping approved flag).
8. **Themes Selector** — AI suggestions, pick 5, per-group context.  
   **Purpose:** Choose five guiding themes/topics per scope from AI suggestions.  
   **State:** `mode`, scope (project or group), `suggestedTopics[]`, `selectedTopics[5]` with title/explanation/order.  
   **Layout:** Scope banner. Suggested topics list with selection/edit controls. Selected panel showing exactly five entries, editable + draggable to set order. Optional helper drawers showing key phrases / FAQ / supplied info context. Buttons to regenerate suggestions and save/approve.  
   **Actions:** Select/edit five topics per scope, approve.  
   **APIs:** `POST /composer/projects/:id/themes/suggest`, `PATCH /composer/projects/:id/themes`, `PATCH /composer/projects/:id` (themes approved flag).
9. **Sample Editor** — RTE with regenerate + approve.  
   **Purpose:** Generate/edit/approve a “golden sample” that defines tone/structure before bulk runs.  
   **State:** mode/scope, representative SKU context, `sampleContent` (title, bullets, description).  
   **Layout:** Scope banner with sample SKU metadata; read-only summary of themes, tone, keywords. Editor area for title, bullet list (with counters), and description textarea/RTE. Controls to regenerate sample, reset to latest AI output, and approve to unlock bulk.  
   **Actions:** Edit sample, regenerate, approve.  
   **APIs:** `POST /composer/projects/:id/sample/generate`, `PATCH /composer/projects/:id/sample`, `PATCH /composer/projects/:id` (sample approved flag).
10. **Bulk Editor** — spreadsheet view per SKU, violation badges, regenerate per row/group.  
    **Purpose:** Review/edit generated copy per SKU, fix violations, approve bulk output.  
    **State:** `variants[]` with generated title/bullets/description + validation flags (`too_long`, `banned_term`, `duplicate`, etc.).  
    **Layout:** Scope banner with filters (all vs issues, optional marketplace). Grid listing SKU, attribute summary, field status icons, overall status, Edit/Regenerate actions. Row detail drawer/modal provides full text with counters/highlights plus inline regenerate buttons per field.  
    **Actions:** Inspect flagged SKUs, edit or re-run AI per field, optionally bulk regenerate problematic ones, approve scope once satisfied.  
    **APIs:** `POST /composer/projects/:id/bulk/generate`, `PATCH /composer/variants/:id/content`, `POST /composer/variants/:id/content/regenerate`, `PATCH /composer/projects/:id` (bulk approved).
11. **Backend Keywords** — text builder with byte counter, approvals.  
    **Purpose:** Build/edit backend keyword strings per SKU and ensure they meet length rules before approval.  
    **State:** per SKU `backendKeywordsString`, length (chars/bytes), flags (`over_limit`, `needs_review`).  
    **Layout:** Scope summary showing limit (e.g., 249 chars). Table listing SKU, attribute summary, truncated keywords preview, length counter, status, Edit/Regenerate buttons. Row editor provides full string input with live length counter plus Trim/Regenerate/Save controls.  
    **Actions:** Review and fix entries, run trimming/regeneration, approve all.  
    **APIs:** `POST /composer/projects/:id/backend-keywords/generate`, `PATCH /composer/variants/:id/backend-keywords`, `PATCH /composer/projects/:id` (backend keywords approved).
12. **Multilingual Output** — locale tabs, translation vs fresh toggle, approvals.  
    **Purpose:** Produce localized content per requested locale (translate vs fresh) and secure approvals.  
    **State:** `locales[]`, per locale/SKU content (title/bullets/description), locale mode (`translate`/`fresh`), validation flags.  
    **Layout:** Locale tabs with settings panel (choose translation mode). Within each locale, bulk-style grid listing SKUs and field statuses, filter for issues, row editor with locale-specific counters/warnings. Per-locale approval CTA.  
    **Actions:** Select locale mode, edit/regenerate localized copy, approve each locale.  
    **APIs:** `POST /composer/projects/:id/locales/:locale/generate`, `PATCH /composer/variants/:id/content?locale=xx-YY`, `PATCH /composer/projects/:id/locales/:locale` (approval flag).
13. **Client Review** — share-link management, preview, comment thread.  
    **Purpose:** Provide a read-only client portal with comments + approve/reject, and let admins manage the link.  
    **State:** Latest approved content per SKU/locale, share link config (`public_url`, enabled flag), `comments[]`, client approval status.  
    **Layout:** Internal controls to enable/disable link and copy URL. Client preview pane with header (brand, product family, marketplaces), variant selector, locale tabs, title/bullets/description (backend keywords optionally hidden). Comment thread visible to both sides. Client action buttons for Approve All / Request Changes (with required note).  
    **Actions:** Internal users toggle link, monitor comments; clients approve/reject with feedback.  
    **APIs:** `PATCH /composer/projects/:id/share-link`, `GET /composer/projects/share/:token`, `POST /composer/projects/:id/comments`, `PATCH /composer/projects/:id` (client approval status).
14. **Export Hub** — buttons & copy utilities; surfaces last-approved version info.  
    **Purpose:** Provide final outputs after approvals—flat files, master CSV, PDFs, JSON, copy helpers.  
    **State:** References to latest approved versions per scope/locale, export job status, selected format options.  
    **Layout:** Summary card showing readiness (“All steps approved”). Buttons for each export (Amazon flat file CSV, master CSV, PDF, JSON, copy title/bullets/backends). Show last-generated timestamp + download link per format. Optional re-run controls for up-to-date exports.  
    **Actions:** Trigger exports/downloads, copy text blocks.  
    **APIs:** `GET /composer/projects/:id/export/flat-file`, `GET /composer/projects/:id/export/master-csv`, `GET /composer/projects/:id/export/pdf`, `GET /composer/projects/:id/export/json`, plus copy endpoints if needed.

## Backend / API Workstreams
1. **Schema & Migrations**
   - Tables: `projects`, `project_versions`, `sku_variants`, `sku_groups`, `product_attributes`, `keyword_pools`, `cleaned_keywords`, `keyword_groups`, `topics`, `generated_content`, `backend_keywords`, `locales`, `client_reviews`.
2. **Project Autosave Service**
   - CRUD endpoints, debounced patch, version snapshot triggers, LocalStorage replay endpoint.
3. **SKU Intake Service**
   - CSV parsing, validation, attribute normalization, strategy + group persistence.
4. **Keyword Services**
   - Upload endpoints, cleaning routines, audit log, GPT-4.1-mini-high grouping suggestion worker.
5. **Theme/Sample/Bulk Generators**
   - GPT-5.1 orchestration, retry queue, approval status updates.
6. **Backend Keyword Builder**
   - Unused keyword selection, byte limit enforcement, banned-word filtering.
7. **Localization Engine**
   - Translation vs fresh generation, locale rule validators, approval tracking.
8. **Client Review + Export APIs**
   - Signed-token links, comment storage, approval toggles, export generators (CSV/PDF/JSON).
9. **Infra & Observability**
   - Secure OpenAI keys, rate limiting, `usage_events` logging, worker job monitoring.

## Tracking / Tasks
- [ ] Pillar 1 — Project system & autosave
- [ ] Pillar 2 — SKU intake & strategy
- [ ] Pillar 3 — Keyword pipeline
- [ ] Pillar 4 — Themes → Sample → Bulk
- [ ] Pillar 5 — Backend keywords, multilingual, review & export
- [ ] Frontend surfaces 1–14
- [ ] Backend workstreams 1–9
