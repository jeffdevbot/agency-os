# Composer Slice 2 — Staged Implementation Plan

**Status:** Approved for Implementation
**Source:** Slice 2 Implementation Plan (`slice_02_implementation_plan.md`)
**Created:** 2025-11-20

## Overview

This document breaks Slice 2 (Keyword Pipeline) into 8 manageable stages to avoid token exhaustion. Each stage is independently testable and builds on previous stages.

**Total estimated effort:** 8-12 sessions

---

## Stage 1: Schema & Backend Foundation ✅ COMPLETED

**Goal:** Create all database tables, types, and core backend infrastructure for keyword pools, groups, and overrides.

**Status:** Completed 2025-11-20

**Subagents to use:**
- `supabase-consultant` (primary) — schema creation, migrations, RLS policies
- `implementer` — TypeScript type updates

**Deliverables:**
- [x] Create `composer_keyword_pools` table
  - Columns: `id`, `organization_id`, `project_id`, `group_id` (nullable), `pool_type`, `status`, `raw_keywords`, `raw_keywords_url`, `cleaned_keywords`, `removed_keywords`, `clean_settings`, `cleaned_at`, `grouped_at`, `grouping_config`, `approved_at`, `created_at`
  - Check constraints: `pool_type` in ('body', 'titles'), `status` in ('empty', 'uploaded', 'cleaned', 'grouped')
  - Foreign keys to `composer_projects` and `composer_sku_groups` with ON DELETE CASCADE
  - Indexes: `(organization_id, project_id, pool_type)`, `(organization_id, project_id, group_id)`
- [x] Create `composer_keyword_groups` table
  - Columns: `id`, `organization_id`, `keyword_pool_id`, `group_index`, `label`, `phrases`, `metadata`, `created_at`
  - Foreign key to `composer_keyword_pools` with ON DELETE CASCADE
  - Index: `(organization_id, keyword_pool_id, group_index)`
- [x] Create `composer_keyword_group_overrides` table
  - Columns: `id`, `organization_id`, `keyword_pool_id`, `source_group_id` (nullable), `phrase`, `action`, `target_group_label`, `target_group_index`, `created_at`
  - Check constraint: `action` in ('move', 'remove', 'add')
  - Foreign keys with ON DELETE CASCADE
- [x] RLS policies for all three tables (org-scoped read/write)
- [x] Update `/lib/composer/types.ts` with new types:
  - `KeywordPoolStatus`, `KeywordCleanSettings`, `GroupingConfig`, `RemovedKeywordEntry`
  - `ComposerKeywordPool`, `ComposerKeywordGroup`, `ComposerKeywordGroupOverride`
  - `KeywordGroupOverrideAction`

**Dependencies:** None (builds on Slice 1 schema)

**Testing/Verification:** ✅ All tests passed
- Run migrations in Supabase
- Verify all tables exist with correct columns and constraints
- Test RLS policies with test user session
- Verify foreign key cascades (delete project → confirm pools/groups/overrides cascade)
- TypeScript types compile without errors

**Migration files created:**
- `supabase/migrations/2025-11-20_composer_slice2_cleanup.sql`
- `supabase/migrations/2025-11-20_composer_slice2_keyword_tables.sql`

---

## Stage 2: Keyword Pool APIs (Upload & Basic CRUD) ✅ COMPLETED

**Status:** Completed 2025-11-20
**Notes:** Implemented keyword pool list/create routes (project + group scopes), single pool fetch/update routes, CSV parsing/merge/dedupe utilities, and state-reset logic on uploads. Added RLS-aware Supabase client mock enhancements and expanded coverage (+66 tests; suite now 148 passing).

**Goal:** Implement API routes for keyword pool management. Focus on upload/ingest flow (Surface 5) without cleaning logic.

**Subagents to use:**
- `api-scaffolder` (primary) — route scaffolding
- `implementer` — business logic
- `qa` — API testing

**Deliverables:**
- [x] `GET /api/composer/projects/:id/keyword-pools` route
  - Returns all pools for a project (body + titles, scoped by group_id if distinct mode)
  - Map DB rows to `ComposerKeywordPool` type
  - Include org verification + RLS
- [x] `POST /api/composer/projects/:id/keyword-pools` route
  - Body: `{ poolType, groupId?, keywords: string[] }`
  - Logic: merge with existing `raw_keywords`, dedupe case-insensitive, trim whitespace
  - Reset `status='uploaded'`, clear `cleaned_at`, `grouped_at`, `approved_at`
  - Enforce min 5 keywords, max 5000 keywords validation
- [x] `GET /api/composer/keyword-pools/:id` route
  - Return single pool by ID with org verification
- [x] `PATCH /api/composer/keyword-pools/:id` route
  - Support updating `raw_keywords`, `status`, approval flags
  - Implement state transition logic (uploading resets approvals)
- [x] Create helper utilities in `/lib/composer/keywords/utils.ts`:
  - `dedupeKeywords(keywords: string[]): string[]`
  - `mergeKeywords(existing: string[], incoming: string[]): string[]`
  - `parseKeywordsCsv(csv: string): string[]`
  - `validateKeywordCount(keywords: string[]): { valid: boolean; error?: string }`
- [x] Vitest unit tests for utilities
- [x] Vitest integration tests for all API routes

**Dependencies:** Stage 1 complete

**Testing/Verification:**
- All route + utility tests passing (66 new tests; total suite 148)
- Verified project-level and group-level pools
- Append/merge deduped case-insensitive; validation enforced for min 5 / max 5000 with warnings under 20
- State transitions confirmed (upload resets cleaned/grouped/approved flags)

---

## Stage 3: Keyword Cleanup APIs & Logic ✅ COMPLETED

**Status:** Completed 2025-11-20
**Notes:** Backend cleaning service + synchronous clean route delivered with org/RLS checks, attribute-driven color/size detection, brand/competitor removal from project data, stopword list, approval gating on PATCH, and full Vitest coverage.

**Goal:** Implement cleaning engine (Surface 6) with deterministic filtering, removed keywords tracking, approval workflow.

**Subagents to use:**
- `implementer` (primary) — cleaning logic and APIs
- `qa` — test coverage

**Deliverables:**
- [x] `POST /api/composer/keyword-pools/:id/clean` route
  - Body: `{ config: KeywordCleanSettings }`
  - Run cleaning filters, update `cleaned_keywords` and `removed_keywords`
  - Persist `clean_settings`, set `cleaned_at` timestamp
  - Status stays `uploaded` until approved
- [x] Create `/lib/composer/keywords/cleaning.ts` service:
  - `cleanKeywords(raw: string[], config: KeywordCleanSettings, project: ComposerProject): CleaningResult`
  - `CleaningResult`: `{ cleaned: string[], removed: RemovedKeywordEntry[] }`
  - Filter logic:
    - Duplicates (case-insensitive, keep first, reason: "duplicate")
    - Brand/competitor (project `client_name` + `what_not_to_say`, which includes competitor names, reason: "brand"/"competitor")
    - Stop/junk terms (small built-in list: e.g., "n/a", "tbd", reason: "stopword")
    - Colors (optional, data-driven from SKU attributes with lexicon fallback, reason: "color")
    - Sizes (optional, data-driven from SKU attributes with regex fallback, reason: "size")
- [x] Create `/lib/composer/keywords/blacklists.ts`:
  - `STOP_WORDS: string[]` (small junk list only)
  - `COLOR_LEXICON: string[]` (fallback for attribute-derived colors)
  - `SIZE_PATTERNS: RegExp[]` (fallback for attribute-derived sizes/dimensions)
- [x] `PATCH /api/composer/keyword-pools/:id` enhancements:
  - Accept `{ cleanedKeywords?, removedKeywords?, approved: boolean }`
  - Handle manual moves (restore from removed, remove from cleaned)
  - When `approved=true`, set `status='cleaned'` and `cleaned_at`
  - Validate can't approve without cleaning results (400 if `cleaned_keywords` missing/empty; also reject if status not `uploaded`)
- [x] Vitest unit tests for cleaning logic
- [x] Vitest integration tests for clean API

**Dependencies:** Stage 2 complete

**Testing/Verification:**
- Cleaning determinism: same input + config = same output
- All removal reasons accurately tracked
- Manual restore/remove operations work
- Approval workflow enforces cleaning prerequisite (400 when approving without cleaned results)
- State machine: `uploaded` → `cleaned`
- Clean endpoint is synchronous (no queue/stream); last write wins, returns persisted `{cleaned, removed, config}`

---

## Stage 4: Frontend — Keyword Upload (Surface 5) ✅ COMPLETED

**Status:** Completed 2025-11-20
**Notes:** Added keyword upload step with scope-aware tabs, CSV/paste/manual inputs, dedupe/validation (min 5, warn <20, max 5k, 5MB limit), optimistic uploads via hook, and tests for hook flows. Works for project-level and group-level pools.

**Goal:** Build Keyword Upload UI with CSV dropzone, paste textarea, manual input, raw keyword preview.

**Subagents to use:**
- `implementer` (primary) — React components and hooks
- `qa` — component testing

**Deliverables:**
- [x] Create `/lib/composer/hooks/useKeywordPools.ts` hook
  - State: `pools: ComposerKeywordPool[]`, `isLoading`, `error`
  - Methods: `refresh()`, `uploadKeywords(poolType, groupId?, keywords)`, `cleanPool(poolId, config)`, `approveClean(poolId)`
  - Optimistic updates for uploads
- [x] Create `KeywordUploadStep.tsx` component
  - Scope selector (if distinct mode, show group tabs)
  - Two pool tabs: "Description & Bullets" and "Titles"
  - Per-pool UI:
    - CSV upload dropzone (accept .csv, .txt)
    - "Download Template" link
    - Paste textarea with "Import" button
    - Manual keyword input + "Add" button
    - Raw keywords preview list (read-only, show dedupe count)
  - Validation banners:
    - Error if <5 keywords
    - Warning if <20 keywords
    - Recommendation for 50-100+ keywords
    - "Continue to Cleanup" button (disabled if <5 in either pool)
- [x] Create `KeywordPoolPanel.tsx` sub-component
  - Renders upload controls + preview for one pool
  - Props: `poolType`, `pool`, `onUpload`, `projectId`, `groupId?`
- [x] CSV parsing utility using `parseKeywordsCsv`
  - Handle UTF-8 encoding
  - Validate single column with optional "keyword" header
  - Max 5MB file size
  - Max 5k keywords
  - Friendly errors
- [x] Drag-and-drop file handling + template download link
- [x] Vitest tests for hook, CSV parsing, validation

**Dependencies:** Stages 2-3 complete

**Testing/Verification:**
- Can upload CSV files (file input), paste keywords, and manually add keywords
- Dedupe works client-side; validation errors/warnings surface
- Proceed only when pools meet minimum; handles variation and distinct scopes
- Tests cover hook flows (load, upload/merge, clean/approve, errors)

---

## Stage 5: Frontend — Keyword Cleanup (Surface 6)

**Goal:** Build Keyword Cleanup UI with dual-pane view, filter toggles, restore/remove actions, approval flow.

**Subagents to use:**
- `implementer` (primary) — React components
- `qa` — interaction testing

**Deliverables:**
- [x] Create `KeywordCleanupStep.tsx` component
  - Scope selector (if distinct mode)
  - Two pool sections (Description/Bullets + Titles) - **implemented as tabs**
  - Per-pool UI:
    - Stats summary (raw/cleaned/removed counts, breakdown by reason)
    - Filter toggles:
      - Remove Colors
      - Remove Sizes
      - Remove Brand Name
      - Remove Competitors
    - "Run Cleaning" button
    - Dual-pane view: **implemented as collapsible lists (400px scroll)**
      - Cleaned panel: keywords list with "Remove" buttons
      - Removed panel: keywords with reason badges + "Restore" buttons
    - Approval: checkbox + "Approve & Continue" button + **unapprove toggle**
- [x] Create `CleanedKeywordsList.tsx` component
  - Props: `keywords`, `onRemove`
  - **Collapsible with 400px max-height scroll** (not virtualized - sufficient for performance)
- [x] Create `RemovedKeywordsList.tsx` component
  - Props: `removed: RemovedKeywordEntry[]`, `onRestore`
  - Group by reason with collapsible sections
  - Reason badge colors (7 types)
- [x] Update `useKeywordPools` hook:
  - `cleanPool(poolId, config)` method
  - `manualRemove(poolId, keyword)` method
  - `manualRestore(poolId, keyword)` method
  - `approveClean(poolId)` method
  - **Added `unapproveClean(poolId)` method**
- [x] Loading states during cleaning
- [x] Optimistic updates for manual operations
- [ ] **MISSING:** Vitest tests for UI components (KeywordCleanupStep, CleanedKeywordsList, RemovedKeywordsList) and `unapproveClean()` function

**Dependencies:** Stages 2-4 complete

**Testing/Verification:**
- Cleaning runs when config toggles change
- Removed keywords show correct reasons
- Manual remove/restore works smoothly
- Can't approve without cleaning
- Stats update correctly
- Approval unlocks Grouping step

---

## Stage 6: Keyword Grouping APIs & AI Integration

**Goal:** Implement AI-powered keyword grouping (Surface 7 backend) with OpenAI integration, group storage, overrides, merged view.

**Subagents to use:**
- `implementer` (primary) — AI orchestration and APIs
- `api-scaffolder` — route scaffolding
- `qa` — testing

**Deliverables:**
- [ ] `POST /api/composer/keyword-pools/:id/grouping-plan` route
  - Body: `{ config: GroupingConfig }`
  - Persist `grouping_config` to pool
  - Trigger AI grouping worker
  - Reset `grouped_at` and `approved_at` if config changed
  - Return job_id or inline groups
- [ ] `GET /api/composer/keyword-pools/:id/groups` route
  - Return `{ aiGroups, overrides, merged }`
  - Merged = AI groups + overrides applied
- [ ] `POST /api/composer/keyword-pools/:id/group-overrides` route
  - Body: `{ phrase, action, targetGroupLabel?, targetGroupIndex?, sourceGroupId? }`
  - Create override record
  - Return updated merged groups
- [ ] `DELETE /api/composer/keyword-pools/:id/group-overrides` route
  - Delete all overrides (reset to AI baseline)
- [ ] Create `/lib/composer/ai/groupKeywords.ts` orchestrator
  - `groupKeywords(keywords, config, project): Promise<ComposerKeywordGroup[]>`
  - Model: `gpt-5.1-nano`
  - Input prompt based on `config.basis`:
    - `'single'`: "Group all keywords into 1 group"
    - `'per_sku'`: "Group keywords per SKU"
    - `'attribute'`: "Group by attribute: {attributeName}"
    - `'custom'`: "Create {groupCount} logical groups"
  - Output: JSON `{ label, keywords }[]`
  - Validation: ensure all keywords assigned
  - Fallback: single "General" group if AI fails
- [ ] Log all AI calls to `composer_usage_events`
  - Action: `'keyword_grouping'`
  - Include tokens, model, duration, project_id
  - Meta: `{ pool_type, pool_id, keyword_count, basis }`
- [ ] Create `/lib/composer/keywords/mergeGroups.ts` utility
  - `mergeGroupsWithOverrides(aiGroups, overrides): MergedGroup[]`
  - Apply overrides in order
- [ ] Vitest unit tests (mocked OpenAI)
- [ ] Vitest integration tests

**Dependencies:** Stages 2-3 complete, OpenAI API key configured

**Testing/Verification:**
- AI grouping produces valid groups for all basis types
- Usage events logged for every AI call
- Overrides correctly modify AI groups
- Merged view is accurate
- Can reset overrides
- State transitions: `cleaned` → `grouped`

**✅ COMPLETED (2025-11-20):**
- All deliverables implemented and tested
- 50 new tests added (235 total tests passing)
- Enhanced usage logging tests added per QA recommendation to explicitly verify all parameters (organizationId, projectId, tokens, duration, meta) on both success and error paths
- Files: [lib/composer/ai/groupKeywords.ts](../../lib/composer/ai/groupKeywords.ts), [lib/composer/ai/openai.ts](../../lib/composer/ai/openai.ts), [lib/composer/ai/usageLogger.ts](../../lib/composer/ai/usageLogger.ts), [lib/composer/keywords/mergeGroups.ts](../../lib/composer/keywords/mergeGroups.ts), [frontend-web/src/app/api/composer/keyword-pools/[poolId]/grouping-plan/route.ts](../../frontend-web/src/app/api/composer/keyword-pools/[poolId]/grouping-plan/route.ts), [frontend-web/src/app/api/composer/keyword-pools/[poolId]/groups/route.ts](../../frontend-web/src/app/api/composer/keyword-pools/[poolId]/groups/route.ts), [frontend-web/src/app/api/composer/keyword-pools/[poolId]/group-overrides/route.ts](../../frontend-web/src/app/api/composer/keyword-pools/[poolId]/group-overrides/route.ts)
- Migration: [supabase/migrations/2025-11-20_composer_usage_events.sql](../../supabase/migrations/2025-11-20_composer_usage_events.sql)
- Reviewed by: Supabase Consultant, QA Agent, Librarian

---

## Stage 7: Frontend — Grouping Plan (Surface 7)

**Goal:** Build Grouping Plan UI with config form, AI preview, manual overrides (drag-drop), approval.

**Subagents to use:**
- `implementer` (primary) — React components with complex interactions
- `qa` — interaction testing

**Deliverables:**
- [ ] Create `GroupingPlanStep.tsx` component
  - Scope selector (if distinct mode)
  - Per-pool UI (Description/Bullets and Titles):
    - Config panel:
      - Strategy dropdown: "Single Group", "Per SKU", "Per Attribute: {attr}", "Custom"
      - If "Per Attribute": attribute dropdown
      - If "Custom": group count input
      - "Target phrases per group" slider
      - Helper text showing group estimate
    - "Generate Groups" button
    - Loading state during AI
    - Preview panel:
      - Group cards (label, phrase count, phrases preview)
      - Drag-and-drop for moving phrases
      - Rename group (inline edit)
      - "Add Custom Group" button
      - "Reset to AI Baseline" button
    - Approval: checkbox + "Approve & Continue" button
- [ ] Create `GroupingConfigForm.tsx` component
  - Props: `config`, `onChange`, `attributes`, `onGenerate`
- [ ] Create `KeywordGroupCard.tsx` component
  - Props: `group`, `onDrop`, `onRename`, `onRemovePhrase`
  - Drag-drop zone (use `dnd-kit`)
  - Collapsible phrase list
  - Inline edit for label
- [ ] Create `DraggableKeyword.tsx` component
  - Draggable phrase item
- [ ] Update `useKeywordPools` hook:
  - `generateGroupingPlan(poolId, config)` method
  - `getGroups(poolId)` method
  - `addOverride(poolId, override)` method
  - `resetOverrides(poolId)` method
  - `approveGrouping(poolId)` method
- [ ] Optimistic updates for overrides
- [ ] Vitest tests for config, drag-drop, overrides, approval

**Dependencies:** Stage 6 complete

**Testing/Verification:**
- Can select all grouping strategies
- AI generation shows loading + results
- Can drag keywords between groups
- Can rename groups
- Can add custom groups
- Can reset to AI baseline
- Overrides persist
- Approval unlocks Themes (Slice 3)
- Preview reflects merged AI + manual groups

---

## Stage 8: Integration, Testing & Polish

**Goal:** End-to-end testing, bug fixes, edge cases, documentation updates.

**Subagents to use:**
- `qa` (primary) — comprehensive testing
- `red-team` — edge case discovery
- `implementer` — bug fixes

**Deliverables:**
- [ ] End-to-end Vitest tests:
  - Complete flow: Upload → Clean → Group → Approve (both pool types)
  - Variation mode (project-level)
  - Distinct mode (per-group)
  - State machine validation
  - Multi-user scenarios (org isolation)
- [ ] Edge case testing:
  - Empty uploads
  - Very large uploads (5k keywords)
  - Special characters, Unicode, emoji
  - CSV wrong format
  - All cleaning filters enabled
  - Grouping with 1 keyword, 1000+ keywords
  - AI failures (timeout, errors)
- [ ] Performance testing:
  - 500+ keyword lists don't freeze UI
  - Virtualization works
  - Optimistic updates are snappy
- [ ] Accessibility audit:
  - Keyboard navigation
  - Screen reader compatibility
  - ARIA labels
- [ ] Error handling improvements:
  - Friendly error messages
  - Retry mechanisms for AI
  - Network error recovery
- [ ] Documentation updates:
  - Update `PROJECT_STATUS.md` with Slice 2 completion
  - Inline code comments
  - API documentation
- [ ] Visual polish:
  - Loading skeletons
  - Empty states
  - Success/error toasts
  - Responsive layout
- [ ] State persistence:
  - Resume project mid-cleanup
  - Browser refresh during AI generation

**Dependencies:** Stages 1-7 complete

**Testing/Verification:**
- All 82 existing tests still pass
- 30+ new Slice 2 tests pass
- No console errors
- Manual QA checklist completed
- Edge cases handled gracefully
- Performance benchmarks met
- Documentation updated

---

## Summary & Dependencies

**Stage-by-stage dependencies:**
1. Schema & Backend Foundation → (none)
2. Keyword Pool APIs → (1)
3. Keyword Cleanup APIs → (2)
4. Frontend Upload → (2, 3)
5. Frontend Cleanup → (2, 3, 4)
6. Grouping APIs & AI → (2, 3)
7. Frontend Grouping → (6)
8. Integration & Polish → (1-7)

**Estimated sessions:**
- Stage 1: 1 session
- Stage 2: 1 session
- Stage 3: 1-2 sessions
- Stage 4: 1 session
- Stage 5: 1-2 sessions
- Stage 6: 1-2 sessions
- Stage 7: 1-2 sessions
- Stage 8: 1 session

**Total: 8-12 sessions**

---

## Next Steps

Once approved, begin with **Stage 1: Schema & Backend Foundation** using the `supabase-consultant` agent.
