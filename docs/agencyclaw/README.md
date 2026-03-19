# AgencyClaw Docs Index

Use this folder as the top-level navigation for AgencyClaw documentation.

## Current note (2026-03-19)
- The broader `agencyclaw/` docs still describe the target architecture and the larger legacy/agent-loop system.
- The currently shipped WBR Slack assistant work lives under `backend-core/app/services/theclaw/`.
- The currently shipped `theclaw/` Slack runtime is DM-only; channel/app-mention behavior is not implemented yet.
- The live WBR Slack path is now running successfully on `gpt-5-mini` after GPT-5-family adapter fixes in `theclaw/openai_client.py`.
- For the live WBR path, read:
  - `backend-core/app/services/theclaw/slack_minimal_runtime.py`
  - `backend-core/app/services/theclaw/skills/README.md`
  - `backend-core/app/services/theclaw/skills/wbr/wbr_summary/SKILL.md`
  - `backend-core/app/services/theclaw/skills/wbr/wbr_weekly_email_draft/SKILL.md`
  - `docs/wbr_snapshot_and_claw_email_plan.md`

## Current Operational Docs
- `docs/agencyclaw/current/26_agencyclaw_task_brief_standard.md`
- `docs/agencyclaw/current/29_catalog_lookup_contract.md`
- `docs/agencyclaw/current/30_agencyclaw_debug_chat_runbook.md` (Claw Gauntlet)
- `docs/agencyclaw/current/31_agencyclaw_test_meeting_fixture.md`
- `docs/agencyclaw/current/32_agencyclaw_supabase_debug_queries.sql`

For canonical live database structure, use `docs/db/schema_master.md`.

## Historical Planning/Execution Docs (Archived)
- `docs/agencyclaw/archive/23_agencyclaw_prd.md`
- `docs/agencyclaw/archive/24_agencyclaw_implementation_plan.md`
- `docs/agencyclaw/archive/25_agencyclaw_execution_tracker.md`
- `docs/agencyclaw/archive/26_agencyclaw_session_handoff.md`
- `docs/agencyclaw/archive/27_agencyclaw_parallel_runbook.md`

## Canonical Architecture Docs (Backend Design)
- `backend-core/docs/design/agencyclaw-architecture-map.md`
- `backend-core/docs/design/agencyclaw-agent-loop.md`

## Recommended Reading Order (New Contributor)
1. `backend-core/docs/design/agencyclaw-architecture-map.md`
2. `backend-core/docs/design/agencyclaw-agent-loop.md`
3. `backend-core/app/services/theclaw/skills/README.md`
4. `docs/wbr_snapshot_and_claw_email_plan.md` (for the shipped WBR/Slack slice)
5. `backend-core/app/services/agencyclaw/README.md`
6. `docs/agencyclaw/current/30_agencyclaw_debug_chat_runbook.md` (if debugging runtime behavior)

## Current WBR Slack Reality
- Surface: Slack DM only
- Live skills:
  - `wbr_summary`
  - `wbr_weekly_email_draft`
- Email drafting supports iterative revision instructions in conversation.
- There is still no browser email editor or automated send flow.

## Test Naming
- The canonical name for the terminal E2E debug test suite is `Claw Gauntlet`.
- Track naming under that suite:
  - `Core Track` (existing baseline runbook: `30_agencyclaw_debug_chat_runbook.md`)
  - `Meeting-to-Motion` (meeting summary -> tasks + follow-up flow)
