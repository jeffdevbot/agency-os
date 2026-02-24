from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.services.agencyclaw.agent_loop_runtime import run_reply_only_agent_loop_turn
from app.services.agencyclaw.pending_confirmation import build_pending_confirmation


class _FakeSlack:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    async def post_message(self, *, channel: str, text: str, blocks=None) -> None:
        self.messages.append({"channel": channel, "text": text})


class _FakeSession:
    def __init__(self, session_id: str = "sess-1", context: dict | None = None) -> None:
        self.id = session_id
        self.context = context or {}


class _FakeSessionService:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    def update_context(self, session_id: str, context: dict) -> None:
        assert session_id == self._session.id
        self._session.context.update(context)


@pytest.mark.asyncio
async def test_c17e_task_list_round_trip_logs_events(monkeypatch):
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

    session = _FakeSession()
    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="show tasks for Distex",
        session=session,
        slack_user_id="U123",
        session_service=_FakeSessionService(session),
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
async def test_c17g_injects_recent_skill_evidence_into_prompt(monkeypatch):
    captured_prompts: list[list[dict[str, str]]] = []

    class FakeStore:
        def __init__(self, _db):
            pass

        def list_recent_run_messages(self, run_id: str, limit: int = 20):
            return [{"role": "user", "content": {"text": "hello"}, "created_at": "2026-01-01T00:00:00Z"}]

        def list_recent_skill_events(self, run_id: str, limit: int = 20):
            return [
                {
                    "event_type": "skill_result",
                    "skill_id": "lookup_client",
                    "payload_summary": '{"clients":["Distex"]}',
                    "created_at": "2026-01-01T00:00:01Z",
                }
            ]

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

    async def _fake_completion(messages, **kwargs):
        _ = kwargs
        captured_prompts.append(messages)
        return {
            "content": '{"mode":"reply","text":"hello"}',
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
        text="hello",
        session=session,
        slack_user_id="U123",
        session_service=_FakeSessionService(session),
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        call_chat_completion_fn=_fake_completion,
    )

    assert handled is True
    assert len(captured_prompts) == 1
    system_messages = [m.get("content", "") for m in captured_prompts[0] if m.get("role") == "system"]
    assert any("Recent skill evidence:" in content for content in system_messages)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "skill_id,args,expected_args",
    [
        ("cc_client_lookup", {"query": "dist"}, {"query": "dist"}),
        ("cc_client_lookup", {"query": ""}, {"query": ""}),
        ("cc_brand_list_all", {"client_name": "Distex"}, {"client_name": "Distex"}),
        ("cc_brand_clickup_mapping_audit", {}, {}),
        ("lookup_client", {}, {}),
        ("lookup_client", {"query": "dist"}, {"query": "dist"}),
        (
            "lookup_brand",
            {"client_name": "Distex", "brand_name": "Alpha"},
            {"client_name": "Distex", "brand_name": "Alpha"},
        ),
        (
            "search_kb",
            {"query": "coupon setup", "client_name": "Distex", "brand_name": "Alpha"},
            {"query": "coupon setup", "client_name": "Distex", "brand_name": "Alpha"},
        ),
        (
            "resolve_brand",
            {"task_text": "Fix listing image", "client_name": "Distex", "brand_hint": "Alpha"},
            {"task_text": "Fix listing image", "client_name": "Distex", "brand_hint": "Alpha"},
        ),
        ("get_client_context", {"client_name": "Distex"}, {"client_name": "Distex"}),
        ("load_prior_skill_result", {"key": "ev:run-1/evt-1"}, {"key": "ev:run-1/evt-1"}),
    ],
)
async def test_c17g_read_skill_round_trip_logs_events(monkeypatch, skill_id, args, expected_args):
    calls: list[tuple[str, tuple]] = []

    class FakeStore:
        def __init__(self, _db):
            pass

        def list_recent_run_messages(self, run_id: str, limit: int = 20):
            return [{"role": "user", "content": {"text": "context"}, "created_at": "2026-01-01T00:00:00Z"}]

    class FakeTurnLogger:
        def __init__(self, _store):
            pass

        def start_main_run(self, session_id: str):
            return {"id": "run-1", "status": "running"}

        def log_user_message(self, run_id: str, text: str):
            calls.append(("log_user_message", (run_id, text)))
            return {"id": "m1"}

        def log_skill_call(self, run_id: str, logged_skill_id: str, payload: dict):
            calls.append(("log_skill_call", (run_id, logged_skill_id, payload)))
            return {"id": "e1"}

        def log_skill_result(self, run_id: str, logged_skill_id: str, payload: dict):
            calls.append(("log_skill_result", (run_id, logged_skill_id, payload)))
            return {"id": "e2"}

        def log_assistant_message(self, run_id: str, text: str):
            calls.append(("log_assistant_message", (run_id, text)))
            return {"id": "m2"}

        def complete_run(self, run_id: str, status: str):
            calls.append(("complete_run", (run_id, status)))
            return None

    tool_call_payload = json.dumps(
        {"mode": "tool_call", "skill_id": skill_id, "args": args},
        separators=(",", ":"),
    )

    completions = iter(
        [
            {
                "content": tool_call_payload,
                "tokens_in": 10,
                "tokens_out": 5,
                "tokens_total": 15,
                "model": "gpt-4o-mini",
                "duration_ms": 10,
            },
            {
                "content": '{"mode":"reply","text":"Done."}',
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

    executed: list[tuple[str, dict]] = []

    async def _execute_read_skill(**kwargs):
        executed.append((kwargs["skill_id"], kwargs["args"]))
        return {"response_text": f"{kwargs['skill_id']} ok"}

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    session = _FakeSession()
    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="run read skill",
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
    assert executed == [(skill_id, expected_args)]
    assert slack.messages == [{"channel": "D1", "text": "Done."}]
    assert ("log_skill_call", ("run-1", skill_id, expected_args)) in calls
    assert ("log_skill_result", ("run-1", skill_id, {"response_text": f"{skill_id} ok"})) in calls
    assert ("complete_run", ("run-1", "completed")) in calls


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_result",
    [
        {"response_text": "Loaded prior result: [skill_result] clickup_task_list: {}"},
        {"response_text": "I couldn't find a prior result for that key.", "evidence": {"ok": False, "error": "not_found"}},
        {"response_text": "I couldn't load that prior result because the key format is invalid.", "evidence": {"ok": False, "error": "invalid_key"}},
    ],
)
async def test_c17g_rehydration_runtime_posts_executor_response(monkeypatch, tool_result):
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
                "content": '{"mode":"tool_call","skill_id":"load_prior_skill_result","args":{"key":"ev:run-1"}}',
                "tokens_in": 10,
                "tokens_out": 5,
                "tokens_total": 15,
                "model": "gpt-4o-mini",
                "duration_ms": 10,
            },
            {
                "content": '{"mode":"reply","text":"Acknowledged."}',
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

    async def _execute_read_skill(**kwargs):
        assert kwargs["skill_id"] == "load_prior_skill_result"
        return tool_result

    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", FakeTurnLogger)

    session = _FakeSession()
    slack = _FakeSlack()
    handled = await run_reply_only_agent_loop_turn(
        text="load prior",
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
    assert slack.messages == [{"channel": "D1", "text": "Acknowledged."}]


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
async def test_c17g_disallowed_read_skill_fails_safely(monkeypatch):
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
            "content": '{"mode":"tool_call","skill_id":"clickup_task_delete","args":{"task_id":"123"}}',
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
        text="delete task 123",
        session=session,
        slack_user_id="U123",
        session_service=_FakeSessionService(session),
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        call_chat_completion_fn=_fake_completion,
    )

    assert handled is True
    assert len(slack.messages) == 1
    assert "issue" in slack.messages[-1]["text"].lower()
    assert ("complete_run", ("run-1", "failed")) in calls


@pytest.mark.asyncio
async def test_c17g_lookup_client_unknown_arg_fails_safe(monkeypatch):
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
            "content": '{"mode":"tool_call","skill_id":"lookup_client","args":{"query":"dist","foo":"bar"}}',
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
        text="lookup client",
        session=session,
        slack_user_id="U123",
        session_service=_FakeSessionService(session),
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        call_chat_completion_fn=_fake_completion,
    )

    assert handled is True
    assert len(slack.messages) == 1
    assert "issue" in slack.messages[-1]["text"].lower()
    assert ("complete_run", ("run-1", "failed")) in calls


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
