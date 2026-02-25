# AgencyClaw Architecture Map (Current State)

Status: active  
Last updated: 2026-02-25  
Audience: engineers onboarding to AgencyClaw (human or AI)

## 1. Purpose
This document is the current-state map of the AgencyClaw backend architecture.

Use this as the first read when you need to understand:
- where Slack requests enter,
- which runtime path executes (agent loop vs legacy),
- where business behavior actually lives,
- where to make focused, low-risk changes.

Related docs:
- Product/behavior intent: `docs/23_agencyclaw_prd.md`
- Implementation history and chunk evidence: `docs/25_agencyclaw_execution_tracker.md`
- Agent-loop deep design: `backend-core/docs/design/agencyclaw-agent-loop.md`

## 2. Entry Points

### API Routes
- Slack HTTP route: `backend-core/app/api/routes/slack.py`
- Route shape:
  - `POST /api/slack/events`
  - `POST /api/slack/interactions`
  - `POST /api/slack/debug/chat` (guarded by env flags/token)

### Route Runtime Adapters
- HTTP verification/parsing: `backend-core/app/services/agencyclaw/slack_http_route_runtime.py`
- Route-to-runtime wiring: `backend-core/app/services/agencyclaw/slack_route_runtime.py`
- Route dependency builders: `backend-core/app/services/agencyclaw/slack_route_deps_runtime.py`
- Debug route guard/parsing: `backend-core/app/services/agencyclaw/slack_debug_route_runtime.py`

## 3. Runtime Mode Matrix

Primary flag:
- `AGENCYCLAW_AGENT_LOOP_ENABLED=true`: agent-loop path is primary.
- `AGENCYCLAW_AGENT_LOOP_ENABLED=false`: legacy orchestrator/deterministic path.

DM flow (high-level):
1. `slack.py` route receives event.
2. `slack_http_route_runtime.py` verifies and parses Slack envelope.
3. `slack_route_runtime.py` constructs DM runtime deps and dispatches.
4. `slack_dm_runtime.py` applies lane lock, loads session, and routes:
   - agent loop path first when enabled;
   - pending continuation;
   - LLM orchestrator path;
   - deterministic fallback path.

Interaction flow:
1. `slack.py` receives interaction payload.
2. `slack_http_route_runtime.py` verifies/parses payload.
3. `slack_route_runtime.py` dispatches interaction handler.
4. `slack_interaction_runtime.py` applies dedupe + button semantics.

## 4. Layered Module Topology

Current package: `backend-core/app/services/agencyclaw` (55 Python files, flat layout).

### A) Slack Route + Runtime Composition
- `slack_route_runtime.py`
- `slack_route_deps_runtime.py`
- `slack_runtime_deps.py`
- `slack_http_route_runtime.py`
- `slack_debug_route_runtime.py`
- `slack_route_helpers.py`
- `debug_chat.py`

### B) DM/Orchestrator/Planner Runtime
- `slack_dm_runtime.py`
- `slack_orchestrator.py`
- `slack_orchestrator_runtime.py`
- `slack_planner_runtime.py`
- `planner.py`
- `plan_executor.py`
- `slack_planner_delegate_runtime.py`

### C) Agent Loop Runtime
- `agent_loop_runtime.py`
- `agent_loop_context_assembler.py`
- `agent_loop_skill_validation.py`
- `agent_loop_intent_recovery.py`
- `agent_loop_store.py`
- `agent_loop_turn_logger.py`
- `agent_loop_evidence.py`
- `agent_loop_evidence_reader.py`
- `slack_agent_loop_bridge_runtime.py`

### D) Task + Pending Flow
- `slack_task_runtime.py`
- `slack_task_list_runtime.py`
- `slack_task_bridge_runtime.py`
- `slack_pending_flow.py`
- `pending_confirmation.py`
- `pending_resolution.py`
- `clickup_reliability.py`

### E) Command Center + Brand/Assignment
- `slack_cc_dispatch.py`
- `slack_cc_bridge_runtime.py`
- `command_center_lookup.py`
- `command_center_assignments.py`
- `command_center_brand_mutations.py`
- `brand_mapping_remediation.py`
- `clickup_space_registry.py`

### F) Policy, Registry, Context, Knowledge
- `policy_gate.py`
- `skill_registry.py`
- `client_context_builder.py`
- `kb_retrieval.py`
- `grounded_task_draft.py`
- `brand_context_resolver.py`
- `preference_memory.py`
- `conversation_buffer.py`
- `catalog_lookup_contract.py` (contract only)

### G) Identity + Queue
- `identity_reconciliation.py`
- `identity_sync_runtime.py`
- `session_lane_queue.py`

## 5. What Is Canonical vs Compatibility

Canonical current behavior:
- `clickup_task_list` is canonical (weekly alias retained for compatibility).
- Agent-loop path is the primary future direction when flag enabled.

Compatibility seams intentionally preserved:
- `backend-core/app/api/routes/slack.py` still exposes wrapper functions (many tests patch these directly).
- Legacy intent/orchestrator paths remain for resilience and controlled rollout.

Practical rule:
- When editing behavior, prefer runtime/service modules.
- Keep route wrapper names stable unless performing a coordinated seam migration.

## 6. Onboarding Reading Order (Fast Path)
1. `backend-core/app/api/routes/slack.py`
2. `backend-core/app/services/agencyclaw/slack_route_runtime.py`
3. `backend-core/app/services/agencyclaw/slack_dm_runtime.py`
4. `backend-core/app/services/agencyclaw/agent_loop_runtime.py`
5. `backend-core/app/services/agencyclaw/slack_task_bridge_runtime.py`
6. `backend-core/app/services/agencyclaw/slack_cc_bridge_runtime.py`
7. `backend-core/app/services/agencyclaw/policy_gate.py`
8. `backend-core/app/services/agencyclaw/skill_registry.py`
9. `docs/25_agencyclaw_execution_tracker.md` (for chunk history/context)

## 7. Where To Change What

Add/modify read skill behavior:
- Agent loop execution: `agent_loop_runtime.py` + `agent_loop_skill_validation.py`
- Legacy/orchestrator routing: `slack_orchestrator_runtime.py`
- Skill implementation: relevant domain module (`command_center_lookup.py`, `slack_task_list_runtime.py`, etc.)
- Policy: `policy_gate.py`

Add/modify mutation behavior:
- Runtime confirmation contracts: `pending_confirmation.py`, `slack_pending_flow.py`, `slack_interaction_runtime.py`
- Mutation execution logic: `slack_task_runtime.py`, `command_center_*`
- Idempotency/retry: `clickup_reliability.py`

Route/http behavior:
- Route shape and wrapper seams: `app/api/routes/slack.py`
- HTTP request parsing/verification: `slack_http_route_runtime.py`

## 8. Test Map (High Signal Suites)

Core regression:
- `backend-core/tests/test_c9b_integration.py`
- `backend-core/tests/test_c10a_policy_gate.py`
- `backend-core/tests/test_c10b_clarify_persistence.py`
- `backend-core/tests/test_task_create.py`
- `backend-core/tests/test_task_list.py`
- `backend-core/tests/test_slack_hardening.py`

Agent-loop focused:
- `backend-core/tests/test_agent_loop_runtime_skill_call.py`
- `backend-core/tests/test_c17c_lane_queue_runtime.py`

Command Center focused:
- `backend-core/tests/test_c11a_command_center_integration.py`
- `backend-core/tests/test_c11e_remediation_integration.py`
- `backend-core/tests/test_c12a_assignment_integration.py`
- `backend-core/tests/test_c12b_brand_mutation_integration.py`

## 9. Folder Reorg Blueprint (Planned)

Target (future) package layout:
- `agencyclaw/runtime/slack/`
- `agencyclaw/runtime/agent_loop/`
- `agencyclaw/skills/tasks/`
- `agencyclaw/skills/command_center/`
- `agencyclaw/context/`
- `agencyclaw/core/`
- `agencyclaw/infra/`

Migration constraints:
- Keep import compatibility shims during transition.
- Preserve `app.api.routes.slack` wrapper seams until tests and callers are migrated.
- Move one area at a time with full-suite validation after each move.

Suggested migration order:
1. Move route runtime modules (`slack_*route*`, `slack_runtime_deps.py`)
2. Move task skill modules
3. Move command-center skill modules
4. Move agent-loop modules
5. Move shared core/context modules
6. Remove shim imports once call sites/tests are migrated

## 10. Known Architectural Debt
- Flat module namespace with mixed layers slows discoverability.
- Route file still carries broad import surface due compatibility wrappers.
- Naming is chunk-history-driven (`*_bridge_runtime`, `*_deps_runtime`) rather than domain-oriented.

This debt is acceptable short-term but should be reduced via the phased folder reorg above.
