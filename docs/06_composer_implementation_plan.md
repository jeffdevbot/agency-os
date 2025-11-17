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
2. **Wizard Frame** — persistent context (project meta, stepper, autosave indicator).
3. **Product Info** — SKU table w/ CSV import, attribute fields, marketplace selector.
4. **Content Strategy Selection** — variation vs distinct toggle, SKU group builder.
5. **Keyword Upload** — per-pool inputs, group tabs, raw preview.
6. **Keyword Cleanup** — removal diff, restore controls, approval button.
7. **Grouping Plan / Preview** — suggested grouping view, overrides, approval.
8. **Themes Selector** — AI suggestions, pick 5, per-group context.
9. **Sample Editor** — RTE with regenerate + approve.
10. **Bulk Editor** — spreadsheet view per SKU, violation badges, regenerate per row/group.
11. **Backend Keywords** — text builder with byte counter, approvals.
12. **Multilingual Output** — locale tabs, translation vs fresh toggle, approvals.
13. **Client Review** — share-link management, preview, comment thread.
14. **Export Hub** — buttons & copy utilities; surfaces last-approved version info.

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
