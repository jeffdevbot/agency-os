# Claw Gauntlet Issue List (2026-02-25)

Source run:
- `docs/agencyclaw/current/30_agencyclaw_debug_chat_runbook.md`
- local transcript (legacy prompt wording): `/tmp/claw_gauntlet_transcript.json`
- local transcript (current contract wording): `/tmp/claw_gauntlet_transcript_contract_v2.json`
- local transcript (latest runtime): `/tmp/claw_gauntlet_transcript_contract_v5_latest.json`
- local transcript (linked user + reset): `/tmp/claw_gauntlet_transcript_contract_v11_local_linked_reset.json`
- focused SOP follow-up check: `/tmp/claw_gauntlet_sop_followup_focus_v12.json`

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

7. `open` Novice guidance flow asks avoidable clarification after successful brand lookup.
   - Symptom: brand resolved (`lookup_brand`) but still returns generic "rephrase with client and target outcome."

8. `open` Planner follow-up quality is weak for "two sprints + open questions".
   - Symptom: planner returns `needs_clarification` despite context from prior audit turn.

9. `fixed` SOP-draft missing-info prompt now asks explicit execution-ready fields.
   - Prior symptom: generic follow-up without concrete readiness fields.
   - Fix landed: execution-readiness intent emits deterministic checklist (owner, discount terms, ASIN/SKU scope, dates, ClickUp destination) and uses latest task draft context.
   - Validation: focused run (`v12`) confirms checklist output.

10. `open` Test runbook lacks machine-checkable assertions.
   - Symptom: pass/fail requires manual inspection; regressions can slip across core prompts.

11. `partially_fixed` Session context over-anchoring after meeting turns is reduced.
   - Symptom (latest run): novice/mutation/planner prompts sometimes continue meeting-task framing instead of re-centering on new user intent.
   - Fix landed: meeting-note exchanges are filtered from LLM prompt context on non-meeting turns.
   - Additional hardening landed: debug route supports `reset_session=true` to force clean-run harness state.
   - Residual: deployed-Render confirmation still needed.

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

1. Planner follow-up quality (`#8`)
2. Novice/context grounding quality (`#7`)
3. Gauntlet automation assertions (`#10`)
4. Render clean-run confirmation (`#11`)
