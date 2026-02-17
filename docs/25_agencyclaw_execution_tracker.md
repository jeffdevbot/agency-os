# AgencyClaw Execution Tracker

Last updated: 2026-02-17 (night)

## 1. Baseline Status
- [x] PRD updated to v1.9 (`docs/23_agencyclaw_prd.md`)
- [x] `20260217000001_agencyclaw_skill_catalog_and_csl_role.sql` applied
- [x] `20260217000002_agencyclaw_runtime_isolation.sql` applied
- [x] `20260217000003_client_brand_context_and_kpi_targets.sql` applied
- [x] `20260217000004_agent_core_tables.sql` applied
- [x] `20260217000005_skill_catalog_phase_2_6_seed.sql` applied
- [x] `20260217000006_clickup_space_skill_seed.sql` applied

## 2. Chunk Progress
| Chunk | Name | Owner | Status | PR/Commit | Notes |
|---|---|---|---|---|---|
| C1 | Weekly task read path (`clickup_task_list_weekly`) | Claude | done | merged (`da5e86f`), follow-up fix (`8211088`) | Slack smoke test passed with linked task list output; skill enabled in `skill_catalog` |
| C2 | Task create flow (`clickup_task_create`) | Claude | todo | - | Thin-task clarify + draft path |
| C3 | Confirmation + dedupe hardening | Claude | todo | - | 10-min expiry + interaction idempotency |
| C4 | Concurrency + ClickUp reliability | Claude | todo | - | Advisory lock + retry/backoff + orphan handling |
| C5 | Team identity sync/reconciliation | Claude | todo | - | `needs_review` admin decisions |
| C6 | ClickUp space sync/classification | Claude | todo | - | `brand_scoped` vs `shared_service` |
| C7 | `meeting_parser` standalone hardening | Claude | in_review | pending | Standalone parser + task review utility integrated; unit tests passing |
| C8 | `client_context_builder` budget pack | Claude | todo | - | 4k token budget + metadata |

## 3. Open Blockers
- [x] Confirm migration `20260217000006_clickup_space_skill_seed.sql` is applied.
- [ ] Decide first chunk start timestamp and branch/PR convention.

## 3.1 Latest Validation Notes
- C1 (Agent 1): `backend-core/tests/test_weekly_tasks.py` passing (37 tests). Added destination filter fix for list-only ClickUp mappings and trailing punctuation sanitization for client hints.
- C1 smoke test: Slack DM query returned 6 linked tasks for `Distex` with status/assignee formatting (pass).
- C1 runtime flag: `clickup_task_list_weekly` set to `implemented_in_code=true`, `enabled_default=true`.
- C7 slice (Agent 2): `frontend-web/src/lib/debrief/__tests__/meetingParser.test.ts` and `frontend-web/src/lib/debrief/__tests__/taskReview.test.ts` passing (18 tests total).
- Backend full test suite still has pre-existing unrelated failures outside these chunks.

## 4. Validation Checklist (Per Chunk)
- [ ] Behavior works in Slack runtime path.
- [ ] Permission/tier checks validated.
- [ ] Idempotency behavior validated.
- [ ] Concurrency behavior validated where relevant.
- [ ] Tests added and passing.
- [ ] `skill_catalog` row updated when chunk is truly implemented.
- [ ] Tracker row updated.
