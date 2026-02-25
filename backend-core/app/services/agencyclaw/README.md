# AgencyClaw Service Package

Current status: active, production-critical, refactor-in-progress.

## Start Here
If you are new to this package:
1. Read `backend-core/docs/design/agencyclaw-architecture-map.md`
2. Read `backend-core/docs/design/agencyclaw-agent-loop.md`
3. Open `backend-core/app/api/routes/slack.py`
4. Follow runtime dispatch into:
   - `slack_route_runtime.py`
   - `slack_dm_runtime.py`
   - `agent_loop_runtime.py`

## What This Package Owns
- Slack request routing/runtime behavior for AgencyClaw.
- Agent-loop runtime and planner delegation flow.
- Task/ClickUp mutation and read paths.
- Command Center chat skill execution.
- Policy gating, pending confirmation, and related safety rails.
- Context/KB utilities used by orchestration/runtime paths.

## Layout Notes (Current)
- The package is currently flat (many modules at one level).
- Names ending with `_bridge_runtime` and `_deps_runtime` are composition/wiring layers.
- `app/api/routes/slack.py` keeps compatibility wrappers that many tests patch directly.

This means:
- prefer editing domain/runtime modules first,
- avoid renaming/removing route wrapper seams unless you are doing a coordinated migration.

## High-Signal Modules

Core runtime flow:
- `slack_route_runtime.py`
- `slack_dm_runtime.py`
- `slack_interaction_runtime.py`
- `slack_orchestrator_runtime.py`
- `agent_loop_runtime.py`

Skill execution:
- `slack_task_runtime.py`
- `slack_task_list_runtime.py`
- `slack_cc_dispatch.py`
- `command_center_lookup.py`
- `command_center_assignments.py`
- `command_center_brand_mutations.py`

Policy + registry:
- `policy_gate.py`
- `skill_registry.py`
- `pending_confirmation.py`
- `clickup_reliability.py`

## Testing Guidance
Before/after behavior changes, run at least:
- `backend-core/tests/test_c9b_integration.py`
- `backend-core/tests/test_c10a_policy_gate.py`
- `backend-core/tests/test_c10b_clarify_persistence.py`
- `backend-core/tests/test_task_create.py`
- `backend-core/tests/test_task_list.py`
- `backend-core/tests/test_slack_hardening.py`

Then run full backend tests:
- `backend-core/.venv/bin/pytest -q backend-core`

## Reorg Plan
Folder reorg is planned and documented in:
- `backend-core/docs/design/agencyclaw-architecture-map.md` (Section: Folder Reorg Blueprint)

Until that migration lands, treat current module paths as stable public internals for tests.
