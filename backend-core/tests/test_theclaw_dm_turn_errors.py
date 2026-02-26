from __future__ import annotations

import pytest

from app.services.theclaw.openai_client import OpenAIError
from app.services.theclaw.slack_minimal_runtime import (
    handle_theclaw_minimal_interaction,
    run_theclaw_minimal_dm_turn,
)

from .theclaw_runtime_test_fakes import FakeSessionService, FakeSlackService


@pytest.mark.asyncio
async def test_run_theclaw_minimal_dm_turn_forces_mutation_disclaimer(monkeypatch):
    fake_slack = FakeSlackService()
    fake_session_service = FakeSessionService()
    call_count = 0

    async def _fake_call_chat_completion(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {
                "content": '{"skill_id":"none","confidence":0.8,"reason":"general"}',
                "tokens_in": 10,
                "tokens_out": 11,
                "tokens_total": 21,
                "model": "gpt-4o-mini",
                "duration_ms": 5,
            }
        return {
            "content": "Task created successfully.",
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
        slack_user_id="U3",
        channel="D3",
        text="create a clickup task in test space",
    )

    assert len(fake_slack.messages) == 1
    assert fake_slack.messages[0]["channel"] == "D3"
    assert "cannot execute actions" in fake_slack.messages[0]["text"].lower()


@pytest.mark.asyncio
async def test_run_theclaw_minimal_dm_turn_skill_selection_error_falls_back_to_no_skill(monkeypatch):
    fake_slack = FakeSlackService()
    fake_session_service = FakeSessionService()
    call_count = 0

    async def _fake_call_chat_completion(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise OpenAIError("router boom")
        return {
            "content": "Router failed but assistant still replied.",
            "tokens_in": 10,
            "tokens_out": 11,
            "tokens_total": 21,
            "model": "gpt-4o-mini",
            "duration_ms": 5,
        }

    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)

    await run_theclaw_minimal_dm_turn(slack_user_id="U5", channel="D5", text="hello")

    assert fake_slack.messages == [{"channel": "D5", "text": "Router failed but assistant still replied."}]


@pytest.mark.asyncio
async def test_run_theclaw_minimal_dm_turn_openai_error_posts_fallback(monkeypatch):
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
        raise OpenAIError("boom")

    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)

    await run_theclaw_minimal_dm_turn(slack_user_id="U2", channel="D2", text="hello")

    assert len(fake_slack.messages) == 1
    assert fake_slack.messages[0]["channel"] == "D2"
    assert "temporary issue" in fake_slack.messages[0]["text"].lower()
    assert fake_slack.closed is True


@pytest.mark.asyncio
async def test_handle_theclaw_minimal_interaction_is_noop():
    await handle_theclaw_minimal_interaction(payload={"type": "block_actions"})
