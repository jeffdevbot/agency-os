"""C17D/C17E/C17F/C17G: Feature-flagged agent loop runtime helper.

C17D: reply-only turn handling
C17E: single read-only tool round-trip (`clickup_task_list`) per turn
C17F: mutation confirmation contract (`clickup_task_create`)
C17G: read-only context skills (`cc_client_lookup`, `cc_brand_list_all`,
`cc_brand_clickup_mapping_audit`)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Awaitable, Callable

from .agent_loop_context_assembler import assemble_prompt_context
from .agent_loop_store import AgentLoopStore
from .agent_loop_turn_logger import AgentLoopTurnLogger
from .openai_client import ChatCompletionResult, OpenAIError, call_chat_completion, parse_json_response
from .pending_confirmation import (
    build_pending_confirmation,
    validate_confirmation,
)

_LOGGER = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are AgencyClaw, an internal assistant for e-commerce operations. "
    "Reply conversationally and helpfully using available conversation context. "
    "For this runtime version, you may request at most one tool call "
    "using strict JSON only. Output either "
    '{"mode":"reply","text":"..."} or '
    '{"mode":"tool_call","skill_id":"clickup_task_list","args":{...}} or '
    '{"mode":"tool_call","skill_id":"cc_client_lookup","args":{...}} or '
    '{"mode":"tool_call","skill_id":"cc_brand_list_all","args":{...}} or '
    '{"mode":"tool_call","skill_id":"cc_brand_clickup_mapping_audit","args":{...}} or '
    '{"mode":"tool_call","skill_id":"lookup_client","args":{...}} or '
    '{"mode":"tool_call","skill_id":"lookup_brand","args":{...}} or '
    '{"mode":"tool_call","skill_id":"search_kb","args":{...}} or '
    '{"mode":"tool_call","skill_id":"resolve_brand","args":{...}} or '
    '{"mode":"tool_call","skill_id":"get_client_context","args":{...}} or '
    '{"mode":"tool_call","skill_id":"load_prior_skill_result","args":{...}} or '
    '{"mode":"tool_call","skill_id":"clickup_task_create","args":{...}}.'
)
_FAILURE_FALLBACK_TEXT = (
    "I hit an issue while processing that. Could you rephrase and try again?"
)
_PENDING_KEY = "pending_confirmation"
_READ_ONLY_SKILLS = {
    "clickup_task_list",
    "cc_client_lookup",
    "cc_brand_list_all",
    "cc_brand_clickup_mapping_audit",
    "lookup_client",
    "lookup_brand",
    "search_kb",
    "resolve_brand",
    "get_client_context",
    "load_prior_skill_result",
}
_REHYDRATION_KEY_PATTERN = re.compile(r"^ev:[^/\s]+(?:/[^/\s]+)?$")


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


def _validate_task_create_args(args: dict[str, Any]) -> dict[str, Any]:
    allowed = {"client_name", "task_title", "task_description", "brand_name"}
    for key in args:
        if key not in allowed:
            raise ValueError(f"unsupported arg: {key}")

    task_title = str(args.get("task_title") or "").strip()
    if not task_title:
        raise ValueError("task_title is required")

    normalized: dict[str, Any] = {"task_title": task_title}
    client_name = str(args.get("client_name") or "").strip()
    if client_name:
        normalized["client_name"] = client_name
    task_description = args.get("task_description")
    if task_description is not None:
        normalized["task_description"] = str(task_description)
    brand_name = str(args.get("brand_name") or "").strip()
    if brand_name:
        normalized["brand_name"] = brand_name
    return normalized


def _validate_read_skill_args(skill_id: str, args: dict[str, Any]) -> dict[str, Any]:
    if skill_id == "clickup_task_list":
        return _validate_task_list_args(args)
    if skill_id in {"cc_client_lookup", "lookup_client"}:
        if "query" not in args or args.get("query") is None:
            return {}
        return {"query": str(args.get("query") or "").strip()}
    if skill_id == "cc_brand_list_all":
        allowed = {"client_name"}
        for key in args:
            if key not in allowed:
                raise ValueError(f"unsupported arg: {key}")
        client_name = str(args.get("client_name") or "").strip()
        return {"client_name": client_name} if client_name else {}
    if skill_id == "lookup_brand":
        allowed = {"client_name", "brand_name"}
        for key in args:
            if key not in allowed:
                raise ValueError(f"unsupported arg: {key}")
        client_name = str(args.get("client_name") or "").strip()
        brand_name = str(args.get("brand_name") or "").strip()
        normalized: dict[str, Any] = {}
        if client_name:
            normalized["client_name"] = client_name
        if brand_name:
            normalized["brand_name"] = brand_name
        return normalized
    if skill_id == "cc_brand_clickup_mapping_audit":
        return {}
    if skill_id == "search_kb":
        allowed = {"query", "client_name", "brand_name"}
        for key in args:
            if key not in allowed:
                raise ValueError(f"unsupported arg: {key}")
        query = str(args.get("query") or "").strip()
        if not query:
            raise ValueError("query is required")
        normalized = {"query": query}
        client_name = str(args.get("client_name") or "").strip()
        brand_name = str(args.get("brand_name") or "").strip()
        if client_name:
            normalized["client_name"] = client_name
        if brand_name:
            normalized["brand_name"] = brand_name
        return normalized
    if skill_id == "resolve_brand":
        allowed = {"task_text", "client_name", "brand_hint"}
        for key in args:
            if key not in allowed:
                raise ValueError(f"unsupported arg: {key}")
        task_text = str(args.get("task_text") or "").strip()
        if not task_text:
            raise ValueError("task_text is required")
        normalized = {"task_text": task_text}
        client_name = str(args.get("client_name") or "").strip()
        brand_hint = str(args.get("brand_hint") or "").strip()
        if client_name:
            normalized["client_name"] = client_name
        if brand_hint:
            normalized["brand_hint"] = brand_hint
        return normalized
    if skill_id == "get_client_context":
        allowed = {"client_name"}
        for key in args:
            if key not in allowed:
                raise ValueError(f"unsupported arg: {key}")
        client_name = str(args.get("client_name") or "").strip()
        if not client_name:
            raise ValueError("client_name is required")
        return {"client_name": client_name}
    if skill_id == "load_prior_skill_result":
        allowed = {"key"}
        for key in args:
            if key not in allowed:
                raise ValueError(f"unsupported arg: {key}")
        evidence_key = str(args.get("key") or "").strip()
        if not evidence_key:
            raise ValueError("key is required")
        if not _REHYDRATION_KEY_PATTERN.match(evidence_key):
            raise ValueError("invalid evidence key format")
        return {"key": evidence_key}
    raise ValueError(f"disallowed read skill: {skill_id}")


async def run_reply_only_agent_loop_turn(
    *,
    text: str,
    session: Any,
    slack_user_id: str,
    session_service: Any,
    channel: str,
    slack: Any,
    supabase_client: Any,
    execute_read_skill_fn: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    execute_task_list_fn: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    execute_create_task_fn: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    check_mutation_policy_fn: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    call_chat_completion_fn: Callable[..., Awaitable[ChatCompletionResult]] = call_chat_completion,
    logger: logging.Logger = _LOGGER,
) -> bool:
    """Run a C17D/C17E/C17F/C17G turn with run/message/event logging.

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

        pending = session.context.get(_PENDING_KEY)
        decision = {"state": "ignore", "reason": "no_pending_confirmation"}
        if isinstance(pending, dict):
            decision = validate_confirmation(
                pending,
                slack_user_id=slack_user_id,
                text=text,
                lane_key=slack_user_id,
            )
        if decision["state"] in {"expired", "cancel", "wrong_actor", "invalid", "confirm"}:
            if decision["state"] in {"expired", "cancel", "invalid"}:
                await asyncio.to_thread(session_service.update_context, session.id, {_PENDING_KEY: None})
            if decision["state"] == "cancel":
                assistant_text = "Cancelled. I won't create that task."
            elif decision["state"] == "expired":
                assistant_text = "That confirmation expired. Please ask me to create it again."
            elif decision["state"] == "invalid":
                assistant_text = "I couldn't validate that confirmation payload. Please create the request again."
            elif decision["state"] == "wrong_actor":
                assistant_text = "Only the original requester can confirm or cancel this proposal."
            else:
                if not isinstance(pending, dict):
                    raise ValueError("missing pending payload")
                skill_id = str(pending.get("skill_id") or "")
                args = pending.get("args")
                if skill_id != "clickup_task_create" or not isinstance(args, dict):
                    raise ValueError("invalid pending confirmation payload")
                if execute_create_task_fn is None:
                    raise ValueError("create-task executor not provided")
                if check_mutation_policy_fn is None:
                    raise ValueError("mutation policy checker not provided")
                policy = await check_mutation_policy_fn(
                    slack_user_id=slack_user_id,
                    session=session,
                    channel=channel,
                    skill_id="clickup_task_create",
                    args=args,
                )
                if not policy.get("allowed"):
                    assistant_text = str(policy.get("user_message") or "That action is not allowed.")
                    await slack.post_message(channel=channel, text=assistant_text)
                    await asyncio.to_thread(turn_logger.log_assistant_message, run_id, assistant_text)
                    await asyncio.to_thread(turn_logger.complete_run, run_id, "completed")
                    return True
                await asyncio.to_thread(turn_logger.log_skill_call, run_id, skill_id, args)
                result = await execute_create_task_fn(
                    slack_user_id=slack_user_id,
                    channel=channel,
                    args=args,
                    session=session,
                    session_service=session_service,
                )
                if not isinstance(result, dict):
                    raise ValueError("create-task result must be dict")
                await asyncio.to_thread(session_service.update_context, session.id, {_PENDING_KEY: None})
                await asyncio.to_thread(turn_logger.log_skill_result, run_id, skill_id, result)
                assistant_text = str(result.get("response_text") or "Task request processed.")

            await slack.post_message(channel=channel, text=assistant_text)
            await asyncio.to_thread(turn_logger.log_assistant_message, run_id, assistant_text)
            await asyncio.to_thread(turn_logger.complete_run, run_id, "completed")
            return True

        session_rows = _build_session_rows(session)
        run_rows = await asyncio.to_thread(store.list_recent_run_messages, run_id, 20)
        if hasattr(store, "list_recent_skill_events"):
            run_skill_events = await asyncio.to_thread(store.list_recent_skill_events, run_id, 12)
        else:
            run_skill_events = []
        assembled = assemble_prompt_context(
            messages=[*session_rows, *run_rows],
            skill_events=run_skill_events,
            budget_chars=4000,
        )

        prompt_messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
        prompt_messages.extend(assembled["messages_for_llm"])
        if assembled["evidence_notes"]:
            evidence_text = "\n".join(assembled["evidence_notes"][-8:])
            if len(evidence_text) > 1200:
                evidence_text = evidence_text[:1197] + "..."
            prompt_messages.append(
                {
                    "role": "system",
                    "content": "Recent skill evidence:\n" + evidence_text,
                }
            )
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
            if skill_id in _READ_ONLY_SKILLS:
                args = _validate_read_skill_args(skill_id, first_payload.get("args") or {})
                await asyncio.to_thread(turn_logger.log_skill_call, run_id, skill_id, args)
                if execute_read_skill_fn is not None:
                    tool_result = await execute_read_skill_fn(
                        skill_id=skill_id,
                        slack_user_id=slack_user_id,
                        channel=channel,
                        args=args,
                        session=session,
                        session_service=session_service,
                    )
                elif skill_id == "clickup_task_list":
                    if execute_task_list_fn is None:
                        raise ValueError("read-skill executor not provided")
                    tool_result = await execute_task_list_fn(
                        slack_user_id=slack_user_id,
                        channel=channel,
                        args=args,
                        session=session,
                        session_service=session_service,
                    )
                else:
                    raise ValueError("read-skill executor not provided")
                if not isinstance(tool_result, dict):
                    raise ValueError("tool result must be dict")
                await asyncio.to_thread(turn_logger.log_skill_result, run_id, skill_id, tool_result)

                tool_context = json.dumps(tool_result, ensure_ascii=True, separators=(",", ":"))
                second_prompt = list(prompt_messages)
                second_prompt.append(
                    {
                        "role": "system",
                        "content": (
                            f"Tool result for {skill_id} (JSON): " + tool_context
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
            elif skill_id == "clickup_task_create":
                args = _validate_task_create_args(first_payload.get("args") or {})
                if check_mutation_policy_fn is None:
                    raise ValueError("mutation policy checker not provided")
                policy = await check_mutation_policy_fn(
                    slack_user_id=slack_user_id,
                    session=session,
                    channel=channel,
                    skill_id="clickup_task_create",
                    args=args,
                )
                if not policy.get("allowed"):
                    assistant_text = str(policy.get("user_message") or "That action is not allowed.")
                else:
                    proposal = build_pending_confirmation(
                        action_type="mutation",
                        skill_id="clickup_task_create",
                        args=args,
                        requested_by=slack_user_id,
                        lane_key=slack_user_id,
                    )
                    await asyncio.to_thread(
                        session_service.update_context,
                        session.id,
                        {_PENDING_KEY: proposal},
                    )
                    title = str(args.get("task_title") or "this task")
                    assistant_text = (
                        f"Ready to create task *{title}*. "
                        "Reply `confirm` to proceed or `cancel` to discard."
                    )
            else:
                raise ValueError(f"disallowed skill in C17E/C17F/C17G: {skill_id}")
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
