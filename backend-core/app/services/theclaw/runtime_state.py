"""Runtime state parsing and normalization helpers for The Claw."""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from uuid import uuid4

_logger = logging.getLogger(__name__)

SESSION_RESOLVED_CONTEXT_KEY = "theclaw_resolved_context_v1"
SESSION_DRAFT_TASKS_KEY = "theclaw_draft_tasks_v1"
SESSION_PENDING_CONFIRMATION_KEY = "theclaw_pending_confirmation_v1"
STATE_BLOCK_START = "---THECLAW_STATE_JSON---"
STATE_BLOCK_END = "---END_THECLAW_STATE_JSON---"
STATE_BLOCK_RE = re.compile(
    rf"{re.escape(STATE_BLOCK_START)}\s*(.*?)\s*{re.escape(STATE_BLOCK_END)}",
    re.DOTALL,
)
UNKNOWN_CONTEXT_VALUES = frozenset({"unknown", ""})
CONTEXT_FIELD_MAX_LEN = 120
DRAFT_TASK_ID_MAX_LEN = 128


def sanitize_context_field(value: object) -> str:
    text = str(value) if value is not None else ""
    sanitized = re.sub(r"[\x00-\x1f\x7f]", " ", text).strip()
    return sanitized[:CONTEXT_FIELD_MAX_LEN]


def resolved_context_from_session_context(context: Any) -> dict[str, Any] | None:
    if not isinstance(context, dict):
        return None
    raw = context.get(SESSION_RESOLVED_CONTEXT_KEY)
    if not isinstance(raw, dict):
        return None
    return raw


def draft_tasks_from_session_context(context: Any) -> list[dict[str, Any]]:
    if not isinstance(context, dict):
        return []
    raw = context.get(SESSION_DRAFT_TASKS_KEY)
    validated = _validate_draft_tasks_update(raw)
    return validated if isinstance(validated, list) else []


def pending_confirmation_from_session_context(context: Any) -> dict[str, Any] | None:
    if not isinstance(context, dict):
        return None
    raw = context.get(SESSION_PENDING_CONFIRMATION_KEY)
    validated = _validate_pending_confirmation_update(raw)
    return validated if isinstance(validated, dict) else None


def _validate_resolved_context_update(raw_value: Any) -> dict[str, Any] | None:
    if not isinstance(raw_value, dict):
        return None

    normalized: dict[str, Any] = {}
    for field in ("client", "brand", "clickup_space", "market_scope", "confidence", "notes"):
        value = raw_value.get(field)
        normalized[field] = sanitize_context_field(value) if value is not None else None

    has_identity = any(
        normalized.get(field) and str(normalized[field]).strip().lower() not in UNKNOWN_CONTEXT_VALUES
        for field in ("client", "brand", "clickup_space", "market_scope")
    )
    if not has_identity:
        return None
    return normalized


def _validate_draft_tasks_update(raw_value: Any) -> list[dict[str, Any]] | None:
    if not isinstance(raw_value, list):
        return None

    normalized_tasks: list[dict[str, Any]] = []
    for item in raw_value:
        if not isinstance(item, dict):
            continue

        task: dict[str, Any] = {}
        for field in (
            "id",
            "title",
            "marketplace",
            "type",
            "description",
            "action",
            "specifics",
            "target_metric",
            "start_date",
            "deadline",
            "coupon_window",
            "reference_docs",
            "source",
            "status",
        ):
            value = item.get(field)
            task[field] = sanitize_context_field(value) if value is not None else None

        asin_list = item.get("asin_list")
        if isinstance(asin_list, list):
            task["asin_list"] = [
                sanitize_context_field(value)
                for value in asin_list
                if sanitize_context_field(value)
            ][:20]
        else:
            task["asin_list"] = []

        source = (task.get("source") or "").lower()
        if source not in {"meeting_notes", "email", "slack_message", "report", "ad_hoc"}:
            task["source"] = "ad_hoc"

        status = (task.get("status") or "").lower()
        if status not in {"draft", "confirmed", "sent"}:
            task["status"] = "draft"

        if task.get("title") or task.get("description") or task.get("action"):
            normalized_tasks.append(task)

    if raw_value and not normalized_tasks:
        return None
    return normalized_tasks


def _validate_pending_confirmation_update(raw_value: Any) -> dict[str, Any] | None:
    if not isinstance(raw_value, dict):
        return None

    task_id = sanitize_context_field(raw_value.get("task_id"))
    task_title = sanitize_context_field(raw_value.get("task_title"))
    clickup_space_id = sanitize_context_field(raw_value.get("clickup_space_id"))
    clickup_space = sanitize_context_field(raw_value.get("clickup_space"))
    notes = sanitize_context_field(raw_value.get("notes"))

    if not task_id and not task_title:
        return None

    status = sanitize_context_field(raw_value.get("status")).lower()
    if status != "pending":
        status = "pending"

    return {
        "task_id": task_id or None,
        "task_title": task_title or None,
        "clickup_space_id": clickup_space_id or None,
        "clickup_space": clickup_space or None,
        "status": status,
        "notes": notes or None,
    }


def _normalize_draft_task_id(value: Any) -> str:
    task_id = sanitize_context_field(value)
    if not task_id:
        return ""
    return task_id[:DRAFT_TASK_ID_MAX_LEN]


def _draft_task_identity_key(task: dict[str, Any]) -> tuple[str, str, str, str]:
    title = str(task.get("title") or "").strip().lower()
    source = str(task.get("source") or "").strip().lower()
    action = str(task.get("action") or "").strip().lower()
    asins = ",".join(str(value or "").strip().lower() for value in task.get("asin_list") or [])
    return (title, source, action, asins)


def _assign_or_preserve_draft_task_ids(
    *,
    incoming_tasks: list[dict[str, Any]],
    existing_tasks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    existing_by_id: dict[str, dict[str, Any]] = {}
    existing_ids_by_key: dict[tuple[str, str, str, str], list[str]] = {}
    for task in existing_tasks:
        task_id = _normalize_draft_task_id(task.get("id"))
        if not task_id:
            continue
        existing_by_id[task_id] = task
        key = _draft_task_identity_key(task)
        existing_ids_by_key.setdefault(key, []).append(task_id)

    used_ids: set[str] = set()
    normalized_tasks: list[dict[str, Any]] = []

    for incoming in incoming_tasks:
        task = dict(incoming)
        incoming_id = _normalize_draft_task_id(task.get("id"))
        chosen_id = ""

        if incoming_id and incoming_id in existing_by_id and incoming_id not in used_ids:
            chosen_id = incoming_id

        if not chosen_id:
            key = _draft_task_identity_key(task)
            candidates = existing_ids_by_key.get(key, [])
            while candidates and candidates[0] in used_ids:
                candidates.pop(0)
            if candidates:
                chosen_id = candidates.pop(0)

        if not chosen_id:
            chosen_id = str(uuid4())
            while chosen_id in used_ids:
                chosen_id = str(uuid4())

        used_ids.add(chosen_id)
        task["id"] = chosen_id

        existing = existing_by_id.get(chosen_id)
        if existing and str(existing.get("status") or "").lower() in {"confirmed", "sent"}:
            if str(task.get("status") or "").lower() == "draft":
                task["status"] = str(existing.get("status") or "draft").lower()

        normalized_tasks.append(task)

    return normalized_tasks


def finalize_state_updates_for_turn(
    *,
    state_updates: dict[str, Any],
    session_context: dict[str, Any] | None,
) -> dict[str, Any]:
    if not state_updates:
        return {}

    finalized = dict(state_updates)
    if SESSION_DRAFT_TASKS_KEY in finalized:
        incoming = finalized.get(SESSION_DRAFT_TASKS_KEY)
        if isinstance(incoming, list):
            existing = draft_tasks_from_session_context(session_context or {})
            finalized[SESSION_DRAFT_TASKS_KEY] = _assign_or_preserve_draft_task_ids(
                incoming_tasks=incoming,
                existing_tasks=existing,
            )
    return finalized


def coerce_runtime_context_updates(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    raw_updates = payload.get("context_updates")
    if not isinstance(raw_updates, dict):
        return {}

    updates: dict[str, Any] = {}
    resolved_update = _validate_resolved_context_update(raw_updates.get(SESSION_RESOLVED_CONTEXT_KEY))
    if resolved_update is not None:
        updates[SESSION_RESOLVED_CONTEXT_KEY] = resolved_update

    draft_tasks_update = _validate_draft_tasks_update(raw_updates.get(SESSION_DRAFT_TASKS_KEY))
    if draft_tasks_update is not None:
        updates[SESSION_DRAFT_TASKS_KEY] = draft_tasks_update

    if SESSION_PENDING_CONFIRMATION_KEY in raw_updates and raw_updates.get(SESSION_PENDING_CONFIRMATION_KEY) is None:
        updates[SESSION_PENDING_CONFIRMATION_KEY] = None
    else:
        pending_confirmation_update = _validate_pending_confirmation_update(raw_updates.get(SESSION_PENDING_CONFIRMATION_KEY))
        if pending_confirmation_update is not None:
            updates[SESSION_PENDING_CONFIRMATION_KEY] = pending_confirmation_update

    return updates


def extract_reply_and_context_updates(reply_text: str) -> tuple[str, dict[str, Any]]:
    text = (reply_text or "").strip()
    if not text:
        return "", {}

    matches = list(STATE_BLOCK_RE.finditer(text))
    if not matches:
        return text, {}

    visible_text = STATE_BLOCK_RE.sub("", text).strip()
    payload_text = matches[-1].group(1).strip()
    try:
        decoded = json.loads(payload_text)
    except json.JSONDecodeError:
        _logger.warning("The Claw state block JSON parse failed")
        return visible_text, {}

    return visible_text, coerce_runtime_context_updates(decoded)


def finalize_reply_text(reply_text: str, *, fallback_text: str) -> str:
    cleaned = (reply_text or "").strip()
    if not cleaned:
        return fallback_text
    return cleaned
