"""ClickUp MCP tool orchestration — destination resolution, URL parsing, task fetch."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from ..auth import _get_supabase_admin_client
from .clickup import (
    ClickUpConfigurationError,
    ClickUpError,
    ClickUpNotFoundError,
    get_clickup_service,
)

_logger = logging.getLogger(__name__)

# Accepted task URL: https://app.clickup.com/t/{task_id}
_CLICKUP_TASK_URL_RE = re.compile(
    r"^https://app\.clickup\.com/t/([A-Za-z0-9_-]+)$"
)


# ---------------------------------------------------------------------------
# Error type
# ---------------------------------------------------------------------------


class ClickUpToolError(Exception):
    """Structured error returned to the MCP tool layer."""

    def __init__(self, error_type: str, message: str) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.message = message


# ---------------------------------------------------------------------------
# URL / task-id parsing
# ---------------------------------------------------------------------------


def parse_clickup_task_id(*, task_id: str | None, task_url: str | None) -> str:
    """Return a bare ClickUp task ID from either a task_id or a task_url.

    Accepted inputs:
      - bare task id (any non-empty string)
      - https://app.clickup.com/t/{task_id}

    Raises ClickUpToolError on invalid or ambiguous input.
    """
    if task_id and task_url:
        raise ClickUpToolError(
            "validation_error",
            "Provide exactly one of task_id or task_url, not both.",
        )
    if not task_id and not task_url:
        raise ClickUpToolError(
            "validation_error",
            "Provide either task_id or task_url.",
        )

    if task_id:
        raw = task_id.strip()
        if not raw:
            raise ClickUpToolError("validation_error", "task_id cannot be empty.")
        return raw

    # Parse from URL
    raw_url = (task_url or "").strip()
    match = _CLICKUP_TASK_URL_RE.match(raw_url)
    if not match:
        raise ClickUpToolError(
            "parse_error",
            f"Unrecognized task URL format: '{raw_url}'. "
            "Accepted format: https://app.clickup.com/t/{{task_id}}",
        )
    return match.group(1)


# ---------------------------------------------------------------------------
# Destination resolution
# ---------------------------------------------------------------------------


def _fetch_brand_rows(db: Any, client_id: str) -> list[dict[str, Any]]:
    """Fetch all brand rows for a client from Command Center."""
    resp = (
        db.table("brands")
        .select("id, client_id, name, clickup_list_id, clickup_space_id")
        .eq("client_id", client_id)
        .execute()
    )
    rows = resp.data if isinstance(resp.data, list) else []
    return [r for r in rows if isinstance(r, dict) and str(r.get("id") or "").strip()]


async def resolve_brand_destination(
    db: Any,
    clickup_service: Any,
    *,
    client_id: str,
    brand_id: str | None,
) -> dict[str, Any]:
    """Resolve the ClickUp list destination for a client/brand pair.

    Resolution order:
      1. If brand_id is provided, use that brand only.
      2. If brand_id is omitted:
         a. Filter to brands that have a ClickUp destination (list_id or space_id).
         b. Use the sole mapped candidate if exactly one exists.
         c. Multiple mapped candidates → fail closed (ambiguous_destination).
         d. No mapped candidates → fail (mapping_error).
         e. No brands at all for the client → fail (not_found).
      3. For the resolved brand:
         a. Prefer clickup_list_id (direct).
         b. Fall back to clickup_space_id: call get_space_lists() directly.
            Do NOT use resolve_default_list_id() — it has a global default_list_id
            shortcut that is not safe for per-brand routing.
         c. No destination → fail with a mapping error.

    Returns a dict: {brand_id, brand_name, list_id, space_id, resolution_basis}
    Raises ClickUpToolError on any failure.
    """
    norm_client_id = (client_id or "").strip()
    norm_brand_id = (brand_id or "").strip() or None

    if not norm_client_id:
        raise ClickUpToolError("validation_error", "client_id is required.")

    all_rows = _fetch_brand_rows(db, norm_client_id)

    if norm_brand_id:
        # Explicit brand_id: find exactly that brand under this client.
        matched = [r for r in all_rows if str(r.get("id") or "").strip() == norm_brand_id]
        if not matched:
            raise ClickUpToolError(
                "not_found",
                f"Brand '{norm_brand_id}' not found under client '{norm_client_id}'.",
            )
        brand = matched[0]
    else:
        # No explicit brand_id: ambiguity is evaluated over mapped candidates only.
        # A brand with neither clickup_list_id nor clickup_space_id is not a candidate.
        if not all_rows:
            raise ClickUpToolError(
                "not_found",
                f"No brands found for client '{norm_client_id}'.",
            )

        def _is_mapped(r: dict[str, Any]) -> bool:
            return bool(
                str(r.get("clickup_list_id") or "").strip()
                or str(r.get("clickup_space_id") or "").strip()
            )

        candidates = [r for r in all_rows if _is_mapped(r)]

        if not candidates:
            raise ClickUpToolError(
                "mapping_error",
                f"No brands for client '{norm_client_id}' have a ClickUp destination configured. "
                "Set clickup_list_id or clickup_space_id in Command Center.",
            )

        if len(candidates) > 1:
            brand_names = ", ".join(
                str(r.get("name") or r.get("id") or "?")
                for r in sorted(candidates, key=lambda r: str(r.get("name") or "").casefold())
            )
            raise ClickUpToolError(
                "ambiguous_destination",
                f"Client has multiple brands with ClickUp destinations: {brand_names}. "
                "Provide brand_id to disambiguate.",
            )

        brand = candidates[0]
    resolved_brand_id = str(brand.get("id") or "").strip()
    brand_name = str(brand.get("name") or "").strip()
    list_id = str(brand.get("clickup_list_id") or "").strip() or None
    space_id = str(brand.get("clickup_space_id") or "").strip() or None

    if list_id:
        return {
            "brand_id": resolved_brand_id,
            "brand_name": brand_name,
            "list_id": list_id,
            "space_id": space_id,
            "resolution_basis": "mapped_list",
        }

    if space_id:
        # Bypass resolve_default_list_id() — it uses a global default_list_id instance
        # variable that overrides the space lookup regardless of which space is passed.
        # Call get_space_lists() directly so we resolve against this specific space.
        try:
            lists = await clickup_service.get_space_lists(space_id)
        except ClickUpError as exc:
            raise ClickUpToolError(
                "clickup_api_error",
                f"Could not fetch lists for space '{space_id}': {exc}",
            ) from exc

        if not lists:
            raise ClickUpToolError(
                "mapping_error",
                f"ClickUp space '{space_id}' has no lists. "
                "Set clickup_list_id on this brand in Command Center.",
            )

        # Prefer a list named "Inbox" (case-insensitive), fall back to first.
        fallback = next(
            (lst for lst in lists if str(lst.get("name") or "").strip().lower() == "inbox"),
            lists[0],
        )
        fallback_list_id = str(fallback.get("id") or "").strip()
        if not fallback_list_id:
            raise ClickUpToolError(
                "clickup_api_error",
                "Space list resolution returned an empty list id.",
            )

        return {
            "brand_id": resolved_brand_id,
            "brand_name": brand_name,
            "list_id": fallback_list_id,
            "space_id": space_id,
            "resolution_basis": "mapped_space_default_list",
        }

    raise ClickUpToolError(
        "mapping_error",
        f"Brand '{brand_name}' has no ClickUp destination configured. "
        "Set clickup_list_id (preferred) or clickup_space_id in Command Center.",
    )


# ---------------------------------------------------------------------------
# Task formatters
# ---------------------------------------------------------------------------


def _extract_status(raw: Any) -> str | None:
    """Normalize ClickUp status — handles both dict and string forms."""
    if isinstance(raw, dict):
        return str(raw.get("status") or "").strip() or None
    return str(raw or "").strip() or None


def _extract_assignee_names(assignees: Any) -> list[str]:
    """Extract display strings from a ClickUp assignees list."""
    if not isinstance(assignees, list):
        return []
    names: list[str] = []
    for a in assignees:
        if not isinstance(a, dict):
            continue
        label = str(a.get("username") or a.get("email") or a.get("id") or "").strip()
        if label:
            names.append(label)
    return names


def _format_task_row(task: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw ClickUp task dict to the list_clickup_tasks row shape."""
    return {
        "id": str(task.get("id") or ""),
        "name": str(task.get("name") or ""),
        "status": _extract_status(task.get("status")),
        "url": task.get("url") or None,
        "assignees": _extract_assignee_names(task.get("assignees")),
        "date_updated": task.get("date_updated") or None,
        "date_created": task.get("date_created") or None,
    }


def _format_full_task(task: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw ClickUp task dict to the get_clickup_task output shape."""
    list_info = task.get("list") or {}
    space_info = task.get("space") or {}
    return {
        "id": str(task.get("id") or ""),
        "name": str(task.get("name") or ""),
        "url": task.get("url") or None,
        "description_md": task.get("description") or None,
        "status": _extract_status(task.get("status")),
        "assignees": _extract_assignee_names(task.get("assignees")),
        "date_created": task.get("date_created") or None,
        "date_updated": task.get("date_updated") or None,
        "list_id": str(list_info.get("id") or "").strip() or None,
        "list_name": str(list_info.get("name") or "").strip() or None,
        "space_id": str(space_info.get("id") or "").strip() or None,
        "space_name": str(space_info.get("name") or "").strip() or None,
    }


# ---------------------------------------------------------------------------
# list_tasks orchestration
# ---------------------------------------------------------------------------


async def list_tasks_for_brand(
    *,
    client_id: str,
    brand_id: str | None,
    updated_since_days: int | None,
    include_closed: bool,
    limit: int,
) -> dict[str, Any]:
    """Resolve destination and fetch tasks for a brand backlog.

    - updated_since_days is interpreted relative to UTC now.
    - limit is a hard cap on both tasks returned and pagination depth.

    Raises ClickUpToolError on resolution or API failure.
    """
    try:
        clickup = get_clickup_service()
    except ClickUpConfigurationError as exc:
        raise ClickUpToolError("configuration_error", str(exc)) from exc

    try:
        db = _get_supabase_admin_client()
        destination = await resolve_brand_destination(
            db, clickup, client_id=client_id, brand_id=brand_id
        )

        # Convert updated_since_days to epoch milliseconds in UTC.
        date_updated_gt: int | None = None
        if updated_since_days and updated_since_days > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=updated_since_days)
            date_updated_gt = int(cutoff.timestamp() * 1000)

        # limit caps both the returned count and how far pagination goes.
        try:
            tasks = await clickup.get_tasks_in_list_all_pages(
                destination["list_id"],
                date_updated_gt=date_updated_gt,
                include_closed=include_closed,
                max_tasks=limit,
            )
        except ClickUpError as exc:
            raise ClickUpToolError("clickup_api_error", str(exc)) from exc

        return {
            "client_id": client_id,
            "brand_id": destination["brand_id"],
            "brand_name": destination["brand_name"],
            "destination": {
                "space_id": destination["space_id"],
                "list_id": destination["list_id"],
                "resolution_basis": destination["resolution_basis"],
            },
            "tasks": [_format_task_row(t) for t in tasks],
        }
    finally:
        try:
            await clickup.aclose()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# get_task orchestration
# ---------------------------------------------------------------------------


async def get_task_by_id_or_url(
    *,
    task_id: str | None,
    task_url: str | None,
) -> dict[str, Any]:
    """Parse a task id/URL and fetch the task from ClickUp.

    Raises ClickUpToolError on parse, config, or API failure.
    """
    parsed_id = parse_clickup_task_id(task_id=task_id, task_url=task_url)

    try:
        clickup = get_clickup_service()
    except ClickUpConfigurationError as exc:
        raise ClickUpToolError("configuration_error", str(exc)) from exc

    try:
        raw = await clickup.get_task(parsed_id)
    except ClickUpNotFoundError:
        raise ClickUpToolError(
            "not_found",
            f"ClickUp task '{parsed_id}' was not found.",
        )
    except ClickUpError as exc:
        raise ClickUpToolError("clickup_api_error", str(exc))
    finally:
        try:
            await clickup.aclose()
        except Exception:
            pass

    return {"task": _format_full_task(raw)}
