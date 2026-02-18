"""Tests for AgencyClaw Slack DM orchestrator (C9A)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.services.agencyclaw.openai_client import ChatCompletionResult, OpenAIError
from app.services.agencyclaw.slack_orchestrator import orchestrate_dm_message
from app.services.agencyclaw.tool_registry import (
    TOOL_SCHEMAS,
    get_missing_required_fields,
    get_tool_descriptions_for_prompt,
    validate_tool_call,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_completion(content_dict: dict) -> ChatCompletionResult:
    """Build a fake ChatCompletionResult wrapping a JSON payload."""
    return ChatCompletionResult(
        content=json.dumps(content_dict),
        tokens_in=50,
        tokens_out=30,
        tokens_total=80,
        model="gpt-4o-mini",
        duration_ms=200,
    )


_DEFAULT_KWARGS = dict(
    profile_id="profile-1",
    slack_user_id="U123",
    session_context={},
    client_context_pack="## Active Tasks\n- Fix landing page [in progress]",
)


# ---------------------------------------------------------------------------
# Tool registry (sync, no mocks)
# ---------------------------------------------------------------------------


class TestToolRegistry:
    def test_validate_known_skill_valid_args(self):
        errors = validate_tool_call(
            "clickup_task_create",
            {"task_title": "Fix bug", "client_name": "Distex"},
        )
        assert errors == []

    def test_validate_unknown_skill(self):
        errors = validate_tool_call("nonexistent_skill", {})
        assert len(errors) == 1
        assert "Unknown skill" in errors[0]

    def test_validate_missing_required_field(self):
        errors = validate_tool_call("clickup_task_create", {"client_name": "Distex"})
        assert any("task_title" in e for e in errors)

    def test_validate_empty_required_field(self):
        errors = validate_tool_call("clickup_task_create", {"task_title": "  ", "client_name": "Distex"})
        assert any("task_title" in e for e in errors)

    def test_validate_weekly_tasks_no_required(self):
        errors = validate_tool_call("clickup_task_list_weekly", {})
        assert errors == []

    def test_validate_unknown_arg(self):
        errors = validate_tool_call("clickup_task_list_weekly", {"bogus": "value"})
        assert any("Unknown argument" in e for e in errors)

    def test_get_missing_required_fields_returns_names(self):
        missing = get_missing_required_fields("clickup_task_create", {"client_name": "Distex"})
        assert missing == ["task_title"]

    def test_get_missing_required_fields_none_missing(self):
        missing = get_missing_required_fields("clickup_task_create", {"task_title": "Fix bug"})
        assert missing == []

    def test_get_missing_required_fields_unknown_skill(self):
        missing = get_missing_required_fields("bogus", {})
        assert missing == []

    def test_tool_descriptions_contains_skill_names(self):
        desc = get_tool_descriptions_for_prompt()
        assert "clickup_task_list_weekly" in desc
        assert "clickup_task_create" in desc
        assert "task_title" in desc

    def test_schemas_have_expected_keys(self):
        assert "clickup_task_list_weekly" in TOOL_SCHEMAS
        assert "clickup_task_create" in TOOL_SCHEMAS
        assert "task_title" in TOOL_SCHEMAS["clickup_task_create"]["args"]


# ---------------------------------------------------------------------------
# Orchestrator: tool_call path
# ---------------------------------------------------------------------------


class TestOrchestrateToolCall:
    @pytest.mark.asyncio
    async def test_natural_language_to_weekly_tasks(self):
        llm_response = _fake_completion({
            "mode": "tool_call",
            "skill_id": "clickup_task_list_weekly",
            "args": {"client_name": "Distex"},
            "confidence": 0.95,
        })

        with patch(
            "app.services.agencyclaw.slack_orchestrator.call_chat_completion",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            result = await orchestrate_dm_message(
                text="show tasks for Distex", **_DEFAULT_KWARGS
            )

        assert result["mode"] == "tool_call"
        assert result["skill_id"] == "clickup_task_list_weekly"
        assert result["args"]["client_name"] == "Distex"
        assert result["confidence"] >= 0.9

    @pytest.mark.asyncio
    async def test_create_task_full(self):
        llm_response = _fake_completion({
            "mode": "tool_call",
            "skill_id": "clickup_task_create",
            "args": {"client_name": "Distex", "task_title": "Fix landing page"},
            "confidence": 0.92,
        })

        with patch(
            "app.services.agencyclaw.slack_orchestrator.call_chat_completion",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            result = await orchestrate_dm_message(
                text="create task for Distex: Fix landing page", **_DEFAULT_KWARGS
            )

        assert result["mode"] == "tool_call"
        assert result["skill_id"] == "clickup_task_create"
        assert result["args"]["task_title"] == "Fix landing page"

    @pytest.mark.asyncio
    async def test_thin_create_asks_clarification(self):
        """LLM correctly returns clarify when title is missing."""
        llm_response = _fake_completion({
            "mode": "clarify",
            "question": "What should the task be called?",
            "missing_fields": ["task_title"],
            "confidence": 0.88,
        })

        with patch(
            "app.services.agencyclaw.slack_orchestrator.call_chat_completion",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            result = await orchestrate_dm_message(
                text="create a task", **_DEFAULT_KWARGS
            )

        assert result["mode"] == "clarify"
        assert "task_title" in result["missing_fields"]
        assert result["question"]

    @pytest.mark.asyncio
    async def test_invalid_tool_args_converted_to_clarify(self):
        """LLM returns tool_call but with missing required args -> converted to clarify."""
        llm_response = _fake_completion({
            "mode": "tool_call",
            "skill_id": "clickup_task_create",
            "args": {"client_name": "Distex"},  # missing task_title
            "confidence": 0.7,
        })

        with patch(
            "app.services.agencyclaw.slack_orchestrator.call_chat_completion",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            result = await orchestrate_dm_message(
                text="add task for Distex", **_DEFAULT_KWARGS
            )

        assert result["mode"] == "clarify"
        assert "task_title" in result["missing_fields"]

    @pytest.mark.asyncio
    async def test_unknown_skill_returns_fallback(self):
        """LLM hallucinated a skill that doesn't exist."""
        llm_response = _fake_completion({
            "mode": "tool_call",
            "skill_id": "clickup_delete_everything",
            "args": {},
            "confidence": 0.5,
        })

        with patch(
            "app.services.agencyclaw.slack_orchestrator.call_chat_completion",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            result = await orchestrate_dm_message(
                text="delete everything", **_DEFAULT_KWARGS
            )

        assert result["mode"] == "fallback"
        assert "Unknown skill" in result["reason"]


# ---------------------------------------------------------------------------
# Orchestrator: reply path
# ---------------------------------------------------------------------------


class TestOrchestrateReply:
    @pytest.mark.asyncio
    async def test_direct_reply(self):
        llm_response = _fake_completion({
            "mode": "reply",
            "text": "Hey! How can I help you today?",
            "confidence": 0.95,
        })

        with patch(
            "app.services.agencyclaw.slack_orchestrator.call_chat_completion",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            result = await orchestrate_dm_message(
                text="hello", **_DEFAULT_KWARGS
            )

        assert result["mode"] == "reply"
        assert "help" in result["text"].lower()
        assert result["confidence"] >= 0.9

    @pytest.mark.asyncio
    async def test_reply_with_client_context(self):
        llm_response = _fake_completion({
            "mode": "reply",
            "text": "You're currently working on Distex. There's 1 active task: Fix landing page.",
            "confidence": 0.9,
        })

        with patch(
            "app.services.agencyclaw.slack_orchestrator.call_chat_completion",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            result = await orchestrate_dm_message(
                text="what am I working on?",
                profile_id="profile-1",
                slack_user_id="U123",
                session_context={"active_client_id": "client-1"},
                client_context_pack="## Active Tasks\n- Fix landing page [in progress]",
            )

        assert result["mode"] == "reply"
        assert "Distex" in result["text"] or "landing page" in result["text"]


# ---------------------------------------------------------------------------
# Orchestrator: fallback path
# ---------------------------------------------------------------------------


class TestOrchestrateFallback:
    @pytest.mark.asyncio
    async def test_fallback_on_llm_error(self):
        with patch(
            "app.services.agencyclaw.slack_orchestrator.call_chat_completion",
            new_callable=AsyncMock,
            side_effect=OpenAIError("Connection refused"),
        ):
            result = await orchestrate_dm_message(
                text="show tasks", **_DEFAULT_KWARGS
            )

        assert result["mode"] == "fallback"
        assert "Connection refused" in result["reason"]
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_fallback_on_json_parse_failure(self):
        bad_completion = ChatCompletionResult(
            content="Sure, I can help with that!",  # not JSON
            tokens_in=20,
            tokens_out=10,
            tokens_total=30,
            model="gpt-4o-mini",
            duration_ms=100,
        )

        with patch(
            "app.services.agencyclaw.slack_orchestrator.call_chat_completion",
            new_callable=AsyncMock,
            return_value=bad_completion,
        ):
            result = await orchestrate_dm_message(
                text="hello", **_DEFAULT_KWARGS
            )

        assert result["mode"] == "fallback"
        assert "parse" in result["reason"].lower() or "json" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_fallback_on_invalid_mode(self):
        llm_response = _fake_completion({
            "mode": "execute_order_66",
            "text": "It will be done, my lord.",
            "confidence": 1.0,
        })

        with patch(
            "app.services.agencyclaw.slack_orchestrator.call_chat_completion",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            result = await orchestrate_dm_message(
                text="do the thing", **_DEFAULT_KWARGS
            )

        assert result["mode"] == "fallback"
        assert "invalid mode" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_fallback_on_generic_exception(self):
        """Non-OpenAI exceptions also produce fallback, not crash."""
        with patch(
            "app.services.agencyclaw.slack_orchestrator.call_chat_completion",
            new_callable=AsyncMock,
            side_effect=RuntimeError("unexpected"),
        ):
            result = await orchestrate_dm_message(
                text="hello", **_DEFAULT_KWARGS
            )

        assert result["mode"] == "fallback"
        assert "unexpected" in result["reason"]


# ---------------------------------------------------------------------------
# Orchestrator: clarify path (LLM-initiated)
# ---------------------------------------------------------------------------


class TestOrchestrateClarify:
    @pytest.mark.asyncio
    async def test_llm_initiated_clarify(self):
        llm_response = _fake_completion({
            "mode": "clarify",
            "question": "Which client is this for?",
            "missing_fields": ["client_name"],
            "confidence": 0.8,
        })

        with patch(
            "app.services.agencyclaw.slack_orchestrator.call_chat_completion",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            result = await orchestrate_dm_message(
                text="show me the tasks",
                profile_id="profile-1",
                slack_user_id="U123",
                session_context={},  # no active client
                client_context_pack="",
            )

        assert result["mode"] == "clarify"
        assert result["question"] == "Which client is this for?"
        assert "client_name" in result["missing_fields"]

    @pytest.mark.asyncio
    async def test_clarify_with_empty_missing_fields(self):
        """Clarify mode should work even if LLM doesn't provide missing_fields."""
        llm_response = _fake_completion({
            "mode": "clarify",
            "question": "Could you be more specific?",
            "confidence": 0.6,
        })

        with patch(
            "app.services.agencyclaw.slack_orchestrator.call_chat_completion",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            result = await orchestrate_dm_message(
                text="do the thing", **_DEFAULT_KWARGS
            )

        assert result["mode"] == "clarify"
        assert result["question"] == "Could you be more specific?"
        assert result["missing_fields"] == []
