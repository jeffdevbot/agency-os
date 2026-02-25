from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.agencyclaw.agent_loop_runtime import run_reply_only_agent_loop_turn
from .agent_loop_runtime_test_fakes import (
    FakeSession as _FakeSession,
    FakeSessionService as _FakeSessionService,
    FakeSlack as _FakeSlack,
)


@pytest.mark.asyncio
async def test_natural_task_list_request_recovers_after_unusable_tool_loop(monkeypatch):
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
            return {"id": "e1"}

        def log_skill_result(self, run_id: str, skill_id: str, payload: dict):
            return {"id": "e2"}

        def log_assistant_message(self, run_id: str, text: str):
            return {"id": "m2"}

        def complete_run(self, run_id: str, status: str):
            return None

    async def _fake_completion(*args, **kwargs):
        _ = args, kwargs
        return {
            "content": '{"mode":"tool_call","skill_id":"unknown_tool","args":{}}',
            "tokens_in": 10,
            "tokens_out": 5,
            "tokens_total": 15,
            "model": "gpt-4o-mini",
            "duration_ms": 10,
        }

    executed: list[tuple[str, dict]] = []

    async def _execute_read_skill(**kwargs):
        executed.append((kwargs["skill_id"], kwargs["args"]))
        return {"response_text": "Recovered task list response."}

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    session = _FakeSession()
    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="For Distex, what are the top 5 tasks due this week?",
        session=session,
        slack_user_id="U123",
        session_service=_FakeSessionService(session),
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        execute_read_skill_fn=_execute_read_skill,
        call_chat_completion_fn=_fake_completion,
    )

    assert handled is True
    assert executed == [("clickup_task_list", {"client_name": "Distex", "window": "this_week"})]
    assert slack.messages[-1]["text"] == "Recovered task list response."


@pytest.mark.asyncio
async def test_natural_brand_list_request_recovers_after_unusable_tool_loop(monkeypatch):
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
            return {"id": "e1"}

        def log_skill_result(self, run_id: str, skill_id: str, payload: dict):
            return {"id": "e2"}

        def log_assistant_message(self, run_id: str, text: str):
            return {"id": "m2"}

        def complete_run(self, run_id: str, status: str):
            return None

    async def _fake_completion(*args, **kwargs):
        _ = args, kwargs
        return {
            "content": '{"mode":"tool_call","skill_id":"unknown_tool","args":{}}',
            "tokens_in": 10,
            "tokens_out": 5,
            "tokens_total": 15,
            "model": "gpt-4o-mini",
            "duration_ms": 10,
        }

    executed: list[tuple[str, dict]] = []

    async def _execute_read_skill(**kwargs):
        executed.append((kwargs["skill_id"], kwargs["args"]))
        return {"response_text": "Recovered brand list response."}

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    session = _FakeSession()
    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="Show brands for Distex.",
        session=session,
        slack_user_id="U123",
        session_service=_FakeSessionService(session),
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        execute_read_skill_fn=_execute_read_skill,
        call_chat_completion_fn=_fake_completion,
    )

    assert handled is True
    assert executed == [("cc_brand_list_all", {"client_name": "Distex"})]
    assert slack.messages[-1]["text"] == "Recovered brand list response."


@pytest.mark.asyncio
async def test_generic_fallback_reply_is_replaced_by_task_list_recovery(monkeypatch):
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
            return {"id": "e1"}

        def log_skill_result(self, run_id: str, skill_id: str, payload: dict):
            return {"id": "e2"}

        def log_assistant_message(self, run_id: str, text: str):
            return {"id": "m2"}

        def complete_run(self, run_id: str, status: str):
            return None

    async def _fake_completion(*args, **kwargs):
        _ = args, kwargs
        return {
            "content": '{"mode":"reply","text":"I couldn\'t complete that flow. Could you rephrase and try again?"}',
            "tokens_in": 10,
            "tokens_out": 5,
            "tokens_total": 15,
            "model": "gpt-4o-mini",
            "duration_ms": 10,
        }

    executed: list[tuple[str, dict]] = []

    async def _execute_read_skill(**kwargs):
        executed.append((kwargs["skill_id"], kwargs["args"]))
        return {"response_text": "Recovered from generic fallback."}

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    session = _FakeSession()
    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="For Distex, what are the top tasks due this week?",
        session=session,
        slack_user_id="U123",
        session_service=_FakeSessionService(session),
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        execute_read_skill_fn=_execute_read_skill,
        call_chat_completion_fn=_fake_completion,
    )

    assert handled is True
    assert executed == [("clickup_task_list", {"client_name": "Distex", "window": "this_week"})]
    assert slack.messages[-1]["text"] == "Recovered from generic fallback."


@pytest.mark.asyncio
async def test_no_skill_reply_for_brand_request_triggers_recovery(monkeypatch):
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
            return {"id": "e1"}

        def log_skill_result(self, run_id: str, skill_id: str, payload: dict):
            return {"id": "e2"}

        def log_assistant_message(self, run_id: str, text: str):
            return {"id": "m2"}

        def complete_run(self, run_id: str, status: str):
            return None

    async def _fake_completion(*args, **kwargs):
        _ = args, kwargs
        return {
            "content": '{"mode":"reply","text":"Let me find the brands for you."}',
            "tokens_in": 10,
            "tokens_out": 5,
            "tokens_total": 15,
            "model": "gpt-4o-mini",
            "duration_ms": 10,
        }

    executed: list[tuple[str, dict]] = []

    async def _execute_read_skill(**kwargs):
        executed.append((kwargs["skill_id"], kwargs["args"]))
        return {"response_text": "Recovered brand list from no-skill reply."}

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    session = _FakeSession()
    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="List all brands for client Distex.",
        session=session,
        slack_user_id="U123",
        session_service=_FakeSessionService(session),
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        execute_read_skill_fn=_execute_read_skill,
        call_chat_completion_fn=_fake_completion,
    )

    assert handled is True
    assert executed == [("cc_brand_list_all", {"client_name": "Distex"})]
    assert slack.messages[-1]["text"] == "Recovered brand list from no-skill reply."


@pytest.mark.asyncio
async def test_brand_action_promise_reply_after_tool_call_triggers_recovery(monkeypatch):
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
            return {"id": "e1"}

        def log_skill_result(self, run_id: str, skill_id: str, payload: dict):
            return {"id": "e2"}

        def log_assistant_message(self, run_id: str, text: str):
            return {"id": "m2"}

        def complete_run(self, run_id: str, status: str):
            return None

    completions = iter(
        [
            {
                "content": '{"mode":"tool_call","skill_id":"lookup_client","args":{"query":"Distex"}}',
                "tokens_in": 10,
                "tokens_out": 5,
                "tokens_total": 15,
                "model": "gpt-4o-mini",
                "duration_ms": 10,
            },
            {
                "content": '{"mode":"reply","text":"It looks like there are multiple entries for Distex. I will proceed with checking the brands."}',
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

    executed: list[tuple[str, dict]] = []

    async def _execute_read_skill(**kwargs):
        executed.append((kwargs["skill_id"], kwargs["args"]))
        if kwargs["skill_id"] == "lookup_client":
            return {"response_text": "Multiple clients: Distex A, Distex B"}
        if kwargs["skill_id"] == "cc_brand_list_all":
            return {"response_text": "Recovered brand list from action-promise reply."}
        raise AssertionError("unexpected skill")

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    session = _FakeSession()
    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="Show brands for Distex.",
        session=session,
        slack_user_id="U123",
        session_service=_FakeSessionService(session),
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        execute_read_skill_fn=_execute_read_skill,
        call_chat_completion_fn=_fake_completion,
    )

    assert handled is True
    assert executed == [
        ("lookup_client", {"query": "Distex"}),
        ("cc_brand_list_all", {"client_name": "Distex"}),
    ]
    assert slack.messages[-1]["text"] == "Recovered brand list from action-promise reply."


@pytest.mark.asyncio
async def test_task_list_postprocess_enforces_top_n_and_priority(monkeypatch):
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
            return {"id": "e1"}

        def log_skill_result(self, run_id: str, skill_id: str, payload: dict):
            return {"id": "e2"}

        def log_assistant_message(self, run_id: str, text: str):
            return {"id": "m2"}

        def complete_run(self, run_id: str, status: str):
            return None

    async def _fake_completion(*args, **kwargs):
        _ = args, kwargs
        return {
            "content": '{"mode":"reply","text":"I couldn\'t complete that flow. Could you rephrase and try again?"}',
            "tokens_in": 10,
            "tokens_out": 5,
            "tokens_total": 15,
            "model": "gpt-4o-mini",
            "duration_ms": 10,
        }

    async def _execute_read_skill(**kwargs):
        _ = kwargs
        return {
            "response_text": (
                "*Tasks for Distex* (this week, 6 tasks):\n"
                "• <https://app.clickup.com/t/1|Task A> [in progress] (Owner 1)\n"
                "• <https://app.clickup.com/t/2|Task B> [review] (Owner 2)\n"
                "• <https://app.clickup.com/t/3|Task C> [in progress] (Owner 3)\n"
                "• <https://app.clickup.com/t/4|Task D> [in progress] (Owner 4)\n"
                "• <https://app.clickup.com/t/5|Task E> [in progress] (Owner 5)\n"
                "• <https://app.clickup.com/t/6|Task F> [in progress] (Owner 6)"
            )
        }

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    session = _FakeSession()
    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="For Distex, what are the top 5 tasks due this week, and what should I prioritize first?",
        session=session,
        slack_user_id="U123",
        session_service=_FakeSessionService(session),
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        execute_read_skill_fn=_execute_read_skill,
        call_chat_completion_fn=_fake_completion,
    )

    assert handled is True
    output = slack.messages[-1]["text"]
    bullet_lines = [line for line in output.splitlines() if line.strip().startswith("• ")]
    assert len(bullet_lines) == 5
    assert "Priority first:" in output


@pytest.mark.asyncio
async def test_sop_draft_request_always_includes_title_and_description(monkeypatch):
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

        def log_assistant_message(self, run_id: str, text: str):
            return {"id": "m2"}

        def complete_run(self, run_id: str, status: str):
            return None

    async def _fake_completion(*args, **kwargs):
        _ = args, kwargs
        return {
            "content": (
                '{"mode":"reply","text":"I found the SOP and summarized the steps. '
                "Now let's draft a task for your approval.\"}"
            ),
            "tokens_in": 10,
            "tokens_out": 5,
            "tokens_total": 15,
            "model": "gpt-4o-mini",
            "duration_ms": 10,
        }

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    session = _FakeSession()
    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="Find SOP for launching an Amazon coupon for Thorinox, then draft task title and description.",
        session=session,
        slack_user_id="U123",
        session_service=_FakeSessionService(session),
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        call_chat_completion_fn=_fake_completion,
    )

    assert handled is True
    output = slack.messages[-1]["text"]
    assert "Task Title:" in output
    assert "Task Description:" in output
    assert "Thorinox" in output
