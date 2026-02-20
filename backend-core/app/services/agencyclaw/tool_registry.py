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
    # C11A: Command Center read-only skills
    "cc_client_lookup": {
        "description": "Search or list agency clients by name.",
        "args": {
            "query": {
                "type": "string",
                "required": False,
                "description": "Client name search query. Omit to list all accessible clients.",
            },
        },
    },
    "cc_brand_list_all": {
        "description": "List brands with their client and ClickUp mapping status.",
        "args": {
            "client_name": {
                "type": "string",
                "required": False,
                "description": "Filter to a specific client. Omit to list all brands.",
            },
        },
    },
    "cc_brand_clickup_mapping_audit": {
        "description": "Audit brands missing ClickUp space or list mappings. Admin only.",
        "args": {},
    },
    # C11E: Brand mapping remediation skills
    "cc_brand_mapping_remediation_preview": {
        "description": "Preview a remediation plan for brands missing ClickUp mappings. Admin only. Shows which brands can be auto-fixed and which are blocked.",
        "args": {
            "client_name": {
                "type": "string",
                "required": False,
                "description": "Filter to a specific client. Omit to scan all brands.",
            },
        },
    },
    "cc_brand_mapping_remediation_apply": {
        "description": "Apply the remediation plan to fix brands missing ClickUp mappings. Admin only. Only updates safe-to-apply items.",
        "args": {
            "client_name": {
                "type": "string",
                "required": False,
                "description": "Filter to a specific client. Omit to apply across all brands.",
            },
        },
    },
    # C12A: Assignment mutation skills
    "cc_assignment_upsert": {
        "description": "Assign or reassign a team member to a client/brand role slot. Admin only. Replaces any existing assignee in that slot.",
        "args": {
            "person_name": {
                "type": "string",
                "required": True,
                "description": "Name of the team member to assign.",
            },
            "role_slug": {
                "type": "string",
                "required": True,
                "description": "Role slug (e.g. ppc_strategist, customer_success_lead).",
            },
            "client_name": {
                "type": "string",
                "required": False,
                "description": "Client name. Omit to use active client.",
            },
            "brand_name": {
                "type": "string",
                "required": False,
                "description": "Brand name for brand-scoped assignment. Omit for client-level.",
            },
        },
    },
    "cc_assignment_remove": {
        "description": "Remove a team member from a client/brand role slot. Admin only.",
        "args": {
            "person_name": {
                "type": "string",
                "required": True,
                "description": "Name of the team member to remove.",
            },
            "role_slug": {
                "type": "string",
                "required": True,
                "description": "Role slug (e.g. ppc_strategist, customer_success_lead).",
            },
            "client_name": {
                "type": "string",
                "required": False,
                "description": "Client name. Omit to use active client.",
            },
            "brand_name": {
                "type": "string",
                "required": False,
                "description": "Brand name for brand-scoped assignment. Omit for client-level.",
            },
        },
    },
    # C12B: Brand CRUD mutation skills
    "cc_brand_create": {
        "description": "Create a new brand under a client. Admin only.",
        "args": {
            "client_name": {
                "type": "string",
                "required": True,
                "description": "Client name (must resolve to a single client).",
            },
            "brand_name": {
                "type": "string",
                "required": True,
                "description": "Name for the new brand.",
            },
            "clickup_space_id": {
                "type": "string",
                "required": False,
                "description": "ClickUp space ID to link to the brand.",
            },
            "clickup_list_id": {
                "type": "string",
                "required": False,
                "description": "ClickUp list ID to link to the brand.",
            },
            "marketplaces": {
                "type": "string",
                "required": False,
                "description": "Comma-separated Amazon marketplace codes (e.g. US,CA,UK).",
            },
        },
    },
    "cc_brand_update": {
        "description": "Update an existing brand's fields. Admin only.",
        "args": {
            "brand_name": {
                "type": "string",
                "required": True,
                "description": "Name of the brand to update (must resolve unambiguously).",
            },
            "client_name": {
                "type": "string",
                "required": False,
                "description": "Client name to scope the brand search. Recommended for disambiguation.",
            },
            "new_brand_name": {
                "type": "string",
                "required": False,
                "description": "Rename the brand to this name.",
            },
            "clickup_space_id": {
                "type": "string",
                "required": False,
                "description": "Set or update the ClickUp space ID.",
            },
            "clickup_list_id": {
                "type": "string",
                "required": False,
                "description": "Set or update the ClickUp list ID.",
            },
            "marketplaces": {
                "type": "string",
                "required": False,
                "description": "Comma-separated Amazon marketplace codes (e.g. US,CA,UK).",
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
