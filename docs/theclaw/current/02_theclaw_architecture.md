# 02 - The Claw Architecture (Reboot)

Status: draft
Last updated: 2026-02-25

## 1) Purpose

Define the rebooted Slack assistant architecture so new contributors can understand runtime boundaries quickly.

## 1A) Terminology

- Canonical term: **skill**
- Avoid using "tool" for runtime capabilities in The Claw docs/code comments.
- A skill may call one or more specialist subagents internally.

## 2) Runtime Entry Points

- FastAPI app bootstrap: `backend-core/app/main.py`
- Slack router: `backend-core/app/api/routes/slack.py`
- Phase-1 minimal runtime: `backend-core/app/services/theclaw/slack_minimal_runtime.py`

## 3) Route Contract (Stable Surface)

- `POST /api/slack/events`
- `POST /api/slack/interactions`

The external Slack endpoint contract remains stable while internals are replaced.

## 4) Phase-1 Internal Flow

1. Slack event request is verified and parsed.
2. DM events dispatch to `_handle_dm_event`.
3. Route uses The Claw minimal runtime.
4. Minimal runtime calls OpenAI chat completion.
5. Reply is posted to Slack DM.

In minimal mode:
- advisory-only behavior,
- no task mutation,
- no SOP/client context machinery.

## 5) Runtime Strategy

- The Claw minimal runtime is the default Slack runtime path.
- Legacy AgencyClaw runtime fallback is removed from route wiring.

## 6) Current Module Boundaries

- The Claw modules (new):
  - `app/services/theclaw/openai_client.py`
  - `app/services/theclaw/slack_minimal_runtime.py`

- Legacy modules (to delete after replacement):
  - `app/services/agencyclaw/*`
  - legacy tests under `backend-core/tests/test_c*` and other AgencyClaw-specific suites

## 7) Testing Gates

For each migration chunk:
1. targeted tests for changed modules,
2. full backend suite,
3. manual Slack DM smoke check.

## 8) Planned Evolution

- Phase 2: meeting notes -> draft tasks (no writes)
- Phase 3: one-by-one confirmed task creation
- Phase 4: follow-up email draft
- Phase 5: legacy AgencyClaw deletion + identity sync removal
