"""Best-effort AI token usage logger.

Writes to ``public.ai_token_usage`` via service-role Supabase client.
Never throws — failures are logged and swallowed so they never block the
response path.
"""

from __future__ import annotations

import logging
from typing import Any

from ..config import settings

logger = logging.getLogger(__name__)


async def log_ai_token_usage(
    *,
    tool: str,
    user_id: str | None = None,
    project_id: str | None = None,
    job_id: str | None = None,
    sku_id: str | None = None,
    stage: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    model: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """Insert a row into ``ai_token_usage``.  Best-effort, never raises."""
    if not settings.usage_logging_enabled:
        return
    if not user_id:
        # ai_token_usage.user_id is NOT NULL; skip silently if actor is unresolved.
        return

    try:
        import asyncio

        from .playbook_session import get_supabase_admin_client

        db = get_supabase_admin_client()

        payload: dict[str, Any] = {"tool": tool}

        payload["user_id"] = user_id
        if project_id is not None:
            payload["project_id"] = project_id
        if job_id is not None:
            payload["job_id"] = job_id
        if sku_id is not None:
            payload["sku_id"] = sku_id
        if stage is not None:
            payload["stage"] = stage
        if prompt_tokens is not None:
            payload["prompt_tokens"] = prompt_tokens
        if completion_tokens is not None:
            payload["completion_tokens"] = completion_tokens
        if total_tokens is not None:
            payload["total_tokens"] = total_tokens
        if model is not None:
            payload["model"] = model
        if meta is not None:
            payload["meta"] = meta

        await asyncio.to_thread(
            lambda: db.table("ai_token_usage").insert(payload).execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to log AI token usage: %s", exc)
