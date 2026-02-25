"""Bridge runtime to keep Slack route file thin while preserving behavior."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


class _CaptureSlack:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def post_message(
        self,
        *,
        channel: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> None:
        _ = channel, blocks
        self.messages.append(text)


@dataclass(frozen=True)
class SlackAgentLoopBridgeRuntimeDeps:
    logger: Any
    get_supabase_admin_client_fn: Callable[[], Any]
    runtime_run_reply_only_agent_loop_turn_fn: Callable[..., Awaitable[bool]]
    check_skill_policy_fn: Callable[..., Awaitable[dict[str, Any]]]
    handle_task_list_fn: Callable[..., Awaitable[None]]
    handle_cc_skill_fn: Callable[..., Awaitable[str | None]]
    lookup_clients_fn: Callable[..., Any]
    format_client_list_fn: Callable[[list[dict[str, Any]]], str]
    list_brands_fn: Callable[..., Any]
    format_brand_list_fn: Callable[[list[dict[str, Any]]], str]
    retrieve_kb_context_fn: Callable[..., Awaitable[dict[str, Any]]]
    preference_memory_service_cls: type[Any]
    resolve_client_for_task_fn: Callable[..., Awaitable[tuple[str | None, str]]]
    resolve_brand_for_task_fn: Callable[..., Awaitable[dict[str, Any]]]
    build_client_context_pack_fn: Callable[..., dict[str, Any]]
    read_evidence_fn: Callable[..., dict[str, Any]]
    agent_loop_store_cls: type[Any]
    enrich_task_draft_fn: Callable[..., Awaitable[dict[str, Any]]]
    execute_task_create_fn: Callable[..., Awaitable[None]]
    execute_planner_delegate_runtime_fn: Callable[..., Awaitable[dict[str, Any]]]
    planner_delegate_runtime_deps_factory: Callable[[Callable[..., Awaitable[dict[str, Any]]]], Any]


async def run_agent_loop_reply_turn_bridge_runtime(
    *,
    text: str,
    session: Any,
    slack_user_id: str,
    session_service: Any,
    channel: str,
    slack: Any,
    deps: SlackAgentLoopBridgeRuntimeDeps,
) -> bool:
    async def _execute_task_list_for_agent_loop(
        *,
        slack_user_id: str,
        channel: str,
        args: dict[str, Any],
        session: Any,
        session_service: Any,
    ) -> dict[str, Any]:
        policy = await deps.check_skill_policy_fn(
            slack_user_id=slack_user_id,
            session=session,
            channel=channel,
            skill_id="clickup_task_list",
            args=args,
        )
        if not policy.get("allowed"):
            return {
                "response_text": str(policy.get("user_message") or "That action is not allowed."),
                "policy_denied": True,
            }

        capture = _CaptureSlack()
        await deps.handle_task_list_fn(
            slack_user_id=slack_user_id,
            channel=channel,
            client_name_hint=str(args.get("client_name") or ""),
            window=str(args.get("window") or ""),
            window_days=args.get("window_days"),
            date_from=str(args.get("date_from") or ""),
            date_to=str(args.get("date_to") or ""),
            session_service=session_service,
            slack=capture,
        )
        return {"response_text": capture.messages[-1] if capture.messages else "No task list response"}

    async def _execute_read_skill_for_agent_loop(
        *,
        skill_id: str,
        slack_user_id: str,
        channel: str,
        args: dict[str, Any],
        session: Any,
        session_service: Any,
    ) -> dict[str, Any]:
        policy = await deps.check_skill_policy_fn(
            slack_user_id=slack_user_id,
            session=session,
            channel=channel,
            skill_id=skill_id,
            args=args,
        )
        if not policy.get("allowed"):
            return {
                "response_text": str(policy.get("user_message") or "That action is not allowed."),
                "policy_denied": True,
            }

        capture = _CaptureSlack()
        if skill_id in {"clickup_task_list", "clickup_task_list_weekly"}:
            await deps.handle_task_list_fn(
                slack_user_id=slack_user_id,
                channel=channel,
                client_name_hint=str(args.get("client_name") or ""),
                window=str(args.get("window") or ""),
                window_days=args.get("window_days"),
                date_from=str(args.get("date_from") or ""),
                date_to=str(args.get("date_to") or ""),
                session_service=session_service,
                slack=capture,
            )
            return {
                "response_text": capture.messages[-1] if capture.messages else "No task list response",
            }

        if skill_id == "cc_client_lookup":
            result_text = await deps.handle_cc_skill_fn(
                skill_id=skill_id,
                args=args,
                session=session,
                session_service=session_service,
                channel=channel,
                slack=capture,
            )
            if capture.messages:
                return {"response_text": capture.messages[-1]}
            return {
                "response_text": (
                    result_text if isinstance(result_text, str) and result_text.strip() else "Read skill completed."
                )
            }

        if skill_id == "lookup_client":
            query = str(args.get("query") or "")
            clients = await asyncio.to_thread(
                deps.lookup_clients_fn,
                session_service.db,
                session.profile_id,
                query,
            )
            return {
                "response_text": deps.format_client_list_fn(clients),
                "clients": clients,
                "query": query,
            }

        if skill_id == "cc_brand_list_all":
            result_text = await deps.handle_cc_skill_fn(
                skill_id=skill_id,
                args=args,
                session=session,
                session_service=session_service,
                channel=channel,
                slack=capture,
            )
            if capture.messages:
                return {"response_text": capture.messages[-1]}
            return {
                "response_text": (
                    result_text if isinstance(result_text, str) and result_text.strip() else "Read skill completed."
                )
            }

        if skill_id == "lookup_brand":
            client_name_hint = str(args.get("client_name") or "").strip()
            brand_name_hint = str(args.get("brand_name") or "").strip().lower()

            client_id: str | None = None
            if client_name_hint:
                matches = await asyncio.to_thread(
                    session_service.find_client_matches, session.profile_id, client_name_hint
                )
                if not matches:
                    return {"response_text": f"I couldn't find a client matching *{client_name_hint}*."}
                if len(matches) > 1:
                    names = ", ".join(str(m.get("name") or "") for m in matches[:5] if isinstance(m, dict))
                    return {"response_text": f"Multiple clients match *{client_name_hint}*: {names}"}
                client_id = str(matches[0].get("id") or "")

            brands = await asyncio.to_thread(
                deps.list_brands_fn, session_service.db, client_id, session.profile_id
            )
            if brand_name_hint:
                brands = [
                    b
                    for b in brands
                    if brand_name_hint in str(b.get("name") or "").strip().lower()
                ]

            return {
                "response_text": deps.format_brand_list_fn(brands),
                "brands": brands,
                "client_id": client_id,
            }

        if skill_id in {"cc_brand_clickup_mapping_audit"}:
            result_text = await deps.handle_cc_skill_fn(
                skill_id=skill_id,
                args=args,
                session=session,
                session_service=session_service,
                channel=channel,
                slack=capture,
            )
            if capture.messages:
                return {"response_text": capture.messages[-1]}
            return {
                "response_text": (
                    result_text if isinstance(result_text, str) and result_text.strip() else "Read skill completed."
                )
            }

        if skill_id == "search_kb":
            query = str(args.get("query") or "")
            brand_name_hint = str(args.get("brand_name") or "").strip()
            client_id: str | None = None
            client_name_hint = str(args.get("client_name") or "").strip()
            if client_name_hint:
                matches = await asyncio.to_thread(
                    session_service.find_client_matches, session.profile_id, client_name_hint
                )
                if len(matches) == 1:
                    client_id = str(matches[0].get("id") or "")
            scoped_query = query
            if brand_name_hint:
                scoped_query = f"{query} brand:{brand_name_hint}".strip()
            retrieval = await deps.retrieve_kb_context_fn(
                query=scoped_query,
                client_id=client_id,
                skill_id=skill_id,
                db=session_service.db,
                max_chars=1200,
            )
            sources = retrieval.get("sources") if isinstance(retrieval, dict) else []
            if not isinstance(sources, list) or not sources:
                return {
                    "response_text": "I couldn't find relevant knowledge-base context for that query.",
                    "kb_sources": [],
                }
            top_titles = [
                str(src.get("title") or "Untitled source")
                for src in sources[:3]
                if isinstance(src, dict)
            ]
            return {
                "response_text": "Found KB context from: " + "; ".join(top_titles),
                "kb_sources": sources[:5],
                "tiers_hit": retrieval.get("tiers_hit", []),
                "query_used": scoped_query,
            }

        if skill_id == "resolve_brand":
            task_text = str(args.get("task_text") or "").strip()
            brand_hint = str(args.get("brand_hint") or "")
            pref_service = deps.preference_memory_service_cls(session_service.db)
            client_id, client_name = await deps.resolve_client_for_task_fn(
                client_name_hint=str(args.get("client_name") or "").strip(),
                session=session,
                session_service=session_service,
                channel=channel,
                slack=capture,
                pref_service=pref_service,
            )
            if not client_id:
                return {
                    "response_text": capture.messages[-1] if capture.messages else "Could not resolve client context.",
                }
            resolution = await deps.resolve_brand_for_task_fn(
                client_id=client_id,
                client_name=client_name,
                task_text=task_text,
                brand_hint=brand_hint,
                session=session,
                session_service=session_service,
                channel=channel,
                slack=capture,
            )
            if capture.messages:
                response_text = capture.messages[-1]
            else:
                response_text = f"Brand resolution mode: {resolution.get('mode', 'unknown')}."
            return {
                "response_text": response_text,
                "resolution": resolution,
                "client_id": client_id,
                "client_name": client_name,
            }

        if skill_id == "get_client_context":
            client_name_hint = str(args.get("client_name") or "").strip()
            matches = await asyncio.to_thread(
                session_service.find_client_matches, session.profile_id, client_name_hint
            )
            if not matches:
                return {"response_text": f"I couldn't find a client matching *{client_name_hint}*."}
            if len(matches) > 1:
                names = ", ".join(str(m.get("name") or "") for m in matches[:5] if isinstance(m, dict))
                return {"response_text": f"Multiple clients match *{client_name_hint}*: {names}"}
            client_id = str(matches[0].get("id") or "")
            client_name = str(matches[0].get("name") or client_name_hint)
            brands = await asyncio.to_thread(
                deps.list_brands_fn, session_service.db, client_id, session.profile_id
            )
            brand_lines = [
                f"{str(b.get('name') or 'Brand')} (space={b.get('clickup_space_id') or '-'}, list={b.get('clickup_list_id') or '-'})"
                for b in brands[:12]
                if isinstance(b, dict)
            ]
            recent_events = []
            recent_exchanges = session.context.get("recent_exchanges") if isinstance(session.context, dict) else []
            if isinstance(recent_exchanges, list):
                for item in recent_exchanges[-5:]:
                    if not isinstance(item, dict):
                        continue
                    user_text = str(item.get("user") or "").strip()
                    assistant_text = str(item.get("assistant") or "").strip()
                    if user_text:
                        recent_events.append(f"user: {user_text}")
                    if assistant_text:
                        recent_events.append(f"assistant: {assistant_text}")

            context_pack = deps.build_client_context_pack_fn(
                {
                    "assignments": [],
                    "kpi_targets": [],
                    "active_tasks": brand_lines,
                    "completed_tasks": [],
                    "sop_slices": [],
                    "recent_events": recent_events,
                    "freshness_context": {"client_id": client_id, "client_name": client_name},
                },
                max_tokens=700,
            )
            context_text = str(context_pack.get("context_text") or "").strip()
            if not context_text:
                context_text = f"No detailed context available for {client_name}."
            return {
                "response_text": context_text,
                "client_context": context_pack,
                "client_id": client_id,
                "client_name": client_name,
            }

        if skill_id == "load_prior_skill_result":
            key = str(args.get("key") or "").strip()
            evidence = await asyncio.to_thread(
                deps.read_evidence_fn,
                deps.agent_loop_store_cls(deps.get_supabase_admin_client_fn()),
                key,
            )
            if evidence.get("ok"):
                summary = str(evidence.get("payload_summary") or "").strip()
                note = str(evidence.get("note") or "").strip()
                response_text = note or summary or "Loaded prior skill result."
            else:
                err = str(evidence.get("error") or "unknown_error")
                if err == "invalid_key":
                    response_text = "I couldn't load that prior result because the key format is invalid."
                elif err == "not_found":
                    response_text = "I couldn't find a prior result for that key."
                else:
                    response_text = "I couldn't load that prior result."
            return {
                "response_text": response_text,
                "evidence": evidence,
            }

        raise ValueError(f"unsupported read skill in agent loop: {skill_id}")

    async def _execute_create_task_for_agent_loop(
        *,
        slack_user_id: str,
        channel: str,
        args: dict[str, Any],
        session: Any,
        session_service: Any,
    ) -> dict[str, Any]:
        capture = _CaptureSlack()
        pref_service = deps.preference_memory_service_cls(session_service.db)
        client_id, client_name = await deps.resolve_client_for_task_fn(
            client_name_hint=str(args.get("client_name") or ""),
            session=session,
            session_service=session_service,
            channel=channel,
            slack=capture,
            pref_service=pref_service,
        )
        if not client_id:
            return {"response_text": capture.messages[-1] if capture.messages else "Could not resolve client."}

        task_title = str(args.get("task_title") or "").strip()
        if not task_title:
            return {"response_text": "I need a task title before I can create a task."}

        resolution = await deps.resolve_brand_for_task_fn(
            client_id=client_id,
            client_name=client_name,
            task_text=task_title,
            brand_hint=str(args.get("brand_name") or ""),
            session=session,
            session_service=session_service,
            channel=channel,
            slack=capture,
        )
        if resolution["mode"] == "no_destination":
            return {
                "response_text": capture.messages[-1] if capture.messages else "No ClickUp destination found."
            }
        if resolution["mode"] in ("ambiguous_brand", "ambiguous_destination"):
            return {
                "response_text": capture.messages[-1] if capture.messages else "Brand mapping is ambiguous."
            }

        brand_ctx = resolution["brand_context"]
        brand_id = str(brand_ctx["id"]) if brand_ctx else None
        brand_name = str(brand_ctx["name"]) if brand_ctx else None
        draft = await deps.enrich_task_draft_fn(
            task_title=task_title,
            client_id=client_id,
            client_name=client_name,
        )
        task_description = str(args.get("task_description") or "")
        if not task_description and isinstance(draft, dict):
            task_description = str(draft.get("description_md") or "")

        await deps.execute_task_create_fn(
            channel=channel,
            session=session,
            session_service=session_service,
            slack=capture,
            client_id=client_id,
            client_name=client_name,
            task_title=task_title,
            task_description=task_description,
            brand_id=brand_id,
            brand_name=brand_name,
        )
        return {"response_text": capture.messages[-1] if capture.messages else "Task request processed."}

    async def _execute_planner_delegate_for_agent_loop(
        *,
        request_text: str,
        slack_user_id: str,
        channel: str,
        session: Any,
        session_service: Any,
        parent_run_id: str,
        child_run_id: str,
        trace_id: str,
        tool_executor: Callable[..., Awaitable[dict[str, Any]]] | None = None,
        execute_skill_fn: Callable[..., Awaitable[dict[str, Any]]] | None = None,
        max_planner_turns: int = 6,
        max_turns: int | None = None,
    ) -> dict[str, Any]:
        delegate_deps = deps.planner_delegate_runtime_deps_factory(
            _execute_read_skill_for_agent_loop,
        )
        return await deps.execute_planner_delegate_runtime_fn(
            request_text=request_text,
            slack_user_id=slack_user_id,
            channel=channel,
            session=session,
            session_service=session_service,
            parent_run_id=parent_run_id,
            child_run_id=child_run_id,
            trace_id=trace_id,
            tool_executor=tool_executor,
            execute_skill_fn=execute_skill_fn,
            max_planner_turns=max_planner_turns,
            max_turns=max_turns,
            deps=delegate_deps,
        )

    return await deps.runtime_run_reply_only_agent_loop_turn_fn(
        text=text,
        session=session,
        slack_user_id=slack_user_id,
        session_service=session_service,
        channel=channel,
        slack=slack,
        supabase_client=deps.get_supabase_admin_client_fn(),
        execute_read_skill_fn=_execute_read_skill_for_agent_loop,
        execute_delegate_planner_fn=_execute_planner_delegate_for_agent_loop,
        execute_task_list_fn=_execute_task_list_for_agent_loop,
        execute_create_task_fn=_execute_create_task_for_agent_loop,
        check_mutation_policy_fn=deps.check_skill_policy_fn,
        logger=deps.logger,
    )
