"""Planner delegate runtime extracted from Slack route layer."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


class _CaptureSlack:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def post_message(
        self,
        *,
        channel: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> None:
        _ = channel, blocks
        self.messages.append(text)


@dataclass(frozen=True)
class SlackPlannerDelegateRuntimeDeps:
    logger: logging.Logger
    get_supabase_admin_client_fn: Callable[[], Any]
    retrieve_kb_context_fn: Callable[..., Awaitable[dict[str, Any]]]
    generate_plan_fn: Callable[..., Awaitable[dict[str, Any]]]
    execute_plan_fn: Callable[..., Awaitable[dict[str, Any]]]
    get_skill_descriptions_for_prompt_fn: Callable[..., str]
    check_skill_policy_fn: Callable[..., Awaitable[dict[str, Any]]]
    execute_read_skill_fn: Callable[..., Awaitable[dict[str, Any]]]
    handle_cc_skill_fn: Callable[..., Awaitable[str | None]]
    agent_loop_store_cls: type[Any]
    agent_loop_turn_logger_cls: type[Any]


async def execute_planner_delegate_for_agent_loop_runtime(
    *,
    request_text: str,
    slack_user_id: str,
    channel: str,
    session: Any,
    session_service: Any,
    parent_run_id: str,
    child_run_id: str,
    trace_id: str,
    tool_executor: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    execute_skill_fn: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    max_planner_turns: int = 6,
    max_turns: int | None = None,
    deps: SlackPlannerDelegateRuntimeDeps,
) -> dict[str, Any]:
    _ = parent_run_id, child_run_id, trace_id
    capture = _CaptureSlack()
    planner_step_executor = tool_executor or execute_skill_fn
    planner_max_turns = (
        max_turns
        if isinstance(max_turns, int) and not isinstance(max_turns, bool) and max_turns > 0
        else max_planner_turns
        if isinstance(max_planner_turns, int)
        and not isinstance(max_planner_turns, bool)
        and max_planner_turns > 0
        else 6
    )
    planner_logger = deps.agent_loop_turn_logger_cls(
        deps.agent_loop_store_cls(deps.get_supabase_admin_client_fn())
    )
    mutation_skill_ids = {
        "clickup_task_create",
        "cc_assignment_upsert",
        "cc_assignment_remove",
        "cc_brand_create",
        "cc_brand_update",
        "cc_brand_mapping_remediation_apply",
    }
    planner_executable_read_skills = {
        "clickup_task_list",
        "clickup_task_list_weekly",
        "cc_client_lookup",
        "cc_brand_list_all",
        "cc_brand_clickup_mapping_audit",
        "cc_brand_mapping_remediation_preview",
        "lookup_client",
        "lookup_brand",
        "search_kb",
        "resolve_brand",
        "get_client_context",
        "load_prior_skill_result",
    }
    planner_prompt_skill_ids = planner_executable_read_skills | mutation_skill_ids

    try:
        client_context_pack = ""
        if session.active_client_id:
            client_name = await asyncio.to_thread(
                session_service.get_client_name, session.active_client_id
            )
            client_context_pack = (
                f"Active client: {client_name or 'Unknown'} (id={session.active_client_id})"
            )

        kb_summary = ""
        try:
            retrieval = await deps.retrieve_kb_context_fn(
                query=request_text,
                client_id=str(session.active_client_id or ""),
                db=deps.get_supabase_admin_client_fn(),
            )
            sources = retrieval.get("sources", []) if isinstance(retrieval, dict) else []
            if isinstance(sources, list) and sources:
                kb_summary = "\n".join(
                    f"- [{s.get('tier', '?')}] {s.get('title', 'Untitled')}: {str(s.get('content', ''))[:200]}"
                    for s in sources[:3]
                    if isinstance(s, dict)
                )
        except Exception:  # noqa: BLE001
            kb_summary = ""

        async def _planner_read_step_handler(
            *,
            skill_id: str,
            client_name_hint: str = "",
            plan_args: dict[str, Any] | None = None,
            **_kwargs: Any,
        ) -> None:
            args = dict(plan_args or {})
            if client_name_hint and not args.get("client_name"):
                args["client_name"] = client_name_hint
            if skill_id == "clickup_task_list_weekly" and not args.get("window"):
                args["window"] = "this_week"
            canonical_skill = (
                "clickup_task_list" if skill_id == "clickup_task_list_weekly" else skill_id
            )
            if planner_step_executor is not None:
                try:
                    callback_result = await planner_step_executor(
                        skill_id=canonical_skill,
                        args=args,
                        plan_args=args,
                        slack_user_id=slack_user_id,
                        channel=channel,
                        session=session,
                        session_service=session_service,
                    )
                    if isinstance(callback_result, dict):
                        callback_text = str(callback_result.get("response_text") or "").strip()
                        if callback_text:
                            capture.messages.append(callback_text)
                        return
                    raise ValueError("planner delegate callback must return dict")
                except Exception:  # noqa: BLE001
                    deps.logger.warning(
                        "Planner delegate callback failed for %s; falling back to local read handler",
                        canonical_skill,
                        exc_info=True,
                    )
            await deps.execute_read_skill_fn(
                skill_id=canonical_skill,
                slack_user_id=slack_user_id,
                channel=channel,
                args=args,
                session=session,
                session_service=session_service,
            )

        async def _planner_cc_step_handler(
            *,
            skill_id: str,
            client_name_hint: str = "",
            plan_args: dict[str, Any] | None = None,
            **_kwargs: Any,
        ) -> None:
            args = dict(plan_args or {})
            if client_name_hint and not args.get("client_name"):
                args["client_name"] = client_name_hint
            if planner_step_executor is not None:
                try:
                    callback_result = await planner_step_executor(
                        skill_id=skill_id,
                        args=args,
                        plan_args=args,
                        slack_user_id=slack_user_id,
                        channel=channel,
                        session=session,
                        session_service=session_service,
                    )
                    if isinstance(callback_result, dict):
                        callback_text = str(callback_result.get("response_text") or "").strip()
                        if callback_text:
                            capture.messages.append(callback_text)
                        return
                    raise ValueError("planner delegate callback must return dict")
                except Exception:  # noqa: BLE001
                    deps.logger.warning(
                        "Planner delegate callback failed for %s; falling back to local CC handler",
                        skill_id,
                        exc_info=True,
                    )
            await deps.handle_cc_skill_fn(
                skill_id=skill_id,
                args=args,
                session=session,
                session_service=session_service,
                channel=channel,
                slack=capture,
            )

        handler_map = {
            "clickup_task_list": lambda **kwargs: _planner_read_step_handler(
                skill_id="clickup_task_list", **kwargs
            ),
            "clickup_task_list_weekly": lambda **kwargs: _planner_read_step_handler(
                skill_id="clickup_task_list_weekly", **kwargs
            ),
            "cc_client_lookup": lambda **kwargs: _planner_read_step_handler(
                skill_id="cc_client_lookup", **kwargs
            ),
            "cc_brand_list_all": lambda **kwargs: _planner_read_step_handler(
                skill_id="cc_brand_list_all", **kwargs
            ),
            "cc_brand_clickup_mapping_audit": lambda **kwargs: _planner_read_step_handler(
                skill_id="cc_brand_clickup_mapping_audit", **kwargs
            ),
            "cc_brand_mapping_remediation_preview": lambda **kwargs: _planner_cc_step_handler(
                skill_id="cc_brand_mapping_remediation_preview", **kwargs
            ),
            "lookup_client": lambda **kwargs: _planner_read_step_handler(
                skill_id="lookup_client", **kwargs
            ),
            "lookup_brand": lambda **kwargs: _planner_read_step_handler(
                skill_id="lookup_brand", **kwargs
            ),
            "search_kb": lambda **kwargs: _planner_read_step_handler(
                skill_id="search_kb", **kwargs
            ),
            "resolve_brand": lambda **kwargs: _planner_read_step_handler(
                skill_id="resolve_brand", **kwargs
            ),
            "get_client_context": lambda **kwargs: _planner_read_step_handler(
                skill_id="get_client_context", **kwargs
            ),
            "load_prior_skill_result": lambda **kwargs: _planner_read_step_handler(
                skill_id="load_prior_skill_result", **kwargs
            ),
        }

        all_mutation_proposals: list[dict[str, Any]] = []
        all_unsupported_steps: list[dict[str, Any]] = []
        iteration_reports: list[dict[str, Any]] = []
        seen_plan_fingerprints: set[str] = set()
        last_exec_result: dict[str, Any] | None = None

        async def _log_child_iteration(
            *,
            turn: int,
            input_text: str,
            plan: dict[str, Any] | None,
            iteration_report: dict[str, Any],
            exec_plan_steps: list[dict[str, Any]] | None = None,
            exec_result: dict[str, Any] | None = None,
        ) -> None:
            try:
                await asyncio.to_thread(
                    planner_logger.log_user_message,
                    child_run_id,
                    f"[planner turn {turn}] {input_text}",
                )
                if isinstance(plan, dict):
                    await asyncio.to_thread(
                        planner_logger.log_skill_call,
                        child_run_id,
                        "delegate_planner",
                        {
                            "turn": turn,
                            "plan_intent": str(plan.get("intent") or "unknown"),
                            "plan": plan,
                        },
                    )
                await asyncio.to_thread(
                    planner_logger.log_skill_result,
                    child_run_id,
                    "delegate_planner",
                    {"turn": turn, "iteration_report": iteration_report},
                )
                await asyncio.to_thread(
                    planner_logger.log_planner_report,
                    child_run_id,
                    {"turn": turn, "plan": plan, "iteration_report": iteration_report},
                )
                if isinstance(exec_plan_steps, list):
                    for planned_step in exec_plan_steps:
                        if not isinstance(planned_step, dict):
                            continue
                        planned_skill_id = str(planned_step.get("skill_id") or "").strip()
                        if not planned_skill_id:
                            continue
                        planned_args = (
                            planned_step.get("args")
                            if isinstance(planned_step.get("args"), dict)
                            else {}
                        )
                        await asyncio.to_thread(
                            planner_logger.log_skill_call,
                            child_run_id,
                            planned_skill_id,
                            {
                                "turn": turn,
                                "source": "planner_iteration",
                                "args": planned_args,
                            },
                        )
                if isinstance(exec_result, dict):
                    step_results = exec_result.get("step_results")
                    if isinstance(step_results, list):
                        for step_result in step_results:
                            if not isinstance(step_result, dict):
                                continue
                            result_skill_id = str(step_result.get("skill_id") or "").strip()
                            if not result_skill_id:
                                continue
                            await asyncio.to_thread(
                                planner_logger.log_skill_result,
                                child_run_id,
                                result_skill_id,
                                {
                                    "turn": turn,
                                    "source": "planner_iteration",
                                    "status": str(step_result.get("status") or ""),
                                    "reason": str(step_result.get("reason") or ""),
                                    "user_message": str(step_result.get("user_message") or ""),
                                },
                            )
            except Exception:  # noqa: BLE001
                deps.logger.warning("Planner child-run iteration logging failed", exc_info=True)

        for turn in range(planner_max_turns):
            iteration_text = request_text
            if iteration_reports:
                previous = iteration_reports[-1]
                iteration_text = (
                    f"{request_text}\n\nPrevious planner iteration result:\n"
                    f"{json.dumps(previous, ensure_ascii=True, separators=(',', ':'))}"
                )

            plan = await deps.generate_plan_fn(
                text=iteration_text,
                session_context=session.context,
                client_context_pack=client_context_pack,
                kb_context_summary=kb_summary,
                available_skills=deps.get_skill_descriptions_for_prompt_fn(
                    include_skill_ids=planner_prompt_skill_ids,
                    exclude_skill_ids={"delegate_planner"},
                ),
            )
            if not plan or not plan.get("steps"):
                await _log_child_iteration(
                    turn=turn + 1,
                    input_text=iteration_text,
                    plan=plan if isinstance(plan, dict) else None,
                    iteration_report={
                        "turn": turn + 1,
                        "status": "needs_clarification",
                        "reason": "no_plan_or_steps",
                    },
                )
                open_q = [f"What should I prioritize for: {request_text}?"]
                return {
                    "ok": True,
                    "status": "needs_clarification",
                    "request_text": request_text,
                    "open_questions": open_q,
                    "iteration_reports": iteration_reports,
                    "mutation_proposals": all_mutation_proposals,
                    "unsupported_steps": all_unsupported_steps,
                    "planner_available_skill_ids": sorted(
                        planner_prompt_skill_ids - {"delegate_planner"}
                    ),
                    "messages": capture.messages,
                    "response_text": "I need a bit more detail before I can complete that plan.",
                }

            plan_fingerprint = json.dumps(
                {
                    "intent": str(plan.get("intent") or ""),
                    "steps": plan.get("steps") if isinstance(plan.get("steps"), list) else [],
                },
                sort_keys=True,
                ensure_ascii=True,
                separators=(",", ":"),
            )
            if plan_fingerprint in seen_plan_fingerprints:
                await _log_child_iteration(
                    turn=turn + 1,
                    input_text=iteration_text,
                    plan=plan,
                    iteration_report={
                        "turn": turn + 1,
                        "status": "completed",
                        "reason": "plan_stabilized",
                    },
                )
                summary = (
                    f"Planner stabilized after {len(iteration_reports)} iteration(s). "
                    f"Executed {int(last_exec_result.get('steps_succeeded', 0)) if isinstance(last_exec_result, dict) else 0}/"
                    f"{int(last_exec_result.get('steps_attempted', 0)) if isinstance(last_exec_result, dict) else 0} steps in the final execution."
                )
                if all_mutation_proposals:
                    summary += (
                        f" Deferred {len(all_mutation_proposals)} mutation proposal(s)."
                    )
                if all_unsupported_steps:
                    summary += f" Blocked {len(all_unsupported_steps)} unsupported step(s)."
                return {
                    "ok": True,
                    "status": "completed",
                    "request_text": request_text,
                    "plan_intent": str(plan.get("intent") or "unknown"),
                    "planner_plan": plan,
                    "execution_result": last_exec_result,
                    "iteration_reports": iteration_reports,
                    "mutation_proposals": all_mutation_proposals,
                    "unsupported_steps": all_unsupported_steps,
                    "planner_available_skill_ids": sorted(
                        planner_prompt_skill_ids - {"delegate_planner"}
                    ),
                    "messages": capture.messages,
                    "response_text": summary,
                }
            seen_plan_fingerprints.add(plan_fingerprint)

            mutation_proposals: list[dict[str, Any]] = []
            executable_steps: list[dict[str, Any]] = []
            for step in plan.get("steps", []):
                if not isinstance(step, dict):
                    continue
                sid = str(step.get("skill_id") or "")
                requires_confirmation = bool(step.get("requires_confirmation"))
                if sid in mutation_skill_ids or requires_confirmation:
                    mutation_proposals.append(
                        {
                            "skill_id": sid,
                            "args": (
                                step.get("args")
                                if isinstance(step.get("args"), dict)
                                else {}
                            ),
                            "reason": str(step.get("reason") or ""),
                            "rejected_reason": "planner_mutation_execution_disallowed",
                        }
                    )
                else:
                    executable_steps.append(step)
            all_mutation_proposals.extend(mutation_proposals)

            unsupported_steps: list[dict[str, Any]] = []
            filtered_exec_steps: list[dict[str, Any]] = []
            for step in executable_steps:
                sid = str(step.get("skill_id") or "")
                if sid in handler_map:
                    filtered_exec_steps.append(step)
                else:
                    unsupported_steps.append(
                        {
                            "skill_id": sid,
                            "args": (
                                step.get("args")
                                if isinstance(step.get("args"), dict)
                                else {}
                            ),
                            "reason": str(step.get("reason") or ""),
                            "rejected_reason": "planner_skill_not_executable",
                        }
                    )
            all_unsupported_steps.extend(unsupported_steps)

            exec_plan = {
                "intent": str(plan.get("intent") or "unknown"),
                "steps": filtered_exec_steps,
                "confidence": float(plan.get("confidence") or 0.0),
                "tokens_in": plan.get("tokens_in"),
                "tokens_out": plan.get("tokens_out"),
                "tokens_total": plan.get("tokens_total"),
                "model_used": plan.get("model_used"),
            }
            if filtered_exec_steps:
                exec_result = await deps.execute_plan_fn(
                    plan=exec_plan,
                    slack_user_id=slack_user_id,
                    channel=channel,
                    session=session,
                    session_service=session_service,
                    slack=capture,
                    check_policy=deps.check_skill_policy_fn,
                    handler_map=handler_map,
                )
            else:
                exec_result = {
                    "plan_intent": str(plan.get("intent") or "unknown"),
                    "steps_attempted": 0,
                    "steps_succeeded": 0,
                    "step_results": [],
                    "aborted": False,
                    "abort_reason": None,
                }
            last_exec_result = exec_result
            iteration_reports.append(
                {
                    "turn": turn + 1,
                    "plan_intent": str(plan.get("intent") or "unknown"),
                    "steps_attempted": int(exec_result.get("steps_attempted", 0)),
                    "steps_succeeded": int(exec_result.get("steps_succeeded", 0)),
                    "mutation_proposals": mutation_proposals,
                    "unsupported_steps": unsupported_steps,
                    "aborted": bool(exec_result.get("aborted", False)),
                    "abort_reason": exec_result.get("abort_reason"),
                }
            )
            await _log_child_iteration(
                turn=turn + 1,
                input_text=iteration_text,
                plan=plan,
                iteration_report=iteration_reports[-1],
                exec_plan_steps=filtered_exec_steps,
                exec_result=exec_result if isinstance(exec_result, dict) else None,
            )

            if bool(exec_result.get("aborted")):
                return {
                    "ok": False,
                    "status": "blocked",
                    "request_text": request_text,
                    "plan_intent": str(plan.get("intent") or "unknown"),
                    "planner_plan": plan,
                    "execution_result": exec_result,
                    "iteration_reports": iteration_reports,
                    "mutation_proposals": all_mutation_proposals,
                    "unsupported_steps": all_unsupported_steps,
                    "planner_available_skill_ids": sorted(
                        planner_prompt_skill_ids - {"delegate_planner"}
                    ),
                    "messages": capture.messages,
                    "response_text": "I couldn't complete that plan because one step was blocked.",
                    "error": "planner_blocked",
                }

            if not filtered_exec_steps and mutation_proposals and not unsupported_steps:
                return {
                    "ok": True,
                    "status": "completed",
                    "request_text": request_text,
                    "plan_intent": str(plan.get("intent") or "unknown"),
                    "planner_plan": plan,
                    "execution_result": exec_result,
                    "iteration_reports": iteration_reports,
                    "mutation_proposals": all_mutation_proposals,
                    "unsupported_steps": all_unsupported_steps,
                    "planner_available_skill_ids": sorted(
                        planner_prompt_skill_ids - {"delegate_planner"}
                    ),
                    "messages": capture.messages,
                    "response_text": f"Planner prepared {len(all_mutation_proposals)} mutation proposal(s) for confirmation.",
                }

        partial_summary = (
            f"Planner reached iteration budget ({planner_max_turns}) with "
            f"{len(iteration_reports)} iteration report(s)."
        )
        await _log_child_iteration(
            turn=planner_max_turns,
            input_text=request_text,
            plan=None,
            iteration_report={
                "turn": planner_max_turns,
                "status": "budget_exhausted",
                "iterations_completed": len(iteration_reports),
            },
        )
        if all_mutation_proposals:
            partial_summary += (
                f" Deferred {len(all_mutation_proposals)} mutation proposal(s)."
            )
        if all_unsupported_steps:
            partial_summary += f" Blocked {len(all_unsupported_steps)} unsupported step(s)."
        return {
            "ok": True,
            "status": "budget_exhausted",
            "request_text": request_text,
            "execution_result": last_exec_result,
            "iteration_reports": iteration_reports,
            "mutation_proposals": all_mutation_proposals,
            "unsupported_steps": all_unsupported_steps,
            "planner_available_skill_ids": sorted(
                planner_prompt_skill_ids - {"delegate_planner"}
            ),
            "messages": capture.messages,
            "response_text": partial_summary,
        }
    except Exception as exc:  # noqa: BLE001
        deps.logger.warning("Agent-loop planner delegate failed: %s", exc, exc_info=True)
        return {
            "ok": False,
            "status": "failed",
            "request_text": request_text,
            "messages": capture.messages,
            "response_text": "I couldn't run planning right now. Could you try again?",
            "error": "planner_exception",
        }

