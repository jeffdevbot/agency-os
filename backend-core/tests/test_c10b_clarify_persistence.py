"""Tests for C10B/C10B.5 polish: clarify-state persistence, client resolution
hardening, history deduplication, and tool_call history persistence.

Covers:
- Regression fixtures R1 (distex coupon drift) and R2 (roger loop title)
- Orchestrator passes through skill_id/args on clarify
- Enriched system prompt includes pending details (no duplicated history)
- slack.py sets pending_task_create when clarify targets a mutation skill
- Client resolution hardening: empty hint uses active-client fallback
- tool_call path persists conversation history
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.api.routes.slack import (
    _handle_dm_event,
    _handle_pending_task_continuation,
    _try_llm_orchestrator,
)
from app.services.agencyclaw.openai_client import ChatCompletionResult
from app.services.agencyclaw.slack_orchestrator import (
    OrchestratorResult,
    _build_system_prompt,
    orchestrate_dm_message,
)


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
    svc.get_brands_with_context_for_client.return_value = [
        {"id": "brand-1", "name": "Brand A", "clickup_space_id": "sp1", "clickup_list_id": "list1"},
    ]
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


def _fake_completion(content_dict: dict) -> ChatCompletionResult:
    return ChatCompletionResult(
        content=json.dumps(content_dict),
        tokens_in=50,
        tokens_out=30,
        tokens_total=80,
        model="gpt-4o-mini",
        duration_ms=200,
    )


def _find_pending_update(svc: MagicMock) -> dict | None:
    """Extract the pending_task_create dict from update_context calls, if any."""
    for c in svc.update_context.call_args_list:
        args = c[0] if c[0] else ()
        if len(args) >= 2 and isinstance(args[1], dict) and "pending_task_create" in args[1]:
            return args[1]["pending_task_create"]
    return None


def _find_exchanges_update(svc: MagicMock) -> list | None:
    """Extract the recent_exchanges list from update_context calls, if any."""
    for c in svc.update_context.call_args_list:
        args = c[0] if c[0] else ()
        if len(args) >= 2 and isinstance(args[1], dict) and "recent_exchanges" in args[1]:
            return args[1]["recent_exchanges"]
    return None


# ---------------------------------------------------------------------------
# 1. Orchestrator: skill_id/args pass-through on clarify
# ---------------------------------------------------------------------------


class TestOrchestratorClarifyPassthrough:
    """C10B: Orchestrator must return skill_id and args on clarify results."""

    @pytest.mark.asyncio
    async def test_validation_promoted_clarify_includes_skill_id(self):
        """When tool_call has missing required fields, promoted clarify keeps skill_id+args."""
        llm_response = _fake_completion({
            "mode": "tool_call",
            "skill_id": "clickup_task_create",
            "args": {"client_name": "Distex"},  # missing task_title
            "confidence": 0.85,
        })

        with patch(
            "app.services.agencyclaw.slack_orchestrator.call_chat_completion",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            result = await orchestrate_dm_message(
                text="create task for Distex",
                profile_id="p1",
                slack_user_id="U1",
                session_context={},
                client_context_pack="",
            )

        assert result["mode"] == "clarify"
        assert result["skill_id"] == "clickup_task_create"
        assert result["args"] == {"client_name": "Distex"}
        assert "task_title" in result["missing_fields"]

    @pytest.mark.asyncio
    async def test_llm_direct_clarify_includes_skill_id(self):
        """When LLM returns clarify with skill_id, it's passed through."""
        llm_response = _fake_completion({
            "mode": "clarify",
            "skill_id": "clickup_task_create",
            "args": {"client_name": "Roger"},
            "question": "What should the task title be?",
            "missing_fields": ["task_title"],
            "confidence": 0.8,
        })

        with patch(
            "app.services.agencyclaw.slack_orchestrator.call_chat_completion",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            result = await orchestrate_dm_message(
                text="create task for roger",
                profile_id="p1",
                slack_user_id="U1",
                session_context={},
                client_context_pack="",
            )

        assert result["mode"] == "clarify"
        assert result["skill_id"] == "clickup_task_create"
        assert result["args"] == {"client_name": "Roger"}

    @pytest.mark.asyncio
    async def test_llm_clarify_without_skill_id_returns_none(self):
        """Generic clarify (no skill_id from LLM) returns None for skill_id."""
        llm_response = _fake_completion({
            "mode": "clarify",
            "question": "Could you be more specific?",
            "missing_fields": [],
            "confidence": 0.5,
        })

        with patch(
            "app.services.agencyclaw.slack_orchestrator.call_chat_completion",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            result = await orchestrate_dm_message(
                text="do something",
                profile_id="p1",
                slack_user_id="U1",
                session_context={},
                client_context_pack="",
            )

        assert result["mode"] == "clarify"
        assert result["skill_id"] is None
        assert result["args"] is None


# ---------------------------------------------------------------------------
# 2. System prompt enrichment + no history duplication
# ---------------------------------------------------------------------------


class TestEnrichedSystemPrompt:
    def test_pending_state_shows_awaiting_and_client(self):
        """System prompt includes pending task details, not just 'in progress'."""
        prompt = _build_system_prompt(
            client_context_pack="Active client: Distex",
            session_context={
                "active_client_id": "client-1",
                "pending_task_create": {
                    "awaiting": "title",
                    "client_id": "client-1",
                    "client_name": "Distex",
                },
            },
        )

        assert "Awaiting: title" in prompt
        assert "Client: Distex" in prompt

    def test_pending_state_shows_title_when_present(self):
        prompt = _build_system_prompt(
            client_context_pack="",
            session_context={
                "pending_task_create": {
                    "awaiting": "confirm_or_details",
                    "client_id": "client-1",
                    "client_name": "Distex",
                    "task_title": "Setup coupons",
                },
            },
        )

        assert "Title: Setup coupons" in prompt
        assert "Awaiting: confirm_or_details" in prompt

    def test_no_pending_state_shows_default(self):
        prompt = _build_system_prompt(
            client_context_pack="",
            session_context={},
        )

        assert "No active session state" in prompt

    def test_no_history_transcript_in_system_prompt(self):
        """System prompt must NOT contain a 'Recent conversation' transcript block.

        History is injected only via role-based messages — never duplicated.
        """
        prompt = _build_system_prompt(
            client_context_pack="",
            session_context={},
        )

        assert "Recent conversation" not in prompt
        assert "No prior conversation" not in prompt


# ---------------------------------------------------------------------------
# 3. slack.py: clarify sets pending state for task_create
# ---------------------------------------------------------------------------


class TestClarifySetsPendingState:
    @pytest.mark.asyncio
    async def test_clarify_for_task_create_sets_pending_title(self):
        """When clarify targets clickup_task_create with missing title, pending state is set."""
        svc, slack = _make_mocks()
        session = FakeSession()
        result = _make_orchestrator_result(
            mode="clarify",
            skill_id="clickup_task_create",
            args={"client_name": "Distex"},
            question="What should the task be called?",
            missing_fields=["task_title"],
        )

        with (
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
        ):
            handled = await _try_llm_orchestrator(
                text="create task for Distex",
                slack_user_id="U123",
                channel="C1",
                session=session,
                session_service=svc,
                slack=slack,
            )

        assert handled is True
        pending = _find_pending_update(svc)
        assert pending is not None, f"pending_task_create not set: {svc.update_context.call_args_list}"
        assert pending["awaiting"] == "title"
        assert pending["client_id"] == "client-1"
        assert pending["client_name"] == "Distex"
        slack.post_message.assert_called()

    @pytest.mark.asyncio
    async def test_clarify_without_skill_id_no_pending(self):
        """Generic clarify (no skill_id) should NOT set pending_task_create."""
        svc, slack = _make_mocks()
        session = FakeSession()
        result = _make_orchestrator_result(
            mode="clarify",
            question="Could you be more specific?",
            missing_fields=[],
        )

        with (
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
        ):
            handled = await _try_llm_orchestrator(
                text="do something",
                slack_user_id="U123",
                channel="C1",
                session=session,
                session_service=svc,
                slack=slack,
            )

        assert handled is True
        pending = _find_pending_update(svc)
        assert pending is None

    @pytest.mark.asyncio
    async def test_clarify_with_title_sets_confirm_or_details(self):
        """When clarify has task_title, pending should be confirm_or_details."""
        svc, slack = _make_mocks()
        session = FakeSession()
        result = _make_orchestrator_result(
            mode="clarify",
            skill_id="clickup_task_create",
            args={"client_name": "Distex", "task_title": "Fix coupons"},
            question="Should I add a description?",
            missing_fields=["task_description"],
        )

        with (
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
        ):
            handled = await _try_llm_orchestrator(
                text="create task for Distex: Fix coupons",
                slack_user_id="U123",
                channel="C1",
                session=session,
                session_service=svc,
                slack=slack,
            )

        assert handled is True
        pending = _find_pending_update(svc)
        assert pending is not None
        assert pending["awaiting"] == "confirm_or_details"
        assert pending["task_title"] == "Fix coupons"
        assert "timestamp" in pending


# ---------------------------------------------------------------------------
# 3b. Client resolution hardening
# ---------------------------------------------------------------------------


class TestClarifyClientResolution:
    @pytest.mark.asyncio
    async def test_empty_client_hint_uses_active_client(self):
        """When LLM clarify has no client_name but session has active client,
        pending should use the active client."""
        svc, slack = _make_mocks()
        # Session has active_client_id="client-1", get_client_name returns "Distex"
        session = FakeSession(active_client_id="client-1")
        result = _make_orchestrator_result(
            mode="clarify",
            skill_id="clickup_task_create",
            args={},  # no client_name
            question="What should the task be called?",
            missing_fields=["task_title"],
        )

        with (
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
        ):
            handled = await _try_llm_orchestrator(
                text="create a task",
                slack_user_id="U123",
                channel="C1",
                session=session,
                session_service=svc,
                slack=slack,
            )

        assert handled is True
        pending = _find_pending_update(svc)
        assert pending is not None
        assert pending["client_id"] == "client-1"
        assert pending["client_name"] == "Distex"

    @pytest.mark.asyncio
    async def test_no_client_no_active_client_posts_picker_no_pending(self):
        """When LLM clarify has no client_name AND no active client,
        a picker is posted and NO pending_task_create is written."""
        svc, slack = _make_mocks()
        # Session with no active client
        session = FakeSession(active_client_id=None)
        result = _make_orchestrator_result(
            mode="clarify",
            skill_id="clickup_task_create",
            args={},  # no client_name
            question="What should the task be called?",
            missing_fields=["task_title"],
        )

        with (
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
        ):
            handled = await _try_llm_orchestrator(
                text="create a task",
                slack_user_id="U123",
                channel="C1",
                session=session,
                session_service=svc,
                slack=slack,
            )

        assert handled is True  # handled (picker posted)
        pending = _find_pending_update(svc)
        assert pending is None, "pending_task_create must NOT be written without a resolved client"
        # Picker/error message should have been posted
        slack.post_message.assert_called()


# ---------------------------------------------------------------------------
# 3c. tool_call path persists conversation history
# ---------------------------------------------------------------------------


class TestToolCallHistoryPersistence:
    _ALLOW_POLICY = {"allowed": True, "reason_code": "allowed", "user_message": "", "meta": {}}

    @pytest.mark.asyncio
    async def test_weekly_tasks_persists_exchange(self):
        """After tool_call for weekly tasks, recent_exchanges is updated."""
        svc, slack = _make_mocks()
        session = FakeSession()
        result = _make_orchestrator_result(
            mode="tool_call",
            skill_id="clickup_task_list_weekly",
            args={"client_name": "Distex"},
        )

        with (
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
            patch("app.api.routes.slack._handle_weekly_tasks", new_callable=AsyncMock),
            patch("app.api.routes.slack._check_tool_policy", new_callable=AsyncMock, return_value=self._ALLOW_POLICY),
        ):
            handled = await _try_llm_orchestrator(
                text="show tasks for Distex",
                slack_user_id="U123",
                channel="C1",
                session=session,
                session_service=svc,
                slack=slack,
            )

        assert handled is True
        exchanges = _find_exchanges_update(svc)
        assert exchanges is not None, "recent_exchanges should be persisted after tool_call"
        assert len(exchanges) == 1
        assert exchanges[0]["user"] == "show tasks for Distex"
        assert "weekly task list" in exchanges[0]["assistant"].lower()

    @pytest.mark.asyncio
    async def test_create_task_persists_exchange(self):
        """After tool_call for task create, recent_exchanges is updated."""
        svc, slack = _make_mocks()
        session = FakeSession()
        result = _make_orchestrator_result(
            mode="tool_call",
            skill_id="clickup_task_create",
            args={"client_name": "Distex", "task_title": "Fix bug"},
        )

        with (
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
            patch("app.api.routes.slack._handle_create_task", new_callable=AsyncMock),
            patch("app.api.routes.slack._check_tool_policy", new_callable=AsyncMock, return_value=self._ALLOW_POLICY),
        ):
            handled = await _try_llm_orchestrator(
                text="create task for Distex: Fix bug",
                slack_user_id="U123",
                channel="C1",
                session=session,
                session_service=svc,
                slack=slack,
            )

        assert handled is True
        exchanges = _find_exchanges_update(svc)
        assert exchanges is not None
        assert len(exchanges) == 1
        assert exchanges[0]["user"] == "create task for Distex: Fix bug"
        assert "task creation" in exchanges[0]["assistant"].lower()


# ---------------------------------------------------------------------------
# 4. Regression Fixture R1: Distex Coupon Drift
# ---------------------------------------------------------------------------


class TestR1DistexCouponDrift:
    """R1: create task for Distex -> title requested -> user provides coupon intent
    details -> must stay in pending mutation flow and avoid generic reply drift.

    Transcript:
      User: "create task for Distex"
      Bot: "What should the task be called?" (clarify, sets pending awaiting=title)
      User: "setup coupons for their store"
      Bot: Must treat as title, show confirm flow (NOT re-classify as generic intent)
    """

    @pytest.mark.asyncio
    async def test_r1_title_captured_not_drifted(self):
        svc, slack = _make_mocks()

        # --- Turn 1: LLM returns clarify for task_create missing title ---
        clarify_result = _make_orchestrator_result(
            mode="clarify",
            skill_id="clickup_task_create",
            args={"client_name": "Distex"},
            question="What should the task be called for Distex?",
            missing_fields=["task_title"],
        )

        session_t1 = FakeSession()

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=clarify_result),
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="create task for Distex")

        # Verify question was posted
        assert any(
            "task be called" in str(c) for c in slack.post_message.call_args_list
        ), "Bot should have asked for task title"

        # Verify pending_task_create was set with awaiting=title
        pending = _find_pending_update(svc)
        assert pending is not None and pending.get("awaiting") == "title", \
            "pending_task_create with awaiting=title must be set"

        # --- Turn 2: User provides "setup coupons for their store" ---
        svc.reset_mock()
        slack.reset_mock()

        session_t2 = FakeSession(context={
            "pending_task_create": {
                "awaiting": "title",
                "client_id": "client-1",
                "client_name": "Distex",
            }
        })
        svc.get_or_create_session.return_value = session_t2

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock) as mock_orch,
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
        ):
            await _handle_dm_event(
                slack_user_id="U123", channel="C1",
                text="setup coupons for their store",
            )

        # The LLM orchestrator should NOT have been called because
        # pending_task_create handler consumed the message
        mock_orch.assert_not_called()

        # The bot should have posted a confirmation block (title accepted)
        assert slack.post_message.called
        sent = str(slack.post_message.call_args_list)
        assert "setup coupons for their store" in sent or "confirm" in sent.lower() or "Create" in sent


# ---------------------------------------------------------------------------
# 5. Regression Fixture R2: Roger Loop Title
# ---------------------------------------------------------------------------


class TestR2RogerLoopTitle:
    """R2: create tasks for roger -> title requested -> ambiguous follow-ups
    -> must converge without looping title prompt indefinitely.

    Transcript:
      User: "can you create tasks for roger"
      Bot: clarify -> sets pending awaiting=title
      User: "jsut create it"
      Bot: Must treat as title and move to confirm (not loop asking for title)
    """

    @pytest.mark.asyncio
    async def test_r2_ambiguous_followup_converges(self):
        svc, slack = _make_mocks()
        svc.find_client_matches.return_value = [{"id": "client-2", "name": "Roger"}]
        svc.get_client_name.return_value = "Roger"

        # Simulate: pending state already set from turn 1 (clarify)
        session = FakeSession(context={
            "pending_task_create": {
                "awaiting": "title",
                "client_id": "client-2",
                "client_name": "Roger",
            }
        })
        svc.get_or_create_session.return_value = session

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock) as mock_orch,
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
        ):
            await _handle_dm_event(
                slack_user_id="U123", channel="C1",
                text="jsut create it",
            )

        # LLM should NOT have been called -- pending handler consumed it
        mock_orch.assert_not_called()

        # Confirm flow reached: bot posted confirm block or message with title
        assert slack.post_message.called
        sent = str(slack.post_message.call_args_list)
        assert "jsut create it" in sent or "Create Task" in sent or "confirm" in sent.lower()

        # Pending state should now be confirm_or_details, not still title
        pending = _find_pending_update(svc)
        assert pending is not None and pending.get("awaiting") == "confirm_or_details", \
            "Should have transitioned to confirm_or_details state"

    @pytest.mark.asyncio
    async def test_r2_make_one_up_converges(self):
        """'make one up for me?' should also be consumed as title, not loop."""
        svc, slack = _make_mocks()
        svc.find_client_matches.return_value = [{"id": "client-2", "name": "Roger"}]

        session = FakeSession(context={
            "pending_task_create": {
                "awaiting": "title",
                "client_id": "client-2",
                "client_name": "Roger",
            }
        })
        svc.get_or_create_session.return_value = session

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock) as mock_orch,
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
        ):
            await _handle_dm_event(
                slack_user_id="U123", channel="C1",
                text="make one up for me?",
            )

        mock_orch.assert_not_called()
        assert slack.post_message.called
