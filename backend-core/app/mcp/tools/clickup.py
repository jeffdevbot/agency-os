"""ClickUp read-only MCP tools — list tasks and inspect a specific task."""

from __future__ import annotations

import logging
from typing import Any

from ..auth import get_current_pilot_user
from ...services.clickup_task_tools import (
    ClickUpToolError,
    get_task_by_id_or_url,
    list_tasks_for_brand,
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
