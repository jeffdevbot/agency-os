"""Tests for C9B: LLM orchestrator integration into slack.py + token telemetry."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.api.routes.slack import (
    _handle_dm_event,
    _help_text,
    _is_deterministic_control_intent,
    _is_llm_orchestrator_enabled,
    _is_llm_strict_mode,
    _should_block_deterministic_intent,
    _try_planner,
    _try_llm_orchestrator,
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
    svc.get_brand_destination_for_client.return_value = {
        "id": "brand-1",
        "name": "Brand A",
        "clickup_space_id": "sp1",
        "clickup_list_id": "list1",
    }
    svc.get_profile_clickup_user_id.return_value = "12345"
    svc.list_clients_for_picker.return_value = [{"id": "c1", "name": "Acme"}]
    svc.touch_session.return_value = None
    svc.update_context.return_value = None
    slack = AsyncMock()
    return svc, slack


_ALLOW_POLICY = {"allowed": True, "reason_code": "allowed", "user_message": "", "meta": {}}


def _make_orchestrator_result(**overrides) -> OrchestratorResult:
    """Build a minimal OrchestratorResult with sensible defaults."""
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


# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------


class TestFeatureFlag:
    def test_flag_off_by_default(self):
        with patch.dict("os.environ", {}, clear=False):
            # Remove the flag if it exists
            import os
            os.environ.pop("AGENCYCLAW_LLM_DM_ORCHESTRATOR", None)
            assert _is_llm_orchestrator_enabled() is False

    @pytest.mark.parametrize("value", ["1", "true", "yes", "on", "True", "YES", "ON"])
    def test_flag_on_values(self, value: str):
        with patch.dict("os.environ", {"AGENCYCLAW_LLM_DM_ORCHESTRATOR": value}):
            assert _is_llm_orchestrator_enabled() is True

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", "", "banana"])
    def test_flag_off_values(self, value: str):
        with patch.dict("os.environ", {"AGENCYCLAW_LLM_DM_ORCHESTRATOR": value}):
            assert _is_llm_orchestrator_enabled() is False


class TestStrictModeHelpers:
    def test_llm_strict_mode_true_when_orchestrator_on_and_legacy_off(self):
        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack._is_legacy_intent_fallback_enabled", return_value=False),
        ):
            assert _is_llm_strict_mode() is True

    def test_llm_strict_mode_false_when_legacy_on(self):
        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack._is_legacy_intent_fallback_enabled", return_value=True),
        ):
            assert _is_llm_strict_mode() is False

    @pytest.mark.parametrize(
        "intent,expected",
        [
            ("switch_client", True),
            ("set_default_client", True),
            ("clear_defaults", True),
            ("create_task", False),
            ("weekly_tasks", False),
            ("cc_brand_list_all", False),
            ("help", False),
        ],
    )
    def test_deterministic_control_intent_allowlist(self, intent: str, expected: bool):
        assert _is_deterministic_control_intent(intent) is expected

    def test_should_block_deterministic_intent_in_strict_mode(self):
        with patch("app.api.routes.slack._is_llm_strict_mode", return_value=True):
            assert _should_block_deterministic_intent("create_task") is True
            assert _should_block_deterministic_intent("weekly_tasks") is True
            assert _should_block_deterministic_intent("switch_client") is False


# ---------------------------------------------------------------------------
# Flag OFF → legacy deterministic path (no orchestrator call)
# ---------------------------------------------------------------------------


class TestFlagOffLegacy:
    """When flag is OFF, _handle_dm_event must NOT call orchestrate_dm_message."""

    @pytest.mark.asyncio
    async def test_flag_off_uses_deterministic_classifier(self):
        svc, slack = _make_mocks()

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock) as mock_orch,
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="hello")

            # Orchestrator was NOT called
            mock_orch.assert_not_called()
            # Deterministic path sent help text (unknown intent → help)
            slack.post_message.assert_called()


# ---------------------------------------------------------------------------
# Flag ON → reply mode
# ---------------------------------------------------------------------------


class TestOrchestratorReplyMode:
    @pytest.mark.asyncio
    async def test_reply_sends_text(self):
        svc, slack = _make_mocks()
        result = _make_orchestrator_result(mode="reply", text="Hi there! How can I help?")

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock) as mock_log,
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="hello")

            # Reply text was sent
            slack.post_message.assert_called()
            sent_text = slack.post_message.call_args_list[0].kwargs.get("text", "")
            assert "Hi there" in sent_text

    @pytest.mark.asyncio
    async def test_reply_mode_does_not_invoke_planner(self):
        svc, slack = _make_mocks()
        result = _make_orchestrator_result(mode="reply", text="Just chatting.")

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack._try_planner", new_callable=AsyncMock) as mock_planner,
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="hey how are you?")

        mock_planner.assert_not_called()


# ---------------------------------------------------------------------------
# Flag ON → clarify mode
# ---------------------------------------------------------------------------


class TestOrchestratorClarifyMode:
    @pytest.mark.asyncio
    async def test_clarify_sends_question(self):
        svc, slack = _make_mocks()
        result = _make_orchestrator_result(
            mode="clarify",
            question="What should the task be called?",
            missing_fields=["task_title"],
        )

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="create a task")

            slack.post_message.assert_called()
            sent_text = slack.post_message.call_args_list[0].kwargs.get("text", "")
            assert "task be called" in sent_text


# ---------------------------------------------------------------------------
# Flag ON → tool_call mode (weekly tasks)
# ---------------------------------------------------------------------------


class TestOrchestratorToolCallWeekly:
    @pytest.mark.asyncio
    async def test_tool_call_weekly_routes_to_handler(self):
        svc, slack = _make_mocks()
        result = _make_orchestrator_result(
            mode="tool_call",
            skill_id="clickup_task_list_weekly",
            args={"client_name": "Distex"},
        )

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack._handle_weekly_tasks", new_callable=AsyncMock) as mock_weekly,
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
            patch("app.api.routes.slack._check_skill_policy", new_callable=AsyncMock, return_value=_ALLOW_POLICY),
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="show tasks for Distex")

            mock_weekly.assert_called_once()
            call_kwargs = mock_weekly.call_args.kwargs
            assert call_kwargs["client_name_hint"] == "Distex"

    @pytest.mark.asyncio
    async def test_tool_call_canonical_task_list_routes_to_handler(self):
        svc, slack = _make_mocks()
        result = _make_orchestrator_result(
            mode="tool_call",
            skill_id="clickup_task_list",
            args={"client_name": "Distex", "window": "this_month"},
        )

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack._handle_weekly_tasks", new_callable=AsyncMock) as mock_task_list,
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
            patch("app.api.routes.slack._check_skill_policy", new_callable=AsyncMock, return_value=_ALLOW_POLICY),
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="show tasks for Distex this month")

        mock_task_list.assert_called_once()
        call_kwargs = mock_task_list.call_args.kwargs
        assert call_kwargs["client_name_hint"] == "Distex"
        assert call_kwargs["window"] == "this_month"


# ---------------------------------------------------------------------------
# Flag ON → tool_call mode (task create)
# ---------------------------------------------------------------------------


class TestOrchestratorToolCallCreate:
    @pytest.mark.asyncio
    async def test_tool_call_create_routes_to_handler(self):
        svc, slack = _make_mocks()
        result = _make_orchestrator_result(
            mode="tool_call",
            skill_id="clickup_task_create",
            args={"client_name": "Distex", "task_title": "Fix landing page"},
        )

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack._handle_create_task", new_callable=AsyncMock) as mock_create,
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
            patch("app.api.routes.slack._check_skill_policy", new_callable=AsyncMock, return_value=_ALLOW_POLICY),
        ):
            await _handle_dm_event(
                slack_user_id="U123", channel="C1", text="create task for Distex: Fix landing page"
            )

            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs["task_title"] == "Fix landing page"
            assert call_kwargs["client_name_hint"] == "Distex"


class TestOrchestratorPlannerDelegation:
    @pytest.mark.asyncio
    async def test_plan_request_routes_to_planner(self):
        svc, slack = _make_mocks()
        result = _make_orchestrator_result(
            mode="plan_request",
            args={"request_text": "for distex list weekly tasks then create follow-ups"},
            skill_id=None,
        )

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack._try_planner", new_callable=AsyncMock, return_value=True) as mock_planner,
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="complex request")

        mock_planner.assert_called_once()
        planner_kwargs = mock_planner.call_args.kwargs
        assert planner_kwargs["text"] == "for distex list weekly tasks then create follow-ups"
        assert planner_kwargs["session_service"] is svc
        assert planner_kwargs["slack"] is slack

    @pytest.mark.asyncio
    async def test_plan_request_planner_disabled_returns_conversational_clarify(self):
        svc, slack = _make_mocks()
        result = _make_orchestrator_result(
            mode="plan_request",
            args={"request_text": "for distex list weekly tasks then create follow-ups"},
            skill_id=None,
        )

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack._is_legacy_intent_fallback_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack._try_planner", new_callable=AsyncMock, return_value=False),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="complex request")

        sent_text = slack.post_message.call_args_list[0].kwargs.get("text", "")
        assert "couldn't run planning" in sent_text.lower()
        assert sent_text != _help_text()
        assert "not sure what to do" not in sent_text.lower()

    @pytest.mark.asyncio
    async def test_plan_request_planner_error_returns_conversational_clarify(self):
        svc, slack = _make_mocks()
        result = _make_orchestrator_result(
            mode="plan_request",
            args={"request_text": "for distex list weekly tasks then create follow-ups"},
            skill_id=None,
        )

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack._is_legacy_intent_fallback_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack._try_planner", new_callable=AsyncMock, side_effect=RuntimeError("boom")),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="complex request")

        sent_text = slack.post_message.call_args_list[0].kwargs.get("text", "")
        assert "couldn't run planning" in sent_text.lower()
        assert sent_text != _help_text()
        assert "not sure what to do" not in sent_text.lower()

    @pytest.mark.asyncio
    async def test_plan_request_planner_unavailable_reroutes_control_intent(self):
        svc, slack = _make_mocks()
        result = _make_orchestrator_result(
            mode="plan_request",
            args={"request_text": "switch to Distex"},
            skill_id=None,
        )

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack._is_legacy_intent_fallback_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack._try_planner", new_callable=AsyncMock, return_value=False),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="switch to Distex")

        svc.set_active_client.assert_called_once()
        sent_text = slack.post_message.call_args_list[0].kwargs.get("text", "")
        assert "working on" in sent_text.lower()
        assert "couldn't run planning" not in sent_text.lower()

    @pytest.mark.asyncio
    async def test_planner_uses_existing_skill_rails(self):
        svc, slack = _make_mocks()
        session = svc.get_or_create_session.return_value

        fake_plan = {
            "intent": "multi_step",
            "steps": [
                {
                    "skill_id": "clickup_task_list_weekly",
                    "args": {"client_name": "Distex"},
                    "reason": "Get context first",
                },
                {
                    "skill_id": "clickup_task_create",
                    "args": {"client_name": "Distex", "task_title": "Follow up blockers"},
                    "reason": "Create follow-up action",
                },
            ],
            "confidence": 0.85,
        }
        fake_result = {"steps_attempted": 2, "steps_succeeded": 2, "step_results": []}

        with (
            patch("app.api.routes.slack._is_planner_enabled", return_value=True),
            patch("app.api.routes.slack.generate_plan", new_callable=AsyncMock, return_value=fake_plan),
            patch("app.api.routes.slack.execute_plan", new_callable=AsyncMock, return_value=fake_result) as mock_exec,
            patch("app.api.routes.slack.retrieve_kb_context", new_callable=AsyncMock, return_value={"sources": []}),
        ):
            handled = await _try_planner(
                text="complex request",
                slack_user_id="U123",
                channel="C1",
                session=session,
                session_service=svc,
                slack=slack,
            )

        assert handled is True
        exec_kwargs = mock_exec.call_args.kwargs
        assert exec_kwargs["handler_map"]["clickup_task_create"].__name__ == "_handle_create_task"
        assert exec_kwargs["handler_map"]["clickup_task_list_weekly"].__name__ == "_handle_weekly_tasks"
        assert exec_kwargs["handler_map"]["clickup_task_list"].__name__ == "_handle_weekly_tasks"
        assert exec_kwargs["check_policy"].__name__ == "_check_skill_policy"

    @pytest.mark.asyncio
    async def test_planner_executes_cc_skill_via_allowlist_handler_map(self):
        svc, slack = _make_mocks()
        session = svc.get_or_create_session.return_value

        fake_plan = {
            "intent": "cc_lookup",
            "steps": [
                {
                    "skill_id": "cc_brand_list_all",
                    "args": {"client_name": "Distex"},
                    "reason": "List brands for client context",
                },
            ],
            "confidence": 0.8,
        }

        with (
            patch("app.api.routes.slack._is_planner_enabled", return_value=True),
            patch("app.api.routes.slack.generate_plan", new_callable=AsyncMock, return_value=fake_plan),
            patch("app.api.routes.slack.retrieve_kb_context", new_callable=AsyncMock, return_value={"sources": []}),
            patch("app.api.routes.slack._check_skill_policy", new_callable=AsyncMock, return_value=_ALLOW_POLICY),
            patch("app.api.routes.slack._handle_cc_skill", new_callable=AsyncMock, return_value="[Listed brands]") as mock_cc,
        ):
            handled = await _try_planner(
                text="show brands for distex",
                slack_user_id="U123",
                channel="C1",
                session=session,
                session_service=svc,
                slack=slack,
            )

        assert handled is True
        mock_cc.assert_called_once()
        call_kwargs = mock_cc.call_args.kwargs
        assert call_kwargs["skill_id"] == "cc_brand_list_all"
        assert call_kwargs["args"]["client_name"] == "Distex"


# ---------------------------------------------------------------------------
# Flag ON → fallback mode → deterministic classifier
# ---------------------------------------------------------------------------


class TestOrchestratorFallbackMode:
    @pytest.mark.asyncio
    async def test_fallback_falls_through_to_deterministic(self):
        svc, slack = _make_mocks()
        result = _make_orchestrator_result(
            mode="fallback",
            reason="OpenAI timeout",
            tokens_in=None,
            tokens_out=None,
            tokens_total=None,
            model_used=None,
        )

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock) as mock_log,
        ):
            # Send "hello" which the deterministic classifier maps to "help"
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="hello")

            # Should have sent help text via deterministic path
            slack.post_message.assert_called()

    @pytest.mark.asyncio
    async def test_fallback_llm_strict_does_not_execute_weekly_deterministically(self):
        svc, slack = _make_mocks()
        result = _make_orchestrator_result(
            mode="fallback",
            reason="OpenAI timeout",
            tokens_in=None,
            tokens_out=None,
            tokens_total=None,
            model_used=None,
        )

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack._is_legacy_intent_fallback_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack._try_planner", new_callable=AsyncMock) as mock_planner,
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
            patch("app.api.routes.slack._handle_weekly_tasks", new_callable=AsyncMock) as mock_weekly,
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="show tasks for Distex")

        mock_planner.assert_not_called()
        mock_weekly.assert_not_called()
        sent_text = slack.post_message.call_args_list[0].kwargs.get("text", "")
        assert "not sure what to do" in sent_text.lower()


# ---------------------------------------------------------------------------
# Token logger called on successful LLM call
# ---------------------------------------------------------------------------


class TestTokenTelemetry:
    @pytest.mark.asyncio
    async def test_token_logger_called_on_success(self):
        svc, slack = _make_mocks()
        result = _make_orchestrator_result(mode="reply", text="Hello!")

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock) as mock_log,
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="hello")

            mock_log.assert_called_once()
            log_kwargs = mock_log.call_args.kwargs
            assert log_kwargs["tool"] == "agencyclaw"
            assert log_kwargs["stage"] == "intent_parse"
            assert log_kwargs["prompt_tokens"] == 50
            assert log_kwargs["completion_tokens"] == 30
            assert log_kwargs["total_tokens"] == 80
            assert log_kwargs["model"] == "gpt-4o-mini"
            assert log_kwargs["user_id"] == "profile-1"
            assert log_kwargs["meta"]["mode"] == "reply"

    @pytest.mark.asyncio
    async def test_token_logger_not_called_on_fallback(self):
        """Fallback mode has no tokens — logger should not be called."""
        svc, slack = _make_mocks()
        result = _make_orchestrator_result(
            mode="fallback",
            reason="timeout",
            tokens_in=None,
            tokens_out=None,
            tokens_total=None,
            model_used=None,
        )

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock) as mock_log,
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="hello")

            # Token logger should NOT have been called (no tokens_in)
            mock_log.assert_not_called()


# ---------------------------------------------------------------------------
# Token logger failure does not break response path
# ---------------------------------------------------------------------------


class TestTokenLoggerResilience:
    @pytest.mark.asyncio
    async def test_token_logger_failure_does_not_break_response(self):
        svc, slack = _make_mocks()
        result = _make_orchestrator_result(mode="reply", text="All good!")

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch(
                "app.api.routes.slack.log_ai_token_usage",
                new_callable=AsyncMock,
                side_effect=RuntimeError("DB down"),
            ),
        ):
            # Should NOT raise — logger failure is swallowed
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="hello")

            # Reply was still sent despite logger failure
            slack.post_message.assert_called()
            sent_text = slack.post_message.call_args_list[0].kwargs.get("text", "")
            assert "All good" in sent_text
