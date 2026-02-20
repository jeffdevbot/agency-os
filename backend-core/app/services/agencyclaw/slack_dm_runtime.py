"""Slack DM event runtime flow for AgencyClaw."""

from __future__ import annotations

import asyncio
from typing import Any

from .slack_runtime_deps import SlackDMRuntimeDeps


async def handle_dm_event_runtime(
    *,
    slack_user_id: str,
    channel: str,
    text: str,
    deps: SlackDMRuntimeDeps,
) -> None:
    """Handle Slack DM event with pending/orchestrator/deterministic routing."""
    session_service = deps.get_session_service_fn()
    pref_service = deps.preference_memory_service_factory(session_service.db)
    slack = deps.get_slack_service_fn()

    try:
        session = await asyncio.to_thread(session_service.get_or_create_session, slack_user_id)
        await asyncio.to_thread(session_service.touch_session, session.id)

        pending = session.context.get("pending_task_create")
        if isinstance(pending, dict) and pending.get("awaiting"):
            consumed = await deps.handle_pending_task_continuation_fn(
                channel=channel,
                text=text,
                session=session,
                session_service=session_service,
                slack=slack,
                pending=pending,
            )
            if consumed:
                return

        if deps.is_llm_orchestrator_enabled_fn():
            handled = await deps.try_llm_orchestrator_fn(
                text=text,
                slack_user_id=slack_user_id,
                channel=channel,
                session=session,
                session_service=session_service,
                slack=slack,
            )
            if handled:
                return

        intent, params = deps.classify_message_fn(text)
        if deps.should_block_deterministic_intent_fn(intent):
            await slack.post_message(
                channel=channel,
                text="I'm not sure what to do with that. "
                "Try asking about a client's tasks, or tell me what you need help with.",
            )
            return

        if intent == "create_task":
            policy = await deps.check_skill_policy_fn(
                slack_user_id=slack_user_id,
                session=session,
                channel=channel,
                skill_id="clickup_task_create",
            )
            if not policy["allowed"]:
                await slack.post_message(channel=channel, text=policy["user_message"])
                return

            await deps.handle_create_task_fn(
                slack_user_id=slack_user_id,
                channel=channel,
                client_name_hint=str(params.get("client_name") or ""),
                task_title=str(params.get("task_title") or ""),
                session_service=session_service,
                slack=slack,
                pref_service=pref_service,
            )
            return

        if intent == "confirm_draft_task":
            await slack.post_message(
                channel=channel,
                text="Nothing to confirm right now. Tell me what task you'd like to create.",
            )
            return

        if intent in ("task_list", "weekly_tasks"):
            policy = await deps.check_skill_policy_fn(
                slack_user_id=slack_user_id,
                session=session,
                channel=channel,
                skill_id="clickup_task_list",
            )
            if not policy["allowed"]:
                await slack.post_message(channel=channel, text=policy["user_message"])
                return

            await deps.handle_task_list_fn(
                slack_user_id=slack_user_id,
                channel=channel,
                client_name_hint=str(params.get("client_name") or ""),
                window=str(params.get("window") or ""),
                window_days=params.get("window_days"),
                date_from=str(params.get("date_from") or ""),
                date_to=str(params.get("date_to") or ""),
                session_service=session_service,
                slack=slack,
            )
            return

        if intent == "switch_client":
            client_name = str(params.get("client_name") or "").strip()
            if not client_name:
                await slack.post_message(channel=channel, text=deps.help_text_fn())
                return

            matches = await asyncio.to_thread(
                session_service.find_client_matches, session.profile_id, client_name
            )
            if not matches:
                clients = await asyncio.to_thread(session_service.list_clients_for_picker, session.profile_id)
                blocks = deps.build_client_picker_blocks_fn(clients) if clients else None
                await slack.post_message(
                    channel=channel,
                    text=f"I couldn't find a client matching: {client_name!r}",
                    blocks=blocks,
                )
                return
            if len(matches) > 1:
                blocks = deps.build_client_picker_blocks_fn(matches)
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
                text=f"Now working on *{client_display}*. What would you like to do for this client?",
            )
            return

        if intent == "set_default_client":
            client_name = str(params.get("client_name") or "").strip()
            if not client_name:
                await slack.post_message(
                    channel=channel,
                    text="Usage: `set my default client to <client name>`",
                )
                return

            if not session.profile_id:
                await slack.post_message(
                    channel=channel,
                    text="I can't save preferences — your Slack account isn't linked to a profile yet.",
                )
                return

            matches = await asyncio.to_thread(
                session_service.find_client_matches, session.profile_id, client_name
            )
            if not matches:
                await slack.post_message(
                    channel=channel,
                    text=f"I couldn't find a client matching *{client_name}*.",
                )
                return
            if len(matches) > 1:
                blocks = deps.build_client_picker_blocks_fn(matches)
                await slack.post_message(
                    channel=channel,
                    text=f"Multiple clients match *{client_name}*. Be more specific:",
                    blocks=blocks,
                )
                return

            client_id = str(matches[0].get("id") or "")
            client_display = str(matches[0].get("name") or client_name)
            await asyncio.to_thread(pref_service.set_default_client, session.profile_id, client_id)
            await asyncio.to_thread(session_service.set_active_client, session.id, client_id)
            await slack.post_message(
                channel=channel,
                text=f"Default client set to *{client_display}*. This will persist across sessions.",
            )
            return

        if intent == "clear_defaults":
            if not session.profile_id:
                await slack.post_message(
                    channel=channel,
                    text="I can't manage preferences — your Slack account isn't linked to a profile yet.",
                )
                return

            await asyncio.to_thread(pref_service.clear_default_client, session.profile_id)
            await slack.post_message(
                channel=channel,
                text="Default client cleared. I'll ask you to pick a client each time.",
            )
            return

        if intent in (
            "cc_client_lookup",
            "cc_brand_list_all",
            "cc_brand_clickup_mapping_audit",
            "cc_brand_mapping_remediation_preview",
            "cc_brand_mapping_remediation_apply",
            "cc_assignment_upsert",
            "cc_assignment_remove",
            "cc_brand_create",
            "cc_brand_update",
        ):
            policy = await deps.check_skill_policy_fn(
                slack_user_id=slack_user_id,
                session=session,
                channel=channel,
                skill_id=intent,
            )
            if not policy["allowed"]:
                await slack.post_message(channel=channel, text=policy["user_message"])
                return

            await deps.handle_cc_skill_fn(
                skill_id=intent,
                args=params,
                session=session,
                session_service=session_service,
                channel=channel,
                slack=slack,
            )
            return

        await slack.post_message(channel=channel, text=deps.help_text_fn())
    except deps.slack_api_error_cls:
        pass
    except Exception as exc:  # noqa: BLE001
        deps.logger.warning("Unhandled error in _handle_dm_event: %s", exc, exc_info=True)
        try:
            await slack.post_message(
                channel=channel,
                text="Something went wrong while processing that. Please try again.",
            )
        except Exception:  # noqa: BLE001
            pass
    finally:
        await slack.aclose()
