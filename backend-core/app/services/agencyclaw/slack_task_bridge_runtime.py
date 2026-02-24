"""Bridge helpers for Slack route task wrapper shims."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from logging import Logger
from typing import Any, Awaitable, Callable

from ..clickup import ClickUpConfigurationError, ClickUpError, get_clickup_service
from .clickup_reliability import (
    RetryExhaustedError,
    build_idempotency_key,
    check_duplicate,
    emit_orphan_event,
    retry_with_backoff,
)
from .grounded_task_draft import build_grounded_task_draft
from .kb_retrieval import retrieve_kb_context
from .slack_helpers import (
    _WEEKLY_TASK_CAP,
    _extract_product_identifiers,
    _format_task_list_response,
    _resolve_task_range,
)
from .slack_runtime_deps import SlackTaskListRuntimeDeps, SlackTaskRuntimeDeps
from .slack_task_list_runtime import handle_task_list_runtime as _runtime_handle_task_list
from .slack_task_runtime import (
    enrich_task_draft_runtime as _runtime_enrich_task_draft,
    execute_task_create_runtime as _runtime_execute_task_create,
    handle_create_task_runtime as _runtime_handle_create_task,
)


@dataclass(frozen=True)
class SlackTaskBridgeRuntimeDeps:
    inflight_lock: asyncio.Lock
    inflight_set: set[str]
    logger: Logger
    build_client_picker_blocks_fn: Callable[[list[dict[str, Any]]], list[dict[str, Any]]]
    get_supabase_admin_client_fn: Callable[[], Any]
    resolve_client_for_task_fn: Callable[..., Awaitable[tuple[str | None, str]]]
    resolve_brand_for_task_fn: Callable[..., Awaitable[dict[str, Any]]]
    get_clickup_service_fn: Callable[[], Any] = get_clickup_service
    clickup_configuration_error_cls: type[Exception] = ClickUpConfigurationError
    clickup_error_cls: type[Exception] = ClickUpError
    resolve_task_range_fn: Callable[..., tuple[int, int, str]] = _resolve_task_range
    format_task_list_response_fn: Callable[..., str] = _format_task_list_response
    task_cap: int = _WEEKLY_TASK_CAP
    build_idempotency_key_fn: Callable[[str, str], str] = build_idempotency_key
    check_duplicate_fn: Callable[..., Any] = check_duplicate
    retry_with_backoff_fn: Callable[..., Awaitable[Any]] = retry_with_backoff
    retry_exhausted_error_cls: type[Exception] = RetryExhaustedError
    emit_orphan_event_fn: Callable[..., Any] = emit_orphan_event
    extract_product_identifiers_fn: Callable[..., list[str]] = _extract_product_identifiers
    retrieve_kb_context_fn: Callable[..., Awaitable[dict[str, Any]]] = retrieve_kb_context
    build_grounded_task_draft_fn: Callable[..., dict[str, Any]] = build_grounded_task_draft


def build_task_bridge_runtime_deps(
    *,
    inflight_lock: asyncio.Lock,
    inflight_set: set[str],
    logger: Logger,
    build_client_picker_blocks_fn: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    get_supabase_admin_client_fn: Callable[[], Any],
    resolve_client_for_task_fn: Callable[..., Awaitable[tuple[str | None, str]]],
    resolve_brand_for_task_fn: Callable[..., Awaitable[dict[str, Any]]],
    get_clickup_service_fn: Callable[[], Any] = get_clickup_service,
    clickup_configuration_error_cls: type[Exception] = ClickUpConfigurationError,
    clickup_error_cls: type[Exception] = ClickUpError,
    resolve_task_range_fn: Callable[..., tuple[int, int, str]] = _resolve_task_range,
    format_task_list_response_fn: Callable[..., str] = _format_task_list_response,
    task_cap: int = _WEEKLY_TASK_CAP,
    build_idempotency_key_fn: Callable[[str, str], str] = build_idempotency_key,
    check_duplicate_fn: Callable[..., Any] = check_duplicate,
    retry_with_backoff_fn: Callable[..., Awaitable[Any]] = retry_with_backoff,
    retry_exhausted_error_cls: type[Exception] = RetryExhaustedError,
    emit_orphan_event_fn: Callable[..., Any] = emit_orphan_event,
    extract_product_identifiers_fn: Callable[..., list[str]] = _extract_product_identifiers,
    retrieve_kb_context_fn: Callable[..., Awaitable[dict[str, Any]]] = retrieve_kb_context,
    build_grounded_task_draft_fn: Callable[..., dict[str, Any]] = build_grounded_task_draft,
) -> SlackTaskBridgeRuntimeDeps:
    return SlackTaskBridgeRuntimeDeps(
        inflight_lock=inflight_lock,
        inflight_set=inflight_set,
        logger=logger,
        build_client_picker_blocks_fn=build_client_picker_blocks_fn,
        get_supabase_admin_client_fn=get_supabase_admin_client_fn,
        resolve_client_for_task_fn=resolve_client_for_task_fn,
        resolve_brand_for_task_fn=resolve_brand_for_task_fn,
        get_clickup_service_fn=get_clickup_service_fn,
        clickup_configuration_error_cls=clickup_configuration_error_cls,
        clickup_error_cls=clickup_error_cls,
        resolve_task_range_fn=resolve_task_range_fn,
        format_task_list_response_fn=format_task_list_response_fn,
        task_cap=task_cap,
        build_idempotency_key_fn=build_idempotency_key_fn,
        check_duplicate_fn=check_duplicate_fn,
        retry_with_backoff_fn=retry_with_backoff_fn,
        retry_exhausted_error_cls=retry_exhausted_error_cls,
        emit_orphan_event_fn=emit_orphan_event_fn,
        extract_product_identifiers_fn=extract_product_identifiers_fn,
        retrieve_kb_context_fn=retrieve_kb_context_fn,
        build_grounded_task_draft_fn=build_grounded_task_draft_fn,
    )


def build_task_list_runtime_deps_bridge_runtime(
    deps: SlackTaskBridgeRuntimeDeps,
) -> SlackTaskListRuntimeDeps:
    return SlackTaskListRuntimeDeps(
        get_clickup_service_fn=deps.get_clickup_service_fn,
        clickup_configuration_error_cls=deps.clickup_configuration_error_cls,
        clickup_error_cls=deps.clickup_error_cls,
        build_client_picker_blocks_fn=deps.build_client_picker_blocks_fn,
        resolve_task_range_fn=deps.resolve_task_range_fn,
        format_task_list_response_fn=deps.format_task_list_response_fn,
        task_cap=deps.task_cap,
    )


def _build_task_runtime_deps(
    deps: SlackTaskBridgeRuntimeDeps,
) -> SlackTaskRuntimeDeps:
    return SlackTaskRuntimeDeps(
        inflight_lock=deps.inflight_lock,
        inflight_set=deps.inflight_set,
        build_idempotency_key_fn=deps.build_idempotency_key_fn,
        get_supabase_admin_client_fn=deps.get_supabase_admin_client_fn,
        check_duplicate_fn=deps.check_duplicate_fn,
        get_clickup_service_fn=deps.get_clickup_service_fn,
        retry_with_backoff_fn=deps.retry_with_backoff_fn,
        retry_exhausted_error_cls=deps.retry_exhausted_error_cls,
        clickup_configuration_error_cls=deps.clickup_configuration_error_cls,
        clickup_error_cls=deps.clickup_error_cls,
        emit_orphan_event_fn=deps.emit_orphan_event_fn,
        extract_product_identifiers_fn=deps.extract_product_identifiers_fn,
        logger=deps.logger,
        resolve_client_for_task_fn=deps.resolve_client_for_task_fn,
        resolve_brand_for_task_fn=deps.resolve_brand_for_task_fn,
        retrieve_kb_context_fn=deps.retrieve_kb_context_fn,
        build_grounded_task_draft_fn=deps.build_grounded_task_draft_fn,
    )


async def handle_task_list_bridge_runtime(
    *,
    slack_user_id: str,
    channel: str,
    client_name_hint: str,
    session_service: Any,
    slack: Any,
    deps: SlackTaskBridgeRuntimeDeps,
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
        deps=build_task_list_runtime_deps_bridge_runtime(deps),
    )


async def handle_weekly_tasks_bridge_runtime(
    *,
    slack_user_id: str,
    channel: str,
    client_name_hint: str,
    session_service: Any,
    slack: Any,
    deps: SlackTaskBridgeRuntimeDeps,
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
        deps=deps,
        window=window or "this_week",
        window_days=window_days,
        date_from=date_from,
        date_to=date_to,
    )


async def execute_task_create_bridge_runtime(
    *,
    channel: str,
    session: Any,
    session_service: Any,
    slack: Any,
    client_id: str,
    client_name: str,
    task_title: str,
    task_description: str,
    deps: SlackTaskBridgeRuntimeDeps,
    brand_id: str | None = None,
    brand_name: str | None = None,
) -> None:
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
        deps=_build_task_runtime_deps(deps),
    )


async def handle_create_task_bridge_runtime(
    *,
    slack_user_id: str,
    channel: str,
    client_name_hint: str,
    task_title: str,
    session_service: Any,
    slack: Any,
    deps: SlackTaskBridgeRuntimeDeps,
    pref_service: Any | None = None,
) -> None:
    await _runtime_handle_create_task(
        slack_user_id=slack_user_id,
        channel=channel,
        client_name_hint=client_name_hint,
        task_title=task_title,
        session_service=session_service,
        slack=slack,
        pref_service=pref_service,
        deps=_build_task_runtime_deps(deps),
    )


async def enrich_task_draft_bridge_runtime(
    *,
    task_title: str,
    client_id: str,
    client_name: str,
    deps: SlackTaskBridgeRuntimeDeps,
) -> dict[str, Any] | None:
    return await _runtime_enrich_task_draft(
        task_title=task_title,
        client_id=client_id,
        client_name=client_name,
        deps=_build_task_runtime_deps(deps),
    )
