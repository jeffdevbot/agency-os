from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.agencyclaw.agent_loop_runtime import run_reply_only_agent_loop_turn


class _FakeSlack:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    async def post_message(self, *, channel: str, text: str, blocks=None) -> None:
        self.messages.append({"channel": channel, "text": text})


class _FakeSession:
    def __init__(self, session_id: str = "sess-1") -> None:
        self.id = session_id
        self.context = {}


@pytest.mark.asyncio
async def test_reply_only_runtime_logs_and_completes(monkeypatch):
    calls: list[tuple[str, tuple, dict]] = []

    class FakeStore:
        def __init__(self, _db):
            pass

        def list_recent_run_messages(self, run_id: str, limit: int = 20):
            assert run_id == "run-1"
            assert limit == 20
            return [{"role": "user", "content": {"text": "hello"}, "created_at": "2026-01-01T00:00:00Z"}]

    class FakeTurnLogger:
        def __init__(self, _store):
            pass

        def start_main_run(self, session_id: str):
            calls.append(("start_main_run", (session_id,), {}))
            return {"id": "run-1", "status": "running"}

        def log_user_message(self, run_id: str, text: str):
            calls.append(("log_user_message", (run_id, text), {}))
            return {"id": "m1"}

        def log_assistant_message(self, run_id: str, text: str):
            calls.append(("log_assistant_message", (run_id, text), {}))
            return {"id": "m2"}

        def complete_run(self, run_id: str, status: str):
            calls.append(("complete_run", (run_id, status), {}))
            return None

    async def _fake_completion(*args, **kwargs):
        return {
            "content": "Agent reply",
            "tokens_in": 10,
            "tokens_out": 5,
            "tokens_total": 15,
            "model": "gpt-4o-mini",
            "duration_ms": 10,
        }

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="hello",
        session=_FakeSession(),
        slack_user_id="U123",
        session_service=MagicMock(),
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        call_chat_completion_fn=_fake_completion,
    )

    assert handled is True
    assert slack.messages == [{"channel": "D1", "text": "Agent reply"}]
    assert ("start_main_run", ("sess-1",), {}) in calls
    assert ("log_user_message", ("run-1", "hello"), {}) in calls
    assert ("log_assistant_message", ("run-1", "Agent reply"), {}) in calls
    assert ("complete_run", ("run-1", "completed"), {}) in calls


@pytest.mark.asyncio
async def test_reply_only_runtime_failure_marks_failed_and_posts_fallback(monkeypatch):
    calls: list[tuple[str, tuple, dict]] = []

    class FakeStore:
        def __init__(self, _db):
            pass

        def list_recent_run_messages(self, run_id: str, limit: int = 20):
            return [{"role": "user", "content": {"text": "hello"}, "created_at": "2026-01-01T00:00:00Z"}]

    class FakeTurnLogger:
        def __init__(self, _store):
            pass

        def start_main_run(self, session_id: str):
            return {"id": "run-1", "status": "running"}

        def log_user_message(self, run_id: str, text: str):
            return {"id": "m1"}

        def log_assistant_message(self, run_id: str, text: str):
            calls.append(("log_assistant_message", (run_id, text), {}))
            return {"id": "m2"}

        def complete_run(self, run_id: str, status: str):
            calls.append(("complete_run", (run_id, status), {}))
            return None

    async def _failing_completion(*args, **kwargs):
        raise RuntimeError("LLM down")

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="hello",
        session=_FakeSession(),
        slack_user_id="U123",
        session_service=MagicMock(),
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        call_chat_completion_fn=_failing_completion,
    )

    assert handled is True
    assert len(slack.messages) == 1
    assert "issue" in slack.messages[0]["text"].lower()
    assert ("complete_run", ("run-1", "failed"), {}) in calls
    assert not any(name == "log_assistant_message" for name, _, _ in calls)
