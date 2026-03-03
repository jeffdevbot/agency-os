# 03 - The Claw Phase 3 Handoff

Status: in progress (paused for N-Gram fix work)
Owner: Jeff + Codex
Last updated: 2026-03-03

## 1) Where We Are

Phase 3 is partially implemented and currently stable at test level.

Latest relevant commits:
- `8528ff7` - pending confirmation state + explicit yes/no guard
- `fad8cad` - confirmation routing/disclaimer tightening
- `cb9d6d8` - confirmed ClickUp execution path + failure handling
- `74c7efe` - pending-confirmation runtime extraction + DM test split

Current backend baseline:
- `backend-core/.venv/bin/pytest -q backend-core`
- Result at handoff: `144 passed, 1 warning`

## 2) What Is Done (Phase 3)

1. Confirmed one-by-one ClickUp create flow exists.
2. Pending confirmation session state (`theclaw_pending_confirmation_v1`) is wired.
3. YES/NO guard executes without calling OpenAI while pending confirmation exists.
4. Create path is fail-closed for missing task/destination and retry-friendly for transient API/config errors.
5. Idempotency guard exists for already-sent tasks in session state.
6. Destination enrichment exists (space name -> space_id) before persistence when possible.
7. Same-turn resolved-context preference is implemented for enrichment.
8. Runtime code was trimmed by extracting pending-confirmation logic to a dedicated module.

Key runtime modules now:
- `backend-core/app/services/theclaw/slack_minimal_runtime.py`
- `backend-core/app/services/theclaw/pending_confirmation_runtime.py`
- `backend-core/app/services/theclaw/clickup_execution.py`
- `backend-core/app/services/theclaw/runtime_state.py`

## 3) What Is Not Done Yet

1. Full destination resolver skill loop for ambiguous/multi-client naming (Phase 3 gate quality, not complete).
2. Strong external dedup strategy beyond session-state guard (for replay/retry across sessions).
3. Manual Slack E2E acceptance pass for Phase 3 in Test Space with a formal transcript artifact.
4. Phase 3.5 read skills (`clickup_task_query`, `clickup_status_check`) not started.

## 4) Known Risks / Open Decisions

1. Current idempotency depends on stored sent linkage in session draft tasks; cross-session duplicate prevention is not yet hardened.
2. Destination enrichment performs a `list_spaces()` call during staging; acceptable now, could need memoization later.
3. ClickUp destination resolution still relies on name matching when IDs are not explicitly present.
4. `phase3_destination_enrichment_qa.md` exists but manual execution evidence is not yet captured in this handoff.

## 5) Next 3 Tasks (Recommended)

1. Destination reliability completion
- Implement/finish explicit destination resolution path so pending confirmation reliably carries `clickup_space_id` or `clickup_list_id`.
- Acceptance: no create attempt runs with unresolved destination name only.

2. Idempotency hardening
- Add deterministic dedup strategy for create retries beyond same-session linkage.
- Acceptance: retry/replay scenarios do not create duplicates.

3. Manual Phase 3 acceptance run (Test Space)
- Execute controlled fixture flow in Slack: extract -> stage -> confirm yes -> verify ClickUp task and status transitions.
- Acceptance: transcript + expected/actual checklist added under `docs/theclaw/current/`.

## 6) Resume Checklist

1. Read in order:
- `AGENTS.md`
- `docs/theclaw/current/01_theclaw_reboot_implementation_plan.md`
- `docs/theclaw/current/03_theclaw_phase3_handoff.md`
- `docs/theclaw/current/04_theclaw_phase3_resume_prompt.md`

2. Verify baseline:
- `backend-core/.venv/bin/pytest -q backend-core`

3. Start with Task #1 from section 5 of this handoff.

## 7) Working Tree Note At Handoff

There are unrelated/uncommitted docs/migration files in the repo; do not auto-revert unrelated changes.
