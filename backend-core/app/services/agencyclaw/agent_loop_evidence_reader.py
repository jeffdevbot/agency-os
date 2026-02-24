"""Evidence rehydration reader for the AgencyClaw agent loop (C17G).

Accepts a rehydration key and an ``AgentLoopStore`` instance, fetches the
corresponding skill event, and returns a deterministic result dict.

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


def read_evidence(store: AgentLoopStore, key: str) -> dict[str, Any]:
    """Rehydrate a single evidence record from a rehydration key.

    Parameters
    ----------
    store:
        An ``AgentLoopStore`` instance wired to the database.
    key:
        A rehydration key produced by :func:`rehydration_key`
        (e.g. ``"ev:run-1/evt-2"``).

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

    # --- Run-only keys: not yet implemented ----------------------------------
    if event_id is None:
        return _fail(
            run_id=run_id,
            error="not_implemented_run_scope",
        )

    # --- Fetch event ---------------------------------------------------------
    row = store.get_skill_event_by_id(run_id, event_id)
    if not row:
        return _fail(run_id=run_id, event_id=event_id, error="not_found")

    # --- Extract fields ------------------------------------------------------
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

    # --- Build summary and note ----------------------------------------------
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
