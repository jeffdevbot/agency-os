"""Tests for C10A: Actor/Surface context resolver + policy gate.

Covers:
- resolve_actor_context: known profile, missing profile, DB error
- resolve_surface_context: event payload, channel ID heuristic, unknown
- evaluate_tool_policy: allow/deny matrix for actor/surface/skill combos
- Integration: denied tool_call posts denial and skips handler
- Integration: deterministic path also blocked by policy when denied
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.routes.slack import (
    _check_tool_policy,
    _handle_dm_event,
    _try_llm_orchestrator,
)
from app.services.agencyclaw.policy_gate import (
    ActorContext,
    PolicyDecision,
    SurfaceContext,
    evaluate_tool_policy,
    resolve_actor_context,
    resolve_surface_context,
)
from app.services.agencyclaw.slack_orchestrator import OrchestratorResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FakeSession:
    id: str = "sess-1"
    slack_user_id: str = "U123"
    profile_id: Optional[str] = "profile-1"
    active_client_id: Optional[str] = "client-1"
    context: dict = None  # type: ignore[assignment]
    last_message_at: Optional[str] = None

    def __post_init__(self):
        if self.context is None:
            object.__setattr__(self, "context", {})


def _make_mocks(**session_overrides) -> tuple[MagicMock, AsyncMock]:
    session = FakeSession(**session_overrides)
    svc = MagicMock()
    svc.get_or_create_session.return_value = session
    svc.find_client_matches.return_value = [{"id": "client-1", "name": "Distex"}]
    svc.get_client_name.return_value = "Distex"
    svc.touch_session.return_value = None
    svc.update_context.return_value = None
    svc.list_clients_for_picker.return_value = [{"id": "c1", "name": "Acme"}]
    slack = AsyncMock()
    return svc, slack


def _make_orchestrator_result(**overrides) -> OrchestratorResult:
    base: dict[str, Any] = {
        "mode": "reply",
        "text": None,
        "question": None,
        "missing_fields": None,
        "skill_id": None,
        "args": None,
        "confidence": 0.9,
        "reason": None,
        "tokens_in": 50,
        "tokens_out": 30,
        "tokens_total": 80,
        "model_used": "gpt-4o-mini",
    }
    base.update(overrides)
    return OrchestratorResult(**base)  # type: ignore[arg-type]


def _make_db(*, profile_row: dict | None = None, raise_error: bool = False):
    """Build a mock Supabase client for resolve_actor_context."""
    db = MagicMock()
    if raise_error:
        db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.side_effect = \
            RuntimeError("DB down")
    else:
        resp = MagicMock()
        resp.data = [profile_row] if profile_row else []
        db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = resp
    return db


def _actor(role: str = "operator", profile_id: str | None = "profile-1") -> ActorContext:
    return ActorContext(profile_id=profile_id, slack_user_id="U123", role=role, is_admin=(role == "admin"))


def _surface(surface_type: str = "dm") -> SurfaceContext:
    return SurfaceContext(channel_id="D123", surface_type=surface_type)


# ---------------------------------------------------------------------------
# 1. resolve_actor_context
# ---------------------------------------------------------------------------


class TestResolveActorContext:
    def test_admin_profile(self):
        db = _make_db(profile_row={"id": "p1", "is_admin": True})
        actor = resolve_actor_context(db, "U123", "p1")
        assert actor["role"] == "admin"
        assert actor["is_admin"] is True
        assert actor["profile_id"] == "p1"

    def test_non_admin_profile(self):
        db = _make_db(profile_row={"id": "p1", "is_admin": False})
        actor = resolve_actor_context(db, "U123", "p1")
        assert actor["role"] == "operator"
        assert actor["is_admin"] is False

    def test_missing_profile_id(self):
        db = _make_db()
        actor = resolve_actor_context(db, "U123", None)
        assert actor["role"] == "unknown"
        assert actor["profile_id"] is None

    def test_profile_not_found_in_db(self):
        db = _make_db(profile_row=None)
        actor = resolve_actor_context(db, "U123", "p-missing")
        assert actor["role"] == "unknown"

    def test_db_error_fails_closed(self):
        db = _make_db(raise_error=True)
        actor = resolve_actor_context(db, "U123", "p1")
        assert actor["role"] == "unknown"
        assert actor["is_admin"] is False


# ---------------------------------------------------------------------------
# 2. resolve_surface_context
# ---------------------------------------------------------------------------


class TestResolveSurfaceContext:
    def test_event_payload_im(self):
        surface = resolve_surface_context("D123", {"channel_type": "im"})
        assert surface["surface_type"] == "dm"

    def test_event_payload_channel(self):
        surface = resolve_surface_context("C456", {"channel_type": "channel"})
        assert surface["surface_type"] == "channel"

    def test_event_payload_group(self):
        surface = resolve_surface_context("G789", {"channel_type": "group"})
        assert surface["surface_type"] == "group"

    def test_event_payload_mpim(self):
        surface = resolve_surface_context("G789", {"channel_type": "mpim"})
        assert surface["surface_type"] == "group"

    def test_channel_id_heuristic_dm(self):
        surface = resolve_surface_context("D123")
        assert surface["surface_type"] == "dm"

    def test_channel_id_heuristic_channel(self):
        surface = resolve_surface_context("C456")
        assert surface["surface_type"] == "channel"

    def test_channel_id_heuristic_group(self):
        surface = resolve_surface_context("G789")
        assert surface["surface_type"] == "group"

    def test_unknown_channel_id(self):
        surface = resolve_surface_context("X999")
        assert surface["surface_type"] == "unknown"

    def test_empty_channel_id(self):
        surface = resolve_surface_context("")
        assert surface["surface_type"] == "unknown"


# ---------------------------------------------------------------------------
# 3. evaluate_tool_policy
# ---------------------------------------------------------------------------


class TestEvaluateToolPolicy:
    def test_allow_dm_operator_weekly_read(self):
        decision = evaluate_tool_policy(_actor("operator"), _surface("dm"), "clickup_task_list_weekly")
        assert decision["allowed"] is True
        assert decision["reason_code"] == "allowed"

    def test_allow_dm_operator_create_task(self):
        decision = evaluate_tool_policy(_actor("operator"), _surface("dm"), "clickup_task_create")
        assert decision["allowed"] is True

    def test_allow_dm_admin_create_task(self):
        decision = evaluate_tool_policy(_actor("admin"), _surface("dm"), "clickup_task_create")
        assert decision["allowed"] is True

    def test_deny_unknown_actor(self):
        decision = evaluate_tool_policy(_actor("unknown"), _surface("dm"), "clickup_task_list_weekly")
        assert decision["allowed"] is False
        assert decision["reason_code"] == "unknown_actor"
        assert decision["user_message"]  # has user-facing text

    def test_deny_unknown_surface(self):
        decision = evaluate_tool_policy(_actor("operator"), _surface("unknown"), "clickup_task_list_weekly")
        assert decision["allowed"] is False
        assert decision["reason_code"] == "unknown_surface"

    def test_deny_non_dm_mutation(self):
        decision = evaluate_tool_policy(_actor("operator"), _surface("channel"), "clickup_task_create")
        assert decision["allowed"] is False
        assert decision["reason_code"] == "non_dm_mutation"

    def test_deny_non_dm_read(self):
        decision = evaluate_tool_policy(_actor("operator"), _surface("channel"), "clickup_task_list_weekly")
        assert decision["allowed"] is False
        assert decision["reason_code"] == "non_dm_read"

    def test_deny_unknown_skill(self):
        decision = evaluate_tool_policy(_actor("operator"), _surface("dm"), "clickup_delete_everything")
        assert decision["allowed"] is False
        assert decision["reason_code"] == "unknown_skill"

    def test_deny_viewer_mutation(self):
        decision = evaluate_tool_policy(_actor("viewer"), _surface("dm"), "clickup_task_create")
        assert decision["allowed"] is False
        assert decision["reason_code"] == "viewer_mutation_denied"

    def test_allow_viewer_read(self):
        decision = evaluate_tool_policy(_actor("viewer"), _surface("dm"), "clickup_task_list_weekly")
        assert decision["allowed"] is True

    def test_meta_always_present(self):
        decision = evaluate_tool_policy(_actor("operator"), _surface("dm"), "clickup_task_create")
        assert "actor_role" in decision["meta"]
        assert "surface_type" in decision["meta"]
        assert "skill_id" in decision["meta"]


# ---------------------------------------------------------------------------
# 4. Integration: LLM orchestrator tool_call denied by policy
# ---------------------------------------------------------------------------


class TestLLMOrchestratorPolicyDenial:
    @pytest.mark.asyncio
    async def test_denied_tool_call_posts_message_skips_handler(self):
        """When policy denies a tool_call, the denial message is posted and handler is NOT called."""
        svc, slack = _make_mocks()
        session = FakeSession()
        result = _make_orchestrator_result(
            mode="tool_call",
            skill_id="clickup_task_list_weekly",
            args={"client_name": "Distex"},
        )

        deny_decision = PolicyDecision(
            allowed=False,
            reason_code="unknown_actor",
            user_message="I couldn't verify your identity.",
            meta={},
        )

        with (
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
            patch("app.api.routes.slack._check_tool_policy", new_callable=AsyncMock, return_value=deny_decision),
            patch("app.api.routes.slack._handle_weekly_tasks", new_callable=AsyncMock) as mock_handler,
        ):
            handled = await _try_llm_orchestrator(
                text="show tasks for Distex",
                slack_user_id="U123",
                channel="D123",
                session=session,
                session_service=svc,
                slack=slack,
            )

        assert handled is True
        mock_handler.assert_not_called()
        slack.post_message.assert_called()
        sent_text = slack.post_message.call_args.kwargs.get("text", "")
        assert "couldn't verify" in sent_text

    @pytest.mark.asyncio
    async def test_allowed_tool_call_executes_handler(self):
        """When policy allows, the handler IS called."""
        svc, slack = _make_mocks()
        session = FakeSession()
        result = _make_orchestrator_result(
            mode="tool_call",
            skill_id="clickup_task_list_weekly",
            args={"client_name": "Distex"},
        )

        allow_decision = PolicyDecision(
            allowed=True,
            reason_code="allowed",
            user_message="",
            meta={},
        )

        with (
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
            patch("app.api.routes.slack._check_tool_policy", new_callable=AsyncMock, return_value=allow_decision),
            patch("app.api.routes.slack._handle_weekly_tasks", new_callable=AsyncMock) as mock_handler,
        ):
            handled = await _try_llm_orchestrator(
                text="show tasks for Distex",
                slack_user_id="U123",
                channel="D123",
                session=session,
                session_service=svc,
                slack=slack,
            )

        assert handled is True
        mock_handler.assert_called_once()


# ---------------------------------------------------------------------------
# 5. Integration: deterministic path blocked by policy
# ---------------------------------------------------------------------------


class TestDeterministicPathPolicyDenial:
    @pytest.mark.asyncio
    async def test_deterministic_create_task_denied(self):
        """When policy denies create_task in deterministic path, handler is NOT called."""
        svc, slack = _make_mocks()

        deny_decision = PolicyDecision(
            allowed=False,
            reason_code="unknown_actor",
            user_message="I couldn't verify your identity.",
            meta={},
        )

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack._check_tool_policy", new_callable=AsyncMock, return_value=deny_decision),
            patch("app.api.routes.slack._handle_create_task", new_callable=AsyncMock) as mock_handler,
        ):
            await _handle_dm_event(
                slack_user_id="U123", channel="D123",
                text="create task for Distex: Fix bug",
            )

        mock_handler.assert_not_called()
        slack.post_message.assert_called()
        sent_text = slack.post_message.call_args.kwargs.get("text", "")
        assert "couldn't verify" in sent_text

    @pytest.mark.asyncio
    async def test_deterministic_weekly_tasks_denied(self):
        """When policy denies weekly_tasks in deterministic path, handler is NOT called."""
        svc, slack = _make_mocks()

        deny_decision = PolicyDecision(
            allowed=False,
            reason_code="unknown_actor",
            user_message="I couldn't verify your identity.",
            meta={},
        )

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack._check_tool_policy", new_callable=AsyncMock, return_value=deny_decision),
            patch("app.api.routes.slack._handle_weekly_tasks", new_callable=AsyncMock) as mock_handler,
        ):
            await _handle_dm_event(
                slack_user_id="U123", channel="D123",
                text="show tasks for Distex",
            )

        mock_handler.assert_not_called()
        slack.post_message.assert_called()

    @pytest.mark.asyncio
    async def test_deterministic_create_task_allowed(self):
        """When policy allows, deterministic create_task handler IS called."""
        svc, slack = _make_mocks()

        allow_decision = PolicyDecision(
            allowed=True,
            reason_code="allowed",
            user_message="",
            meta={},
        )

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack._check_tool_policy", new_callable=AsyncMock, return_value=allow_decision),
            patch("app.api.routes.slack._handle_create_task", new_callable=AsyncMock) as mock_handler,
        ):
            await _handle_dm_event(
                slack_user_id="U123", channel="D123",
                text="create task for Distex: Fix bug",
            )

        mock_handler.assert_called_once()
