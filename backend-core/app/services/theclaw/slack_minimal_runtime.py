"""Minimal Phase-1 Slack runtime for The Claw reboot."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from ..playbook_session import get_playbook_session_service
from ..slack import get_slack_service
from .openai_client import OpenAIConfigurationError, OpenAIError, call_chat_completion
from .skill_registry import TheClawSkill, build_available_skills_xml, get_skill_by_id, load_skills

_logger = logging.getLogger(__name__)

_FALLBACK_REPLY = "I ran into a temporary issue generating a reply. Please retry."
_NEW_SESSION_REPLY = "Started a new session. I cleared prior conversation context."
_MUTATION_DISCLAIMER = (
    "I can draft and advise, but I cannot execute actions in ClickUp or other systems yet."
)
_NEW_SESSION_RE = re.compile(r"^\s*new session\s*$", re.IGNORECASE)
_MUTATION_REQUEST_RE = re.compile(
    r"\b(create|add|update|delete|remove|assign|send|post|publish|launch)\b.*\b(task|clickup|email|campaign|message)\b"
    r"|\b(task|clickup|email|campaign|message)\b.*\b(create|add|update|delete|remove|assign|send|post|publish|launch)\b",
    re.IGNORECASE,
)
_SESSION_HISTORY_KEY = "theclaw_history_v1"
_SESSION_RESOLVED_CONTEXT_KEY = "theclaw_resolved_context_v1"
_MAX_HISTORY_TURNS = 25
_ENTITY_RESOLVER_SKILL_ID = "entity_resolver"
_SKILL_SELECTION_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
_SKILL_SELECTION_PROMPT = (
    "You are the The Claw skill router. Select at most one skill for this user turn. "
    "Use intent and context, not keyword matching. If no skill is needed, choose 'none'. "
    "Return strict JSON only with this schema: "
    '{"skill_id":"<skill id or none>","confidence":<0.0-1.0>,"reason":"<brief reason>"}. '
    "Do not include markdown, prose, or code fences."
)
_ENTITY_RESOLVER_FIELD_RE = re.compile(r"^\s*([a-zA-Z ]+)\s*:\s*(.+?)\s*$")


def _build_system_prompt(*, selected_skill: TheClawSkill | None = None) -> str:
    prompt = (
        "You are The Claw, an agency operations copilot for Amazon-focused client work. "
        "Keep answers concise, clear, and action-oriented, and avoid generic marketing fluff. "
        "In this minimal mode, you can advise and draft text only. "
        "Do not claim to have created tasks, changed systems, sent messages, or performed external actions. "
        "If asked to execute an action, explicitly state that you cannot execute system actions yet, then provide the best draft. "
        "For task drafting, if key fields are missing (client/brand, owner, due date, priority), ask up to 2 clarifying questions before finalizing the draft. "
        "When using lists, use plain numbered format like '1.' and do not use bold-number bullets."
    )
    if selected_skill is not None:
        prompt = (
            f"{prompt} You are executing skill '{selected_skill.name}' "
            f"(id: {selected_skill.skill_id}). Follow this skill contract exactly: "
            f"{selected_skill.system_prompt}"
        )
    return prompt


def _build_skill_selection_system_prompt(*, available_skills_xml: str) -> str:
    return f"{_SKILL_SELECTION_PROMPT}\n\n{available_skills_xml}"


def _get_session_service():
    return get_playbook_session_service()


def _trim_reply(content: str) -> str:
    reply = (content or "").strip()
    if not reply:
        return _FALLBACK_REPLY
    return reply


def _is_mutation_request(text: str) -> bool:
    return bool(_MUTATION_REQUEST_RE.search(text or ""))


def _is_new_session_command(text: str) -> bool:
    return bool(_NEW_SESSION_RE.match(text or ""))


def _apply_mutation_disclaimer(*, user_text: str, reply_text: str) -> str:
    if not _is_mutation_request(user_text):
        return reply_text
    normalized_reply = (reply_text or "").lower()
    if "cannot execute" in normalized_reply or "can't create" in normalized_reply:
        return reply_text
    return f"{_MUTATION_DISCLAIMER}\n\n{reply_text}"


def _normalize_history_messages(history: Any) -> list[dict[str, str]]:
    if not isinstance(history, list):
        return []

    normalized: list[dict[str, str]] = []
    for item in history:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip()
        content = str(item.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        normalized.append({"role": role, "content": content})
    return normalized


def _history_from_session_context(context: Any) -> list[dict[str, str]]:
    if not isinstance(context, dict):
        return []
    return _normalize_history_messages(context.get(_SESSION_HISTORY_KEY))


def _append_turn_and_cap_history(
    history_messages: list[dict[str, str]],
    *,
    user_text: str,
    assistant_text: str,
) -> list[dict[str, str]]:
    updated = [
        *history_messages,
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": assistant_text},
    ]
    max_messages = _MAX_HISTORY_TURNS * 2
    if len(updated) > max_messages:
        updated = updated[-max_messages:]
    return updated


def _parse_entity_resolver_response(reply_text: str) -> dict[str, Any] | None:
    text = (reply_text or "").strip()
    if not text:
        return None

    lower_text = text.lower()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    has_resolved_header = "resolved context" in lower_text

    field_map: dict[str, str] = {}
    for line in lines:
        match = _ENTITY_RESOLVER_FIELD_RE.match(line)
        if not match:
            continue
        key = match.group(1).strip().lower()
        value = match.group(2).strip()
        if value:
            field_map[key] = value

    if has_resolved_header or any(
        key in field_map
        for key in ("client", "brand", "clickup space", "market scope", "confidence", "notes")
    ):
        context_payload = {
            "client": field_map.get("client"),
            "brand": field_map.get("brand"),
            "clickup_space": field_map.get("clickup space"),
            "market_scope": field_map.get("market scope"),
            "confidence": field_map.get("confidence"),
            "notes": field_map.get("notes"),
        }
        if any(value for value in context_payload.values()):
            return {"mode": "resolved", "context": context_payload}
        return None

    question = next((line for line in lines if "?" in line), "")
    if question:
        return {"mode": "clarification", "question": question}
    return None


def _extract_entity_resolver_context_updates(
    *,
    selected_skill: TheClawSkill | None,
    reply_text: str,
) -> dict[str, Any]:
    if selected_skill is None or selected_skill.skill_id.lower() != _ENTITY_RESOLVER_SKILL_ID:
        return {}

    parsed = _parse_entity_resolver_response(reply_text)
    if not parsed:
        return {}

    mode = str(parsed.get("mode") or "").strip().lower()
    if mode == "resolved":
        context_payload = parsed.get("context")
        if isinstance(context_payload, dict):
            return {_SESSION_RESOLVED_CONTEXT_KEY: context_payload}
    return {}


def _parse_skill_selection(raw_text: str) -> tuple[str | None, float]:
    text = (raw_text or "").strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()

    payload: dict[str, Any] | None = None
    try:
        decoded = json.loads(text)
        if isinstance(decoded, dict):
            payload = decoded
    except json.JSONDecodeError:
        match = _SKILL_SELECTION_JSON_RE.search(text)
        if match:
            try:
                decoded = json.loads(match.group(0))
                if isinstance(decoded, dict):
                    payload = decoded
            except json.JSONDecodeError:
                payload = None

    if not payload:
        return None, 0.0

    skill_id_value = str(payload.get("skill_id") or "").strip().lower()
    confidence_raw = payload.get("confidence", 0)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.0

    if skill_id_value in {"", "none", "null"}:
        return None, max(0.0, min(1.0, confidence))
    return skill_id_value, max(0.0, min(1.0, confidence))


async def _select_skill_for_turn(
    *,
    user_text: str,
    history_messages: list[dict[str, str]],
) -> TheClawSkill | None:
    skills = load_skills()
    if not skills:
        return None

    available_skills_xml = build_available_skills_xml(skills=skills)
    try:
        selection_response = await call_chat_completion(
            messages=[
                {"role": "system", "content": _build_skill_selection_system_prompt(available_skills_xml=available_skills_xml)},
                *history_messages[-8:],
                {"role": "user", "content": user_text},
            ],
            temperature=0.0,
            max_tokens=160,
        )
    except OpenAIError as exc:
        _logger.warning("The Claw skill selection failed, falling back to no skill: %s", exc)
        return None

    selected_skill_id, confidence = _parse_skill_selection(selection_response["content"])
    if not selected_skill_id:
        return None

    selected_skill = get_skill_by_id(selected_skill_id)
    if selected_skill is None:
        _logger.warning("The Claw selected unknown skill id '%s'", selected_skill_id)
        return None

    if confidence < 0.45:
        _logger.info(
            "The Claw skill selection confidence too low; skipping skill",
            extra={"skill_id": selected_skill_id, "confidence": confidence},
        )
        return None
    return selected_skill


async def run_theclaw_minimal_dm_turn(*, slack_user_id: str, channel: str, text: str) -> None:
    user_text = (text or "").strip()
    if not user_text:
        return

    session = None
    history_messages: list[dict[str, str]] = []
    session_service = None
    try:
        session_service = _get_session_service()
    except Exception as exc:  # noqa: BLE001
        _logger.warning("The Claw session service unavailable: %s", exc)

    if _is_new_session_command(user_text):
        if session_service is not None:
            try:
                session_service.clear_active_session(slack_user_id)
            except Exception as exc:  # noqa: BLE001
                _logger.warning("The Claw session clear failed: %s", exc)
        slack = get_slack_service()
        try:
            await slack.post_message(channel=channel, text=_NEW_SESSION_REPLY)
        finally:
            try:
                await slack.aclose()
            except Exception:  # noqa: BLE001
                pass
        return

    if session_service is not None:
        try:
            session = session_service.get_or_create_session(slack_user_id)
            history_messages = _history_from_session_context(getattr(session, "context", {}))
        except Exception as exc:  # noqa: BLE001
            _logger.warning("The Claw session retrieval failed: %s", exc)
            session = None
            history_messages = []

    selected_skill = await _select_skill_for_turn(
        user_text=user_text,
        history_messages=history_messages,
    )
    system_prompt = _build_system_prompt(selected_skill=selected_skill)

    slack = get_slack_service()
    try:
        try:
            response = await call_chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    *history_messages,
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

        if session_service is not None and session is not None:
            try:
                updated_history = _append_turn_and_cap_history(
                    history_messages,
                    user_text=user_text,
                    assistant_text=reply_text,
                )
                context_updates: dict[str, Any] = {_SESSION_HISTORY_KEY: updated_history}
                context_updates.update(
                    _extract_entity_resolver_context_updates(
                        selected_skill=selected_skill,
                        reply_text=reply_text,
                    )
                )
                session_service.update_context(
                    session.id,
                    context_updates,
                )
            except Exception as exc:  # noqa: BLE001
                _logger.warning("The Claw session update failed: %s", exc)

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
