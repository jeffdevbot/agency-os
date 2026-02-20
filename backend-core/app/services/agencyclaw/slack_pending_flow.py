"""Pending task-create continuation flow helpers for Slack runtime."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from .pending_resolution import resolve_pending_action


def compose_asin_pending_description(stashed_draft: dict[str, Any] | None) -> str:
    """Build unresolved-task description when user proceeds without identifiers."""
    from app.services.agencyclaw.grounded_task_draft import _ASIN_OPEN_QUESTION

    draft = stashed_draft or {}
    open_qs = list(draft.get("open_questions") or [])
    if not open_qs:
        open_qs = [_ASIN_OPEN_QUESTION]

    parts: list[str] = []
    if draft.get("description"):
        parts.append(str(draft["description"]))

    checklist = draft.get("checklist") or []
    if isinstance(checklist, list) and checklist:
        parts.append("## Checklist\n" + "\n".join(f"- [ ] {s}" for s in checklist))

    citations = draft.get("citations") or []
    if isinstance(citations, list) and citations:
        titles = [str(c.get("title")) for c in citations if isinstance(c, dict) and c.get("title")]
        if titles:
            parts.append("---\nSources: " + ", ".join(titles))

    parts.append("## Unresolved\n- " + "\n- ".join(open_qs))
    parts.append("**First step:** Resolve ASIN(s)/SKU(s) before executing this task.")
    return "\n\n".join(parts)


async def handle_pending_task_continuation(
    *,
    channel: str,
    text: str,
    session: Any,
    session_service: Any,
    slack: Any,
    pending: dict[str, Any],
    classify_message: Callable[[str], tuple[str, dict[str, Any]]],
    resolve_brand_for_task: Callable[..., Awaitable[dict[str, Any]]],
    enrich_task_draft: Callable[..., Awaitable[dict[str, Any] | None]],
    execute_task_create: Callable[..., Awaitable[None]],
    extract_product_identifiers: Callable[..., list[str]],
) -> bool:
    """Handle follow-up messages when a task create is pending."""
    awaiting = pending.get("awaiting")

    if awaiting == "brand":
        brand_hint = text.strip()
        if not brand_hint:
            return False

        probe_intent, _ = classify_message(text)
        if probe_intent != "help":
            await asyncio.to_thread(
                session_service.update_context, session.id, {"pending_task_create": None}
            )
            return False

        client_id = pending.get("client_id", "")
        client_name = pending.get("client_name", "")
        task_title = pending.get("task_title", "")

        resolution = await resolve_brand_for_task(
            client_id=client_id,
            client_name=client_name,
            task_text=task_title,
            brand_hint=brand_hint,
            session=session,
            session_service=session_service,
            channel=channel,
            slack=slack,
        )

        if resolution["mode"] in ("ambiguous_brand", "ambiguous_destination"):
            return True

        if resolution["mode"] == "no_destination":
            await slack.post_message(channel=channel, text="No matching brand with ClickUp mapping found.")
            return True

        brand_ctx = resolution["brand_context"]
        brand_id = str(brand_ctx["id"]) if brand_ctx else None
        brand_name = str(brand_ctx["name"]) if brand_ctx else None
        brand_note = f" (brand: {brand_name})" if brand_name else ""

        if not task_title:
            new_pending = {
                "awaiting": "title",
                "client_id": client_id,
                "client_name": client_name,
                "brand_id": brand_id,
                "brand_name": brand_name,
                "brand_resolution_mode": resolution["mode"],
            }
            await asyncio.to_thread(
                session_service.update_context, session.id, {"pending_task_create": new_pending}
            )
            await slack.post_message(
                channel=channel,
                text=f"Got it, brand: *{brand_name or 'selected'}*. What should the task be called?",
            )
            return True

        new_pending = {
            "awaiting": "confirm_or_details",
            "client_id": client_id,
            "client_name": client_name,
            "brand_id": brand_id,
            "brand_name": brand_name,
            "brand_resolution_mode": resolution["mode"],
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
            channel=channel,
            text=f"Ready to create task '{task_title}'. Confirm?",
            blocks=blocks,
        )
        return True

    if awaiting == "title":
        title = text.strip()
        if not title:
            return False

        probe_intent, _ = classify_message(text)
        if probe_intent != "help":
            await asyncio.to_thread(
                session_service.update_context, session.id, {"pending_task_create": None}
            )
            return False

        client_id = pending.get("client_id", "")
        client_name = pending.get("client_name", "")
        brand_id = pending.get("brand_id")
        brand_name = pending.get("brand_name")
        brand_resolution_mode = pending.get("brand_resolution_mode")

        if not brand_id:
            resolution = await resolve_brand_for_task(
                client_id=client_id,
                client_name=client_name,
                task_text=title,
                brand_hint="",
                session=session,
                session_service=session_service,
                channel=channel,
                slack=slack,
            )

            if resolution["mode"] == "no_destination":
                await asyncio.to_thread(
                    session_service.update_context, session.id, {"pending_task_create": None}
                )
                await slack.post_message(
                    channel=channel,
                    text=(
                        f"No brand with ClickUp mapping found for *{client_name}*. "
                        "Ask an admin to configure a ClickUp destination in Command Center."
                    ),
                )
                return True

            if resolution["mode"] in ("ambiguous_brand", "ambiguous_destination"):
                new_pending = {
                    "awaiting": "brand",
                    "client_id": client_id,
                    "client_name": client_name,
                    "task_title": title,
                    "brand_candidates": [
                        {"id": str(b.get("id") or ""), "name": str(b.get("name") or "")}
                        for b in resolution["candidates"]
                    ],
                }
                await asyncio.to_thread(
                    session_service.update_context, session.id, {"pending_task_create": new_pending}
                )
                return True

            brand_ctx = resolution["brand_context"]
            brand_id = str(brand_ctx["id"]) if brand_ctx else None
            brand_name = str(brand_ctx["name"]) if brand_ctx else None
            brand_resolution_mode = resolution["mode"]

        new_pending = {
            "awaiting": "confirm_or_details",
            "client_id": client_id,
            "client_name": client_name,
            "brand_id": brand_id,
            "brand_name": brand_name,
            "brand_resolution_mode": brand_resolution_mode,
            "task_title": title,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await asyncio.to_thread(
            session_service.update_context, session.id, {"pending_task_create": new_pending}
        )

        _brand_name = brand_name
        _brand_note = f" (brand: {_brand_name})" if _brand_name else ""
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"Ready to create task *{title}* for *{client_name}*{_brand_note}.\n\n"
                        "Send a description to include, or click Create to proceed as draft."
                    ),
                },
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
            channel=channel,
            text=f"Ready to create task '{title}'. Confirm?",
            blocks=blocks,
        )
        return True

    if awaiting == "confirm_or_details":
        from app.services.agencyclaw.grounded_task_draft import (
            _ASIN_CLARIFICATION,
            _ASIN_OPEN_QUESTION,
            _has_product_identifier,
            _is_product_scoped,
        )

        probe_intent, _ = classify_message(text)
        pending_action = resolve_pending_action(
            awaiting="confirm_or_details",
            text=text,
            known_intent=probe_intent,
            has_identifier=_has_product_identifier(text),
        )

        client_id = pending.get("client_id", "")
        client_name = pending.get("client_name", "")
        task_title = pending.get("task_title", "")
        stashed_draft = pending.get("draft") if isinstance(pending.get("draft"), dict) else None

        if pending_action["action"] == "interrupt":
            await asyncio.to_thread(
                session_service.update_context, session.id, {"pending_task_create": None}
            )
            return False

        if pending_action["action"] == "cancel":
            await asyncio.to_thread(
                session_service.update_context, session.id, {"pending_task_create": None}
            )
            await slack.post_message(channel=channel, text="Okay, canceled task creation.")
            return True

        if pending_action["action"] == "off_topic":
            return False

        if pending_action["action"] == "proceed_with_asin_pending":
            if not stashed_draft:
                draft = await enrich_task_draft(
                    task_title=task_title,
                    client_id=client_id,
                    client_name=client_name,
                )
                stashed_draft = dict(draft) if draft else {}
            description = compose_asin_pending_description(stashed_draft)
            await execute_task_create(
                channel=channel,
                session=session,
                session_service=session_service,
                slack=slack,
                client_id=client_id,
                client_name=client_name,
                task_title=task_title,
                task_description=description,
                brand_id=pending.get("brand_id"),
                brand_name=pending.get("brand_name"),
            )
            return True

        if pending_action["action"] == "proceed_draft":
            enriched_description = ""
            draft = await enrich_task_draft(
                task_title=task_title,
                client_id=client_id,
                client_name=client_name,
            )

            if draft and draft.get("open_questions"):
                question = draft.get("clarification_question") or "Could you provide more details?"
                pending["awaiting"] = "asin_or_pending"
                pending["draft"] = dict(draft)
                await asyncio.to_thread(
                    session_service.update_context, session.id, {"pending_task_create": pending}
                )
                await slack.post_message(channel=channel, text=question)
                return True

            if draft and not draft["needs_clarification"]:
                parts: list[str] = []
                if draft["description"]:
                    parts.append(draft["description"])
                if draft["checklist"]:
                    parts.append("## Checklist\n" + "\n".join(f"- [ ] {s}" for s in draft["checklist"]))
                if draft["citations"]:
                    parts.append("---\nSources: " + ", ".join(c["title"] for c in draft["citations"]))
                if parts:
                    enriched_description = "\n\n".join(parts)

            await execute_task_create(
                channel=channel,
                session=session,
                session_service=session_service,
                slack=slack,
                client_id=client_id,
                client_name=client_name,
                task_title=task_title,
                task_description=enriched_description,
                brand_id=pending.get("brand_id"),
                brand_name=pending.get("brand_name"),
            )
            return True

        description = text.strip()

        combined_text = f"{task_title} {description}"
        if _is_product_scoped(combined_text) and not _has_product_identifier(combined_text):
            pending["awaiting"] = "asin_or_pending"
            pending["draft"] = {"description": description, "open_questions": [_ASIN_OPEN_QUESTION]}
            await asyncio.to_thread(
                session_service.update_context, session.id, {"pending_task_create": pending}
            )
            await slack.post_message(channel=channel, text=_ASIN_CLARIFICATION)
            return True

        await execute_task_create(
            channel=channel,
            session=session,
            session_service=session_service,
            slack=slack,
            client_id=client_id,
            client_name=client_name,
            task_title=task_title,
            task_description=description,
            brand_id=pending.get("brand_id"),
            brand_name=pending.get("brand_name"),
        )
        return True

    if awaiting == "asin_or_pending":
        from app.services.agencyclaw.grounded_task_draft import _has_product_identifier

        probe_intent, _ = classify_message(text)
        pending_action = resolve_pending_action(
            awaiting="asin_or_pending",
            text=text,
            known_intent=probe_intent,
            has_identifier=_has_product_identifier(text),
        )

        client_id = pending.get("client_id", "")
        client_name = pending.get("client_name", "")
        task_title = pending.get("task_title", "")
        stashed_draft = pending.get("draft") or {}

        if pending_action["action"] == "interrupt":
            await asyncio.to_thread(
                session_service.update_context, session.id, {"pending_task_create": None}
            )
            return False

        if pending_action["action"] == "cancel":
            await asyncio.to_thread(
                session_service.update_context, session.id, {"pending_task_create": None}
            )
            await slack.post_message(channel=channel, text="Okay, canceled task creation.")
            return True

        if pending_action["action"] == "proceed_with_asin_pending":
            description = compose_asin_pending_description(stashed_draft)
            await execute_task_create(
                channel=channel,
                session=session,
                session_service=session_service,
                slack=slack,
                client_id=client_id,
                client_name=client_name,
                task_title=task_title,
                task_description=description,
                brand_id=pending.get("brand_id"),
                brand_name=pending.get("brand_name"),
            )
            return True

        if pending_action["action"] == "provide_identifier":
            parts = []
            if stashed_draft.get("description"):
                parts.append(stashed_draft["description"])
            extracted_identifiers = extract_product_identifiers(text)
            identifier_payload = ", ".join(extracted_identifiers) if extracted_identifiers else text.strip()
            parts.append(f"Product identifiers: {identifier_payload}")
            description = "\n\n".join(parts)

            await execute_task_create(
                channel=channel,
                session=session,
                session_service=session_service,
                slack=slack,
                client_id=client_id,
                client_name=client_name,
                task_title=task_title,
                task_description=description,
                brand_id=pending.get("brand_id"),
                brand_name=pending.get("brand_name"),
            )
            return True

        if pending_action["action"] == "off_topic":
            return False

        from app.services.agencyclaw.grounded_task_draft import _ASIN_CLARIFICATION

        await slack.post_message(
            channel=channel,
            text=_ASIN_CLARIFICATION,
        )
        return True

    await asyncio.to_thread(
        session_service.update_context, session.id, {"pending_task_create": None}
    )
    return False
