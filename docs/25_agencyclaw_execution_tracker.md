# AgencyClaw Execution Tracker

Last updated: 2026-02-19 (C10A completed and validated)

## 1. Baseline Status
- [x] PRD updated to v1.14 (`docs/23_agencyclaw_prd.md`)
- [x] `20260217000001_agencyclaw_skill_catalog_and_csl_role.sql` applied
- [x] `20260217000002_agencyclaw_runtime_isolation.sql` applied
- [x] `20260217000003_client_brand_context_and_kpi_targets.sql` applied
- [x] `20260217000004_agent_core_tables.sql` applied
- [x] `20260217000005_skill_catalog_phase_2_6_seed.sql` applied
- [x] `20260217000006_clickup_space_skill_seed.sql` applied
- [x] `20260217000007_agent_tasks_source_reference_index.sql` applied
- [x] `20260219000001_clickup_space_registry.sql` applied

## 2. Chunk Progress
| Chunk | Name | Owner | Status | PR/Commit | Notes |
|---|---|---|---|---|---|
| C1 | Weekly task read path (`clickup_task_list_weekly`) | Claude | done | merged (`da5e86f`), follow-up fix (`8211088`) | Slack smoke test passed with linked task list output; skill enabled in `skill_catalog` |
| C2 | Task create flow (`clickup_task_create`) | Claude | done | merged (`ec23b78`, builds on `07b4b7e`) | Slack smoke passed; confirm/cancel flow active; `skill_catalog` updated (`implemented_in_code=true`, `enabled_default=true`) |
| C3 | Confirmation + dedupe hardening | Claude | done | merged (`ec23b78`) | Block Kit confirm/cancel, 10-min expiry, interaction dedupe via `slack_event_receipts` |
| C4 | Concurrency + ClickUp reliability | Claude | done | merged (`ee303b5`, `649b6cb`, `753a886`, `1422bdb`) | C4A-C4C landed: idempotency, duplicate suppression, retry/backoff, orphan event, indexed source reference, in-memory concurrency guard with ownership-safe release |
| C5 | Team identity sync/reconciliation | Claude | done | merged (`164c23c`, `48713dc`) | C5A-C5C landed: deterministic reconciliation engine, runtime sync service, and admin endpoint `POST /admin/identity-sync/run` |
| C6 | ClickUp space sync/classification | Claude | done | merged (`698e144`, `5abb867`) | Backend registry + admin endpoints + frontend admin page shipped; live Render smoke passed |
| C7 | `meeting_parser` standalone hardening | Claude | done | merged (`9001c27`) | Parser/review modules integrated; unit tests, typecheck, and production build passing |
| C8 | `client_context_builder` budget pack | Claude | done | merged (`a26da6a`) | Deterministic 4k budget pack, strict section caps, omission metadata + tests |
| C9 | Slack conversational orchestrator (LLM-first) | Claude | done | merged (`ec23b78`) | Feature-flagged DM orchestration + tool routing + backend `ai_token_usage` telemetry |
| C10B | Mutation clarify-state persistence loop hardening | Claude | done | merged (`647f365`) | Clarify-mode skill/args continuity + pending mutation-state persistence hardened to prevent task-create loop regressions |
| C10B.5 | Session conversation history buffer | Claude | done | merged (`647f365`) | Added bounded last-5 exchange buffer with 1,500-token cap + deterministic oldest-first eviction and role-based history injection |
| C10A | Actor/surface context resolver + policy gate | Claude | done | merged (`02fb45f`) | Added actor/surface policy gate with fail-closed enforcement on LLM + deterministic tool paths |
| C10C | KB retrieval cascade + source-grounded drafts | Claude | todo | - | SOP -> internal docs -> similar tasks -> external docs with citation/confidence output |
| C10D | Planner + capability-skill de-hardcoding | Claude | todo | - | Reduce rigid intent branches, explicitly carve out N-gram hardcoded path, keep behavior parity |
| C10E | Lightweight durable preference memory | Claude | todo | - | Persist operator defaults (assignee/cadence/client) and apply safely in drafting |

## 3. Open Blockers
- [x] Confirm migration `20260217000006_clickup_space_skill_seed.sql` is applied.
- [x] Confirm backend service has C9 runtime env keys in `agency-os-env-var` (`OPENAI_API_KEY`, `OPENAI_MODEL_PRIMARY`, `OPENAI_MODEL_FALLBACK`, `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `CLICKUP_API_TOKEN`, `CLICKUP_TEAM_ID`, `ENABLE_USAGE_LOGGING=1`).
- [x] Decide first chunk start timestamp and branch/PR convention.
- [x] Start C10B implementation branch and land regression tests for clarify-loop transcripts.
- [x] Start C10B.5 branch and land recent-history buffer tests for follow-up coherence.
- [x] Start C10A implementation branch and land actor/surface policy gate tests.

## 3.3 Locked Regression Fixtures (C10B)
- `R1_distex_coupon_drift`
  - `create task for Distex` -> title requested -> user provides coupon intent details -> must stay in pending mutation flow and avoid generic coupon/support reply drift.
- `R2_roger_loop_title`
  - `can you create tasks for roger` -> title requested -> repeated/ambiguous follow-ups (`setup coupons`, `jsut create it`, `make one up for me?`) -> must converge without looping title prompt indefinitely.

## 3.2 Deferred Future Features
- [x] `C4D` distributed cross-worker mutation lock explicitly deferred (pin for later hardening).
  Current runtime keeps in-memory per-worker guard + idempotency key duplicate suppression.

## 3.1 Latest Validation Notes
- C1 (Agent 1): `backend-core/tests/test_weekly_tasks.py` passing (37 tests). Added destination filter fix for list-only ClickUp mappings and trailing punctuation sanitization for client hints.
- C1 smoke test: Slack DM query returned 6 linked tasks for `Distex` with status/assignee formatting (pass).
- C1 runtime flag: `clickup_task_list_weekly` set to `implemented_in_code=true`, `enabled_default=true`.
- C7 slice (Agent 2): `frontend-web/src/lib/debrief/__tests__/meetingParser.test.ts` and `frontend-web/src/lib/debrief/__tests__/taskReview.test.ts` passing (18 tests total).
- C7 integration sanity: `frontend-web` typecheck and `next build` both pass with parser/review imports wired into debrief extract route.
- C2 (Agent 1): `backend-core/tests/test_task_create.py` + `backend-core/tests/test_weekly_tasks.py` passing (85 tests total). Includes pending-state guards for both `title` and `confirm_or_details`.
- C8 (Agent 2): `backend-core/tests/test_client_context_builder.py` passing (7 tests). Includes deterministic output, strict section caps, and deduplicated omission reasons.
- C3/C9 merge (`ec23b78`): `backend-core/tests/test_task_create.py`, `backend-core/tests/test_weekly_tasks.py`, `backend-core/tests/test_slack_orchestrator.py`, `backend-core/tests/test_c9b_integration.py`, and `backend-core/tests/test_slack_hardening.py` passing (136 tests total).
- C9 telemetry: backend logger now writes best-effort token usage rows to `ai_token_usage` (`tool='agencyclaw'`, stage `intent_parse`) when orchestrator LLM calls succeed.
- Runtime validation: Slack DM chat flow passed end-to-end (weekly read + create task + clarify/confirm behavior).
- Runtime validation: `ai_token_usage` now shows `tool='agencyclaw'` rows (model + token counts + meta) after enabling `ENABLE_USAGE_LOGGING=1`.
- C4A/C5A merge (`164c23c`): `backend-core/tests/test_clickup_reliability.py` + `backend-core/tests/test_identity_reconciliation.py` passing (31 tests total).
- C4B/C4C merge (`ee303b5`, `649b6cb`, `753a886`, `1422bdb`): `backend-core/tests/test_c4b_task_create_reliability.py`, `backend-core/tests/test_task_create.py`, and `backend-core/tests/test_weekly_tasks.py` passing (100 tests total).
- C5B/C5C merge (`48713dc`): `backend-core/tests/test_identity_reconciliation.py`, `backend-core/tests/test_identity_sync_runtime.py`, and `backend-core/tests/test_admin_identity_sync.py` passing (18 tests total).
- C6A merge (`698e144`): `backend-core/tests/test_clickup_space_registry.py` passing (20 tests).
- C6B/C6B.1 merge (`5abb867`): frontend ClickUp spaces admin page + API client + tests (17 tests).
- C6 live smoke (Render): `POST /admin/clickup-spaces/sync`, `GET /admin/clickup-spaces`, `POST /admin/clickup-spaces/classify`, filtered list, and map/unmap endpoints all returned 200.
- C10B/C10B.5 merge (`647f365`): `backend-core/tests/test_c10b_clarify_persistence.py`, `backend-core/tests/test_conversation_buffer.py`, `backend-core/tests/test_slack_orchestrator.py`, `backend-core/tests/test_task_create.py`, `backend-core/tests/test_weekly_tasks.py`, `backend-core/tests/test_c9b_integration.py`, and `backend-core/tests/test_slack_hardening.py` passing (171 tests).
- C10B/C10B.5 full-suite check after merge: `283 passed, 3 failed` (same pre-existing unrelated failures in `test_ngram_analytics.py`, `test_root_services.py`, `test_str_parser_spend.py`).
- C10A merge (`02fb45f`): `backend-core/tests/test_c10a_policy_gate.py` plus C10B/C9 integration suites passing (185 tests).
- C10A full-suite check after merge: `313 passed, 3 failed` (same pre-existing unrelated failures in `test_ngram_analytics.py`, `test_root_services.py`, `test_str_parser_spend.py`).
- Backend full test suite still has pre-existing unrelated failures outside these chunks.

## 4. Validation Checklist (Per Chunk)
- [ ] Behavior works in Slack runtime path.
- [ ] Permission/tier checks validated.
- [ ] Idempotency behavior validated.
- [ ] Concurrency behavior validated where relevant.
- [ ] Tests added and passing.
- [ ] `skill_catalog` row updated when chunk is truly implemented.
- [ ] Token telemetry written to `ai_token_usage` with `tool='agencyclaw'`.
- [ ] Tracker row updated.

## 5. Unified Coverage Matrix (PRD -> Plan -> Tracker)
| PRD Section | Implementation Plan Mapping | Tracker Status | Evidence | Remaining Gap / Next Action |
|---|---|---|---|---|
| 1. Product Intent | Global (all chunks) | in_progress | C1, C2, C3, C4, C5, C6, C7, C8, C9, C10B, C10B.5, C10A completed | Execute C10C -> C10D -> C10E |
| 2. Current Reality (Codebase) | Global baseline | done | Existing routes/services reused; no Bolt migration | Maintain reuse-first approach |
| 3. Naming + Role Standards | Baseline migrations | mostly_done | `20260217000001` applied; CSL rename landed | Verify all UI copy/runtime labels stay consistent |
| 4. Architecture (v1) | C1-C10 foundation | in_progress | LLM-first DM orchestration merged with deterministic fallback; C4/C5/C6 runtime wiring complete; C10B/C10B.5 continuity+history landed; C10A policy gate landed | Add KB retrieval cascade + planner/capability runtime convergence |
| 5. Slack Runtime Decision | C1-C4 + C9 | mostly_done | `/api/slack/events` + `/api/slack/interactions` active; C3/C4/C9 merged | Add distributed (cross-worker) concurrency lock if required |
| 6. Debrief As Slack-Native | C7 (+ later runtime wiring) | in_progress | C7 parser/review hardening done with tests/build pass | Add deeper runtime workflow checks as features expand |
| 7. Permissions Model | C2-C10 (policy-sensitive) | mostly_done | Identity mapping path in use; C5 runtime sync + admin execution endpoint merged; C10A actor/surface tool policy gate merged | Expand policy coverage for future non-DM/channel surfaces and granular role policies |
| 8. Data Model | Baseline migrations | done_for_v1_scope | `000001`..`000006` applied | Add new migrations only when new chunk needs schema |
| 9. Knowledge Base Strategy | C8 + C9 + C10C | in_progress | SOP/debrief paths exist; C8 + C9 merged | Implement retrieval cascade + source-grounded drafting with confidence tiers; then apply preference defaults |
| 10. Idempotency + Concurrency | C3, C4 | mostly_done | C3 merged; C4A-C4C merged incl. duplicate suppression + in-memory guard | Upgrade to distributed lock (Redis or DB advisory lock) for multi-worker safety |
| 11. Queue Strategy | Deferred in plan | deferred | Explicitly deferred in PRD/plan | Revisit after C1-C8 completion |
| 12. Google Meeting Notes Inputs | C7 | mostly_done | Debrief extraction flow and parser utilities validated | Add optional end-to-end runtime smoke as needed |
| 13. Skill Registry | C1-C9 | in_progress | Skills seeded via `000001`, `000005`, `000006`; C1 enabled | Enable each skill only when implemented and smoke-tested |
| 14. Failure + Compensation | C3, C4 | mostly_done | C3 merged; C4A-C4C helpers integrated into live task-create path | Add orphan reconciliation/sweep workflow |
| 15. Phased Delivery Plan | C1-C10 roadmap | in_progress | C1, C2, C3, C4, C5, C6, C7, C8, C9, C10B, C10B.5, C10A done | Execute remaining C10 order: C -> D -> E |
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
| C9 | 4, 5, 9, 13, 15 | 7, 10, 14 |
| C10B | 4, 5, 13, 15 | 10, 14 |
| C10B.5 | 4, 5, 13, 15 | 9, 10, 14 |
| C10A | 4, 7, 13, 15 | 5, 10, 14 |
| C10C | 4, 9, 13, 15 | 7, 14 |
| C10D | 4, 13, 15 | 5, 9, 10 |
| C10E | 4, 9, 13, 15 | 7, 14 |
