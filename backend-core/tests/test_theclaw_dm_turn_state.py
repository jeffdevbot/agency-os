from __future__ import annotations

import pytest

from app.services.theclaw.slack_minimal_runtime import run_theclaw_minimal_dm_turn

from .theclaw_runtime_test_fakes import FakeSession, FakeSessionService, FakeSlackService


@pytest.mark.asyncio
async def test_run_theclaw_minimal_dm_turn_persists_entity_resolved_context(monkeypatch):
    fake_slack = FakeSlackService()
    fake_session_service = FakeSessionService()
    call_count = 0

    async def _fake_call_chat_completion(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {
                "content": '{"skill_id":"none","confidence":0.9,"reason":"general"}',
                "tokens_in": 10,
                "tokens_out": 11,
                "tokens_total": 21,
                "model": "gpt-4o-mini",
                "duration_ms": 5,
            }
        return {
            "content": (
                "Resolved Context\n"
                "Client: Whoosh\n"
                "---THECLAW_STATE_JSON---\n"
                '{"context_updates":{"theclaw_resolved_context_v1":{"client":"Whoosh","brand":"Whoosh","clickup_space":"Whoosh","market_scope":"CA","confidence":"high","notes":"from thread"}}}\n'
                "---END_THECLAW_STATE_JSON---"
            ),
            "tokens_in": 10,
            "tokens_out": 11,
            "tokens_total": 21,
            "model": "gpt-4o-mini",
            "duration_ms": 5,
        }

    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)

    await run_theclaw_minimal_dm_turn(slack_user_id="U11", channel="D11", text="create task for whoosh ca")

    assert len(fake_session_service.updated) == 1
    _, updates = fake_session_service.updated[0]
    assert "theclaw_resolved_context_v1" in updates
    assert updates["theclaw_resolved_context_v1"]["client"] == "Whoosh"
    assert updates["theclaw_resolved_context_v1"]["market_scope"] == "CA"


@pytest.mark.asyncio
async def test_run_theclaw_minimal_dm_turn_persists_draft_tasks_with_runtime_id(monkeypatch):
    fake_slack = FakeSlackService()
    fake_session_service = FakeSessionService()
    call_count = 0

    async def _fake_call_chat_completion(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {
                "content": '{"skill_id":"task_extraction","confidence":0.93,"reason":"source material"}',
                "tokens_in": 10,
                "tokens_out": 11,
                "tokens_total": 21,
                "model": "gpt-4o-mini",
                "duration_ms": 5,
            }
        return {
            "content": (
                "Internal ClickUp Tasks (Agency)\n"
                "Task 1: Launch campaign\n\n"
                "---THECLAW_STATE_JSON---\n"
                '{"context_updates":{"theclaw_draft_tasks_v1":[{"title":"Launch campaign","source":"meeting_notes","status":"draft","asin_list":["B0ABC"]}]}}\n'
                "---END_THECLAW_STATE_JSON---"
            ),
            "tokens_in": 10,
            "tokens_out": 11,
            "tokens_total": 21,
            "model": "gpt-4o-mini",
            "duration_ms": 5,
        }

    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)

    await run_theclaw_minimal_dm_turn(slack_user_id="U13", channel="D13", text="extract tasks from this email")

    assert len(fake_session_service.updated) == 1
    _, updates = fake_session_service.updated[0]
    tasks = updates["theclaw_draft_tasks_v1"]
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Launch campaign"
    assert tasks[0]["id"]
    assert tasks[0]["id"] != "fake-model-id"


@pytest.mark.asyncio
async def test_run_theclaw_minimal_dm_turn_preserves_existing_resolved_context_when_no_state_block(monkeypatch):
    fake_slack = FakeSlackService()
    fake_session = FakeSession(
        context={
            "theclaw_resolved_context_v1": {
                "client": "Whoosh",
                "brand": "Whoosh",
                "clickup_space": "Whoosh",
                "market_scope": "CA",
                "confidence": "high",
                "notes": "existing",
            }
        }
    )
    fake_session_service = FakeSessionService(session=fake_session)
    call_count = 0

    async def _fake_call_chat_completion(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {
                "content": '{"skill_id":"entity_resolver","confidence":0.91,"reason":"entity clarification"}',
                "tokens_in": 10,
                "tokens_out": 10,
                "tokens_total": 20,
                "model": "gpt-4o-mini",
                "duration_ms": 5,
            }
        return {
            "content": "Which Whoosh do you mean?",
            "tokens_in": 10,
            "tokens_out": 10,
            "tokens_total": 20,
            "model": "gpt-4o-mini",
            "duration_ms": 5,
        }

    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)

    await run_theclaw_minimal_dm_turn(slack_user_id="U14", channel="D14", text="create task for whoosh")

    assert len(fake_session_service.updated) == 1
    _, updates = fake_session_service.updated[0]
    assert "theclaw_resolved_context_v1" not in updates
    assert fake_session.context["theclaw_resolved_context_v1"]["client"] == "Whoosh"


@pytest.mark.asyncio
async def test_run_theclaw_minimal_dm_turn_pending_confirmation_yes_clears_pending_without_openai(monkeypatch):
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

    await run_theclaw_minimal_dm_turn(slack_user_id="U20", channel="D20", text="yes")

    assert len(fake_slack.messages) == 1
    assert "cannot execute clickup task creation yet" in fake_slack.messages[0]["text"].lower()
    assert "launch campaign" in fake_slack.messages[0]["text"].lower()
    assert len(fake_session_service.updated) == 1
    _, updates = fake_session_service.updated[0]
    assert updates["theclaw_pending_confirmation_v1"] is None


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
