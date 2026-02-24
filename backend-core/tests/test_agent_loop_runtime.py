from __future__ import annotations

from typing import Any
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
    assert "try again" in slack.messages[0]["text"].lower()
    assert ("complete_run", ("run-1", "completed"), {}) in calls
    assert any(name == "log_assistant_message" for name, _, _ in calls)


@pytest.mark.asyncio
async def test_main_agent_multi_turn_skill_chain_single_turn(monkeypatch):
    calls: list[tuple[str, tuple, dict]] = []

    class FakeStore:
        def __init__(self, _db):
            pass

        def list_recent_run_messages(self, run_id: str, limit: int = 20):
            return []

    class FakeTurnLogger:
        def __init__(self, _store):
            pass

        def start_main_run(self, session_id: str):
            return {"id": "run-1", "status": "running"}

        def log_user_message(self, run_id: str, text: str):
            return {"id": "m1"}

        def log_skill_call(self, run_id: str, skill_id: str, payload: dict):
            calls.append(("log_skill_call", (run_id, skill_id, payload), {}))
            return {"id": "e1"}

        def log_skill_result(self, run_id: str, skill_id: str, payload: dict):
            calls.append(("log_skill_result", (run_id, skill_id, payload), {}))
            return {"id": "e2"}

        def log_assistant_message(self, run_id: str, text: str):
            calls.append(("log_assistant_message", (run_id, text), {}))
            return {"id": "m2"}

        def complete_run(self, run_id: str, status: str):
            calls.append(("complete_run", (run_id, status), {}))
            return None

    completions = iter(
        [
            {
                "content": '{"mode":"tool_call","skill_id":"lookup_client","args":{"query":"dist"}}',
                "tokens_in": 10,
                "tokens_out": 5,
                "tokens_total": 15,
                "model": "gpt-4o-mini",
                "duration_ms": 10,
            },
            {
                "content": '{"mode":"tool_call","skill_id":"search_kb","args":{"query":"coupon setup"}}',
                "tokens_in": 10,
                "tokens_out": 5,
                "tokens_total": 15,
                "model": "gpt-4o-mini",
                "duration_ms": 10,
            },
            {
                "content": '{"mode":"reply","text":"Here is the combined answer."}',
                "tokens_in": 10,
                "tokens_out": 5,
                "tokens_total": 15,
                "model": "gpt-4o-mini",
                "duration_ms": 10,
            },
        ]
    )

    async def _fake_completion(*args, **kwargs):
        _ = args, kwargs
        return next(completions)

    async def _execute_read_skill(**kwargs):
        if kwargs["skill_id"] == "lookup_client":
            return {"response_text": "Clients: Distex"}
        if kwargs["skill_id"] == "search_kb":
            return {"response_text": "KB: coupon SOP"}
        raise AssertionError("unexpected skill")

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="help with distex coupons",
        session=_FakeSession(),
        slack_user_id="U123",
        session_service=MagicMock(),
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        execute_read_skill_fn=_execute_read_skill,
        call_chat_completion_fn=_fake_completion,
    )

    assert handled is True
    assert slack.messages == [{"channel": "D1", "text": "Here is the combined answer."}]
    assert ("log_skill_call", ("run-1", "lookup_client", {"query": "dist"}), {}) in calls
    assert ("log_skill_call", ("run-1", "search_kb", {"query": "coupon setup"}), {}) in calls
    assert ("complete_run", ("run-1", "completed"), {}) in calls


@pytest.mark.asyncio
async def test_delegate_planner_happy_path_creates_child_run_and_main_reply(monkeypatch):
    calls: list[tuple[str, tuple, dict]] = []
    prompts: list[list[dict[str, str]]] = []

    class FakeStore:
        def __init__(self, _db):
            pass

        def list_recent_run_messages(self, run_id: str, limit: int = 20):
            return []

        def list_recent_skill_events(self, run_id: str, limit: int = 20):
            return []

    class FakeTurnLogger:
        def __init__(self, _store):
            pass

        def start_main_run(self, session_id: str):
            calls.append(("start_main_run", (session_id,), {}))
            return {"id": "run-main", "status": "running"}

        def set_run_trace_id(self, run_id: str, trace_id: str):
            calls.append(("set_run_trace_id", (run_id, trace_id), {}))
            return None

        def start_planner_run(self, session_id: str, *, parent_run_id: str, trace_id: str):
            calls.append(("start_planner_run", (session_id,), {"parent_run_id": parent_run_id, "trace_id": trace_id}))
            return {"id": "run-child", "status": "running"}

        def log_user_message(self, run_id: str, text: str):
            calls.append(("log_user_message", (run_id, text), {}))
            return {"id": "m1"}

        def log_skill_call(self, run_id: str, skill_id: str, payload: dict):
            calls.append(("log_skill_call", (run_id, skill_id, payload), {}))
            return {"id": "e1"}

        def log_skill_result(self, run_id: str, skill_id: str, payload: dict):
            calls.append(("log_skill_result", (run_id, skill_id, payload), {}))
            return {"id": "e2"}

        def log_planner_report(self, run_id: str, report: dict[str, Any], summary: str | None = None):
            calls.append(("log_planner_report", (run_id, report), {"summary": summary}))
            return {"id": "m2"}

        def log_assistant_message(self, run_id: str, text: str):
            calls.append(("log_assistant_message", (run_id, text), {}))
            return {"id": "m3"}

        def complete_run(self, run_id: str, status: str):
            calls.append(("complete_run", (run_id, status), {}))
            return None

    completions = iter(
        [
            {
                "content": '{"mode":"tool_call","skill_id":"delegate_planner","args":{"request_text":"make a plan"}}',
                "tokens_in": 10,
                "tokens_out": 5,
                "tokens_total": 15,
                "model": "gpt-4o-mini",
                "duration_ms": 10,
            },
            {
                "content": '{"mode":"reply","text":"I planned this and here is the summary."}',
                "tokens_in": 12,
                "tokens_out": 7,
                "tokens_total": 19,
                "model": "gpt-4o-mini",
                "duration_ms": 12,
            },
        ]
    )

    async def _fake_completion(*args, **kwargs):
        prompts.append(args[0])
        _ = kwargs
        return next(completions)

    async def _delegate_planner(**kwargs):
        assert kwargs["request_text"] == "make a plan"
        assert kwargs["parent_run_id"] == "run-main"
        assert kwargs["child_run_id"] == "run-child"
        assert kwargs["trace_id"] == "run-main"
        assert kwargs.get("max_turns") == 6 or kwargs.get("max_planner_turns") == 6
        executor = kwargs.get("tool_executor") or kwargs.get("execute_skill_fn")
        assert callable(executor)
        blocked = await executor(skill_id="clickup_task_create", args={"task_title": "X"})
        assert blocked.get("blocked") is True
        assert blocked.get("mutation_proposals", [{}])[0].get("skill_id") == "clickup_task_create"
        return {
            "ok": True,
            "status": "completed",
            "request_text": kwargs["request_text"],
            "steps_succeeded": 2,
            "steps_attempted": 2,
        }

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="please plan this",
        session=_FakeSession(),
        slack_user_id="U123",
        session_service=MagicMock(),
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        execute_delegate_planner_fn=_delegate_planner,
        call_chat_completion_fn=_fake_completion,
    )

    assert handled is True
    assert slack.messages == [{"channel": "D1", "text": "I planned this and here is the summary."}]
    assert ("set_run_trace_id", ("run-main", "run-main"), {}) in calls
    assert ("start_planner_run", ("sess-1",), {"parent_run_id": "run-main", "trace_id": "run-main"}) in calls
    assert ("complete_run", ("run-child", "completed"), {}) in calls
    assert ("complete_run", ("run-main", "completed"), {}) in calls
    assert any(
        isinstance(msg, dict) and "Tool result for delegate_planner" in str(msg.get("content", ""))
        for msg in prompts[1]
    )


@pytest.mark.asyncio
async def test_delegate_planner_unavailable_returns_safe_reply_and_marks_child_blocked(monkeypatch):
    calls: list[tuple[str, tuple, dict]] = []

    class FakeStore:
        def __init__(self, _db):
            pass

        def list_recent_run_messages(self, run_id: str, limit: int = 20):
            return []

    class FakeTurnLogger:
        def __init__(self, _store):
            pass

        def start_main_run(self, session_id: str):
            return {"id": "run-main", "status": "running", "trace_id": "trace-1"}

        def start_planner_run(self, session_id: str, *, parent_run_id: str, trace_id: str):
            _ = session_id, parent_run_id, trace_id
            return {"id": "run-child", "status": "running"}

        def log_user_message(self, run_id: str, text: str):
            return {"id": "m1"}

        def log_skill_call(self, run_id: str, skill_id: str, payload: dict):
            _ = run_id, skill_id, payload
            return {"id": "e1"}

        def log_skill_result(self, run_id: str, skill_id: str, payload: dict):
            _ = run_id, skill_id, payload
            return {"id": "e2"}

        def log_planner_report(self, run_id: str, report: dict[str, Any], summary: str | None = None):
            _ = run_id, report, summary
            return {"id": "m2"}

        def log_assistant_message(self, run_id: str, text: str):
            calls.append(("log_assistant_message", (run_id, text), {}))
            return {"id": "m3"}

        def complete_run(self, run_id: str, status: str):
            calls.append(("complete_run", (run_id, status), {}))
            return None

    async def _fake_completion(*args, **kwargs):
        _ = args, kwargs
        return {
            "content": '{"mode":"tool_call","skill_id":"delegate_planner","args":{"request_text":"do planning"}}',
            "tokens_in": 10,
            "tokens_out": 5,
            "tokens_total": 15,
            "model": "gpt-4o-mini",
            "duration_ms": 10,
        }

    async def _delegate_planner(**kwargs):
        _ = kwargs
        return {
            "ok": False,
            "status": "blocked",
            "response_text": "I couldn't run planning right now. Could you try again?",
        }

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="plan it",
        session=_FakeSession(),
        slack_user_id="U123",
        session_service=MagicMock(),
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        execute_delegate_planner_fn=_delegate_planner,
        call_chat_completion_fn=_fake_completion,
    )

    assert handled is True
    assert slack.messages == [{"channel": "D1", "text": "I couldn't run planning right now. Could you try again?"}]
    assert ("complete_run", ("run-child", "blocked"), {}) in calls
    assert ("complete_run", ("run-main", "completed"), {}) in calls
