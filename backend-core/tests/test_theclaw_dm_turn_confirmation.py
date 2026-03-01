from __future__ import annotations

import pytest

from app.services.theclaw.slack_minimal_runtime import run_theclaw_minimal_dm_turn

from .theclaw_runtime_test_fakes import FakeSession, FakeSessionService, FakeSlackService


@pytest.mark.asyncio
async def test_run_theclaw_minimal_dm_turn_pending_confirmation_yes_calls_execution(monkeypatch):
    """YES with pending confirmation calls execute_confirmed_task_creation, not OpenAI."""
    from app.services.theclaw.clickup_execution import ClickUpExecutionResult

    fake_slack = FakeSlackService()
    fake_session = FakeSession(
        context={
            "theclaw_pending_confirmation_v1": {
                "task_id": "task-123",
                "task_title": "Launch campaign",
                "status": "pending",
            },
            "theclaw_draft_tasks_v1": [
                {"id": "task-123", "title": "Launch campaign", "status": "draft"},
            ],
        }
    )
    fake_session_service = FakeSessionService(session=fake_session)

    async def _fake_call_chat_completion(**kwargs):
        raise AssertionError("OpenAI should not be called when pending confirmation is active")

    execution_calls = []

    async def _fake_execute(*, session_context, pending_confirmation):
        execution_calls.append((session_context, pending_confirmation))
        return (
            ClickUpExecutionResult(
                success=True,
                clickup_task_id="cu_42",
                clickup_task_url="https://app.clickup.com/t/cu_42",
            ),
            {"theclaw_pending_confirmation_v1": None},
        )

    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)
    monkeypatch.setattr("app.services.theclaw.pending_confirmation_runtime.execute_confirmed_task_creation", _fake_execute)

    await run_theclaw_minimal_dm_turn(slack_user_id="U20", channel="D20", text="yes")

    assert len(execution_calls) == 1
    assert len(fake_slack.messages) == 1
    assert "created" in fake_slack.messages[0]["text"].lower()
    assert "cu_42" in fake_slack.messages[0]["text"]
    assert len(fake_session_service.updated) == 1
    _, updates = fake_session_service.updated[0]
    assert updates["theclaw_pending_confirmation_v1"] is None


@pytest.mark.asyncio
async def test_run_theclaw_minimal_dm_turn_pending_confirmation_yes_failure_shows_error(monkeypatch):
    """YES with execution failure returns the error message and keeps pending if transient."""
    from app.services.theclaw.clickup_execution import ClickUpExecutionResult

    fake_slack = FakeSlackService()
    fake_session = FakeSession(
        context={
            "theclaw_pending_confirmation_v1": {
                "task_id": "task-123",
                "task_title": "Launch campaign",
                "status": "pending",
            },
            "theclaw_draft_tasks_v1": [
                {"id": "task-123", "title": "Launch campaign", "status": "draft"},
            ],
        }
    )
    fake_session_service = FakeSessionService(session=fake_session)

    async def _fake_call_chat_completion(**kwargs):
        raise AssertionError("OpenAI should not be called when pending confirmation is active")

    async def _fake_execute(*, session_context, pending_confirmation):
        return (
            ClickUpExecutionResult(
                success=False,
                error_message="ClickUp task creation failed: 500. Say 'yes' to retry.",
            ),
            {},  # Pending kept for retry.
        )

    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)
    monkeypatch.setattr("app.services.theclaw.pending_confirmation_runtime.execute_confirmed_task_creation", _fake_execute)

    await run_theclaw_minimal_dm_turn(slack_user_id="U20", channel="D20", text="yes")

    assert len(fake_slack.messages) == 1
    assert "retry" in fake_slack.messages[0]["text"].lower()
    _, updates = fake_session_service.updated[0]
    assert "theclaw_pending_confirmation_v1" not in updates


@pytest.mark.asyncio
async def test_run_theclaw_minimal_dm_turn_pending_confirmation_no_clears_pending_without_openai(monkeypatch):
    fake_slack = FakeSlackService()
    fake_session = FakeSession(
        context={
            "theclaw_pending_confirmation_v1": {
                "task_id": "task-123",
                "task_title": "Launch campaign",
                "status": "pending",
            }
        }
    )
    fake_session_service = FakeSessionService(session=fake_session)

    async def _fake_call_chat_completion(**kwargs):
        raise AssertionError("OpenAI should not be called when pending confirmation is active")

    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)

    await run_theclaw_minimal_dm_turn(slack_user_id="U21", channel="D21", text="no")

    assert len(fake_slack.messages) == 1
    assert "canceled pending creation" in fake_slack.messages[0]["text"].lower()
    assert len(fake_session_service.updated) == 1
    _, updates = fake_session_service.updated[0]
    assert updates["theclaw_pending_confirmation_v1"] is None


@pytest.mark.asyncio
async def test_run_theclaw_minimal_dm_turn_pending_confirmation_ambiguous_reprompts_without_openai(monkeypatch):
    fake_slack = FakeSlackService()
    fake_session = FakeSession(
        context={
            "theclaw_pending_confirmation_v1": {
                "task_id": "task-123",
                "task_title": "Launch campaign",
                "status": "pending",
            }
        }
    )
    fake_session_service = FakeSessionService(session=fake_session)

    async def _fake_call_chat_completion(**kwargs):
        raise AssertionError("OpenAI should not be called when pending confirmation is active")

    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)

    await run_theclaw_minimal_dm_turn(slack_user_id="U22", channel="D22", text="maybe")

    assert len(fake_slack.messages) == 1
    assert "pending confirmation for 'launch campaign'" in fake_slack.messages[0]["text"].lower()
    assert "reply with exactly 'yes' to proceed or 'no' to cancel" in fake_slack.messages[0]["text"].lower()
    assert len(fake_session_service.updated) == 1
    _, updates = fake_session_service.updated[0]
    assert "theclaw_pending_confirmation_v1" not in updates
