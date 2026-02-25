# Claw Gauntlet Issue List (2026-02-25)

Source run:
- `docs/agencyclaw/current/30_agencyclaw_debug_chat_runbook.md`
- local transcript (legacy prompt wording): `/tmp/claw_gauntlet_transcript.json`
- local transcript (current contract wording): `/tmp/claw_gauntlet_transcript_contract_v2.json`
- local transcript (latest runtime): `/tmp/claw_gauntlet_transcript_contract_v5_latest.json`
- local transcript (linked user + reset): `/tmp/claw_gauntlet_transcript_contract_v11_local_linked_reset.json`
- focused SOP follow-up check: `/tmp/claw_gauntlet_sop_followup_focus_v12.json`
- local transcript (planner fix pass): `/tmp/claw_gauntlet_transcript_contract_v16_local_linked_reset.json`
- local transcript (novice recovery pass): `/tmp/claw_gauntlet_transcript_contract_v19_local_linked_reset.json`
- render transcript (deployed check): `/tmp/claw_gauntlet_transcript_contract_v20_render_linked_reset.json`
- render transcript (deployed check, post-deploy pass): `/tmp/claw_gauntlet_transcript_contract_v21_render_linked_reset.json`

## Open issues

1. `fixed` Raw control JSON leaked to user in SOP prompt.
   - Symptom: assistant replied with `{"mode":"search_kb","args":...}` instead of a user answer.
   - Root cause: agent-loop payload parser only accepted `mode="tool_call"` shape.
   - Fix landed: parse backward-compatible `{"mode":"<skill_id>","args":{...}}` as a tool call.

2. `fixed` Meeting-fixture extraction now deterministically returns SOP-mapped draft tasks.
   - Prior symptom: client-name lookup collapsed to sentence fragments.
   - Current behavior: fixture prompt returns actionable draft tasks + SOP mapping in draft-only mode.

3. `fixed` Follow-up meeting extraction now reuses recent meeting-notes context.
   - Prior symptom: follow-up mapping prompt asked for more details instead of using prior notes.
   - Current behavior: follow-up prompt re-emits SOP-mapped draft task set from recent meeting context.

4. `fixed` Mutation intent routing now recovers create path for natural phrasing.
   - Symptom: `"Create this task in ClickUp for Test: ..."` routed to read skills (`clickup_task_list`, `cc_client_lookup`) then clarification.
   - Fix landed: deterministic create-intent recovery now infers task args and stores pending confirmation.

5. `fixed` Confirmation handling + no-pending guardrail.
   - Symptom: `"Yes, create it."` was previously treated as non-confirmation or routed into generic clarification.
   - Fix landed: punctuation-tolerant confirmation normalization, expanded affirmative phrase set, and explicit no-pending response for bare confirm/cancel replies.

6. `fixed` Client/brand phrase parsing for create requests is now explicit.
   - Symptom: `"client Test and brand Test"` interpreted as a single client hint.
   - Fix landed: deterministic parser extracts `client_name`, `brand_name`, `task_title`, `task_description`.

7. `fixed` Novice guidance now returns deterministic first-step coaching and missing-only prompts.
   - Prior symptom: novice prompts drifted into generic SOP tutorials or weak clarification loops.
   - Fix landed: novice-intent recovery emits a stable "start first" plan and a brand-scoped "only missing inputs" response when user says "ask only what is missing."
   - Validation: local run (`v19`) shows stable outputs for `novice_1`, `novice_2`, and `novice_3`.

8. `fixed` Planner follow-up now returns deterministic two-sprint plan with open questions.
   - Prior symptom: planner returned `needs_clarification` despite context from prior audit turn.
   - Fix landed: deterministic planner-intent recovery for mapping audit + two-sprint follow-up, grounded on recent audit evidence when available.
   - Validation: local runs (`v16`, `v19`) show stable `planner_1` audit output and structured `planner_2` response.

9. `fixed` SOP-draft missing-info prompt now asks explicit execution-ready fields.
   - Prior symptom: generic follow-up without concrete readiness fields.
   - Fix landed: execution-readiness intent emits deterministic checklist (owner, discount terms, ASIN/SKU scope, dates, ClickUp destination) and uses latest task draft context.
   - Validation: focused run (`v12`) confirms checklist output.

10. `fixed` Test runbook now has machine-checkable assertions.
   - Symptom: pass/fail required manual inspection; regressions could slip across core prompts.
   - Fix landed: added `backend-core/scripts/claw_gauntlet_assert.py` for transcript contract checks.
   - Validation: `python backend-core/scripts/claw_gauntlet_assert.py /tmp/claw_gauntlet_transcript_contract_v19_local_linked_reset.json` passes.

11. `fixed` Session context over-anchoring after meeting turns is reduced.
   - Symptom (older runs): novice/mutation/planner prompts sometimes continued meeting-task framing instead of re-centering on new user intent.
   - Fix landed: meeting-note exchanges are filtered from LLM prompt context on non-meeting turns.
   - Additional hardening landed: debug route supports `reset_session=true` to force clean-run harness state.
   - Local status: clean-reset local runs (`v16`, `v19`) no longer show meeting-turn bleed into planner/mutation paths.
   - Render status (2026-02-25): initial deployed check (`v20`) failed novice assertions; post-deploy check (`v21`) passes full gauntlet assertion contract.
   - Validation: `python backend-core/scripts/claw_gauntlet_assert.py /tmp/claw_gauntlet_transcript_contract_v21_render_linked_reset.json` passes.

12. `fixed` Baseline capabilities prompt now returns deterministic help scope.
   - Symptom: first gauntlet prompt sometimes drifted into unrelated planner replies.
   - Fix landed: capabilities-intent guard returns stable capability list.

13. `fixed` SOP summary prompt recovers from non-answer action promises.
   - Symptom: SOP lookup prompts answered with "let me try again" instead of retrieval.
   - Fix landed: deterministic `search_kb` recovery for SOP-summary requests.

14. `fixed` SOP follow-up execution-readiness is now draft-grounded.
   - Prior symptom (`sop_3`): reply fell back to `Which client? Pick one and ask again:`.
   - Fix landed: execution-readiness intent path now bypasses task-list recovery and emits a missing-field checklist grounded on the latest task draft.
   - Validation: focused run (`v12`) returns owner + discount + ASIN/SKU + dates + ClickUp destination checklist.

## Proposed fix order

1. None (all tracked gauntlet issues are currently closed)
