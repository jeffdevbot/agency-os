"""Slack planner runtime flow for AgencyClaw."""

from __future__ import annotations

import asyncio
from typing import Any

from .slack_runtime_deps import SlackPlannerRuntimeDeps


async def try_planner_runtime(
    *,
    text: str,
    slack_user_id: str,
    channel: str,
    session: Any,
    session_service: Any,
    slack: Any,
    deps: SlackPlannerRuntimeDeps,
) -> bool:
    """Attempt planner-driven execution. Returns True when handled."""
    if not deps.is_planner_enabled_fn():
        return False

    try:
        client_context_pack = ""
        if session.active_client_id:
            client_name = await asyncio.to_thread(
                session_service.get_client_name, session.active_client_id,
            )
            client_context_pack = (
                f"Active client: {client_name or 'Unknown'} (id={session.active_client_id})"
            )

        kb_summary = ""
        try:
            db = deps.get_supabase_admin_client_fn()
            retrieval = await deps.retrieve_kb_context_fn(
                query=text,
                client_id=str(session.active_client_id or ""),
                db=db,
            )
            if retrieval["sources"]:
                kb_summary = "\n".join(
                    f"- [{s['tier']}] {s['title']}: {s['content'][:200]}"
                    for s in retrieval["sources"][:3]
                )
        except Exception:  # noqa: BLE001
            pass

        plan = await deps.generate_plan_fn(
            text=text,
            session_context=session.context,
            client_context_pack=client_context_pack,
            kb_context_summary=kb_summary,
        )

        if not plan or not plan["steps"]:
            return False

        async def _planner_cc_step_handler(
            *,
            skill_id: str,
            client_name_hint: str = "",
            plan_args: dict[str, Any] | None = None,
            **_kwargs: Any,
        ) -> None:
            args = dict(plan_args or {})
            if client_name_hint and not args.get("client_name"):
                args["client_name"] = client_name_hint
            await deps.handle_cc_skill_fn(
                skill_id=skill_id,
                args=args,
                session=session,
                session_service=session_service,
                channel=channel,
                slack=slack,
            )

        handler_map = {
            "clickup_task_create": deps.handle_create_task_fn,
            "clickup_task_list_weekly": deps.handle_weekly_tasks_fn,
            "cc_client_lookup": lambda **kwargs: _planner_cc_step_handler(
                skill_id="cc_client_lookup", **kwargs,
            ),
            "cc_brand_list_all": lambda **kwargs: _planner_cc_step_handler(
                skill_id="cc_brand_list_all", **kwargs,
            ),
            "cc_brand_clickup_mapping_audit": lambda **kwargs: _planner_cc_step_handler(
                skill_id="cc_brand_clickup_mapping_audit", **kwargs,
            ),
            "cc_assignment_upsert": lambda **kwargs: _planner_cc_step_handler(
                skill_id="cc_assignment_upsert", **kwargs,
            ),
            "cc_assignment_remove": lambda **kwargs: _planner_cc_step_handler(
                skill_id="cc_assignment_remove", **kwargs,
            ),
            "cc_brand_create": lambda **kwargs: _planner_cc_step_handler(
                skill_id="cc_brand_create", **kwargs,
            ),
            "cc_brand_update": lambda **kwargs: _planner_cc_step_handler(
                skill_id="cc_brand_update", **kwargs,
            ),
        }

        result = await deps.execute_plan_fn(
            plan=plan,
            slack_user_id=slack_user_id,
            channel=channel,
            session=session,
            session_service=session_service,
            slack=slack,
            check_policy=deps.check_skill_policy_fn,
            handler_map=handler_map,
        )

        summary = f"[Planned: {plan['intent']} — {result['steps_succeeded']}/{result['steps_attempted']} steps]"
        recent = session.context.get("recent_exchanges") or []
        updated = deps.append_exchange_fn(recent, text, summary)
        await asyncio.to_thread(
            session_service.update_context, session.id,
            {"recent_exchanges": deps.compact_exchanges_fn(updated)},
        )
        return True
    except Exception:  # noqa: BLE001
        deps.logger.warning("C10D: Planner failed, falling through", exc_info=True)
        return False
