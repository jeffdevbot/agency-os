"""Resolution helpers extracted from Slack route layer."""

from __future__ import annotations

import asyncio
from typing import Any

from .brand_context_resolver import BrandResolution, resolve_brand_context


async def resolve_client_for_task_runtime(
    *,
    client_name_hint: str,
    session: Any,
    session_service: Any,
    channel: str,
    slack: Any,
    pref_service: Any | None = None,
    build_client_picker_blocks_fn: Any,
) -> tuple[str | None, str]:
    """Resolve client_id + client_name from hint or active session."""
    if client_name_hint:
        matches = await asyncio.to_thread(
            session_service.find_client_matches, session.profile_id, client_name_hint
        )
        if not matches:
            await slack.post_message(
                channel=channel,
                text=f"I couldn't find a client matching *{client_name_hint}*.",
            )
            return None, ""
        if len(matches) > 1:
            blocks = build_client_picker_blocks_fn(matches)
            await slack.post_message(
                channel=channel,
                text=f"Multiple clients match *{client_name_hint}*. Pick one and try again:",
                blocks=blocks,
            )
            return None, ""
        return str(matches[0].get("id") or ""), str(matches[0].get("name") or client_name_hint)

    if pref_service and session.profile_id:
        pref_client_id = await asyncio.to_thread(
            pref_service.get_default_client_id, session.profile_id
        )
        if pref_client_id:
            name = await asyncio.to_thread(session_service.get_client_name, pref_client_id)
            if name:
                return pref_client_id, name

    if session.active_client_id:
        name = await asyncio.to_thread(session_service.get_client_name, session.active_client_id)
        return session.active_client_id, name or "Client"

    clients = await asyncio.to_thread(session_service.list_clients_for_picker, session.profile_id)
    if clients:
        blocks = build_client_picker_blocks_fn(clients)
        await slack.post_message(
            channel=channel,
            text="Which client is this task for? Pick one and try again:",
            blocks=blocks,
        )
    else:
        await slack.post_message(
            channel=channel,
            text="I couldn't find any clients. Ask an admin to assign you.",
        )
    return None, ""


async def resolve_brand_for_task_runtime(
    *,
    client_id: str,
    client_name: str,
    task_text: str,
    brand_hint: str,
    session: Any,
    session_service: Any,
    channel: str,
    slack: Any,
    build_brand_picker_blocks_fn: Any,
) -> BrandResolution:
    """Resolve brand context for task creation."""
    _ = session
    brands = await asyncio.to_thread(
        session_service.get_brands_with_context_for_client, client_id,
    )
    resolution = resolve_brand_context(brands, brand_hint=brand_hint, task_text=task_text)

    if resolution["mode"] in ("ambiguous_brand", "ambiguous_destination"):
        qualifier = (
            "different ClickUp destinations"
            if resolution["mode"] == "ambiguous_destination"
            else "multiple brands"
        )
        blocks = build_brand_picker_blocks_fn(resolution["candidates"], client_name)
        await slack.post_message(
            channel=channel,
            text=f"*{client_name}* has {qualifier}. Which brand is this for?",
            blocks=blocks,
        )

    return resolution


async def resolve_assignment_client_runtime(
    *,
    args: dict[str, Any],
    session_service: Any,
    session: Any,
    channel: str,
    slack: Any,
    build_client_picker_blocks_fn: Any,
) -> str | bool:
    """Resolve client for assignment skills (always requires concrete client)."""
    client_hint = str(args.get("client_name") or "").strip()

    if client_hint:
        matches = await asyncio.to_thread(
            session_service.find_client_matches, session.profile_id, client_hint,
        )
        if not matches:
            await slack.post_message(
                channel=channel,
                text=f"I couldn't find a client matching *{client_hint}*.",
            )
            return False
        if len(matches) > 1:
            blocks = build_client_picker_blocks_fn(matches)
            await slack.post_message(
                channel=channel,
                text=f"Multiple clients match *{client_hint}*. Pick one and try again:",
                blocks=blocks,
            )
            return False
        return str(matches[0].get("id") or "")

    if session.active_client_id:
        return str(session.active_client_id)

    clients = await asyncio.to_thread(
        session_service.list_clients_for_picker, session.profile_id,
    )
    if clients:
        blocks = build_client_picker_blocks_fn(clients)
        await slack.post_message(
            channel=channel,
            text="Which client is this assignment for? Pick one or say *switch to <client>* first:",
            blocks=blocks,
        )
    else:
        await slack.post_message(
            channel=channel,
            text="I need a client for this assignment. Say *switch to <client>* first.",
        )
    return False
