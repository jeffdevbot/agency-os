"""Minimal Phase-1 Slack runtime for The Claw reboot."""

from __future__ import annotations

import logging
import re
from typing import Any

from ..slack import get_slack_service
from .openai_client import OpenAIConfigurationError, OpenAIError, call_chat_completion

_logger = logging.getLogger(__name__)

_FALLBACK_REPLY = "I ran into a temporary issue generating a reply. Please retry."
_MUTATION_DISCLAIMER = (
    "I can draft and advise, but I cannot execute actions in ClickUp or other systems yet."
)
_MUTATION_REQUEST_RE = re.compile(
    r"\b(create|add|update|delete|remove|assign|send|post|publish|launch)\b.*\b(task|clickup|email|campaign|message)\b"
    r"|\b(task|clickup|email|campaign|message)\b.*\b(create|add|update|delete|remove|assign|send|post|publish|launch)\b",
    re.IGNORECASE,
)
_MEETING_KEYWORD_RE = re.compile(r"\bmeeting\b", re.IGNORECASE)
_MEETING_NOTES_KEYWORD_RE = re.compile(
    r"\b(notes?|summary|transcript|minutes|recap|follow[- ]?up)\b",
    re.IGNORECASE,
)
_TASK_KEYWORD_RE = re.compile(r"\b(task|action items?|next steps?)\b", re.IGNORECASE)


def _build_system_prompt() -> str:
    return (
        "You are The Claw, an agency operations copilot for Amazon-focused client work. "
        "Keep answers concise, clear, and action-oriented, and avoid generic marketing fluff. "
        "In this minimal mode, you can advise and draft text only. "
        "Do not claim to have created tasks, changed systems, sent messages, or performed external actions. "
        "If asked to execute an action, explicitly state that you cannot execute system actions yet, then provide the best draft. "
        "For task drafting, if key fields are missing (client/brand, owner, due date, priority), ask up to 2 clarifying questions before finalizing the draft. "
        "When using lists, use plain numbered format like '1.' and do not use bold-number bullets."
    )


def _build_meeting_task_system_prompt() -> str:
    return (
        f"{_build_system_prompt()} "
        "When the user shares meeting notes, convert them into practical task drafts only. "
        "Do not claim anything was created in external systems. "
        "Use this exact structure: "
        "'Draft tasks (not executed):' then numbered tasks. "
        "Each task must include these fields on separate lines: "
        "'Title:', 'Why this matters:', 'Suggested owner:', 'Suggested due date:', 'Priority:', 'Needs clarification?:'. "
        "Use 'TBD' for unknown fields. "
        "After the list, include 'Clarifying questions:' with up to 3 concise questions only if needed."
    )


def _trim_reply(content: str) -> str:
    reply = (content or "").strip()
    if not reply:
        return _FALLBACK_REPLY
    return reply


def _is_meeting_to_task_request(text: str) -> bool:
    if not text:
        return False
    has_meeting = bool(_MEETING_KEYWORD_RE.search(text))
    has_notes = bool(_MEETING_NOTES_KEYWORD_RE.search(text))
    has_tasking = bool(_TASK_KEYWORD_RE.search(text))
    looks_like_pasted_notes = len(text) >= 350 and "\n" in text
    return (has_meeting and has_tasking and (has_notes or looks_like_pasted_notes)) or (
        has_notes and has_tasking and looks_like_pasted_notes
    )


def _is_mutation_request(text: str) -> bool:
    return bool(_MUTATION_REQUEST_RE.search(text or ""))


def _apply_mutation_disclaimer(*, user_text: str, reply_text: str) -> str:
    if not _is_mutation_request(user_text):
        return reply_text
    normalized_reply = (reply_text or "").lower()
    if "cannot execute" in normalized_reply or "can't create" in normalized_reply:
        return reply_text
    return f"{_MUTATION_DISCLAIMER}\n\n{reply_text}"


async def run_theclaw_minimal_dm_turn(*, slack_user_id: str, channel: str, text: str) -> None:
    user_text = (text or "").strip()
    if not user_text:
        return

    system_prompt = _build_system_prompt()
    if _is_meeting_to_task_request(user_text):
        system_prompt = _build_meeting_task_system_prompt()

    slack = get_slack_service()
    try:
        try:
            response = await call_chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
                temperature=0.2,
                max_tokens=500,
            )
            reply_text = _trim_reply(response["content"])
            reply_text = _apply_mutation_disclaimer(user_text=user_text, reply_text=reply_text)
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
