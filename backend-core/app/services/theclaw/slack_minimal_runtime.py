"""Minimal Phase-1 Slack runtime for The Claw reboot."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from .context_providers import fetch_context_blobs, render_context_blobs_for_prompt
from .pending_confirmation_runtime import (
    build_pending_confirmation_reply as _build_pending_confirmation_reply,
    enrich_pending_destination_if_present as _enrich_pending_destination_if_present,
)
from ..playbook_session import get_playbook_session_service
from ..slack import get_slack_service
from .openai_client import OpenAIConfigurationError, OpenAIError, call_chat_completion
from .runtime_state import (
    extract_reply_and_context_updates as _extract_reply_and_context_updates,
    finalize_reply_text as _finalize_reply_text_base,
    finalize_state_updates_for_turn as _finalize_state_updates_for_turn,
    pending_confirmation_from_session_context as _pending_confirmation_from_session_context,
)
from .skill_registry import TheClawSkill, build_available_skills_xml, get_skill_by_id, load_skills

_logger = logging.getLogger(__name__)

_FALLBACK_REPLY = "I ran into a temporary issue generating a reply. Please retry."
_NEW_SESSION_REPLY = "Started a new session. I cleared prior conversation context."
_NEW_SESSION_RE = re.compile(r"^\s*new session\s*$", re.IGNORECASE)
_SESSION_HISTORY_KEY = "theclaw_history_v1"
_MAX_HISTORY_TURNS = 25
_SKILL_SELECTION_PROMPT = (
    "You are the The Claw skill router. Select at most one skill for this user turn. "
    "Use intent and context, not keyword matching. If no skill is needed, choose 'none'. "
    "Return strict JSON only with this schema: "
    '{"skill_id":"<skill id or none>","confidence":<0.0-1.0>,"reason":"<brief reason>"}. '
    "Do not include markdown, prose, or code fences."
)
_REPLY_MAX_TOKENS = 1600
_MAX_TOOL_TURNS = 6
_TOOL_BUDGET_EXHAUSTED_REPLY = (
    "I hit a processing limit while working through that. Please retry with a narrower request."
)


def _build_system_prompt(
    *,
    selected_skill: TheClawSkill | None = None,
    context_blobs: dict[str, Any] | None = None,
    required_context_keys: set[str] | None = None,
) -> str:
    prompt = (
        "You are The Claw, an agency operations copilot for Amazon-focused client work. "
        "Keep answers concise, clear, and action-oriented, and avoid generic marketing fluff. "
        "You can look up data, advise, and draft text. "
        "You cannot create tasks, send messages, update ClickUp, or perform any action in an external system. "
        "Never claim you performed an action you did not perform. "
        "If asked to execute an action, state that you cannot execute system actions yet and provide the best draft instead. "
        "For task drafting, if key fields are missing (client/brand, owner, due date, priority), ask up to 2 clarifying questions before finalizing the draft. "
        "When using lists, use plain numbered format like '1.' and do not use bold-number bullets."
    )
    if selected_skill is not None:
        prompt = (
            f"{prompt} You are executing skill '{selected_skill.name}' "
            f"(id: {selected_skill.skill_id}). Follow this skill contract exactly: "
            f"{selected_skill.system_prompt}"
        )

    context_prompt = render_context_blobs_for_prompt(
        context_blobs=context_blobs or {},
        required_context_keys=required_context_keys or set(),
    )
    if context_prompt:
        prompt = f"{prompt} {context_prompt}"
    return prompt


def _build_skill_selection_system_prompt(*, available_skills_xml: str) -> str:
    return f"{_SKILL_SELECTION_PROMPT}\n\n{available_skills_xml}"


def _get_session_service():
    return get_playbook_session_service()


def _is_new_session_command(text: str) -> bool:
    return bool(_NEW_SESSION_RE.match(text or ""))


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


def _finalize_reply_text(reply_text: str) -> str:
    return _finalize_reply_text_base(reply_text, fallback_text=_FALLBACK_REPLY)


def _build_context_updates_for_turn(
    *,
    history_messages: list[dict[str, str]],
    user_text: str,
    assistant_text: str,
    state_updates: dict[str, Any],
) -> dict[str, Any]:
    updated_history = _append_turn_and_cap_history(
        history_messages,
        user_text=user_text,
        assistant_text=assistant_text,
    )
    context_updates: dict[str, Any] = {_SESSION_HISTORY_KEY: updated_history}
    context_updates.update(state_updates)
    return context_updates


async def _persist_and_post_reply(
    *,
    slack,
    channel: str,
    session_service,
    session,
    history_messages: list[dict[str, str]],
    user_text: str,
    reply_text: str,
    state_updates: dict[str, Any],
) -> None:
    if session_service is not None and session is not None:
        try:
            context_updates = _build_context_updates_for_turn(
                history_messages=history_messages,
                user_text=user_text,
                assistant_text=reply_text,
                state_updates=state_updates,
            )
            session_service.update_context(
                session.id,
                context_updates,
            )
        except Exception as exc:  # noqa: BLE001
            _logger.warning("The Claw session update failed: %s", exc)

    await slack.post_message(channel=channel, text=reply_text)


def _process_model_reply_for_turn(*, user_text: str, model_reply_text: str) -> tuple[str, dict[str, Any]]:
    visible_reply, state_updates = _extract_reply_and_context_updates(model_reply_text)
    finalized_reply = _finalize_reply_text(visible_reply)
    return finalized_reply, state_updates


def _build_execution_grounding_note(round_tools: list[tuple[str, str]]) -> str:
    """Build a grounding note based on the actual outcomes of tools in this round.

    Each entry is ``(tool_name, outcome)`` where *outcome* is one of the
    ``ToolOutcome`` literals from ``skill_tools``.  Returns an empty string
    when no tools ran (caller should not inject a message in that case).
    """
    if not round_tools:
        return ""

    outcomes = {outcome for _, outcome in round_tools}

    if "mutation_executed" in outcomes:
        return (
            "Some of the tools above modified external systems. "
            "Report what happened accurately based on the tool outputs."
        )

    if "mutation_not_executed" in outcomes:
        return (
            "A mutation was attempted but did not execute. "
            "Do not claim the action was performed. "
            "Report the error or reason from the tool output."
        )

    if "tool_error" in outcomes:
        if "read_only_success" in outcomes or "read_only_miss" in outcomes:
            prefix = "Some tools retrieved data or executed normally but others encountered errors."
        else:
            prefix = "The tool(s) encountered errors."
        return (
            f"{prefix} "
            "No external systems were modified. "
            "Do not claim to have performed any external action."
        )

    if "read_only_miss" in outcomes:
        if "read_only_success" in outcomes:
            prefix = "Some tools retrieved data but others found no matching profile or data."
        else:
            prefix = "The tool(s) executed but found no matching profile or data."
        return (
            f"{prefix} "
            "No external systems were modified. "
            "Do not claim the requested data was successfully retrieved."
        )

    # All read_only_success
    return (
        "The tools you called only retrieved data. "
        "No external systems were modified. "
        "Do not claim to have performed any external action."
    )


def _parse_skill_selection(raw_text: str) -> tuple[str | None, float, str]:
    """Parse skill-selection JSON.  response_format=json_object guarantees clean JSON."""
    text = (raw_text or "").strip()
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None, 0.0, ""

    if not isinstance(payload, dict):
        return None, 0.0, ""

    skill_id_value = str(payload.get("skill_id") or "").strip().lower()
    confidence_raw = payload.get("confidence", 0)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.0

    reason = str(payload.get("reason") or "").strip()
    if skill_id_value in {"", "none", "null"}:
        return None, max(0.0, min(1.0, confidence)), reason
    return skill_id_value, max(0.0, min(1.0, confidence)), reason


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
            response_format={"type": "json_object"},
        )
    except OpenAIError as exc:
        _logger.warning("The Claw skill selection failed, falling back to no skill: %s", exc)
        return None

    selected_skill_id, confidence, reason = _parse_skill_selection(selection_response["content"])
    if not selected_skill_id:
        _logger.info(f"The Claw skill selection decided no skill is needed | confidence={confidence} reason='{reason}'")
        return None

    selected_skill = get_skill_by_id(selected_skill_id)
    if selected_skill is None:
        _logger.warning(f"The Claw selected unknown skill id '{selected_skill_id}' | confidence={confidence} reason='{reason}'")
        return None

    if confidence < 0.45:
        _logger.info(f"The Claw skill selection confidence too low; skipping skill | skill_id={selected_skill_id} confidence={confidence} reason='{reason}'")
        return None

    _logger.info(f"The Claw selected skill | skill_id={selected_skill_id} confidence={confidence} reason='{reason}'")
    return selected_skill


async def run_theclaw_minimal_dm_turn(*, slack_user_id: str, channel: str, text: str) -> None:
    user_text = (text or "").strip()
    if not user_text:
        return

    _logger.info(f"The Claw minimal turn started | slack_user_id={slack_user_id} channel={channel} text_len={len(user_text)}")

    session = None
    session_context: dict[str, Any] = {}
    history_messages: list[dict[str, str]] = []
    context_blobs: dict[str, Any] = {}
    pending_confirmation: dict[str, Any] | None = None
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
            existing_session = session_service.get_active_session(slack_user_id)
            if existing_session:
                session = session_service.ensure_session_profile_link(existing_session)
                _logger.info(f"The Claw found active session | session_id={session.id}")
            else:
                profile_id = session_service.get_profile_id_by_slack_user_id(slack_user_id)
                session = session_service.create_session(slack_user_id=slack_user_id, profile_id=profile_id)
                _logger.info(f"The Claw created new session | session_id={session.id}")

            session_context = getattr(session, "context", {})
            history_messages = _history_from_session_context(session_context)
            pending_confirmation = _pending_confirmation_from_session_context(session_context)
        except Exception as exc:  # noqa: BLE001
            _logger.warning("The Claw session retrieval/creation failed: %s", exc)
            session = None
            session_context = {}
            history_messages = []
            pending_confirmation = None
            _logger.info("The Claw active session not found or unavailable")

    if pending_confirmation is not None:
        reply_text, state_updates = await _build_pending_confirmation_reply(
            user_text=user_text,
            pending_confirmation=pending_confirmation,
            session_context=session_context,
            fallback_reply=_FALLBACK_REPLY,
        )

        slack = get_slack_service()
        try:
            await _persist_and_post_reply(
                slack=slack,
                channel=channel,
                session_service=session_service,
                session=session,
                history_messages=history_messages,
                user_text=user_text,
                reply_text=reply_text,
                state_updates=state_updates,
            )
        except Exception as exc:  # noqa: BLE001
            _logger.warning(
                "The Claw minimal runtime failed to post pending confirmation reply (user=%s, channel=%s): %s",
                slack_user_id,
                channel,
                exc,
            )
        finally:
            try:
                await slack.aclose()
            except Exception:  # noqa: BLE001
                pass
        return

    selected_skill = await _select_skill_for_turn(
        user_text=user_text,
        history_messages=history_messages,
    )
    required_context_keys = set(selected_skill.needs_context) if selected_skill is not None else set()
    context_blobs = await fetch_context_blobs(
        required_context_keys=required_context_keys,
        session_context=session_context,
    )

    system_prompt = _build_system_prompt(
        selected_skill=selected_skill,
        context_blobs=context_blobs,
        required_context_keys=required_context_keys,
    )

    # Resolve tools for the selected skill (if any).
    skill_tool_defs: list[dict[str, Any]] | None = None
    if selected_skill is not None:
        from .skill_tools import get_skill_tool_definitions

        skill_tool_defs = get_skill_tool_definitions(selected_skill.skill_id)

    slack = get_slack_service()
    try:
        try:
            llm_messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                *history_messages,
                {"role": "user", "content": user_text},
            ]

            # No-tools-available grounding: if the LLM has no tools for
            # this turn, ground it in that fact before it generates.
            if not skill_tool_defs:
                llm_messages.append({
                    "role": "system",
                    "content": (
                        "No action tools are available for this turn. "
                        "Do not claim to have performed any external action."
                    ),
                })

            # Bounded multi-step tool-use loop.
            # The LLM can call tools, see results, and call more tools
            # until it produces a final text reply or the budget runs out.
            tool_budget_exhausted = False
            total_tool_calls_this_turn = 0
            total_tool_rounds_this_turn = 0
            
            for _tool_turn in range(_MAX_TOOL_TURNS):
                response = await call_chat_completion(
                    messages=llm_messages,
                    temperature=0.2,
                    max_tokens=_REPLY_MAX_TOKENS,
                    tools=skill_tool_defs,
                )

                if not response.get("tool_calls"):
                    break

                # Model wants to call tools — execute and loop.
                from .skill_tools import execute_skill_tool_call

                total_tool_rounds_this_turn += 1
                total_tool_calls_this_turn += len(response["tool_calls"])

                llm_messages.append({
                    "role": "assistant",
                    "content": response.get("content") or None,
                    "tool_calls": response["tool_calls"],
                })
                round_tools: list[tuple[str, str]] = []
                for tc in response["tool_calls"]:
                    func = tc.get("function") or {}
                    tool_name = func.get("name", "")
                    tool_result = await execute_skill_tool_call(
                        skill_id=selected_skill.skill_id,
                        tool_name=tool_name,
                        arguments_json=func.get("arguments", "{}"),
                    )
                    llm_messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": tool_result["content"],
                    })
                    round_tools.append((tool_name, tool_result["outcome"]))

                # Execution-state grounding: tell the LLM what actually
                # happened based on the outcomes of the tools that ran.
                grounding = _build_execution_grounding_note(round_tools)
                if grounding:
                    llm_messages.append({
                        "role": "system",
                        "content": grounding,
                    })
            else:
                # Loop completed without break — budget exhausted.
                tool_budget_exhausted = True

            if tool_budget_exhausted:
                reply_text = _TOOL_BUDGET_EXHAUSTED_REPLY
                state_updates: dict[str, Any] = {}
            else:
                reply_text, state_updates = _process_model_reply_for_turn(
                    user_text=user_text,
                    model_reply_text=response["content"],
                )
                state_updates = _finalize_state_updates_for_turn(
                    state_updates=state_updates,
                    session_context=session_context,
                )
                state_updates = await _enrich_pending_destination_if_present(
                    state_updates=state_updates,
                    session_context=session_context,
                )

            _logger.info(
                f"The Claw turn completion | "
                f"answered_directly={total_tool_rounds_this_turn == 0} "
                f"tool_rounds={total_tool_rounds_this_turn} "
                f"tool_calls={total_tool_calls_this_turn} "
                f"budget_exhausted={tool_budget_exhausted} "
                f"reply_length={len(reply_text)} "
                f"session_updated={bool(state_updates)}"
            )
        except OpenAIConfigurationError:
            reply_text = "The Claw is not configured yet. Please set OPENAI_API_KEY and try again."
            state_updates = {}
        except OpenAIError as exc:
            _logger.warning("The Claw minimal runtime OpenAI error: %s", exc)
            reply_text = _FALLBACK_REPLY
            state_updates = {}

        await _persist_and_post_reply(
            slack=slack,
            channel=channel,
            session_service=session_service,
            session=session,
            history_messages=history_messages,
            user_text=user_text,
            reply_text=reply_text,
            state_updates=state_updates,
        )
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
