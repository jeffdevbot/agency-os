# AgencyClaw Session Handoff

Last updated: 2026-02-20

## 1. Current State Snapshot
- PRD source of truth: `docs/23_agencyclaw_prd.md` version `1.18`.
- Execution source of truth: `docs/25_agencyclaw_execution_tracker.md`.
- Migrations through `20260219000002_agencyclaw_user_preferences.sql` are marked applied in tracker.
- Completed runtime chunks include C1 through C11F-A.
- Current active work has moved into Phase 2.6 chat-parity mutations (C12x).

## 2. Recently Landed
- C11D: Brand context resolver for destination-vs-brand split.
- C11E: Admin remediation preview/apply for unmapped ClickUp brand mappings.
- C11F-A: LLM-first conversational cleanup (no command-menu fallback in normal LLM-first path).

## 3. How To Resume Safely
1. Read these in order:
   - `docs/25_agencyclaw_execution_tracker.md` (status, commits, next actions)
   - `docs/24_agencyclaw_implementation_plan.md` (chunk contract)
   - `docs/23_agencyclaw_prd.md` (behavior/policy decisions)
2. Pick only the next `planned` or `in_progress` chunk from tracker.
3. Do not change completed chunk behavior unless fixing a verified bug/regression.

## 4. Session Resume Prompt
```text
Resume AgencyClaw implementation from tracker state.
Read:
1) docs/25_agencyclaw_execution_tracker.md
2) docs/24_agencyclaw_implementation_plan.md
3) docs/23_agencyclaw_prd.md

Implement only the next planned/in-progress chunk.
Preserve behavior of completed chunks unless fixing a confirmed bug.
Update tests and tracker with commit hash + validation notes.
```

## 5. Notes
- Avoid using this file as the execution ledger; use `docs/25_agencyclaw_execution_tracker.md`.
- Keep PRD version references consistent across docs when bumping.
