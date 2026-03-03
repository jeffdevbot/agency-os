# 04 - The Claw Phase 3 Resume Prompt

Use this prompt to restart The Claw Phase 3 work in a fresh AI session.

---

You are continuing The Claw Phase 3 work in `agency-os`.

Read first (in order):
1. `AGENTS.md`
2. `docs/theclaw/current/01_theclaw_reboot_implementation_plan.md`
3. `docs/theclaw/current/03_theclaw_phase3_handoff.md`
4. `docs/theclaw/current/phase3_destination_enrichment_qa.md`

Current assumptions:
- Phase 3 is in progress.
- Latest The Claw commits include:
  - `8528ff7`
  - `fad8cad`
  - `cb9d6d8`
  - `74c7efe`
- Runtime split includes:
  - `backend-core/app/services/theclaw/slack_minimal_runtime.py`
  - `backend-core/app/services/theclaw/pending_confirmation_runtime.py`
  - `backend-core/app/services/theclaw/clickup_execution.py`
  - `backend-core/app/services/theclaw/runtime_state.py`
- Last known backend baseline: `144 passed, 1 warning`.

First tasks:
1. Verify local baseline:
   - `backend-core/.venv/bin/pytest -q backend-core`
2. Quick context audit of hot files:
   - `backend-core/app/services/theclaw/slack_minimal_runtime.py`
   - `backend-core/app/services/theclaw/pending_confirmation_runtime.py`
   - `backend-core/app/services/theclaw/clickup_execution.py`
   - `backend-core/tests/test_theclaw_dm_turn_confirmation.py`
   - `backend-core/tests/test_theclaw_dm_turn_enrichment.py`
3. Implement next safe Phase 3 chunk only:
   - destination reliability completion (IDs preferred over names)
   - no scope expansion to Phase 3.5
4. Run targeted tests + full backend run.
5. Commit with concise message and report:
   - files changed + rationale
   - exact test counts/results
   - residual risks

Constraints:
- No broad refactor beyond the active chunk.
- Preserve behavior and fail-closed mutation safety.
- Do not revert unrelated user changes in dirty working tree.
- Keep runtime modular (avoid adding large inline logic back into `slack_minimal_runtime.py`).

Definition of success for this session:
- One safe, test-verified Phase 3 improvement landed.
- Full backend suite remains green.
- Handoff notes updated if priorities changed.

---
