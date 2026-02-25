from __future__ import annotations

import pytest

from app.services.theclaw.openai_client import OpenAIError
from app.services.theclaw.slack_minimal_runtime import (
    _apply_mutation_disclaimer,
    _build_meeting_task_system_prompt,
    _build_system_prompt,
    _is_meeting_to_task_request,
    _is_mutation_request,
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


def test_build_system_prompt_contains_phase1_behavior_contract():
    prompt = _build_system_prompt().lower()
    assert "cannot execute system actions" in prompt
    assert "clarifying questions" in prompt
    assert "plain numbered format" in prompt


def test_build_meeting_task_prompt_contains_draft_contract():
    prompt = _build_meeting_task_system_prompt().lower()
    assert "draft tasks (not executed)" in prompt
    assert "title:" in prompt
    assert "why this matters:" in prompt
    assert "needs clarification?:" in prompt


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Here are my meeting notes summary. Please draft task action items.\n- owner: TBD\n- due: TBD\n",
            True,
        ),
        (
            "I had a meeting and pasted notes below. Please create task action items.\n"
            + ("line\n" * 120),
            True,
        ),
        (
            "meeting notes summary with action items and next steps:\n"
            + ("line\n" * 80),
            True,
        ),
        ("Give me five task ideas for PPC.", False),
    ],
)
def test_is_meeting_to_task_request(text: str, expected: bool):
    assert _is_meeting_to_task_request(text) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("create a clickup task for test space", True),
        ("send this follow-up email", True),
        ("give me five ppc action items", False),
    ],
)
def test_is_mutation_request(text: str, expected: bool):
    assert _is_mutation_request(text) is expected


def test_apply_mutation_disclaimer_prepends_for_mutation_requests():
    output = _apply_mutation_disclaimer(
        user_text="create a clickup task for this",
        reply_text="Here is a suggested draft task.",
    )
    assert output.startswith("I can draft and advise")
    assert "suggested draft task" in output


def test_apply_mutation_disclaimer_respects_existing_limitation_language():
    output = _apply_mutation_disclaimer(
        user_text="create a clickup task for this",
        reply_text="I cannot execute actions yet, but here is the draft.",
    )
    assert output == "I cannot execute actions yet, but here is the draft."


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
async def test_run_theclaw_minimal_dm_turn_forces_mutation_disclaimer(monkeypatch):
    fake_slack = _FakeSlackService()

    async def _fake_call_chat_completion(**kwargs):
        return {
            "content": "Task created successfully.",
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

    await run_theclaw_minimal_dm_turn(
        slack_user_id="U3",
        channel="D3",
        text="create a clickup task in test space",
    )

    assert len(fake_slack.messages) == 1
    assert fake_slack.messages[0]["channel"] == "D3"
    assert "cannot execute actions" in fake_slack.messages[0]["text"].lower()


@pytest.mark.asyncio
async def test_run_theclaw_minimal_dm_turn_uses_meeting_prompt_when_detected(monkeypatch):
    fake_slack = _FakeSlackService()
    captured: dict[str, object] = {}

    async def _fake_call_chat_completion(**kwargs):
        captured.update(kwargs)
        return {
            "content": "Draft tasks (not executed):\n1. Title: ...",
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

    await run_theclaw_minimal_dm_turn(
        slack_user_id="U4",
        channel="D4",
        text="meeting notes summary with action items and next steps:\n" + ("line\n" * 80),
    )

    messages = captured["messages"]
    assert isinstance(messages, list)
    assert "draft tasks (not executed)" in messages[0]["content"].lower()


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
