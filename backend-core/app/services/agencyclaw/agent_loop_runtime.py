"""C17D: Feature-flagged reply-only agent loop runtime helper.

This module intentionally supports only the reply path (no skill calls).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from .agent_loop_context_assembler import assemble_prompt_context
from .agent_loop_store import AgentLoopStore
from .agent_loop_turn_logger import AgentLoopTurnLogger
from .openai_client import ChatCompletionResult, call_chat_completion

_LOGGER = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are AgencyClaw, an internal assistant for e-commerce operations. "
    "Reply conversationally and helpfully using available conversation context. "
    "Do not claim to perform actions in this mode; this is reply-only."
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


async def run_reply_only_agent_loop_turn(
    *,
    text: str,
    session: Any,
    channel: str,
    slack: Any,
    supabase_client: Any,
    call_chat_completion_fn: Callable[..., Awaitable[ChatCompletionResult]] = call_chat_completion,
    logger: logging.Logger = _LOGGER,
) -> bool:
    """Run a C17D reply-only turn with run/message logging.

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
        assistant_text = (completion.get("content") or "").strip() or "How can I help?"

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
