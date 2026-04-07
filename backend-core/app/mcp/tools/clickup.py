"""ClickUp MCP tools — list, inspect, resolve assignees, prepare, create, and update tasks."""

from __future__ import annotations

from typing import Any

from ...services.clickup_task_tools import (
    ClickUpToolError,
    create_task_for_brand,
    get_task_by_id_or_url,
    list_tasks_for_brand,
    prepare_task_for_brand,
    resolve_team_member_matches,
    update_task_by_id_or_url,
)
from ..event_logging import start_mcp_tool_invocation

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 200


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
        invocation = start_mcp_tool_invocation("list_clickup_tasks", is_mutation=False)
        effective_limit = max(1, min(limit, _MAX_LIMIT))
        try:
            result = await list_tasks_for_brand(
                client_id=client_id,
                brand_id=brand_id or None,
                updated_since_days=updated_since_days,
                include_closed=include_closed,
                limit=effective_limit,
            )
            invocation.success(
                client_id=client_id,
                brand_id=result.get("brand_id"),
                task_count=len(result.get("tasks", [])),
                include_closed=include_closed,
                limit=effective_limit,
            )
            return result
        except ClickUpToolError as exc:
            invocation.error(
                error_type=exc.error_type,
                client_id=client_id,
                include_closed=include_closed,
                limit=effective_limit,
            )
            return {"error": exc.error_type, "message": exc.message}

    @mcp.tool(
        name="get_clickup_task",
        description=(
            "Fetch a single ClickUp task by task ID or URL. "
            "Accepted formats: bare task id, or https://app.clickup.com/t/{task_id}. "
            "Returns structured task data including status, assignees, and list/space metadata. "
            "Only tasks in mapped Agency OS brand destinations may be fetched."
        ),
        structured_output=True,
    )
    async def get_clickup_task(
        task_id: str | None = None,
        task_url: str | None = None,
    ) -> dict[str, Any]:
        invocation = start_mcp_tool_invocation("get_clickup_task", is_mutation=False)
        try:
            result = await get_task_by_id_or_url(task_id=task_id, task_url=task_url)
            fetched_id = result.get("task", {}).get("id", "")
            invocation.success(task_id=fetched_id)
            return result
        except ClickUpToolError as exc:
            invocation.error(error_type=exc.error_type)
            return {"error": exc.error_type, "message": exc.message}

    @mcp.tool(
        name="update_clickup_task",
        description=(
            "Update an existing ClickUp task by task ID or URL. "
            "Accepted task inputs: bare task id, or https://app.clickup.com/t/{task_id}. "
            "Only tasks in mapped Agency OS brand destinations may be updated. "
            "You may update title, description, or assignee. "
            "For assignee: provide assignee_query (natural language) or assignee_profile_id. "
            "Set clear_assignees=true to remove assignees."
        ),
        structured_output=True,
    )
    async def update_clickup_task(
        task_id: str | None = None,
        task_url: str | None = None,
        title: str | None = None,
        description_md: str | None = None,
        assignee_profile_id: str | None = None,
        assignee_query: str | None = None,
        clear_assignees: bool = False,
        client_id: str | None = None,
        brand_id: str | None = None,
    ) -> dict[str, Any]:
        invocation = start_mcp_tool_invocation("update_clickup_task", is_mutation=True)
        try:
            result = await update_task_by_id_or_url(
                task_id=task_id,
                task_url=task_url,
                title=title,
                description_md=description_md,
                assignee_profile_id=assignee_profile_id,
                assignee_query=assignee_query,
                clear_assignees=clear_assignees,
                client_id=client_id,
                brand_id=brand_id,
            )
            invocation.success(
                task_id=result.get("task", {}).get("id"),
                assignee_status=result.get("assignee", {}).get("resolution_status"),
                client_id=client_id,
                brand_id=brand_id,
            )
            return result
        except ClickUpToolError as exc:
            invocation.error(error_type=exc.error_type, client_id=client_id, brand_id=brand_id)
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
        invocation = start_mcp_tool_invocation("resolve_team_member", is_mutation=False)
        try:
            result = resolve_team_member_matches(
                query=query, client_id=client_id, brand_id=brand_id
            )
            invocation.success(
                client_id=client_id,
                brand_id=brand_id,
                query_length=len(str(query or "").strip()),
                match_count=len(result.get("matches", [])),
            )
            return result
        except ClickUpToolError as exc:
            invocation.error(
                error_type=exc.error_type,
                client_id=client_id,
                brand_id=brand_id,
                query_length=len(str(query or "").strip()),
            )
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
        invocation = start_mcp_tool_invocation("prepare_clickup_task", is_mutation=False)
        try:
            result = await prepare_task_for_brand(
                client_id=client_id,
                brand_id=brand_id or None,
                title=title,
                description_md=description_md,
                assignee_profile_id=assignee_profile_id,
                assignee_query=assignee_query,
            )
            invocation.success(
                client_id=client_id,
                brand_id=result.get("brand_id"),
                list_id=result.get("destination", {}).get("list_id"),
                assignee_status=result.get("assignee", {}).get("resolution_status"),
                warning_count=len(result.get("warnings", [])),
            )
            return result
        except ClickUpToolError as exc:
            invocation.error(
                error_type=exc.error_type,
                client_id=client_id,
                brand_id=brand_id,
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
        invocation = start_mcp_tool_invocation("create_clickup_task", is_mutation=True)
        try:
            result = await create_task_for_brand(
                client_id=client_id,
                brand_id=brand_id or None,
                title=title,
                description_md=description_md,
                assignee_profile_id=assignee_profile_id,
                assignee_query=assignee_query,
            )
            invocation.success(
                client_id=client_id,
                brand_id=result.get("brand_id"),
                list_id=result.get("destination", {}).get("list_id"),
                assignee_status=result.get("assignee", {}).get("resolution_status"),
                clickup_task_id=result.get("task_id"),
            )
            return result
        except ClickUpToolError as exc:
            invocation.error(
                error_type=exc.error_type,
                client_id=client_id,
                brand_id=brand_id,
            )
            return {"error": exc.error_type, "message": exc.message}
