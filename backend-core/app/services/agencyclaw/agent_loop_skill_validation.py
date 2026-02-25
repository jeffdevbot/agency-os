"""Skill ID canonicalization and argument validation for agent loop runtime."""

from __future__ import annotations

import re
from typing import Any

REHYDRATION_KEY_PATTERN = re.compile(r"^ev:[^/\s]+(?:/[^/\s]+)?$")

SKILL_ID_ALIASES = {
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


def canonical_skill_id(skill_id: str) -> str:
    normalized = (skill_id or "").strip()
    return SKILL_ID_ALIASES.get(normalized, normalized)


def validate_task_list_args(args: dict[str, Any]) -> dict[str, Any]:
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


def validate_task_create_args(args: dict[str, Any]) -> dict[str, Any]:
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


def validate_read_skill_args(skill_id: str, args: dict[str, Any], *, read_only_skills: set[str]) -> dict[str, Any]:
    if skill_id in {"clickup_task_list", "clickup_task_list_weekly"}:
        return validate_task_list_args(args)
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
        if not REHYDRATION_KEY_PATTERN.match(evidence_key):
            raise ValueError("invalid evidence key format")
        return {"key": evidence_key}
    if skill_id not in read_only_skills:
        raise ValueError(f"disallowed read skill: {skill_id}")
    raise ValueError(f"unsupported read skill: {skill_id}")


def validate_delegate_planner_args(args: dict[str, Any]) -> dict[str, Any]:
    allowed = {"request_text"}
    for key in args:
        if key not in allowed:
            raise ValueError(f"unsupported arg: {key}")
    request_text = str(args.get("request_text") or "").strip()
    return {"request_text": request_text} if request_text else {}

