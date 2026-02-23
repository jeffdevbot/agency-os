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
async def test_skill_call_clickup_task_list_round_trip_logs_events(monkeypatch):
    calls: list[tuple[str, tuple]] = []

    class FakeStore:
        def __init__(self, _db):
            pass

        def list_recent_run_messages(self, run_id: str, limit: int = 20):
            return [{"role": "user", "content": {"text": "show tasks"}, "created_at": "2026-01-01T00:00:00Z"}]

    class FakeTurnLogger:
        def __init__(self, _store):
            pass

        def start_main_run(self, session_id: str):
            return {"id": "run-1", "status": "running"}

        def log_user_message(self, run_id: str, text: str):
            calls.append(("log_user_message", (run_id, text)))
            return {"id": "m1"}

        def log_skill_call(self, run_id: str, skill_id: str, payload: dict):
            calls.append(("log_skill_call", (run_id, skill_id, payload)))
            return {"id": "e1"}

        def log_skill_result(self, run_id: str, skill_id: str, payload: dict):
            calls.append(("log_skill_result", (run_id, skill_id, payload)))
            return {"id": "e2"}

        def log_assistant_message(self, run_id: str, text: str):
            calls.append(("log_assistant_message", (run_id, text)))
            return {"id": "m2"}

        def complete_run(self, run_id: str, status: str):
            calls.append(("complete_run", (run_id, status)))
            return None

    completions = iter(
        [
            {
                "content": '{"mode":"tool_call","skill_id":"clickup_task_list","args":{"client_name":"Distex"}}',
                "tokens_in": 10,
                "tokens_out": 5,
                "tokens_total": 15,
                "model": "gpt-4o-mini",
                "duration_ms": 10,
            },
            {
                "content": '{"mode":"reply","text":"Here are your tasks for Distex."}',
                "tokens_in": 12,
                "tokens_out": 7,
                "tokens_total": 19,
                "model": "gpt-4o-mini",
                "duration_ms": 12,
            },
        ]
    )

    async def _fake_completion(*args, **kwargs):
        _ = args, kwargs
        return next(completions)

    executed: list[dict] = []

    async def _execute_task_list(**kwargs):
        executed.append(kwargs["args"])
        return {"response_text": "Task A, Task B"}

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="show tasks for Distex",
        session=_FakeSession(),
        slack_user_id="U123",
        session_service=MagicMock(),
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        execute_task_list_fn=_execute_task_list,
        call_chat_completion_fn=_fake_completion,
    )

    assert handled is True
    assert executed == [{"client_name": "Distex"}]
    assert slack.messages == [{"channel": "D1", "text": "Here are your tasks for Distex."}]
    assert ("log_skill_call", ("run-1", "clickup_task_list", {"client_name": "Distex"})) in calls
    assert ("log_skill_result", ("run-1", "clickup_task_list", {"response_text": "Task A, Task B"})) in calls
    assert ("complete_run", ("run-1", "completed")) in calls


@pytest.mark.asyncio
async def test_disallowed_skill_id_falls_back_and_marks_failed(monkeypatch):
    calls: list[tuple[str, tuple]] = []

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

        def complete_run(self, run_id: str, status: str):
            calls.append(("complete_run", (run_id, status)))
            return None

    async def _fake_completion(*args, **kwargs):
        _ = args, kwargs
        return {
            "content": '{"mode":"tool_call","skill_id":"clickup_task_create","args":{"task_title":"x"}}',
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
        text="create a task",
        session=_FakeSession(),
        slack_user_id="U123",
        session_service=MagicMock(),
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        call_chat_completion_fn=_fake_completion,
        execute_task_list_fn=None,
    )

    assert handled is True
    assert len(slack.messages) == 1
    assert "issue" in slack.messages[0]["text"].lower()
    assert ("complete_run", ("run-1", "failed")) in calls


@pytest.mark.asyncio
async def test_tool_execution_exception_falls_back_and_marks_failed(monkeypatch):
    calls: list[tuple[str, tuple]] = []

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
            calls.append(("log_skill_call", (run_id, skill_id, payload)))
            return {"id": "e1"}

        def complete_run(self, run_id: str, status: str):
            calls.append(("complete_run", (run_id, status)))
            return None

    async def _fake_completion(*args, **kwargs):
        _ = args, kwargs
        return {
            "content": '{"mode":"tool_call","skill_id":"clickup_task_list","args":{"client_name":"Distex"}}',
            "tokens_in": 10,
            "tokens_out": 5,
            "tokens_total": 15,
            "model": "gpt-4o-mini",
            "duration_ms": 10,
        }

    async def _raise_tool(**kwargs):
        _ = kwargs
        raise RuntimeError("clickup down")

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="show tasks",
        session=_FakeSession(),
        slack_user_id="U123",
        session_service=MagicMock(),
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        call_chat_completion_fn=_fake_completion,
        execute_task_list_fn=_raise_tool,
    )

    assert handled is True
    assert len(slack.messages) == 1
    assert "issue" in slack.messages[0]["text"].lower()
    assert ("log_skill_call", ("run-1", "clickup_task_list", {"client_name": "Distex"})) in calls
    assert ("complete_run", ("run-1", "failed")) in calls
