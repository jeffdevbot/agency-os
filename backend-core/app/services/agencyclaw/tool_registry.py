"""Tool skill schemas and validation for AgencyClaw orchestrator."""

from __future__ import annotations

from typing import Any, TypedDict


class ArgSchema(TypedDict):
    type: str
    required: bool
    description: str


class ToolSchema(TypedDict):
    description: str
    args: dict[str, ArgSchema]


TOOL_SCHEMAS: dict[str, ToolSchema] = {
    "clickup_task_list_weekly": {
        "description": "List ClickUp tasks updated this week for a client.",
        "args": {
            "client_name": {
                "type": "string",
                "required": False,
                "description": "Client name hint (fuzzy match). Omit to use active client.",
            },
        },
    },
    "clickup_task_create": {
        "description": "Create a new ClickUp task for a client.",
        "args": {
            "client_name": {
                "type": "string",
                "required": False,
                "description": "Client name hint. Omit to use active client.",
            },
            "task_title": {
                "type": "string",
                "required": True,
                "description": "Title for the new task.",
            },
            "task_description": {
                "type": "string",
                "required": False,
                "description": "Optional description or details for the task.",
            },
        },
    },
    "ngram_research": {
        "description": "Create an N-gram keyword research task for a client using the SOP.",
        "args": {
            "client_name": {
                "type": "string",
                "required": False,
                "description": "Client name. Omit to use active client.",
            },
        },
    },
}


def validate_tool_call(skill_id: str, args: dict[str, Any]) -> list[str]:
    """Validate a tool call against its schema.

    Returns a list of validation errors (empty list means valid).
    """
    errors: list[str] = []

    schema = TOOL_SCHEMAS.get(skill_id)
    if schema is None:
        errors.append(f"Unknown skill: {skill_id}")
        return errors

    arg_schemas = schema["args"]

    for arg_name, arg_def in arg_schemas.items():
        value = args.get(arg_name)
        if arg_def["required"]:
            if value is None or (isinstance(value, str) and not value.strip()):
                errors.append(f"Missing required argument: {arg_name}")
                continue
        if value is not None and arg_def["type"] == "string" and not isinstance(value, str):
            errors.append(f"Argument {arg_name} must be a string, got {type(value).__name__}")

    # Flag any unknown args
    known = set(arg_schemas.keys())
    for key in args:
        if key not in known:
            errors.append(f"Unknown argument: {key}")

    return errors


def get_missing_required_fields(skill_id: str, args: dict[str, Any]) -> list[str]:
    """Return names of required fields that are missing or empty."""
    schema = TOOL_SCHEMAS.get(skill_id)
    if schema is None:
        return []

    missing: list[str] = []
    for arg_name, arg_def in schema["args"].items():
        if not arg_def["required"]:
            continue
        value = args.get(arg_name)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(arg_name)
    return missing


def get_tool_descriptions_for_prompt() -> str:
    """Format tool schemas into a text block for the LLM system prompt."""
    lines: list[str] = []
    for skill_id, schema in TOOL_SCHEMAS.items():
        lines.append(f"### {skill_id}")
        lines.append(schema["description"])
        lines.append("Arguments:")
        for arg_name, arg_def in schema["args"].items():
            req = "REQUIRED" if arg_def["required"] else "optional"
            lines.append(f"  - {arg_name} ({arg_def['type']}, {req}): {arg_def['description']}")
        lines.append("")
    return "\n".join(lines)
