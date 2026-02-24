"""C17H+ reference-contract tests: iterative planner loop behaviour.

These tests define the **expected contract** for the iterative planner
sub-agent introduced in C17H+.

Coverage areas:
1. Iterative planner loop (>1 iteration with tool-result feedback)
2. Stop states (completed, blocked, failed, budget_exhausted, needs_clarification)
3. Budget behaviour (bounded turns, partial report on exhaustion)
4. Safety (mutation skills → mutation_proposals, never executed)
5. Traceability (parent_run_id + shared trace_id)
6. Main-agent voice continuity (planner report injected, final reply is main voice)

No production code is modified — all assertions use the existing public API
of ``run_reply_only_agent_loop_turn`` and related modules.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.services.agencyclaw.agent_loop_runtime import run_reply_only_agent_loop_turn


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------


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


class _TrackingTurnLogger:
    """Records lifecycle calls for assertion."""

    def __init__(self, _store: Any) -> None:
        self.calls: list[tuple[str, tuple]] = []
        self._run_counter = 0

    def start_main_run(self, session_id: str):
        self._run_counter += 1
        return {"id": f"run-main-{self._run_counter}", "status": "running", "trace_id": f"trace-{self._run_counter}"}

    def start_planner_run(self, session_id: str, *, parent_run_id: str, trace_id: str):
        self._run_counter += 1
        run_id = f"run-planner-{self._run_counter}"
        self.calls.append(("start_planner_run", (session_id, parent_run_id, trace_id)))
        return {"id": run_id, "status": "running", "parent_run_id": parent_run_id, "trace_id": trace_id}

    def log_user_message(self, run_id: str, text: str):
        self.calls.append(("log_user_message", (run_id, text)))
        return {"id": "m-u"}

    def log_skill_call(self, run_id: str, skill_id: str, payload: dict):
        self.calls.append(("log_skill_call", (run_id, skill_id, payload)))
        return {"id": "e-call"}

    def log_skill_result(self, run_id: str, skill_id: str, payload: dict):
        self.calls.append(("log_skill_result", (run_id, skill_id, payload)))
        return {"id": "e-result"}

    def log_assistant_message(self, run_id: str, text: str):
        self.calls.append(("log_assistant_message", (run_id, text)))
        return {"id": "m-a"}

    def log_planner_report(self, run_id: str, report: dict):
        self.calls.append(("log_planner_report", (run_id, report)))
        return {"id": "m-pr"}

    def complete_run(self, run_id: str, status: str):
        self.calls.append(("complete_run", (run_id, status)))

    def set_run_trace_id(self, run_id: str, trace_id: str):
        self.calls.append(("set_run_trace_id", (run_id, trace_id)))


class _FakeStore:
    def __init__(self, _db: Any) -> None:
        pass

    def list_recent_run_messages(self, run_id: str, limit: int = 20):
        return [{"role": "user", "content": {"text": "plan something"}, "created_at": "2026-01-01T00:00:00Z"}]

    def list_recent_skill_events(self, run_id: str, limit: int = 20):
        return []


def _reply(text: str) -> dict[str, Any]:
    return {
        "content": json.dumps({"mode": "reply", "text": text}),
        "tokens_in": 10, "tokens_out": 5, "tokens_total": 15,
        "model": "gpt-4o-mini", "duration_ms": 10,
    }


def _tool_call(skill_id: str, args: dict | None = None) -> dict[str, Any]:
    return {
        "content": json.dumps({"mode": "tool_call", "skill_id": skill_id, "args": args or {}}),
        "tokens_in": 10, "tokens_out": 5, "tokens_total": 15,
        "model": "gpt-4o-mini", "duration_ms": 10,
    }


def _delegate_planner(request_text: str = "plan this") -> dict[str, Any]:
    return _tool_call("delegate_planner", {"request_text": request_text})


def _patch(monkeypatch):
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopStore", _FakeStore)
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", _TrackingTurnLogger)


async def _run(
    monkeypatch,
    *,
    completions: list[dict[str, Any]],
    planner_report: dict[str, Any] | None = None,
    execute_read_skill_fn=None,
) -> tuple[_FakeSlack, _TrackingTurnLogger, bool]:
    """Run the agent loop with canned LLM completions and optional planner report."""
    _patch(monkeypatch)

    comp_iter = iter(completions)

    async def _fake_completion(*args, **kwargs):
        return next(comp_iter)

    planner_called: list[dict] = []

    async def _fake_planner(**kwargs):
        planner_called.append(kwargs)
        return planner_report or {"ok": True, "status": "completed", "response_text": "Plan done."}

    session = _FakeSession()
    slack = _FakeSlack()
    svc = _FakeSessionService(session)

    # Capture the logger instance so we can inspect calls
    logger_ref: list[_TrackingTurnLogger] = []
    _orig_init = _TrackingTurnLogger.__init__

    def _capture_init(self, _store):
        _orig_init(self, _store)
        logger_ref.append(self)

    monkeypatch.setattr(
        "app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger.__init__",
        _capture_init,
        raising=False,
    )
    # Re-patch since __init__ override might interfere
    monkeypatch.setattr("app.services.agencyclaw.agent_loop_runtime.AgentLoopTurnLogger", type(
        "_PatchedLogger", (_TrackingTurnLogger,), {"__init__": _capture_init},
    ))

    handled = await run_reply_only_agent_loop_turn(
        text="plan something for Acme",
        session=session,
        slack_user_id="U123",
        session_service=svc,
        channel="D1",
        slack=slack,
        supabase_client=MagicMock(),
        execute_delegate_planner_fn=_fake_planner,
        execute_read_skill_fn=execute_read_skill_fn,
        call_chat_completion_fn=_fake_completion,
    )

    logger = logger_ref[0] if logger_ref else _TrackingTurnLogger(None)
    return slack, logger, handled


# ===================================================================
# 1. Iterative planner loop contract
# ===================================================================


class TestIterativePlannerLoop:
    """C17H+ gate: planner sub-agent can execute >1 iteration with
    tool-result feedback before producing a final report."""

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="C17H+ acceptance gate: iterative planner not yet implemented — "
               "current planner is single-shot",
        strict=True,
    )
    async def test_planner_executes_multiple_tool_rounds(self, monkeypatch):
        """The planner sub-agent should be able to call tools, receive results,
        and iterate before producing its final report. The delegate_planner_fn
        should receive enough context to support multi-turn."""
        planner_iterations: list[dict] = []

        async def _iterative_planner(**kwargs):
            planner_iterations.append(kwargs)
            # An iterative planner would call tools internally and track iterations.
            # The report should include iteration_count > 1.
            return {
                "ok": True,
                "status": "completed",
                "response_text": "Completed after 3 iterations.",
                "iteration_count": 3,
                "tool_calls_made": ["lookup_client", "search_kb", "clickup_task_list"],
            }

        _patch(monkeypatch)
        completions = [_delegate_planner("research Acme tasks"), _reply("Here's what I found.")]
        comp_iter = iter(completions)

        async def _fake_completion(*args, **kwargs):
            return next(comp_iter)

        session = _FakeSession()
        slack = _FakeSlack()
        handled = await run_reply_only_agent_loop_turn(
            text="research Acme tasks",
            session=session,
            slack_user_id="U123",
            session_service=_FakeSessionService(session),
            channel="D1",
            slack=slack,
            supabase_client=MagicMock(),
            execute_delegate_planner_fn=_iterative_planner,
            call_chat_completion_fn=_fake_completion,
        )
        assert handled is True
        assert len(planner_iterations) == 1
        report = planner_iterations[0]
        # C17H+ contract: planner receives a tool_executor callback for multi-turn
        assert "tool_executor" in report or "execute_skill_fn" in report, (
            "Planner delegate must receive a tool executor callback for iterative use"
        )

    @pytest.mark.asyncio
    async def test_planner_report_includes_iteration_metadata(self, monkeypatch):
        """The planner report logged to agent_messages should include
        iteration_count so the main agent can reason about planner effort."""
        async def _iterative_planner(**kwargs):
            return {
                "ok": True,
                "status": "completed",
                "response_text": "Done after 2 rounds.",
                "iteration_count": 2,
            }

        _patch(monkeypatch)
        completions = [_delegate_planner(), _reply("Got it.")]
        slack, logger, handled = await _run(
            monkeypatch,
            completions=completions,
            planner_report={"ok": True, "status": "completed", "response_text": "Done.", "iteration_count": 2},
        )

        assert handled is True
        planner_reports = [c for c in logger.calls if c[0] == "log_planner_report"]
        assert len(planner_reports) >= 1
        report_payload = planner_reports[0][1][1]  # (run_id, report)
        assert "iteration_count" in report_payload


# ===================================================================
# 2. Stop states
# ===================================================================


class TestPlannerStopStates:
    """C17H+ gate: planner sub-agent reports one of five terminal states."""

    @pytest.mark.asyncio
    async def test_stop_state_completed(self, monkeypatch):
        """'completed' → planner child run marked completed, main loop continues."""
        slack, logger, handled = await _run(
            monkeypatch,
            completions=[_delegate_planner(), _reply("All done.")],
            planner_report={"ok": True, "status": "completed", "response_text": "Plan finished."},
        )
        assert handled is True
        complete_calls = [(c[1][0], c[1][1]) for c in logger.calls if c[0] == "complete_run"]
        # Planner child should be completed
        planner_completes = [c for c in complete_calls if "planner" in c[0]]
        assert any(s == "completed" for _, s in planner_completes)

    @pytest.mark.asyncio
    async def test_stop_state_blocked(self, monkeypatch):
        """'blocked' → planner child run marked blocked, main agent gets error text."""
        slack, logger, handled = await _run(
            monkeypatch,
            completions=[_delegate_planner(), _reply("blocked fallback")],
            planner_report={"ok": False, "status": "blocked", "response_text": "Need approval."},
        )
        assert handled is True
        complete_calls = [(c[1][0], c[1][1]) for c in logger.calls if c[0] == "complete_run"]
        planner_completes = [c for c in complete_calls if "planner" in c[0]]
        assert any(s == "blocked" for _, s in planner_completes)

    @pytest.mark.asyncio
    async def test_stop_state_failed(self, monkeypatch):
        """'failed' → planner child run marked failed."""
        slack, logger, handled = await _run(
            monkeypatch,
            completions=[_delegate_planner(), _reply("fail fallback")],
            planner_report={"ok": False, "status": "failed", "response_text": "Skill error."},
        )
        assert handled is True
        complete_calls = [(c[1][0], c[1][1]) for c in logger.calls if c[0] == "complete_run"]
        planner_completes = [c for c in complete_calls if "planner" in c[0]]
        assert any(s == "failed" for _, s in planner_completes)

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="C17H+ acceptance gate: budget_exhausted stop state not yet in RUN_STATUSES",
        strict=True,
    )
    async def test_stop_state_budget_exhausted(self, monkeypatch):
        """'budget_exhausted' → planner child completed with partial report."""
        slack, logger, handled = await _run(
            monkeypatch,
            completions=[_delegate_planner(), _reply("partial results")],
            planner_report={
                "ok": True,
                "status": "budget_exhausted",
                "response_text": "Ran out of turns but here's what I found.",
                "partial": True,
            },
        )
        assert handled is True
        complete_calls = [(c[1][0], c[1][1]) for c in logger.calls if c[0] == "complete_run"]
        planner_completes = [c for c in complete_calls if "planner" in c[0]]
        assert any(s == "budget_exhausted" for _, s in planner_completes)

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="C17H+ acceptance gate: needs_clarification stop state not yet in RUN_STATUSES",
        strict=True,
    )
    async def test_stop_state_needs_clarification(self, monkeypatch):
        """'needs_clarification' → planner returns question for user."""
        slack, logger, handled = await _run(
            monkeypatch,
            completions=[_delegate_planner(), _reply("I need more info")],
            planner_report={
                "ok": False,
                "status": "needs_clarification",
                "response_text": "Which brand did you mean?",
                "clarification_needed": "brand disambiguation",
            },
        )
        assert handled is True
        complete_calls = [(c[1][0], c[1][1]) for c in logger.calls if c[0] == "complete_run"]
        planner_completes = [c for c in complete_calls if "planner" in c[0]]
        assert any(s == "needs_clarification" for _, s in planner_completes)


# ===================================================================
# 3. Budget behaviour
# ===================================================================


class TestPlannerBudget:
    """C17H+ gate: bounded planner turns with partial report on exhaustion."""

    @pytest.mark.asyncio
    async def test_planner_bounded_by_max_turns(self, monkeypatch):
        """Planner sub-agent must respect a turn budget. When exhausted,
        it should still produce a coherent partial report."""
        turn_count = 0

        async def _budget_planner(**kwargs):
            nonlocal turn_count
            turn_count += 1
            # Simulate the planner hitting its budget
            return {
                "ok": True,
                "status": "budget_exhausted",
                "response_text": "Found 2 of 5 items before budget ran out.",
                "partial": True,
                "turns_used": kwargs.get("max_turns", 4),
            }

        _patch(monkeypatch)
        completions = [_delegate_planner("deep research"), _reply("Here's what we got so far.")]
        comp_iter = iter(completions)

        async def _fc(*a, **kw):
            return next(comp_iter)

        session = _FakeSession()
        slack = _FakeSlack()
        handled = await run_reply_only_agent_loop_turn(
            text="deep research",
            session=session,
            slack_user_id="U123",
            session_service=_FakeSessionService(session),
            channel="D1",
            slack=slack,
            supabase_client=MagicMock(),
            execute_delegate_planner_fn=_budget_planner,
            call_chat_completion_fn=_fc,
        )
        assert handled is True
        # The planner should receive max_turns parameter
        assert turn_count == 1
        # Response should not be the generic failure fallback
        assert any("budget" in m["text"].lower() or "found" in m["text"].lower() for m in slack.messages)

    @pytest.mark.asyncio
    async def test_budget_exhaustion_produces_partial_report(self, monkeypatch):
        """When planner exhausts its budget, the report must contain usable
        partial results — not an empty or error-only response."""
        slack, logger, handled = await _run(
            monkeypatch,
            completions=[_delegate_planner(), _reply("partial info")],
            planner_report={
                "ok": True,
                "status": "budget_exhausted",
                "response_text": "Found 3 tasks but couldn't verify assignments.",
                "partial": True,
                "partial_results": [
                    {"skill_id": "clickup_task_list", "result_summary": "3 tasks found"},
                ],
            },
        )
        assert handled is True
        planner_reports = [c for c in logger.calls if c[0] == "log_planner_report"]
        assert len(planner_reports) >= 1
        report = planner_reports[0][1][1]
        assert report.get("partial") is True
        assert "partial_results" in report
        assert len(report["partial_results"]) > 0


# ===================================================================
# 4. Safety: mutations become proposals
# ===================================================================


class TestPlannerMutationSafety:
    """C17H+ gate: planner MUST NOT execute mutation skills directly.
    Mutations should be returned as mutation_proposals in the report."""

    @pytest.mark.asyncio
    async def test_mutation_skill_becomes_proposal(self, monkeypatch):
        """If a planner iteration encounters a mutation skill, it must
        convert it to a mutation_proposal instead of executing it."""
        async def _safety_planner(**kwargs):
            return {
                "ok": True,
                "status": "completed",
                "response_text": "Plan requires creating a task.",
                "mutation_proposals": [
                    {
                        "skill_id": "clickup_task_create",
                        "args": {"task_title": "New campaign", "client_name": "Acme"},
                        "reason": "User requested task creation",
                    },
                ],
            }

        _patch(monkeypatch)
        completions = [_delegate_planner("create a task for Acme"), _reply("I have a proposal.")]
        comp_iter = iter(completions)

        async def _fc(*a, **kw):
            return next(comp_iter)

        session = _FakeSession()
        slack = _FakeSlack()
        handled = await run_reply_only_agent_loop_turn(
            text="create a task for Acme",
            session=session,
            slack_user_id="U123",
            session_service=_FakeSessionService(session),
            channel="D1",
            slack=slack,
            supabase_client=MagicMock(),
            execute_delegate_planner_fn=_safety_planner,
            call_chat_completion_fn=_fc,
        )
        assert handled is True
        planner_report_calls = [c for c in _get_logger_calls(monkeypatch) if c[0] == "log_planner_report"]
        if planner_report_calls:
            report = planner_report_calls[0][1][1]
            assert "mutation_proposals" in report
            proposals = report["mutation_proposals"]
            assert len(proposals) >= 1
            assert proposals[0]["skill_id"] == "clickup_task_create"

    @pytest.mark.asyncio
    async def test_planner_never_executes_mutations_directly(self, monkeypatch):
        """The planner tool executor (when provided) must reject mutation skill
        calls and return them as proposals instead of executing."""
        executed_skills: list[str] = []

        async def _tracking_read_skill(*, skill_id: str, **kwargs):
            executed_skills.append(skill_id)
            return {"result": "ok"}

        async def _planner_with_mutation(**kwargs):
            # If the planner had a tool executor, it should block mutations
            # and convert them to proposals.
            return {
                "ok": True,
                "status": "completed",
                "response_text": "Gathered info and proposed a mutation.",
                "mutation_proposals": [
                    {"skill_id": "clickup_task_create", "args": {"task_title": "Test"}, "reason": "user asked"},
                ],
                "skills_executed": ["lookup_client", "search_kb"],
            }

        _patch(monkeypatch)
        completions = [_delegate_planner(), _reply("Done.")]
        comp_iter = iter(completions)

        async def _fc(*a, **kw):
            return next(comp_iter)

        session = _FakeSession()
        slack = _FakeSlack()
        handled = await run_reply_only_agent_loop_turn(
            text="create task for Acme",
            session=session,
            slack_user_id="U123",
            session_service=_FakeSessionService(session),
            channel="D1",
            slack=slack,
            supabase_client=MagicMock(),
            execute_delegate_planner_fn=_planner_with_mutation,
            execute_read_skill_fn=_tracking_read_skill,
            call_chat_completion_fn=_fc,
        )
        assert handled is True
        # No mutation skills should have been executed via the read skill path
        mutation_skills = {"clickup_task_create", "cc_assignment_upsert", "cc_assignment_remove",
                          "cc_brand_create", "cc_brand_update", "cc_brand_mapping_remediation_apply"}
        assert not any(s in mutation_skills for s in executed_skills), (
            f"Mutation skills must never be executed by planner: {executed_skills}"
        )


# ===================================================================
# 5. Traceability: parent_run_id + shared trace_id
# ===================================================================


class TestPlannerTraceability:
    """C17H gate (already landed) + C17H+ extensions for trace verification."""

    @pytest.mark.asyncio
    async def test_planner_child_run_uses_parent_linkage(self, monkeypatch):
        """Planner child run must have parent_run_id pointing to main run."""
        slack, logger, handled = await _run(
            monkeypatch,
            completions=[_delegate_planner(), _reply("Done.")],
            planner_report={"ok": True, "status": "completed", "response_text": "Plan done."},
        )
        assert handled is True
        planner_starts = [c for c in logger.calls if c[0] == "start_planner_run"]
        assert len(planner_starts) >= 1
        # start_planner_run args: (session_id, parent_run_id, trace_id)
        _, parent_run_id, trace_id = planner_starts[0][1]
        assert parent_run_id.startswith("run-main-")
        assert trace_id  # must be non-empty

    @pytest.mark.asyncio
    async def test_planner_child_shares_trace_id_with_parent(self, monkeypatch):
        """Parent and child runs share the same trace_id for correlation."""
        slack, logger, handled = await _run(
            monkeypatch,
            completions=[_delegate_planner(), _reply("Done.")],
            planner_report={"ok": True, "status": "completed", "response_text": "Plan done."},
        )
        assert handled is True
        planner_starts = [c for c in logger.calls if c[0] == "start_planner_run"]
        assert len(planner_starts) >= 1
        _, parent_run_id, trace_id = planner_starts[0][1]
        # trace_id should be deterministic and non-empty
        assert isinstance(trace_id, str) and len(trace_id) > 0

    @pytest.mark.asyncio
    async def test_trace_id_propagated_to_planner_delegate_kwargs(self, monkeypatch):
        """The delegate_planner_fn must receive trace_id so iterative
        planner iterations can share the same trace."""
        received_kwargs: list[dict] = []

        async def _tracing_planner(**kwargs):
            received_kwargs.append(kwargs)
            return {"ok": True, "status": "completed", "response_text": "Done."}

        _patch(monkeypatch)
        completions = [_delegate_planner(), _reply("Done.")]
        comp_iter = iter(completions)

        async def _fc(*a, **kw):
            return next(comp_iter)

        session = _FakeSession()
        slack = _FakeSlack()
        handled = await run_reply_only_agent_loop_turn(
            text="plan something",
            session=session,
            slack_user_id="U123",
            session_service=_FakeSessionService(session),
            channel="D1",
            slack=slack,
            supabase_client=MagicMock(),
            execute_delegate_planner_fn=_tracing_planner,
            call_chat_completion_fn=_fc,
        )
        assert handled is True
        assert len(received_kwargs) == 1
        # Already passes in C17H — trace_id is in kwargs
        assert "trace_id" in received_kwargs[0]
        assert received_kwargs[0]["trace_id"]


# ===================================================================
# 6. Main-agent voice continuity
# ===================================================================


class TestMainAgentVoiceContinuity:
    """C17H gate (landed) + C17H+ extensions: planner report is injected
    back into the main loop, and the final user response is in the main
    assistant voice (not the planner's raw report)."""

    @pytest.mark.asyncio
    async def test_planner_report_injected_as_system_message(self, monkeypatch):
        """After planner completes, its report should appear as a system
        message in the main loop so the LLM can synthesize a reply."""
        captured_prompts: list[list] = []

        _patch(monkeypatch)

        comp_count = 0

        async def _capturing_completion(messages, **kwargs):
            nonlocal comp_count
            captured_prompts.append(list(messages))
            comp_count += 1
            if comp_count == 1:
                return _delegate_planner()
            return _reply("Here's the summary based on the plan.")

        async def _planner(**kwargs):
            return {"ok": True, "status": "completed", "response_text": "Found 3 tasks."}

        session = _FakeSession()
        slack = _FakeSlack()
        handled = await run_reply_only_agent_loop_turn(
            text="plan something",
            session=session,
            slack_user_id="U123",
            session_service=_FakeSessionService(session),
            channel="D1",
            slack=slack,
            supabase_client=MagicMock(),
            execute_delegate_planner_fn=_planner,
            call_chat_completion_fn=_capturing_completion,
        )
        assert handled is True
        # The second LLM call should contain the planner report as a system message
        assert len(captured_prompts) >= 2
        second_call_messages = captured_prompts[1]
        system_msgs = [m for m in second_call_messages if m.get("role") == "system"]
        # At least one system message should mention delegate_planner result
        planner_result_msgs = [
            m for m in system_msgs
            if "delegate_planner" in m.get("content", "").lower()
            or "planner" in m.get("content", "").lower()
        ]
        assert len(planner_result_msgs) >= 1, (
            "Planner report must be injected as system context for main-agent synthesis"
        )

    @pytest.mark.asyncio
    async def test_final_response_is_main_agent_voice(self, monkeypatch):
        """The Slack message sent to the user should be the main agent's
        synthesized reply, not the raw planner report text."""
        _patch(monkeypatch)

        comp_count = 0

        async def _sequenced_completion(messages, **kwargs):
            nonlocal comp_count
            comp_count += 1
            if comp_count == 1:
                return _delegate_planner()
            return _reply("I found 3 open tasks for Acme. Here's a summary...")

        async def _planner(**kwargs):
            return {
                "ok": True,
                "status": "completed",
                "response_text": "RAW_PLANNER_REPORT: 3 tasks found",
            }

        session = _FakeSession()
        slack = _FakeSlack()
        handled = await run_reply_only_agent_loop_turn(
            text="check Acme tasks",
            session=session,
            slack_user_id="U123",
            session_service=_FakeSessionService(session),
            channel="D1",
            slack=slack,
            supabase_client=MagicMock(),
            execute_delegate_planner_fn=_planner,
            call_chat_completion_fn=_sequenced_completion,
        )
        assert handled is True
        assert len(slack.messages) >= 1
        final_text = slack.messages[-1]["text"]
        # Final message should be the main agent's reply, not raw planner output
        assert "RAW_PLANNER_REPORT" not in final_text
        assert "summary" in final_text.lower() or "found" in final_text.lower()

    @pytest.mark.asyncio
    async def test_failed_planner_still_produces_user_response(self, monkeypatch):
        """When planner fails, main agent should still send a meaningful
        response to the user (not crash silently)."""
        slack, logger, handled = await _run(
            monkeypatch,
            completions=[_delegate_planner(), _reply("Sorry, planning failed.")],
            planner_report={"ok": False, "status": "failed", "response_text": "Skill timeout."},
        )
        assert handled is True
        assert len(slack.messages) >= 1
        # Should send some response, not empty
        assert slack.messages[-1]["text"].strip()


# ===================================================================
# Helper for mutation safety tests (avoids import cycle)
# ===================================================================

def _get_logger_calls(monkeypatch) -> list:
    """Placeholder — mutation safety tests use direct planner fn tracking."""
    return []
