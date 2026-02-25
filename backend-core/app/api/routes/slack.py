import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse

from ...services.agencyclaw import orchestrate_dm_message
from ...services.agencyclaw.conversation_buffer import append_exchange, compact_exchanges
from ...services.agencyclaw.policy_gate import (
    evaluate_skill_policy,
    resolve_actor_context,
    resolve_surface_context,
)
from ...services.agencyclaw.brand_context_resolver import (
    BrandResolution,
)
from ...services.agencyclaw.brand_mapping_remediation import (
    apply_brand_mapping_remediation_plan,
    build_brand_mapping_remediation_plan,
)
from ...services.agencyclaw.command_center_assignments import (
    format_person_ambiguous,
    format_remove_result,
    format_upsert_result,
    remove_assignment,
    resolve_brand_for_assignment,
    resolve_person,
    resolve_role,
    upsert_assignment,
)
from ...services.agencyclaw.command_center_brand_mutations import (
    create_brand,
    format_brand_ambiguous,
    format_brand_create_result,
    format_brand_update_result,
    resolve_brand_for_mutation,
    update_brand,
)
from ...services.agencyclaw.command_center_lookup import (
    audit_brand_mappings,
    format_brand_list,
    format_client_list,
    format_mapping_audit,
    list_brands,
    lookup_clients,
)
from ...services.agencyclaw.grounded_task_draft import build_grounded_task_draft
from ...services.agencyclaw.kb_retrieval import retrieve_kb_context
from ...services.agencyclaw.client_context_builder import build_client_context_pack
from ...services.agencyclaw.agent_loop_evidence_reader import read_evidence
from ...services.agencyclaw.agent_loop_store import AgentLoopStore
from ...services.agencyclaw.agent_loop_turn_logger import AgentLoopTurnLogger
from ...services.agencyclaw.slack_pending_flow import (
    compose_asin_pending_description as _pending_flow_compose_asin_pending_description,
    handle_pending_task_continuation as _pending_flow_handle_pending_task_continuation,
)
from ...services.agencyclaw.slack_planner_runtime import (
    try_planner_runtime as _runtime_try_planner,
)
from ...services.agencyclaw.slack_orchestrator_runtime import (
    try_llm_orchestrator_runtime as _runtime_try_llm_orchestrator,
)
from ...services.agencyclaw.agent_loop_runtime import (
    run_reply_only_agent_loop_turn as _runtime_run_reply_only_agent_loop_turn,
)
from ...services.agencyclaw.slack_planner_delegate_runtime import execute_planner_delegate_for_agent_loop_runtime
from ...services.agencyclaw.slack_resolution_runtime import (
    resolve_brand_for_task_runtime,
    resolve_client_for_task_runtime,
)
from ...services.agencyclaw.slack_route_helpers import (
    build_brand_picker_blocks as _build_brand_picker_blocks,
    build_client_picker_blocks as _build_client_picker_blocks,
    parse_interaction_payload as _parse_interaction_payload,
    parse_json_payload as _parse_json,
    verify_request_or_401 as _verify_request_or_401,
)
from ...services.agencyclaw.slack_route_runtime import (
    SlackRouteRuntimeDeps,
    handle_dm_event_route_runtime,
    handle_interaction_route_runtime,
)
from ...services.agencyclaw.slack_debug_route_runtime import (
    handle_debug_chat_route_runtime,
)
from ...services.agencyclaw.slack_route_deps_runtime import build_route_runtime_deps_runtime
from ...services.agencyclaw.slack_route_deps_runtime import (
    build_cc_bridge_deps_from_bindings_runtime,
    build_task_bridge_deps_from_bindings_runtime,
)
from ...services.agencyclaw.slack_policy_bridge_runtime import (
    SlackPolicyBridgeRuntimeDeps,
    check_skill_policy_runtime,
    is_agent_loop_enabled_runtime,
    is_llm_strict_mode_runtime,
    is_planner_enabled_runtime,
)
from ...services.agencyclaw.slack_runtime_deps import (
    SlackOrchestratorRuntimeDeps,
    SlackPlannerRuntimeDeps,
)
from ...services.agencyclaw.plan_executor import execute_plan
from ...services.agencyclaw.planner import generate_plan
from ...services.agencyclaw.skill_registry import get_skill_descriptions_for_prompt
from ...services.agencyclaw.slack_cc_bridge_runtime import (
    format_remediation_apply_result_bridge_runtime,
    format_remediation_preview_bridge_runtime,
    handle_cc_skill_bridge_runtime,
    resolve_assignment_client_bridge_runtime,
    resolve_cc_client_hint_bridge_runtime,
)
from ...services.agencyclaw.slack_task_bridge_runtime import (
    enrich_task_draft_bridge_runtime,
    execute_task_create_bridge_runtime,
    handle_create_task_bridge_runtime,
    handle_task_list_bridge_runtime,
)
from ...services.agencyclaw.slack_helpers import (
    _WEEKLY_TASK_CAP,
    _classify_message,
    _current_week_range_ms,
    _extract_product_identifiers,
    _format_task_list_response,
    _format_task_line,
    _format_weekly_tasks_response,
    _help_text,
    _is_deterministic_control_intent as _helpers_is_deterministic_control_intent,
    _is_legacy_intent_fallback_enabled as _helpers_is_legacy_intent_fallback_enabled,
    _is_llm_orchestrator_enabled as _helpers_is_llm_orchestrator_enabled,
    _resolve_task_range,
    _sanitize_client_name_hint,
)
from ...services.agencyclaw.clickup_reliability import (
    RetryExhaustedError,
    build_idempotency_key,
    check_duplicate,
    emit_orphan_event,
    retry_with_backoff,
)
from ...services.ai_token_usage_logger import log_ai_token_usage
from ...services.agencyclaw.preference_memory import PreferenceMemoryService
from ...services.playbook_session import get_playbook_session_service, get_supabase_admin_client
from ...services.clickup import ClickUpError, ClickUpConfigurationError, get_clickup_service
from ...services.slack import (
    SlackAPIError,
    SlackReceiptService,
    get_slack_service,
    get_slack_signing_secret,
)

_logger = logging.getLogger(__name__)

# C4C: In-memory concurrency guard for task mutations.
# Prevents two simultaneous creates for the same target from racing past
# the duplicate check.  Single-process only; see plan for multi-worker TODO.
_task_create_inflight: set[str] = set()
_task_create_inflight_lock = asyncio.Lock()

router = APIRouter(prefix="/slack", tags=["slack"])

def _build_policy_bridge_deps() -> SlackPolicyBridgeRuntimeDeps:
    return SlackPolicyBridgeRuntimeDeps(
        get_supabase_admin_client_fn=get_supabase_admin_client,
        resolve_actor_context_fn=resolve_actor_context,
        resolve_surface_context_fn=resolve_surface_context,
        evaluate_skill_policy_fn=evaluate_skill_policy,
        is_llm_orchestrator_enabled_fn=_is_llm_orchestrator_enabled,
        is_legacy_intent_fallback_enabled_fn=_is_legacy_intent_fallback_enabled,
        is_deterministic_control_intent_fn=_is_deterministic_control_intent,
    )


def _is_llm_orchestrator_enabled() -> bool:
    return _helpers_is_llm_orchestrator_enabled()


def _is_agent_loop_enabled() -> bool:
    return is_agent_loop_enabled_runtime()


def _is_planner_enabled() -> bool:
    """Check if the C10D planner feature flag is enabled."""
    return is_planner_enabled_runtime()


def _is_legacy_intent_fallback_enabled() -> bool:
    return _helpers_is_legacy_intent_fallback_enabled()


def _is_llm_strict_mode() -> bool:
    return is_llm_strict_mode_runtime(_build_policy_bridge_deps())


def _is_deterministic_control_intent(intent: str) -> bool:
    return _helpers_is_deterministic_control_intent(intent)


def _should_block_deterministic_intent(intent: str) -> bool:
    return _is_llm_strict_mode() and not _is_deterministic_control_intent(intent)


def _get_receipt_service() -> SlackReceiptService:
    return SlackReceiptService(get_supabase_admin_client())

def _build_task_bridge_deps():
    return build_task_bridge_deps_from_bindings_runtime(
        bindings=globals(),
        inflight_lock=_task_create_inflight_lock,
        inflight_set=_task_create_inflight,
        logger=_logger,
        build_client_picker_blocks_fn=_build_client_picker_blocks,
        get_supabase_admin_client_fn=get_supabase_admin_client,
        resolve_client_for_task_fn=_resolve_client_for_task,
        resolve_brand_for_task_fn=_resolve_brand_for_task,
    )

def _build_cc_bridge_deps():
    return build_cc_bridge_deps_from_bindings_runtime(
        bindings=globals(),
        build_client_picker_blocks_fn=_build_client_picker_blocks,
    )


async def _handle_task_list(
    *,
    slack_user_id: str,
    channel: str,
    client_name_hint: str,
    session_service: Any,
    slack: Any,
    window: str = "",
    window_days: Any = None,
    date_from: str = "",
    date_to: str = "",
) -> None:
    await handle_task_list_bridge_runtime(
        slack_user_id=slack_user_id,
        channel=channel,
        client_name_hint=client_name_hint,
        session_service=session_service,
        slack=slack,
        deps=_build_task_bridge_deps(),
        window=window,
        window_days=window_days,
        date_from=date_from,
        date_to=date_to,
    )


async def _handle_weekly_tasks(
    *,
    slack_user_id: str,
    channel: str,
    client_name_hint: str,
    session_service: Any,
    slack: Any,
    window: str = "",
    window_days: Any = None,
    date_from: str = "",
    date_to: str = "",
) -> None:
    """Compatibility wrapper for legacy weekly handler call sites."""
    await _handle_task_list(
        slack_user_id=slack_user_id,
        channel=channel,
        client_name_hint=client_name_hint,
        session_service=session_service,
        slack=slack,
        window=window or "this_week",
        window_days=window_days,
        date_from=date_from,
        date_to=date_to,
    )


async def _resolve_client_for_task(
    *,
    client_name_hint: str,
    session: Any,
    session_service: Any,
    channel: str,
    slack: Any,
    pref_service: Any | None = None,
) -> tuple[str | None, str]:
    return await resolve_client_for_task_runtime(
        client_name_hint=client_name_hint,
        session=session,
        session_service=session_service,
        channel=channel,
        slack=slack,
        pref_service=pref_service,
        build_client_picker_blocks_fn=_build_client_picker_blocks,
    )


# ---------------------------------------------------------------------------
# C11D: Brand context resolution helper
# ---------------------------------------------------------------------------


async def _resolve_brand_for_task(
    *,
    client_id: str,
    client_name: str,
    task_text: str,
    brand_hint: str,
    session: Any,
    session_service: Any,
    channel: str,
    slack: Any,
) -> BrandResolution:
    return await resolve_brand_for_task_runtime(
        client_id=client_id,
        client_name=client_name,
        task_text=task_text,
        brand_hint=brand_hint,
        session=session,
        session_service=session_service,
        channel=channel,
        slack=slack,
        build_brand_picker_blocks_fn=_build_brand_picker_blocks,
    )


# ---------------------------------------------------------------------------
# C11A: Command Center read-only skill handler
# ---------------------------------------------------------------------------


async def _resolve_cc_client_hint(
    *,
    args: dict[str, Any],
    session_service: Any,
    session: Any,
    channel: str,
    slack: Any,
    build_client_picker_blocks: Any | None = None,
) -> str | None | bool:
    return await resolve_cc_client_hint_bridge_runtime(
        args=args,
        session_service=session_service,
        session=session,
        channel=channel,
        slack=slack,
        deps=_build_cc_bridge_deps(),
        build_client_picker_blocks=build_client_picker_blocks,
    )


async def _resolve_assignment_client(
    *,
    args: dict[str, Any],
    session_service: Any,
    session: Any,
    channel: str,
    slack: Any,
) -> str | bool:
    return await resolve_assignment_client_bridge_runtime(
        args=args,
        session_service=session_service,
        session=session,
        channel=channel,
        slack=slack,
        deps=_build_cc_bridge_deps(),
    )


def _format_remediation_preview(plan: list[dict[str, Any]]) -> str:
    return format_remediation_preview_bridge_runtime(plan)


def _format_remediation_apply_result(result: dict[str, Any]) -> str:
    return format_remediation_apply_result_bridge_runtime(result)


async def _handle_cc_skill(
    *,
    skill_id: str,
    args: dict[str, Any],
    session: Any,
    session_service: Any,
    channel: str,
    slack: Any,
) -> str:
    return await handle_cc_skill_bridge_runtime(
        skill_id=skill_id,
        args=args,
        session=session,
        session_service=session_service,
        channel=channel,
        slack=slack,
        deps=_build_cc_bridge_deps(),
    )


async def _execute_task_create(
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
) -> None:
    await execute_task_create_bridge_runtime(
        channel=channel,
        session=session,
        session_service=session_service,
        slack=slack,
        client_id=client_id,
        client_name=client_name,
        task_title=task_title,
        task_description=task_description,
        brand_id=brand_id,
        brand_name=brand_name,
        deps=_build_task_bridge_deps(),
    )


async def _handle_create_task(
    *,
    slack_user_id: str,
    channel: str,
    client_name_hint: str,
    task_title: str,
    session_service: Any,
    slack: Any,
    pref_service: Any | None = None,
) -> None:
    await handle_create_task_bridge_runtime(
        slack_user_id=slack_user_id,
        channel=channel,
        client_name_hint=client_name_hint,
        task_title=task_title,
        session_service=session_service,
        slack=slack,
        pref_service=pref_service,
        deps=_build_task_bridge_deps(),
    )


async def _try_planner(
    *,
    text: str,
    slack_user_id: str,
    channel: str,
    session: Any,
    session_service: Any,
    slack: Any,
) -> bool:
    planner_deps = SlackPlannerRuntimeDeps(
        logger=_logger,
        is_planner_enabled_fn=_is_planner_enabled,
        get_supabase_admin_client_fn=get_supabase_admin_client,
        retrieve_kb_context_fn=retrieve_kb_context,
        generate_plan_fn=generate_plan,
        execute_plan_fn=execute_plan,
        check_skill_policy_fn=_check_skill_policy,
        handle_create_task_fn=_handle_create_task,
        handle_task_list_fn=_handle_task_list,
        handle_cc_skill_fn=_handle_cc_skill,
        append_exchange_fn=append_exchange,
        compact_exchanges_fn=compact_exchanges,
    )
    return await _runtime_try_planner(
        text=text,
        slack_user_id=slack_user_id,
        channel=channel,
        session=session,
        session_service=session_service,
        slack=slack,
        deps=planner_deps,
    )


async def _enrich_task_draft(
    *,
    task_title: str,
    client_id: str,
    client_name: str,
) -> dict[str, Any] | None:
    return await enrich_task_draft_bridge_runtime(
        task_title=task_title,
        client_id=client_id,
        client_name=client_name,
        deps=_build_task_bridge_deps(),
    )


def _compose_asin_pending_description(stashed_draft: dict[str, Any] | None) -> str:
    return _pending_flow_compose_asin_pending_description(stashed_draft)


async def _handle_pending_task_continuation(
    *,
    channel: str,
    text: str,
    session: Any,
    session_service: Any,
    slack: Any,
    pending: dict[str, Any],
) -> bool:
    return await _pending_flow_handle_pending_task_continuation(
        channel=channel,
        text=text,
        session=session,
        session_service=session_service,
        slack=slack,
        pending=pending,
        classify_message=_classify_message,
        resolve_brand_for_task=_resolve_brand_for_task,
        enrich_task_draft=_enrich_task_draft,
        execute_task_create=_execute_task_create,
        extract_product_identifiers=_extract_product_identifiers,
    )


async def _try_llm_orchestrator(
    *,
    text: str,
    slack_user_id: str,
    channel: str,
    session: Any,
    session_service: Any,
    slack: Any,
) -> bool:
    orchestrator_deps = SlackOrchestratorRuntimeDeps(
        logger=_logger,
        orchestrate_dm_message_fn=orchestrate_dm_message,
        log_ai_token_usage_fn=log_ai_token_usage,
        check_skill_policy_fn=_check_skill_policy,
        handle_task_list_fn=_handle_task_list,
        handle_create_task_fn=_handle_create_task,
        handle_cc_skill_fn=_handle_cc_skill,
        resolve_client_for_task_fn=_resolve_client_for_task,
        resolve_brand_for_task_fn=_resolve_brand_for_task,
        preference_memory_service_factory=PreferenceMemoryService,
        try_planner_fn=_try_planner,
        classify_message_fn=_classify_message,
        is_deterministic_control_intent_fn=_is_deterministic_control_intent,
    )
    return await _runtime_try_llm_orchestrator(
        text=text,
        slack_user_id=slack_user_id,
        channel=channel,
        session=session,
        session_service=session_service,
        slack=slack,
        deps=orchestrator_deps,
    )


async def _check_skill_policy(
    *,
    slack_user_id: str,
    session: Any,
    channel: str,
    skill_id: str,
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """C10A: Resolve actor/surface and evaluate skill policy.

    Returns the PolicyDecision dict.  Caller should check ``allowed`` and
    post ``user_message`` on deny.
    """
    return await check_skill_policy_runtime(
        slack_user_id=slack_user_id,
        session=session,
        channel=channel,
        skill_id=skill_id,
        args=args,
        deps=_build_policy_bridge_deps(),
    )

def _build_route_runtime_deps() -> SlackRouteRuntimeDeps:
    return build_route_runtime_deps_runtime(
        logger=_logger,
        get_supabase_admin_client_fn=get_supabase_admin_client,
        runtime_run_reply_only_agent_loop_turn_fn=_runtime_run_reply_only_agent_loop_turn,
        check_skill_policy_fn=_check_skill_policy,
        handle_task_list_fn=_handle_task_list,
        handle_cc_skill_fn=_handle_cc_skill,
        lookup_clients_fn=lookup_clients,
        format_client_list_fn=format_client_list,
        list_brands_fn=list_brands,
        format_brand_list_fn=format_brand_list,
        retrieve_kb_context_fn=retrieve_kb_context,
        preference_memory_service_cls=PreferenceMemoryService,
        resolve_client_for_task_fn=_resolve_client_for_task,
        resolve_brand_for_task_fn=_resolve_brand_for_task,
        build_client_context_pack_fn=build_client_context_pack,
        read_evidence_fn=read_evidence,
        agent_loop_store_cls=AgentLoopStore,
        enrich_task_draft_fn=_enrich_task_draft,
        execute_task_create_fn=_execute_task_create,
        execute_planner_delegate_runtime_fn=execute_planner_delegate_for_agent_loop_runtime,
        generate_plan_fn=generate_plan,
        execute_plan_fn=execute_plan,
        get_skill_descriptions_for_prompt_fn=get_skill_descriptions_for_prompt,
        agent_loop_turn_logger_cls=AgentLoopTurnLogger,
        get_session_service_fn=get_playbook_session_service,
        get_slack_service_fn=get_slack_service,
        is_agent_loop_enabled_fn=_is_agent_loop_enabled,
        handle_pending_task_continuation_fn=_handle_pending_task_continuation,
        is_llm_orchestrator_enabled_fn=_is_llm_orchestrator_enabled,
        try_llm_orchestrator_fn=_try_llm_orchestrator,
        classify_message_fn=_classify_message,
        should_block_deterministic_intent_fn=_should_block_deterministic_intent,
        handle_create_task_fn=_handle_create_task,
        help_text_fn=_help_text,
        build_client_picker_blocks_fn=_build_client_picker_blocks,
        slack_api_error_cls=SlackAPIError,
        get_receipt_service_fn=_get_receipt_service,
    )


async def _handle_dm_event(*, slack_user_id: str, channel: str, text: str) -> None:
    await handle_dm_event_route_runtime(
        slack_user_id=slack_user_id,
        channel=channel,
        text=text,
        deps=_build_route_runtime_deps(),
    )


async def _handle_interaction(payload: dict[str, Any]) -> None:
    await handle_interaction_route_runtime(
        payload,
        deps=_build_route_runtime_deps(),
    )


@router.post("/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    signing_secret = get_slack_signing_secret().strip()
    if not signing_secret:
        raise HTTPException(status_code=500, detail="SLACK_SIGNING_SECRET not set")

    body = await request.body()
    _verify_request_or_401(signing_secret=signing_secret, request=request, body=body)

    # If Slack retries a delivery, avoid duplicating side effects.
    if request.headers.get("X-Slack-Retry-Num"):
        return JSONResponse({"ok": True})

    payload = _parse_json(body)

    if payload.get("type") == "url_verification":
        challenge = payload.get("challenge")
        if not isinstance(challenge, str) or not challenge:
            raise HTTPException(status_code=400, detail="Missing Slack challenge")
        return JSONResponse({"challenge": challenge})

    if payload.get("type") == "event_callback":
        event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
        if (
            event.get("type") == "message"
            and event.get("channel_type") == "im"
            and not event.get("bot_id")
            and not event.get("subtype")
        ):
            channel = str(event.get("channel") or "").strip()
            text = str(event.get("text") or "")
            slack_user_id = str(event.get("user") or "").strip()
            if channel and text and slack_user_id:
                background_tasks.add_task(
                    _handle_dm_event,
                    slack_user_id=slack_user_id,
                    channel=channel,
                    text=text,
                )

    return JSONResponse({"ok": True})


@router.post("/interactions")
async def slack_interactions(request: Request, background_tasks: BackgroundTasks):
    signing_secret = get_slack_signing_secret().strip()
    if not signing_secret:
        raise HTTPException(status_code=500, detail="SLACK_SIGNING_SECRET not set")

    body = await request.body()
    _verify_request_or_401(signing_secret=signing_secret, request=request, body=body)

    interaction = _parse_interaction_payload(body)
    if interaction:
        background_tasks.add_task(_handle_interaction, interaction)

    return JSONResponse({"ok": True})


# ---------------------------------------------------------------------------
# Debug chat endpoint (terminal-based testing against deployed instance)
# ---------------------------------------------------------------------------


@router.post("/debug/chat")
async def debug_chat(request: Request):
    result = await handle_debug_chat_route_runtime(
        request=request,
        deps=_build_route_runtime_deps(),
    )
    return JSONResponse(result)
