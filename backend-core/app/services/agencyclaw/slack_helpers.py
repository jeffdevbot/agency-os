"""Pure/helper utilities for AgencyClaw Slack runtime routing.

These helpers are intentionally side-effect free and safe to import from route
handlers without pulling in DB/network dependencies.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any


def _is_llm_orchestrator_enabled() -> bool:
    """Check if the LLM DM orchestrator feature flag is enabled."""
    return os.environ.get("AGENCYCLAW_LLM_DM_ORCHESTRATOR", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _is_legacy_intent_fallback_enabled() -> bool:
    """Whether regex-based deterministic intent fallback is enabled."""
    if not _is_llm_orchestrator_enabled():
        return True
    return os.environ.get("AGENCYCLAW_ENABLE_LEGACY_INTENTS", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


_DETERMINISTIC_CONTROL_INTENTS = frozenset({
    "switch_client",
    "set_default_client",
    "clear_defaults",
})


def _is_llm_strict_mode() -> bool:
    """Strict mode means LLM orchestrator on and legacy fallback disabled."""
    return _is_llm_orchestrator_enabled() and not _is_legacy_intent_fallback_enabled()


def _is_deterministic_control_intent(intent: str) -> bool:
    """Return True only for explicitly allowed deterministic control intents."""
    return intent in _DETERMINISTIC_CONTROL_INTENTS


def _should_block_deterministic_intent(intent: str) -> bool:
    """C13A/C13B gate: block deterministic non-control intents in strict LLM mode."""
    return _is_llm_strict_mode() and not _is_deterministic_control_intent(intent)


# Patterns that indicate a task list query.
# Captures an optional trailing client name after "for <client>".
_TASK_LIST_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"(?:what(?:'s| is) being worked on|what(?:'s| are) the tasks|"
        r"show (?:me )?tasks|list tasks|weekly tasks|this week(?:'s)? tasks)"
        r"(?:\s+(?:this week|this month|last\s+\d+\s+days)?\s*(?:for\s+(.+))?)?$"
    ),
    re.compile(
        r"tasks?\s+(?:(?:this week|this month|last\s+\d+\s+days)\s+)?for\s+(.+?)(?:\s+(?:this week|this month|last\s+\d+\s+days))?$"
    ),
]


def _sanitize_client_name_hint(value: str) -> str:
    """Normalize captured client hints (e.g., 'distex?' -> 'distex')."""
    collapsed = " ".join((value or "").strip().split())
    return re.sub(r"[?!.,:;]+$", "", collapsed).strip()


# Patterns for task creation intent.
# Supports: "create task for <client>: <title>", "add a task: <title>", "new task for <client>", etc.
_CREATE_TASK_PATTERN = re.compile(
    r"(?:create|add|new)\s+(?:a\s+)?tasks?"
    r"(?:\s+for\s+([^:]+?))?"  # optional "for <client>"
    r"(?:\s*:\s*(.+))?"        # optional ": <title>"
    r"$"
)

# Product identifier extraction (C12C Path-1; no catalog lookup).
_ASIN_TOKEN_RE = re.compile(r"\b[A-Z0-9]{10}\b")
_SKU_TOKEN_RE = re.compile(r"\b[A-Z0-9][A-Z0-9_-]{3,23}\b")


def _extract_product_identifiers(*texts: str) -> list[str]:
    """Extract explicit ASIN/SKU-like identifiers from provided text."""
    seen: set[str] = set()
    ordered: list[str] = []

    for raw in texts:
        text = (raw or "").upper()
        for token in _ASIN_TOKEN_RE.findall(text):
            if token not in seen:
                seen.add(token)
                ordered.append(token)
        for token in _SKU_TOKEN_RE.findall(text):
            if token in seen:
                continue
            has_alpha = any(ch.isalpha() for ch in token)
            has_digit = any(ch.isdigit() for ch in token)
            if not (has_alpha and has_digit):
                continue
            seen.add(token)
            ordered.append(token)

    return ordered


# Patterns for confirming a draft task creation.
_CONFIRM_DRAFT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^(?:create anyway|create as draft|just create it|yes,?\s*create(?:\s+it)?)$"),
]


def _task_list_params_from_text(original_text: str) -> dict[str, Any] | None:
    text = " ".join((original_text or "").strip().split())
    lower_text = text.lower()

    matched = False
    for pattern in _TASK_LIST_PATTERNS:
        if pattern.search(lower_text):
            matched = True
            break
    if not matched:
        return None

    window = ""
    window_days: int | None = None

    if "this month" in lower_text:
        window = "this_month"
    else:
        last_days_match = re.search(r"\blast\s+(\d{1,3})\s+days\b", lower_text)
        if last_days_match:
            parsed_days = int(last_days_match.group(1))
            if 1 <= parsed_days <= 365:
                window = "last_n_days"
                window_days = parsed_days

    client_name = ""
    for_match = re.search(r"\bfor\s+(.+)$", text, re.IGNORECASE)
    if for_match:
        client_name = _sanitize_client_name_hint(for_match.group(1))
        client_name = re.sub(
            r"\s+(?:this week|this month|last\s+\d+\s+days)$",
            "",
            client_name,
            flags=re.IGNORECASE,
        ).strip()

    params: dict[str, Any] = {"client_name": client_name}
    if window:
        params["window"] = window
    if window_days is not None:
        params["window_days"] = window_days
    return params


def _classify_message(text: str) -> tuple[str, dict[str, Any]]:
    original = " ".join((text or "").strip().split())
    t = original.lower()
    if t.startswith("switch to "):
        return ("switch_client", {"client_name": t.removeprefix("switch to ").strip()})
    if t.startswith("work on "):
        return ("switch_client", {"client_name": t.removeprefix("work on ").strip()})

    # C10E: Set / clear default client preferences
    if t.startswith("set my default client to "):
        return ("set_default_client", {"client_name": t.removeprefix("set my default client to ").strip()})
    if t.startswith("set default client "):
        return ("set_default_client", {"client_name": t.removeprefix("set default client ").strip()})
    if t in ("clear my defaults", "clear defaults", "clear my default client"):
        return ("clear_defaults", {})

    # Task creation (check BEFORE weekly tasks — "create task for X" must not match "tasks for X")
    m = _CREATE_TASK_PATTERN.match(t)
    if m:
        client_hint = _sanitize_client_name_hint(m.group(1) or "")
        # Preserve original casing for the task title by extracting from original text
        title_start = m.start(2) if m.group(2) else -1
        task_title = original[title_start:].strip() if title_start >= 0 else ""
        return ("create_task", {"client_name": client_hint, "task_title": task_title})

    # Task list queries (weekly default, optional custom windows).
    task_list_params = _task_list_params_from_text(original)
    if task_list_params is not None:
        return ("weekly_tasks", task_list_params)

    # Confirm draft creation (only meaningful when pending state exists in session)
    for pattern in _CONFIRM_DRAFT_PATTERNS:
        if pattern.match(t):
            return ("confirm_draft_task", {})

    # C11A: Command Center read-only skills
    if any(kw in t for kw in ("show me clients", "list clients", "my clients")):
        return ("cc_client_lookup", {"query": ""})
    if any(kw in t for kw in ("list all brands", "list brands", "show brands")):
        return ("cc_brand_list_all", {})
    if any(kw in t for kw in ("missing clickup mapping", "mapping audit", "brands missing")):
        return ("cc_brand_clickup_mapping_audit", {})

    # C11E: Brand mapping remediation
    def _extract_remediation_client_hint(trigger: str) -> str:
        idx = t.find(trigger)
        if idx < 0:
            return ""
        tail = t[idx + len(trigger):].strip()
        if not tail.startswith("for "):
            return ""
        return _sanitize_client_name_hint(tail.removeprefix("for ").strip())

    for kw in (
        "apply brand mapping remediation",
        "apply mapping remediation",
        "run mapping remediation now",
        "apply remediation",
    ):
        if kw in t:
            client_hint = _extract_remediation_client_hint(kw)
            return (
                "cc_brand_mapping_remediation_apply",
                {"client_name": client_hint} if client_hint else {},
            )

    for kw in (
        "preview brand mapping remediation",
        "preview mapping remediation",
        "show mapping remediation plan",
        "what can we auto-fix for mappings",
        "remediation preview",
        "mapping remediation",
    ):
        if kw in t:
            client_hint = _extract_remediation_client_hint(kw)
            return (
                "cc_brand_mapping_remediation_preview",
                {"client_name": client_hint} if client_hint else {},
            )

    # C12A: Assignment mutation skills
    _ASSIGN_PATTERN = re.compile(
        r"(?:assign|make|set)\s+(.+?)\s+(?:as|to)\s+(\S+)"
        r"(?:\s+(?:on|for)\s+(.+))?$",
        re.IGNORECASE,
    )
    _REMOVE_PATTERN = re.compile(
        r"(?:remove|unassign)\s+(.+?)\s+(?:from|as)\s+(\S+)"
        r"(?:\s+(?:on|for)\s+(.+))?$",
        re.IGNORECASE,
    )
    m = _ASSIGN_PATTERN.match(original)
    if m:
        return ("cc_assignment_upsert", {
            "person_name": m.group(1).strip(),
            "role_slug": m.group(2).strip(),
            "client_name": _sanitize_client_name_hint(m.group(3) or ""),
        })
    m = _REMOVE_PATTERN.match(original)
    if m:
        return ("cc_assignment_remove", {
            "person_name": m.group(1).strip(),
            "role_slug": m.group(2).strip(),
            "client_name": _sanitize_client_name_hint(m.group(3) or ""),
        })

    # C12B: Brand CRUD mutation skills
    _CREATE_BRAND_PATTERN = re.compile(
        r"(?:create|add|new)\s+brand\s+(.+?)\s+(?:for|under|on)\s+(.+?)$",
        re.IGNORECASE,
    )
    _UPDATE_BRAND_PATTERN = re.compile(
        r"(?:update|edit|rename)\s+brand\s+(.+?)(?:\s+(?:for|under|on)\s+(.+?))?$",
        re.IGNORECASE,
    )
    m = _CREATE_BRAND_PATTERN.match(original)
    if m:
        return ("cc_brand_create", {
            "brand_name": m.group(1).strip(),
            "client_name": _sanitize_client_name_hint(m.group(2) or ""),
        })
    m = _UPDATE_BRAND_PATTERN.match(original)
    if m:
        return ("cc_brand_update", {
            "brand_name": m.group(1).strip(),
            "client_name": _sanitize_client_name_hint(m.group(2) or ""),
        })

    return ("help", {})


def _help_text() -> str:
    return (
        "I can help with ClickUp tasks, weekly status, and SOP-based work.\n\n"
        "Ask naturally, for example:\n"
        "- What's being worked on this week for Distex?\n"
        "- Show tasks for Distex this month\n"
        "- Show tasks for Distex last 14 days\n"
        "- Create a task for Distex: Set up 20% coupon for Thorinox\n"
        "- Switch to Revant\n"
        "- Show me clients / list brands / brands missing clickup mapping\n"
        "- Preview brand mapping remediation / apply brand mapping remediation"
    )


_WEEKLY_TASK_CAP = 200


def _current_week_range_ms() -> tuple[int, int]:
    """Return (start_ms, end_ms) for the current ISO week (Monday 00:00 UTC through Sunday 23:59)."""
    now = datetime.now(timezone.utc)
    monday = now - timedelta(days=now.weekday())
    start = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def _current_month_range_ms() -> tuple[int, int]:
    """Return (start_ms, end_ms) for current calendar month in UTC."""
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def _last_n_days_range_ms(days: int) -> tuple[int, int]:
    """Return (start_ms, end_ms) for trailing N-day window ending now."""
    bounded_days = max(1, min(int(days), 365))
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=bounded_days)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def _resolve_task_range(
    *,
    window: str = "",
    window_days: int | None = None,
    date_from: str = "",
    date_to: str = "",
) -> tuple[int, int, str]:
    """Resolve query window into (start_ms, end_ms, display_label)."""
    if window == "this_month":
        start_ms, end_ms = _current_month_range_ms()
        return start_ms, end_ms, "this month"
    if window == "last_n_days":
        try:
            days = int(window_days or 14)
        except (TypeError, ValueError):
            days = 14
        start_ms, end_ms = _last_n_days_range_ms(days)
        return start_ms, end_ms, f"last {days} days"
    if date_from and date_to:
        try:
            start = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            end = datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
            return int(start.timestamp() * 1000), int(end.timestamp() * 1000), f"{date_from} to {date_to}"
        except ValueError:
            pass
    start_ms, end_ms = _current_week_range_ms()
    return start_ms, end_ms, "this week"


def _format_task_line(task: dict[str, Any]) -> str:
    name = str(task.get("name") or "Untitled")
    url = task.get("url") or ""
    status_obj = task.get("status")
    status = str(status_obj.get("status") or "") if isinstance(status_obj, dict) else ""

    assignees = task.get("assignees") or []
    assignee_names = []
    for a in (assignees if isinstance(assignees, list) else []):
        if isinstance(a, dict):
            assignee_names.append(str(a.get("username") or a.get("initials") or ""))

    parts = []
    if url:
        parts.append(f"<{url}|{name}>")
    else:
        parts.append(name)
    if status:
        parts.append(f"[{status}]")
    if assignee_names:
        parts.append(f"({', '.join(n for n in assignee_names if n)})")
    return "• " + " ".join(parts)


def _format_weekly_tasks_response(
    *,
    client_name: str,
    tasks: list[dict[str, Any]],
    total_fetched: int,
    brand_names: list[str],
) -> str:
    return _format_task_list_response(
        client_name=client_name,
        tasks=tasks,
        total_fetched=total_fetched,
        brand_names=brand_names,
        range_label="this week",
    )


def _format_task_list_response(
    *,
    client_name: str,
    tasks: list[dict[str, Any]],
    total_fetched: int,
    brand_names: list[str],
    range_label: str,
) -> str:
    if not tasks:
        brands = ", ".join(brand_names) if brand_names else "no brands"
        return f"No tasks found for *{client_name}* ({range_label}; checked: {brands})."

    header = (
        f"*Tasks for {client_name}* ({range_label}, "
        f"{len(tasks)} task{'s' if len(tasks) != 1 else ''}):\n"
    )
    lines = [_format_task_line(t) for t in tasks[:_WEEKLY_TASK_CAP]]
    body = "\n".join(lines)

    truncation = ""
    if total_fetched > _WEEKLY_TASK_CAP:
        truncation = f"\n\n_Showing {_WEEKLY_TASK_CAP} of {total_fetched} tasks. Check ClickUp for the full list._"

    return header + body + truncation
