"""ClickUp mutation reliability primitives for AgencyClaw.

Provides:
1. Deterministic idempotency key builder
2. Duplicate suppression via ``agent_tasks.source_reference``
3. Retry/backoff wrapper for ClickUp mutations
4. Orphan detection event emitter via ``agent_events``
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, TypedDict, TypeVar

from ..clickup import (
    ClickUpAPIError,
    ClickUpRateLimitError,
    ClickUpTask,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

# ---------------------------------------------------------------------------
# 1) Idempotency key builder
# ---------------------------------------------------------------------------

_MAX_RETRY_ATTEMPTS = 3
_BASE_BACKOFF_S = 1.0


def build_idempotency_key(brand_id: str, title: str, date: datetime | None = None) -> str:
    """Build a deterministic idempotency key for a ClickUp mutation.

    Key = sha256(brand_id + ":" + normalized_title + ":" + yyyy_mm_dd)

    Normalization: trim, lowercase, collapse whitespace.
    """
    normalized_title = " ".join((title or "").strip().lower().split())
    day = (date or datetime.now(timezone.utc)).strftime("%Y_%m_%d")
    raw = f"{brand_id}:{normalized_title}:{day}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 2) Duplicate suppression
# ---------------------------------------------------------------------------


class DuplicateCandidate(TypedDict):
    agent_task_id: str
    clickup_task_id: str | None
    status: str
    created_at: str


def check_duplicate(
    db: Any,
    idempotency_key: str,
    *,
    window_hours: int = 24,
) -> DuplicateCandidate | None:
    """Check ``agent_tasks`` for an existing task with the same idempotency key.

    Searches ``source_reference`` for ``idempotency_key`` within the last
    ``window_hours``.  Returns the first match or ``None``.

    This is a **synchronous** call (Supabase Python client is sync); callers
    should wrap in ``asyncio.to_thread`` when calling from async code.
    """
    if not idempotency_key:
        return None

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()

    response = (
        db.table("agent_tasks")
        .select("id, clickup_task_id, status, created_at")
        .eq("source_reference", idempotency_key)
        .gte("created_at", cutoff)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    rows = response.data if isinstance(response.data, list) else []
    if not rows:
        return None

    row = rows[0]
    return DuplicateCandidate(
        agent_task_id=str(row.get("id") or ""),
        clickup_task_id=row.get("clickup_task_id"),
        status=str(row.get("status") or ""),
        created_at=str(row.get("created_at") or ""),
    )


# ---------------------------------------------------------------------------
# 3) Retry / backoff wrapper
# ---------------------------------------------------------------------------


class RetryExhaustedError(Exception):
    """All retry attempts failed."""

    def __init__(self, attempts: int, last_error: Exception) -> None:
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"All {attempts} attempts failed. Last error: {last_error}")


_RETRYABLE_EXCEPTIONS = (
    ClickUpAPIError,
    ClickUpRateLimitError,
)


async def retry_with_backoff(
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = _MAX_RETRY_ATTEMPTS,
    base_backoff_s: float = _BASE_BACKOFF_S,
    retryable: tuple[type[Exception], ...] = _RETRYABLE_EXCEPTIONS,
) -> T:
    """Execute ``fn`` with exponential backoff on retryable failures.

    Returns the result on success, or raises ``RetryExhaustedError`` after
    ``max_attempts`` failures.  Non-retryable exceptions propagate immediately.
    """
    last_exc: Exception | None = None
    backoff = base_backoff_s

    for attempt in range(1, max_attempts + 1):
        try:
            return await fn()
        except retryable as exc:
            last_exc = exc
            if attempt == max_attempts:
                break
            logger.info(
                "Retry %d/%d after %s: %s",
                attempt,
                max_attempts,
                type(exc).__name__,
                exc,
            )
            await asyncio.sleep(backoff)
            backoff *= 2

    raise RetryExhaustedError(max_attempts, last_exc)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 4) Orphan detection
# ---------------------------------------------------------------------------


def emit_orphan_event(
    db: Any,
    *,
    clickup_task: ClickUpTask | None,
    idempotency_key: str,
    client_id: str | None = None,
    employee_id: str | None = None,
    error: str,
) -> None:
    """Record a ``clickup_orphan`` event in ``agent_events``.

    Called when a ClickUp mutation succeeded externally but the local
    persistence step (e.g. ``agent_tasks`` insert) failed.

    Synchronous — callers should wrap in ``asyncio.to_thread`` from async code.
    """
    payload: dict[str, Any] = {
        "idempotency_key": idempotency_key,
        "error": error,
    }
    if clickup_task:
        payload["clickup_task_id"] = clickup_task.id
        if clickup_task.url:
            payload["clickup_task_url"] = clickup_task.url

    row: dict[str, Any] = {
        "event_type": "clickup_orphan",
        "payload": payload,
    }
    if client_id:
        row["client_id"] = client_id
    if employee_id:
        row["employee_id"] = employee_id

    try:
        db.table("agent_events").insert(row).execute()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to emit orphan event: %s", exc)
