import asyncio
import json
import logging
import os
from typing import Any
from urllib.parse import parse_qs

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
    resolve_brand_context,
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
from ...services.agencyclaw.slack_dm_runtime import (
    handle_dm_event_runtime as _runtime_handle_dm_event,
)
from ...services.agencyclaw.slack_interaction_runtime import (
    handle_interaction_runtime as _runtime_handle_interaction,
)
from ...services.agencyclaw.slack_task_runtime import (
    enrich_task_draft_runtime as _runtime_enrich_task_draft,
    execute_task_create_runtime as _runtime_execute_task_create,
    handle_create_task_runtime as _runtime_handle_create_task,
)
from ...services.agencyclaw.slack_task_list_runtime import (
    handle_task_list_runtime as _runtime_handle_task_list,
)
from ...services.agencyclaw.slack_runtime_deps import (
    SlackDMRuntimeDeps,
    SlackInteractionRuntimeDeps,
    SlackOrchestratorRuntimeDeps,
    SlackPlannerRuntimeDeps,
    SlackTaskListRuntimeDeps,
    SlackTaskRuntimeDeps,
)
from ...services.agencyclaw.plan_executor import execute_plan
from ...services.agencyclaw.planner import generate_plan
from ...services.agencyclaw.slack_cc_dispatch import (
    format_remediation_apply_result as _cc_format_remediation_apply_result,
    format_remediation_preview as _cc_format_remediation_preview,
    handle_cc_skill as _cc_handle_cc_skill,
    resolve_cc_client_hint as _cc_resolve_cc_client_hint,
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
from ...services.clickup import ClickUpError, ClickUpConfigurationError, get_clickup_service
from ...services.agencyclaw.preference_memory import PreferenceMemoryService
from ...services.playbook_session import get_playbook_session_service, get_supabase_admin_client
from ...services.slack import (
    SlackAPIError,
    SlackReceiptService,
    get_slack_service,
    get_slack_signing_secret,
    verify_slack_signature,
)

_logger = logging.getLogger(__name__)

# C4C: In-memory concurrency guard for task mutations.
# Prevents two simultaneous creates for the same target from racing past
# the duplicate check.  Single-process only; see plan for multi-worker TODO.
_task_create_inflight: set[str] = set()
_task_create_inflight_lock = asyncio.Lock()

router = APIRouter(prefix="/slack", tags=["slack"])


def _is_llm_orchestrator_enabled() -> bool:
    return _helpers_is_llm_orchestrator_enabled()


def _is_planner_enabled() -> bool:
    """Check if the C10D planner feature flag is enabled."""
    return os.environ.get("AGENCYCLAW_ENABLE_PLANNER", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _is_legacy_intent_fallback_enabled() -> bool:
    return _helpers_is_legacy_intent_fallback_enabled()


def _is_llm_strict_mode() -> bool:
    return _is_llm_orchestrator_enabled() and not _is_legacy_intent_fallback_enabled()


def _is_deterministic_control_intent(intent: str) -> bool:
    return _helpers_is_deterministic_control_intent(intent)


def _should_block_deterministic_intent(intent: str) -> bool:
    return _is_llm_strict_mode() and not _is_deterministic_control_intent(intent)


def _get_receipt_service() -> SlackReceiptService:
    return SlackReceiptService(get_supabase_admin_client())



def _parse_json(body: bytes) -> dict[str, Any]:
    try:
        value = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    return value


def _verify_request_or_401(*, signing_secret: str, request: Request, body: bytes) -> None:
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    if not verify_slack_signature(signing_secret, timestamp, body, signature):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")


def _build_client_picker_blocks(clients: list[dict[str, Any]]) -> list[dict[str, Any]]:
    top = clients[:10]
    blocks: list[dict[str, Any]] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "Which client are you working on today?"},
        }
    ]

    # Slack actions block supports up to 5 elements; cap overall at 10.
    for i in range(0, len(top), 5):
        chunk = top[i : i + 5]
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": str(client.get("name", "Client"))},
                        "action_id": f"select_client_{client.get('id')}",
                        "value": str(client.get("id")),
                    }
                    for client in chunk
                ],
            }
        )

    return blocks


def _build_brand_picker_blocks(
    brands: list[dict[str, Any]], client_name: str,
) -> list[dict[str, Any]]:
    """Build Slack action blocks for brand selection (same pattern as client picker)."""
    top = brands[:10]
    blocks: list[dict[str, Any]] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"Which brand under *{client_name}*?"},
        }
    ]
    for i in range(0, len(top), 5):
        chunk = top[i : i + 5]
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": str(b.get("name", "Brand"))},
                        "action_id": f"select_brand_{b.get('id')}",
                        "value": str(b.get("id")),
                    }
                    for b in chunk
                ],
            }
        )
    return blocks


def _build_task_list_runtime_deps() -> SlackTaskListRuntimeDeps:
    return SlackTaskListRuntimeDeps(
        get_clickup_service_fn=get_clickup_service,
        clickup_configuration_error_cls=ClickUpConfigurationError,
        clickup_error_cls=ClickUpError,
        build_client_picker_blocks_fn=_build_client_picker_blocks,
        resolve_task_range_fn=_resolve_task_range,
        format_task_list_response_fn=_format_task_list_response,
        task_cap=_WEEKLY_TASK_CAP,
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
    await _runtime_handle_task_list(
        slack_user_id=slack_user_id,
        channel=channel,
        client_name_hint=client_name_hint,
        session_service=session_service,
        slack=slack,
        window=window,
        window_days=window_days,
        date_from=date_from,
        date_to=date_to,
        deps=_build_task_list_runtime_deps(),
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
    """Resolve client_id + client_name from hint or active session.

    Returns (client_id, client_name).  client_id is None on failure (message already sent).

    Precedence: explicit hint > actor preference > session active client > picker.
    """
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
            blocks = _build_client_picker_blocks(matches)
            await slack.post_message(
                channel=channel,
                text=f"Multiple clients match *{client_name_hint}*. Pick one and try again:",
                blocks=blocks,
            )
            return None, ""
        return str(matches[0].get("id") or ""), str(matches[0].get("name") or client_name_hint)

    # C10E: Check actor preference (durable default)
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
        blocks = _build_client_picker_blocks(clients)
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
    """Resolve brand context for task creation.

    Fetches brands, calls the pure resolver, posts picker if ambiguous.
    """
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
        blocks = _build_brand_picker_blocks(resolution["candidates"], client_name)
        await slack.post_message(
            channel=channel,
            text=f"*{client_name}* has {qualifier}. Which brand is this for?",
            blocks=blocks,
        )

    return resolution


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
    return await _cc_resolve_cc_client_hint(
        args=args,
        session_service=session_service,
        session=session,
        channel=channel,
        slack=slack,
        build_client_picker_blocks=build_client_picker_blocks or _build_client_picker_blocks,
    )


async def _resolve_assignment_client(
    *,
    args: dict[str, Any],
    session_service: Any,
    session: Any,
    channel: str,
    slack: Any,
) -> str | bool:
    """Resolve client for assignment skills (always requires a concrete client).

    Unlike ``_resolve_cc_client_hint`` (which returns None for "scan all"),
    assignment skills always need a client_id.

    Returns:
    - A client_id string on success.
    - ``False`` if resolution failed (message already posted to Slack).
    """
    client_hint = str(args.get("client_name") or "").strip()

    # Explicit client_name hint — resolve via fuzzy match
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
            blocks = _build_client_picker_blocks(matches)
            await slack.post_message(
                channel=channel,
                text=f"Multiple clients match *{client_hint}*. Pick one and try again:",
                blocks=blocks,
            )
            return False
        return str(matches[0].get("id") or "")

    # No hint — fall back to active client on session
    if session.active_client_id:
        return str(session.active_client_id)

    # No active client — ask user to pick or switch
    clients = await asyncio.to_thread(
        session_service.list_clients_for_picker, session.profile_id,
    )
    if clients:
        blocks = _build_client_picker_blocks(clients)
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


def _format_remediation_preview(plan: list[dict[str, Any]]) -> str:
    return _cc_format_remediation_preview(plan)


def _format_remediation_apply_result(result: dict[str, Any]) -> str:
    return _cc_format_remediation_apply_result(result)


async def _handle_cc_skill(
    *,
    skill_id: str,
    args: dict[str, Any],
    session: Any,
    session_service: Any,
    channel: str,
    slack: Any,
) -> str:
    return await _cc_handle_cc_skill(
        skill_id=skill_id,
        args=args,
        session=session,
        session_service=session_service,
        channel=channel,
        slack=slack,
        build_client_picker_blocks=_build_client_picker_blocks,
        resolve_cc_client_hint_fn=_resolve_cc_client_hint,
        resolve_assignment_client_fn=_resolve_assignment_client,
        lookup_clients_fn=lookup_clients,
        format_client_list_fn=format_client_list,
        list_brands_fn=list_brands,
        format_brand_list_fn=format_brand_list,
        audit_brand_mappings_fn=audit_brand_mappings,
        format_mapping_audit_fn=format_mapping_audit,
        build_brand_mapping_remediation_plan_fn=build_brand_mapping_remediation_plan,
        apply_brand_mapping_remediation_plan_fn=apply_brand_mapping_remediation_plan,
        format_remediation_preview_fn=_format_remediation_preview,
        format_remediation_apply_result_fn=_format_remediation_apply_result,
        resolve_person_fn=resolve_person,
        resolve_role_fn=resolve_role,
        resolve_brand_for_assignment_fn=resolve_brand_for_assignment,
        upsert_assignment_fn=upsert_assignment,
        remove_assignment_fn=remove_assignment,
        format_person_ambiguous_fn=format_person_ambiguous,
        format_upsert_result_fn=format_upsert_result,
        format_remove_result_fn=format_remove_result,
        create_brand_fn=create_brand,
        format_brand_create_result_fn=format_brand_create_result,
        resolve_brand_for_mutation_fn=resolve_brand_for_mutation,
        format_brand_ambiguous_fn=format_brand_ambiguous,
        update_brand_fn=update_brand,
        format_brand_update_result_fn=format_brand_update_result,
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
    task_deps = SlackTaskRuntimeDeps(
        inflight_lock=_task_create_inflight_lock,
        inflight_set=_task_create_inflight,
        build_idempotency_key_fn=build_idempotency_key,
        get_supabase_admin_client_fn=get_supabase_admin_client,
        check_duplicate_fn=check_duplicate,
        get_clickup_service_fn=get_clickup_service,
        retry_with_backoff_fn=retry_with_backoff,
        retry_exhausted_error_cls=RetryExhaustedError,
        clickup_configuration_error_cls=ClickUpConfigurationError,
        clickup_error_cls=ClickUpError,
        emit_orphan_event_fn=emit_orphan_event,
        extract_product_identifiers_fn=_extract_product_identifiers,
        logger=_logger,
        resolve_client_for_task_fn=_resolve_client_for_task,
        resolve_brand_for_task_fn=_resolve_brand_for_task,
        retrieve_kb_context_fn=retrieve_kb_context,
        build_grounded_task_draft_fn=build_grounded_task_draft,
    )
    await _runtime_execute_task_create(
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
        deps=task_deps,
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
    task_deps = SlackTaskRuntimeDeps(
        inflight_lock=_task_create_inflight_lock,
        inflight_set=_task_create_inflight,
        build_idempotency_key_fn=build_idempotency_key,
        get_supabase_admin_client_fn=get_supabase_admin_client,
        check_duplicate_fn=check_duplicate,
        get_clickup_service_fn=get_clickup_service,
        retry_with_backoff_fn=retry_with_backoff,
        retry_exhausted_error_cls=RetryExhaustedError,
        clickup_configuration_error_cls=ClickUpConfigurationError,
        clickup_error_cls=ClickUpError,
        emit_orphan_event_fn=emit_orphan_event,
        extract_product_identifiers_fn=_extract_product_identifiers,
        logger=_logger,
        resolve_client_for_task_fn=_resolve_client_for_task,
        resolve_brand_for_task_fn=_resolve_brand_for_task,
        retrieve_kb_context_fn=retrieve_kb_context,
        build_grounded_task_draft_fn=build_grounded_task_draft,
    )
    await _runtime_handle_create_task(
        slack_user_id=slack_user_id,
        channel=channel,
        client_name_hint=client_name_hint,
        task_title=task_title,
        session_service=session_service,
        slack=slack,
        pref_service=pref_service,
        deps=task_deps,
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
    task_deps = SlackTaskRuntimeDeps(
        inflight_lock=_task_create_inflight_lock,
        inflight_set=_task_create_inflight,
        build_idempotency_key_fn=build_idempotency_key,
        get_supabase_admin_client_fn=get_supabase_admin_client,
        check_duplicate_fn=check_duplicate,
        get_clickup_service_fn=get_clickup_service,
        retry_with_backoff_fn=retry_with_backoff,
        retry_exhausted_error_cls=RetryExhaustedError,
        clickup_configuration_error_cls=ClickUpConfigurationError,
        clickup_error_cls=ClickUpError,
        emit_orphan_event_fn=emit_orphan_event,
        extract_product_identifiers_fn=_extract_product_identifiers,
        logger=_logger,
        resolve_client_for_task_fn=_resolve_client_for_task,
        resolve_brand_for_task_fn=_resolve_brand_for_task,
        retrieve_kb_context_fn=retrieve_kb_context,
        build_grounded_task_draft_fn=build_grounded_task_draft,
    )
    return await _runtime_enrich_task_draft(
        task_title=task_title,
        client_id=client_id,
        client_name=client_name,
        deps=task_deps,
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
    actor = await asyncio.to_thread(
        resolve_actor_context,
        get_supabase_admin_client(),
        slack_user_id,
        session.profile_id,
    )
    surface = resolve_surface_context(channel)
    return evaluate_skill_policy(actor, surface, skill_id, args, session.context)

async def _handle_dm_event(*, slack_user_id: str, channel: str, text: str) -> None:
    dm_deps = SlackDMRuntimeDeps(
        get_session_service_fn=get_playbook_session_service,
        get_slack_service_fn=get_slack_service,
        preference_memory_service_factory=PreferenceMemoryService,
        handle_pending_task_continuation_fn=_handle_pending_task_continuation,
        is_llm_orchestrator_enabled_fn=_is_llm_orchestrator_enabled,
        try_llm_orchestrator_fn=_try_llm_orchestrator,
        classify_message_fn=_classify_message,
        should_block_deterministic_intent_fn=_should_block_deterministic_intent,
        check_skill_policy_fn=_check_skill_policy,
        handle_create_task_fn=_handle_create_task,
        handle_task_list_fn=_handle_task_list,
        help_text_fn=_help_text,
        build_client_picker_blocks_fn=_build_client_picker_blocks,
        handle_cc_skill_fn=_handle_cc_skill,
        logger=_logger,
        slack_api_error_cls=SlackAPIError,
    )
    await _runtime_handle_dm_event(
        slack_user_id=slack_user_id,
        channel=channel,
        text=text,
        deps=dm_deps,
    )


def _parse_interaction_payload(raw_body: bytes) -> dict[str, Any]:
    try:
        form = parse_qs(raw_body.decode("utf-8"), keep_blank_values=True)
    except UnicodeDecodeError:
        return {}

    payload_str = (form.get("payload") or [""])[0]
    if not payload_str:
        return {}
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


async def _handle_interaction(payload: dict[str, Any]) -> None:
    interaction_deps = SlackInteractionRuntimeDeps(
        get_receipt_service_fn=_get_receipt_service,
        get_session_service_fn=get_playbook_session_service,
        get_slack_service_fn=get_slack_service,
        execute_task_create_fn=_execute_task_create,
        logger=_logger,
        slack_api_error_cls=SlackAPIError,
    )
    await _runtime_handle_interaction(
        payload,
        deps=interaction_deps,
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
