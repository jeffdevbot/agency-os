"""LLM orchestrator runtime execution flow for Slack route."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from .conversation_buffer import append_exchange, compact_exchanges
from .slack_runtime_deps import SlackOrchestratorRuntimeDeps


async def try_llm_orchestrator_runtime(
    *,
    text: str,
    slack_user_id: str,
    channel: str,
    session: Any,
    session_service: Any,
    slack: Any,
    deps: SlackOrchestratorRuntimeDeps,
) -> bool:
    """Attempt LLM-first orchestration. Returns True if fully handled."""
    try:
        client_context_pack = ""
        if session.active_client_id:
            client_name = await asyncio.to_thread(
                session_service.get_client_name, session.active_client_id
            )
            client_context_pack = f"Active client: {client_name or 'Unknown'} (id={session.active_client_id})"

        raw_exchanges = session.context.get("recent_exchanges") or []
        recent_exchanges = compact_exchanges(raw_exchanges)

        result = await deps.orchestrate_dm_message_fn(
            text=text,
            profile_id=session.profile_id,
            slack_user_id=slack_user_id,
            session_context=session.context,
            client_context_pack=client_context_pack,
            recent_exchanges=recent_exchanges,
        )

        mode = result["mode"]

        if result.get("tokens_in") is not None:
            try:
                await deps.log_ai_token_usage_fn(
                    tool="agencyclaw",
                    stage="intent_parse",
                    user_id=session.profile_id,
                    model=result.get("model_used"),
                    prompt_tokens=result.get("tokens_in"),
                    completion_tokens=result.get("tokens_out"),
                    total_tokens=result.get("tokens_total"),
                    meta={
                        "run_type": "dm_orchestrate",
                        "skill_id": result.get("skill_id"),
                        "client_id": session.active_client_id,
                        "channel_id": channel,
                        "mode": mode,
                    },
                )
            except Exception:  # noqa: BLE001
                pass

        if mode == "fallback":
            deps.logger.info("LLM orchestrator fallback: %s", result.get("reason", ""))
            return False

        if mode == "reply":
            reply_text = result.get("text") or "I'm not sure how to help with that."
            await slack.post_message(channel=channel, text=reply_text)
            updated = append_exchange(recent_exchanges, text, reply_text)
            await asyncio.to_thread(
                session_service.update_context, session.id,
                {"recent_exchanges": compact_exchanges(updated)},
            )
            return True

        if mode == "clarify":
            question = result.get("question") or "Could you provide more details?"
            clarify_skill_id = result.get("skill_id") or ""
            clarify_args = result.get("args") or {}

            if clarify_skill_id == "clickup_task_create":
                client_name_hint = str(clarify_args.get("client_name") or "")
                task_title = str(clarify_args.get("task_title") or "")

                pref_service = deps.preference_memory_service_factory(session_service.db)
                client_id, client_name = await deps.resolve_client_for_task_fn(
                    client_name_hint=client_name_hint,
                    session=session,
                    session_service=session_service,
                    channel=channel,
                    slack=slack,
                    pref_service=pref_service,
                )
                if not client_id:
                    return True

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
                        text=f"No ClickUp destination configured for *{client_name}*.",
                    )
                    return True

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
                        session_service.update_context, session.id,
                        {"pending_task_create": pending},
                    )
                    return True

                brand_ctx = resolution["brand_context"]
                brand_id = str(brand_ctx["id"]) if brand_ctx else None
                brand_name = str(brand_ctx["name"]) if brand_ctx else None

                if not task_title:
                    pending = {
                        "awaiting": "title",
                        "client_id": client_id,
                        "client_name": client_name,
                        "brand_id": brand_id,
                        "brand_name": brand_name,
                        "brand_resolution_mode": resolution["mode"],
                    }
                else:
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
                    session_service.update_context, session.id,
                    {"pending_task_create": pending},
                )

            await slack.post_message(channel=channel, text=question)
            updated = append_exchange(recent_exchanges, text, question)
            await asyncio.to_thread(
                session_service.update_context, session.id,
                {"recent_exchanges": compact_exchanges(updated)},
            )
            return True

        if mode == "tool_call":
            skill_id = result.get("skill_id") or ""
            args = result.get("args") or {}

            policy = await deps.check_skill_policy_fn(
                slack_user_id=slack_user_id,
                session=session,
                channel=channel,
                skill_id=skill_id,
                args=args,
            )
            if not policy["allowed"]:
                deps.logger.info(
                    "C10A policy denied: reason=%s skill=%s",
                    policy["reason_code"], skill_id,
                )
                await slack.post_message(channel=channel, text=policy["user_message"])
                return True

            skill_summary = ""

            if skill_id in ("clickup_task_list", "clickup_task_list_weekly"):
                await deps.handle_weekly_tasks_fn(
                    slack_user_id=slack_user_id,
                    channel=channel,
                    client_name_hint=str(args.get("client_name") or ""),
                    window=str(args.get("window") or ""),
                    window_days=args.get("window_days"),
                    date_from=str(args.get("date_from") or ""),
                    date_to=str(args.get("date_to") or ""),
                    session_service=session_service,
                    slack=slack,
                )
                if skill_id == "clickup_task_list_weekly":
                    skill_summary = f"[Ran weekly task list for {args.get('client_name', 'client')}]"
                else:
                    skill_summary = f"[Ran task list for {args.get('client_name', 'client')}]"

            elif skill_id == "clickup_task_create":
                await deps.handle_create_task_fn(
                    slack_user_id=slack_user_id,
                    channel=channel,
                    client_name_hint=str(args.get("client_name") or ""),
                    task_title=str(args.get("task_title") or ""),
                    session_service=session_service,
                    slack=slack,
                )
                skill_summary = f"[Started task creation for {args.get('client_name', 'client')}]"

            elif skill_id in (
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
                skill_summary = await deps.handle_cc_skill_fn(
                    skill_id=skill_id,
                    args=args,
                    session=session,
                    session_service=session_service,
                    channel=channel,
                    slack=slack,
                )
            else:
                deps.logger.warning("LLM orchestrator returned unknown skill: %s", skill_id)
                return False

            if skill_summary:
                updated = append_exchange(recent_exchanges, text, skill_summary)
                await asyncio.to_thread(
                    session_service.update_context, session.id,
                    {"recent_exchanges": compact_exchanges(updated)},
                )
            return True

        if mode == "plan_request":
            plan_args = result.get("args") or {}
            planner_text = text
            if isinstance(plan_args, dict):
                delegated_text = str(plan_args.get("request_text") or "").strip()
                if delegated_text:
                    planner_text = delegated_text

            try:
                planned = await deps.try_planner_fn(
                    text=planner_text,
                    slack_user_id=slack_user_id,
                    channel=channel,
                    session=session,
                    session_service=session_service,
                    slack=slack,
                )
            except Exception as exc:  # noqa: BLE001
                deps.logger.warning("Planner delegation failed: %s", exc)
                planned = False

            if planned:
                return True

            intent, _ = deps.classify_message_fn(text)
            if deps.is_deterministic_control_intent_fn(intent):
                deps.logger.info(
                    "Planner unavailable for plan_request; rerouting control intent via deterministic path: %s",
                    intent,
                )
                return False

            clarify_text = (
                "I couldn't run planning for that request right now. "
                "Can you narrow it to one concrete step so I can run it directly?"
            )
            await slack.post_message(channel=channel, text=clarify_text)
            updated = append_exchange(recent_exchanges, text, clarify_text)
            await asyncio.to_thread(
                session_service.update_context, session.id,
                {"recent_exchanges": compact_exchanges(updated)},
            )
            return True

        return False

    except Exception as exc:  # noqa: BLE001
        deps.logger.warning("LLM orchestrator error: %s", exc)
        return False
