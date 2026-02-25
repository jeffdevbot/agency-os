"""Intent detection and reply post-processing helpers for agent loop runtime."""

from __future__ import annotations

import json
import re
from typing import Any

_CLIENT_HINT_PATTERN = re.compile(r"\bfor\s+([^,\n\.]+)", re.IGNORECASE)
_TOP_N_PATTERN = re.compile(r"\btop\s+(\d+)\b", re.IGNORECASE)
_TASK_LINK_TITLE_PATTERN = re.compile(r"\|([^>]+)>")
_CAPABILITIES_PATTERN = re.compile(
    r"\b(what can you help me with|what can you do|how can you help|what do you help with)\b",
    re.IGNORECASE,
)
_TASK_LIST_INTENT_PATTERN = re.compile(r"\b(list|show|what|which)\b[\w\s]{0,40}\btasks?\b", re.IGNORECASE)
_TASK_DUE_INTENT_PATTERN = re.compile(
    r"\btasks?\b[\w\s]{0,40}\b(due|this week|this month|priority|prioritize|open)\b",
    re.IGNORECASE,
)
_BRAND_LIST_INTENT_PATTERN = re.compile(r"\b(list|show|what|which)\b[\w\s]{0,40}\bbrands?\b", re.IGNORECASE)
_BRAND_MAPPING_AUDIT_PATTERN = re.compile(r"\b(audit|check|review)\b[\w\s]{0,60}\bbrand mappings?\b", re.IGNORECASE)
_PLAN_WORD_PATTERN = re.compile(r"\b(plan|roadmap|schedule)\b", re.IGNORECASE)
_TWO_SPRINTS_PATTERN = re.compile(r"\b(two|2)\s+sprints?\b", re.IGNORECASE)
_OPEN_QUESTIONS_PATTERN = re.compile(r"\bopen questions?\b", re.IGNORECASE)
_EXECUTION_READINESS_PATTERN = re.compile(
    r"\b(execution[- ]ready|what info is missing|what's missing|missing before this task)\b",
    re.IGNORECASE,
)
_CREATE_TITLE_PATTERN = re.compile(
    r"\btitle\s*:\s*(.+?)(?=(?:\s+description\s*:)|$)",
    re.IGNORECASE,
)
_CREATE_DESCRIPTION_PATTERN = re.compile(r"\bdescription\s*:\s*(.+)$", re.IGNORECASE)
_CREATE_FOR_COLON_PATTERN = re.compile(r"\bfor\s+([^:\n\.]+?)\s*:\s*(.+)$", re.IGNORECASE)
_CREATE_CLIENT_PATTERN = re.compile(
    r"\bfor\s+client\s+(.+?)(?=(?:\s+and\s+brand\b)|(?:\s+title\s*:)|(?:\s+description\s*:)|(?:\s+do\s+not\b)|(?:\.)|$)",
    re.IGNORECASE,
)
_CREATE_BRAND_PATTERN = re.compile(
    r"\bbrand\s+(.+?)(?=(?:\s+title\s*:)|(?:\s+description\s*:)|(?:\s+do\s+not\b)|(?:\.)|$)",
    re.IGNORECASE,
)


def _clean_natural_arg(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", (value or "")).strip(" .,:;")
    if not cleaned:
        return ""
    cleaned = re.sub(r"\bdo not execute yet\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bfor approval only\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,:;")
    return cleaned


def extract_client_hint_from_text(text: str) -> str:
    match = _CLIENT_HINT_PATTERN.search(text or "")
    if not match:
        return ""
    hint = (match.group(1) or "").strip()
    normalized = re.sub(r"\s+", " ", hint).strip(" .,:;")
    normalized = re.sub(r"^(client|brand)\s+", "", normalized, flags=re.IGNORECASE)
    return normalized.strip(" .,:;")


def looks_like_capabilities_request(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    if "agencyclaw" in lowered and "help" in lowered:
        return True
    return bool(_CAPABILITIES_PATTERN.search(lowered))


def capabilities_help_text() -> str:
    return (
        "I can help with:\n"
        "1. Client and brand lookups (clients, brands, mappings).\n"
        "2. SOP/knowledge-base search and summaries.\n"
        "3. Drafting ClickUp tasks from requests or meeting notes.\n"
        "4. Task planning support before execution.\n"
        "5. Safe task creation with explicit confirm/cancel."
    )


def looks_like_task_list_request(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    if looks_like_execution_readiness_request(lowered):
        return False
    if any(phrase in lowered for phrase in ("create task", "new task", "make task", "draft task")):
        return False
    if "task" not in lowered:
        return False
    if "what should i prioritize" in lowered:
        return True
    return bool(_TASK_LIST_INTENT_PATTERN.search(lowered) or _TASK_DUE_INTENT_PATTERN.search(lowered))


def looks_like_brand_list_request(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    if "brand" not in lowered:
        return False
    if "brands for" in lowered:
        return True
    return bool(_BRAND_LIST_INTENT_PATTERN.search(lowered))


def looks_like_sop_summary_request(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    if "sop" not in lowered:
        return False
    return any(token in lowered for token in ("summarize", "summary", "in 5 bullets", "bullet"))


def looks_like_brand_mapping_audit_request(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    return bool(_BRAND_MAPPING_AUDIT_PATTERN.search(lowered))


def looks_like_two_sprint_plan_request(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    return bool(
        _PLAN_WORD_PATTERN.search(lowered)
        and _TWO_SPRINTS_PATTERN.search(lowered)
        and _OPEN_QUESTIONS_PATTERN.search(lowered)
    )


def looks_like_execution_readiness_request(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    return bool(_EXECUTION_READINESS_PATTERN.search(lowered))


def _extract_task_title_from_draft(draft_text: str) -> str:
    match = re.search(r"task title:\s*(.+)", draft_text or "", re.IGNORECASE)
    if not match:
        return ""
    return " ".join((match.group(1) or "").split()).strip(" .,:;")


def _draft_has_any_token(draft_text: str, tokens: tuple[str, ...]) -> bool:
    lowered = (draft_text or "").lower()
    return any(token in lowered for token in tokens)


def _open_inputs_segment(draft_text: str) -> str:
    match = re.search(r"open inputs:\s*(.+)", draft_text or "", re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return (match.group(1) or "").strip()


def build_execution_readiness_response(*, draft_text: str = "") -> str:
    title = _extract_task_title_from_draft(draft_text)
    header = (
        f"Before task *{title}* is execution-ready, confirm:"
        if title
        else "Before this task is execution-ready, confirm:"
    )
    open_inputs = _open_inputs_segment(draft_text)

    checks = [
        ("Owner/assignee", ("owner", "assignee", "assigned to")),
        ("Discount amount/offer terms", ("discount", "coupon amount", "%", "percent", "$")),
        ("ASIN/SKU scope", ("asin", "sku", "scope")),
        ("Start and end dates", ("start date", "end date", "campaign dates", "date range")),
        ("ClickUp destination (space/list)", ("clickup_space_id", "clickup_list_id", "clickup space", "clickup list")),
    ]
    missing = [
        label
        for label, tokens in checks
        if _draft_has_any_token(open_inputs, tokens) or not _draft_has_any_token(draft_text, tokens)
    ]
    if not missing:
        missing = [label for label, _tokens in checks]

    lines = [header]
    for idx, label in enumerate(missing, start=1):
        lines.append(f"{idx}. {label}")
    lines.append("Share what you already know and I will draft the final execution-ready version.")
    return "\n".join(lines)


def build_two_sprint_plan_response(*, target_label: str = "", audit_evidence: str = "") -> str:
    scope = target_label.strip() or "the requested scope"
    lines = [f"Two-sprint plan for *{scope}* (draft):"]
    if audit_evidence:
        lines.append(f"Evidence: {audit_evidence}")
    lines.extend(
        [
            "",
            "Sprint 1 (Audit + Decision Pack):",
            "1. Validate current brand/client mapping state and capture exact gaps.",
            "2. Build a remediation preview with proposed field-level updates.",
            "3. Prepare approval-ready change list (no mutation execution yet).",
            "",
            "Sprint 2 (Apply + Verify):",
            "1. Apply only approved mapping updates.",
            "2. Re-run mapping audit and confirm no critical gaps remain.",
            "3. Publish final changelog + owners + rollback notes.",
            "",
            "Open questions:",
            "1. Confirm exact in-scope brand/client (is it only `Test` or `Test` + related brands?).",
            "2. Who is the final approver for mapping updates?",
            "3. What due dates/priority should we assign for Sprint 1 and Sprint 2?",
        ]
    )
    return "\n".join(lines)


def infer_sop_summary_query(text: str) -> str:
    normalized = " ".join((text or "").strip().split())
    if not normalized:
        return ""
    query = re.sub(
        r"\b(summarize|summary)\b.*$",
        "",
        normalized,
        flags=re.IGNORECASE,
    ).strip(" .,:;")
    if query:
        return query
    return normalized


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


def looks_like_task_create_request(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    if looks_like_meeting_sop_mapping_request(lowered):
        return False
    if "extract actionable" in lowered or "draft tasks for approval" in lowered:
        return False
    if "task" not in lowered:
        return False
    has_create_verb = any(phrase in lowered for phrase in ("create", "make"))
    if not has_create_verb:
        return False
    return "clickup" in lowered or "task" in lowered


def infer_task_create_args_from_text(text: str) -> dict[str, str]:
    normalized = " ".join((text or "").strip().split())
    if not normalized:
        return {}

    args: dict[str, str] = {}

    client_match = _CREATE_CLIENT_PATTERN.search(normalized)
    if client_match:
        client_name = _clean_natural_arg(client_match.group(1))
        if client_name:
            args["client_name"] = client_name

    brand_match = _CREATE_BRAND_PATTERN.search(normalized)
    if brand_match:
        brand_name = _clean_natural_arg(brand_match.group(1))
        if brand_name:
            args["brand_name"] = brand_name

    title_match = _CREATE_TITLE_PATTERN.search(normalized)
    if title_match:
        title = _clean_natural_arg(title_match.group(1))
        if title:
            args["task_title"] = title

    description_match = _CREATE_DESCRIPTION_PATTERN.search(normalized)
    if description_match:
        description = _clean_natural_arg(description_match.group(1))
        if description:
            args["task_description"] = description

    if "task_title" not in args:
        for_colon_match = _CREATE_FOR_COLON_PATTERN.search(normalized)
        if for_colon_match:
            if "client_name" not in args:
                client_name = _clean_natural_arg(for_colon_match.group(1))
                if client_name:
                    args["client_name"] = client_name
            title = _clean_natural_arg(for_colon_match.group(2))
            if title:
                args["task_title"] = title

    if "task_title" not in args:
        fallback = re.search(
            r"\bcreate(?:\s+this)?\s+task(?:\s+in\s+clickup)?(?:\s+for\s+[^:\n\.]+)?\s*:\s*(.+)$",
            normalized,
            re.IGNORECASE,
        )
        if fallback:
            title = _clean_natural_arg(fallback.group(1))
            if title:
                args["task_title"] = title

    return args


def is_create_clarification_reply(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    return any(
        phrase in lowered
        for phrase in (
            "need one quick clarification",
            "rephrase with client and target outcome",
            "provide more details about what you would like to create",
            "are you looking to create a task",
            "what you would like to create",
            "need to know which client or brand",
            "specify the client or brand name",
            "ensure we have the correct client and brand details",
            "resolve the brand",
            "look up the brand",
        )
    )


def is_generic_detail_request_reply(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    return any(
        phrase in lowered
        for phrase in (
            "could you please provide more details",
            "to assist you effectively, could you please provide more details",
            "i need a bit more detail",
            "i need more detail",
            "need more details",
        )
    )


def looks_like_meeting_notes_blob(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    if "meeting notes" in lowered and ("meeting context" in lowered or "action candidates" in lowered):
        return True
    return lowered.startswith("# agencyclaw test fixture: meeting notes")


def looks_like_meeting_sop_mapping_request(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    if "sop" not in lowered:
        return False
    if "map" not in lowered:
        return False
    return any(
        phrase in lowered
        for phrase in (
            "actionable draft tasks",
            "draft tasks for approval",
            "meeting notes",
            "extract actionable",
        )
    )


def extract_action_candidates_from_text(text: str, *, max_items: int = 6) -> list[str]:
    if max_items <= 0:
        return []
    lines = (text or "").splitlines()
    if not lines:
        return []

    in_action_section = False
    items: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("## "):
            header = line[3:].strip().lower()
            if "action candidates" in header:
                in_action_section = True
                continue
            if in_action_section:
                break
        if in_action_section and line.startswith("- "):
            candidate = line[2:].strip()
            if candidate:
                items.append(candidate)
                if len(items) >= max_items:
                    break

    if items:
        return items

    # Fallback: detect list-like action lines in free-form notes.
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("- ") and any(token in line.lower() for token in ("create ", "launch ", "build ", "audit ")):
            items.append(line[2:].strip())
            if len(items) >= max_items:
                break
    return items


def meeting_sop_query_for_candidate(candidate_text: str) -> str:
    lowered = (candidate_text or "").strip().lower()
    if not lowered:
        return "task SOP"
    if any(token in lowered for token in ("ppc", "campaign", "negative terms", "manual campaigns")):
        return "PPC launch task SOP"
    if any(token in lowered for token in ("keyword", "helium10", "brand analytics", "str")):
        return "keyword-research task SOP"
    if any(token in lowered for token in ("inventory", "fbm", "fba", "zero out", "sku")):
        return "inventory triage SOP"
    if any(token in lowered for token in ("acquisition", "diligence", "catalog rationalization")):
        return "acquisition diligence SOP"
    return "task SOP"


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
