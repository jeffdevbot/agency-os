"""Slack task-create runtime helpers."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from .slack_runtime_deps import SlackTaskRuntimeDeps

async def execute_task_create_runtime(
    *,
    channel: str,
    session: Any,
    session_service: Any,
    slack: Any,
    client_id: str,
    client_name: str,
    task_title: str,
    task_description: str,
    brand_id: str | None = None,
    brand_name: str | None = None,
    deps: SlackTaskRuntimeDeps,
) -> None:
    """Create a ClickUp task and report the result in Slack."""
    clickup = None
    idempotency_key = ""
    acquired_inflight = False
    try:
        if not session.profile_id:
            await slack.post_message(
                channel=channel,
                text="I couldn't link your Slack user to a profile. Ask an admin to set `profiles.slack_user_id`.",
            )
            return

        if brand_id:
            try:
                brand_resp = await asyncio.to_thread(
                    lambda: session_service.db.table("brands")
                    .select("id,name,clickup_space_id,clickup_list_id")
                    .eq("id", brand_id)
                    .limit(1)
                    .execute()
                )
                rows = brand_resp.data if isinstance(brand_resp.data, list) else []
                destination = rows[0] if rows else None
            except Exception:  # noqa: BLE001
                destination = None
        else:
            destination = await asyncio.to_thread(
                session_service.get_brand_destination_for_client, client_id
            )
        list_id = destination.get("clickup_list_id") if destination else None
        space_id = destination.get("clickup_space_id") if destination else None

        if not destination or (not space_id and not list_id):
            await slack.post_message(
                channel=channel,
                text=(
                    f"No brand with ClickUp mapping found for *{client_name}*. "
                    "Ask an admin to configure a ClickUp destination in Command Center."
                ),
            )
            return

        brand_id = brand_id or str(destination.get("id") or "")
        brand_name_display = brand_name or destination.get("name") or ""
        idempotency_key = deps.build_idempotency_key_fn(brand_id, task_title)

        async with deps.inflight_lock:
            if idempotency_key in deps.inflight_set:
                await slack.post_message(
                    channel=channel,
                    text="Another operation for this target is in progress. Please wait and try again.",
                )
                return
            deps.inflight_set.add(idempotency_key)
            acquired_inflight = True

        try:
            db = deps.get_supabase_admin_client_fn()
            duplicate = await asyncio.to_thread(deps.check_duplicate_fn, db, idempotency_key)
        except Exception as dedupe_exc:  # noqa: BLE001
            deps.logger.warning("Dedupe check failed (fail-closed): %s", dedupe_exc)
            await slack.post_message(
                channel=channel,
                text="I couldn't safely validate duplicate protection right now. Please try again in a minute.",
            )
            return

        if duplicate:
            cu_id = duplicate.get("clickup_task_id") or ""
            if cu_id:
                await slack.post_message(
                    channel=channel,
                    text=f"A task with that title was already created today (ClickUp `{cu_id}`). Skipping duplicate.",
                )
            else:
                await slack.post_message(
                    channel=channel,
                    text="A task with that title was already created today. Skipping duplicate.",
                )
            return

        clickup_user_id = await asyncio.to_thread(
            session_service.get_profile_clickup_user_id, session.profile_id
        )
        clickup = deps.get_clickup_service_fn()

        full_description = task_description or ""
        explicit_identifiers = deps.extract_product_identifiers_fn(task_title, task_description)
        has_identifier_block = "product identifiers:" in full_description.lower()
        if explicit_identifiers and not has_identifier_block:
            full_description = (
                f"**Product identifiers:** {', '.join(explicit_identifiers)}\n\n{full_description}"
            ).rstrip()
        if brand_name_display:
            full_description = f"**Brand:** {brand_name_display}\n\n{full_description}".rstrip()

        if list_id:
            async def _create_fn():  # type: ignore[return]
                return await clickup.create_task_in_list(
                    list_id=str(list_id),
                    name=task_title,
                    description_md=full_description,
                    assignee_ids=[clickup_user_id] if clickup_user_id else None,
                )
        else:
            async def _create_fn():  # type: ignore[return]
                return await clickup.create_task_in_space(
                    space_id=str(space_id),
                    name=task_title,
                    description_md=full_description,
                    assignee_ids=[clickup_user_id] if clickup_user_id else None,
                )

        try:
            task = await deps.retry_with_backoff_fn(_create_fn)
        except deps.retry_exhausted_error_cls as exc:  # type: ignore[misc]
            await slack.post_message(
                channel=channel,
                text=f"Failed to create ClickUp task: {exc.last_error}",
            )
            return

        try:
            await asyncio.to_thread(
                lambda: db.table("agent_tasks").insert({
                    "clickup_task_id": task.id,
                    "client_id": client_id,
                    "assignee_id": session.profile_id,
                    "source": "slack_dm",
                    "source_reference": idempotency_key,
                    "skill_invoked": "clickup_task_create",
                    "status": "pending",
                }).execute()
            )
        except Exception as persist_exc:  # noqa: BLE001
            deps.logger.warning("agent_tasks insert failed (orphan): %s", persist_exc)
            try:
                await asyncio.to_thread(
                    deps.emit_orphan_event_fn,
                    db,
                    clickup_task=task,
                    idempotency_key=idempotency_key,
                    client_id=client_id,
                    employee_id=session.profile_id,
                    error=str(persist_exc),
                )
            except Exception:  # noqa: BLE001
                pass

        url = task.url or ""
        link = f"<{url}|{task_title}>" if url else task_title
        brand_note = f" (brand: {brand_name_display})" if brand_name_display else ""
        draft_note = ""
        if not task_description:
            draft_note = "\n_Created as draft — add details directly in ClickUp._"
        await slack.post_message(
            channel=channel,
            text=f"Task created: {link}{brand_note}{draft_note}",
        )
    except (deps.clickup_configuration_error_cls, deps.clickup_error_cls) as exc:
        await slack.post_message(channel=channel, text=f"Failed to create ClickUp task: {exc}")
    finally:
        if acquired_inflight:
            async with deps.inflight_lock:
                deps.inflight_set.discard(idempotency_key)
        await asyncio.to_thread(
            session_service.update_context, session.id, {"pending_task_create": None}
        )
        if clickup:
            await clickup.aclose()


async def handle_create_task_runtime(
    *,
    slack_user_id: str,
    channel: str,
    client_name_hint: str,
    task_title: str,
    session_service: Any,
    slack: Any,
    pref_service: Any | None,
    deps: SlackTaskRuntimeDeps,
) -> None:
    """Handle deterministic create-task path."""
    session = await asyncio.to_thread(session_service.get_or_create_session, slack_user_id)
    client_id, client_name = await deps.resolve_client_for_task_fn(
        client_name_hint=client_name_hint,
        session=session,
        session_service=session_service,
        channel=channel,
        slack=slack,
        pref_service=pref_service,
    )
    if not client_id:
        return

    resolution = await deps.resolve_brand_for_task_fn(
        client_id=client_id,
        client_name=client_name,
        task_text=task_title,
        brand_hint="",
        session=session,
        session_service=session_service,
        channel=channel,
        slack=slack,
    )

    if resolution["mode"] == "no_destination":
        await slack.post_message(
            channel=channel,
            text=(
                f"No brand with ClickUp mapping found for *{client_name}*. "
                "Ask an admin to configure a ClickUp destination in Command Center."
            ),
        )
        return

    if resolution["mode"] in ("ambiguous_brand", "ambiguous_destination"):
        pending = {
            "awaiting": "brand",
            "client_id": client_id,
            "client_name": client_name,
            "task_title": task_title,
            "brand_candidates": [
                {"id": str(b.get("id") or ""), "name": str(b.get("name") or "")}
                for b in resolution["candidates"]
            ],
        }
        await asyncio.to_thread(
            session_service.update_context, session.id, {"pending_task_create": pending}
        )
        return

    brand_ctx = resolution["brand_context"]
    brand_id = str(brand_ctx["id"]) if brand_ctx else None
    brand_name = str(brand_ctx["name"]) if brand_ctx else None
    brand_note = f" (brand: {brand_name})" if brand_name else ""

    if not task_title:
        pending = {
            "awaiting": "title",
            "client_id": client_id,
            "client_name": client_name,
            "brand_id": brand_id,
            "brand_name": brand_name,
            "brand_resolution_mode": resolution["mode"],
        }
        await asyncio.to_thread(
            session_service.update_context, session.id, {"pending_task_create": pending}
        )
        await slack.post_message(
            channel=channel,
            text=f"What should the task be called for *{client_name}*{brand_note}? Send the title.",
        )
        return

    pending = {
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
        session_service.update_context, session.id, {"pending_task_create": pending}
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


async def enrich_task_draft_runtime(
    *,
    task_title: str,
    client_id: str,
    client_name: str,
    deps: SlackTaskRuntimeDeps,
) -> dict[str, Any] | None:
    """Attempt KB retrieval + grounded draft. Returns None on failures."""
    try:
        db = deps.get_supabase_admin_client_fn()
        retrieval = await deps.retrieve_kb_context_fn(
            query=task_title,
            client_id=client_id,
            skill_id="clickup_task_create",
            db=db,
        )
        if not retrieval["sources"]:
            return None

        draft = deps.build_grounded_task_draft_fn(
            request_text=task_title,
            client_name=client_name,
            retrieved_context=retrieval,
            task_title=task_title,
        )
        return draft
    except Exception:
        deps.logger.warning("C10C: KB retrieval/draft failed, continuing without enrichment", exc_info=True)
        return None
