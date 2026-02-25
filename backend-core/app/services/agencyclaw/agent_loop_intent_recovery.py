"""Intent detection and reply post-processing helpers for agent loop runtime."""

from __future__ import annotations

import json
import re
from typing import Any

_CLIENT_HINT_PATTERN = re.compile(r"\bfor\s+([^,\n\.]+)", re.IGNORECASE)
_TOP_N_PATTERN = re.compile(r"\btop\s+(\d+)\b", re.IGNORECASE)
_TASK_LINK_TITLE_PATTERN = re.compile(r"\|([^>]+)>")


def extract_client_hint_from_text(text: str) -> str:
    match = _CLIENT_HINT_PATTERN.search(text or "")
    if not match:
        return ""
    hint = (match.group(1) or "").strip()
    normalized = re.sub(r"\s+", " ", hint).strip(" .,:;")
    normalized = re.sub(r"^(client|brand)\s+", "", normalized, flags=re.IGNORECASE)
    return normalized.strip(" .,:;")


def looks_like_task_list_request(text: str) -> bool:
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


def looks_like_brand_list_request(text: str) -> bool:
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


def infer_window_from_text(text: str) -> str:
    lowered = (text or "").strip().lower()
    if "this week" in lowered or "weekly" in lowered:
        return "this_week"
    if "this month" in lowered or "monthly" in lowered:
        return "this_month"
    return ""


def response_text_from_tool_result(tool_result: dict[str, Any]) -> str:
    raw = tool_result.get("response_text")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return json.dumps(tool_result, ensure_ascii=True, separators=(",", ":"))


def is_generic_failure_reply(text: str) -> bool:
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


def is_non_answer_action_promise(text: str) -> bool:
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


def requested_top_n(text: str) -> int | None:
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


def postprocess_task_list_answer(user_text: str, assistant_text: str) -> str:
    if not looks_like_task_list_request(user_text):
        return assistant_text
    if "*Tasks" not in assistant_text:
        return assistant_text

    lines = assistant_text.splitlines()
    bullet_idxs = _task_bullet_indices(lines)
    if not bullet_idxs:
        return assistant_text

    top_n = requested_top_n(user_text)
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
    hint = extract_client_hint_from_text(text)
    if hint:
        return hint
    lowered = text or ""
    match = re.search(r"\bfor\s+([A-Za-z0-9][A-Za-z0-9 _-]{1,60})", lowered)
    if not match:
        return ""
    candidate = (match.group(1) or "").strip(" .,:;")
    candidate = re.sub(r"^(client|brand)\s+", "", candidate, flags=re.IGNORECASE)
    return candidate


def ensure_sop_draft_payload(user_text: str, assistant_text: str) -> str:
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

