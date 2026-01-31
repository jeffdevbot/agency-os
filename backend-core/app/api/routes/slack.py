import json
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse

from ...services.slack import (
    SlackAPIError,
    get_slack_service,
    get_slack_signing_secret,
    verify_slack_signature,
)

router = APIRouter(prefix="/slack", tags=["slack"])


async def _echo_dm(channel: str, text: str) -> None:
    service = get_slack_service()
    try:
        await service.post_message(channel=channel, text=f"Echo: {text}")
    except SlackAPIError:
        # Keep the endpoint fast and non-fatal; Slack will retry delivery if needed.
        pass
    finally:
        await service.aclose()


def _parse_json(body: bytes) -> dict[str, Any]:
    try:
        value = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    return value


def _verify_request_or_401(*, signing_secret: str, request: Request, body: bytes) -> None:
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    if not verify_slack_signature(signing_secret, timestamp, body, signature):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")


@router.post("/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    signing_secret = get_slack_signing_secret().strip()
    if not signing_secret:
        raise HTTPException(status_code=500, detail="SLACK_SIGNING_SECRET not set")

    body = await request.body()
    _verify_request_or_401(signing_secret=signing_secret, request=request, body=body)

    # If Slack retries a delivery, avoid duplicating side effects.
    if request.headers.get("X-Slack-Retry-Num"):
        return JSONResponse({"ok": True})

    payload = _parse_json(body)

    # 2) URL verification challenge
    if payload.get("type") == "url_verification":
        challenge = payload.get("challenge")
        if not isinstance(challenge, str) or not challenge:
            raise HTTPException(status_code=400, detail="Missing Slack challenge")
        return JSONResponse({"challenge": challenge})

    # 3) Echo DMs (message.im)
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
            if channel and text:
                # 4) Return quickly (Slack timeout ~3s) and send message in background.
                background_tasks.add_task(_echo_dm, channel, text)

    return JSONResponse({"ok": True})


@router.post("/interactions")
async def slack_interactions(request: Request):
    signing_secret = get_slack_signing_secret().strip()
    if not signing_secret:
        raise HTTPException(status_code=500, detail="SLACK_SIGNING_SECRET not set")

    body = await request.body()
    _verify_request_or_401(signing_secret=signing_secret, request=request, body=body)

    # Phase 2 scope: acknowledge quickly; interactions will be handled in later phases.
    return JSONResponse({"ok": True})
