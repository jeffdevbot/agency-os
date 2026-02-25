"""HTTP route runtime helpers for The Claw Slack endpoints."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import BackgroundTasks, HTTPException, Request

from ..slack import get_slack_signing_secret
from .slack_route_helpers import (
    parse_interaction_payload,
    parse_json_payload,
    verify_request_or_401,
)


async def handle_slack_events_http_runtime(
    *,
    request: Request,
    background_tasks: BackgroundTasks,
    handle_dm_event_fn: Callable[..., Awaitable[None]],
) -> dict[str, Any]:
    signing_secret = get_slack_signing_secret().strip()
    if not signing_secret:
        raise HTTPException(status_code=500, detail="SLACK_SIGNING_SECRET not set")

    body = await request.body()
    verify_request_or_401(signing_secret=signing_secret, request=request, body=body)

    if request.headers.get("X-Slack-Retry-Num"):
        return {"ok": True}

    payload = parse_json_payload(body)
    if payload.get("type") == "url_verification":
        challenge = payload.get("challenge")
        if not isinstance(challenge, str) or not challenge:
            raise HTTPException(status_code=400, detail="Missing Slack challenge")
        return {"challenge": challenge}

    if payload.get("type") == "event_callback":
        event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
        if (
            event.get("type") == "message"
            and event.get("channel_type") == "im"
            and not event.get("bot_id")
            and not event.get("subtype")
        ):
            channel = str(event.get("channel") or "").strip()
            text = str(event.get("text") or "")
            slack_user_id = str(event.get("user") or "").strip()
            if channel and text and slack_user_id:
                background_tasks.add_task(
                    handle_dm_event_fn,
                    slack_user_id=slack_user_id,
                    channel=channel,
                    text=text,
                )

    return {"ok": True}


async def handle_slack_interactions_http_runtime(
    *,
    request: Request,
    background_tasks: BackgroundTasks,
    handle_interaction_fn: Callable[[dict[str, Any]], Awaitable[None]],
) -> dict[str, Any]:
    signing_secret = get_slack_signing_secret().strip()
    if not signing_secret:
        raise HTTPException(status_code=500, detail="SLACK_SIGNING_SECRET not set")

    body = await request.body()
    verify_request_or_401(signing_secret=signing_secret, request=request, body=body)

    interaction = parse_interaction_payload(body)
    if interaction:
        background_tasks.add_task(handle_interaction_fn, interaction)

    return {"ok": True}
