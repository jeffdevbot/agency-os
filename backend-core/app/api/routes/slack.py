import asyncio
import json
from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse

from ...services.clickup import ClickUpError, ClickUpConfigurationError, get_clickup_service
from ...services.playbook_session import get_playbook_session_service
from ...services.sop_sync import SOPSyncService
from ...services.slack import (
    SlackAPIError,
    get_slack_service,
    get_slack_signing_secret,
    verify_slack_signature,
)

router = APIRouter(prefix="/slack", tags=["slack"])


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


def _build_client_picker_blocks(clients: list[dict[str, Any]]) -> list[dict[str, Any]]:
    top = clients[:10]
    blocks: list[dict[str, Any]] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "Which client are you working on today?"},
        }
    ]

    # Slack actions block supports up to 5 elements; cap overall at 10.
    for i in range(0, len(top), 5):
        chunk = top[i : i + 5]
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": str(client.get("name", "Client"))},
                        "action_id": f"select_client_{client.get('id')}",
                        "value": str(client.get("id")),
                    }
                    for client in chunk
                ],
            }
        )

    return blocks


def _classify_message(text: str) -> tuple[str, dict[str, Any]]:
    t = " ".join((text or "").strip().lower().split())
    if any(kw in t for kw in ("ngram", "n-gram", "keyword research")):
        return ("create_ngram_task", {})
    if t.startswith("switch to "):
        return ("switch_client", {"client_name": t.removeprefix("switch to ").strip()})
    if t.startswith("work on "):
        return ("switch_client", {"client_name": t.removeprefix("work on ").strip()})
    return ("help", {})


def _help_text() -> str:
    return (
        "I can help you create ClickUp tasks from SOPs.\n\n"
        "Try:\n"
        "- `start ngram research`\n"
        "- `switch to <client name>`"
    )


async def _handle_dm_event(*, slack_user_id: str, channel: str, text: str) -> None:
    session_service = get_playbook_session_service()
    slack = get_slack_service()

    try:
        session = await asyncio.to_thread(session_service.get_or_create_session, slack_user_id)
        await asyncio.to_thread(session_service.touch_session, session.id)

        intent, params = _classify_message(text)

        if intent == "switch_client":
            client_name = str(params.get("client_name") or "").strip()
            if not client_name:
                await slack.post_message(channel=channel, text=_help_text())
                return

            matches = await asyncio.to_thread(
                session_service.find_client_matches, session.profile_id, client_name
            )

            if not matches:
                clients = await asyncio.to_thread(session_service.list_clients_for_picker, session.profile_id)
                blocks = _build_client_picker_blocks(clients) if clients else None
                await slack.post_message(
                    channel=channel,
                    text=f"I couldn't find a client matching: {client_name!r}",
                    blocks=blocks,
                )
                return

            if len(matches) > 1:
                blocks = _build_client_picker_blocks(matches)
                await slack.post_message(
                    channel=channel,
                    text=f"Multiple clients match {client_name!r}. Pick one:",
                    blocks=blocks,
                )
                return

            client_id = str(matches[0].get("id") or "")
            client_display = str(matches[0].get("name") or "that client")
            await asyncio.to_thread(session_service.set_active_client, session.id, client_id)
            await asyncio.to_thread(session_service.update_context, session.id, {"pending_task": None})
            await slack.post_message(
                channel=channel,
                text=f"Now working on *{client_display}*.\n\nTry: `start ngram research`",
            )
            return

        if not session.active_client_id:
            clients = await asyncio.to_thread(session_service.list_clients_for_picker, session.profile_id)
            if not clients:
                await slack.post_message(
                    channel=channel,
                    text="I couldn’t find any clients to pick from. Ask an admin to assign you.",
                )
                return

            blocks = _build_client_picker_blocks(clients)
            await slack.post_message(channel=channel, text=_help_text())
            await slack.post_message(channel=channel, text="Select a client", blocks=blocks)
            return

        if intent == "create_ngram_task":
            client_id = str(session.active_client_id or "")
            client_name = await asyncio.to_thread(session_service.get_client_name, client_id)
            client_name = client_name or "Client"

            if not session.profile_id:
                await slack.post_message(
                    channel=channel,
                    text="I couldn't link your Slack user to a profile. Ask an admin to set `profiles.slack_user_id`.",
                )
                return

            clickup_user_id = await asyncio.to_thread(
                session_service.get_profile_clickup_user_id, session.profile_id
            )

            destination = await asyncio.to_thread(session_service.get_brand_destination_for_client, client_id)
            if not destination or not destination.get("clickup_space_id"):
                await slack.post_message(
                    channel=channel,
                    text=f"No brand configured for *{client_name}* with `clickup_space_id`. Ask an admin to set it in Command Center.",
                )
                return

            sop_service = SOPSyncService(clickup_token="", supabase_client=session_service.db)
            sop = await sop_service.get_sop_by_category("ngram")
            sop_md = str((sop or {}).get("content_md") or "")
            if not sop_md.strip():
                await slack.post_message(
                    channel=channel,
                    text="N-gram SOP not found (category='ngram'). Ask an admin to run the SOP sync.",
                )
                return

            pending = {
                "intent": "create_ngram_task",
                "client_id": client_id,
                "client_name": client_name,
                "brand_id": destination.get("id"),
                "brand_name": destination.get("name"),
            }
            await asyncio.to_thread(session_service.update_context, session.id, {"pending_task": pending})

            clickup = None
            try:
                clickup = get_clickup_service()
                task = await clickup.create_task_in_space(
                    space_id=str(destination.get("clickup_space_id")),
                    name=f"N-gram Research: {client_name}",
                    description_md=sop_md,
                    assignee_ids=[clickup_user_id] if clickup_user_id else None,
                    override_list_id=str(destination.get("clickup_list_id"))
                    if destination.get("clickup_list_id")
                    else None,
                )
            except (ClickUpConfigurationError, ClickUpError) as exc:
                await slack.post_message(channel=channel, text=f"Failed to create ClickUp task: {exc}")
                return
            finally:
                await asyncio.to_thread(session_service.update_context, session.id, {"pending_task": None})
                if clickup:
                    await clickup.aclose()

            url = task.url or ""
            link = f"<{url}|N-gram Research: {client_name}>" if url else f"N-gram Research: {client_name}"
            await slack.post_message(
                channel=channel,
                text=f"Task created: {link}",
            )
            return

        await slack.post_message(channel=channel, text=_help_text())
    except SlackAPIError:
        # Keep the endpoint non-fatal; Slack will retry delivery if needed.
        pass
    finally:
        await slack.aclose()


def _parse_interaction_payload(raw_body: bytes) -> dict[str, Any]:
    try:
        form = parse_qs(raw_body.decode("utf-8"), keep_blank_values=True)
    except UnicodeDecodeError:
        return {}

    payload_str = (form.get("payload") or [""])[0]
    if not payload_str:
        return {}
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


async def _handle_interaction(payload: dict[str, Any]) -> None:
    if payload.get("type") != "block_actions":
        return

    actions = payload.get("actions")
    if not isinstance(actions, list) or not actions:
        return

    action = actions[0] if isinstance(actions[0], dict) else {}
    action_id = str(action.get("action_id") or "")
    if not action_id.startswith("select_client_"):
        return

    client_id = str(action.get("value") or "").strip()
    user = payload.get("user") if isinstance(payload.get("user"), dict) else {}
    channel = payload.get("channel") if isinstance(payload.get("channel"), dict) else {}
    message = payload.get("message") if isinstance(payload.get("message"), dict) else {}

    slack_user_id = str(user.get("id") or "").strip()
    channel_id = str(channel.get("id") or "").strip()
    message_ts = str(message.get("ts") or "").strip()

    if not client_id or not slack_user_id or not channel_id:
        return

    session_service = get_playbook_session_service()
    slack = get_slack_service()
    try:
        session = await asyncio.to_thread(session_service.get_or_create_session, slack_user_id)
        await asyncio.to_thread(session_service.set_active_client, session.id, client_id)
        await asyncio.to_thread(session_service.update_context, session.id, {"pending_task": None})

        client_name = await asyncio.to_thread(session_service.get_client_name, client_id)
        client_name = client_name or "that client"

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Now working on *{client_name}*.\n\nTry: `start ngram research`",
                },
            }
        ]

        if message_ts:
            await slack.update_message(
                channel=channel_id,
                ts=message_ts,
                text=f"Working on: {client_name}",
                blocks=blocks,
            )
        else:
            await slack.post_message(channel=channel_id, text=f"Working on: {client_name}", blocks=blocks)
    except SlackAPIError:
        pass
    finally:
        await slack.aclose()


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

    if payload.get("type") == "url_verification":
        challenge = payload.get("challenge")
        if not isinstance(challenge, str) or not challenge:
            raise HTTPException(status_code=400, detail="Missing Slack challenge")
        return JSONResponse({"challenge": challenge})

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
                    _handle_dm_event,
                    slack_user_id=slack_user_id,
                    channel=channel,
                    text=text,
                )

    return JSONResponse({"ok": True})


@router.post("/interactions")
async def slack_interactions(request: Request, background_tasks: BackgroundTasks):
    signing_secret = get_slack_signing_secret().strip()
    if not signing_secret:
        raise HTTPException(status_code=500, detail="SLACK_SIGNING_SECRET not set")

    body = await request.body()
    _verify_request_or_401(signing_secret=signing_secret, request=request, body=body)

    interaction = _parse_interaction_payload(body)
    if interaction:
        background_tasks.add_task(_handle_interaction, interaction)

    return JSONResponse({"ok": True})
