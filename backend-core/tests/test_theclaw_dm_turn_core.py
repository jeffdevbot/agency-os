from __future__ import annotations

import pytest

from app.services.theclaw.slack_minimal_runtime import run_theclaw_minimal_dm_turn

from .theclaw_runtime_test_fakes import FakeSession, FakeSessionService, FakeSlackService


@pytest.mark.asyncio
async def test_run_theclaw_minimal_dm_turn_posts_model_reply(monkeypatch):
    fake_slack = FakeSlackService()
    fake_session_service = FakeSessionService()
    calls: list[dict[str, object]] = []

    async def _fake_call_chat_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return {
                "content": '{"skill_id":"none","confidence":0.92,"reason":"general chat"}',
                "tokens_in": 10,
                "tokens_out": 11,
                "tokens_total": 21,
                "model": "gpt-4o-mini",
                "duration_ms": 5,
            }
        return {
            "content": "Reply from The Claw",
            "tokens_in": 10,
            "tokens_out": 11,
            "tokens_total": 21,
            "model": "gpt-4o-mini",
            "duration_ms": 5,
        }

    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)

    await run_theclaw_minimal_dm_turn(slack_user_id="U1", channel="D1", text="Help me with amazon ads")

    assert len(calls) == 2
    assert calls[0]["temperature"] == 0.0
    assert calls[0]["max_tokens"] == 160
    assert "<available_skills>" in calls[0]["messages"][0]["content"]
    assert calls[1]["temperature"] == 0.2
    assert calls[1]["max_tokens"] == 1600
    messages = calls[1]["messages"]
    assert isinstance(messages, list)
    assert len(messages) == 2
    assert messages[1]["content"] == "Help me with amazon ads"
    assert fake_slack.messages == [{"channel": "D1", "text": "Reply from The Claw"}]
    assert fake_slack.closed is True
    assert len(fake_session_service.updated) == 1
    session_id, updates = fake_session_service.updated[0]
    assert session_id == "S1"
    assert "theclaw_history_v1" in updates
    assert len(updates["theclaw_history_v1"]) == 2


@pytest.mark.asyncio
async def test_run_theclaw_minimal_dm_turn_new_session_command_clears_context(monkeypatch):
    fake_slack = FakeSlackService()
    fake_session_service = FakeSessionService()

    async def _fake_call_chat_completion(**kwargs):
        raise AssertionError("OpenAI should not be called for new session")

    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)

    await run_theclaw_minimal_dm_turn(slack_user_id="U9", channel="D9", text="new session")

    assert fake_session_service.cleared_users == ["U9"]
    assert fake_slack.messages == [
        {"channel": "D9", "text": "Started a new session. I cleared prior conversation context."}
    ]
    assert fake_slack.closed is True


@pytest.mark.asyncio
async def test_run_theclaw_minimal_dm_turn_includes_prior_history_messages(monkeypatch):
    fake_slack = FakeSlackService()
    fake_session = FakeSession(
        context={
            "theclaw_history_v1": [
                {"role": "user", "content": "Client is TestBrand."},
                {"role": "assistant", "content": "Got it."},
            ]
        }
    )
    fake_session_service = FakeSessionService(session=fake_session)
    calls: list[dict[str, object]] = []

    async def _fake_call_chat_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return {
                "content": '{"skill_id":"none","confidence":0.7,"reason":"general"}',
                "tokens_in": 10,
                "tokens_out": 11,
                "tokens_total": 21,
                "model": "gpt-4o-mini",
                "duration_ms": 5,
            }
        return {
            "content": "Using prior context now.",
            "tokens_in": 10,
            "tokens_out": 11,
            "tokens_total": 21,
            "model": "gpt-4o-mini",
            "duration_ms": 5,
        }

    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)

    await run_theclaw_minimal_dm_turn(slack_user_id="U10", channel="D10", text="What should I do next?")

    messages = calls[1]["messages"]
    assert isinstance(messages, list)
    assert messages[1] == {"role": "user", "content": "Client is TestBrand."}
    assert messages[2] == {"role": "assistant", "content": "Got it."}


@pytest.mark.asyncio
async def test_run_theclaw_minimal_dm_turn_uses_selected_skill_prompt(monkeypatch):
    fake_slack = FakeSlackService()
    fake_session = FakeSession(
        context={
            "theclaw_draft_tasks_v1": [
                {"id": "task-123", "title": "Launch campaign", "source": "meeting_notes", "status": "draft"}
            ]
        }
    )
    fake_session_service = FakeSessionService(session=fake_session)
    calls: list[dict[str, object]] = []

    async def _fake_call_chat_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return {
                "content": '{"skill_id":"task_extraction","confidence":0.93,"reason":"meeting recap"}',
                "tokens_in": 10,
                "tokens_out": 11,
                "tokens_total": 21,
                "model": "gpt-4o-mini",
                "duration_ms": 5,
            }
        return {
            "content": "The Claw: Task Extraction\nInternal ClickUp Tasks (Agency)\nTask 1: ...",
            "tokens_in": 10,
            "tokens_out": 11,
            "tokens_total": 21,
            "model": "gpt-4o-mini",
            "duration_ms": 5,
        }

    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)

    await run_theclaw_minimal_dm_turn(
        slack_user_id="U4",
        channel="D4",
        text="meeting notes summary with action items and next steps:\n" + ("line\n" * 80),
    )

    response_prompt = calls[1]["messages"][0]["content"].lower()
    assert "executing skill 'task extraction'" in response_prompt
    assert "internal clickup tasks (agency)" in response_prompt
    assert "existing draft tasks context for id preservation" in response_prompt
    assert '"id":"task-123"' in response_prompt


@pytest.mark.asyncio
async def test_run_theclaw_minimal_dm_turn_injects_resolved_context_into_system_prompt(monkeypatch):
    fake_slack = FakeSlackService()
    fake_session = FakeSession(
        context={
            "theclaw_resolved_context_v1": {
                "client": "Whoosh",
                "brand": "Whoosh",
                "clickup_space": "Whoosh",
                "market_scope": "CA",
                "confidence": "high",
                "notes": "explicit",
            }
        }
    )
    fake_session_service = FakeSessionService(session=fake_session)
    calls: list[dict[str, object]] = []

    async def _fake_call_chat_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return {
                "content": '{"skill_id":"none","confidence":0.9,"reason":"general"}',
                "tokens_in": 10,
                "tokens_out": 10,
                "tokens_total": 20,
                "model": "gpt-4o-mini",
                "duration_ms": 5,
            }
        return {
            "content": "Here is my answer.",
            "tokens_in": 10,
            "tokens_out": 10,
            "tokens_total": 20,
            "model": "gpt-4o-mini",
            "duration_ms": 5,
        }

    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)

    await run_theclaw_minimal_dm_turn(slack_user_id="U12", channel="D12", text="what should I focus on?")

    system_prompt = calls[1]["messages"][0]["content"]
    assert "Active context:" in system_prompt
    assert "Client: Whoosh" in system_prompt
    assert "Market: CA" in system_prompt
