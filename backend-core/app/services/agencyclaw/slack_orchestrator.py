"""LLM-first Slack DM orchestrator for AgencyClaw.

Decides whether to reply directly, ask a clarifying question, or call a tool skill.
"""

from __future__ import annotations

from typing import Any, TypedDict

from .conversation_buffer import Exchange, exchanges_to_chat_messages
from .openai_client import (
    ChatMessage,
    OpenAIError,
    call_chat_completion,
    parse_json_response,
)
from .tool_registry import (
    get_missing_required_fields,
    get_tool_descriptions_for_prompt,
    validate_tool_call,
)

_VALID_MODES = {"reply", "clarify", "tool_call"}


class OrchestratorResult(TypedDict):
    mode: str  # "reply" | "clarify" | "tool_call" | "fallback"
    text: str | None
    question: str | None
    missing_fields: list[str] | None
    skill_id: str | None
    args: dict[str, Any] | None
    confidence: float
    reason: str | None
    # Token telemetry (populated on successful LLM call, None on fallback)
    tokens_in: int | None
    tokens_out: int | None
    tokens_total: int | None
    model_used: str | None


def _make_fallback(reason: str) -> OrchestratorResult:
    return OrchestratorResult(
        mode="fallback",
        text=None,
        question=None,
        missing_fields=None,
        skill_id=None,
        args=None,
        confidence=0.0,
        reason=reason,
        tokens_in=None,
        tokens_out=None,
        tokens_total=None,
        model_used=None,
    )


def _build_system_prompt(
    client_context_pack: str,
    session_context: dict[str, Any],
) -> str:
    tool_block = get_tool_descriptions_for_prompt()

    session_summary_parts: list[str] = []
    if session_context.get("active_client_id"):
        session_summary_parts.append(f"Active client ID: {session_context['active_client_id']}")
    if session_context.get("pending_task_create"):
        ptc = session_context["pending_task_create"]
        pending_parts = ["A task creation is in progress."]
        pending_parts.append(f"  Awaiting: {ptc.get('awaiting', 'unknown')}")
        if ptc.get("client_name"):
            pending_parts.append(f"  Client: {ptc['client_name']}")
        if ptc.get("task_title"):
            pending_parts.append(f"  Title: {ptc['task_title']}")
        session_summary_parts.append("\n".join(pending_parts))
    session_summary = "\n".join(session_summary_parts) if session_summary_parts else "No active session state."

    return f"""\
You are AgencyClaw, a friendly agency operations assistant inside a Slack DM.
You are conversational and Jarvis-like — never reply with command menus or syntax hints.
Keep responses short and helpful.

## Available tools
{tool_block}

## Current session
{session_summary}

## Client context
{client_context_pack if client_context_pack.strip() else "No client context available."}

## Instructions
Analyze the user's message and respond with a single JSON object (no markdown fences).

Choose one mode:

1. **tool_call** — The user's request clearly maps to one of the available tools.
   Return: {{"mode": "tool_call", "skill_id": "<tool_name>", "args": {{...}}, "confidence": 0.0-1.0}}
   Include all arguments you can extract. If a required argument is missing, use "clarify" instead.

2. **clarify** — The request likely maps to a tool but required information is missing.
   Return: {{"mode": "clarify", "skill_id": "<tool_name>", "args": {{<partial args collected so far>}}, "question": "<what to ask>", "missing_fields": ["field1", ...], "confidence": 0.0-1.0}}

3. **reply** — The message is conversational, a greeting, off-topic, or a question you can answer directly without tools.
   Return: {{"mode": "reply", "text": "<your response>", "confidence": 0.0-1.0}}
   Use this for greetings, small talk, questions about yourself, and anything that doesn't need a tool.
   Be friendly and natural — do NOT list available commands or suggest command syntax.

Rules:
- Always return valid JSON with the "mode" field.
- For tool_call, only use skill_ids from the available tools list.
- Preserve the user's original casing for task titles.
- If the user says something like "create a task" with no title, use "clarify" with missing_fields ["task_title"].
- Default to "reply" for ambiguous or conversational messages — do NOT force a tool_call.
- confidence should reflect how certain you are about the classification (0.0 = guess, 1.0 = certain).\
"""


async def orchestrate_dm_message(
    text: str,
    profile_id: str | None,
    slack_user_id: str,
    session_context: dict[str, Any],
    client_context_pack: str,
    recent_exchanges: list[Exchange] | None = None,
) -> OrchestratorResult:
    """Classify a Slack DM and return an action decision.

    Returns one of:
    - reply: direct text response
    - clarify: ask a clarifying question (with missing_fields)
    - tool_call: invoke a registered skill
    - fallback: LLM call failed, caller should use deterministic routing
    """
    system_prompt = _build_system_prompt(client_context_pack, session_context)

    # C10B.5: Inject bounded conversation history as alternating messages
    history_messages = exchanges_to_chat_messages(recent_exchanges or [])

    messages: list[ChatMessage] = [
        {"role": "system", "content": system_prompt},
        *history_messages,
        {"role": "user", "content": text},
    ]

    try:
        completion = await call_chat_completion(
            messages, temperature=0.2, max_tokens=500
        )
        parsed = parse_json_response(completion["content"])
    except (OpenAIError, Exception) as exc:
        return _make_fallback(str(exc))

    # Extract token telemetry from successful LLM call
    _tokens_in = completion.get("tokens_in")
    _tokens_out = completion.get("tokens_out")
    _tokens_total = completion.get("tokens_total")
    _model_used = completion.get("model")

    mode = parsed.get("mode", "")
    if mode not in _VALID_MODES:
        return _make_fallback(f"LLM returned invalid mode: {mode!r}")

    confidence = float(parsed.get("confidence", 0.5))

    if mode == "tool_call":
        skill_id = parsed.get("skill_id", "")
        args = parsed.get("args") or {}
        if not isinstance(args, dict):
            args = {}

        errors = validate_tool_call(skill_id, args)
        if errors:
            missing = get_missing_required_fields(skill_id, args)
            if missing:
                return OrchestratorResult(
                    mode="clarify",
                    text=None,
                    question=f"I need a bit more info to proceed. What's the {', '.join(missing)}?",
                    missing_fields=missing,
                    skill_id=skill_id,
                    args=args,
                    confidence=confidence,
                    reason=None,
                    tokens_in=_tokens_in,
                    tokens_out=_tokens_out,
                    tokens_total=_tokens_total,
                    model_used=_model_used,
                )
            return _make_fallback(f"Invalid tool call: {'; '.join(errors)}")

        return OrchestratorResult(
            mode="tool_call",
            text=None,
            question=None,
            missing_fields=None,
            skill_id=skill_id,
            args=args,
            confidence=confidence,
            reason=None,
            tokens_in=_tokens_in,
            tokens_out=_tokens_out,
            tokens_total=_tokens_total,
            model_used=_model_used,
        )

    if mode == "clarify":
        return OrchestratorResult(
            mode="clarify",
            text=None,
            question=str(parsed.get("question", "Could you provide more details?")),
            missing_fields=parsed.get("missing_fields") or [],
            skill_id=parsed.get("skill_id"),
            args=parsed.get("args") if isinstance(parsed.get("args"), dict) else None,
            confidence=confidence,
            reason=None,
            tokens_in=_tokens_in,
            tokens_out=_tokens_out,
            tokens_total=_tokens_total,
            model_used=_model_used,
        )

    # mode == "reply"
    return OrchestratorResult(
        mode="reply",
        text=str(parsed.get("text", "")),
        question=None,
        missing_fields=None,
        skill_id=None,
        args=None,
        confidence=confidence,
        reason=None,
        tokens_in=_tokens_in,
        tokens_out=_tokens_out,
        tokens_total=_tokens_total,
        model_used=_model_used,
    )
