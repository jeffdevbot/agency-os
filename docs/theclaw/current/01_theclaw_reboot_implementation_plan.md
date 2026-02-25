# 01 - The Claw Reboot Implementation Plan

Status: proposed
Owner: Jeff + Codex
Last updated: 2026-02-25

## 1) Goal

Reboot AgencyClaw into **The Claw** with a strict baby-step rollout:
- make Slack assistant reliable first,
- add capabilities one skill at a time,
- remove legacy AgencyClaw code only after each replacement is proven.

## 2) Scope

In scope:
- New Slack runtime path for The Claw.
- Minimal phase-1 behavior (plain assistant chat via OpenAI).
- Skill-by-skill rollout with test gates.
- Controlled removal of legacy AgencyClaw files/tests.
- Removal of identity sync for now.
- Regression protection for existing non-Slack routes.

Out of scope (for reboot start):
- SOP-grounded execution,
- deep client memory/context,
- complex multi-step autonomous planning,
- broad admin automation.

## 3) Principles

1. Ship smallest possible working slice.
2. One new skill at a time.
3. No silent behavior changes.
4. Keep rollback path until replacement is proven.
5. Delete only after replacement tests are green.

## 3A) Guiding Philosophy

The Claw is being built as a **Jarvis-like operator assistant** for the agency:
- long-term, it should understand clients, agency operations, and Amazon selling deeply;
- short-term, it earns that capability one proven slice at a time.

Execution philosophy:
1. **LLM-first orchestration**: use strong models for understanding, planning, and response generation.
2. **Skill-calling architecture**: let the model call skills and specialist subagents when action is needed.
3. **No regex determinism as core intelligence**: avoid brittle intent-routing trees as the main control plane.
4. **Determinism only for safety rails**: keep hard checks for auth, policy, confirmations, idempotency, and auditability.
5. **Progressive depth**: ship basic usefulness first, then add memory/context and multi-step execution after each layer proves reliable.

## 4) Architecture Direction

- Keep `backend-core/app/main.py` as app bootstrap and router mount point.
- Keep Slack route surface (`/api/slack/...`) stable.
- Replace internals behind Slack route with new The Claw runtime modules.
- Remove legacy AgencyClaw runtime paths as replacements land.

## 5) Phase Plan (Baby Steps)

## Phase 0 - Baseline and Freeze

Deliverables:
- Capture passing backend baseline and route smoke checks.
- Freeze legacy behavior for reference.

Gate:
- `pytest -q backend-core` passes at baseline.
- Non-Slack product-route smoke checks (ngram/npat/root/adscope/clickup endpoints) unchanged.

## Phase 1 - Minimal Slack Assistant (No Skills)

Deliverables:
- Gut `backend-core/app/api/routes/slack.py` internals to minimal runtime path.
- Keep event verification and DM handling only.
- Single OpenAI call with a high-level Amazon agency assistant system prompt.
- No mutations, no SOP lookup, no planner, no pending state machine.
- No legacy fallback path in runtime.

Gate:
- Slack DM round-trip works manually.
- Assistant handles basic Q&A without crashes.
- Existing non-Slack route tests still pass.

## Phase 2 - Meeting Notes -> Task Suggestions (Draft Only)

Deliverables:
- Add first real skill: parse meeting notes and output structured draft tasks.
- Strictly draft mode only (no ClickUp writes).
- Response format is deterministic and readable.

Gate:
- Unit tests for parser/formatter + manual Slack transcript check.
- False positives reduced (no unrelated SOP references).

## Phase 3 - Task Creation Skill (One-by-One Confirmed Writes)

Deliverables:
- Add ClickUp create skill with explicit confirmation per task.
- Enforce one-by-one task creation, not bulk firehose.
- Idempotency and duplicate guard for retries.

Gate:
- Integration tests for successful create, duplicate prevention, and reject paths.
- Manual test in Test space with controlled fixtures.

## Phase 4 - Follow-up Email Draft Skill

Deliverables:
- Add email drafting skill from meeting notes + created tasks context.
- Draft-only output (no send).

Gate:
- Formatting and content quality checks pass against fixture cases.

## Phase 5 - Legacy Deletion

Deliverables:
- Remove unused AgencyClaw modules and tests.
- Remove identity sync endpoints/runtime.
- Remove legacy env flags not used by The Claw.

Deletion rules:
- Delete only when replacement tests exist and are passing.
- Delete in chunks with grep proof of no live imports.
- Keep rollback tag before each delete chunk.

Gate:
- Full backend suite green.
- `rg "services\.agencyclaw|AGENCYCLAW_" backend-core/app backend-core/tests` only shows intentional survivors (or none).

## Phase 6 - Hardening and Docs

Deliverables:
- Consolidated architecture doc for new contributors.
- Runbook for local and Render testing.
- Matrix tests for The Claw gauntlets.

Gate:
- New coder can run and validate flows from docs in under 30 minutes.

## 6) Skill Rollout Contract

Every skill must include:
- explicit trigger contract,
- explicit output schema,
- policy for allowed/disallowed actions,
- unit tests,
- one manual transcript test,
- rollback strategy.

No new skill ships without all six.

## 7) Test Strategy

Required on each chunk:
1. Targeted tests for touched modules.
2. Slack route runtime tests.
3. Full backend run before merge.
4. Manual Slack validation when behavior changes.

Minimum manual checks after each Slack change:
- DM greeting and plain question,
- meeting-notes to draft task suggestions,
- reject unsafe or ambiguous mutation attempts,
- confirm non-Slack routes still respond.

## 8) Cutover + Rollback

Cutover:
- Keep route path stable and cut internals directly to The Claw runtime.
- Do not maintain dual-path runtime flags.

Rollback:
- Preserve pre-cutover tag/branch.
- Roll back by git commit/tag, not runtime fallback toggles.

## 9) Immediate Execution Backlog

1. Create The Claw architecture doc skeleton.
2. Implement Phase 1 minimal Slack handler behind guarded switch.
3. Add tests for Phase 1 DM round-trip and error handling.
4. Run full backend suite and manual Slack smoke.
5. Then start Phase 2 (meeting notes -> draft tasks).

## 10) Definition of Done for Reboot

The reboot is done when:
- Slack assistant is stable for real daily use,
- meeting-notes -> draft tasks -> confirmed task creation works reliably,
- follow-up draft email works reliably,
- legacy AgencyClaw and identity sync are removed,
- docs and tests are simple enough for fast onboarding.
