# AgencyClaw Execution Tracker

Last updated: 2026-02-18 (C8 merged; test pass updates recorded)

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
| C2 | Task create flow (`clickup_task_create`) | Claude | in_review | committed (`07b4b7e`) | Multi-turn create flow, list-only brand support, intent-hijack guards, and regression tests landed; pending Slack smoke + skill enable |
| C3 | Confirmation + dedupe hardening | Claude | todo | - | 10-min expiry + interaction idempotency |
| C4 | Concurrency + ClickUp reliability | Claude | todo | - | Advisory lock + retry/backoff + orphan handling |
| C5 | Team identity sync/reconciliation | Claude | todo | - | `needs_review` admin decisions |
| C6 | ClickUp space sync/classification | Claude | todo | - | `brand_scoped` vs `shared_service` |
| C7 | `meeting_parser` standalone hardening | Claude | done | merged (`9001c27`) | Parser/review modules integrated; unit tests, typecheck, and production build passing |
| C8 | `client_context_builder` budget pack | Claude | done | merged (`a26da6a`) | Deterministic 4k budget pack, strict section caps, omission metadata + tests |

## 3. Open Blockers
- [x] Confirm migration `20260217000006_clickup_space_skill_seed.sql` is applied.
- [ ] Decide first chunk start timestamp and branch/PR convention.

## 3.1 Latest Validation Notes
- C1 (Agent 1): `backend-core/tests/test_weekly_tasks.py` passing (37 tests). Added destination filter fix for list-only ClickUp mappings and trailing punctuation sanitization for client hints.
- C1 smoke test: Slack DM query returned 6 linked tasks for `Distex` with status/assignee formatting (pass).
- C1 runtime flag: `clickup_task_list_weekly` set to `implemented_in_code=true`, `enabled_default=true`.
- C7 slice (Agent 2): `frontend-web/src/lib/debrief/__tests__/meetingParser.test.ts` and `frontend-web/src/lib/debrief/__tests__/taskReview.test.ts` passing (18 tests total).
- C7 integration sanity: `frontend-web` typecheck and `next build` both pass with parser/review imports wired into debrief extract route.
- C2 (Agent 1): `backend-core/tests/test_task_create.py` + `backend-core/tests/test_weekly_tasks.py` passing (85 tests total). Includes pending-state guards for both `title` and `confirm_or_details`.
- C8 (Agent 2): `backend-core/tests/test_client_context_builder.py` passing (7 tests). Includes deterministic output, strict section caps, and deduplicated omission reasons.
- Backend full test suite still has pre-existing unrelated failures outside these chunks.

## 4. Validation Checklist (Per Chunk)
- [ ] Behavior works in Slack runtime path.
- [ ] Permission/tier checks validated.
- [ ] Idempotency behavior validated.
- [ ] Concurrency behavior validated where relevant.
- [ ] Tests added and passing.
- [ ] `skill_catalog` row updated when chunk is truly implemented.
- [ ] Tracker row updated.

## 5. Unified Coverage Matrix (PRD -> Plan -> Tracker)
| PRD Section | Implementation Plan Mapping | Tracker Status | Evidence | Remaining Gap / Next Action |
|---|---|---|---|---|
| 1. Product Intent | Global (all chunks) | in_progress | C1 and C7 completed | Continue phased delivery C2-C8 |
| 2. Current Reality (Codebase) | Global baseline | done | Existing routes/services reused; no Bolt migration | Maintain reuse-first approach |
| 3. Naming + Role Standards | Baseline migrations | mostly_done | `20260217000001` applied; CSL rename landed | Verify all UI copy/runtime labels stay consistent |
| 4. Architecture (v1) | C1-C8 foundation | in_progress | Single orchestrator-compatible path preserved | Complete C2-C8 and document runtime seams |
| 5. Slack Runtime Decision | C1-C4 | in_progress | `/api/slack/events` + `/api/slack/interactions` active | Finish confirmation/dedupe hardening in C3 |
| 6. Debrief As Slack-Native | C7 (+ later runtime wiring) | in_progress | C7 parser/review hardening done with tests/build pass | Add deeper runtime workflow checks as features expand |
| 7. Permissions Model | C2-C6 (policy-sensitive) | in_progress | Identity mapping path in use (`profiles.slack_user_id`) | Complete explicit policy/tier enforcement coverage |
| 8. Data Model | Baseline migrations | done_for_v1_scope | `000001`..`000006` applied | Add new migrations only when new chunk needs schema |
| 9. Knowledge Base Strategy | C8 + SOP paths | mostly_done | SOP/debrief paths exist; C8 merged with budgeted context builder | Add runtime integration smoke when C8 is wired into orchestration path |
| 10. Idempotency + Concurrency | C3, C4 | todo | Foundations exist (`slack_event_receipts`, `agent_runs`) | Implement C3/C4 behavior and tests |
| 11. Queue Strategy | Deferred in plan | deferred | Explicitly deferred in PRD/plan | Revisit after C1-C8 completion |
| 12. Google Meeting Notes Inputs | C7 | mostly_done | Debrief extraction flow and parser utilities validated | Add optional end-to-end runtime smoke as needed |
| 13. Skill Registry | C1-C8 | in_progress | Skills seeded via `000001`, `000005`, `000006`; C1 enabled | Enable each skill only when implemented and smoke-tested |
| 14. Failure + Compensation | C3, C4 | todo | Partial user-facing error handling present | Implement retry/backoff/orphan/idempotency guarantees |
| 15. Phased Delivery Plan | C1-C8 roadmap | in_progress | C1 done, C7 done, C2 in progress via Agent 1 | Continue sequentially with tracker updates per chunk |
| 16. Immediate Decisions Locked | Baseline + governance | mostly_done | Key architectural and migration decisions applied | Keep matrix/tracker synchronized as work lands |

## 6. Chunk-To-PRD Traceability
| Chunk | Primary PRD Coverage | Secondary PRD Coverage |
|---|---|---|
| C1 | 5, 10, 13, 15 | 7, 14 |
| C2 | 7, 13, 14, 15 | 5, 10 |
| C3 | 5, 10, 14, 15 | 7, 13 |
| C4 | 10, 14, 15 | 5, 7, 13 |
| C5 | 7, 13, 15 | 4, 10 |
| C6 | 4, 7, 13, 15 | 8, 10 |
| C7 | 6, 12, 13, 15 | 4, 14 |
| C8 | 4, 9, 13, 15 | 10, 14 |
