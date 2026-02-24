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
from app.services.agencyclaw import slack_orchestrator as slack_orchestrator_module
from app.services.agencyclaw.skill_registry import (
    LEGACY_PROMPT_EXCLUDED_SKILLS,
    get_legacy_skill_descriptions_for_prompt,
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


class TestAgentLoopFlagDispatch:
    @pytest.mark.asyncio
    async def test_agent_loop_flag_off_keeps_legacy_parity(self):
        svc, slack = _make_mocks()

        with (
            patch("app.api.routes.slack._is_agent_loop_enabled", return_value=False),
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch(
                "app.api.routes.slack._runtime_run_reply_only_agent_loop_turn",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_agent_loop,
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="hello")

        mock_agent_loop.assert_not_called()
        slack.post_message.assert_called()

    @pytest.mark.asyncio
    async def test_agent_loop_flag_on_routes_to_reply_loop(self):
        svc, slack = _make_mocks()

        with (
            patch("app.api.routes.slack._is_agent_loop_enabled", return_value=True),
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.get_supabase_admin_client", return_value=MagicMock()),
            patch(
                "app.api.routes.slack._runtime_run_reply_only_agent_loop_turn",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_agent_loop,
            patch("app.api.routes.slack._classify_message") as mock_classify,
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="hello")

        mock_agent_loop.assert_called_once()
        mock_classify.assert_not_called()

    @pytest.mark.asyncio
    async def test_agent_loop_task_list_executor_enforces_policy_gate(self):
        svc, slack = _make_mocks()
        captured_result: dict[str, Any] = {}

        async def _exercise_executor(**kwargs) -> bool:
            execute_task_list_fn = kwargs["execute_task_list_fn"]
            captured_result.update(
                await execute_task_list_fn(
                    slack_user_id="U123",
                    channel="C1",
                    args={"client_name": "Distex"},
                    session=svc.get_or_create_session.return_value,
                    session_service=svc,
                )
            )
            return True

        deny_policy = {
            "allowed": False,
            "reason_code": "not_allowed",
            "user_message": "That action requires admin access.",
            "meta": {},
        }

        with (
            patch("app.api.routes.slack._is_agent_loop_enabled", return_value=True),
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.get_supabase_admin_client", return_value=MagicMock()),
            patch(
                "app.api.routes.slack._runtime_run_reply_only_agent_loop_turn",
                side_effect=_exercise_executor,
            ),
            patch("app.api.routes.slack._check_skill_policy", new_callable=AsyncMock, return_value=deny_policy),
            patch("app.api.routes.slack._handle_task_list", new_callable=AsyncMock) as mock_task_list,
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="show tasks for Distex")

        assert captured_result["policy_denied"] is True
        assert "admin access" in captured_result["response_text"].lower()
        mock_task_list.assert_not_called()

    @pytest.mark.asyncio
    async def test_agent_loop_cc_read_executor_dispatches_and_enforces_policy(self):
        svc, slack = _make_mocks()
        captured_result: dict[str, Any] = {}

        async def _exercise_executor(**kwargs) -> bool:
            execute_read_skill_fn = kwargs["execute_read_skill_fn"]
            captured_result.update(
                await execute_read_skill_fn(
                    skill_id="cc_brand_list_all",
                    slack_user_id="U123",
                    channel="C1",
                    args={"client_name": "Distex"},
                    session=svc.get_or_create_session.return_value,
                    session_service=svc,
                )
            )
            return True

        with (
            patch("app.api.routes.slack._is_agent_loop_enabled", return_value=True),
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.get_supabase_admin_client", return_value=MagicMock()),
            patch(
                "app.api.routes.slack._runtime_run_reply_only_agent_loop_turn",
                side_effect=_exercise_executor,
            ),
            patch("app.api.routes.slack._check_skill_policy", new_callable=AsyncMock, return_value=_ALLOW_POLICY),
            patch("app.api.routes.slack._handle_cc_skill", new_callable=AsyncMock, return_value="[Listed brands]") as mock_cc,
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="show brands for distex")

        assert captured_result["response_text"] == "[Listed brands]"
        mock_cc.assert_called_once()
        call_kwargs = mock_cc.call_args.kwargs
        assert call_kwargs["skill_id"] == "cc_brand_list_all"
        assert call_kwargs["args"] == {"client_name": "Distex"}

    @pytest.mark.asyncio
    async def test_agent_loop_new_context_skill_policy_denial_blocks_execution(self):
        svc, slack = _make_mocks()
        captured_result: dict[str, Any] = {}
        deny_policy = {
            "allowed": False,
            "reason_code": "not_allowed",
            "user_message": "Denied by policy.",
            "meta": {},
        }

        async def _exercise_executor(**kwargs) -> bool:
            execute_read_skill_fn = kwargs["execute_read_skill_fn"]
            captured_result.update(
                await execute_read_skill_fn(
                    skill_id="search_kb",
                    slack_user_id="U123",
                    channel="C1",
                    args={"query": "coupon setup"},
                    session=svc.get_or_create_session.return_value,
                    session_service=svc,
                )
            )
            return True

        with (
            patch("app.api.routes.slack._is_agent_loop_enabled", return_value=True),
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.get_supabase_admin_client", return_value=MagicMock()),
            patch(
                "app.api.routes.slack._runtime_run_reply_only_agent_loop_turn",
                side_effect=_exercise_executor,
            ),
            patch("app.api.routes.slack._check_skill_policy", new_callable=AsyncMock, return_value=deny_policy),
            patch("app.api.routes.slack.retrieve_kb_context", new_callable=AsyncMock) as mock_kb,
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="search kb coupon setup")

        assert captured_result["policy_denied"] is True
        assert "denied by policy" in captured_result["response_text"].lower()
        mock_kb.assert_not_called()

    @pytest.mark.asyncio
    async def test_agent_loop_search_kb_brand_name_scopes_query(self):
        svc, slack = _make_mocks()
        captured_result: dict[str, Any] = {}

        async def _exercise_executor(**kwargs) -> bool:
            execute_read_skill_fn = kwargs["execute_read_skill_fn"]
            captured_result.update(
                await execute_read_skill_fn(
                    skill_id="search_kb",
                    slack_user_id="U123",
                    channel="C1",
                    args={"query": "coupon setup", "brand_name": "Alpha"},
                    session=svc.get_or_create_session.return_value,
                    session_service=svc,
                )
            )
            return True

        kb_payload = {
            "sources": [{"title": "SOP Coupons", "content": "..."}, {"title": "Brand Alpha Playbook", "content": "..."}],
            "tiers_hit": ["sop"],
        }

        with (
            patch("app.api.routes.slack._is_agent_loop_enabled", return_value=True),
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.get_supabase_admin_client", return_value=MagicMock()),
            patch(
                "app.api.routes.slack._runtime_run_reply_only_agent_loop_turn",
                side_effect=_exercise_executor,
            ),
            patch("app.api.routes.slack._check_skill_policy", new_callable=AsyncMock, return_value=_ALLOW_POLICY),
            patch("app.api.routes.slack.retrieve_kb_context", new_callable=AsyncMock, return_value=kb_payload) as mock_kb,
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="search kb for alpha coupon setup")

        assert "found kb context" in captured_result["response_text"].lower()
        assert captured_result["query_used"] == "coupon setup brand:Alpha"
        assert mock_kb.call_args.kwargs["query"] == "coupon setup brand:Alpha"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "evidence_result,expected_text",
        [
            (
                {"ok": True, "note": "[skill_result] clickup_task_list: {}", "payload_summary": "ok"},
                "[skill_result] clickup_task_list: {}",
            ),
            (
                {"ok": False, "error": "not_found"},
                "couldn't find a prior result",
            ),
            (
                {"ok": False, "error": "invalid_key"},
                "key format is invalid",
            ),
        ],
    )
    async def test_agent_loop_rehydration_executor_maps_result_to_safe_response(
        self, evidence_result, expected_text
    ):
        svc, slack = _make_mocks()
        captured_result: dict[str, Any] = {}

        async def _exercise_executor(**kwargs) -> bool:
            execute_read_skill_fn = kwargs["execute_read_skill_fn"]
            captured_result.update(
                await execute_read_skill_fn(
                    skill_id="load_prior_skill_result",
                    slack_user_id="U123",
                    channel="C1",
                    args={"key": "ev:run-1"},
                    session=svc.get_or_create_session.return_value,
                    session_service=svc,
                )
            )
            return True

        with (
            patch("app.api.routes.slack._is_agent_loop_enabled", return_value=True),
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.get_supabase_admin_client", return_value=MagicMock()),
            patch(
                "app.api.routes.slack._runtime_run_reply_only_agent_loop_turn",
                side_effect=_exercise_executor,
            ),
            patch("app.api.routes.slack._check_skill_policy", new_callable=AsyncMock, return_value=_ALLOW_POLICY),
            patch("app.api.routes.slack.read_evidence", return_value=evidence_result),
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="load prior result")

        assert expected_text.lower() in captured_result["response_text"].lower()

    @pytest.mark.asyncio
    async def test_agent_loop_delegate_planner_executor_routes_to_planner_runtime(self):
        svc, slack = _make_mocks()
        captured_report: dict[str, Any] = {}
        tool_executor_calls: list[dict[str, Any]] = []

        async def _exercise_executor(**kwargs) -> bool:
            execute_delegate_planner_fn = kwargs["execute_delegate_planner_fn"]
            async def _noop_tool_executor(**_tool_kwargs):
                tool_executor_calls.append(dict(_tool_kwargs))
                return {"ok": True, "response_text": "callback-ok"}
            captured_report.update(
                await execute_delegate_planner_fn(
                    request_text="plan this work",
                    slack_user_id="U123",
                    channel="C1",
                    session=svc.get_or_create_session.return_value,
                    session_service=svc,
                    parent_run_id="run-main",
                    child_run_id="run-child",
                    trace_id="trace-1",
                    tool_executor=_noop_tool_executor,
                    max_planner_turns=4,
                )
            )
            return True

        async def _fake_execute_plan(*, plan: dict[str, Any], handler_map: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
            steps = plan.get("steps") if isinstance(plan, dict) else []
            attempted = 0
            for step in steps or []:
                if not isinstance(step, dict):
                    continue
                skill_id = str(step.get("skill_id") or "")
                handler = handler_map.get(skill_id)
                if handler is None:
                    continue
                attempted += 1
                await handler(
                    plan_args=step.get("args") if isinstance(step.get("args"), dict) else {},
                    client_name_hint="",
                )
            return {
                "plan_intent": str(plan.get("intent") or "multi_step"),
                "steps_attempted": attempted,
                "steps_succeeded": attempted,
                "step_results": [],
                "aborted": False,
                "abort_reason": None,
            }

        with (
            patch("app.api.routes.slack._is_agent_loop_enabled", return_value=True),
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.get_supabase_admin_client", return_value=MagicMock()),
            patch(
                "app.api.routes.slack._runtime_run_reply_only_agent_loop_turn",
                side_effect=_exercise_executor,
            ),
            patch("app.api.routes.slack.generate_plan", new_callable=AsyncMock, return_value={
                "intent": "multi_step",
                "steps": [{"skill_id": "lookup_client", "args": {"query": "Distex"}, "requires_confirmation": False, "reason": "read"}],
                "confidence": 0.8,
                "tokens_in": None,
                "tokens_out": None,
                "tokens_total": None,
                "model_used": None,
            }) as mock_generate_plan,
            patch("app.api.routes.slack.execute_plan", new_callable=AsyncMock, side_effect=_fake_execute_plan) as mock_execute_plan,
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="plan this")

        assert captured_report["ok"] is True
        assert captured_report["status"] == "completed"
        assert captured_report["request_text"] == "plan this work"
        assert mock_execute_plan.call_count == 1
        execute_kwargs = mock_execute_plan.call_args.kwargs
        assert execute_kwargs["plan"]["steps"][0]["skill_id"] == "lookup_client"
        assert "lookup_client" in execute_kwargs["handler_map"]
        assert any(call.get("skill_id") == "lookup_client" for call in tool_executor_calls)
        assert "delegate_planner" not in captured_report["planner_available_skill_ids"]
        available_text = mock_generate_plan.call_args.kwargs.get("available_skills", "")
        assert "### delegate_planner" not in available_text

    @pytest.mark.asyncio
    async def test_agent_loop_delegate_planner_rejects_mutation_steps(self):
        svc, slack = _make_mocks()
        captured_report: dict[str, Any] = {}

        async def _exercise_executor(**kwargs) -> bool:
            execute_delegate_planner_fn = kwargs["execute_delegate_planner_fn"]
            captured_report.update(
                await execute_delegate_planner_fn(
                    request_text="plan this work",
                    slack_user_id="U123",
                    channel="C1",
                    session=svc.get_or_create_session.return_value,
                    session_service=svc,
                    parent_run_id="run-main",
                    child_run_id="run-child",
                    trace_id="trace-1",
                )
            )
            return True

        with (
            patch("app.api.routes.slack._is_agent_loop_enabled", return_value=True),
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.get_supabase_admin_client", return_value=MagicMock()),
            patch(
                "app.api.routes.slack._runtime_run_reply_only_agent_loop_turn",
                side_effect=_exercise_executor,
            ),
            patch("app.api.routes.slack.generate_plan", new_callable=AsyncMock, return_value={
                "intent": "create_only",
                "steps": [{"skill_id": "clickup_task_create", "args": {"task_title": "X"}, "requires_confirmation": True, "reason": "mut"}],
                "confidence": 0.7,
                "tokens_in": None,
                "tokens_out": None,
                "tokens_total": None,
                "model_used": None,
            }),
            patch("app.api.routes.slack.execute_plan", new_callable=AsyncMock) as mock_execute_plan,
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="plan create")

        assert captured_report["ok"] is True
        assert captured_report["status"] == "completed"
        assert len(captured_report.get("mutation_proposals", [])) == 1
        proposal = captured_report["mutation_proposals"][0]
        assert proposal["skill_id"] == "clickup_task_create"
        assert proposal["rejected_reason"] == "planner_mutation_execution_disallowed"
        mock_execute_plan.assert_not_called()

    @pytest.mark.asyncio
    async def test_agent_loop_delegate_planner_performs_replan_cycle(self):
        svc, slack = _make_mocks()
        captured_report: dict[str, Any] = {}

        async def _exercise_executor(**kwargs) -> bool:
            execute_delegate_planner_fn = kwargs["execute_delegate_planner_fn"]
            captured_report.update(
                await execute_delegate_planner_fn(
                    request_text="plan this work",
                    slack_user_id="U123",
                    channel="C1",
                    session=svc.get_or_create_session.return_value,
                    session_service=svc,
                    parent_run_id="run-main",
                    child_run_id="run-child",
                    trace_id="trace-1",
                )
            )
            return True

        plan1 = {
            "intent": "phase1",
            "steps": [{"skill_id": "lookup_client", "args": {"query": "Distex"}, "requires_confirmation": False, "reason": "ctx1"}],
            "confidence": 0.8,
            "tokens_in": None,
            "tokens_out": None,
            "tokens_total": None,
            "model_used": None,
        }
        plan2 = {
            "intent": "phase2",
            "steps": [{"skill_id": "search_kb", "args": {"query": "coupon setup"}, "requires_confirmation": False, "reason": "ctx2"}],
            "confidence": 0.8,
            "tokens_in": None,
            "tokens_out": None,
            "tokens_total": None,
            "model_used": None,
        }

        with (
            patch("app.api.routes.slack._is_agent_loop_enabled", return_value=True),
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.get_supabase_admin_client", return_value=MagicMock()),
            patch(
                "app.api.routes.slack._runtime_run_reply_only_agent_loop_turn",
                side_effect=_exercise_executor,
            ),
            patch("app.api.routes.slack.generate_plan", new_callable=AsyncMock, side_effect=[plan1, plan2, plan2]) as mock_generate,
            patch("app.api.routes.slack.execute_plan", new_callable=AsyncMock, return_value={
                "plan_intent": "phase",
                "steps_attempted": 1,
                "steps_succeeded": 1,
                "step_results": [],
                "aborted": False,
                "abort_reason": None,
            }) as mock_execute_plan,
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="plan iterative")

        assert captured_report["status"] == "completed"
        assert len(captured_report.get("iteration_reports", [])) >= 2
        assert mock_generate.call_count >= 2
        assert mock_execute_plan.call_count >= 2

    @pytest.mark.asyncio
    async def test_agent_loop_delegate_planner_logs_child_run_step_events_per_iteration(self):
        svc, slack = _make_mocks()
        captured_report: dict[str, Any] = {}
        logger_calls: list[tuple[str, str, dict[str, Any]]] = []

        async def _exercise_executor(**kwargs) -> bool:
            execute_delegate_planner_fn = kwargs["execute_delegate_planner_fn"]
            captured_report.update(
                await execute_delegate_planner_fn(
                    request_text="plan this work",
                    slack_user_id="U123",
                    channel="C1",
                    session=svc.get_or_create_session.return_value,
                    session_service=svc,
                    parent_run_id="run-main",
                    child_run_id="run-child",
                    trace_id="trace-1",
                )
            )
            return True

        class _FakePlannerLogger:
            def __init__(self, _store):
                pass

            def log_user_message(self, run_id: str, text: str):
                _ = run_id, text
                return {"id": "m-user"}

            def log_skill_call(self, run_id: str, skill_id: str, payload: dict[str, Any]):
                _ = run_id
                logger_calls.append(("skill_call", skill_id, payload))
                return {"id": "e-call"}

            def log_skill_result(self, run_id: str, skill_id: str, payload: dict[str, Any]):
                _ = run_id
                logger_calls.append(("skill_result", skill_id, payload))
                return {"id": "e-result"}

            def log_planner_report(self, run_id: str, report: dict[str, Any]):
                _ = run_id, report
                return {"id": "m-report"}

        plan = {
            "intent": "phase1",
            "steps": [{"skill_id": "lookup_client", "args": {"query": "Distex"}, "requires_confirmation": False, "reason": "ctx"}],
            "confidence": 0.8,
            "tokens_in": None,
            "tokens_out": None,
            "tokens_total": None,
            "model_used": None,
        }

        with (
            patch("app.api.routes.slack._is_agent_loop_enabled", return_value=True),
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.get_supabase_admin_client", return_value=MagicMock()),
            patch(
                "app.api.routes.slack._runtime_run_reply_only_agent_loop_turn",
                side_effect=_exercise_executor,
            ),
            patch("app.api.routes.slack.AgentLoopTurnLogger", _FakePlannerLogger),
            patch("app.api.routes.slack.generate_plan", new_callable=AsyncMock, side_effect=[plan, plan]),
            patch("app.api.routes.slack.execute_plan", new_callable=AsyncMock, return_value={
                "plan_intent": "phase1",
                "steps_attempted": 1,
                "steps_succeeded": 1,
                "step_results": [{"skill_id": "lookup_client", "status": "success", "reason": "ctx", "user_message": ""}],
                "aborted": False,
                "abort_reason": None,
            }),
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="plan iterative logging")

        assert captured_report["status"] == "completed"
        assert any(
            call_kind == "skill_call"
            and skill_id == "lookup_client"
            and payload.get("source") == "planner_iteration"
            for call_kind, skill_id, payload in logger_calls
        )
        assert any(
            call_kind == "skill_result"
            and skill_id == "lookup_client"
            and payload.get("source") == "planner_iteration"
            and payload.get("status") == "success"
            for call_kind, skill_id, payload in logger_calls
        )

    @pytest.mark.asyncio
    async def test_agent_loop_delegate_planner_budget_exhausted_partial_report(self):
        svc, slack = _make_mocks()
        captured_report: dict[str, Any] = {}

        async def _exercise_executor(**kwargs) -> bool:
            execute_delegate_planner_fn = kwargs["execute_delegate_planner_fn"]
            captured_report.update(
                await execute_delegate_planner_fn(
                    request_text="plan this work",
                    slack_user_id="U123",
                    channel="C1",
                    session=svc.get_or_create_session.return_value,
                    session_service=svc,
                    parent_run_id="run-main",
                    child_run_id="run-child",
                    trace_id="trace-1",
                )
            )
            return True

        def _plan(turn: int) -> dict[str, Any]:
            return {
                "intent": f"phase{turn}",
                "steps": [{"skill_id": "lookup_client", "args": {"query": f"q{turn}"}, "requires_confirmation": False, "reason": f"r{turn}"}],
                "confidence": 0.8,
                "tokens_in": None,
                "tokens_out": None,
                "tokens_total": None,
                "model_used": None,
            }

        with (
            patch("app.api.routes.slack._is_agent_loop_enabled", return_value=True),
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.get_supabase_admin_client", return_value=MagicMock()),
            patch(
                "app.api.routes.slack._runtime_run_reply_only_agent_loop_turn",
                side_effect=_exercise_executor,
            ),
            patch("app.api.routes.slack.generate_plan", new_callable=AsyncMock, side_effect=[_plan(i) for i in range(1, 7)]),
            patch("app.api.routes.slack.execute_plan", new_callable=AsyncMock, return_value={
                "plan_intent": "phase",
                "steps_attempted": 1,
                "steps_succeeded": 1,
                "step_results": [],
                "aborted": False,
                "abort_reason": None,
            }),
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="plan budget")

        assert captured_report["status"] == "budget_exhausted"
        assert len(captured_report.get("iteration_reports", [])) == 6
        assert "iteration budget" in captured_report.get("response_text", "").lower()

    @pytest.mark.asyncio
    async def test_agent_loop_delegate_planner_needs_clarification_returns_open_questions(self):
        svc, slack = _make_mocks()
        captured_report: dict[str, Any] = {}

        async def _exercise_executor(**kwargs) -> bool:
            execute_delegate_planner_fn = kwargs["execute_delegate_planner_fn"]
            captured_report.update(
                await execute_delegate_planner_fn(
                    request_text="ambiguous ask",
                    slack_user_id="U123",
                    channel="C1",
                    session=svc.get_or_create_session.return_value,
                    session_service=svc,
                    parent_run_id="run-main",
                    child_run_id="run-child",
                    trace_id="trace-1",
                )
            )
            return True

        with (
            patch("app.api.routes.slack._is_agent_loop_enabled", return_value=True),
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=False),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.get_supabase_admin_client", return_value=MagicMock()),
            patch(
                "app.api.routes.slack._runtime_run_reply_only_agent_loop_turn",
                side_effect=_exercise_executor,
            ),
            patch("app.api.routes.slack.generate_plan", new_callable=AsyncMock, return_value={
                "intent": "unknown",
                "steps": [],
                "confidence": 0.1,
                "tokens_in": None,
                "tokens_out": None,
                "tokens_total": None,
                "model_used": None,
            }),
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="plan unclear")

        assert captured_report["status"] == "needs_clarification"
        assert isinstance(captured_report.get("open_questions"), list)
        assert len(captured_report["open_questions"]) >= 1


class TestStrictModeHelpers:
    def test_legacy_prompt_skill_block_excludes_delegate_planner(self):
        prompt = get_legacy_skill_descriptions_for_prompt()
        assert "### delegate_planner" not in prompt
        assert "delegate_planner" in LEGACY_PROMPT_EXCLUDED_SKILLS

    def test_orchestrator_system_prompt_excludes_delegate_planner(self):
        system_prompt = slack_orchestrator_module._build_system_prompt("", {})
        assert "### delegate_planner" not in system_prompt

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
            ("task_list", False),
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
            patch("app.api.routes.slack._handle_task_list", new_callable=AsyncMock) as mock_weekly,
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
            patch("app.api.routes.slack._handle_task_list", new_callable=AsyncMock) as mock_task_list,
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
            patch("app.api.routes.slack._check_skill_policy", new_callable=AsyncMock, return_value=_ALLOW_POLICY),
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="show tasks for Distex this month")

        mock_task_list.assert_called_once()
        call_kwargs = mock_task_list.call_args.kwargs
        assert call_kwargs["client_name_hint"] == "Distex"
        assert call_kwargs["window"] == "this_month"

    @pytest.mark.asyncio
    async def test_tool_call_task_list_window_days_int_routes(self):
        svc, slack = _make_mocks()
        result = _make_orchestrator_result(
            mode="tool_call",
            skill_id="clickup_task_list",
            args={"client_name": "Distex", "window": "last_n_days", "window_days": 14},
        )

        with (
            patch("app.api.routes.slack._is_llm_orchestrator_enabled", return_value=True),
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
            patch("app.api.routes.slack.orchestrate_dm_message", new_callable=AsyncMock, return_value=result),
            patch("app.api.routes.slack._handle_task_list", new_callable=AsyncMock) as mock_task_list,
            patch("app.api.routes.slack.log_ai_token_usage", new_callable=AsyncMock),
            patch("app.api.routes.slack._check_skill_policy", new_callable=AsyncMock, return_value=_ALLOW_POLICY),
        ):
            await _handle_dm_event(slack_user_id="U123", channel="C1", text="show tasks for Distex last 14 days")

        call_kwargs = mock_task_list.call_args.kwargs
        assert call_kwargs["window"] == "last_n_days"
        assert call_kwargs["window_days"] == 14


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
    async def test_planner_runtime_generate_plan_uses_legacy_skill_filter(self):
        svc, slack = _make_mocks()
        session = svc.get_or_create_session.return_value

        with (
            patch("app.api.routes.slack._is_planner_enabled", return_value=True),
            patch("app.api.routes.slack.generate_plan", new_callable=AsyncMock, return_value={
                "intent": "unknown",
                "steps": [],
                "confidence": 0.0,
                "tokens_in": None,
                "tokens_out": None,
                "tokens_total": None,
                "model_used": None,
            }) as mock_generate,
            patch("app.api.routes.slack.retrieve_kb_context", new_callable=AsyncMock, return_value={"sources": []}),
        ):
            await _try_planner(
                text="plan this",
                slack_user_id="U123",
                channel="C1",
                session=session,
                session_service=svc,
                slack=slack,
            )

        available = mock_generate.call_args.kwargs.get("available_skills", "")
        assert "### delegate_planner" not in available

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
        assert exec_kwargs["handler_map"]["clickup_task_list_weekly"].__name__ == "_handle_task_list"
        assert exec_kwargs["handler_map"]["clickup_task_list"].__name__ == "_handle_task_list"
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
            patch("app.api.routes.slack._handle_task_list", new_callable=AsyncMock) as mock_weekly,
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
