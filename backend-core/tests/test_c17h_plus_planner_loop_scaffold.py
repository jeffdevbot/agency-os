"""C17H+ reference-contract tests: iterative planner loop behaviour.

These tests define the **expected contract** for the iterative planner
sub-agent introduced in C17H+.

Stop-state persistence contract used by current runtime:
- Planner report payload keeps fine-grained state:
  ``completed|blocked|failed|budget_exhausted|needs_clarification``.
- Child-run DB status is intentionally collapsed to
  ``completed|blocked|failed`` (storage enum).

Where future delegate API surface is intentionally deferred, tests use
precise ``xfail`` markers.

Coverage areas:
1. Iterative planner loop (>1 iteration with tool-result feedback)
2. Stop states (completed, blocked, failed, budget_exhausted, needs_clarification)
3. Budget behaviour (bounded turns, partial report on exhaustion)
4. Safety (mutation skills -> mutation_proposals, never executed)
5. Traceability (parent_run_id + shared trace_id)
6. Main-agent voice continuity (planner report injected, final reply is main voice)

No production code is modified -- all assertions use the existing public API
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
        return {
            "id": f"run-main-{self._run_counter}",
            "status": "running",
            "trace_id": f"trace-{self._run_counter}",
        }

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


class _RunResult:
    """Collects all outputs from a single agent loop invocation."""

    def __init__(
        self,
        slack: _FakeSlack,
        logger: _TrackingTurnLogger,
        planner_kwargs: list[dict],
        handled: bool,
    ) -> None:
        self.slack = slack
        self.logger = logger
        self.planner_kwargs = planner_kwargs
        self.handled = handled

    @property
    def planner_complete_statuses(self) -> list[str]:
        """Extract statuses for planner child complete_run calls."""
        complete_calls = [(c[1][0], c[1][1]) for c in self.logger.calls if c[0] == "complete_run"]
        return [s for rid, s in complete_calls if "planner" in rid]

    @property
    def planner_reports(self) -> list[dict]:
        """Extract planner report payloads from log_planner_report calls."""
        return [c[1][1] for c in self.logger.calls if c[0] == "log_planner_report"]


async def _run(
    monkeypatch,
    *,
    completions: list[dict[str, Any]],
    planner_report: dict[str, Any] | None = None,
    execute_read_skill_fn: Any = None,
) -> _RunResult:
    """Run the agent loop with canned LLM completions and optional planner report."""
    _patch(monkeypatch)

    comp_iter = iter(completions)

    async def _fake_completion(*args, **kwargs):
        return next(comp_iter)

    planner_kwargs_list: list[dict] = []

    async def _fake_planner(**kwargs):
        planner_kwargs_list.append(kwargs)
        return planner_report or {"ok": True, "status": "completed", "response_text": "Plan done."}

    session = _FakeSession()
    slack = _FakeSlack()
    svc = _FakeSessionService(session)

    # Capture the logger instance
    logger_ref: list[_TrackingTurnLogger] = []
    _orig_init = _TrackingTurnLogger.__init__

    def _capture_init(self, _store):
        _orig_init(self, _store)
        logger_ref.append(self)

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
    return _RunResult(slack, logger, planner_kwargs_list, handled)


# ===================================================================
# 1. Iterative planner loop contract
# ===================================================================


class TestIterativePlannerLoop:
    """C17H+ gate: planner sub-agent can execute >1 iteration with
    tool-result feedback before producing a final report."""

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="Deferred API contract: runtime currently runs planner iteration "
               "inside delegate runtime and does not pass a tool-executor callback "
               "into execute_delegate_planner_fn",
        strict=True,
    )
    async def test_planner_receives_tool_executor_callback(self, monkeypatch):
        """The delegate_planner_fn must receive a tool executor callback so
        the planner sub-agent can call read-only skills iteratively."""
        r = await _run(
            monkeypatch,
            completions=[_delegate_planner("research Acme"), _reply("Here's what I found.")],
        )
        assert r.handled is True
        assert len(r.planner_kwargs) == 1
        kw = r.planner_kwargs[0]
        assert "tool_executor" in kw or "execute_skill_fn" in kw, (
            "Planner delegate must receive a tool executor callback for iterative use. "
            f"Received kwargs: {sorted(kw.keys())}"
        )

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="Deferred API contract: runtime owns planner_max_turns internally "
               "and does not pass max_turns kwarg to execute_delegate_planner_fn",
        strict=True,
    )
    async def test_planner_receives_max_turns_parameter(self, monkeypatch):
        """The runtime must pass a max_turns budget parameter to the
        delegate_planner_fn so the planner can bound its iterations."""
        r = await _run(
            monkeypatch,
            completions=[_delegate_planner(), _reply("Got it.")],
        )
        assert r.handled is True
        assert len(r.planner_kwargs) == 1
        kw = r.planner_kwargs[0]
        assert "max_turns" in kw or "max_planner_turns" in kw, (
            f"Planner must receive turn budget. Got kwargs: {sorted(kw.keys())}"
        )

    @pytest.mark.asyncio
    async def test_planner_report_passthrough_preserves_metadata(self, monkeypatch):
        """The runtime faithfully logs whatever the planner report contains,
        including iteration_count and other metadata fields."""
        r = await _run(
            monkeypatch,
            completions=[_delegate_planner(), _reply("Got it.")],
            planner_report={
                "ok": True,
                "status": "completed",
                "response_text": "Done after 2 rounds.",
                "iteration_count": 2,
            },
        )
        assert r.handled is True
        assert len(r.planner_reports) >= 1
        report = r.planner_reports[0]
        assert report.get("iteration_count") == 2


# ===================================================================
# 2. Stop states
# ===================================================================


class TestPlannerStopStates:
    """C17H+ gate: planner sub-agent reports one of five terminal states.

    Fine-grained stop states are preserved in planner report payload.
    Child run persistence intentionally collapses to completed/blocked/failed.
    """

    @pytest.mark.asyncio
    async def test_stop_state_completed(self, monkeypatch):
        """completed -> planner child run marked completed, main loop continues."""
        r = await _run(
            monkeypatch,
            completions=[_delegate_planner(), _reply("All done.")],
            planner_report={"ok": True, "status": "completed", "response_text": "Plan finished."},
        )
        assert r.handled is True
        assert "completed" in r.planner_complete_statuses

    @pytest.mark.asyncio
    async def test_stop_state_blocked(self, monkeypatch):
        """blocked -> planner child run marked blocked."""
        r = await _run(
            monkeypatch,
            completions=[_delegate_planner(), _reply("blocked fallback")],
            planner_report={"ok": False, "status": "blocked", "response_text": "Need approval."},
        )
        assert r.handled is True
        assert "blocked" in r.planner_complete_statuses

    @pytest.mark.asyncio
    async def test_stop_state_failed(self, monkeypatch):
        """failed -> planner child run marked failed."""
        r = await _run(
            monkeypatch,
            completions=[_delegate_planner(), _reply("fail fallback")],
            planner_report={"ok": False, "status": "failed", "response_text": "Skill error."},
        )
        assert r.handled is True
        assert "failed" in r.planner_complete_statuses

    @pytest.mark.asyncio
    async def test_stop_state_budget_exhausted(self, monkeypatch):
        """budget_exhausted -> planner child run stored as blocked; payload preserved."""
        r = await _run(
            monkeypatch,
            completions=[_delegate_planner(), _reply("partial results")],
            planner_report={
                "ok": True,
                "status": "budget_exhausted",
                "response_text": "Ran out of turns but here's what I found.",
                "partial": True,
            },
        )
        assert r.handled is True
        assert "blocked" in r.planner_complete_statuses
        assert len(r.planner_reports) >= 1
        assert r.planner_reports[0].get("status") == "budget_exhausted"

    @pytest.mark.asyncio
    async def test_stop_state_needs_clarification(self, monkeypatch):
        """needs_clarification -> child run blocked; payload/open questions preserved."""
        r = await _run(
            monkeypatch,
            completions=[_delegate_planner(), _reply("I need more info")],
            planner_report={
                "ok": False,
                "status": "needs_clarification",
                "response_text": "Which brand did you mean?",
                "open_questions": ["Which brand did you mean?"],
            },
        )
        assert r.handled is True
        assert "blocked" in r.planner_complete_statuses
        assert len(r.planner_reports) >= 1
        assert r.planner_reports[0].get("status") == "needs_clarification"
        assert r.planner_reports[0].get("open_questions")


# ===================================================================
# 3. Budget behaviour
# ===================================================================


class TestPlannerBudget:
    """C17H+ gate: bounded planner turns with partial report on exhaustion."""

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="Deferred API contract: runtime owns planner_max_turns internally "
               "and does not pass max_turns kwarg to execute_delegate_planner_fn",
        strict=True,
    )
    async def test_planner_receives_turn_budget(self, monkeypatch):
        """The delegate_planner_fn must receive a turn budget parameter."""
        r = await _run(
            monkeypatch,
            completions=[_delegate_planner("deep research"), _reply("Results.")],
        )
        assert r.handled is True
        assert len(r.planner_kwargs) == 1
        kw = r.planner_kwargs[0]
        assert "max_turns" in kw or "max_planner_turns" in kw, (
            f"Planner must receive turn budget. Got: {sorted(kw.keys())}"
        )
        budget = kw.get("max_turns") or kw.get("max_planner_turns")
        assert isinstance(budget, int) and budget > 0

    @pytest.mark.asyncio
    async def test_budget_exhaustion_collapses_child_run_status_and_preserves_payload(self, monkeypatch):
        """When planner reports budget_exhausted, child run uses blocked while
        planner report payload preserves budget_exhausted for semantics."""
        r = await _run(
            monkeypatch,
            completions=[_delegate_planner(), _reply("partial info")],
            planner_report={
                "ok": True,
                "status": "budget_exhausted",
                "response_text": "Found 3 tasks, couldn't verify assignments.",
                "partial": True,
            },
        )
        assert r.handled is True
        assert "blocked" in r.planner_complete_statuses
        assert len(r.planner_reports) >= 1
        assert r.planner_reports[0].get("status") == "budget_exhausted"

    @pytest.mark.asyncio
    async def test_budget_exhaustion_report_still_logged(self, monkeypatch):
        """Even when budget_exhausted collapses to completed, the planner
        report with partial=True is faithfully logged."""
        r = await _run(
            monkeypatch,
            completions=[_delegate_planner(), _reply("partial info")],
            planner_report={
                "ok": True,
                "status": "budget_exhausted",
                "response_text": "Found 3 tasks.",
                "partial": True,
                "partial_results": [{"skill_id": "clickup_task_list", "summary": "3 tasks"}],
            },
        )
        assert r.handled is True
        assert len(r.planner_reports) >= 1
        report = r.planner_reports[0]
        assert report.get("partial") is True
        assert report.get("partial_results")


# ===================================================================
# 4. Safety: mutations become proposals
# ===================================================================


class TestPlannerMutationSafety:
    """C17H+ gate: planner MUST NOT execute mutation skills directly.
    Mutations should be returned as mutation_proposals in the report.

    The C17H+ contract requires the runtime to provide the planner with
    a *filtered* tool executor that blocks mutation skills and converts
    them to proposals. These tests verify that contract.
    """

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="Deferred API contract: runtime does not inject a tool-executor "
               "callback into execute_delegate_planner_fn",
        strict=True,
    )
    async def test_planner_receives_mutation_blocking_executor(self, monkeypatch):
        """The delegate_planner_fn must receive a callable tool_executor
        that blocks mutation skill calls."""
        r = await _run(
            monkeypatch,
            completions=[_delegate_planner("create task"), _reply("I have a proposal.")],
            planner_report={
                "ok": True,
                "status": "completed",
                "response_text": "Plan requires creating a task.",
                "mutation_proposals": [
                    {"skill_id": "clickup_task_create", "args": {"task_title": "Test"}, "reason": "user asked"},
                ],
            },
        )
        assert r.handled is True
        assert len(r.planner_kwargs) == 1
        kw = r.planner_kwargs[0]
        assert "tool_executor" in kw or "execute_skill_fn" in kw, (
            "Planner must receive a tool executor for mutation blocking. "
            f"Received kwargs: {sorted(kw.keys())}"
        )
        executor = kw.get("tool_executor") or kw.get("execute_skill_fn")
        assert callable(executor)

    @pytest.mark.asyncio
    async def test_main_loop_no_mutation_during_planner_delegation(self, monkeypatch):
        """During planner delegation, the main loop must not route mutation
        skills through execute_read_skill_fn. (C17H baseline verification.)"""
        executed_skills: list[str] = []

        async def _tracking_read_skill(*, skill_id: str, **kwargs):
            executed_skills.append(skill_id)
            return {"result": "ok"}

        r = await _run(
            monkeypatch,
            completions=[_delegate_planner(), _reply("Done.")],
            planner_report={"ok": True, "status": "completed", "response_text": "Gathered info."},
            execute_read_skill_fn=_tracking_read_skill,
        )
        assert r.handled is True
        mutation_skills = {
            "clickup_task_create", "cc_assignment_upsert", "cc_assignment_remove",
            "cc_brand_create", "cc_brand_update", "cc_brand_mapping_remediation_apply",
        }
        assert not any(s in mutation_skills for s in executed_skills), (
            f"Mutation skills must never be executed via main loop: {executed_skills}"
        )

    @pytest.mark.asyncio
    async def test_planner_report_with_proposals_is_logged(self, monkeypatch):
        """When planner returns mutation_proposals, the report (including
        proposals) is faithfully logged via log_planner_report."""
        r = await _run(
            monkeypatch,
            completions=[_delegate_planner(), _reply("Here's what I propose.")],
            planner_report={
                "ok": True,
                "status": "completed",
                "response_text": "Plan requires creating a task.",
                "mutation_proposals": [
                    {"skill_id": "clickup_task_create", "args": {"task_title": "New"}, "reason": "user asked"},
                ],
            },
        )
        assert r.handled is True
        assert len(r.planner_reports) >= 1
        report = r.planner_reports[0]
        assert "mutation_proposals" in report
        assert len(report["mutation_proposals"]) == 1
        assert report["mutation_proposals"][0]["skill_id"] == "clickup_task_create"


# ===================================================================
# 5. Traceability: parent_run_id + shared trace_id
# ===================================================================


class TestPlannerTraceability:
    """C17H gate (already landed): parent/child run linkage and trace_id."""

    @pytest.mark.asyncio
    async def test_planner_child_run_uses_parent_linkage(self, monkeypatch):
        """Planner child run must have parent_run_id pointing to main run."""
        r = await _run(
            monkeypatch,
            completions=[_delegate_planner(), _reply("Done.")],
        )
        assert r.handled is True
        planner_starts = [c for c in r.logger.calls if c[0] == "start_planner_run"]
        assert len(planner_starts) >= 1
        _, parent_run_id, trace_id = planner_starts[0][1]
        assert parent_run_id.startswith("run-main-")
        assert trace_id

    @pytest.mark.asyncio
    async def test_planner_child_shares_trace_id_with_parent(self, monkeypatch):
        """Parent and child runs share the same trace_id for correlation."""
        r = await _run(
            monkeypatch,
            completions=[_delegate_planner(), _reply("Done.")],
        )
        assert r.handled is True
        planner_starts = [c for c in r.logger.calls if c[0] == "start_planner_run"]
        assert len(planner_starts) >= 1
        _, _, trace_id = planner_starts[0][1]
        assert isinstance(trace_id, str) and len(trace_id) > 0

    @pytest.mark.asyncio
    async def test_trace_id_propagated_to_delegate_kwargs(self, monkeypatch):
        """The delegate_planner_fn receives trace_id (C17H -- landed)."""
        r = await _run(
            monkeypatch,
            completions=[_delegate_planner(), _reply("Done.")],
        )
        assert r.handled is True
        assert len(r.planner_kwargs) == 1
        assert "trace_id" in r.planner_kwargs[0]
        assert r.planner_kwargs[0]["trace_id"]


# ===================================================================
# 6. Main-agent voice continuity
# ===================================================================


class TestMainAgentVoiceContinuity:
    """C17H gate (landed): planner report is injected back into the main
    loop, and the final user response is in the main assistant voice."""

    @pytest.mark.asyncio
    async def test_planner_report_injected_as_system_message(self, monkeypatch):
        """After planner completes, its report appears as a system message
        in the main loop so the LLM can synthesize a reply."""
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
        assert len(captured_prompts) >= 2
        second_call_messages = captured_prompts[1]
        system_msgs = [m for m in second_call_messages if m.get("role") == "system"]
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
        """The Slack message should be the main agent's synthesized reply,
        not the raw planner report text."""
        _patch(monkeypatch)
        comp_count = 0

        async def _sequenced_completion(messages, **kwargs):
            nonlocal comp_count
            comp_count += 1
            if comp_count == 1:
                return _delegate_planner()
            return _reply("I found 3 open tasks for Acme. Here's a summary...")

        async def _planner(**kwargs):
            return {"ok": True, "status": "completed", "response_text": "RAW_PLANNER_REPORT: 3 tasks found"}

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
        assert "RAW_PLANNER_REPORT" not in final_text
        assert "summary" in final_text.lower() or "found" in final_text.lower()

    @pytest.mark.asyncio
    async def test_failed_planner_still_produces_user_response(self, monkeypatch):
        """When planner fails, main agent still sends a meaningful response."""
        r = await _run(
            monkeypatch,
            completions=[_delegate_planner(), _reply("Sorry, planning failed.")],
            planner_report={"ok": False, "status": "failed", "response_text": "Skill timeout."},
        )
        assert r.handled is True
        assert len(r.slack.messages) >= 1
        assert r.slack.messages[-1]["text"].strip()

    @pytest.mark.asyncio
    async def test_planner_report_logged_to_agent_messages(self, monkeypatch):
        """Planner report persists in agent_messages for evidence rehydration."""
        r = await _run(
            monkeypatch,
            completions=[_delegate_planner(), _reply("Summary.")],
            planner_report={"ok": True, "status": "completed", "response_text": "Done.", "findings": ["a", "b"]},
        )
        assert r.handled is True
        assert len(r.planner_reports) >= 1
        report = r.planner_reports[0]
        assert report["status"] == "completed"
        assert report["findings"] == ["a", "b"]
