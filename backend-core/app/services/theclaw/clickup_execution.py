"""ClickUp task execution helpers for The Claw Phase 3.

Handles one-at-a-time confirmed task creation with fail-closed behavior
and idempotency via draft task status + clickup_task_id linkage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from ..clickup import (
    ClickUpError,
    get_clickup_service,
)
from .runtime_state import (
    SESSION_DRAFT_TASKS_KEY,
    SESSION_PENDING_CONFIRMATION_KEY,
    draft_tasks_from_session_context,
    resolved_context_from_session_context,
    sanitize_context_field,
)

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClickUpExecutionResult:
    """Structured result from a ClickUp task creation attempt."""

    success: bool
    clickup_task_id: str | None = None
    clickup_task_url: str | None = None
    error_message: str | None = None
    already_sent: bool = False


def _find_draft_task_by_id(
    *,
    draft_tasks: list[dict[str, Any]],
    task_id: str,
) -> dict[str, Any] | None:
    target = task_id.strip()
    if not target:
        return None
    for task in draft_tasks:
        if str(task.get("id") or "").strip() == target:
            return task
    return None


@dataclass(frozen=True)
class _ResolvedDestination:
    """Resolved ClickUp destination — either a list_id (direct) or space_id."""

    list_id: str | None = None
    space_id: str | None = None


async def _resolve_destination(
    *,
    clickup_service,
    pending: dict[str, Any],
    resolved_ctx: dict[str, Any] | None,
) -> _ResolvedDestination:
    # 1. Direct list_id — skip space resolution entirely.
    list_id = sanitize_context_field(pending.get("clickup_list_id"))
    if list_id:
        return _ResolvedDestination(list_id=list_id)

    # 2. Direct space_id from pending confirmation.
    space_id = sanitize_context_field(pending.get("clickup_space_id"))
    if space_id:
        return _ResolvedDestination(space_id=space_id)

    # 3. Resolve space name → ID via ClickUp API.
    space_name = sanitize_context_field(pending.get("clickup_space"))
    if not space_name and resolved_ctx:
        space_name = sanitize_context_field(resolved_ctx.get("clickup_space"))

    if space_name:
        spaces = await clickup_service.list_spaces()
        target = space_name.strip().lower()
        for space in spaces:
            if str(space.get("name", "")).strip().lower() == target:
                return _ResolvedDestination(space_id=str(space["id"]))

    return _ResolvedDestination()


def _build_task_description_md(task: dict[str, Any]) -> str:
    parts: list[str] = []
    if task.get("description"):
        parts.append(str(task["description"]))

    details: list[str] = []
    if task.get("marketplace"):
        details.append(f"**Marketplace:** {task['marketplace']}")
    if task.get("type"):
        details.append(f"**Type:** {task['type']}")
    if task.get("action"):
        details.append(f"**Action:** {task['action']}")
    if task.get("specifics"):
        details.append(f"**Specifics:** {task['specifics']}")
    if task.get("target_metric"):
        details.append(f"**Target Metric:** {task['target_metric']}")
    if task.get("start_date"):
        details.append(f"**Start Date:** {task['start_date']}")
    if task.get("deadline"):
        details.append(f"**Deadline:** {task['deadline']}")
    if task.get("asin_list"):
        asins = [str(a) for a in task["asin_list"] if a]
        if asins:
            details.append(f"**ASINs:** {', '.join(asins)}")
    if task.get("coupon_window") and str(task["coupon_window"]).strip().lower() != "n/a":
        details.append(f"**Coupon Window:** {task['coupon_window']}")
    if task.get("reference_docs") and str(task["reference_docs"]).strip().lower() != "n/a":
        details.append(f"**Reference Docs:** {task['reference_docs']}")
    if task.get("source"):
        details.append(f"**Source:** {task['source']}")

    if details:
        if parts:
            parts.append("")
        parts.extend(details)

    parts.append("")
    parts.append("*Created by The Claw*")
    return "\n".join(parts)


async def execute_confirmed_task_creation(
    *,
    session_context: dict[str, Any],
    pending_confirmation: dict[str, Any],
) -> tuple[ClickUpExecutionResult, dict[str, Any]]:
    """Execute ClickUp task creation for a confirmed pending task.

    Returns ``(result, state_updates)`` where *state_updates* should be
    merged into session context by the caller.

    Failure policy:
    - Config errors (missing env vars): keep pending state so user can fix
      config and retry.
    - Transient API errors (timeout, 5xx, rate limit): keep pending state
      for retry — user can say "yes" again.
    - Missing draft task or missing destination: clear pending state because
      retrying the same confirmation cannot succeed; user must re-stage.
    """
    task_id = sanitize_context_field(pending_confirmation.get("task_id"))
    if not task_id:
        return (
            ClickUpExecutionResult(
                success=False,
                error_message="No task ID in pending confirmation. Please re-stage the task.",
            ),
            {SESSION_PENDING_CONFIRMATION_KEY: None},
        )

    draft_tasks = draft_tasks_from_session_context(session_context)
    target_task = _find_draft_task_by_id(draft_tasks=draft_tasks, task_id=task_id)
    if target_task is None:
        return (
            ClickUpExecutionResult(
                success=False,
                error_message=f"Draft task '{task_id}' not found in session. It may have been removed. Please re-stage.",
            ),
            {SESSION_PENDING_CONFIRMATION_KEY: None},
        )

    # Idempotency: task already sent with a ClickUp ID — do not create again.
    if (
        str(target_task.get("status") or "").lower() == "sent"
        and target_task.get("clickup_task_id")
    ):
        existing_url = target_task.get("clickup_task_url")
        return (
            ClickUpExecutionResult(
                success=True,
                clickup_task_id=str(target_task["clickup_task_id"]),
                clickup_task_url=str(existing_url) if existing_url else None,
                already_sent=True,
            ),
            {SESSION_PENDING_CONFIRMATION_KEY: None},
        )

    # Acquire ClickUp service.
    try:
        clickup = get_clickup_service()
    except Exception as exc:  # noqa: BLE001
        # Catches ClickUpConfigurationError, ValueError from bad env, etc.
        _logger.warning("The Claw ClickUp service init failed: %s", exc)
        return (
            ClickUpExecutionResult(
                success=False,
                error_message=f"ClickUp is not configured: {exc}",
            ),
            {},  # Keep pending — config issue is fixable without re-staging.
        )

    try:
        # Resolve destination (list_id > space_id > space name lookup).
        resolved_ctx = resolved_context_from_session_context(session_context)
        destination = await _resolve_destination(
            clickup_service=clickup,
            pending=pending_confirmation,
            resolved_ctx=resolved_ctx,
        )
        if not destination.list_id and not destination.space_id:
            return (
                ClickUpExecutionResult(
                    success=False,
                    error_message=(
                        "No ClickUp destination could be resolved. "
                        "Set a client/space context first, then re-stage the task."
                    ),
                ),
                # Clear pending — retrying won't help without a context change.
                {SESSION_PENDING_CONFIRMATION_KEY: None},
            )

        # Create the task.
        task_name = str(target_task.get("title") or "Untitled Task").strip()
        description_md = _build_task_description_md(target_task)
        if destination.list_id:
            created = await clickup.create_task_in_list(
                list_id=destination.list_id,
                name=task_name,
                description_md=description_md,
            )
        else:
            created = await clickup.create_task_in_space(
                space_id=destination.space_id,
                name=task_name,
                description_md=description_md,
            )
    except ClickUpError as exc:
        _logger.warning("The Claw ClickUp task creation failed: %s", exc)
        return (
            ClickUpExecutionResult(
                success=False,
                error_message=f"ClickUp task creation failed: {exc}. Say 'yes' to retry.",
            ),
            {},  # Keep pending intact for retry.
        )
    except Exception as exc:  # noqa: BLE001
        # Catch-all for unexpected errors (e.g., httpx bugs, encoding issues).
        _logger.exception("The Claw ClickUp execution unexpected error: %s", exc)
        return (
            ClickUpExecutionResult(
                success=False,
                error_message="An unexpected error occurred during ClickUp task creation. Say 'yes' to retry.",
            ),
            {},  # Keep pending for retry.
        )
    finally:
        try:
            await clickup.aclose()
        except Exception:  # noqa: BLE001
            pass

    # Success: mark draft task as sent with ClickUp linkage.
    updated_tasks: list[dict[str, Any]] = []
    for task in draft_tasks:
        task_copy = dict(task)
        if str(task_copy.get("id") or "").strip() == task_id.strip():
            task_copy["status"] = "sent"
            task_copy["clickup_task_id"] = created.id
            if created.url:
                task_copy["clickup_task_url"] = created.url
        updated_tasks.append(task_copy)

    state_updates: dict[str, Any] = {
        SESSION_PENDING_CONFIRMATION_KEY: None,
        SESSION_DRAFT_TASKS_KEY: updated_tasks,
    }
    return (
        ClickUpExecutionResult(
            success=True,
            clickup_task_id=created.id,
            clickup_task_url=created.url,
        ),
        state_updates,
    )
