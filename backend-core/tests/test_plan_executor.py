"""Tests for C10D: Deterministic plan executor.

Covers:
- Single step executes handler
- N-gram step calls handler with correct kwargs
- Policy denied aborts plan and skips remaining steps
- Multi-step partial failure (first errors, second still attempted)
- Unknown skill_id records error, not crash
- Execution result counts (steps_attempted, steps_succeeded)
- Policy check exception continues to next step
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.agencyclaw.plan_executor import (
    ExecutionResult,
    StepResult,
    execute_plan,
)
from app.services.agencyclaw.planner import ExecutionPlan, PlanStep


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_plan(
    *,
    intent: str = "test",
    steps: list[PlanStep] | None = None,
    confidence: float = 0.9,
) -> ExecutionPlan:
    return ExecutionPlan(
        intent=intent,
        steps=steps or [],
        confidence=confidence,
        tokens_in=10,
        tokens_out=5,
        tokens_total=15,
        model_used="gpt-4o-mini",
    )


def _allow_policy(**kwargs) -> dict:
    return {"allowed": True, "reason_code": "allowed", "user_message": "", "meta": {}}


def _deny_policy(**kwargs) -> dict:
    return {
        "allowed": False,
        "reason_code": "viewer_mutation_denied",
        "user_message": "You don't have permission.",
        "meta": {},
    }


def _make_step(
    skill_id: str = "ngram_research",
    args: dict | None = None,
    requires_confirmation: bool = True,
    reason: str = "test step",
) -> PlanStep:
    return PlanStep(
        skill_id=skill_id,
        args=args or {},
        requires_confirmation=requires_confirmation,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestExecutePlan:
    @pytest.mark.asyncio
    async def test_single_step_executes_handler(self):
        handler = AsyncMock()
        plan = _make_plan(steps=[_make_step(skill_id="ngram_research")])

        result = await execute_plan(
            plan=plan,
            slack_user_id="U1",
            channel="D1",
            session=MagicMock(),
            session_service=MagicMock(),
            slack=AsyncMock(),
            check_policy=AsyncMock(side_effect=_allow_policy),
            handler_map={"ngram_research": handler},
        )

        handler.assert_called_once()
        assert result["steps_attempted"] == 1
        assert result["steps_succeeded"] == 1
        assert result["aborted"] is False
        assert result["step_results"][0]["status"] == "success"

    @pytest.mark.asyncio
    async def test_ngram_step_passes_correct_kwargs(self):
        handler = AsyncMock()
        plan = _make_plan(
            steps=[_make_step(skill_id="ngram_research", args={"client_name": "Distex"})]
        )

        slack_mock = AsyncMock()
        session_service_mock = MagicMock()

        await execute_plan(
            plan=plan,
            slack_user_id="U1",
            channel="D1",
            session=MagicMock(),
            session_service=session_service_mock,
            slack=slack_mock,
            check_policy=AsyncMock(side_effect=_allow_policy),
            handler_map={"ngram_research": handler},
        )

        call_kwargs = handler.call_args.kwargs
        assert call_kwargs["slack_user_id"] == "U1"
        assert call_kwargs["channel"] == "D1"
        assert call_kwargs["client_name_hint"] == "Distex"
        assert call_kwargs["session_service"] is session_service_mock
        assert call_kwargs["slack"] is slack_mock

    @pytest.mark.asyncio
    async def test_create_task_step_passes_task_title(self):
        handler = AsyncMock()
        plan = _make_plan(
            steps=[
                _make_step(
                    skill_id="clickup_task_create",
                    args={"client_name": "Distex", "task_title": "Fix bug"},
                )
            ]
        )

        await execute_plan(
            plan=plan,
            slack_user_id="U1",
            channel="D1",
            session=MagicMock(),
            session_service=MagicMock(),
            slack=AsyncMock(),
            check_policy=AsyncMock(side_effect=_allow_policy),
            handler_map={"clickup_task_create": handler},
        )

        call_kwargs = handler.call_args.kwargs
        assert call_kwargs["task_title"] == "Fix bug"
        assert call_kwargs["client_name_hint"] == "Distex"

    @pytest.mark.asyncio
    async def test_policy_denied_aborts_plan(self):
        handler = AsyncMock()
        slack_mock = AsyncMock()
        plan = _make_plan(
            steps=[
                _make_step(skill_id="ngram_research"),
                _make_step(skill_id="clickup_task_create", args={"task_title": "X"}),
            ]
        )

        result = await execute_plan(
            plan=plan,
            slack_user_id="U1",
            channel="D1",
            session=MagicMock(),
            session_service=MagicMock(),
            slack=slack_mock,
            check_policy=AsyncMock(side_effect=_deny_policy),
            handler_map={"ngram_research": handler, "clickup_task_create": handler},
        )

        handler.assert_not_called()
        assert result["aborted"] is True
        assert result["steps_succeeded"] == 0
        assert result["step_results"][0]["status"] == "denied"
        assert result["step_results"][1]["status"] == "skipped"
        slack_mock.post_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_multi_step_partial_failure(self):
        """First handler errors, second still attempted and succeeds."""
        failing_handler = AsyncMock(side_effect=RuntimeError("boom"))
        success_handler = AsyncMock()
        plan = _make_plan(
            steps=[
                _make_step(skill_id="ngram_research"),
                _make_step(skill_id="clickup_task_create", args={"task_title": "X"}),
            ]
        )

        result = await execute_plan(
            plan=plan,
            slack_user_id="U1",
            channel="D1",
            session=MagicMock(),
            session_service=MagicMock(),
            slack=AsyncMock(),
            check_policy=AsyncMock(side_effect=_allow_policy),
            handler_map={
                "ngram_research": failing_handler,
                "clickup_task_create": success_handler,
            },
        )

        assert result["steps_attempted"] == 2
        assert result["steps_succeeded"] == 1
        assert result["aborted"] is False
        assert result["step_results"][0]["status"] == "error"
        assert result["step_results"][1]["status"] == "success"

    @pytest.mark.asyncio
    async def test_unknown_skill_records_error(self):
        plan = _make_plan(steps=[_make_step(skill_id="ngram_research")])

        result = await execute_plan(
            plan=plan,
            slack_user_id="U1",
            channel="D1",
            session=MagicMock(),
            session_service=MagicMock(),
            slack=AsyncMock(),
            check_policy=AsyncMock(side_effect=_allow_policy),
            handler_map={},  # No handlers registered
        )

        assert result["steps_attempted"] == 1
        assert result["steps_succeeded"] == 0
        assert result["step_results"][0]["status"] == "error"
        assert "No handler" in result["step_results"][0]["reason"]

    @pytest.mark.asyncio
    async def test_execution_result_counts(self):
        handler = AsyncMock()
        plan = _make_plan(
            intent="multi_step",
            steps=[
                _make_step(skill_id="ngram_research"),
                _make_step(skill_id="ngram_research"),
                _make_step(skill_id="ngram_research"),
            ],
        )

        result = await execute_plan(
            plan=plan,
            slack_user_id="U1",
            channel="D1",
            session=MagicMock(),
            session_service=MagicMock(),
            slack=AsyncMock(),
            check_policy=AsyncMock(side_effect=_allow_policy),
            handler_map={"ngram_research": handler},
        )

        assert result["plan_intent"] == "multi_step"
        assert result["steps_attempted"] == 3
        assert result["steps_succeeded"] == 3
        assert len(result["step_results"]) == 3
        assert handler.call_count == 3

    @pytest.mark.asyncio
    async def test_empty_plan_no_steps(self):
        result = await execute_plan(
            plan=_make_plan(intent="unknown", steps=[]),
            slack_user_id="U1",
            channel="D1",
            session=MagicMock(),
            session_service=MagicMock(),
            slack=AsyncMock(),
            check_policy=AsyncMock(),
            handler_map={},
        )

        assert result["steps_attempted"] == 0
        assert result["steps_succeeded"] == 0
        assert result["step_results"] == []
        assert result["aborted"] is False

    @pytest.mark.asyncio
    async def test_policy_check_exception_continues(self):
        """If policy check itself throws, step is recorded as error and next step continues."""
        handler = AsyncMock()

        async def _exploding_policy(**kwargs):
            raise RuntimeError("DB down")

        plan = _make_plan(
            steps=[
                _make_step(skill_id="ngram_research"),
                _make_step(skill_id="clickup_task_create", args={"task_title": "X"}),
            ]
        )

        result = await execute_plan(
            plan=plan,
            slack_user_id="U1",
            channel="D1",
            session=MagicMock(),
            session_service=MagicMock(),
            slack=AsyncMock(),
            check_policy=_exploding_policy,
            handler_map={
                "ngram_research": handler,
                "clickup_task_create": handler,
            },
        )

        # Both steps had policy errors, neither handler called
        assert result["steps_attempted"] == 2
        assert result["steps_succeeded"] == 0
        assert result["aborted"] is False
        assert result["step_results"][0]["status"] == "error"
        assert result["step_results"][1]["status"] == "error"

    @pytest.mark.asyncio
    async def test_client_name_defaults_empty(self):
        """When step args don't include client_name, hint defaults to empty string."""
        handler = AsyncMock()
        plan = _make_plan(steps=[_make_step(skill_id="ngram_research", args={})])

        await execute_plan(
            plan=plan,
            slack_user_id="U1",
            channel="D1",
            session=MagicMock(),
            session_service=MagicMock(),
            slack=AsyncMock(),
            check_policy=AsyncMock(side_effect=_allow_policy),
            handler_map={"ngram_research": handler},
        )

        assert handler.call_args.kwargs["client_name_hint"] == ""

    @pytest.mark.asyncio
    async def test_deny_second_step_skips_third(self):
        """Policy allows step 1 but denies step 2 → step 3 skipped."""
        call_count = 0

        async def _allow_then_deny(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _allow_policy()
            return _deny_policy()

        handler = AsyncMock()
        slack_mock = AsyncMock()
        plan = _make_plan(
            steps=[
                _make_step(skill_id="ngram_research"),
                _make_step(skill_id="ngram_research"),
                _make_step(skill_id="ngram_research"),
            ]
        )

        result = await execute_plan(
            plan=plan,
            slack_user_id="U1",
            channel="D1",
            session=MagicMock(),
            session_service=MagicMock(),
            slack=slack_mock,
            check_policy=_allow_then_deny,
            handler_map={"ngram_research": handler},
        )

        assert handler.call_count == 1  # Only first step executed
        assert result["steps_succeeded"] == 1
        assert result["aborted"] is True
        assert result["step_results"][0]["status"] == "success"
        assert result["step_results"][1]["status"] == "denied"
        assert result["step_results"][2]["status"] == "skipped"
