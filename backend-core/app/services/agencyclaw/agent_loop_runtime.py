"""C17D/C17E: Feature-flagged agent loop runtime helper.

C17D: reply-only turn handling
C17E: single read-only tool round-trip (`clickup_task_list`) per turn
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

from .agent_loop_context_assembler import assemble_prompt_context
from .agent_loop_store import AgentLoopStore
from .agent_loop_turn_logger import AgentLoopTurnLogger
from .openai_client import ChatCompletionResult, OpenAIError, call_chat_completion, parse_json_response

_LOGGER = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are AgencyClaw, an internal assistant for e-commerce operations. "
    "Reply conversationally and helpfully using available conversation context. "
    "For this runtime version, you may request at most one read-only tool call "
    "using strict JSON only. Output either "
    '{"mode":"reply","text":"..."} or '
    '{"mode":"tool_call","skill_id":"clickup_task_list","args":{...}}.'
)
_FAILURE_FALLBACK_TEXT = (
    "I hit an issue while processing that. Could you rephrase and try again?"
)


def _build_session_rows(session: Any) -> list[dict[str, Any]]:
    """Convert legacy recent_exchanges session context into message rows."""
    context = getattr(session, "context", {}) or {}
    exchanges = context.get("recent_exchanges")
    if not isinstance(exchanges, list):
        return []

    rows: list[dict[str, Any]] = []
    for idx, exchange in enumerate(exchanges):
        if not isinstance(exchange, dict):
            continue
        user_text = exchange.get("user")
        if isinstance(user_text, str) and user_text.strip():
            rows.append(
                {
                    "role": "user",
                    "content": {"text": user_text.strip()},
                    "created_at": f"session-{idx:04d}-u",
                }
            )
        assistant_text = exchange.get("assistant")
        if isinstance(assistant_text, str) and assistant_text.strip():
            rows.append(
                {
                    "role": "assistant",
                    "content": {"text": assistant_text.strip()},
                    "created_at": f"session-{idx:04d}-a",
                }
            )
    return rows


def _extract_mode_payload(content: str) -> dict[str, Any]:
    """Parse model content into reply/tool_call envelope."""
    try:
        payload = parse_json_response(content)
    except OpenAIError:
        text = content.strip()
        return {"mode": "reply", "text": text or "How can I help?"}

    mode = str(payload.get("mode") or "").strip()
    if mode == "tool_call":
        return {
            "mode": "tool_call",
            "skill_id": str(payload.get("skill_id") or "").strip(),
            "args": payload.get("args") if isinstance(payload.get("args"), dict) else {},
        }

    text = payload.get("text")
    if isinstance(text, str) and text.strip():
        return {"mode": "reply", "text": text.strip()}
    return {"mode": "reply", "text": content.strip() or "How can I help?"}


def _validate_task_list_args(args: dict[str, Any]) -> dict[str, Any]:
    allowed = {"client_name", "window", "window_days", "date_from", "date_to"}
    for key in args:
        if key not in allowed:
            raise ValueError(f"unsupported arg: {key}")

    normalized: dict[str, Any] = {}
    if "client_name" in args and args["client_name"] is not None:
        normalized["client_name"] = str(args["client_name"])
    if "window" in args and args["window"] is not None:
        normalized["window"] = str(args["window"])
    if "window_days" in args and args["window_days"] is not None:
        value = args["window_days"]
        if isinstance(value, bool):
            raise ValueError("window_days must be int-like")
        if isinstance(value, (int, float, str)):
            try:
                normalized["window_days"] = int(value)
            except (TypeError, ValueError) as exc:
                raise ValueError("window_days must be int-like") from exc
        else:
            raise ValueError("window_days must be int-like")
    if "date_from" in args and args["date_from"] is not None:
        normalized["date_from"] = str(args["date_from"])
    if "date_to" in args and args["date_to"] is not None:
        normalized["date_to"] = str(args["date_to"])
    return normalized


async def run_reply_only_agent_loop_turn(
    *,
    text: str,
    session: Any,
    slack_user_id: str,
    session_service: Any,
    channel: str,
    slack: Any,
    supabase_client: Any,
    execute_task_list_fn: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    call_chat_completion_fn: Callable[..., Awaitable[ChatCompletionResult]] = call_chat_completion,
    logger: logging.Logger = _LOGGER,
) -> bool:
    """Run a C17D/C17E turn with run/message/event logging.

    Returns True when the turn was handled (including fallback paths).
    """
    store = AgentLoopStore(supabase_client)
    turn_logger = AgentLoopTurnLogger(store)
    run_id: str | None = None

    try:
        run = await asyncio.to_thread(turn_logger.start_main_run, str(session.id))
        run_id = str(run.get("id") or "").strip()
        if not run_id:
            raise ValueError("failed to create agent run")

        await asyncio.to_thread(turn_logger.log_user_message, run_id, text)

        session_rows = _build_session_rows(session)
        run_rows = await asyncio.to_thread(store.list_recent_run_messages, run_id, 20)
        assembled = assemble_prompt_context(
            messages=[*session_rows, *run_rows],
            skill_events=[],
            budget_chars=4000,
        )

        prompt_messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
        prompt_messages.extend(assembled["messages_for_llm"])
        if not any(m.get("role") == "user" for m in assembled["messages_for_llm"]):
            prompt_messages.append({"role": "user", "content": text})

        completion = await call_chat_completion_fn(
            prompt_messages,
            temperature=0.2,
            max_tokens=400,
        )
        first_payload = _extract_mode_payload(str(completion.get("content") or ""))

        if first_payload.get("mode") == "tool_call":
            skill_id = str(first_payload.get("skill_id") or "")
            if skill_id != "clickup_task_list":
                raise ValueError(f"disallowed skill in C17E: {skill_id}")
            if execute_task_list_fn is None:
                raise ValueError("task-list executor not provided")

            args = _validate_task_list_args(first_payload.get("args") or {})
            await asyncio.to_thread(turn_logger.log_skill_call, run_id, skill_id, args)
            tool_result = await execute_task_list_fn(
                slack_user_id=slack_user_id,
                channel=channel,
                args=args,
                session=session,
                session_service=session_service,
            )
            if not isinstance(tool_result, dict):
                raise ValueError("tool result must be dict")
            await asyncio.to_thread(turn_logger.log_skill_result, run_id, skill_id, tool_result)

            tool_context = json.dumps(tool_result, ensure_ascii=True, separators=(",", ":"))
            second_prompt = list(prompt_messages)
            second_prompt.append(
                {
                    "role": "system",
                    "content": (
                        "Tool result for clickup_task_list (JSON): " + tool_context
                        + ". Respond naturally to the user using this result."
                    ),
                }
            )
            second_prompt.append({"role": "user", "content": text})
            completion2 = await call_chat_completion_fn(
                second_prompt,
                temperature=0.2,
                max_tokens=400,
            )
            second_payload = _extract_mode_payload(str(completion2.get("content") or ""))
            assistant_text = str(second_payload.get("text") or "").strip() or "How can I help?"
        else:
            assistant_text = str(first_payload.get("text") or "").strip() or "How can I help?"

        await slack.post_message(channel=channel, text=assistant_text)
        await asyncio.to_thread(turn_logger.log_assistant_message, run_id, assistant_text)
        await asyncio.to_thread(turn_logger.complete_run, run_id, "completed")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Agent loop reply-only turn failed: %s", exc, exc_info=True)
        if run_id:
            try:
                await asyncio.to_thread(turn_logger.complete_run, run_id, "failed")
            except Exception:  # noqa: BLE001
                pass
        await slack.post_message(channel=channel, text=_FAILURE_FALLBACK_TEXT)
        return True
