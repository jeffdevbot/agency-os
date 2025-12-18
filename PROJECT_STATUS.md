# Changelog — Ecomlabs Tools

_Last updated: 2025-12-17 (EST)_

> Development history for the project. For setup instructions and project overview, see [AGENTS.md](AGENTS.md).

---

## 2025-12-17 (EST)
- **Command Center UI polish:** Redesigned Clients list into a searchable, filterable table with brand chips/counts and a collapsed archived section. Refreshed Manage Client → Brands to use an "Add New Brand" modal (marketplace pill multiselect) and a visual org-chart tree with dashed support line + optimistic assignment updates for faster UX.
- **Command Center Tokens page:** Added `/command-center/tokens` with official OpenAI daily costs vs internal `ai_token_usage` attribution (range selector, rounded charts, fast-loading sections, CSV export of full selected range).
- **Debrief UX upgrades:** Added per-meeting "Draft Email" (modal editor + copy + Gmail compose link) and meeting dismissal ("Remove" on `/debrief`, stored as `status='dismissed'`). Added meeting list pagination (10 at a time with "Show 10 more").

## 2025-12-16 (EST)
- **Command Center MVP shipped:** Implemented Ghost Profiles + merge-on-login, core schema (clients, brands, roles, assignments), admin-only UI (`/command-center`) with org-chart role slots, team roster, per-member assignment view, brand marketplaces, and safe archive/delete actions for test data. Added Debrief helper endpoints for brand+role routing.
- **Debrief Stage 1–3 shipped (manual extraction):** Set up Google Workspace domain-wide delegation + impersonation, Drive folder ingestion, and Debrief MVP routes (`/debrief`) to sync "Notes by Gemini" into Supabase, view meetings, and manually run extraction per meeting (no ClickUp yet).
- **Debrief token usage logging:** Generalized `ai_token_usage.stage` constraint to allow non-Scribe stages (migration `20251216000001_ai_token_usage_stage_check_generalize.sql`) and wired Debrief extraction to log OpenAI usage via `frontend-web/src/lib/ai/usageLogger.ts`.
- **Auth hardening:** Updated Command Center route handlers to use `supabase.auth.getUser()` (verified identity) rather than trusting `getSession()` payloads, removing noisy warnings and improving server-side correctness.

## 2025-12-12 (EST)
- **AdScope Sponsored Brands Views + Data Accuracy Fixes:** Added SB analytics to AdScope (match/targeting types and ad formats) sourced from Bulk SB tabs. Implemented stable Bulk mappings for SB fields (`ad_format`, targeting expressions), new backend `views.sponsored_brands` payload, and corresponding frontend canvas/tab. Tightened SB targeting breakdown to use target-level SB entities only (Keyword + Product Targeting), removed negative keyword types from SB view, and added a spend-alignment warning when Bulk exports are campaign-rolled-up.
- **AdScope Bidding Strategy Mapping Bug Fix:** Diagnosed incorrect bidding-strategy buckets (numeric values) to fuzzy matching falsely mapping `Bid` → `Bidding Strategy` due to substring logic. Added exclusion in `bulk_parser.py` so bid-like headers cannot match `Bidding Strategy`, restoring correct strategy names (e.g., Dynamic bids / Fixed bid) in Bidding & Placements view.
- **AdScope UI Polish:** Fixed Explorer nav alignment/classes, added SB section in Explorer, and removed the hardcoded "Target: 30%" label from ACoS overview cards for cleaner presentation.

## 2025-12-11 (EST)
- **Supabase Auth Deadlock Fix:** Fixed critical auth bug causing homepage to hang on "Checking session..." indefinitely. Root cause: `async getUser()` inside `onAuthStateChange` callback triggered Supabase internal locking deadlock. Fix: (1) Changed initial auth check from `getUser()` to `getSession()`. (2) Removed async from `onAuthStateChange` callback. (3) Added `.catch()` handler to clear corrupted sessions. Commits: `b754d01`, `d143d4d`.
- **Scribe Stage C Prompt Improvements:** Enhanced copy generation prompt in `copyGenerator.ts` to fix attribute override mode, SKU code leakage, and product name rephrasing issues.

## 2025-12-10 (EST)
- **AdScope Backend/Frontend Landing (testable):** Added FastAPI router `/adscope/audit` with memory/file caps, fuzzy bulk/STR parsing (header-row scan), date-range mismatch warning, and all 13 precomputed views; hardened optional-column handling (placements/price sensitivity/zombies) and inclusive budget cap date span. Frontend `/adscope` now has ingest UI, dark workspace with all view tabs, mock JSON contract, and server-side chat proxy (no client key leakage). Bulk tab selection prioritizes SP Campaigns per schema.

## 2025-12-09 (EST)
- **AdScope Parser & Metrics Fixes:** Resolved critical data accuracy issues. Multi-tab parsing for SP/SB/SD campaigns. Switched overview metrics source from STR to Bulk file. Added backfill logic for missing columns.
- **Token Usage Tracking Refactor:** Generalized logging to support Scribe and AdScope. Migrated `scribe_usage_logs` to `ai_token_usage`. Consolidated logging into `frontend-web/src/lib/ai/usageLogger.ts`.
- **Root Keyword Analysis Tool Shipped:** Backend `/root/process` with parsing, week bucketing, hierarchical aggregation, and formatted Excel workbook. Frontend `/root-keywords` with drag/drop upload.

## 2025-12-08 (EST)
- **N-Gram Special Character Preservation Fix:** Fixed token cleaning in `analytics.py` to preserve measurement symbols (`"`, `'`, `°`), brand symbols (`™`, `®`, `©`), and common characters (`&`, `+`, `#`). Added 23-test suite in `test_ngram_analytics.py`.

## 2025-12-04 (EST)
- **Scribe Stage C CSV Export & Dirty Regenerate:** Implemented `/api/scribe/projects/[projectId]/export-copy` with dynamic attribute columns. Dirty-state now forces full regenerate-all when stale.
- **Scribe Test Coverage Expanded:** Added API tests for export-copy, generate-copy, generated-content. Composer tests quarantined via `describe.skip`.
- **N-Gram Two-Step Negatives Flow:** Refreshed `/ngram` UI into two clear cards, added new collector for formatted NE summary (Excel).
- **N-PAT PRD & Plan Ready:** Authored `docs/03_npat_prd.md` and `docs/03_npat_plan.md`.

## 2025-12-03 (EST)
- **Scribe Stage B Topic Selection Bug Fixed:** Resolved React state closure issue in `handleToggleTopic` causing selections not to persist.
- **Scribe Stage C Attribute Preferences Specification Complete:** Documented feature allowing control of which attributes appear in title/bullets/description.

## 2025-12-02 (EST)
- **Scribe Stage B (Topics) Shipped:** Complete UI with topic generation workflow, 5-topic selection limit, dirty state detection, and Previous/Next navigation. Added `PATCH /api/scribe/projects/{projectId}/topics/{topicId}` endpoint.
- **Scribe Stage A Polish:** Fixed EditSkuPanel save button, custom attributes persistence, keyword limits. Optimized with `Promise.all()` for parallel API calls.
- **Scribe CSV Upload Bug Fixes:** Auto-detect delimiter, fixed field name mismatch, added duplicate handling.
- **Scribe Lite Foundation Components:** Built `ScribeHeader` and `ScribeProgressTracker`. Replaced approval/locking with "Dirty State" model.
- **Scribe Lite Restart:** Archived legacy Scribe frontend (`_legacy_v1`) and docs (`docs/archive/scribe_legacy`).

## 2025-11-29 (EST)
- **Scribe Stage navigation/approval guard fixes:** Normalized status handling so refreshes land on correct stage.

## 2025-11-28 (EST)
- **Scribe Stage C shipped (backend + UI):** Generate/regenerate/approve/edit routes, job runner, Stage C fields in CSV export, per-SKU editor.
- **Scribe CSV export fixes:** RFC 4180 formatting with proper quoting and UTF-8 BOM.
- **Scribe variant attribute values persistence fixed:** Replaced `upsert()` with manual check-then-update-or-insert.

## 2025-11-27
- **Scribe Stage C spec ready (docs):** PRD, implementation plan, schema, prompt/orchestration, and test plan updated.
- **Scribe Stage B tests passing:** Gate, job, CSV edge, RLS/limits telemetry tests (Vitest).
- **Scribe Stage B refinements:** Topics prompt updated to 3-bullet descriptions, token usage logging wired.
- **Scribe Stage A polished & CSV upsert:** Per-SKU blocks, CSV import upserts by `sku_code`.

## 2025-11-26
- **Scribe per-SKU migration and docs aligned:** Applied Supabase migration to drop shared/default columns, enforce `sku_id` NOT NULL.

## 2025-11-25
- **Scribe Slice 1 (Projects Shell) Complete:** Projects API with owner scoping, frontend dashboard at `/scribe`.
- **Scribe Stage A Grid In Progress:** Grid-centric layout with sticky SKU column, dynamic variant attribute columns.

## 2025-11-22
- **Composer Deprecated, Scribe Announced:** Paused Composer work. Initiated Scribe replacement.
- **Fixed Keyword Grouping Generation:** Resolved three critical issues with the "GENERATE GROUPING PLAN" button.

## 2025-11-21
- **Database Migrations for Team Central, The Operator, and ClickUp Service:** Created 3 production-ready Supabase migrations.
- **Composer Slice 2 Stage 7 (Keyword Grouping UI):** Full drag-and-drop interface, approval workflow, override tracking.

## 2025-11-20
- **Composer Slice 2 Stage 6 (Keyword Grouping APIs & AI Integration):** AI-powered keyword grouping with OpenAI integration, 4 grouping basis types, merge utility.
- **Composer Slice 2 Stage 5 (Keyword Cleanup UI):** Tab-based navigation, collapsible keyword lists, grouped removed keywords by reason.
- **Composer Slice 2 Stage 4 (Keyword Upload UI):** Scope-aware tabs, CSV/paste/manual inputs, dedupe/validation.
- **Composer Slice 2 Stage 3 (Keyword Cleanup APIs & Logic):** Deterministic cleaning service, approval gating.
- **Composer Slice 2 Stage 2 (Keyword Pool APIs):** Upload/merge endpoints, CSV parsing helpers.
- **Composer Slice 2 Stage 1 (Schema & Backend Foundation):** Created keyword pipeline tables with RLS policies.

## 2025-11-19
- **Composer Slice 2 planning:** Aligned schema/types with keyword pool state machine.
- **Composer Slice 1 polish:** Key-attribute highlight grid, keyword grouping override spec.
- **Composer Slice 1 Surface 4 (Content Strategy):** StrategyToggle, SkuGroupsBuilder, GroupCard, full SKU groups API.

## 2025-11-18
- **Frontend migration to `@supabase/ssr`:** Fixed async cookies regression, aligned Composer fallback org.

## 2025-11-17
- **Composer Slice 1 Surface 3 (Product Info):** Autosave meta forms, FAQ editor, SKU intake with CSV import.

## 2025-11-16
- **Composer Slice 1 Surface 1+2:** Dashboard list/create, wizard frame with autosave shell.

## 2025-11-15
- **Composer schema + tenancy:** Created all `composer_*` tables, RLS policies, canonical TypeScript types.

## 2025-11-14
- **Composer PRD rebuild (v1.6):** End-to-end implementation plan.

## 2025-11-13
- **N-Gram Processor migration:** FastAPI backend + refreshed Next.js page.
- **Supabase-aware middleware:** Guards `/ngram` for logged-out users.
