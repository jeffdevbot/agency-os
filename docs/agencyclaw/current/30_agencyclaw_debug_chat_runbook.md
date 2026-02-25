# AgencyClaw Claw Gauntlet Runbook

Canonical name: `Claw Gauntlet`.

This runbook is for fast end-to-end testing through:
- `POST /api/slack/debug/chat`
- `backend-core/scripts/debug_chat.py`

It validates natural-language behavior, skill routing, SOP retrieval, client/brand resolution, and safe task creation in your Test ClickUp space.

## 1) Prerequisites

Render env vars:
- `AGENCYCLAW_DEBUG_CHAT_ENABLED=true`
- `AGENCYCLAW_DEBUG_CHAT_TOKEN=<secret>`
- `AGENCYCLAW_DEBUG_CHAT_USER_ID=U_DEBUG_TERMINAL` (recommended)
- `AGENCYCLAW_DEBUG_CHAT_ALLOW_MUTATIONS=true` (set `false` for read-only)
- `AGENCYCLAW_AGENT_LOOP_ENABLED=true`

Local shell:
```bash
export DEBUG_CHAT_TOKEN="<same-secret>"
python backend-core/scripts/debug_chat.py https://<your-render-backend>
```

## 2) Baseline Smoke Tests

Send these first:
1. `Hi, what can you help me with for AgencyClaw?`
2. `List the clients you can access.`
3. `Show me brands for <TEST_CLIENT>.`

Expected:
- No repeated generic fallback.
- Responses should vary naturally and include concrete data.

## 3) SOP + Task-Brief Tests

1. `Find our SOP for launching an Amazon coupon for <TEST_BRAND>. Summarize it in 5 bullets.`
2. `Now draft a task title and description for that SOP for <TEST_CLIENT>. Do not execute yet.`
3. `What info is missing before this task is execution-ready?`

Expected:
- SOP-aware summary (not hallucinated process text).
- Draft contains structured, usable steps.
- Missing-data questions should be explicit (owner, ASINs/SKUs, discount terms, dates).

## 4) Meeting-Notes Extraction Test

Paste contents of `docs/agencyclaw/current/31_agencyclaw_test_meeting_fixture.md` as one message (under 2000 chars), then send:

`Please convert this into the top 4 tasks, map SOPs, and present draft tasks for approval only.`

Expected:
- Extracted tasks map to meeting decisions.
- Suggested SOP linkage where available.
- No direct mutation unless explicitly requested and confirmed.

## 5) Team-User (Novice) Tests

1. `I am not sure how to launch this campaign safely. What should I do first?`
2. `Can you walk me through this as if I am new, then draft the task for me?`
3. `I only know the brand name <TEST_BRAND>. Please figure out the rest and ask me only what is missing.`

Expected:
- Coaching tone + clear next step.
- Natural clarification instead of rigid command-menu behavior.
- Uses context skills before asking unnecessary follow-ups.

## 6) Mutation Tests (Test Space Only)

1. `Create this task in ClickUp for <TEST_CLIENT>: Launch coupon promo for <TEST_BRAND> with SOP-aligned checklist.`
2. Confirm with natural language: `Yes, create it.`
3. Retry replay safety: send `Yes, create it.` again.

Expected:
- One task creation path with confirmation.
- No duplicate creates from repeated confirmation.
- Response includes destination/task link details.

## 7) Planner / Complex-Request Tests

1. `Audit brand mappings for <TEST_CLIENT>, identify issues, and propose exact updates before executing anything.`
2. `Plan this work across two sprints and show open questions.`

Expected:
- Main agent remains user voice.
- Planner-style report includes actions/evidence/open questions/confidence.
- Mutations should be proposed, not silently executed.

## 8) Failure Triage Signals

If you repeatedly get `I hit an issue while processing that. Could you rephrase and try again?`:
1. Check Render logs for traceback around `/api/slack/debug/chat`.
2. Run SQL checks from `docs/agencyclaw/current/32_agencyclaw_supabase_debug_queries.sql`.
3. Confirm `AGENCYCLAW_AGENT_LOOP_ENABLED=true` on backend.
4. Confirm request payload text length is <= 2000 chars.

## 9) Pass/Fail Gate

Minimum pass before wider use:
- Baseline smoke passes.
- SOP + meeting-notes tasks draft correctly.
- Client/brand resolution is correct for test entities.
- Mutation confirmation and idempotency behave correctly.
- No repeated generic fallback across the core test set.
