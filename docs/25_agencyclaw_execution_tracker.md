# AgencyClaw Execution Tracker

Last updated: 2026-02-20 (C12C Path-1 runtime landed)

## 1. Baseline Status
- [x] PRD updated to v1.19 (`docs/23_agencyclaw_prd.md`)
- [x] `20260217000001_agencyclaw_skill_catalog_and_csl_role.sql` applied
- [x] `20260217000002_agencyclaw_runtime_isolation.sql` applied
- [x] `20260217000003_client_brand_context_and_kpi_targets.sql` applied
- [x] `20260217000004_agent_core_tables.sql` applied
- [x] `20260217000005_skill_catalog_phase_2_6_seed.sql` applied
- [x] `20260217000006_clickup_space_skill_seed.sql` applied
- [x] `20260217000007_agent_tasks_source_reference_index.sql` applied
- [x] `20260219000001_clickup_space_registry.sql` applied
- [x] `20260219000002_agencyclaw_user_preferences.sql` applied

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
| C9 | Slack conversational orchestrator (LLM-first) | Claude | done | merged (`ec23b78`) | Feature-flagged DM orchestration + skill routing + backend `ai_token_usage` telemetry |
| C10B | Mutation clarify-state persistence loop hardening | Claude | done | merged (`647f365`) | Clarify-mode skill/args continuity + pending mutation-state persistence hardened to prevent task-create loop regressions |
| C10B.5 | Session conversation history buffer | Claude | done | merged (`647f365`) | Added bounded last-5 exchange buffer with 1,500-token cap + deterministic oldest-first eviction and role-based history injection |
| C10A | Actor/surface context resolver + policy gate | Claude | done | merged (`02fb45f`) | Added actor/surface policy gate with fail-closed enforcement on LLM + deterministic skill paths |
| C10C | KB retrieval cascade + source-grounded drafts | Claude | done | merged (`c1d7c77`) | Tiered retrieval (SOP/internal/similar/external placeholder) + deterministic grounded draft builder with citations/clarify behavior |
| C10D | Planner + capability-skill de-hardcoding | Claude | done | merged (`c43c6bd`) | Planner + deterministic executor landed behind feature flag; initial N-gram carve-out moved off hardcoded deterministic branch |
| C10E | Lightweight durable preference memory | Claude | done | merged (`fecab25`) | Durable user preference store + default-client set/clear commands + resolver integration merged; migration `20260219000002` applied |
| C10F | Semantic pending-state resolver hardening | Codex | done | merged (`3dbfd95`) | Added typed pending resolver service to decouple pending intent interpretation from route code; supports natural-language deferral/cancel/off-topic interruption without control-text leakage |
| C11A | Command Center read-only chat skills | Codex | done | merged (`8ac34b1`) | Added `cc_client_lookup`, `cc_brand_list_all`, and admin-only `cc_brand_clickup_mapping_audit` across LLM + deterministic paths with policy enforcement |
| C11B | LLM-first fallback cleanup | Codex | done | merged (`8ac34b1`) | Removed legacy hardcoded N-gram deterministic branch; defaulted runtime to LLM-first fallback behavior (`AGENCYCLAW_ENABLE_LEGACY_INTENTS` opt-in override) |
| C11D | Brand context resolver (destination-vs-brand split) | Codex | done | merged (`694d900`) | Resolver + runtime wiring landed with hardening: punctuation-safe product scope, title-step re-resolution, invalid brand-button guard; Slack smoke passed |
| C11E | Admin remediation skill for unmapped brands | Claude | done | foundation (`04a8589`), wiring (`f8729b6`) | Remediation preview + apply wired into Slack classifier/handler/policy; admin-only; 39 integration tests + 8 unit tests passing; no regressions in 208-test targeted suite |
| C11F-A | Conversational runtime cleanup (LLM-first) | Claude | done | merged (`d0d7328`) | Removed command-style fallback in LLM-first mode; tightened orchestrator prompt for natural replies; 11 tests + 314-test regression suite green |
| C12A | Command Center assignment mutation skills | Claude | done | merged (`cdd6749`) | Admin-only `cc_assignment_upsert` + `cc_assignment_remove` skills; service layer with fuzzy person resolve, role aliases, brand-scoped slots; classifier + handler + dual dispatcher wiring; 63 integration tests (incl. follow-up fixes: active-client fallback, bm/brand_manager alias, atomic upsert) |
| C12B | Brand CRUD chat mutations | Claude | done | merged (`cdd6749`) | Admin-only `cc_brand_create` + `cc_brand_update` skills; duplicate-safe create, partial-patch update, marketplace support; classifier + handler + dual dispatcher wiring; casing-preserving classifier capture fix included |
| C12C-prep | Catalog lookup contract/docs scaffolding | Codex | done | merged (`2036d19`) | Contract + fixtures only (`docs/29_catalog_lookup_contract.md`, `catalog_lookup_contract.py`, isolated tests); no Slack runtime wiring |
| C12C | Product identifier guardrail (Path-1, no catalog dependency) | Claude + Codex | done | merged (`0509cb7`) | Runtime fail-closed clarify/pending flow wired with deterministic identifier extraction and no lookup/guessing; explicit pending cues expanded; targeted guardrail tests passing |
| C13A | Strict LLM-first deterministic gating | Claude | done | merged (`e939160`) | In strict LLM mode (orchestrator on, legacy fallback off), deterministic classifier now allows only control intents (`switch_client`, `set_default_client`, `clear_defaults`). Non-control intents (`create_task`, `weekly_tasks`, `cc_*`) no longer execute via deterministic fallback. |
| C14A | Slack runtime decomposition phase 1 (helper extraction) | Codex | done | merged (`14cd21b`) | Extracted pure routing/helpers (`slack_helpers.py`) while keeping endpoint handlers in `slack.py`; no behavior change. |
| C14B | Pending task-create continuation extraction | Codex | done | merged (`efff226`) | Extracted pending continuation flow (`slack_pending_flow.py`) with compatibility wrappers in `slack.py`; pending FSM/messages preserved. |
| C14C | Command Center dispatch extraction | Codex | done | merged (`59088ff`) | Extracted CC dispatch/remediation formatting/client-hint helpers (`slack_cc_dispatch.py`) with injected dependencies for patch compatibility. |
| C14D | LLM orchestrator runtime extraction | Codex | done | merged (`14ae29d`) | Extracted `_try_llm_orchestrator` runtime into `slack_orchestrator_runtime.py` with thin wrapper/dependency injection in `slack.py`; no behavior change. |
| C14E | Slack DM event runtime extraction | Codex | done | merged (`4e5a87f`) | Extracted `_handle_dm_event` runtime flow into `slack_dm_runtime.py` with thin wrapper/dependency injection in `slack.py`; strict LLM-first gating and deterministic fallback behavior preserved. |
| C14F | Slack interaction runtime extraction | Codex | done | merged (`5c7e8e4`) | Extracted `_handle_interaction` runtime flow into `slack_interaction_runtime.py` with thin wrapper/dependency injection in `slack.py`; interaction dedupe, picker, and confirm/cancel semantics preserved. |
| C14G | Slack task-create runtime extraction | Codex | done | merged (`b85bd63`) | Extracted task-create runtime (`_execute_task_create`, `_handle_create_task`, `_enrich_task_draft`) into `slack_task_runtime.py` with thin wrappers/dependency injection in `slack.py`; task-create semantics preserved. |
| C14I | Runtime dependency contract hardening | Codex | done | pending commit | Introduced typed runtime dependency containers (`slack_runtime_deps.py`) and switched runtime modules/wrappers to pass a single deps object per runtime to reduce signature drift risk without behavior changes. |

## 3. Open Blockers
- [x] Confirm migration `20260217000006_clickup_space_skill_seed.sql` is applied.
- [x] Confirm backend service has C9 runtime env keys in `agency-os-env-var` (`OPENAI_API_KEY`, `OPENAI_MODEL_PRIMARY`, `OPENAI_MODEL_FALLBACK`, `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `CLICKUP_API_TOKEN`, `CLICKUP_TEAM_ID`, `ENABLE_USAGE_LOGGING=1`).
- [x] Decide first chunk start timestamp and branch/PR convention.
- [x] Start C10B implementation branch and land regression tests for clarify-loop transcripts.
- [x] Start C10B.5 branch and land recent-history buffer tests for follow-up coherence.
- [x] Start C10A implementation branch and land actor/surface policy gate tests.
- [x] Start C11D implementation branch and land shared-destination brand disambiguation tests.

## 3.3 Locked Regression Fixtures (C10B)
- `R1_distex_coupon_drift`
  - `create task for Distex` -> title requested -> user provides coupon intent details -> must stay in pending mutation flow and avoid generic coupon/support reply drift.
- `R2_roger_loop_title`
  - `can you create tasks for roger` -> title requested -> repeated/ambiguous follow-ups (`setup coupons`, `jsut create it`, `make one up for me?`) -> must converge without looping title prompt indefinitely.

## 3.2 Deferred Future Features
- [x] `C4D` distributed cross-worker mutation lock explicitly deferred (pin for later hardening).
  Current runtime keeps in-memory per-worker guard + idempotency key duplicate suppression.
- [x] Path-1 decision for `C12C` is locked: fail-closed identifier clarification without live catalog lookup integration.
  Runtime must clarify missing identifiers or create explicit "ASIN pending" drafts with unresolved fields; no silent identifier guessing.
- [x] C12C Path-1 runtime wiring shipped (no catalog integration): explicit identifier capture/normalization, clarify/pending behavior, and regression coverage.
- [ ] Optional later path: `catalog_lookup` skill with real product data source integration.
- [ ] Multi-user channel memory hardening under C10E:
  actor-scoped preferences only, requester-bound pending state, and explicit `requested_by` vs `confirmed_by` audit fields.

## 3.4 Scope Freeze (Near-Term)
- Committed now:
  - Complete and harden current chat parity path (through C12B) plus C12C Path-1 fail-closed identifier behavior.
  - Keep LLM-first conversational runtime with policy/idempotency/confirmation rails.
- Deferred indefinitely (not release blockers):
  - Distributed cross-worker lock (`C4D`) unless operational contention proves current guard insufficient.
  - Queue-lane architecture and background orchestration expansion.
  - Cross-user admin approval workflow beyond self-confirmation model.
  - Inbound ClickUp webhook sync.
- Explicitly optional / not near-term commitments:
  - Vector semantic retrieval tiers.
  - External transcript/document ingestion (for example YouTube pipelines).
  - Multi-agent decomposition.

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
- C10C implementation: `backend-core/tests/test_kb_retrieval.py` + `backend-core/tests/test_grounded_task_draft.py` passing (38 tests).
- C10C targeted check (C9B-C10C): `223 passed, 0 failed`.
- C10C full-suite check: `351 passed, 3 failed` (same pre-existing unrelated failures in `test_ngram_analytics.py`, `test_root_services.py`, `test_str_parser_spend.py`).
- Task brief standard documented in `docs/26_agencyclaw_task_brief_standard.md` and linked in PRD/implementation plan (includes bucketed templates + generic unclassified fallback).
- ASIN ambiguity guardrail documented: no identifier guessing; clarify for ASIN/SKU or explicit pending fields in draft output.
- C10D planner suites: `backend-core/tests/test_planner.py` + `backend-core/tests/test_plan_executor.py` passing (27 tests).
- C10E targeted checks: `backend-core/tests/test_preference_memory.py` + `backend-core/tests/test_task_create.py` + `backend-core/tests/test_c10b_clarify_persistence.py` passing (97 tests).
- Full-suite check after C10E: `430 passed, 3 failed` (same pre-existing unrelated failures in `test_ngram_analytics.py`, `test_root_services.py`, `test_str_parser_spend.py`).
- ASIN interruption hardening: pending `asin_or_pending` flow now supports intent escape + cancel + off-topic fallthrough to normal routing; regression tests added in `backend-core/tests/test_task_create.py` (`59 passed`) and targeted continuity suites remain green (`54 passed`).
- C10F semantic resolver check: `backend-core/tests/test_pending_resolution.py`, `backend-core/tests/test_task_create.py`, `backend-core/tests/test_c10b_clarify_persistence.py`, and `backend-core/tests/test_weekly_tasks.py` passing (`131 passed`).
- C10F full-suite check: `451 passed, 3 failed` (same pre-existing unrelated failures in `test_ngram_analytics.py`, `test_root_services.py`, `test_str_parser_spend.py`).
- SOP sync runtime bugfix (`sop_sync.py`): fixed Supabase update chain incompatibility; live sync now succeeds (`15/15` SOPs synced, `0` missing content rows).
- C11A/C11B merge (`8ac34b1`): `backend-core/tests/test_command_center_lookup.py`, `backend-core/tests/test_c11a_command_center_integration.py`, `backend-core/tests/test_c9b_integration.py`, `backend-core/tests/test_task_create.py`, and `backend-core/tests/test_weekly_tasks.py` passing (targeted suites green).
- C11A/C11B full-suite check after merge: `512 passed, 3 failed` (same pre-existing unrelated failures in `test_ngram_analytics.py`, `test_root_services.py`, `test_str_parser_spend.py`).
- N-gram special skill cleanup: removed `ngram_research` from `skill_registry`, policy gate mutation set, planner handler map, and orchestrator dispatch. N-gram requests now route through normal `clickup_task_create` + C10C SOP grounding path (no dedicated N-gram execution skill).
- C11A query hardening (`43bd149`): command-center brand/client lookup now falls back safely when FK join metadata is unavailable; tests `26 passed` (`test_command_center_lookup.py`) and C11A integration suite `36 passed`.
- C11E foundation (`04a8589`): `backend-core/app/services/agencyclaw/brand_mapping_remediation.py` + `backend-core/tests/test_brand_mapping_remediation.py` added; planner/apply unit suite `8 passed`.
- C11D merge (`694d900`): brand context resolver shipped end-to-end with runtime hardening. Targeted suites: `test_brand_context_resolver.py` (35), `test_task_create.py` (brand/title path subset), `test_slack_hardening.py`, and `test_c10b_clarify_persistence.py` all passing.
- C11D Slack smoke passed in production DM path:
  - shared-destination + product-scoped prompts trigger brand picker,
  - shared-destination + generic prompts proceed client-level,
  - punctuation variants (`coupon?`, `listing,`, `product-level`) correctly treated as product-scoped.
- C11E wiring: `test_c11e_remediation_integration.py` (39 passed), `test_brand_mapping_remediation.py` (8 passed), `test_c11a_command_center_integration.py` (36 passed). Targeted regression suite (task_create, weekly_tasks, slack_hardening, c10b, c9b, command_center_lookup, c10a_policy_gate): 208 passed, 0 failed.
- C11F-A: `test_c11f_conversational_cleanup.py` (11 passed). Broad regression suite (c9b, slack_orchestrator, c10b, task_create, weekly_tasks, slack_hardening, c11a, c11e, c10a_policy_gate, command_center_lookup): 314 passed, 0 failed.
- C11A UX clarification (`e19dce7`): client lookup output now explicitly states assignment/access scope to reduce confusion when users see only assigned clients.
- C12A: `test_c12a_assignment_integration.py` (53 passed). Full regression suite: 674 passed, 3 failed (same pre-existing unrelated failures in `test_ngram_analytics.py`, `test_root_services.py`, `test_str_parser_spend.py`).
- C12A follow-up fixes: `test_c12a_assignment_integration.py` (63 passed, up from 53). Added active-client fallback, bm/brand_manager -> CSL alias, atomic update-in-place for slot replacement. Full suite: 684 passed, 3 failed (pre-existing).
- C12B: `test_c12b_brand_mutation_integration.py` (52 passed). Targeted regression suite: 414 passed, 0 failed. Full suite: 740 passed, 3 failed (same pre-existing unrelated failures).
- C12C prep (docs/scaffolding only): added `docs/29_catalog_lookup_contract.md`, tightened PRD/plan acceptance wording, and added isolated contract tests (`backend-core/tests/test_catalog_lookup_contract.py`) with no Slack runtime wiring changes.
- C12A/C12B merge + classifier casing fix (`cdd6749`): targeted suites (`test_c11a_command_center_integration.py`, `test_c12a_assignment_integration.py`, `test_c12b_brand_mutation_integration.py`, `test_catalog_lookup_contract.py`) passing (`155 passed`).
- C12C Path-1 runtime: `backend-core/tests/test_task_create.py`, `backend-core/tests/test_c12c_identifier_guardrail.py`, and `backend-core/tests/test_c10b_clarify_persistence.py` passing (`93 passed`).
- C13A LLM-first hardening: in strict LLM mode (orchestrator on, legacy fallback off), deterministic classifier now allows only control intents (`switch_client`, `set_default_client`, `clear_defaults`). Non-control intents (`create_task`, `weekly_tasks`, `cc_*`) no longer execute via deterministic fallback. Targeted suites: `test_c11f_conversational_cleanup.py`, `test_c9b_integration.py`, `test_task_create.py`, `test_weekly_tasks.py` passing (`148 passed`).
- C13B routing cleanup: extracted strict-mode deterministic gating into helpers (`_is_llm_strict_mode`, `_is_deterministic_control_intent`, `_should_block_deterministic_intent`) with no behavior change; targeted suites remain green.
- C13C alias cleanup: removed temporary tool->skill compatibility aliases from `skill_registry`, `policy_gate`, `slack.py`, and `agencyclaw.__init__`; canonical naming only (`SKILL_SCHEMAS`, `validate_skill_call`, `get_skill_descriptions_for_prompt`, `evaluate_skill_policy`, `_check_skill_policy`). No behavior change observed in targeted regression suites.
- C14A decomposition (phase 1): extracted pure Slack routing helpers into `backend-core/app/services/agencyclaw/slack_helpers.py` (intent classification/patterns, strict LLM deterministic gating helpers, identifier extraction, and weekly formatting utilities) while keeping endpoint handlers in `slack.py`; behavior-preserving targeted suite remained green.
- C14B decomposition (phase 1): extracted pending task-create continuation flow (`_compose_asin_pending_description`, `_handle_pending_task_continuation`) into `backend-core/app/services/agencyclaw/slack_pending_flow.py` with `slack.py` compatibility wrappers; pending FSM behavior/messages preserved in targeted regression suites.
- C14C decomposition (phase 1): extracted Command Center dispatch and remediation format/client-hint helpers into `backend-core/app/services/agencyclaw/slack_cc_dispatch.py` with `slack.py` compatibility wrappers; CC routing behavior preserved in targeted integration suites.
- C14D decomposition (phase 1): extracted LLM orchestrator runtime (`_try_llm_orchestrator`) into `backend-core/app/services/agencyclaw/slack_orchestrator_runtime.py` with a thin wrapper/dependency-injection bridge in `slack.py`; orchestrator routing behavior preserved in targeted suites.
- C14E decomposition (phase 1): extracted DM event runtime (`_handle_dm_event`) into `backend-core/app/services/agencyclaw/slack_dm_runtime.py` with a thin wrapper/dependency-injection bridge in `slack.py`; planner/orchestrator/deterministic routing behavior preserved in targeted suites.
- C14F decomposition (phase 1): extracted interaction runtime (`_handle_interaction`) into `backend-core/app/services/agencyclaw/slack_interaction_runtime.py` with a thin wrapper/dependency-injection bridge in `slack.py`; dedupe/picker/confirm-cancel behavior preserved in targeted suites.
- C14G decomposition (phase 1): extracted task-create runtime (`_execute_task_create`, `_handle_create_task`, `_enrich_task_draft`) into `backend-core/app/services/agencyclaw/slack_task_runtime.py` with thin wrapper/dependency-injection bridges in `slack.py`; task-create behavior preserved in targeted suites.
- C14I hardening: added typed dependency containers in `backend-core/app/services/agencyclaw/slack_runtime_deps.py` and migrated extracted runtimes (`slack_orchestrator_runtime.py`, `slack_dm_runtime.py`, `slack_interaction_runtime.py`, `slack_task_runtime.py`) plus `slack.py` wrappers to single-object dependency wiring; no behavior changes expected.
- Full backend validation is currently green: `898 passed, 0 failed, 1 warning` (`pytest -q backend-core`).

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
| 1. Product Intent | Global (all chunks) | mostly_done | C1, C2, C3, C4, C5, C6, C7, C8, C9, C10B, C10B.5, C10A, C10C, C10D, C10E, C10F, C11A, C11B, C11D, C11E, C11F-A, C12A, C12B, C12C Path-1 done | Phase 2 closure smoke + decide Phase 3 kickoff timing |
| 2. Current Reality (Codebase) | Global baseline | done | Existing routes/services reused; no Bolt migration | Maintain reuse-first approach |
| 3. Naming + Role Standards | Baseline migrations | mostly_done | `20260217000001` applied; CSL rename landed | Verify all UI copy/runtime labels stay consistent |
| 4. Architecture (v1) | C1-C11 foundation | mostly_done | LLM-first DM orchestration merged; C11B reduced deterministic fallback pressure; C4/C5/C6 runtime wiring complete; C10B/C10B.5/C10A/C10C/C10D/C10E/C10F/C11D/C11E landed | Expand channel-surface policy coverage |
| 5. Slack Runtime Decision | C1-C4 + C9 | mostly_done | `/api/slack/events` + `/api/slack/interactions` active; C3/C4/C9 merged | Add distributed (cross-worker) concurrency lock if required |
| 6. Debrief As Slack-Native | C7 (+ later runtime wiring) | in_progress | C7 parser/review hardening done with tests/build pass | Add deeper runtime workflow checks as features expand |
| 7. Permissions Model | C2-C10 (policy-sensitive) | mostly_done | Identity mapping path in use; C5 runtime sync + admin execution endpoint merged; C10A actor/surface skill policy gate merged | Expand policy coverage for future non-DM/channel surfaces and granular role policies |
| 8. Data Model | Baseline migrations | done_for_v1_scope | `000001`..`000006` applied | Add new migrations only when new chunk needs schema |
| 9. Knowledge Base Strategy | C8 + C9 + C10C | mostly_done | SOP/debrief paths exist; C8 + C9 merged; C10C retrieval cascade + grounded draft composer merged | Keep vector/external retrieval explicitly optional (not required for Phase 2.6) |
| 10. Idempotency + Concurrency | C3, C4 | mostly_done | C3 merged; C4A-C4C merged incl. duplicate suppression + in-memory guard | Upgrade to distributed lock (Redis or DB advisory lock) for multi-worker safety |
| 11. Queue Strategy | Deferred in plan | deferred | Explicitly deferred in PRD/plan | Revisit only if runtime load requires it |
| 12. Google Meeting Notes Inputs | C7 | mostly_done | Debrief extraction flow and parser utilities validated | Add optional end-to-end runtime smoke as needed |
| 13. Skill Registry | C1-C9 | in_progress | Skills seeded via `000001`, `000005`, `000006`; C1 enabled | Enable each skill only when implemented and smoke-tested |
| 14. Failure + Compensation | C3, C4 | mostly_done | C3 merged; C4A-C4C helpers integrated into live task-create path | Add orphan reconciliation/sweep workflow |
| 15. Phased Delivery Plan | C1-C12 roadmap | mostly_done | C1, C2, C3, C4, C5, C6, C7, C8, C9, C10B, C10B.5, C10A, C10C, C10D, C10E, C10F, C11A, C11B, C11D, C11E, C11F-A, C12A, C12B, C12C Path-1 done | Optional C12C Path-2 (catalog integration) remains deferred by scope freeze |
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
| C11A | 4, 7, 13, 15 | 5, 10 |
| C11B | 4, 5, 13, 15 | 10, 14 |
| C11D | 4, 7, 13, 15 | 9, 10, 14 |
| C11E | 4, 7, 13, 15 | 10, 14 |
| C11F-A | 4, 5, 13, 15 | 10 |
| C12A | 4, 7, 13, 15 | 5, 8, 10 |
| C12B | 4, 7, 8, 13, 15 | 5, 10 |
