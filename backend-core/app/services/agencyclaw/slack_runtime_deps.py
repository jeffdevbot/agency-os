"""Typed dependency containers for Slack runtime decomposition layers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from logging import Logger
from typing import Any, Awaitable, Callable, Protocol


class SlackClientProtocol(Protocol):
    async def post_message(self, *, channel: str, text: str, blocks: list[dict[str, Any]] | None = None) -> Any: ...
    async def update_message(self, *, channel: str, ts: str, text: str, blocks: list[dict[str, Any]] | None = None) -> Any: ...
    async def aclose(self) -> Any: ...


class SessionServiceProtocol(Protocol):
    db: Any

    def get_or_create_session(self, slack_user_id: str) -> Any: ...
    def touch_session(self, session_id: str) -> Any: ...
    def update_context(self, session_id: str, context: dict[str, Any]) -> Any: ...


@dataclass(frozen=True)
class SlackOrchestratorRuntimeDeps:
    logger: Logger
    orchestrate_dm_message_fn: Callable[..., Awaitable[dict[str, Any]]]
    log_ai_token_usage_fn: Callable[..., Awaitable[None]]
    check_skill_policy_fn: Callable[..., Awaitable[dict[str, Any]]]
    handle_weekly_tasks_fn: Callable[..., Awaitable[None]]
    handle_create_task_fn: Callable[..., Awaitable[None]]
    handle_cc_skill_fn: Callable[..., Awaitable[str]]
    resolve_client_for_task_fn: Callable[..., Awaitable[tuple[str | None, str]]]
    resolve_brand_for_task_fn: Callable[..., Awaitable[dict[str, Any]]]
    preference_memory_service_factory: Callable[..., Any]
    try_planner_fn: Callable[..., Awaitable[bool]]
    classify_message_fn: Callable[[str], tuple[str, dict[str, Any]]]
    is_deterministic_control_intent_fn: Callable[[str], bool]


@dataclass(frozen=True)
class SlackDMRuntimeDeps:
    get_session_service_fn: Callable[[], SessionServiceProtocol]
    get_slack_service_fn: Callable[[], SlackClientProtocol]
    preference_memory_service_factory: Callable[[Any], Any]
    handle_pending_task_continuation_fn: Callable[..., Awaitable[bool]]
    is_llm_orchestrator_enabled_fn: Callable[[], bool]
    try_llm_orchestrator_fn: Callable[..., Awaitable[bool]]
    classify_message_fn: Callable[[str], tuple[str, dict[str, Any]]]
    should_block_deterministic_intent_fn: Callable[[str], bool]
    check_skill_policy_fn: Callable[..., Awaitable[dict[str, Any]]]
    handle_create_task_fn: Callable[..., Awaitable[None]]
    handle_weekly_tasks_fn: Callable[..., Awaitable[None]]
    help_text_fn: Callable[[], str]
    build_client_picker_blocks_fn: Callable[[list[dict[str, Any]]], list[dict[str, Any]]]
    handle_cc_skill_fn: Callable[..., Awaitable[str]]
    logger: Logger
    slack_api_error_cls: type[Exception]


@dataclass(frozen=True)
class SlackInteractionRuntimeDeps:
    get_receipt_service_fn: Callable[[], Any]
    get_session_service_fn: Callable[[], SessionServiceProtocol]
    get_slack_service_fn: Callable[[], SlackClientProtocol]
    execute_task_create_fn: Callable[..., Awaitable[None]]
    logger: Logger
    slack_api_error_cls: type[Exception]


@dataclass(frozen=True)
class SlackPlannerRuntimeDeps:
    logger: Logger
    is_planner_enabled_fn: Callable[[], bool]
    get_supabase_admin_client_fn: Callable[[], Any]
    retrieve_kb_context_fn: Callable[..., Awaitable[dict[str, Any]]]
    generate_plan_fn: Callable[..., Awaitable[dict[str, Any]]]
    execute_plan_fn: Callable[..., Awaitable[dict[str, Any]]]
    check_skill_policy_fn: Callable[..., Awaitable[dict[str, Any]]]
    handle_create_task_fn: Callable[..., Awaitable[None]]
    handle_weekly_tasks_fn: Callable[..., Awaitable[None]]
    handle_cc_skill_fn: Callable[..., Awaitable[str]]
    append_exchange_fn: Callable[[list[dict[str, Any]], str, str], list[dict[str, Any]]]
    compact_exchanges_fn: Callable[[list[dict[str, Any]]], list[dict[str, Any]]]


@dataclass(frozen=True)
class SlackTaskRuntimeDeps:
    inflight_lock: asyncio.Lock
    inflight_set: set[str]
    build_idempotency_key_fn: Callable[[str, str], str]
    get_supabase_admin_client_fn: Callable[[], Any]
    check_duplicate_fn: Callable[..., Any]
    get_clickup_service_fn: Callable[[], Any]
    retry_with_backoff_fn: Callable[..., Awaitable[Any]]
    retry_exhausted_error_cls: type[Exception]
    clickup_configuration_error_cls: type[Exception]
    clickup_error_cls: type[Exception]
    emit_orphan_event_fn: Callable[..., Any]
    extract_product_identifiers_fn: Callable[..., list[str]]
    logger: Logger
    resolve_client_for_task_fn: Callable[..., Awaitable[tuple[str | None, str]]]
    resolve_brand_for_task_fn: Callable[..., Awaitable[dict[str, Any]]]
    retrieve_kb_context_fn: Callable[..., Awaitable[dict[str, Any]]]
    build_grounded_task_draft_fn: Callable[..., dict[str, Any]]
