"""Storage wrapper for AgencyClaw agent loop tables (C17D prep).

This module is intentionally isolated from runtime wiring. It provides small,
typed helpers around:
- public.agent_runs
- public.agent_messages
- public.agent_skill_events
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from supabase import Client

RUN_TYPES = {"main", "planner"}
RUN_STATUSES = {"running", "completed", "blocked", "failed"}
MESSAGE_ROLES = {"user", "assistant", "system", "planner_report"}
SKILL_EVENT_TYPES = {"skill_call", "skill_result"}


def summarize_json(payload: dict[str, Any], max_chars: int = 280) -> str:
    """Return a deterministic, prompt-safe JSON summary string."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")
    if max_chars <= 0:
        raise ValueError("max_chars must be > 0")

    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    if len(rendered) <= max_chars:
        return rendered
    if max_chars <= 3:
        return rendered[:max_chars]
    return f"{rendered[: max_chars - 3]}..."


class AgentLoopStore:
    """Small data-access wrapper for agent loop storage tables."""

    def __init__(self, supabase_client: Client) -> None:
        self.db = supabase_client

    def create_run(
        self,
        session_id: str,
        run_type: str = "main",
        parent_run_id: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        session_id = _require_non_empty("session_id", session_id)
        run_type = _normalize_choice("run_type", run_type, RUN_TYPES)
        parent_run_id = _normalize_optional_id("parent_run_id", parent_run_id)
        trace_id = _normalize_optional_id("trace_id", trace_id)

        payload: dict[str, Any] = {
            "session_id": session_id,
            "run_type": run_type,
            "status": "running",
            # Legacy runtime-isolation schema requires run_key (NOT NULL).
            # Use stable session scope so modern + legacy shapes both work.
            "run_key": f"session:{session_id}",
        }
        if parent_run_id is not None:
            payload["parent_run_id"] = parent_run_id
        if trace_id is not None:
            payload["trace_id"] = trace_id

        response = self.db.table("agent_runs").insert(payload).execute()
        return _first_row(response)

    def append_message(
        self,
        run_id: str,
        role: str,
        content: dict[str, Any],
        summary: str | None = None,
    ) -> dict[str, Any]:
        run_id = _require_non_empty("run_id", run_id)
        role = _normalize_choice("role", role, MESSAGE_ROLES)
        if not isinstance(content, dict):
            raise ValueError("content must be a dict")

        payload: dict[str, Any] = {
            "run_id": run_id,
            "role": role,
            "content": content,
        }
        if summary is not None:
            payload["summary"] = str(summary)

        response = self.db.table("agent_messages").insert(payload).execute()
        return _first_row(response)

    def append_skill_event(
        self,
        run_id: str,
        event_type: str,
        skill_id: str,
        payload: dict[str, Any],
        payload_summary: str | None = None,
    ) -> dict[str, Any]:
        run_id = _require_non_empty("run_id", run_id)
        event_type = _normalize_choice("event_type", event_type, SKILL_EVENT_TYPES)
        skill_id = _require_non_empty("skill_id", skill_id)
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")

        row: dict[str, Any] = {
            "run_id": run_id,
            "event_type": event_type,
            "skill_id": skill_id,
            "payload": payload,
        }
        if payload_summary is not None:
            row["payload_summary"] = str(payload_summary)

        response = self.db.table("agent_skill_events").insert(row).execute()
        return _first_row(response)

    def update_run_status(self, run_id: str, status: str, completed: bool = False) -> None:
        run_id = _require_non_empty("run_id", run_id)
        status = _normalize_choice("status", status, RUN_STATUSES)

        payload: dict[str, Any] = {"status": status}
        if completed:
            payload["completed_at"] = datetime.now(timezone.utc).isoformat()

        self.db.table("agent_runs").update(payload).eq("id", run_id).execute()

    def set_run_trace_id(self, run_id: str, trace_id: str) -> None:
        run_id = _require_non_empty("run_id", run_id)
        trace_id = _require_non_empty("trace_id", trace_id)
        self.db.table("agent_runs").update({"trace_id": trace_id}).eq("id", run_id).execute()

    def get_skill_event_by_id(self, run_id: str, event_id: str) -> dict[str, Any]:
        """Fetch a single skill event by run and event ID.

        Returns the row dict, or ``{}`` if not found.
        """
        run_id = _require_non_empty("run_id", run_id)
        event_id = _require_non_empty("event_id", event_id)

        response = (
            self.db.table("agent_skill_events")
            .select("*")
            .eq("run_id", run_id)
            .eq("id", event_id)
            .limit(1)
            .execute()
        )
        return _first_row(response)

    def list_recent_skill_events(self, run_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """Fetch recent skill events for a run, newest first.

        Returns a list of row dicts, or ``[]`` if none found.
        """
        run_id = _require_non_empty("run_id", run_id)
        if limit <= 0:
            raise ValueError("limit must be > 0")

        response = (
            self.db.table("agent_skill_events")
            .select("*")
            .eq("run_id", run_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        return [row for row in rows if isinstance(row, dict)]

    def list_recent_run_messages(self, run_id: str, limit: int = 20) -> list[dict[str, Any]]:
        run_id = _require_non_empty("run_id", run_id)
        if limit <= 0:
            raise ValueError("limit must be > 0")

        response = (
            self.db.table("agent_messages")
            .select("*")
            .eq("run_id", run_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        return [row for row in rows if isinstance(row, dict)]


def _first_row(response: Any) -> dict[str, Any]:
    rows = response.data if isinstance(getattr(response, "data", None), list) else []
    if not rows:
        return {}
    first = rows[0]
    return first if isinstance(first, dict) else {}


def _require_non_empty(name: str, value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError(f"{name} is required")
    return normalized


def _normalize_optional_id(name: str, value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must be non-empty when provided")
    return normalized


def _normalize_choice(name: str, value: str, allowed: set[str]) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError(f"{name} is required")
    if normalized not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise ValueError(f"{name} must be one of: {allowed_text}")
    return normalized
