"""Debug chat handler for terminal-based AgencyClaw testing.

Reuses the full DM pipeline with a response-capturing fake Slack service.
All other dependencies (sessions, ClickUp, OpenAI, Supabase) are real.

Gated by AGENCYCLAW_DEBUG_CHAT_ENABLED env var.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from .policy_gate import _MUTATION_SKILLS
from .slack_route_runtime import SlackRouteRuntimeDeps, handle_dm_event_route_runtime


class DebugSlackCapture:
    """Drop-in replacement for SlackService that captures messages."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def post_message(
        self,
        *,
        channel: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> Any:
        self.messages.append({"text": text, "blocks": blocks})
        return type("R", (), {"ok": True, "ts": "debug-ts", "channel": channel})()

    async def update_message(
        self,
        *,
        channel: str,
        ts: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> Any:
        self.messages.append({"text": text, "blocks": blocks, "update": True})
        return type("R", (), {"ok": True, "ts": ts, "channel": channel})()

    async def aclose(self) -> None:
        pass


async def handle_debug_chat(
    *,
    text: str,
    deps: SlackRouteRuntimeDeps,
    user_id: str = "U_DEBUG_TERMINAL",
    channel: str = "D_DEBUG",
    allow_mutations: bool = False,
) -> dict[str, Any]:
    """Run the full DM pipeline, capturing Slack output instead of posting it.

    Returns ``{"messages": [{"text": "...", "blocks": ...}, ...]}``.
    """
    capture = DebugSlackCapture()
    replacements: dict[str, Any] = {"get_slack_service_fn": lambda: capture}

    if not allow_mutations:
        original_check = deps.check_skill_policy_fn

        async def _block_mutations(*args: Any, **kwargs: Any) -> dict[str, Any]:
            skill_id = args[0] if args else kwargs.get("skill_id", "")
            if skill_id in _MUTATION_SKILLS:
                return {"allowed": False, "reason": "debug_read_only"}
            return await original_check(*args, **kwargs)

        replacements["check_skill_policy_fn"] = _block_mutations

    patched_deps = dataclasses.replace(deps, **replacements)

    await handle_dm_event_route_runtime(
        slack_user_id=user_id,
        channel=channel,
        text=text,
        deps=patched_deps,
    )

    return {"messages": capture.messages, "user_id": user_id}
