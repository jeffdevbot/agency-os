from __future__ import annotations

import pytest

from app.services.theclaw.openai_client import OpenAIError
from app.services.theclaw.slack_minimal_runtime import (
    handle_theclaw_minimal_interaction,
    run_theclaw_minimal_dm_turn,
)


class _FakeSlackService:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []
        self.closed = False

    async def post_message(self, *, channel: str, text: str) -> None:
        self.messages.append({"channel": channel, "text": text})

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_run_theclaw_minimal_dm_turn_posts_model_reply(monkeypatch):
    fake_slack = _FakeSlackService()
    captured: dict[str, object] = {}

    async def _fake_call_chat_completion(**kwargs):
        captured.update(kwargs)
        return {
            "content": "Reply from The Claw",
            "tokens_in": 10,
            "tokens_out": 11,
            "tokens_total": 21,
            "model": "gpt-4o-mini",
            "duration_ms": 5,
        }

    monkeypatch.setattr(
        "app.services.theclaw.slack_minimal_runtime.get_slack_service",
        lambda: fake_slack,
    )
    monkeypatch.setattr(
        "app.services.theclaw.slack_minimal_runtime.call_chat_completion",
        _fake_call_chat_completion,
    )

    await run_theclaw_minimal_dm_turn(slack_user_id="U1", channel="D1", text="Help me with amazon ads")

    assert captured["temperature"] == 0.2
    assert captured["max_tokens"] == 500
    messages = captured["messages"]
    assert isinstance(messages, list)
    assert len(messages) == 2
    assert messages[1]["content"] == "Help me with amazon ads"
    assert fake_slack.messages == [{"channel": "D1", "text": "Reply from The Claw"}]
    assert fake_slack.closed is True


@pytest.mark.asyncio
async def test_run_theclaw_minimal_dm_turn_openai_error_posts_fallback(monkeypatch):
    fake_slack = _FakeSlackService()

    async def _fake_call_chat_completion(**kwargs):
        raise OpenAIError("boom")

    monkeypatch.setattr(
        "app.services.theclaw.slack_minimal_runtime.get_slack_service",
        lambda: fake_slack,
    )
    monkeypatch.setattr(
        "app.services.theclaw.slack_minimal_runtime.call_chat_completion",
        _fake_call_chat_completion,
    )

    await run_theclaw_minimal_dm_turn(slack_user_id="U2", channel="D2", text="hello")

    assert len(fake_slack.messages) == 1
    assert fake_slack.messages[0]["channel"] == "D2"
    assert "temporary issue" in fake_slack.messages[0]["text"].lower()
    assert fake_slack.closed is True


@pytest.mark.asyncio
async def test_handle_theclaw_minimal_interaction_is_noop():
    await handle_theclaw_minimal_interaction(payload={"type": "block_actions"})
