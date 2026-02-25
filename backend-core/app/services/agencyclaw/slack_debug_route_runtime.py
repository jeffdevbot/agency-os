"""Runtime helper for the /api/slack/debug/chat route."""

from __future__ import annotations

import asyncio
import os
import secrets
from typing import Any

from fastapi import HTTPException, Request

from .debug_chat import handle_debug_chat
from .slack_route_runtime import SlackRouteRuntimeDeps


async def handle_debug_chat_route_runtime(
    *,
    request: Request,
    deps: SlackRouteRuntimeDeps,
) -> dict[str, Any]:
    """Validate debug-route guards/payload and execute debug chat runtime."""
    enabled = os.environ.get("AGENCYCLAW_DEBUG_CHAT_ENABLED", "").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        raise HTTPException(status_code=404, detail="Not found")

    token = os.environ.get("AGENCYCLAW_DEBUG_CHAT_TOKEN", "").strip()
    header_token = request.headers.get("X-Debug-Token") or ""
    if not token or not secrets.compare_digest(token, header_token):
        raise HTTPException(status_code=401, detail="Unauthorized")

    body = await request.json()
    text = str(body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    if len(text) > 2000:
        raise HTTPException(status_code=400, detail="text exceeds 2000 char limit")

    user_id_override = os.environ.get("AGENCYCLAW_DEBUG_CHAT_USER_ID", "").strip()
    user_id = user_id_override or str(body.get("user_id") or "U_DEBUG_TERMINAL").strip()
    reset_session = bool(body.get("reset_session"))
    if reset_session:
        session_service = deps.get_session_service_fn()
        clear_fn = getattr(session_service, "clear_active_session", None)
        if not callable(clear_fn):
            raise HTTPException(status_code=500, detail="reset_session is not supported by session service")
        try:
            await asyncio.to_thread(clear_fn, user_id)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail="failed to reset debug session") from exc
    allow_mutations = os.environ.get(
        "AGENCYCLAW_DEBUG_CHAT_ALLOW_MUTATIONS", "false"
    ).strip().lower() in {"1", "true", "yes", "on"}

    return await handle_debug_chat(
        text=text,
        deps=deps,
        user_id=user_id,
        allow_mutations=allow_mutations,
    )
