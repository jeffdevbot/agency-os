"""Evidence rehydration reader for the AgencyClaw agent loop (C17G).

Accepts a rehydration key and an ``AgentLoopStore`` instance, fetches the
corresponding skill event(s), and returns a deterministic result dict.

Supports two key formats:
- ``ev:<run_id>/<event_id>`` — single-event rehydration
- ``ev:<run_id>`` — run-scoped aggregate of recent skill events

No runtime wiring — pure service function consumed by tests until
integration lands.
"""

from __future__ import annotations

from typing import Any

from .agent_loop_evidence import (
    build_evidence_note,
    build_payload_summary,
    parse_rehydration_key,
)
from .agent_loop_store import AgentLoopStore

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RUN_SCOPE_EVENT_LIMIT: int = 10
_RUN_SCOPE_SUMMARY_MAX_CHARS: int = 1000


def read_evidence(store: AgentLoopStore, key: str) -> dict[str, Any]:
    """Rehydrate evidence from a rehydration key.

    Parameters
    ----------
    store:
        An ``AgentLoopStore`` instance wired to the database.
    key:
        A rehydration key produced by :func:`rehydration_key`
        (e.g. ``"ev:run-1/evt-2"`` or ``"ev:run-1"``).

    Returns
    -------
    A dict with shape::

        {
            "ok": bool,
            "run_id": str | None,
            "event_id": str | None,
            "note": str | None,
            "payload_summary": str | None,
            "error": str | None,
        }
    """
    # --- Parse key -----------------------------------------------------------
    try:
        parsed = parse_rehydration_key(key)
    except (ValueError, TypeError):
        return _fail(error="invalid_key")

    run_id: str = parsed["run_id"]
    event_id: str | None = parsed["event_id"]

    # --- Run-scope aggregation -----------------------------------------------
    if event_id is None:
        return _read_run_scope(store, run_id)

    # --- Single-event rehydration --------------------------------------------
    return _read_single_event(store, run_id, event_id)


# ---------------------------------------------------------------------------
# Single-event path
# ---------------------------------------------------------------------------


def _read_single_event(
    store: AgentLoopStore, run_id: str, event_id: str,
) -> dict[str, Any]:
    row = store.get_skill_event_by_id(run_id, event_id)
    if not row:
        return _fail(run_id=run_id, event_id=event_id, error="not_found")

    skill_id = row.get("skill_id")
    event_type = row.get("event_type")
    payload = row.get("payload")

    if (
        not isinstance(skill_id, str)
        or not skill_id.strip()
        or not isinstance(event_type, str)
        or not event_type.strip()
        or not isinstance(payload, dict)
    ):
        return _fail(
            run_id=run_id,
            event_id=event_id,
            error="invalid_event_payload",
        )

    payload_summary = build_payload_summary(skill_id, payload)
    note = build_evidence_note(event_type, skill_id, payload_summary)

    return {
        "ok": True,
        "run_id": run_id,
        "event_id": event_id,
        "note": note,
        "payload_summary": payload_summary,
        "error": None,
    }


# ---------------------------------------------------------------------------
# Run-scope path
# ---------------------------------------------------------------------------


def _read_run_scope(store: AgentLoopStore, run_id: str) -> dict[str, Any]:
    rows = store.list_recent_skill_events(run_id, limit=_RUN_SCOPE_EVENT_LIMIT)

    if not rows:
        return _fail(run_id=run_id, error="not_found")

    # Build individual notes, oldest-first for chronological reading.
    # The store returns newest-first, so reverse.
    notes: list[str] = []
    for row in reversed(rows):
        skill_id = row.get("skill_id")
        event_type = row.get("event_type")
        payload = row.get("payload")

        if (
            not isinstance(skill_id, str)
            or not skill_id.strip()
            or not isinstance(event_type, str)
            or not event_type.strip()
        ):
            continue

        if isinstance(payload, dict):
            summary = build_payload_summary(skill_id, payload)
        else:
            ps = row.get("payload_summary")
            summary = str(ps) if ps is not None else "{}"

        notes.append(build_evidence_note(event_type, skill_id, summary))

    if not notes:
        return _fail(run_id=run_id, error="not_found")

    # Aggregate note: join with newlines, bounded by char budget.
    aggregate_note = "\n".join(notes)
    if len(aggregate_note) > _RUN_SCOPE_SUMMARY_MAX_CHARS:
        aggregate_note = aggregate_note[:_RUN_SCOPE_SUMMARY_MAX_CHARS - 3] + "..."

    # Compact summary: count + skill list.
    skill_ids = []
    seen: set[str] = set()
    for row in reversed(rows):
        sid = row.get("skill_id")
        if isinstance(sid, str) and sid.strip() and sid not in seen:
            skill_ids.append(sid)
            seen.add(sid)
    compact_summary = f"{len(notes)} events across {len(skill_ids)} skill(s): {', '.join(skill_ids)}"

    return {
        "ok": True,
        "run_id": run_id,
        "event_id": None,
        "note": aggregate_note,
        "payload_summary": compact_summary,
        "error": None,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fail(
    *,
    run_id: str | None = None,
    event_id: str | None = None,
    error: str,
) -> dict[str, Any]:
    return {
        "ok": False,
        "run_id": run_id,
        "event_id": event_id,
        "note": None,
        "payload_summary": None,
        "error": error,
    }
