"""Route-layer runtime wiring for Slack DM/interaction handlers.

Keeps API route module thin while preserving existing wrapper seams.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from .slack_agent_loop_bridge_runtime import (
    SlackAgentLoopBridgeRuntimeDeps,
    run_agent_loop_reply_turn_bridge_runtime,
)
from .slack_dm_runtime import handle_dm_event_runtime
from .slack_interaction_runtime import handle_interaction_runtime
from .slack_runtime_deps import (
    SlackDMRuntimeDeps,
    SlackInteractionRuntimeDeps,
)


@dataclass(frozen=True)
class SlackRouteRuntimeDeps:
    logger: Any
    get_supabase_admin_client_fn: Callable[[], Any]
    runtime_run_reply_only_agent_loop_turn_fn: Callable[..., Awaitable[bool]]
    check_skill_policy_fn: Callable[..., Awaitable[dict[str, Any]]]
    handle_task_list_fn: Callable[..., Awaitable[None]]
    handle_cc_skill_fn: Callable[..., Awaitable[str]]
    lookup_clients_fn: Callable[..., Any]
    format_client_list_fn: Callable[..., str]
    list_brands_fn: Callable[..., Any]
    format_brand_list_fn: Callable[..., str]
    retrieve_kb_context_fn: Callable[..., Awaitable[dict[str, Any]]]
    preference_memory_service_cls: type[Any]
    resolve_client_for_task_fn: Callable[..., Awaitable[tuple[str | None, str]]]
    resolve_brand_for_task_fn: Callable[..., Awaitable[dict[str, Any]]]
    build_client_context_pack_fn: Callable[..., dict[str, Any]]
    read_evidence_fn: Callable[..., dict[str, Any]]
    agent_loop_store_cls: type[Any]
    enrich_task_draft_fn: Callable[..., Awaitable[dict[str, Any] | None]]
    execute_task_create_fn: Callable[..., Awaitable[None]]
    execute_planner_delegate_runtime_fn: Callable[..., Awaitable[dict[str, Any]]]
    planner_delegate_runtime_deps_factory: Callable[[Callable[..., Awaitable[dict[str, Any]]]], Any]

    get_session_service_fn: Callable[[], Any]
    get_slack_service_fn: Callable[[], Any]
    is_agent_loop_enabled_fn: Callable[[], bool]
    handle_pending_task_continuation_fn: Callable[..., Awaitable[bool]]
    is_llm_orchestrator_enabled_fn: Callable[[], bool]
    try_llm_orchestrator_fn: Callable[..., Awaitable[bool]]
    classify_message_fn: Callable[[str], tuple[str, str, str]]
    should_block_deterministic_intent_fn: Callable[[str], bool]
    handle_create_task_fn: Callable[..., Awaitable[None]]
    help_text_fn: Callable[[], str]
    build_client_picker_blocks_fn: Callable[[list[dict[str, Any]]], list[dict[str, Any]]]
    slack_api_error_cls: type[Exception]

    get_receipt_service_fn: Callable[[], Any]


async def handle_dm_event_route_runtime(
    *,
    slack_user_id: str,
    channel: str,
    text: str,
    deps: SlackRouteRuntimeDeps,
) -> None:
    async def _run_agent_loop_reply_turn(
        *,
        text: str,
        session: Any,
        slack_user_id: str,
        session_service: Any,
        channel: str,
        slack: Any,
    ) -> bool:
        bridge_deps = SlackAgentLoopBridgeRuntimeDeps(
            logger=deps.logger,
            get_supabase_admin_client_fn=deps.get_supabase_admin_client_fn,
            runtime_run_reply_only_agent_loop_turn_fn=deps.runtime_run_reply_only_agent_loop_turn_fn,
            check_skill_policy_fn=deps.check_skill_policy_fn,
            handle_task_list_fn=deps.handle_task_list_fn,
            handle_cc_skill_fn=deps.handle_cc_skill_fn,
            lookup_clients_fn=deps.lookup_clients_fn,
            format_client_list_fn=deps.format_client_list_fn,
            list_brands_fn=deps.list_brands_fn,
            format_brand_list_fn=deps.format_brand_list_fn,
            retrieve_kb_context_fn=deps.retrieve_kb_context_fn,
            preference_memory_service_cls=deps.preference_memory_service_cls,
            resolve_client_for_task_fn=deps.resolve_client_for_task_fn,
            resolve_brand_for_task_fn=deps.resolve_brand_for_task_fn,
            build_client_context_pack_fn=deps.build_client_context_pack_fn,
            read_evidence_fn=deps.read_evidence_fn,
            agent_loop_store_cls=deps.agent_loop_store_cls,
            enrich_task_draft_fn=deps.enrich_task_draft_fn,
            execute_task_create_fn=deps.execute_task_create_fn,
            execute_planner_delegate_runtime_fn=deps.execute_planner_delegate_runtime_fn,
            planner_delegate_runtime_deps_factory=deps.planner_delegate_runtime_deps_factory,
        )
        return await run_agent_loop_reply_turn_bridge_runtime(
            text=text,
            session=session,
            slack_user_id=slack_user_id,
            session_service=session_service,
            channel=channel,
            slack=slack,
            deps=bridge_deps,
        )

    dm_deps = SlackDMRuntimeDeps(
        get_session_service_fn=deps.get_session_service_fn,
        get_slack_service_fn=deps.get_slack_service_fn,
        preference_memory_service_factory=deps.preference_memory_service_cls,
        is_agent_loop_enabled_fn=deps.is_agent_loop_enabled_fn,
        run_agent_loop_reply_fn=_run_agent_loop_reply_turn,
        handle_pending_task_continuation_fn=deps.handle_pending_task_continuation_fn,
        is_llm_orchestrator_enabled_fn=deps.is_llm_orchestrator_enabled_fn,
        try_llm_orchestrator_fn=deps.try_llm_orchestrator_fn,
        classify_message_fn=deps.classify_message_fn,
        should_block_deterministic_intent_fn=deps.should_block_deterministic_intent_fn,
        check_skill_policy_fn=deps.check_skill_policy_fn,
        handle_create_task_fn=deps.handle_create_task_fn,
        handle_task_list_fn=deps.handle_task_list_fn,
        help_text_fn=deps.help_text_fn,
        build_client_picker_blocks_fn=deps.build_client_picker_blocks_fn,
        handle_cc_skill_fn=deps.handle_cc_skill_fn,
        logger=deps.logger,
        slack_api_error_cls=deps.slack_api_error_cls,
    )
    await handle_dm_event_runtime(
        slack_user_id=slack_user_id,
        channel=channel,
        text=text,
        deps=dm_deps,
    )


async def handle_interaction_route_runtime(
    payload: dict[str, Any],
    *,
    deps: SlackRouteRuntimeDeps,
) -> None:
    interaction_deps = SlackInteractionRuntimeDeps(
        get_receipt_service_fn=deps.get_receipt_service_fn,
        get_session_service_fn=deps.get_session_service_fn,
        get_slack_service_fn=deps.get_slack_service_fn,
        handle_pending_task_continuation_fn=deps.handle_pending_task_continuation_fn,
        logger=deps.logger,
        slack_api_error_cls=deps.slack_api_error_cls,
    )
    await handle_interaction_runtime(payload, deps=interaction_deps)
