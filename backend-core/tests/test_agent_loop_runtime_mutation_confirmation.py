from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.services.agencyclaw.agent_loop_runtime import run_reply_only_agent_loop_turn
from app.services.agencyclaw.pending_confirmation import build_pending_confirmation
from .agent_loop_runtime_test_fakes import (
    FakeSession as _FakeSession,
    FakeSessionService as _FakeSessionService,
    FakeSlack as _FakeSlack,
)

@pytest.mark.asyncio
async def test_c17f_create_task_proposal_is_stored_not_executed(monkeypatch):
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
            "content": '{"mode":"tool_call","skill_id":"clickup_task_create","args":{"client_name":"Distex","task_title":"Fix title"}}',
            "tokens_in": 10,
            "tokens_out": 5,
            "tokens_total": 15,
            "model": "gpt-4o-mini",
            "duration_ms": 10,
        }

    async def _allow_policy(**kwargs):
        _ = kwargs
        return {"allowed": True, "user_message": "", "reason_code": "allowed", "meta": {}}

    executed = 0

    async def _execute_create_task(**kwargs):
        nonlocal executed
        _ = kwargs
        executed += 1
        return {"response_text": "Task created"}

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    session = _FakeSession()
    session_service = _FakeSessionService(session)
    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="create task for Distex",
        session=session,
        slack_user_id="U123",
        session_service=session_service,
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        execute_create_task_fn=_execute_create_task,
        check_mutation_policy_fn=_allow_policy,
        call_chat_completion_fn=_fake_completion,
    )

    assert handled is True
    assert executed == 0
    pending = session.context.get("pending_confirmation")
    assert isinstance(pending, dict)
    assert pending.get("skill_id") == "clickup_task_create"
    assert "confirm" in slack.messages[-1]["text"].lower()


@pytest.mark.asyncio
async def test_c17f_natural_create_recovery_sets_pending_after_clarification_reply(monkeypatch):
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
                "content": '{"mode":"tool_call","skill_id":"clickup_task_list","args":{}}',
                "tokens_in": 10,
                "tokens_out": 5,
                "tokens_total": 15,
                "model": "gpt-4o-mini",
                "duration_ms": 10,
            },
            {
                "content": (
                    '{"mode":"reply","text":"It looks like I need to know which client or brand this task is for. '
                    'Could you please specify the client or brand name for this task?"}'
                ),
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

    async def _allow_policy(**kwargs):
        _ = kwargs
        return {"allowed": True, "user_message": "", "reason_code": "allowed", "meta": {}}

    async def _execute_task_list(**kwargs):
        _ = kwargs
        return {"response_text": "Which client? Pick one and ask again:"}

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    session = _FakeSession()
    session_service = _FakeSessionService(session)
    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="Create this task in ClickUp for Test: Launch coupon promo for Test with SOP-aligned checklist.",
        session=session,
        slack_user_id="U123",
        session_service=session_service,
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        execute_task_list_fn=_execute_task_list,
        check_mutation_policy_fn=_allow_policy,
        execute_create_task_fn=MagicMock(),
        call_chat_completion_fn=_fake_completion,
    )

    assert handled is True
    pending = session.context.get("pending_confirmation")
    assert isinstance(pending, dict)
    assert pending.get("skill_id") == "clickup_task_create"
    assert pending.get("args", {}).get("client_name") == "Test"
    assert pending.get("args", {}).get("task_title") == "Launch coupon promo for Test with SOP-aligned checklist"
    assert "ready to create task" in slack.messages[-1]["text"].lower()


@pytest.mark.asyncio
async def test_c17f_natural_create_recovery_sets_pending_after_action_promise_reply(monkeypatch):
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
                "{\"mode\":\"reply\",\"text\":\"Let's start by identifying the client and brand details for "
                "\\\"Test\\\" to gather any existing information that might help us proceed. "
                "I'll look up the brand \\\"Test\\\" first.\"}"
            ),
            "tokens_in": 10,
            "tokens_out": 5,
            "tokens_total": 15,
            "model": "gpt-4o-mini",
            "duration_ms": 10,
        }

    async def _allow_policy(**kwargs):
        _ = kwargs
        return {"allowed": True, "user_message": "", "reason_code": "allowed", "meta": {}}

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    session = _FakeSession()
    session_service = _FakeSessionService(session)
    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="Create this task in ClickUp for Test: Launch coupon promo for Test with SOP-aligned checklist.",
        session=session,
        slack_user_id="U123",
        session_service=session_service,
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        check_mutation_policy_fn=_allow_policy,
        execute_create_task_fn=MagicMock(),
        call_chat_completion_fn=_fake_completion,
    )

    assert handled is True
    pending = session.context.get("pending_confirmation")
    assert isinstance(pending, dict)
    assert pending.get("skill_id") == "clickup_task_create"
    assert pending.get("args", {}).get("client_name") == "Test"
    assert pending.get("args", {}).get("task_title") == "Launch coupon promo for Test with SOP-aligned checklist"
    assert "ready to create task" in slack.messages[-1]["text"].lower()


@pytest.mark.asyncio
async def test_c17f_confirm_like_reply_without_pending_returns_guardrail(monkeypatch):
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

    called = False

    async def _fake_completion(*args, **kwargs):
        nonlocal called
        _ = args, kwargs
        called = True
        return {
            "content": '{"mode":"reply","text":"fallback"}',
            "tokens_in": 10,
            "tokens_out": 5,
            "tokens_total": 15,
            "model": "gpt-4o-mini",
            "duration_ms": 10,
        }

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    session = _FakeSession()
    session_service = _FakeSessionService(session)
    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="Yes, create it.",
        session=session,
        slack_user_id="U123",
        session_service=session_service,
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        call_chat_completion_fn=_fake_completion,
    )

    assert handled is True
    assert called is False
    assert "isn't a pending task proposal" in slack.messages[-1]["text"].lower()


@pytest.mark.asyncio
async def test_c17f_action_promise_recovery_then_confirm_executes_once(monkeypatch):
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
            "content": (
                "{\"mode\":\"reply\",\"text\":\"Let's start by identifying the client and brand details for "
                "\\\"Test\\\" to gather any existing information that might help us proceed. "
                "I'll look up the brand \\\"Test\\\" first.\"}"
            ),
            "tokens_in": 10,
            "tokens_out": 5,
            "tokens_total": 15,
            "model": "gpt-4o-mini",
            "duration_ms": 10,
        }

    async def _allow_policy(**kwargs):
        _ = kwargs
        return {"allowed": True, "user_message": "", "reason_code": "allowed", "meta": {}}

    executed = 0

    async def _execute_create_task(**kwargs):
        nonlocal executed
        _ = kwargs
        executed += 1
        return {"response_text": "Task created: <https://example.test|Launch coupon promo>"}

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    session = _FakeSession()
    session_service = _FakeSessionService(session)
    slack = _FakeSlack()

    first_handled = await run_reply_only_agent_loop_turn(
        text="Create this task in ClickUp for Test: Launch coupon promo for Test with SOP-aligned checklist.",
        session=session,
        slack_user_id="U123",
        session_service=session_service,
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        check_mutation_policy_fn=_allow_policy,
        execute_create_task_fn=_execute_create_task,
        call_chat_completion_fn=_fake_completion,
    )
    assert first_handled is True
    assert isinstance(session.context.get("pending_confirmation"), dict)

    second_handled = await run_reply_only_agent_loop_turn(
        text="Yes, create it.",
        session=session,
        slack_user_id="U123",
        session_service=session_service,
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        check_mutation_policy_fn=_allow_policy,
        execute_create_task_fn=_execute_create_task,
        call_chat_completion_fn=_fake_completion,
    )

    assert second_handled is True
    assert executed == 1
    assert session.context.get("pending_confirmation") is None
    assert "task created" in slack.messages[-1]["text"].lower()


@pytest.mark.asyncio
async def test_c17f_natural_create_recovery_parses_client_brand_title_description(monkeypatch):
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
                '{"mode":"reply","text":"Could you please provide more details about what you would like to create?"}'
            ),
            "tokens_in": 10,
            "tokens_out": 5,
            "tokens_total": 15,
            "model": "gpt-4o-mini",
            "duration_ms": 10,
        }

    async def _allow_policy(**kwargs):
        _ = kwargs
        return {"allowed": True, "user_message": "", "reason_code": "allowed", "meta": {}}

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    session = _FakeSession()
    session_service = _FakeSessionService(session)
    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text=(
            "Create a ClickUp task for client Test and brand Test. "
            "Title: Launch coupon promo with SOP checklist. "
            "Description: follow SOP, include checklist, owner Jeff, due Friday. "
            "Do not execute yet."
        ),
        session=session,
        slack_user_id="U123",
        session_service=session_service,
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        check_mutation_policy_fn=_allow_policy,
        execute_create_task_fn=MagicMock(),
        call_chat_completion_fn=_fake_completion,
    )

    assert handled is True
    pending = session.context.get("pending_confirmation")
    assert isinstance(pending, dict)
    assert pending.get("args", {}).get("client_name") == "Test"
    assert pending.get("args", {}).get("brand_name") == "Test"
    assert pending.get("args", {}).get("task_title") == "Launch coupon promo with SOP checklist"
    assert "follow SOP, include checklist, owner Jeff, due Friday" in pending.get("args", {}).get(
        "task_description", ""
    )


@pytest.mark.asyncio
async def test_c17f_confirm_executes_once_and_clears_payload(monkeypatch):
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

        def log_skill_result(self, run_id: str, skill_id: str, payload: dict):
            calls.append(("log_skill_result", (run_id, skill_id, payload)))
            return {"id": "e2"}

        def log_assistant_message(self, run_id: str, text: str):
            calls.append(("log_assistant_message", (run_id, text)))
            return {"id": "m2"}

        def complete_run(self, run_id: str, status: str):
            calls.append(("complete_run", (run_id, status)))
            return None

    pending = build_pending_confirmation(
        action_type="mutation",
        skill_id="clickup_task_create",
        args={"task_title": "Fix title", "client_name": "Distex"},
        requested_by="U123",
        lane_key="U123",
        now=datetime.now(timezone.utc),
        ttl_seconds=600,
    )

    executed = 0

    async def _execute_create_task(**kwargs):
        nonlocal executed
        _ = kwargs
        executed += 1
        return {"response_text": "Task created: <url|Fix title>"}

    async def _allow_policy(**kwargs):
        _ = kwargs
        return {"allowed": True, "user_message": "", "reason_code": "allowed", "meta": {}}

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    session = _FakeSession(context={"pending_confirmation": pending})
    session_service = _FakeSessionService(session)
    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="confirm",
        session=session,
        slack_user_id="U123",
        session_service=session_service,
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        execute_create_task_fn=_execute_create_task,
        check_mutation_policy_fn=_allow_policy,
    )

    assert handled is True
    assert executed == 1
    assert session.context.get("pending_confirmation") is None
    assert ("log_skill_call", ("run-1", "clickup_task_create", {"task_title": "Fix title", "client_name": "Distex"})) in calls
    assert ("complete_run", ("run-1", "completed")) in calls


@pytest.mark.asyncio
async def test_c17f_cancel_clears_payload_without_execution(monkeypatch):
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

    pending = build_pending_confirmation(
        action_type="mutation",
        skill_id="clickup_task_create",
        args={"task_title": "Fix title"},
        requested_by="U123",
        lane_key="U123",
    )

    executed = 0

    async def _execute_create_task(**kwargs):
        nonlocal executed
        _ = kwargs
        executed += 1
        return {"response_text": "Task created"}

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    session = _FakeSession(context={"pending_confirmation": pending})
    session_service = _FakeSessionService(session)
    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="cancel",
        session=session,
        slack_user_id="U123",
        session_service=session_service,
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        execute_create_task_fn=_execute_create_task,
    )

    assert handled is True
    assert executed == 0
    assert session.context.get("pending_confirmation") is None
    assert "cancelled" in slack.messages[-1]["text"].lower()


@pytest.mark.asyncio
async def test_c17f_expired_payload_rejected_and_cleared(monkeypatch):
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

    pending = build_pending_confirmation(
        action_type="mutation",
        skill_id="clickup_task_create",
        args={"task_title": "Fix title"},
        requested_by="U123",
        lane_key="U123",
        now=datetime.now(timezone.utc) - timedelta(minutes=20),
        ttl_seconds=60,
    )

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    session = _FakeSession(context={"pending_confirmation": pending})
    session_service = _FakeSessionService(session)
    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="confirm",
        session=session,
        slack_user_id="U123",
        session_service=session_service,
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
    )

    assert handled is True
    assert session.context.get("pending_confirmation") is None
    assert "expired" in slack.messages[-1]["text"].lower()


@pytest.mark.asyncio
async def test_c17f_wrong_actor_cannot_confirm(monkeypatch):
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

    pending = build_pending_confirmation(
        action_type="mutation",
        skill_id="clickup_task_create",
        args={"task_title": "Fix title"},
        requested_by="U123",
        lane_key="U123",
    )

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    session = _FakeSession(context={"pending_confirmation": pending})
    session_service = _FakeSessionService(session)
    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="confirm",
        session=session,
        slack_user_id="U999",
        session_service=session_service,
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
    )

    assert handled is True
    assert session.context.get("pending_confirmation") is not None
    assert "original requester" in slack.messages[-1]["text"].lower()


@pytest.mark.asyncio
async def test_c17f_confirm_time_policy_denial_blocks_execution_and_keeps_pending(monkeypatch):
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

    pending = build_pending_confirmation(
        action_type="mutation",
        skill_id="clickup_task_create",
        args={"task_title": "Fix title"},
        requested_by="U123",
        lane_key="U123",
    )
    executed = 0

    async def _execute_create_task(**kwargs):
        nonlocal executed
        _ = kwargs
        executed += 1
        return {"response_text": "Task created"}

    async def _deny_policy(**kwargs):
        _ = kwargs
        return {"allowed": False, "user_message": "Not allowed in this channel.", "reason_code": "deny", "meta": {}}

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    session = _FakeSession(context={"pending_confirmation": pending})
    session_service = _FakeSessionService(session)
    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="confirm",
        session=session,
        slack_user_id="U123",
        session_service=session_service,
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        execute_create_task_fn=_execute_create_task,
        check_mutation_policy_fn=_deny_policy,
    )

    assert handled is True
    assert executed == 0
    assert session.context.get("pending_confirmation") is not None
    assert "not allowed" in slack.messages[-1]["text"].lower()


@pytest.mark.asyncio
async def test_c17f_fingerprint_mismatch_rejected_and_cleared(monkeypatch):
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

    pending = build_pending_confirmation(
        action_type="mutation",
        skill_id="clickup_task_create",
        args={"task_title": "Fix title"},
        requested_by="U123",
        lane_key="U123",
    )
    pending["proposal_fingerprint"] = "bad-fingerprint"

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    session = _FakeSession(context={"pending_confirmation": pending})
    session_service = _FakeSessionService(session)
    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="confirm",
        session=session,
        slack_user_id="U123",
        session_service=session_service,
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
    )

    assert handled is True
    assert session.context.get("pending_confirmation") is None
    assert "couldn't validate" in slack.messages[-1]["text"].lower()

@pytest.mark.asyncio
async def test_c17f_failed_create_keeps_pending_for_retry(monkeypatch):
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

        def complete_run(self, run_id: str, status: str):
            return None

    pending = build_pending_confirmation(
        action_type="mutation",
        skill_id="clickup_task_create",
        args={"task_title": "Fix title"},
        requested_by="U123",
        lane_key="U123",
    )

    async def _raise_create(**kwargs):
        _ = kwargs
        raise RuntimeError("create failed")

    async def _allow_policy(**kwargs):
        _ = kwargs
        return {"allowed": True, "user_message": "", "reason_code": "allowed", "meta": {}}

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    session = _FakeSession(context={"pending_confirmation": pending})
    session_service = _FakeSessionService(session)
    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="confirm",
        session=session,
        slack_user_id="U123",
        session_service=session_service,
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        execute_create_task_fn=_raise_create,
        check_mutation_policy_fn=_allow_policy,
    )

    assert handled is True
    assert session.context.get("pending_confirmation") is not None
    assert "issue" in slack.messages[-1]["text"].lower()
