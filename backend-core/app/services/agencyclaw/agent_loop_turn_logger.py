"""High-level turn logger for the AgencyClaw agent loop (C17D).

Wraps :class:`AgentLoopStore` with a lifecycle-oriented API that the
future DM runtime can call without knowing storage column details.

Typical turn lifecycle::

    run  = logger.start_main_run(session_id)
    run_id = run["id"]

    logger.log_user_message(run_id, "Show me tasks for Acme")
    logger.log_skill_call(run_id, "clickup_task_list", {"client_name": "Acme"})
    logger.log_skill_result(run_id, "clickup_task_list", {"tasks": [...]})
    logger.log_assistant_message(run_id, "Here are 3 tasks for Acme...")

    logger.complete_run(run_id, "completed")

No DM runtime wiring — this module is imported only by tests until C17D
integration lands.
"""

from __future__ import annotations

from typing import Any

from .agent_loop_store import AgentLoopStore, summarize_json


class AgentLoopTurnLogger:
    """Lifecycle facade over :class:`AgentLoopStore`.

    All methods are thin, synchronous wrappers that delegate to the
    store.  They exist so callers can express *intent* (``log_user_message``)
    rather than raw storage primitives (``append_message(..., role="user")``).
    """

    def __init__(self, store: AgentLoopStore) -> None:
        self._store = store

    # ------------------------------------------------------------------
    # Run lifecycle
    # ------------------------------------------------------------------

    def start_main_run(
        self,
        session_id: str,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Open a new ``main`` run and return the inserted row.

        The returned dict contains at least ``{"id": "<uuid>", "status": "running"}``.
        """
        return self._store.create_run(
            session_id, run_type="main", trace_id=trace_id,
        )

    def complete_run(self, run_id: str, status: str) -> None:
        """Mark a run as finished (``completed`` | ``failed`` | ``blocked``).

        Sets ``completed_at`` for terminal statuses (``completed`` / ``failed`` / ``blocked``).
        """
        terminal = status in {"completed", "failed", "blocked"}
        self._store.update_run_status(run_id, status, completed=terminal)

    # ------------------------------------------------------------------
    # Message logging
    # ------------------------------------------------------------------

    def log_user_message(
        self,
        run_id: str,
        text: str,
        summary: str | None = None,
    ) -> dict[str, Any]:
        """Record an inbound user message."""
        return self._store.append_message(
            run_id, "user", {"text": text}, summary=summary,
        )

    def log_assistant_message(
        self,
        run_id: str,
        text: str,
        summary: str | None = None,
    ) -> dict[str, Any]:
        """Record an outbound assistant reply."""
        return self._store.append_message(
            run_id, "assistant", {"text": text}, summary=summary,
        )

    # ------------------------------------------------------------------
    # Skill event logging
    # ------------------------------------------------------------------

    def log_skill_call(
        self,
        run_id: str,
        skill_id: str,
        payload: dict[str, Any],
        payload_summary: str | None = None,
    ) -> dict[str, Any]:
        """Record a skill invocation (args sent to the skill)."""
        return self._store.append_skill_event(
            run_id,
            "skill_call",
            skill_id,
            payload,
            payload_summary=payload_summary or summarize_json(payload),
        )

    def log_skill_result(
        self,
        run_id: str,
        skill_id: str,
        payload: dict[str, Any],
        payload_summary: str | None = None,
    ) -> dict[str, Any]:
        """Record a skill execution result."""
        return self._store.append_skill_event(
            run_id,
            "skill_result",
            skill_id,
            payload,
            payload_summary=payload_summary or summarize_json(payload),
        )
