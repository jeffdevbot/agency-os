"""Slack task-list runtime flow for AgencyClaw."""

from __future__ import annotations

import asyncio
from typing import Any

from .slack_runtime_deps import SlackTaskListRuntimeDeps


async def handle_task_list_runtime(
    *,
    slack_user_id: str,
    channel: str,
    client_name_hint: str,
    session_service: Any,
    slack: Any,
    window: str = "",
    window_days: int | None = None,
    date_from: str = "",
    date_to: str = "",
    deps: SlackTaskListRuntimeDeps,
) -> None:
    """Handle task-list intent with optional time range."""
    session = await asyncio.to_thread(session_service.get_or_create_session, slack_user_id)

    client_id: str | None = None
    client_name: str = ""

    if client_name_hint:
        matches = await asyncio.to_thread(
            session_service.find_client_matches, session.profile_id, client_name_hint,
        )
        if not matches:
            await slack.post_message(
                channel=channel,
                text=f"I couldn't find a client matching *{client_name_hint}*.",
            )
            return
        if len(matches) > 1:
            blocks = deps.build_client_picker_blocks_fn(matches)
            await slack.post_message(
                channel=channel,
                text=f"Multiple clients match *{client_name_hint}*. Pick one and ask again:",
                blocks=blocks,
            )
            return
        client_id = str(matches[0].get("id") or "")
        client_name = str(matches[0].get("name") or client_name_hint)
    elif session.active_client_id:
        client_id = session.active_client_id
        client_name = await asyncio.to_thread(session_service.get_client_name, client_id) or "Client"
    else:
        clients = await asyncio.to_thread(session_service.list_clients_for_picker, session.profile_id)
        if clients:
            blocks = deps.build_client_picker_blocks_fn(clients)
            await slack.post_message(
                channel=channel,
                text="Which client? Pick one and ask again:",
                blocks=blocks,
            )
        else:
            await slack.post_message(
                channel=channel,
                text="I couldn't find any clients. Ask an admin to assign you.",
            )
        return

    if not client_id:
        await slack.post_message(channel=channel, text="Could not resolve client.")
        return

    destinations = await asyncio.to_thread(
        session_service.get_all_brand_destinations_for_client, client_id,
    )
    if not destinations:
        await slack.post_message(
            channel=channel,
            text=(
                f"No brands with ClickUp mapping found for *{client_name}*. "
                "Ask an admin to configure brand destinations."
            ),
        )
        return

    start_ms, end_ms, range_label = deps.resolve_task_range_fn(
        window=window,
        window_days=window_days,
        date_from=date_from,
        date_to=date_to,
    )

    clickup = None
    all_tasks: list[dict[str, Any]] = []
    brand_names: list[str] = []

    try:
        clickup = deps.get_clickup_service_fn()

        for dest in destinations:
            list_id = dest.get("clickup_list_id")
            space_id = dest.get("clickup_space_id")
            brand_names.append(str(dest.get("name") or "Unknown"))

            if list_id:
                target_list_id = str(list_id)
            elif space_id:
                try:
                    target_list_id = await clickup.resolve_default_list_id(str(space_id))
                except (deps.clickup_configuration_error_cls, deps.clickup_error_cls):
                    continue
            else:
                continue

            try:
                tasks = await clickup.get_tasks_in_list_all_pages(
                    target_list_id,
                    date_updated_gt=start_ms,
                    date_updated_lt=end_ms,
                    include_closed=False,
                    max_tasks=deps.task_cap + 1,
                )
                all_tasks.extend(tasks)
            except deps.clickup_error_cls:
                continue
    except (deps.clickup_configuration_error_cls, deps.clickup_error_cls) as exc:
        await slack.post_message(
            channel=channel,
            text=f"Failed to fetch tasks from ClickUp: {exc}",
        )
        return
    finally:
        if clickup:
            await clickup.aclose()

    seen_ids: set[str] = set()
    unique_tasks: list[dict[str, Any]] = []
    for task in all_tasks:
        task_id = str(task.get("id") or "")
        if task_id and task_id not in seen_ids:
            seen_ids.add(task_id)
            unique_tasks.append(task)

    response_text = deps.format_task_list_response_fn(
        client_name=client_name,
        tasks=unique_tasks,
        total_fetched=len(unique_tasks),
        brand_names=brand_names,
        range_label=range_label,
    )
    await slack.post_message(channel=channel, text=response_text)
