"""Tool definitions and execution handlers for Claw skills.

Skills can register tools here so the runtime can offer them to the LLM
via OpenAI function calling.  The LLM decides when to call a tool — the
runtime just executes it and feeds the result back.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Literal, TypedDict

ToolOutcome = Literal[
    "read_only_success",
    "read_only_miss",
    "mutation_executed",
    "mutation_not_executed",
    "tool_error",
]


class ToolCallResult(TypedDict):
    """Structured result from a skill tool execution.

    *content* is the JSON string the LLM sees.
    *outcome* tells the runtime what actually happened so it can build
    accurate execution-state grounding.
    """

    content: str
    outcome: ToolOutcome

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# WBR lookup tool
# ---------------------------------------------------------------------------

_WBR_LOOKUP_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "lookup_wbr",
        "description": (
            "Look up the Weekly Business Review (WBR) snapshot for a concrete "
            "client and marketplace pair. Use this after you have chosen the "
            "best matching canonical client name. This is not the fuzzy "
            "discovery step. Returns the WBR digest with key metrics on "
            "success, or a miss/error object if the combination is not found."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "client": {
                    "type": "string",
                    "description": "The client name (e.g. 'Whoosh', 'Acme').",
                },
                "marketplace": {
                    "type": "string",
                    "description": "The marketplace code (e.g. 'US', 'CA', 'UK', 'MX').",
                },
            },
            "required": ["client", "marketplace"],
        },
    },
}

_WBR_LIST_PROFILES_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "list_wbr_profiles",
        "description": (
            "List the configured WBR client/marketplace profiles so you can "
            "resolve the best matching canonical client name and marketplace "
            "before calling lookup_wbr. Use this when the user gives a short, "
            "partial, abbreviated, or uncertain client name, or when a prior "
            "lookup_wbr call misses."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
}


async def _handle_lookup_wbr(arguments: dict[str, Any]) -> dict[str, Any]:
    from .wbr_skill_bridge import lookup_wbr_digest

    client = str(arguments.get("client") or "").strip()
    marketplace = str(arguments.get("marketplace") or "").strip().upper()
    if not client or not marketplace:
        return {"error": "Both client and marketplace are required."}
    return await asyncio.to_thread(lookup_wbr_digest, client, marketplace)


async def _handle_list_wbr_profiles(arguments: dict[str, Any]) -> dict[str, Any]:
    from .wbr_skill_bridge import list_wbr_profiles

    return await asyncio.to_thread(list_wbr_profiles)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_ToolHandler = Any  # Callable[[dict], Awaitable[dict]]

_SKILL_TOOLS: dict[str, dict[str, Any]] = {
    "wbr_summary": {
        "definitions": [_WBR_LOOKUP_TOOL, _WBR_LIST_PROFILES_TOOL],
        "handlers": {
            "lookup_wbr": _handle_lookup_wbr,
            "list_wbr_profiles": _handle_list_wbr_profiles,
        },
        "mutates": {"lookup_wbr": False, "list_wbr_profiles": False},
    },
}


def get_skill_tool_definitions(skill_id: str) -> list[dict[str, Any]] | None:
    """Return OpenAI tool definitions for *skill_id*, or None."""
    entry = _SKILL_TOOLS.get(skill_id)
    return list(entry["definitions"]) if entry else None


def tool_mutates(skill_id: str, tool_name: str) -> bool:
    """Return True if *tool_name* may modify external systems.

    Defaults to True (conservative) for undeclared tools so that unknown
    tools are never falsely labeled read-only.
    """
    entry = _SKILL_TOOLS.get(skill_id)
    if not entry:
        return True
    return bool(entry.get("mutates", {}).get(tool_name, True))


async def execute_skill_tool_call(
    *,
    skill_id: str,
    tool_name: str,
    arguments_json: str,
) -> ToolCallResult:
    """Execute a tool call and return structured result with outcome metadata.

    The *content* field is the JSON string the LLM sees (unchanged from
    before).  The *outcome* field tells the runtime what actually happened
    so it can build accurate execution-state grounding notes.
    """
    entry = _SKILL_TOOLS.get(skill_id)
    if not entry:
        return ToolCallResult(
            content=json.dumps({"error": f"No tools registered for skill '{skill_id}'"}),
            outcome="tool_error",
        )

    handler = entry["handlers"].get(tool_name)
    if not handler:
        return ToolCallResult(
            content=json.dumps({"error": f"Unknown tool '{tool_name}'"}),
            outcome="tool_error",
        )

    try:
        args = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError:
        args = {}

    safe_args = {}
    for k in ("client", "marketplace", "skill_id", "tool_name", "action", "status"):
        if k in args:
            safe_args[k] = str(args[k])[:50]
    arg_summary = ", ".join(f"{k}='{v}'" for k, v in safe_args.items())
    keys_present = ",".join(args.keys())

    _logger.info(f"The Claw executing tool | skill_id={skill_id} tool_name={tool_name} keys=[{keys_present}] safe_args=[{arg_summary}]")

    try:
        result = await handler(args)
    except Exception as exc:  # noqa: BLE001
        _logger.warning(f"Skill tool '{tool_name}' failed: {exc} | skill_id={skill_id}")
        return ToolCallResult(
            content=json.dumps({"error": f"Tool execution failed: {exc}"}),
            outcome="tool_error",
        )

    content = json.dumps(result, default=str, ensure_ascii=True)
    mutates = bool(entry.get("mutates", {}).get(tool_name, True))
    is_error_result = isinstance(result, dict) and "error" in result
    is_miss_result = isinstance(result, dict) and result.get("status") in {"no_profile", "no_data"}

    if is_error_result:
        outcome: ToolOutcome = "mutation_not_executed" if mutates else "tool_error"
    elif is_miss_result and not mutates:
        outcome: ToolOutcome = "read_only_miss"
    elif not mutates:
        outcome = "read_only_success"
    else:
        outcome = "mutation_executed"

    if isinstance(result, dict):
        status_val = str(result.get("status", ""))
        version_val = str(result.get("digest_version", ""))
        res_summary = ""
        if status_val:
            res_summary += f"status='{status_val}' "
        if version_val:
            res_summary += f"version='{version_val}'"
        res_keys = ",".join(result.keys())
    else:
        res_summary = f"type='{type(result).__name__}'"
        res_keys = ""

    _logger.info(
        f"The Claw tool execution completed | skill_id={skill_id} tool_name={tool_name} outcome={outcome} keys=[{res_keys}] result_summary=[{res_summary.strip()}]"
    )

    return ToolCallResult(content=content, outcome=outcome)
