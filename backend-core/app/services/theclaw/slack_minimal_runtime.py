"""Minimal Phase-1 Slack runtime for The Claw reboot."""

from __future__ import annotations

import logging
from typing import Any

from ..slack import get_slack_service
from .openai_client import OpenAIConfigurationError, OpenAIError, call_chat_completion

_logger = logging.getLogger(__name__)

_FALLBACK_REPLY = "I ran into a temporary issue generating a reply. Please retry."


def _build_system_prompt() -> str:
    return (
        "You are The Claw, a practical assistant for running an Amazon agency. "
        "Keep answers concise, clear, and action-oriented. "
        "In this minimal mode, you can advise and draft text only. "
        "Do not claim to have created tasks, changed systems, or performed external actions. "
        "If asked to execute something, explain the limitation briefly and provide the next best draft."
    )


def _trim_reply(content: str) -> str:
    reply = (content or "").strip()
    if not reply:
        return _FALLBACK_REPLY
    return reply


async def run_theclaw_minimal_dm_turn(*, slack_user_id: str, channel: str, text: str) -> None:
    user_text = (text or "").strip()
    if not user_text:
        return

    slack = get_slack_service()
    try:
        try:
            response = await call_chat_completion(
                messages=[
                    {"role": "system", "content": _build_system_prompt()},
                    {"role": "user", "content": user_text},
                ],
                temperature=0.2,
                max_tokens=500,
            )
            reply_text = _trim_reply(response["content"])
        except OpenAIConfigurationError:
            reply_text = "The Claw is not configured yet. Please set OPENAI_API_KEY and try again."
        except OpenAIError as exc:
            _logger.warning("The Claw minimal runtime OpenAI error: %s", exc)
            reply_text = _FALLBACK_REPLY

        await slack.post_message(channel=channel, text=reply_text)
    except Exception as exc:  # noqa: BLE001
        _logger.warning(
            "The Claw minimal runtime failed to post reply (user=%s, channel=%s): %s",
            slack_user_id,
            channel,
            exc,
        )
    finally:
        try:
            await slack.aclose()
        except Exception:  # noqa: BLE001
            pass


async def handle_theclaw_minimal_interaction(*, payload: dict[str, Any]) -> None:
    _logger.info(
        "The Claw minimal runtime ignores Slack interactions",
        extra={"interaction_type": str(payload.get("type") or "")},
    )
