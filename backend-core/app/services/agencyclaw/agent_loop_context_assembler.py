"""Prompt-context assembler for the AgencyClaw agent loop (C17D).

Turns stored ``agent_messages`` and ``agent_skill_events`` rows into a
bounded prompt payload suitable for the LLM call.  Pure assembly logic —
no DB access, no runtime wiring.

Output shape::

    {
        "messages_for_llm": [{"role": "user", "content": "..."}, ...],
        "evidence_notes":   ["[skill_call] clickup_task_list: ...", ...],
        "stats": {
            "messages_in":  <int>,   # rows received
            "messages_out": <int>,   # rows emitted after budget trim
            "events_in":    <int>,   # skill event rows received
            "events_out":   <int>,   # events emitted as evidence notes
            "truncated":    <bool>,  # True if any rows were dropped for budget
        },
    }

Budget enforcement:
    The assembler enforces a configurable character budget (default 6000).
    It keeps the *newest* context and trims the *oldest* first.
"""

from __future__ import annotations

import json
from typing import Any, TypedDict

from .agent_loop_store import summarize_json

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BUDGET_CHARS: int = 6_000

# Roles accepted from agent_messages rows.
_PASSTHROUGH_ROLES = {"user", "assistant", "system"}

# ---------------------------------------------------------------------------
# Role normalization
# ---------------------------------------------------------------------------


def normalize_role(role: str) -> str | None:
    """Map a stored message role to a prompt-safe LLM role.

    Returns ``None`` for roles that should be dropped from the prompt
    context (the caller skips those rows).

    Mapping:
        ``user``            → ``"user"``
        ``assistant``       → ``"assistant"``
        ``system``          → ``"system"``
        ``planner_report``  → ``"system"``  (injected as system context)
        anything else       → ``None``  (dropped)
    """
    if not isinstance(role, str):
        return None
    role = role.strip().lower()
    if role in _PASSTHROUGH_ROLES:
        return role
    if role == "planner_report":
        return "system"
    return None


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------


def _extract_message_text(row: dict[str, Any]) -> str:
    """Best-effort text from a message row.

    Preference order:
        1. ``summary`` field (pre-truncated for prompt use)
        2. ``content["text"]`` when content is a dict with a text key
        3. Compact JSON of ``content`` via ``summarize_json``
        4. Empty string (malformed row)
    """
    summary = row.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()

    content = row.get("content")
    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        try:
            return summarize_json(content)
        except (ValueError, TypeError):
            return ""

    if isinstance(content, str) and content.strip():
        return content.strip()

    return ""


def _extract_event_note(row: dict[str, Any]) -> str:
    """Build a one-line evidence note from a skill event row.

    Format: ``[event_type] skill_id: summary_text``
    """
    event_type = row.get("event_type", "event")
    skill_id = row.get("skill_id", "unknown")

    payload_summary = row.get("payload_summary")
    if isinstance(payload_summary, str) and payload_summary.strip():
        summary_text = payload_summary.strip()
    else:
        payload = row.get("payload")
        if isinstance(payload, dict):
            try:
                summary_text = summarize_json(payload, max_chars=200)
            except (ValueError, TypeError):
                summary_text = "{}"
        else:
            summary_text = str(payload) if payload is not None else "{}"

    return f"[{event_type}] {skill_id}: {summary_text}"


def _estimate_chars(text: str) -> int:
    """Character count used for budget enforcement."""
    return len(text)


# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------


class AssemblyStats(TypedDict):
    messages_in: int
    messages_out: int
    events_in: int
    events_out: int
    truncated: bool


class AssembledContext(TypedDict):
    messages_for_llm: list[dict[str, str]]
    evidence_notes: list[str]
    stats: AssemblyStats


# ---------------------------------------------------------------------------
# Main assembler
# ---------------------------------------------------------------------------


def assemble_prompt_context(
    messages: list[dict[str, Any]],
    skill_events: list[dict[str, Any]],
    *,
    budget_chars: int = DEFAULT_BUDGET_CHARS,
) -> AssembledContext:
    """Assemble a bounded prompt context from stored rows.

    Parameters
    ----------
    messages:
        Rows from ``agent_messages`` table.  Expected keys:
        ``role``, ``content``, optional ``summary``, ``created_at``.
    skill_events:
        Rows from ``agent_skill_events`` table.  Expected keys:
        ``event_type``, ``skill_id``, ``payload``, optional
        ``payload_summary``, ``created_at``.
    budget_chars:
        Maximum total character budget for all emitted content.
        Oldest items are trimmed first to stay within budget.

    Returns
    -------
    AssembledContext with ``messages_for_llm``, ``evidence_notes``, ``stats``.
    """
    if budget_chars <= 0:
        raise ValueError("budget_chars must be > 0")

    messages_in = len(messages)
    events_in = len(skill_events)

    # --- Phase 1: Parse and sort messages oldest-first -----------------
    parsed_msgs: list[tuple[str, str, str]] = []  # (created_at, role, text)
    for row in messages:
        if not isinstance(row, dict):
            continue
        raw_role = row.get("role")
        mapped_role = normalize_role(raw_role) if isinstance(raw_role, str) else None
        if mapped_role is None:
            continue
        text = _extract_message_text(row)
        if not text:
            continue
        created_at = str(row.get("created_at", ""))
        parsed_msgs.append((created_at, mapped_role, text))

    # Sort oldest-first by created_at (lexicographic on ISO timestamps).
    parsed_msgs.sort(key=lambda t: t[0])

    # --- Phase 2: Parse skill events oldest-first ----------------------
    parsed_events: list[tuple[str, str]] = []  # (created_at, note)
    for row in skill_events:
        if not isinstance(row, dict):
            continue
        note = _extract_event_note(row)
        created_at = str(row.get("created_at", ""))
        parsed_events.append((created_at, note))

    parsed_events.sort(key=lambda t: t[0])

    # --- Phase 3: Budget enforcement (trim oldest first) ---------------
    # Build candidate lists with char costs, then trim from the front.
    msg_items = [
        (role, text, _estimate_chars(text))
        for _, role, text in parsed_msgs
    ]
    event_items = [
        (note, _estimate_chars(note))
        for _, note in parsed_events
    ]

    total_chars = sum(c for _, _, c in msg_items) + sum(c for _, c in event_items)
    truncated = total_chars > budget_chars

    # Trim oldest messages first, then oldest events, until within budget.
    while total_chars > budget_chars and msg_items:
        _, _, cost = msg_items.pop(0)
        total_chars -= cost

    while total_chars > budget_chars and event_items:
        _, cost = event_items.pop(0)
        total_chars -= cost

    # --- Phase 4: Build output -----------------------------------------
    messages_for_llm = [
        {"role": role, "content": text}
        for role, text, _ in msg_items
    ]
    evidence_notes = [note for note, _ in event_items]

    return AssembledContext(
        messages_for_llm=messages_for_llm,
        evidence_notes=evidence_notes,
        stats=AssemblyStats(
            messages_in=messages_in,
            messages_out=len(messages_for_llm),
            events_in=events_in,
            events_out=len(evidence_notes),
            truncated=truncated,
        ),
    )
