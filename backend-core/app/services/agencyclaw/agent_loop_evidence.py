"""Retention summaries and rehydration helpers for agent loop evidence (C17G).

Provides deterministic payload summarization, evidence-note formatting,
and rehydration key generation/parsing for stored skill events.

These helpers are consumed by the context assembler and (future) evidence
retrieval endpoints.  No DB access — pure functions only.
"""

from __future__ import annotations

import re
from typing import Any

from .agent_loop_store import summarize_json

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REHYDRATION_PREFIX = "ev:"
_REHYDRATION_SEP = "/"
_REHYDRATION_PATTERN = re.compile(
    r"^ev:(?P<run_id>[A-Za-z0-9_-]+)(?:/(?P<event_id>[A-Za-z0-9_-]+))?$"
)

# ---------------------------------------------------------------------------
# Payload summarization
# ---------------------------------------------------------------------------


def build_payload_summary(
    skill_id: str,
    payload: dict[str, Any],
    max_chars: int = 280,
) -> str:
    """Build a deterministic, prompt-safe summary of a skill payload.

    Delegates to :func:`summarize_json` for the heavy lifting but accepts
    ``skill_id`` so future versions can apply skill-specific formatting.

    Parameters
    ----------
    skill_id:
        Identifies the skill (e.g. ``"clickup_task_list"``).
    payload:
        The raw skill payload dict.
    max_chars:
        Maximum character length for the returned summary.

    Returns
    -------
    A compact JSON string, truncated with ``...`` if needed.

    Raises
    ------
    ValueError
        If *payload* is not a dict or *max_chars* <= 0.
    """
    if not isinstance(skill_id, str) or not skill_id.strip():
        raise ValueError("skill_id is required")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")
    if max_chars <= 0:
        raise ValueError("max_chars must be > 0")

    return summarize_json(payload, max_chars=max_chars)


# ---------------------------------------------------------------------------
# Evidence note formatting
# ---------------------------------------------------------------------------


def build_evidence_note(
    event_type: str,
    skill_id: str,
    payload_summary: str,
) -> str:
    """Format a one-line evidence note from skill event fields.

    Output format: ``[event_type] skill_id: payload_summary``

    Parameters
    ----------
    event_type:
        ``"skill_call"`` or ``"skill_result"``.
    skill_id:
        The skill identifier.
    payload_summary:
        Pre-built summary string (from :func:`build_payload_summary`).

    Raises
    ------
    ValueError
        If any required field is empty.
    """
    if not isinstance(event_type, str) or not event_type.strip():
        raise ValueError("event_type is required")
    if not isinstance(skill_id, str) or not skill_id.strip():
        raise ValueError("skill_id is required")
    if not isinstance(payload_summary, str):
        raise ValueError("payload_summary must be a string")

    return f"[{event_type.strip()}] {skill_id.strip()}: {payload_summary.strip()}"


# ---------------------------------------------------------------------------
# Rehydration keys
# ---------------------------------------------------------------------------


def rehydration_key(run_id: str, event_id: str | None = None) -> str:
    """Build a compact rehydration key for evidence retrieval.

    Format: ``ev:<run_id>`` or ``ev:<run_id>/<event_id>``

    Parameters
    ----------
    run_id:
        The agent run UUID.
    event_id:
        Optional event UUID for single-event retrieval.

    Raises
    ------
    ValueError
        If *run_id* is empty or *event_id* is empty when provided.
    """
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id is required")

    key = f"{_REHYDRATION_PREFIX}{run_id.strip()}"

    if event_id is not None:
        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("event_id must be non-empty when provided")
        key += f"{_REHYDRATION_SEP}{event_id.strip()}"

    return key


def parse_rehydration_key(key: str) -> dict[str, str | None]:
    """Parse a rehydration key back into its component IDs.

    Returns
    -------
    ``{"run_id": "<str>", "event_id": "<str>|None"}``

    Raises
    ------
    ValueError
        If the key does not match the expected format.
    """
    if not isinstance(key, str):
        raise ValueError("key must be a string")

    match = _REHYDRATION_PATTERN.match(key.strip())
    if not match:
        raise ValueError(f"invalid rehydration key: {key!r}")

    return {
        "run_id": match.group("run_id"),
        "event_id": match.group("event_id"),  # None when not present
    }
