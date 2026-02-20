"""C10D: Constrained planner for AgencyClaw.

Takes user text + context and produces a strict JSON execution plan.
The plan contains ordered steps, each mapping to a whitelisted skill_id
with validated args. Unknown/invalid plans fail closed to None.

No open-ended ReAct loop — the planner runs once and returns a fixed plan.
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from .openai_client import (
    ChatMessage,
    OpenAIError,
    call_chat_completion,
    parse_json_response,
)
from .skill_registry import SKILL_SCHEMAS, get_skill_descriptions_for_prompt, validate_skill_call

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

MAX_PLAN_STEPS = 3


class PlanStep(TypedDict):
    skill_id: str
    args: dict[str, Any]
    requires_confirmation: bool
    reason: str


class ExecutionPlan(TypedDict):
    intent: str
    steps: list[PlanStep]
    confidence: float
    tokens_in: int | None
    tokens_out: int | None
    tokens_total: int | None
    model_used: str | None


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_TEMPLATE = """\
You are a task planner for an agency operations bot.

Given the user's request, produce a JSON execution plan that maps to available skills.

## Available skills
{available_skills}

## KB context
{kb_context_summary}

## Client context
{client_context_pack}

## Session state
{session_state_summary}

## Output format (strict JSON, no markdown fences)
{{
  "intent": "<short description of user intent>",
  "steps": [
    {{
      "skill_id": "<must be one of the available skill IDs>",
      "args": {{}},
      "requires_confirmation": true,
      "reason": "<why this step>"
    }}
  ],
  "confidence": 0.0
}}

## Rules
- Only use skill_ids from the available skills list above.
- Each step must have all required args filled; use null for optional args you don't have.
- If you cannot map the request to available skills, return: {{"intent": "unknown", "steps": [], "confidence": 0.0}}
- Maximum {max_steps} steps.
- Set requires_confirmation=true for any step that creates or modifies data.
- Do not invent skill_ids that are not listed above.
"""


# ---------------------------------------------------------------------------
# Plan validation
# ---------------------------------------------------------------------------


def _validate_plan(parsed: dict[str, Any]) -> ExecutionPlan | None:
    """Validate parsed LLM output into a strict ExecutionPlan.

    Returns None if validation fails (caller should fall back).
    """
    intent = str(parsed.get("intent") or "unknown")
    confidence = float(parsed.get("confidence") or 0.0)
    steps_raw = parsed.get("steps")

    if not isinstance(steps_raw, list):
        logger.warning("C10D: Plan steps is not a list")
        return None

    if len(steps_raw) > MAX_PLAN_STEPS:
        logger.warning("C10D: Plan has %d steps (max %d)", len(steps_raw), MAX_PLAN_STEPS)
        return None

    # Empty steps with intent != "unknown" is suspicious
    if not steps_raw and intent != "unknown":
        logger.warning("C10D: Non-unknown intent with empty steps")
        return None

    # Empty plan (intent=unknown, steps=[]) is valid — means "can't handle"
    if not steps_raw:
        return ExecutionPlan(
            intent=intent,
            steps=[],
            confidence=0.0,
            tokens_in=None,
            tokens_out=None,
            tokens_total=None,
            model_used=None,
        )

    validated_steps: list[PlanStep] = []
    for i, raw_step in enumerate(steps_raw):
        if not isinstance(raw_step, dict):
            logger.warning("C10D: Step %d is not a dict", i)
            return None

        skill_id = str(raw_step.get("skill_id") or "")
        if skill_id not in SKILL_SCHEMAS:
            logger.warning("C10D: Step %d has unknown skill_id: %s", i, skill_id)
            return None

        args = raw_step.get("args") or {}
        if not isinstance(args, dict):
            logger.warning("C10D: Step %d args is not a dict", i)
            return None

        # Validate args against schema (allow missing optional args)
        errors = validate_skill_call(skill_id, args)
        if errors:
            logger.warning("C10D: Step %d validation errors: %s", i, errors)
            return None

        validated_steps.append(PlanStep(
            skill_id=skill_id,
            args=args,
            requires_confirmation=bool(raw_step.get("requires_confirmation", True)),
            reason=str(raw_step.get("reason") or ""),
        ))

    return ExecutionPlan(
        intent=intent,
        steps=validated_steps,
        confidence=confidence,
        tokens_in=None,
        tokens_out=None,
        tokens_total=None,
        model_used=None,
    )


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------


async def generate_plan(
    *,
    text: str,
    session_context: dict[str, Any],
    client_context_pack: str,
    kb_context_summary: str,
    available_skills: str | None = None,
) -> ExecutionPlan | None:
    """Generate a constrained execution plan from user text.

    Returns None on any failure (LLM error, parse error, validation error).
    Caller should fall back to existing routing.
    """
    if available_skills is None:
        available_skills = get_skill_descriptions_for_prompt()

    # Build session state summary
    session_parts: list[str] = []
    if session_context.get("active_client_id"):
        session_parts.append(f"Active client ID: {session_context['active_client_id']}")
    if session_context.get("pending_task_create"):
        session_parts.append("A task creation is in progress.")
    session_state_summary = "\n".join(session_parts) if session_parts else "No active session state."

    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        available_skills=available_skills,
        kb_context_summary=kb_context_summary or "None available.",
        client_context_pack=client_context_pack or "No client context.",
        session_state_summary=session_state_summary,
        max_steps=MAX_PLAN_STEPS,
    )

    messages: list[ChatMessage] = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=text),
    ]

    try:
        result = await call_chat_completion(messages, temperature=0.1, max_tokens=500)
    except OpenAIError as exc:
        logger.warning("C10D: LLM call failed: %s", exc)
        return None
    except Exception:
        logger.warning("C10D: Unexpected error in LLM call", exc_info=True)
        return None

    try:
        parsed = parse_json_response(result["content"])
    except OpenAIError as exc:
        logger.warning("C10D: Failed to parse plan JSON: %s", exc)
        return None

    plan = _validate_plan(parsed)
    if plan is None:
        return None

    # Attach token telemetry
    plan["tokens_in"] = result.get("tokens_in")
    plan["tokens_out"] = result.get("tokens_out")
    plan["tokens_total"] = result.get("tokens_total")
    plan["model_used"] = result.get("model")

    return plan
