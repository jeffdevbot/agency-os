"""C17D/C17E/C17F/C17G/C17H: Feature-flagged agent loop runtime helper.

C17D: reply-only turn handling
C17E: single read-only tool round-trip (`clickup_task_list`) per turn
C17F: mutation confirmation contract (`clickup_task_create`)
C17G: read-only context skills (`cc_client_lookup`, `cc_brand_list_all`,
`cc_brand_clickup_mapping_audit`)
C17H: planner sub-agent delegation (`delegate_planner`) with parent/child
run linkage
"""

from __future__ import annotations

import asyncio
import hashlib
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
    "For this runtime version, use strict JSON only. "
    "Each response may either request one tool call or provide a final reply. "
    "Output either "
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
    '{"mode":"tool_call","skill_id":"delegate_planner","args":{"request_text":"..."}} or '
    '{"mode":"tool_call","skill_id":"clickup_task_create","args":{...}}.'
)
_FAILURE_FALLBACK_TEXT = (
    "I hit an issue while processing that. Could you rephrase and try again?"
)
_PENDING_KEY = "pending_confirmation"
_READ_ONLY_SKILLS = {
    "clickup_task_list",
    "clickup_task_list_weekly",
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
_MUTATION_SKILLS = {
    "clickup_task_create",
    "cc_assignment_upsert",
    "cc_assignment_remove",
    "cc_brand_create",
    "cc_brand_update",
    "cc_brand_mapping_remediation_apply",
}
_REHYDRATION_KEY_PATTERN = re.compile(r"^ev:[^/\s]+(?:/[^/\s]+)?$")
_MAX_LOOP_TURNS = 6
_SKILL_ID_ALIASES = {
    "task_list": "clickup_task_list",
    "weekly_tasks": "clickup_task_list_weekly",
    "list_tasks": "clickup_task_list",
    "task_priority": "clickup_task_list",
    "task_priorities": "clickup_task_list",
    "task_due_list": "clickup_task_list",
    "client_lookup": "cc_client_lookup",
    "list_clients": "cc_client_lookup",
    "brand_list": "cc_brand_list_all",
    "list_brands": "cc_brand_list_all",
    "get_brands": "cc_brand_list_all",
    "brand_lookup": "lookup_brand",
    "brand_mapping_audit": "cc_brand_clickup_mapping_audit",
}
_CLIENT_HINT_PATTERN = re.compile(r"\bfor\s+([^,\n\.]+)", re.IGNORECASE)
_TOP_N_PATTERN = re.compile(r"\btop\s+(\d+)\b", re.IGNORECASE)
_TASK_LINK_TITLE_PATTERN = re.compile(r"\|([^>]+)>")


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
    if mode == "delegate_planner":
        return {
            "mode": "tool_call",
            "skill_id": "delegate_planner",
            "args": payload.get("args") if isinstance(payload.get("args"), dict) else {},
        }

    text = payload.get("text")
    if isinstance(text, str) and text.strip():
        return {"mode": "reply", "text": text.strip()}
    return {"mode": "reply", "text": content.strip() or "How can I help?"}


def _canonical_skill_id(skill_id: str) -> str:
    normalized = (skill_id or "").strip()
    return _SKILL_ID_ALIASES.get(normalized, normalized)


def _clean_assistant_text(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return "How can I help?"

    # Sometimes the model returns malformed JSON-looking text for replies.
    # Best effort unwrap avoids exposing raw control JSON to end users.
    if cleaned.startswith("{") and "\"mode\"" in cleaned and "\"text\"" in cleaned:
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                mode = str(parsed.get("mode") or "").strip()
                txt = parsed.get("text")
                if mode == "reply" and isinstance(txt, str) and txt.strip():
                    return txt.strip()
        except Exception:
            pass

        text_match = re.search(r'"text"\s*:\s*"([\s\S]*)$', cleaned)
        if text_match:
            candidate = text_match.group(1).strip()
            candidate = candidate.rstrip("}").rstrip('"').strip()
            candidate = candidate.replace('\\"', '"').replace("\\n", "\n")
            if candidate:
                return candidate

    return cleaned


def _error_code(exc: Exception) -> str:
    raw = f"{type(exc).__name__}:{exc}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]


def _extract_client_hint_from_text(text: str) -> str:
    match = _CLIENT_HINT_PATTERN.search(text or "")
    if not match:
        return ""
    hint = (match.group(1) or "").strip()
    normalized = re.sub(r"\s+", " ", hint).strip(" .,:;")
    normalized = re.sub(r"^(client|brand)\s+", "", normalized, flags=re.IGNORECASE)
    return normalized.strip(" .,:;")


def _looks_like_task_list_request(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    if any(phrase in lowered for phrase in ("create task", "new task", "make task", "draft task")):
        return False
    if "task" not in lowered:
        return False
    return any(
        phrase in lowered
        for phrase in (
            "top ",
            "due ",
            "this week",
            "this month",
            "priority",
            "prioritize",
            "open tasks",
            "what should i prioritize",
            "list tasks",
        )
    )


def _looks_like_brand_list_request(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    if "brand" not in lowered:
        return False
    return any(
        phrase in lowered
        for phrase in (
            "show",
            "list",
            "what brands",
            "which brands",
            "brands for",
        )
    )


def _infer_window_from_text(text: str) -> str:
    lowered = (text or "").strip().lower()
    if "this week" in lowered or "weekly" in lowered:
        return "this_week"
    if "this month" in lowered or "monthly" in lowered:
        return "this_month"
    return ""


def _response_text_from_tool_result(tool_result: dict[str, Any]) -> str:
    raw = tool_result.get("response_text")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return json.dumps(tool_result, ensure_ascii=True, separators=(",", ":"))


def _is_generic_failure_reply(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    return any(
        phrase in lowered
        for phrase in (
            "could you rephrase and try again",
            "couldn't complete that flow",
            "i hit an issue while processing",
        )
    )


def _is_non_answer_action_promise(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    return any(
        phrase in lowered
        for phrase in (
            "let me ",
            "i'll proceed",
            "i will proceed",
            "i'll check",
            "i will check",
            "i'll find",
            "i will find",
        )
    )


def _requested_top_n(text: str) -> int | None:
    match = _TOP_N_PATTERN.search(text or "")
    if not match:
        return None
    try:
        value = int(match.group(1))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _task_bullet_indices(lines: list[str]) -> list[int]:
    return [idx for idx, line in enumerate(lines) if line.strip().startswith("• ")]


def _extract_task_title_from_bullet(line: str) -> str:
    match = _TASK_LINK_TITLE_PATTERN.search(line)
    if match:
        return (match.group(1) or "").strip()
    return line.replace("•", "").strip()


def _postprocess_task_list_answer(user_text: str, assistant_text: str) -> str:
    if not _looks_like_task_list_request(user_text):
        return assistant_text
    if "*Tasks" not in assistant_text:
        return assistant_text

    lines = assistant_text.splitlines()
    bullet_idxs = _task_bullet_indices(lines)
    if not bullet_idxs:
        return assistant_text

    top_n = _requested_top_n(user_text)
    if top_n is not None and len(bullet_idxs) > top_n:
        keep = set(bullet_idxs[:top_n])
        lines = [line for idx, line in enumerate(lines) if idx not in bullet_idxs or idx in keep]
        bullet_idxs = _task_bullet_indices(lines)

    lowered_user = (user_text or "").lower()
    lowered_answer = (assistant_text or "").lower()
    wants_priority = "priorit" in lowered_user
    has_priority_already = "priority first" in lowered_answer or "priority suggestion" in lowered_answer
    if wants_priority and not has_priority_already and bullet_idxs:
        chosen_idx = bullet_idxs[0]
        for idx in bullet_idxs:
            line_lower = lines[idx].lower()
            if "[review]" in line_lower:
                chosen_idx = idx
                break
        chosen_title = _extract_task_title_from_bullet(lines[chosen_idx])
        lines.append("")
        lines.append(
            f"Priority first: {chosen_title} — start with this because it appears closest to completion."
        )

    return "\n".join(lines).strip()


def _looks_like_sop_draft_request(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    has_sop = "sop" in lowered or "procedure" in lowered
    has_draft = "draft" in lowered
    wants_title = "task title" in lowered
    wants_description = "description" in lowered
    return has_sop and has_draft and wants_title and wants_description


def _has_concrete_task_draft(text: str) -> bool:
    lowered = (text or "").strip().lower()
    return "task title:" in lowered and "task description:" in lowered


def _infer_brand_hint(text: str) -> str:
    hint = _extract_client_hint_from_text(text)
    if hint:
        return hint
    lowered = text or ""
    match = re.search(r"\bfor\s+([A-Za-z0-9][A-Za-z0-9 _-]{1,60})", lowered)
    if not match:
        return ""
    candidate = (match.group(1) or "").strip(" .,:;")
    candidate = re.sub(r"^(client|brand)\s+", "", candidate, flags=re.IGNORECASE)
    return candidate


def _ensure_sop_draft_payload(user_text: str, assistant_text: str) -> str:
    if not _looks_like_sop_draft_request(user_text):
        return assistant_text
    if _has_concrete_task_draft(assistant_text):
        return assistant_text

    brand = _infer_brand_hint(user_text) or "Target Brand"
    title = f"Launch Amazon Coupon for {brand}"
    draft = (
        "\n\nTask Title: "
        + title
        + "\n"
        + "Task Description:\n"
        + "- Objective: Execute the coupon launch SOP for this brand on Amazon.\n"
        + "- SOP Basis: Use the standard coupon workflow (settings, timing, targeting, budget).\n"
        + "- Deliverables: Coupon created, validation checks completed, and launch details documented.\n"
        + "- Open Inputs: Confirm discount amount, ASIN scope, and campaign dates before launch."
    )
    return assistant_text.rstrip() + draft


def _validate_task_list_args(args: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    client_name = args.get("client_name")
    if client_name is None:
        client_name = args.get("client")
    if client_name is None:
        client_name = args.get("client_hint")
    if client_name is not None:
        normalized["client_name"] = str(client_name)
    raw_window = args.get("window")
    if raw_window is None:
        raw_window = args.get("timeframe")
    if raw_window is None:
        raw_window = args.get("period")
    if raw_window is not None:
        window = str(raw_window).strip().lower().replace("-", "_").replace(" ", "_")
        if window in {"week", "weekly"}:
            window = "this_week"
        elif window in {"month", "monthly"}:
            window = "this_month"
        elif window in {"thisweek"}:
            window = "this_week"
        elif window in {"thismonth"}:
            window = "this_month"
        normalized["window"] = window
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
    if skill_id in {"clickup_task_list", "clickup_task_list_weekly"}:
        return _validate_task_list_args(args)
    if skill_id == "cc_client_lookup":
        if "query" not in args or args.get("query") is None:
            return {}
        return {"query": str(args.get("query") or "").strip()}
    if skill_id == "lookup_client":
        allowed = {"query"}
        for key in args:
            if key not in allowed:
                raise ValueError(f"unsupported arg: {key}")
        if "query" not in args or args.get("query") is None:
            return {}
        return {"query": str(args.get("query") or "").strip()}
    if skill_id == "cc_brand_list_all":
        # Tolerate common arg-shape drift for client filter.
        # Be tolerant to model arg-shape drift: map query -> client_name.
        client_name = str(
            args.get("client_name")
            or args.get("query")
            or args.get("client")
            or args.get("client_hint")
            or ""
        ).strip()
        return {"client_name": client_name} if client_name else {}
    if skill_id == "lookup_brand":
        client_name = str(args.get("client_name") or args.get("client") or "").strip()
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


def _validate_delegate_planner_args(args: dict[str, Any]) -> dict[str, Any]:
    allowed = {"request_text"}
    for key in args:
        if key not in allowed:
            raise ValueError(f"unsupported arg: {key}")
    request_text = str(args.get("request_text") or "").strip()
    return {"request_text": request_text} if request_text else {}


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
    execute_delegate_planner_fn: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    execute_task_list_fn: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    execute_create_task_fn: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    check_mutation_policy_fn: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    call_chat_completion_fn: Callable[..., Awaitable[ChatCompletionResult]] = call_chat_completion,
    logger: logging.Logger = _LOGGER,
) -> bool:
    """Run a C17D/C17E/C17F/C17G/C17H turn with run/message/event logging.

    Returns True when the turn was handled (including fallback paths).
    """
    store = AgentLoopStore(supabase_client)
    turn_logger = AgentLoopTurnLogger(store)
    run_id: str | None = None
    planner_child_run_id: str | None = None
    planner_child_done = False

    async def _safe_log_call(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if not run_id:
            return None
        try:
            return await asyncio.to_thread(fn, *args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Agent loop logging call failed: %s", exc, exc_info=True)
            return None

    async def _safe_log_method(method_name: str, *args: Any) -> Any:
        method = getattr(turn_logger, method_name, None)
        if not callable(method):
            return None
        return await _safe_log_call(method, *args)

    try:
        run: dict[str, Any] = {}
        try:
            run = await asyncio.to_thread(turn_logger.start_main_run, str(session.id))
            run_id = str(run.get("id") or "").strip() or None
            if not run_id:
                logger.warning("Agent loop run start returned empty run_id; continuing without run logging")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Agent loop run logging init failed; continuing without run logging: %s", exc, exc_info=True)
            run_id = None

        await _safe_log_call(turn_logger.log_user_message, run_id, text)

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
                    await _safe_log_method("log_assistant_message", run_id, assistant_text)
                    await _safe_log_method("complete_run", run_id, "completed")
                    return True
                await _safe_log_call(turn_logger.log_skill_call, run_id, skill_id, args)
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
                await _safe_log_call(turn_logger.log_skill_result, run_id, skill_id, result)
                assistant_text = str(result.get("response_text") or "Task request processed.")

            await slack.post_message(channel=channel, text=assistant_text)
            await _safe_log_method("log_assistant_message", run_id, assistant_text)
            await _safe_log_method("complete_run", run_id, "completed")
            return True

        session_rows = _build_session_rows(session)
        run_rows = await asyncio.to_thread(store.list_recent_run_messages, run_id, 20) if run_id else []
        if run_id and hasattr(store, "list_recent_skill_events"):
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

        loop_messages = list(prompt_messages)
        assistant_text: str | None = None
        last_tool_error: str | None = None
        executed_skill_count = 0

        async def _execute_read_skill(
            skill_id: str,
            args: dict[str, Any],
        ) -> dict[str, Any]:
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
            return tool_result

        async def _recover_from_natural_read_request() -> str | None:
            nonlocal executed_skill_count
            inferred_skill_id = ""
            inferred_args: dict[str, Any] = {}
            client_hint = _extract_client_hint_from_text(text)

            if _looks_like_task_list_request(text):
                inferred_skill_id = "clickup_task_list"
                if client_hint:
                    inferred_args["client_name"] = client_hint
                window = _infer_window_from_text(text)
                if window:
                    inferred_args["window"] = window
            elif _looks_like_brand_list_request(text):
                inferred_skill_id = "cc_brand_list_all"
                if client_hint:
                    inferred_args["client_name"] = client_hint

            if not inferred_skill_id:
                return None

            normalized_args = _validate_read_skill_args(inferred_skill_id, inferred_args)
            await _safe_log_call(turn_logger.log_skill_call, run_id, inferred_skill_id, normalized_args)
            tool_result = await _execute_read_skill(inferred_skill_id, normalized_args)
            await _safe_log_call(turn_logger.log_skill_result, run_id, inferred_skill_id, tool_result)
            executed_skill_count += 1
            return _response_text_from_tool_result(tool_result)

        for _turn in range(_MAX_LOOP_TURNS):
            try:
                completion = await call_chat_completion_fn(
                    loop_messages,
                    temperature=0.2,
                    max_tokens=400,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Agent loop model call failed: %s", exc, exc_info=True)
                assistant_text = "I couldn't reach the AI service right now. Please try again in a moment."
                break
            payload = _extract_mode_payload(str(completion.get("content") or ""))
            if payload.get("mode") != "tool_call":
                assistant_text = str(payload.get("text") or "").strip() or "How can I help?"
                break

            skill_id = _canonical_skill_id(str(payload.get("skill_id") or ""))
            raw_args = payload.get("args") if isinstance(payload.get("args"), dict) else {}

            try:
                if skill_id in _READ_ONLY_SKILLS:
                    args = _validate_read_skill_args(skill_id, raw_args)
                    await _safe_log_call(turn_logger.log_skill_call, run_id, skill_id, args)
                    tool_result = await _execute_read_skill(skill_id, args)
                    await _safe_log_call(turn_logger.log_skill_result, run_id, skill_id, tool_result)
                    executed_skill_count += 1

                    tool_context = json.dumps(tool_result, ensure_ascii=True, separators=(",", ":"))
                    loop_messages.append(
                        {
                            "role": "system",
                            "content": (
                                f"Tool result for {skill_id} (JSON): " + tool_context
                                + ". Continue by either calling another tool or replying to the user."
                            ),
                        }
                    )
                    continue

                if skill_id == "delegate_planner":
                    if execute_delegate_planner_fn is None:
                        raise ValueError("planner delegate executor not provided")
                    if not run_id:
                        assistant_text = (
                            "Planning isn't available right now because run logging is unavailable. "
                            "Please try again in a moment."
                        )
                        break
                    args = _validate_delegate_planner_args(raw_args)
                    await _safe_log_call(turn_logger.log_skill_call, run_id, skill_id, args)
                    request_text = str(args.get("request_text") or "").strip() or text
                    trace_id = str(run.get("trace_id") or "").strip() or run_id
                    if not str(run.get("trace_id") or "").strip():
                        await _safe_log_method("set_run_trace_id", run_id, trace_id)

                    planner_child = await asyncio.to_thread(
                        turn_logger.start_planner_run,
                        str(session.id),
                        parent_run_id=run_id,
                        trace_id=trace_id,
                    )
                    planner_child_run_id = str(planner_child.get("id") or "").strip()
                    if not planner_child_run_id:
                        raise ValueError("failed to create planner child run")

                    async def _planner_tool_executor(
                        *,
                        skill_id: str,
                        args: dict[str, Any] | None = None,
                        plan_args: dict[str, Any] | None = None,
                        **_kwargs: Any,
                    ) -> dict[str, Any]:
                        normalized_skill = str(skill_id or "").strip()
                        if not normalized_skill:
                            raise ValueError("skill_id is required")
                        raw_tool_args = (
                            dict(args)
                            if isinstance(args, dict)
                            else dict(plan_args)
                            if isinstance(plan_args, dict)
                            else {}
                        )

                        if normalized_skill in _MUTATION_SKILLS:
                            proposal = {
                                "skill_id": normalized_skill,
                                "args": raw_tool_args,
                                "rejected_reason": "planner_mutation_execution_disallowed",
                            }
                            return {
                                "ok": True,
                                "blocked": True,
                                "status": "mutation_proposal",
                                "response_text": "Mutation execution is disabled in planner delegation.",
                                "mutation_proposals": [proposal],
                            }
                        if normalized_skill not in _READ_ONLY_SKILLS:
                            raise ValueError(f"disallowed planner skill: {normalized_skill}")

                        normalized_args = _validate_read_skill_args(normalized_skill, raw_tool_args)
                        return await _execute_read_skill(normalized_skill, normalized_args)

                    planner_report = await execute_delegate_planner_fn(
                        request_text=request_text,
                        slack_user_id=slack_user_id,
                        channel=channel,
                        session=session,
                        session_service=session_service,
                        parent_run_id=run_id,
                        child_run_id=planner_child_run_id,
                        trace_id=trace_id,
                        tool_executor=_planner_tool_executor,
                        execute_skill_fn=_planner_tool_executor,
                        max_planner_turns=_MAX_LOOP_TURNS,
                        max_turns=_MAX_LOOP_TURNS,
                    )
                    if not isinstance(planner_report, dict):
                        raise ValueError("planner delegate report must be dict")
                    await _safe_log_call(turn_logger.log_skill_result, run_id, skill_id, planner_report)
                    executed_skill_count += 1

                    planner_status = str(planner_report.get("status") or "").strip().lower()
                    if planner_status not in {
                        "completed",
                        "blocked",
                        "failed",
                        "budget_exhausted",
                        "needs_clarification",
                    }:
                        planner_status = "completed" if bool(planner_report.get("ok")) else "failed"

                    child_run_status = (
                        "completed"
                        if planner_status == "completed"
                        else "failed"
                        if planner_status == "failed"
                        else "blocked"
                    )
                    await _safe_log_method("complete_run", planner_child_run_id, child_run_status)
                    planner_child_done = True
                    await _safe_log_method("log_planner_report", run_id, planner_report)

                    tool_context = json.dumps(planner_report, ensure_ascii=True, separators=(",", ":"))
                    loop_messages.append(
                        {
                            "role": "system",
                            "content": (
                                "Tool result for delegate_planner (JSON): " + tool_context
                                + ". Continue in the main assistant voice."
                            ),
                        }
                    )
                    if planner_status != "completed":
                        assistant_text = str(
                            planner_report.get("response_text")
                            or "I couldn't run planning right now. Could you rephrase and try again?"
                        )
                        break
                    continue

                if skill_id == "clickup_task_create":
                    args = _validate_task_create_args(raw_args)
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
                        await asyncio.to_thread(session_service.update_context, session.id, {_PENDING_KEY: proposal})
                        title = str(args.get("task_title") or "this task")
                        assistant_text = (
                            f"Ready to create task *{title}*. "
                            "Reply `confirm` to proceed or `cancel` to discard."
                        )
                    break

                if not skill_id:
                    raise ValueError("missing skill_id in tool_call")

                loop_messages.append(
                    {
                        "role": "system",
                        "content": (
                            f"Unsupported skill_id `{skill_id}`. "
                            "Use an available skill or reply directly to the user."
                        ),
                    }
                )
                continue
            except Exception as tool_exc:  # noqa: BLE001
                last_tool_error = f"{skill_id}: {tool_exc}"
                logger.info("Tool-call handling soft-failed (%s)", last_tool_error, exc_info=True)
                loop_messages.append(
                    {
                        "role": "system",
                        "content": (
                            f"Previous tool call failed ({last_tool_error}). "
                            "Adjust args/skill and continue, or reply with a clarification question."
                        ),
                    }
                )
                continue

        if not assistant_text:
            try:
                recovered_text = await _recover_from_natural_read_request()
                if recovered_text:
                    assistant_text = recovered_text
            except Exception as recovery_exc:  # noqa: BLE001
                logger.info("Natural read-intent recovery failed: %s", recovery_exc, exc_info=True)
                last_tool_error = last_tool_error or f"recovery: {recovery_exc}"

        if not assistant_text:
            if last_tool_error:
                assistant_text = (
                    "I can help with that, but I need one quick clarification "
                    "to run the right action. Could you rephrase with client and target outcome?"
                )
            else:
                assistant_text = "I couldn't complete that flow. Could you rephrase and try again?"

        assistant_text = _clean_assistant_text(assistant_text)
        if executed_skill_count == 0 and (
            _looks_like_task_list_request(text) or _looks_like_brand_list_request(text)
        ):
            try:
                recovered_text = await _recover_from_natural_read_request()
                if recovered_text:
                    assistant_text = recovered_text
            except Exception as recovery_exc:  # noqa: BLE001
                logger.info("No-skill natural-read recovery failed: %s", recovery_exc, exc_info=True)
        if _is_generic_failure_reply(assistant_text):
            try:
                recovered_text = await _recover_from_natural_read_request()
                if recovered_text:
                    assistant_text = recovered_text
            except Exception as recovery_exc:  # noqa: BLE001
                logger.info("Generic-fallback recovery failed: %s", recovery_exc, exc_info=True)
        elif _looks_like_brand_list_request(text) and _is_non_answer_action_promise(assistant_text):
            try:
                recovered_text = await _recover_from_natural_read_request()
                if recovered_text:
                    assistant_text = recovered_text
            except Exception as recovery_exc:  # noqa: BLE001
                logger.info("Action-promise recovery failed: %s", recovery_exc, exc_info=True)

        assistant_text = _postprocess_task_list_answer(text, assistant_text)
        assistant_text = _ensure_sop_draft_payload(text, assistant_text)

        await slack.post_message(channel=channel, text=assistant_text)
        await _safe_log_method("log_assistant_message", run_id, assistant_text)
        await _safe_log_method("complete_run", run_id, "completed")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Agent loop reply-only turn failed: %s", exc, exc_info=True)
        if planner_child_run_id and not planner_child_done:
            try:
                await _safe_log_method("complete_run", planner_child_run_id, "failed")
            except Exception:  # noqa: BLE001
                pass
        if run_id:
            try:
                await _safe_log_method("complete_run", run_id, "failed")
            except Exception:  # noqa: BLE001
                pass
        short_ref = (run_id or "n/a")[-8:]
        code = _error_code(exc)
        await slack.post_message(
            channel=channel,
            text=f"{_FAILURE_FALLBACK_TEXT} (ref: {short_ref}, code: {code})",
        )
        return True
