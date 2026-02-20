"""C10D: Deterministic plan executor for AgencyClaw.

Executes validated plans step-by-step:
- Only whitelisted skill IDs (from skill_registry) are dispatched
- Each step runs through the C10A policy gate
- Policy denial aborts the remaining plan (fail-closed)
- Non-policy errors are recorded but execution continues to the next step
- No dynamic code/skill injection — dispatch is a static skill_id→handler map
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine, TypedDict

from .planner import ExecutionPlan

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class StepResult(TypedDict):
    skill_id: str
    status: str        # "success" | "denied" | "error" | "skipped"
    reason: str
    user_message: str


class ExecutionResult(TypedDict):
    plan_intent: str
    steps_attempted: int
    steps_succeeded: int
    step_results: list[StepResult]
    aborted: bool
    abort_reason: str | None


# Type alias for handler dispatch map
SkillHandler = Callable[..., Coroutine[Any, Any, None]]


# ---------------------------------------------------------------------------
# Main executor
# ---------------------------------------------------------------------------


async def execute_plan(
    *,
    plan: ExecutionPlan,
    slack_user_id: str,
    channel: str,
    session: Any,
    session_service: Any,
    slack: Any,
    check_policy: Any,         # async callable: (slack_user_id, session, channel, skill_id) -> PolicyDecision
    handler_map: dict[str, SkillHandler],  # skill_id → async handler
) -> ExecutionResult:
    """Execute a validated plan step-by-step.

    Parameters
    ----------
    plan : ExecutionPlan
        Validated plan from ``generate_plan``.
    check_policy : callable
        Async function matching ``_check_skill_policy`` signature.
    handler_map : dict
        Maps skill_id → async handler. Each handler is called with
        ``(slack_user_id=, channel=, client_name_hint=, session_service=, slack=, **extra_args)``.
    """
    step_results: list[StepResult] = []
    steps_succeeded = 0
    aborted = False
    abort_reason: str | None = None

    for i, step in enumerate(plan["steps"]):
        skill_id = step["skill_id"]
        args = step["args"]

        # --- Policy gate ---
        try:
            policy = await check_policy(
                slack_user_id=slack_user_id,
                session=session,
                channel=channel,
                skill_id=skill_id,
            )
        except Exception:
            logger.warning("C10D: Policy check failed for step %d (%s)", i, skill_id, exc_info=True)
            step_results.append(StepResult(
                skill_id=skill_id,
                status="error",
                reason="Policy check failed",
                user_message="",
            ))
            continue

        if not policy["allowed"]:
            await slack.post_message(channel=channel, text=policy["user_message"])
            step_results.append(StepResult(
                skill_id=skill_id,
                status="denied",
                reason=policy.get("reason_code", "denied"),
                user_message=policy["user_message"],
            ))
            aborted = True
            abort_reason = f"Step {i} ({skill_id}) denied: {policy.get('reason_code', 'denied')}"

            # Mark remaining steps as skipped
            for remaining in plan["steps"][i + 1:]:
                step_results.append(StepResult(
                    skill_id=remaining["skill_id"],
                    status="skipped",
                    reason="Plan aborted by policy denial",
                    user_message="",
                ))
            break

        # --- Dispatch to handler ---
        handler = handler_map.get(skill_id)
        if handler is None:
            logger.warning("C10D: No handler registered for skill: %s", skill_id)
            step_results.append(StepResult(
                skill_id=skill_id,
                status="error",
                reason=f"No handler for {skill_id}",
                user_message="",
            ))
            continue

        try:
            # Build handler kwargs from step args
            handler_kwargs: dict[str, Any] = {
                "slack_user_id": slack_user_id,
                "channel": channel,
                "session_service": session_service,
                "slack": slack,
            }
            # Map common arg patterns
            if "client_name" in args:
                handler_kwargs["client_name_hint"] = str(args["client_name"] or "")
            else:
                handler_kwargs["client_name_hint"] = ""
            if "task_title" in args:
                handler_kwargs["task_title"] = str(args["task_title"] or "")
            if skill_id in ("clickup_task_list", "clickup_task_list_weekly"):
                if "window" in args:
                    handler_kwargs["window"] = str(args.get("window") or "")
                if "window_days" in args:
                    handler_kwargs["window_days"] = args.get("window_days")
                if "date_from" in args:
                    handler_kwargs["date_from"] = str(args.get("date_from") or "")
                if "date_to" in args:
                    handler_kwargs["date_to"] = str(args.get("date_to") or "")
            if skill_id.startswith("cc_"):
                handler_kwargs["plan_args"] = dict(args)

            await handler(**handler_kwargs)
            step_results.append(StepResult(
                skill_id=skill_id,
                status="success",
                reason=step.get("reason", ""),
                user_message="",
            ))
            steps_succeeded += 1
        except Exception:
            logger.warning("C10D: Handler failed for step %d (%s)", i, skill_id, exc_info=True)
            step_results.append(StepResult(
                skill_id=skill_id,
                status="error",
                reason="Handler execution failed",
                user_message="",
            ))

    return ExecutionResult(
        plan_intent=plan["intent"],
        steps_attempted=len(plan["steps"]),
        steps_succeeded=steps_succeeded,
        step_results=step_results,
        aborted=aborted,
        abort_reason=abort_reason,
    )
