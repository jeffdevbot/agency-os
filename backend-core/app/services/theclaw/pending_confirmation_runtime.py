"""Pending-confirmation helpers for The Claw runtime."""

from __future__ import annotations

import logging
import re
from typing import Any

from .clickup_execution import (
    enrich_pending_confirmation_destination,
    execute_confirmed_task_creation,
)
from .runtime_state import (
    SESSION_PENDING_CONFIRMATION_KEY,
    SESSION_RESOLVED_CONTEXT_KEY,
    resolved_context_from_session_context,
    sanitize_context_field,
)

_logger = logging.getLogger(__name__)

_PENDING_CONFIRMATION_EXPLICIT_PROMPT = "Reply with exactly 'yes' to proceed or 'no' to cancel."


def _pending_confirmation_label(pending_confirmation: dict[str, Any]) -> str:
    title = sanitize_context_field(pending_confirmation.get("task_title"))
    task_id = sanitize_context_field(pending_confirmation.get("task_id"))
    return title or task_id or "the pending draft task"


def parse_pending_confirmation_decision(text: str) -> str | None:
    normalized = (text or "").strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = normalized.strip(" .!?")
    if normalized in {
        "yes",
        "y",
        "confirm",
        "confirmed",
        "approve",
        "approved",
        "go ahead",
        "proceed",
        "do it",
    }:
        return "yes"
    if normalized in {
        "no",
        "n",
        "cancel",
        "stop",
        "do not",
        "dont",
        "don't",
        "not now",
        "hold off",
        "never mind",
    }:
        return "no"
    return None


async def enrich_pending_destination_if_present(
    *,
    state_updates: dict[str, Any],
    session_context: dict[str, Any],
) -> dict[str, Any]:
    """Eagerly resolve pending confirmation destination IDs if present."""
    pending = state_updates.get(SESSION_PENDING_CONFIRMATION_KEY)
    if not isinstance(pending, dict):
        return state_updates
    try:
        # Prefer same-turn resolved context (if the LLM emitted both in one reply),
        # then fall back to prior session state.
        same_turn_rc = state_updates.get(SESSION_RESOLVED_CONTEXT_KEY)
        resolved_ctx = (
            same_turn_rc
            if isinstance(same_turn_rc, dict)
            else resolved_context_from_session_context(session_context)
        )
        enriched = await enrich_pending_confirmation_destination(
            pending=pending,
            resolved_ctx=resolved_ctx,
        )
        if enriched is not pending:
            updated = dict(state_updates)
            updated[SESSION_PENDING_CONFIRMATION_KEY] = enriched
            return updated
    except Exception:  # noqa: BLE001
        _logger.debug("The Claw pending destination enrichment failed", exc_info=True)
    return state_updates


async def build_pending_confirmation_reply(
    *,
    user_text: str,
    pending_confirmation: dict[str, Any],
    session_context: dict[str, Any],
    fallback_reply: str,
) -> tuple[str, dict[str, Any]]:
    """Build reply + state updates for a pending confirmation turn."""
    decision = parse_pending_confirmation_decision(user_text)
    task_label = _pending_confirmation_label(pending_confirmation)

    if decision == "yes":
        try:
            result, state_updates = await execute_confirmed_task_creation(
                session_context=session_context,
                pending_confirmation=pending_confirmation,
            )
        except Exception as exc:  # noqa: BLE001
            _logger.exception("The Claw execution unexpected error: %s", exc)
            result = None
            state_updates = {}
        if result is not None and result.success:
            if result.already_sent:
                url_part = f" ({result.clickup_task_url})" if result.clickup_task_url else ""
                reply_text = f"'{task_label}' was already created in ClickUp{url_part}. No duplicate was sent."
            else:
                url_part = f"\n{result.clickup_task_url}" if result.clickup_task_url else ""
                reply_text = f"Created '{task_label}' in ClickUp.{url_part}"
        elif result is not None:
            reply_text = result.error_message or fallback_reply
        else:
            reply_text = f"Something went wrong creating '{task_label}'. Say 'yes' to retry."
        return reply_text, state_updates

    if decision == "no":
        return (
            f"Canceled pending creation for '{task_label}'. No external actions were executed.",
            {SESSION_PENDING_CONFIRMATION_KEY: None},
        )

    return (
        f"Pending confirmation for '{task_label}'. {_PENDING_CONFIRMATION_EXPLICIT_PROMPT}",
        {},
    )

