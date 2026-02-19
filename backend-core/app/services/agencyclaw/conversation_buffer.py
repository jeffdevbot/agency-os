"""Bounded conversation history buffer for Slack DM orchestrator (C10B.5).

Provides deterministic, pure-function utilities for managing a rolling
window of recent user↔assistant exchanges.  The buffer is stored in the
session context JSONB column — no schema changes required.

Limits (hard):
- MAX_EXCHANGES = 5   (10 messages max)
- MAX_TOKENS    = 1500 (estimated via simple heuristic)

Eviction strategy: drop the **oldest** full exchange first, then re-check.
"""

from __future__ import annotations

from typing import Any, TypedDict


class Exchange(TypedDict):
    user: str
    assistant: str


MAX_EXCHANGES: int = 5
MAX_TOKENS: int = 1_500


def estimate_tokens(text: str) -> int:
    """Estimate token count using a simple chars/4 heuristic.

    This intentionally mirrors the common "1 token ≈ 4 characters" rule of
    thumb used across the project.  It is deterministic and fast.
    """
    return max(len(text) // 4, 1) if text else 0


def _total_tokens(exchanges: list[Exchange]) -> int:
    """Sum estimated tokens across all exchanges."""
    return sum(
        estimate_tokens(ex["user"]) + estimate_tokens(ex["assistant"])
        for ex in exchanges
    )


def append_exchange(
    exchanges: list[Exchange],
    user_msg: str,
    assistant_msg: str,
) -> list[Exchange]:
    """Append a new exchange and return the updated list (does NOT compact)."""
    return [*exchanges, Exchange(user=user_msg, assistant=assistant_msg)]


def compact_exchanges(
    exchanges: list[Exchange],
    *,
    max_exchanges: int = MAX_EXCHANGES,
    max_tokens: int = MAX_TOKENS,
) -> list[Exchange]:
    """Return a compacted copy that satisfies both count and token limits.

    Eviction is deterministic: drop the oldest (first) exchange, then
    re-check both limits.  Repeat until both hold.
    """
    result = list(exchanges)

    # Enforce exchange count limit first (cheap)
    while len(result) > max_exchanges:
        result.pop(0)

    # Enforce token budget
    while result and _total_tokens(result) > max_tokens:
        result.pop(0)

    return result


def exchanges_to_chat_messages(
    exchanges: list[Exchange],
) -> list[dict[str, str]]:
    """Convert exchanges into alternating user/assistant ChatMessage dicts."""
    messages: list[dict[str, str]] = []
    for ex in exchanges:
        messages.append({"role": "user", "content": ex["user"]})
        messages.append({"role": "assistant", "content": ex["assistant"]})
    return messages
