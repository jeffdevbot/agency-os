"""Tests for C10D: Constrained planner.

Covers:
- Valid plan generation (schema-conformant)
- N-gram request produces plan
- Unknown request produces empty plan
- Invalid skill_id rejected
- Too many steps rejected
- Malformed JSON returns None
- LLM error returns None
- Validation error returns None
- Token telemetry captured
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.services.agencyclaw.openai_client import ChatCompletionResult, OpenAIError
from app.services.agencyclaw.planner import (
    ExecutionPlan,
    PlanStep,
    _validate_plan,
    generate_plan,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_completion(content_dict: dict) -> ChatCompletionResult:
    return ChatCompletionResult(
        content=json.dumps(content_dict),
        tokens_in=40,
        tokens_out=25,
        tokens_total=65,
        model="gpt-4o-mini",
        duration_ms=150,
    )


def _valid_ngram_plan() -> dict:
    return {
        "intent": "ngram_research",
        "steps": [
            {
                "skill_id": "ngram_research",
                "args": {"client_name": "Distex"},
                "requires_confirmation": True,
                "reason": "Create N-gram research task using SOP",
            }
        ],
        "confidence": 0.9,
    }


def _valid_create_task_plan() -> dict:
    return {
        "intent": "task_creation",
        "steps": [
            {
                "skill_id": "clickup_task_create",
                "args": {"client_name": "Distex", "task_title": "Fix bug"},
                "requires_confirmation": True,
                "reason": "Create task as requested",
            }
        ],
        "confidence": 0.85,
    }


def _unknown_plan() -> dict:
    return {
        "intent": "unknown",
        "steps": [],
        "confidence": 0.0,
    }


# ---------------------------------------------------------------------------
# Validation unit tests
# ---------------------------------------------------------------------------


class TestPlanValidation:
    def test_valid_plan_passes(self):
        result = _validate_plan(_valid_ngram_plan())
        assert result is not None
        assert result["intent"] == "ngram_research"
        assert len(result["steps"]) == 1
        assert result["steps"][0]["skill_id"] == "ngram_research"

    def test_unknown_intent_empty_steps_valid(self):
        result = _validate_plan(_unknown_plan())
        assert result is not None
        assert result["steps"] == []
        assert result["confidence"] == 0.0

    def test_invalid_skill_id_rejected(self):
        plan = {
            "intent": "test",
            "steps": [{"skill_id": "nonexistent_skill", "args": {}, "requires_confirmation": False, "reason": ""}],
            "confidence": 0.5,
        }
        result = _validate_plan(plan)
        assert result is None

    def test_too_many_steps_rejected(self):
        plan = {
            "intent": "test",
            "steps": [
                {"skill_id": "ngram_research", "args": {}, "requires_confirmation": True, "reason": ""}
                for _ in range(5)
            ],
            "confidence": 0.5,
        }
        result = _validate_plan(plan)
        assert result is None

    def test_steps_not_list_rejected(self):
        plan = {"intent": "test", "steps": "not a list", "confidence": 0.5}
        result = _validate_plan(plan)
        assert result is None

    def test_non_unknown_intent_empty_steps_rejected(self):
        plan = {"intent": "ngram_research", "steps": [], "confidence": 0.9}
        result = _validate_plan(plan)
        assert result is None

    def test_step_missing_required_arg_rejected(self):
        """clickup_task_create requires task_title — missing it should reject."""
        plan = {
            "intent": "test",
            "steps": [
                {"skill_id": "clickup_task_create", "args": {"client_name": "Distex"}, "requires_confirmation": True, "reason": ""}
            ],
            "confidence": 0.5,
        }
        result = _validate_plan(plan)
        assert result is None

    def test_valid_create_task_plan(self):
        result = _validate_plan(_valid_create_task_plan())
        assert result is not None
        assert result["steps"][0]["skill_id"] == "clickup_task_create"
        assert result["steps"][0]["args"]["task_title"] == "Fix bug"


# ---------------------------------------------------------------------------
# generate_plan integration tests
# ---------------------------------------------------------------------------


class TestGeneratePlan:
    @pytest.mark.asyncio
    async def test_valid_plan_schema_conformant(self):
        llm_response = _fake_completion(_valid_ngram_plan())

        with patch(
            "app.services.agencyclaw.planner.call_chat_completion",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            plan = await generate_plan(
                text="start ngram research for Distex",
                session_context={},
                client_context_pack="Active client: Distex",
                kb_context_summary="",
            )

        assert plan is not None
        assert plan["intent"] == "ngram_research"
        assert len(plan["steps"]) == 1
        assert plan["steps"][0]["skill_id"] == "ngram_research"

    @pytest.mark.asyncio
    async def test_ngram_request_produces_plan(self):
        llm_response = _fake_completion(_valid_ngram_plan())

        with patch(
            "app.services.agencyclaw.planner.call_chat_completion",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            plan = await generate_plan(
                text="start ngram research",
                session_context={},
                client_context_pack="",
                kb_context_summary="- [sop] N-gram Analysis: ...",
            )

        assert plan is not None
        assert plan["steps"][0]["skill_id"] == "ngram_research"

    @pytest.mark.asyncio
    async def test_create_task_request_produces_plan(self):
        llm_response = _fake_completion(_valid_create_task_plan())

        with patch(
            "app.services.agencyclaw.planner.call_chat_completion",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            plan = await generate_plan(
                text="create task for Distex: Fix bug",
                session_context={},
                client_context_pack="",
                kb_context_summary="",
            )

        assert plan is not None
        assert plan["steps"][0]["skill_id"] == "clickup_task_create"

    @pytest.mark.asyncio
    async def test_unknown_request_empty_plan(self):
        llm_response = _fake_completion(_unknown_plan())

        with patch(
            "app.services.agencyclaw.planner.call_chat_completion",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            plan = await generate_plan(
                text="asdfghjkl",
                session_context={},
                client_context_pack="",
                kb_context_summary="",
            )

        assert plan is not None
        assert plan["steps"] == []
        assert plan["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_malformed_json_returns_none(self):
        bad_response = ChatCompletionResult(
            content="this is not json at all",
            tokens_in=10,
            tokens_out=5,
            tokens_total=15,
            model="gpt-4o-mini",
            duration_ms=100,
        )

        with patch(
            "app.services.agencyclaw.planner.call_chat_completion",
            new_callable=AsyncMock,
            return_value=bad_response,
        ):
            plan = await generate_plan(
                text="test",
                session_context={},
                client_context_pack="",
                kb_context_summary="",
            )

        assert plan is None

    @pytest.mark.asyncio
    async def test_llm_error_returns_none(self):
        with patch(
            "app.services.agencyclaw.planner.call_chat_completion",
            new_callable=AsyncMock,
            side_effect=OpenAIError("timeout"),
        ):
            plan = await generate_plan(
                text="test",
                session_context={},
                client_context_pack="",
                kb_context_summary="",
            )

        assert plan is None

    @pytest.mark.asyncio
    async def test_validation_error_returns_none(self):
        """LLM returns invalid skill_id → None."""
        bad_plan = {
            "intent": "test",
            "steps": [{"skill_id": "delete_everything", "args": {}, "requires_confirmation": False, "reason": ""}],
            "confidence": 0.9,
        }
        llm_response = _fake_completion(bad_plan)

        with patch(
            "app.services.agencyclaw.planner.call_chat_completion",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            plan = await generate_plan(
                text="test",
                session_context={},
                client_context_pack="",
                kb_context_summary="",
            )

        assert plan is None

    @pytest.mark.asyncio
    async def test_token_telemetry_captured(self):
        llm_response = _fake_completion(_valid_ngram_plan())

        with patch(
            "app.services.agencyclaw.planner.call_chat_completion",
            new_callable=AsyncMock,
            return_value=llm_response,
        ):
            plan = await generate_plan(
                text="start ngram",
                session_context={},
                client_context_pack="",
                kb_context_summary="",
            )

        assert plan is not None
        assert plan["tokens_in"] == 40
        assert plan["tokens_out"] == 25
        assert plan["tokens_total"] == 65
        assert plan["model_used"] == "gpt-4o-mini"
