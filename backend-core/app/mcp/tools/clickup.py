"""ClickUp MCP tools — list, inspect, resolve assignees, prepare, and create tasks."""

from __future__ import annotations

import logging
from typing import Any

from ..auth import get_current_pilot_user
from ...services.clickup_task_tools import (
    ClickUpToolError,
    create_task_for_brand,
    get_task_by_id_or_url,
    list_tasks_for_brand,
    prepare_task_for_brand,
    resolve_team_member_matches,
)

_logger = logging.getLogger(__name__)

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 200


def _log_tool_outcome(tool_name: str, outcome: str, **extra: Any) -> None:
    user = get_current_pilot_user()
    suffix = " ".join(f"{key}={value}" for key, value in extra.items())
    if suffix:
        suffix = f" {suffix}"
    _logger.info(
        "MCP tool invocation | tool=%s user_id=%s outcome=%s%s",
        tool_name,
        user.user_id if user else None,
        outcome,
        suffix,
    )


def register_clickup_tools(mcp: Any) -> None:
    @mcp.tool(
        name="list_clickup_tasks",
        description=(
            "List tasks from a resolved brand backlog destination in ClickUp. "
            "Requires client_id (use resolve_client first). Provide brand_id when the "
            "client has multiple brands — omitting it for a multi-brand client fails closed. "
            "Does not fetch subtasks."
        ),
        structured_output=True,
    )
    async def list_clickup_tasks(
        client_id: str,
        brand_id: str | None = None,
        updated_since_days: int = 14,
        include_closed: bool = False,
        limit: int = _DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        _log_tool_outcome("list_clickup_tasks", "started", client_id=client_id)
        effective_limit = max(1, min(limit, _MAX_LIMIT))
        try:
            result = await list_tasks_for_brand(
                client_id=client_id,
                brand_id=brand_id or None,
                updated_since_days=updated_since_days,
                include_closed=include_closed,
                limit=effective_limit,
            )
            _log_tool_outcome(
                "list_clickup_tasks",
                "success",
                client_id=client_id,
                brand_id=result.get("brand_id"),
                task_count=len(result.get("tasks", [])),
            )
            return result
        except ClickUpToolError as exc:
            _log_tool_outcome(
                "list_clickup_tasks", f"error:{exc.error_type}", client_id=client_id
            )
            return {"error": exc.error_type, "message": exc.message}

    @mcp.tool(
        name="get_clickup_task",
        description=(
            "Fetch a single ClickUp task by task ID or URL. "
            "Accepted formats: bare task id, or https://app.clickup.com/t/{task_id}. "
            "Returns structured task data including status, assignees, and list/space metadata. "
            "Note: any valid ClickUp task URL is readable in the current pilot."
        ),
        structured_output=True,
    )
    async def get_clickup_task(
        task_id: str | None = None,
        task_url: str | None = None,
    ) -> dict[str, Any]:
        _log_tool_outcome("get_clickup_task", "started")
        try:
            result = await get_task_by_id_or_url(task_id=task_id, task_url=task_url)
            fetched_id = result.get("task", {}).get("id", "")
            _log_tool_outcome("get_clickup_task", "success", task_id=fetched_id)
            return result
        except ClickUpToolError as exc:
            _log_tool_outcome("get_clickup_task", f"error:{exc.error_type}")
            return {"error": exc.error_type, "message": exc.message}

    @mcp.tool(
        name="resolve_team_member",
        description=(
            "Resolve a natural-language team-member reference to concrete Agency OS profiles. "
            "Use before assigning a task when you have conversational intent like 'assign to Susie'. "
            "Accepts optional client_id/brand_id to improve ranking and reduce ambiguity. "
            "Returns resolution_status per match: resolved (one result with valid ClickUp mapping), "
            "missing_mapping (one result but no clickup_user_id), or ambiguous (multiple results)."
        ),
        structured_output=True,
    )
    async def resolve_team_member(
        query: str,
        client_id: str | None = None,
        brand_id: str | None = None,
    ) -> dict[str, Any]:
        _log_tool_outcome("resolve_team_member", "started", query=query)
        try:
            result = resolve_team_member_matches(
                query=query, client_id=client_id, brand_id=brand_id
            )
            _log_tool_outcome(
                "resolve_team_member",
                "success",
                query=query,
                matches=len(result.get("matches", [])),
            )
            return result
        except ClickUpToolError as exc:
            _log_tool_outcome("resolve_team_member", f"error:{exc.error_type}")
            return {"error": exc.error_type, "message": exc.message}

    @mcp.tool(
        name="prepare_clickup_task",
        description=(
            "Dry-run task creation: resolve the destination and assignee, return the full payload "
            "and any warnings without mutating ClickUp. "
            "Use this before create_clickup_task to preview what would be sent. "
            "Requires client_id (use resolve_client first). "
            "For assignee: provide assignee_query (natural language) or assignee_profile_id "
            "(already resolved). Omit both to preview an unassigned task."
        ),
        structured_output=True,
    )
    async def prepare_clickup_task(
        client_id: str,
        title: str,
        brand_id: str | None = None,
        description_md: str | None = None,
        assignee_profile_id: str | None = None,
        assignee_query: str | None = None,
    ) -> dict[str, Any]:
        _log_tool_outcome("prepare_clickup_task", "started", client_id=client_id)
        try:
            result = await prepare_task_for_brand(
                client_id=client_id,
                brand_id=brand_id or None,
                title=title,
                description_md=description_md,
                assignee_profile_id=assignee_profile_id,
                assignee_query=assignee_query,
            )
            _log_tool_outcome(
                "prepare_clickup_task",
                "success",
                client_id=client_id,
                brand_id=result.get("brand_id"),
                list_id=result.get("destination", {}).get("list_id"),
                assignee_status=result.get("assignee", {}).get("resolution_status"),
                warnings=len(result.get("warnings", [])),
            )
            return result
        except ClickUpToolError as exc:
            _log_tool_outcome(
                "prepare_clickup_task", f"error:{exc.error_type}", client_id=client_id
            )
            return {"error": exc.error_type, "message": exc.message}

    @mcp.tool(
        name="create_clickup_task",
        description=(
            "Create a task in the resolved brand backlog destination in ClickUp. "
            "Requires client_id (use resolve_client first). Provide brand_id when the "
            "client has multiple brands — omitting it for a multi-brand client fails closed. "
            "For assignee: provide assignee_query (natural language) or assignee_profile_id "
            "(already resolved via resolve_team_member). Omit both to create unassigned. "
            "Consider calling prepare_clickup_task first to preview the payload. "
            "v1: duplicate creates are not guarded — do not retry a successful call."
        ),
        structured_output=True,
    )
    async def create_clickup_task(
        client_id: str,
        title: str,
        brand_id: str | None = None,
        description_md: str | None = None,
        assignee_profile_id: str | None = None,
        assignee_query: str | None = None,
    ) -> dict[str, Any]:
        _log_tool_outcome("create_clickup_task", "started", client_id=client_id)
        try:
            result = await create_task_for_brand(
                client_id=client_id,
                brand_id=brand_id or None,
                title=title,
                description_md=description_md,
                assignee_profile_id=assignee_profile_id,
                assignee_query=assignee_query,
            )
            _log_tool_outcome(
                "create_clickup_task",
                "success",
                client_id=client_id,
                brand_id=result.get("brand_id"),
                list_id=result.get("destination", {}).get("list_id"),
                assignee_status=result.get("assignee", {}).get("resolution_status"),
                clickup_task_id=result.get("task_id"),
            )
            return result
        except ClickUpToolError as exc:
            _log_tool_outcome(
                "create_clickup_task", f"error:{exc.error_type}", client_id=client_id
            )
            return {"error": exc.error_type, "message": exc.message}
