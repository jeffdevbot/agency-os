# Scribe Test Plan (Stages A–C)

**Status (2025-11-28, EST):** Stage A/B/C API/UI tests implemented and passing (Vitest) including Stage C gates/limits/jobs/export and generated-content GET/PATCH. Composer suites remain quarantined (deprecated). Attribute prefs overrides UI is minimal and will need additional UX polish coverage later. Unapprove endpoints covered at API level; UI locks editing when approved; export CTA added to Stage C UI.

Purpose: Minimal but comprehensive coverage for Scribe as Stage B ships. Focus on API correctness, RLS, limits, and critical UI flows.

---

## Scope
- Stage A: Projects/SKUs/variant attrs, keywords, questions, words_to_avoid, copy-from SKU, CSV import/export, status transitions, archive read-only.
- Stage B: Topics generation job lifecycle, per-SKU regenerate, selection/reorder (8 stored/5 approved), approval guard, Stage C dependency.
- Stage C: Copy generation job lifecycle, per-section regenerate, approval guard, limits (title length, bullets=5, backend keyword byte cap), export correctness.
- Cross-cutting: RLS isolation, validation limits, standard error envelope, telemetry logging for token usage.

---

## Test Types & Focus

### API Integration
- Stage A CRUD: projects, SKUs, variant attrs/values, keywords, questions, words_to_avoid; copy-from SKU.
- Stage A CSV: import/export round-trip small fixture; enforce max 10 keywords/SKU.
- Status transitions: draft ↔ stage_a_approved → stage_b_approved → stage_c_approved → approved; archive/restore; archived blocks writes.
- Stage B: generate-topics (all vs subset SKUs), per-SKU regenerate, list topics, patch (title/description/topic_index/approved), approve-topics guard (requires 5 approved/sku), job status flow; unapprove-topics transitions back to `stage_a_approved`.
- Stage C: generate-copy (all vs subset), full regenerate (section-scoped not supported in v1), approve-copy guard; unapprove-copy transitions back to `stage_b_approved`; enforce title length, bullets=5, backend keyword byte cap; attribute prefs smoke (auto/overrides toggle).
- Limits/guards: 50 SKUs/project; 10 keywords/SKU; 8 topics stored max; max 5 approved enforced server-side; Stage C endpoints reject if Stage B not approved (test mixed approval counts per SKU, e.g., 0/4 topics).
- Error envelope: validation_error/409/403 consistent with spec.

### RLS / Multitenancy
- Two-user isolation: user B cannot list/read/write user A’s projects/SKUs/keywords/questions/topics; job status gated by owner.
- Archived write-block: ensure writes to child tables fail when project is archived.

### UI E2E Smoke (Cypress/Playwright)
- Stage A grid: add/edit/delete SKU; add/edit/delete keywords/questions; variant value edit; copy-from SKU; CSV export/import of small fixture; archive read-only.
- Stage B surface: generate topics, verify up to 8 rows; select/deselect with selected count; reorder persists; regenerate clears/refreshes topics; approve blocked until 5 approved per SKU; stepper/tab switches to Stage B and back.
- Stage C surface: empty state with Generate All/Sample; per-SKU editor (title/bullets/description/backend keywords), per-section regenerate; save + version bump; mini preview updates on save; approval gate blocks until content exists for all SKUs; attribute usage panel passes prefs (smoke-level).

### Jobs / Async
- Job lifecycle: queued→running→succeeded/failed for topics; per-SKU failures captured in job payload; approval blocked if any SKU missing 5 approved topics.
- Failure paths: OpenAI/network errors/timeouts bubble to job = failed; stale jobs don’t hang forever; partial failures recorded and surfaced; retries don’t create duplicates.
- Regenerate: deletes previous topics, inserts fresh set, clears approvals.
- Stage C: queued→running→succeeded/failed; per-SKU errors recorded; regenerate bumps version and overwrites sections; failed job blocks approval.

### CSV (Stage A; Stage B partial; Stage C export)
- Export includes approved topics column (pipe-separated, ordered, max 5) alongside Stage A fields; import remains Stage A only.
- Edge cases: enforce 50 SKU limit on import (e.g., 46 existing + 10 incoming → reject); duplicate SKUs in CSV; SKUs with >10 keywords in import (reject/trim per spec).
- Stage C: export includes title, bullet_1..5, description, backend_keywords per SKU; no Stage C import in v1.

### Telemetry
- Token usage: one `scribe_usage_logs` row per topics generation call with tool/user/project/job linkage; totals populated.
- Stage C: one `scribe_usage_logs` row per copy generation call with tool/user/project/job/sku; totals/model/prompt_version populated.

### RLS / Security
- RLS on jobs table: user cannot list/read/update another user’s `scribe_generation_jobs`.
- Topics approval integrity: approved topics can’t be un-approved after Stage C starts (if enforced), `approved_at` immutable once set; ensure state transitions can’t bypass Stage B/C guards.
- RLS on generated_content: user cannot read/write other users’ content; archived write-block on jobs/generated_content.

---

## Fixtures / Data
- Two users (owner vs other) for RLS checks.
- Project with 2–3 SKUs; one SKU with no questions (fallback coverage).
- CSV fixture for Stage A round-trip (keywords/questions/words_to_avoid).

---

## Acceptance Checklist (per release)
- API tests pass for Stage A/B core flows and limits.
- RLS isolation verified (two-user fixture) and archived write-block enforced.
- E2E smoke passes for Stage A grid + Stage B selection/reorder/approve gate.
- Job lifecycle verified; regenerate clears/replaces; approval guard blocks until 5 approved/sku.
- Telemetry rows written for topics job; approved topics appear in CSV export (max 5, ordered).
