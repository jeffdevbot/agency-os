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
            "Look up the Weekly Business Review (WBR) snapshot for a client "
            "and marketplace.  Returns the WBR digest with key metrics on "
            "success, or an error object if the combination is not found."
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


async def _handle_lookup_wbr(arguments: dict[str, Any]) -> dict[str, Any]:
    from .wbr_skill_bridge import lookup_wbr_digest

    client = str(arguments.get("client") or "").strip()
    marketplace = str(arguments.get("marketplace") or "").strip()
    if not client or not marketplace:
        return {"error": "Both client and marketplace are required."}
    return await asyncio.to_thread(lookup_wbr_digest, client, marketplace)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_ToolHandler = Any  # Callable[[dict], Awaitable[dict]]

_SKILL_TOOLS: dict[str, dict[str, Any]] = {
    "wbr_summary": {
        "definitions": [_WBR_LOOKUP_TOOL],
        "handlers": {"lookup_wbr": _handle_lookup_wbr},
        "mutates": {"lookup_wbr": False},
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

    try:
        result = await handler(args)
    except Exception as exc:  # noqa: BLE001
        _logger.warning("Skill tool '%s' failed: %s", tool_name, exc)
        return ToolCallResult(
            content=json.dumps({"error": f"Tool execution failed: {exc}"}),
            outcome="tool_error",
        )

    content = json.dumps(result, default=str, ensure_ascii=True)
    mutates = bool(entry.get("mutates", {}).get(tool_name, True))
    is_error_result = isinstance(result, dict) and "error" in result

    if is_error_result:
        outcome: ToolOutcome = "mutation_not_executed" if mutates else "tool_error"
    elif not mutates:
        outcome = "read_only_success"
    else:
        outcome = "mutation_executed"

    return ToolCallResult(content=content, outcome=outcome)
