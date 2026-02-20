"""Tests for C11F-A: Conversational runtime cleanup (LLM-first, no command menus).

Covers:
- LLM-first mode: off-topic messages get natural replies, not command menus
- LLM reply path works for conversational questions
- Skill requests still invoke deterministic execution after orchestrator tool_call
- Legacy mode still supports deterministic classifier when explicitly enabled
- Orchestrator prompt encourages reply mode for ambiguous/off-topic messages
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.routes.slack import _handle_dm_event, _help_text
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


_ALLOW_POLICY = {"allowed": True, "reason_code": "allowed", "user_message": "", "meta": {}}


# ---------------------------------------------------------------------------
# LLM-first mode: off-topic gets natural reply, not command menu
# ---------------------------------------------------------------------------


class TestLLMFirstNoCommandMenu:
    """When LLM orchestrator is ON and returns reply for off-topic, no command menu."""

    @pytest.mark.asyncio
    async def test_off_topic_gets_natural_reply(self):
        """'Where are you from?' should get a conversational reply, not a command list."""
        svc, slack = _make_mocks()
        result = _make_orchestrator_result(
            mode="reply",
            text="I'm AgencyClaw, your agency operations assistant! I live in the cloud.",
        )

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
        ):
            await _handle_dm_event(slack_user_id="U123", channel="D1", text="Where are you from?")

        sent_text = slack.post_message.call_args_list[0].kwargs.get("text", "")
        assert "agencyclaw" in sent_text.lower() or "cloud" in sent_text.lower()
        # Must NOT contain command-style guidance
        assert "create task" not in sent_text.lower()
        assert "switch to" not in sent_text.lower()

    @pytest.mark.asyncio
    async def test_greeting_gets_natural_reply(self):
        svc, slack = _make_mocks()
        result = _make_orchestrator_result(
            mode="reply",
            text="Hey! What can I help you with today?",
        )

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
        ):
            await _handle_dm_event(slack_user_id="U123", channel="D1", text="hello!")

        sent_text = slack.post_message.call_args_list[0].kwargs.get("text", "")
        assert "help" in sent_text.lower()
        # No command menu
        assert "- " not in sent_text or "show me clients" not in sent_text.lower()


class TestLLMFallbackNoCommandMenu:
    """When LLM orchestrator returns fallback, the catch-all should NOT be a command menu."""

    @pytest.mark.asyncio
    async def test_fallback_then_unrecognized_intent_no_command_list(self):
        """LLM fallback + classifier=help -> natural nudge, not command list."""
        svc, slack = _make_mocks()
        result = _make_orchestrator_result(
            mode="fallback",
            reason="JSON parse failure",
        )

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack._is_legacy_intent_fallback_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
        ):
            await _handle_dm_event(slack_user_id="U123", channel="D1", text="tell me a joke")

        sent_text = slack.post_message.call_args_list[0].kwargs.get("text", "")
        # Should NOT contain the legacy help text with command examples
        help_text = _help_text()
        assert sent_text != help_text
        assert "create a task for" not in sent_text.lower()
        assert "start n-gram research" not in sent_text.lower()

    @pytest.mark.asyncio
    async def test_fallback_non_control_intent_does_not_dispatch_cc_skill(self):
        """LLM fallback + legacy-off: non-control CC intents must not dispatch deterministically."""
        svc, slack = _make_mocks()
        result = _make_orchestrator_result(
            mode="fallback",
            reason="JSON parse failure",
        )

        mock_cc = AsyncMock(return_value="[Listed brands]")

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack._is_legacy_intent_fallback_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
            patch("app.api.routes.slack._check_skill_policy", new_callable=AsyncMock, return_value=_ALLOW_POLICY),
            patch("app.api.routes.slack._handle_cc_skill", mock_cc),
        ):
            await _handle_dm_event(slack_user_id="U123", channel="D1", text="list brands")

        mock_cc.assert_not_called()
        sent_text = slack.post_message.call_args_list[0].kwargs.get("text", "")
        assert sent_text != _help_text()
        assert "not sure what to do" in sent_text.lower()


class TestLLMFallbackStructuralIntentStillWorks:
    """LLM fallback + control intent still dispatches deterministically."""

    @pytest.mark.asyncio
    async def test_switch_client_works_after_fallback(self):
        svc, slack = _make_mocks()
        result = _make_orchestrator_result(mode="fallback", reason="timeout")

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack._is_legacy_intent_fallback_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
        ):
            await _handle_dm_event(slack_user_id="U123", channel="D1", text="switch to Distex")

        # Should have processed the switch (post_message called for switch confirmation)
        sent_text = slack.post_message.call_args_list[0].kwargs.get("text", "")
        assert "distex" in sent_text.lower() or "switched" in sent_text.lower() or "working on" in sent_text.lower()

    @pytest.mark.asyncio
    async def test_create_task_not_dispatched_in_llm_strict_mode(self):
        svc, slack = _make_mocks()
        result = _make_orchestrator_result(mode="fallback", reason="timeout")

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack._is_legacy_intent_fallback_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
            patch("app.api.routes.slack._handle_create_task", new_callable=AsyncMock) as mock_create,
        ):
            await _handle_dm_event(slack_user_id="U123", channel="D1", text="create task for Distex: Fix title")

        mock_create.assert_not_called()
        sent_text = slack.post_message.call_args_list[0].kwargs.get("text", "")
        assert "not sure what to do" in sent_text.lower()

    @pytest.mark.asyncio
    async def test_weekly_tasks_not_dispatched_in_llm_strict_mode(self):
        svc, slack = _make_mocks()
        result = _make_orchestrator_result(mode="fallback", reason="timeout")

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack._is_legacy_intent_fallback_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
            patch("app.api.routes.slack._handle_weekly_tasks", new_callable=AsyncMock) as mock_weekly,
        ):
            await _handle_dm_event(slack_user_id="U123", channel="D1", text="show tasks for Distex")

        mock_weekly.assert_not_called()
        sent_text = slack.post_message.call_args_list[0].kwargs.get("text", "")
        assert "not sure what to do" in sent_text.lower()


# ---------------------------------------------------------------------------
# Legacy mode: deterministic classifier still works when explicitly enabled
# ---------------------------------------------------------------------------


class TestLegacyModeStillWorks:
    @pytest.mark.asyncio
    async def test_legacy_mode_shows_help_text(self):
        """When legacy intents are ON, unrecognized messages get the full help text."""
        svc, slack = _make_mocks()

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
        ):
            await _handle_dm_event(slack_user_id="U123", channel="D1", text="tell me a joke")

        sent_text = slack.post_message.call_args_list[0].kwargs.get("text", "")
        assert sent_text == _help_text()

    @pytest.mark.asyncio
    async def test_legacy_mode_with_explicit_flag_shows_help(self):
        """Even with LLM ON, explicit ENABLE_LEGACY_INTENTS=1 restores help text."""
        svc, slack = _make_mocks()
        result = _make_orchestrator_result(mode="fallback", reason="timeout")

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack._is_legacy_intent_fallback_enabled", return_value=True),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
        ):
            await _handle_dm_event(slack_user_id="U123", channel="D1", text="tell me a joke")

        sent_text = slack.post_message.call_args_list[0].kwargs.get("text", "")
        assert sent_text == _help_text()

    @pytest.mark.asyncio
    async def test_legacy_mode_with_explicit_flag_allows_deterministic_create(self):
        svc, slack = _make_mocks()
        result = _make_orchestrator_result(mode="fallback", reason="timeout")

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack._is_legacy_intent_fallback_enabled", return_value=True),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
            patch("app.api.routes.slack._check_skill_policy", new_callable=AsyncMock, return_value=_ALLOW_POLICY),
            patch("app.api.routes.slack._handle_create_task", new_callable=AsyncMock) as mock_create,
        ):
            await _handle_dm_event(slack_user_id="U123", channel="D1", text="create task for Distex: Fix landing page")

        mock_create.assert_called_once()


# ---------------------------------------------------------------------------
# Skill requests still route through deterministic execution after tool_call
# ---------------------------------------------------------------------------


class TestSkillExecutionStillDeterministic:
    @pytest.mark.asyncio
    async def test_tool_call_weekly_tasks_routes_to_handler(self):
        """LLM returns tool_call -> handler is invoked (not a conversational reply)."""
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
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
            patch("app.api.routes.slack._check_skill_policy", new_callable=AsyncMock, return_value=_ALLOW_POLICY),
            patch("app.api.routes.slack._handle_weekly_tasks", new_callable=AsyncMock) as mock_weekly,
        ):
            await _handle_dm_event(slack_user_id="U123", channel="D1", text="show tasks for Distex")

        mock_weekly.assert_called_once()


# ---------------------------------------------------------------------------
# Orchestrator prompt content checks
# ---------------------------------------------------------------------------


class TestOrchestratorPromptContent:
    def test_prompt_mentions_conversational_reply(self):
        """System prompt should explicitly instruct reply mode for off-topic/conversational."""
        from app.services.agencyclaw.slack_orchestrator import _build_system_prompt

        prompt = _build_system_prompt("", {})
        assert "conversational" in prompt.lower() or "off-topic" in prompt.lower()
        assert "reply" in prompt.lower()

    def test_prompt_discourages_command_menus(self):
        from app.services.agencyclaw.slack_orchestrator import _build_system_prompt

        prompt = _build_system_prompt("", {})
        assert "command" in prompt.lower()
        # Should say NOT to list commands
        assert "do not" in prompt.lower() or "never" in prompt.lower()

    def test_prompt_defaults_to_reply_for_ambiguous(self):
        from app.services.agencyclaw.slack_orchestrator import _build_system_prompt

        prompt = _build_system_prompt("", {})
        assert "default" in prompt.lower() and "reply" in prompt.lower()
