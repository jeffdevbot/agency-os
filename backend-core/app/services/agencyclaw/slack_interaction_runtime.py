"""Slack interaction runtime flow for AgencyClaw."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from .slack_runtime_deps import SlackInteractionRuntimeDeps


async def handle_interaction_runtime(
    payload: dict[str, Any],
    *,
    deps: SlackInteractionRuntimeDeps,
) -> None:
    if payload.get("type") != "block_actions":
        return

    actions = payload.get("actions")
    if not isinstance(actions, list) or not actions:
        return

    action = actions[0] if isinstance(actions[0], dict) else {}
    action_id = str(action.get("action_id") or "")

    user = payload.get("user") if isinstance(payload.get("user"), dict) else {}
    channel = payload.get("channel") if isinstance(payload.get("channel"), dict) else {}
    message = payload.get("message") if isinstance(payload.get("message"), dict) else {}

    slack_user_id = str(user.get("id") or "").strip()
    channel_id = str(channel.get("id") or "").strip()
    message_ts = str(message.get("ts") or "").strip()

    if not slack_user_id or not channel_id:
        return

    receipt_service = deps.get_receipt_service_fn()
    dedupe_key = f"interaction:{slack_user_id}:{action_id}:{message_ts}"[-255:]

    is_new = await asyncio.to_thread(
        receipt_service.attempt_insert_dedupe,
        event_key=dedupe_key,
        event_source="interactions",
        payload=payload,
    )

    if not is_new:
        deps.logger.debug("Duplicate interaction ignored: %s", dedupe_key)
        return

    session_service = deps.get_session_service_fn()
    slack = deps.get_slack_service_fn()

    try:
        session = await asyncio.to_thread(session_service.get_or_create_session, slack_user_id)

        if action_id.startswith("select_client_"):
            client_id = str(action.get("value") or "").strip()
            if not client_id:
                return

            await asyncio.to_thread(session_service.set_active_client, session.id, client_id)
            await asyncio.to_thread(session_service.update_context, session.id, {"pending_task": None})

            client_name = await asyncio.to_thread(session_service.get_client_name, client_id)
            client_name = client_name or "that client"

            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Now working on *{client_name}*. What would you like to do for this client?",
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

            receipt_service.update_status(dedupe_key, "processed")
            return

        if action_id.startswith("select_brand_"):
            brand_id = str(action.get("value") or "").strip()
            if not brand_id:
                return

            pending = session.context.get("pending_task_create")
            if not isinstance(pending, dict) or pending.get("awaiting") != "brand":
                await slack.post_message(channel=channel_id, text="No pending brand selection.")
                receipt_service.update_status(dedupe_key, "ignored")
                return

            candidates = pending.get("brand_candidates") or []
            valid_brand_ids = {
                str(c.get("id") or "")
                for c in candidates
                if isinstance(c, dict)
            }
            if brand_id not in valid_brand_ids:
                await slack.post_message(
                    channel=channel_id,
                    text="That brand option is no longer valid. Please choose from the current picker.",
                )
                receipt_service.update_status(dedupe_key, "ignored", {"reason": "invalid_brand_selection"})
                return

            brand_name = next(
                (str(c.get("name", "Brand")) for c in candidates if str(c.get("id")) == brand_id),
                "Brand",
            )

            client_id = pending.get("client_id", "")
            client_name = pending.get("client_name", "")
            task_title = pending.get("task_title", "")

            if message_ts:
                await slack.update_message(
                    channel=channel_id,
                    ts=message_ts,
                    text=f"Selected brand: {brand_name}",
                    blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": f"Selected: *{brand_name}*"}}],
                )

            brand_note = f" (brand: {brand_name})"

            if not task_title:
                new_pending = {
                    "awaiting": "title",
                    "client_id": client_id,
                    "client_name": client_name,
                    "brand_id": brand_id,
                    "brand_name": brand_name,
                    "brand_resolution_mode": "explicit_brand",
                }
                await asyncio.to_thread(
                    session_service.update_context, session.id, {"pending_task_create": new_pending}
                )
                await slack.post_message(
                    channel=channel_id,
                    text=f"Got it, brand: *{brand_name}*. What should the task be called for *{client_name}*?",
                )
            else:
                new_pending = {
                    "awaiting": "confirm_or_details",
                    "client_id": client_id,
                    "client_name": client_name,
                    "brand_id": brand_id,
                    "brand_name": brand_name,
                    "brand_resolution_mode": "explicit_brand",
                    "task_title": task_title,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                await asyncio.to_thread(
                    session_service.update_context, session.id, {"pending_task_create": new_pending}
                )
                blocks = [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"Ready to create task *{task_title}* for *{client_name}*{brand_note}.\n\n"
                                "Send a description to include, or click Create to proceed as draft."
                            )
                        }
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "Create Task (Draft)"},
                                "style": "primary",
                                "action_id": "confirm_create_task_draft",
                                "value": "confirmed",
                            },
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "Cancel"},
                                "style": "danger",
                                "action_id": "cancel_create_task",
                                "value": "cancelled",
                            },
                        ],
                    },
                ]
                await slack.post_message(
                    channel=channel_id,
                    text=f"Ready to create task '{task_title}'. Confirm?",
                    blocks=blocks,
                )

            receipt_service.update_status(dedupe_key, "processed")
            return

        if action_id == "confirm_create_task_draft":
            pending = session.context.get("pending_task_create")
            if not isinstance(pending, dict) or pending.get("awaiting") != "confirm_or_details":
                await slack.post_message(channel=channel_id, text="No pending task to confirm.")
                receipt_service.update_status(dedupe_key, "ignored", {"reason": "no_state"})
                return

            ts_str = pending.get("timestamp")
            if ts_str:
                try:
                    dt = datetime.fromisoformat(str(ts_str))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) - dt > timedelta(minutes=10):
                        await asyncio.to_thread(session_service.update_context, session.id, {"pending_task_create": None})
                        await slack.update_message(
                            channel=channel_id,
                            ts=message_ts,
                            text="Task creation timed out.",
                            blocks=[],
                        )
                        receipt_service.update_status(dedupe_key, "ignored", {"reason": "expired"})
                        return
                except ValueError:
                    pass

            await slack.update_message(
                channel=channel_id,
                ts=message_ts,
                text="Creating task...",
                blocks=[],
            )

            await deps.execute_task_create_fn(
                channel=channel_id,
                session=session,
                session_service=session_service,
                slack=slack,
                client_id=pending.get("client_id", ""),
                client_name=pending.get("client_name", ""),
                task_title=pending.get("task_title", ""),
                task_description="",
                brand_id=pending.get("brand_id"),
                brand_name=pending.get("brand_name"),
            )
            receipt_service.update_status(dedupe_key, "processed")
            return

        if action_id == "cancel_create_task":
            await asyncio.to_thread(session_service.update_context, session.id, {"pending_task_create": None})
            await slack.update_message(
                channel=channel_id,
                ts=message_ts,
                text="Task creation cancelled.",
                blocks=[],
            )
            receipt_service.update_status(dedupe_key, "processed")
            return

    except deps.slack_api_error_cls:
        receipt_service.update_status(dedupe_key, "failed")
    except Exception as exc:  # noqa: BLE001
        deps.logger.warning("Error handling interaction: %s", exc)
        receipt_service.update_status(dedupe_key, "failed", {"error": str(exc)})
    finally:
        await slack.aclose()
