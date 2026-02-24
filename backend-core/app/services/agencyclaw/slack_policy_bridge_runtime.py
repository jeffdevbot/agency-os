"""Policy/flag bridge helpers for Slack route wrappers."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass(frozen=True)
class SlackPolicyBridgeRuntimeDeps:
    get_supabase_admin_client_fn: Callable[[], Any]
    resolve_actor_context_fn: Callable[..., dict[str, Any]]
    resolve_surface_context_fn: Callable[[str], dict[str, Any]]
    evaluate_skill_policy_fn: Callable[..., dict[str, Any]]
    is_llm_orchestrator_enabled_fn: Callable[[], bool]
    is_legacy_intent_fallback_enabled_fn: Callable[[], bool]
    is_deterministic_control_intent_fn: Callable[[str], bool]


def is_agent_loop_enabled_runtime() -> bool:
    return os.environ.get("AGENCYCLAW_AGENT_LOOP_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def is_planner_enabled_runtime() -> bool:
    return os.environ.get("AGENCYCLAW_ENABLE_PLANNER", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def is_llm_strict_mode_runtime(deps: SlackPolicyBridgeRuntimeDeps) -> bool:
    return deps.is_llm_orchestrator_enabled_fn() and not deps.is_legacy_intent_fallback_enabled_fn()


def should_block_deterministic_intent_runtime(
    intent: str,
    *,
    deps: SlackPolicyBridgeRuntimeDeps,
) -> bool:
    return is_llm_strict_mode_runtime(deps) and not deps.is_deterministic_control_intent_fn(intent)


async def check_skill_policy_runtime(
    *,
    slack_user_id: str,
    session: Any,
    channel: str,
    skill_id: str,
    args: dict[str, Any] | None,
    deps: SlackPolicyBridgeRuntimeDeps,
) -> dict[str, Any]:
    actor = await asyncio.to_thread(
        deps.resolve_actor_context_fn,
        deps.get_supabase_admin_client_fn(),
        slack_user_id,
        session.profile_id,
    )
    surface = deps.resolve_surface_context_fn(channel)
    return deps.evaluate_skill_policy_fn(actor, surface, skill_id, args, session.context)
