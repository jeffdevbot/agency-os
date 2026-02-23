from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.services.agencyclaw.slack_dm_runtime import handle_dm_event_runtime
from app.services.agencyclaw.slack_runtime_deps import SlackDMRuntimeDeps


@dataclass
class _SessionState:
    session_id: str
    profile_id: str
    active_client_id: str | None
    context: dict[str, Any]


class _FakeSessionService:
    def __init__(self, state_by_user: dict[str, _SessionState], *, get_or_create_delay: float = 0.0) -> None:
        self._state_by_user = state_by_user
        self.db = MagicMock()
        self.get_or_create_delay = get_or_create_delay
        self.created_count_by_user: dict[str, int] = {}
        self.max_in_flight_by_user: dict[str, int] = {}
        self.max_in_flight_global = 0
        self._in_flight_global = 0
        self._in_flight_by_user: dict[str, int] = {}
        self._counter_lock = threading.Lock()

    def get_or_create_session(self, slack_user_id: str) -> Any:
        with self._counter_lock:
            self._in_flight_global += 1
            self.max_in_flight_global = max(self.max_in_flight_global, self._in_flight_global)
            per_user = self._in_flight_by_user.get(slack_user_id, 0) + 1
            self._in_flight_by_user[slack_user_id] = per_user
            self.max_in_flight_by_user[slack_user_id] = max(
                self.max_in_flight_by_user.get(slack_user_id, 0), per_user
            )

        if self.get_or_create_delay > 0:
            time.sleep(self.get_or_create_delay)

        state = self._state_by_user.get(slack_user_id)
        if state is None:
            state = _SessionState(
                session_id=f"sess-{slack_user_id}",
                profile_id=f"profile-{slack_user_id}",
                active_client_id=None,
                context={},
            )
            self._state_by_user[slack_user_id] = state
            self.created_count_by_user[slack_user_id] = self.created_count_by_user.get(slack_user_id, 0) + 1

        with self._counter_lock:
            self._in_flight_global -= 1
            self._in_flight_by_user[slack_user_id] -= 1

        # Return a copy so stale snapshot races are observable in tests.
        return SimpleNamespace(
            id=state.session_id,
            profile_id=state.profile_id,
            active_client_id=state.active_client_id,
            context=dict(state.context),
        )

    def touch_session(self, session_id: str) -> None:
        return None

    def update_context(self, session_id: str, context: dict[str, Any]) -> None:
        for state in self._state_by_user.values():
            if state.session_id == session_id:
                state.context.update(context)
                return
        raise AssertionError(f"unknown session_id: {session_id}")

    def get_context_value(self, session_id: str, key: str, default: Any = None) -> Any:
        for state in self._state_by_user.values():
            if state.session_id == session_id:
                return state.context.get(key, default)
        raise AssertionError(f"unknown session_id: {session_id}")


class _FakeSlack:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self.closed = 0

    async def post_message(self, *, channel: str, text: str, blocks: list[dict[str, Any]] | None = None) -> None:
        self.messages.append({"channel": channel, "text": text, "blocks": blocks})

    async def aclose(self) -> None:
        self.closed += 1


class _DummyPrefService:
    def set_default_client(self, profile_id: str, client_id: str) -> None:
        return None

    def clear_default_client(self, profile_id: str) -> None:
        return None


def _build_deps(
    *,
    session_service: _FakeSessionService,
    slack: _FakeSlack,
    handle_pending_task_continuation_fn,
) -> SlackDMRuntimeDeps:
    async def _allow_policy(**kwargs) -> dict[str, Any]:
        return {"allowed": True, "reason_code": "allowed", "user_message": "", "meta": {}}

    async def _noop_async(**kwargs) -> None:
        return None

    return SlackDMRuntimeDeps(
        get_session_service_fn=lambda: session_service,
        get_slack_service_fn=lambda: slack,
        preference_memory_service_factory=lambda _db: _DummyPrefService(),
        is_agent_loop_enabled_fn=lambda: False,
        run_agent_loop_reply_fn=_noop_async,
        handle_pending_task_continuation_fn=handle_pending_task_continuation_fn,
        is_llm_orchestrator_enabled_fn=lambda: False,
        try_llm_orchestrator_fn=_noop_async,
        classify_message_fn=lambda _text: ("help", {}),
        should_block_deterministic_intent_fn=lambda _intent: False,
        check_skill_policy_fn=_allow_policy,
        handle_create_task_fn=_noop_async,
        handle_task_list_fn=_noop_async,
        help_text_fn=lambda: "help",
        build_client_picker_blocks_fn=lambda _items: [],
        handle_cc_skill_fn=_noop_async,
        logger=MagicMock(),
        slack_api_error_cls=RuntimeError,
    )


class TestC17CLaneQueueRuntime:
    @pytest.mark.asyncio
    async def test_same_user_first_message_race_serializes_session_creation(self) -> None:
        state: dict[str, _SessionState] = {}
        session_service = _FakeSessionService(state, get_or_create_delay=0.01)
        slack = _FakeSlack()

        async def _pending_handler(**kwargs) -> bool:
            return False

        deps = _build_deps(
            session_service=session_service,
            slack=slack,
            handle_pending_task_continuation_fn=_pending_handler,
        )

        await asyncio.gather(
            handle_dm_event_runtime(slack_user_id="U1", channel="D1", text="first", deps=deps),
            handle_dm_event_runtime(slack_user_id="U1", channel="D1", text="second", deps=deps),
        )

        assert session_service.created_count_by_user.get("U1", 0) == 1
        assert session_service.max_in_flight_by_user.get("U1", 0) == 1

    @pytest.mark.asyncio
    async def test_same_session_serialization_prevents_lost_update(self) -> None:
        state = {
            "U1": _SessionState(
                session_id="sess-1",
                profile_id="profile-1",
                active_client_id="client-1",
                context={"pending_task_create": {"awaiting": True}, "counter": 0},
            )
        }
        session_service = _FakeSessionService(state)
        slack = _FakeSlack()

        async def _pending_handler(**kwargs) -> bool:
            session = kwargs["session"]
            read_counter = int(session_service.get_context_value(session.id, "counter", 0) or 0)
            await asyncio.sleep(0.01)
            session_service.update_context(session.id, {"counter": read_counter + 1})
            return True

        deps = _build_deps(
            session_service=session_service,
            slack=slack,
            handle_pending_task_continuation_fn=_pending_handler,
        )

        t1 = asyncio.create_task(
            handle_dm_event_runtime(slack_user_id="U1", channel="D1", text="first", deps=deps)
        )
        t2 = asyncio.create_task(
            handle_dm_event_runtime(slack_user_id="U1", channel="D1", text="second", deps=deps)
        )
        await asyncio.gather(t1, t2)

        assert state["U1"].context["counter"] == 2

    @pytest.mark.asyncio
    async def test_same_session_never_runs_pending_handler_concurrently(self) -> None:
        state = {
            "U1": _SessionState(
                session_id="sess-1",
                profile_id="profile-1",
                active_client_id="client-1",
                context={"pending_task_create": {"awaiting": True}},
            )
        }
        session_service = _FakeSessionService(state)
        slack = _FakeSlack()
        in_flight = 0
        max_in_flight = 0

        async def _pending_handler(**kwargs) -> bool:
            nonlocal in_flight, max_in_flight
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
            await asyncio.sleep(0.01)
            in_flight -= 1
            return True

        deps = _build_deps(
            session_service=session_service,
            slack=slack,
            handle_pending_task_continuation_fn=_pending_handler,
        )

        await asyncio.gather(
            handle_dm_event_runtime(slack_user_id="U1", channel="D1", text="first", deps=deps),
            handle_dm_event_runtime(slack_user_id="U1", channel="D1", text="second", deps=deps),
        )

        assert max_in_flight == 1

    @pytest.mark.asyncio
    async def test_different_sessions_remain_concurrent(self) -> None:
        state = {
            "U1": _SessionState(
                session_id="sess-1",
                profile_id="profile-1",
                active_client_id="client-1",
                context={"pending_task_create": {"awaiting": True}},
            ),
            "U2": _SessionState(
                session_id="sess-2",
                profile_id="profile-2",
                active_client_id="client-2",
                context={"pending_task_create": {"awaiting": True}},
            ),
        }
        session_service = _FakeSessionService(state)
        slack = _FakeSlack()
        gate = asyncio.Event()
        started: set[str] = set()

        async def _pending_handler(**kwargs) -> bool:
            session = kwargs["session"]
            started.add(session.id)
            await gate.wait()
            return True

        deps = _build_deps(
            session_service=session_service,
            slack=slack,
            handle_pending_task_continuation_fn=_pending_handler,
        )

        t1 = asyncio.create_task(
            handle_dm_event_runtime(slack_user_id="U1", channel="D1", text="first", deps=deps)
        )
        t2 = asyncio.create_task(
            handle_dm_event_runtime(slack_user_id="U2", channel="D2", text="second", deps=deps)
        )

        for _ in range(20):
            if started == {"sess-1", "sess-2"}:
                break
            await asyncio.sleep(0.005)
        assert started == {"sess-1", "sess-2"}

        gate.set()
        await asyncio.gather(t1, t2)

    @pytest.mark.asyncio
    async def test_different_users_can_overlap_session_creation(self) -> None:
        state: dict[str, _SessionState] = {}
        session_service = _FakeSessionService(state, get_or_create_delay=0.02)
        slack = _FakeSlack()

        async def _pending_handler(**kwargs) -> bool:
            return False

        deps = _build_deps(
            session_service=session_service,
            slack=slack,
            handle_pending_task_continuation_fn=_pending_handler,
        )

        await asyncio.gather(
            handle_dm_event_runtime(slack_user_id="U1", channel="D1", text="first", deps=deps),
            handle_dm_event_runtime(slack_user_id="U2", channel="D2", text="second", deps=deps),
        )

        assert session_service.created_count_by_user.get("U1", 0) == 1
        assert session_service.created_count_by_user.get("U2", 0) == 1
        assert session_service.max_in_flight_global >= 2
