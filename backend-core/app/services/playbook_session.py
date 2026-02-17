from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from supabase import Client, create_client

from ..config import settings


class PlaybookSessionError(Exception):
    pass


class PlaybookSessionConfigurationError(PlaybookSessionError):
    pass


@dataclass(frozen=True)
class PlaybookSession:
    id: str
    slack_user_id: str
    profile_id: Optional[str]
    active_client_id: Optional[str]
    context: dict[str, Any]
    last_message_at: Optional[str] = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cutoff_iso(minutes: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def _coerce_session(row: dict[str, Any]) -> PlaybookSession:
    return PlaybookSession(
        id=str(row.get("id") or ""),
        slack_user_id=str(row.get("slack_user_id") or ""),
        profile_id=str(row.get("profile_id")) if row.get("profile_id") else None,
        active_client_id=str(row.get("active_client_id")) if row.get("active_client_id") else None,
        context=row.get("context") if isinstance(row.get("context"), dict) else {},
        last_message_at=str(row.get("last_message_at")) if row.get("last_message_at") else None,
    )


class PlaybookSessionService:
    def __init__(self, supabase_client: Client) -> None:
        self.db = supabase_client

    def get_active_session(self, slack_user_id: str) -> Optional[PlaybookSession]:
        slack_user_id = (slack_user_id or "").strip()
        if not slack_user_id:
            return None

        response = (
            self.db.table("playbook_slack_sessions")
            .select("*")
            .eq("slack_user_id", slack_user_id)
            .gt("last_message_at", _cutoff_iso(30))
            .order("last_message_at", desc=True)
            .limit(1)
            .execute()
        )

        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            return None
        return _coerce_session(rows[0])

    def get_profile_id_by_slack_user_id(self, slack_user_id: str) -> Optional[str]:
        slack_user_id = (slack_user_id or "").strip()
        if not slack_user_id:
            return None

        response = (
            self.db.table("profiles")
            .select("id")
            .eq("slack_user_id", slack_user_id)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            return None
        profile_id = rows[0].get("id")
        return str(profile_id) if profile_id else None

    def create_session(self, slack_user_id: str, profile_id: Optional[str]) -> PlaybookSession:
        slack_user_id = (slack_user_id or "").strip()
        if not slack_user_id:
            raise PlaybookSessionError("Missing slack_user_id")

        payload: dict[str, Any] = {
            "slack_user_id": slack_user_id,
            "profile_id": profile_id,
            "last_message_at": _utc_now_iso(),
        }

        response = self.db.table("playbook_slack_sessions").insert(payload).execute()
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise PlaybookSessionError("Failed to create session")
        return _coerce_session(rows[0])

    def touch_session(self, session_id: str) -> None:
        session_id = (session_id or "").strip()
        if not session_id:
            return
        self.db.table("playbook_slack_sessions").update({"last_message_at": _utc_now_iso()}).eq(
            "id", session_id
        ).execute()

    def set_active_client(self, session_id: str, client_id: str) -> None:
        session_id = (session_id or "").strip()
        client_id = (client_id or "").strip()
        if not session_id or not client_id:
            return
        self.db.table("playbook_slack_sessions").update(
            {"active_client_id": client_id, "last_message_at": _utc_now_iso()}
        ).eq("id", session_id).execute()

    def update_context(self, session_id: str, context_updates: dict[str, Any]) -> None:
        """Merge updates into session context (e.g., store pending_task)."""
        session_id = (session_id or "").strip()
        if not session_id or not context_updates:
            return

        # Fetch current context
        response = (
            self.db.table("playbook_slack_sessions")
            .select("context")
            .eq("id", session_id)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        current_context = rows[0].get("context") if rows else {}
        if not isinstance(current_context, dict):
            current_context = {}

        # Merge updates (None values are stored as null in JSONB)
        for key, value in context_updates.items():
            current_context[key] = value

        self.db.table("playbook_slack_sessions").update(
            {"context": current_context, "last_message_at": _utc_now_iso()}
        ).eq("id", session_id).execute()

    def get_session_by_id(self, session_id: str) -> Optional[PlaybookSession]:
        """Get session by ID (used to refresh session after context update)."""
        session_id = (session_id or "").strip()
        if not session_id:
            return None

        response = (
            self.db.table("playbook_slack_sessions")
            .select("*")
            .eq("id", session_id)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            return None
        return _coerce_session(rows[0])

    def ensure_session_profile_link(self, session: PlaybookSession) -> PlaybookSession:
        if session.profile_id:
            return session

        profile_id = self.get_profile_id_by_slack_user_id(session.slack_user_id)
        if not profile_id:
            return session

        self.db.table("playbook_slack_sessions").update({"profile_id": profile_id}).eq(
            "id", session.id
        ).execute()

        return PlaybookSession(
            id=session.id,
            slack_user_id=session.slack_user_id,
            profile_id=profile_id,
            active_client_id=session.active_client_id,
            context=session.context,
            last_message_at=session.last_message_at,
        )

    def get_or_create_session(self, slack_user_id: str) -> PlaybookSession:
        existing = self.get_active_session(slack_user_id)
        if existing:
            return self.ensure_session_profile_link(existing)

        profile_id = self.get_profile_id_by_slack_user_id(slack_user_id)
        return self.create_session(slack_user_id=slack_user_id, profile_id=profile_id)

    def list_clients_for_picker(self, profile_id: Optional[str]) -> list[dict[str, Any]]:
        """
        Return clients a user can pick from.

        Prefer assigned clients (via `client_assignments`), with a fallback to all active clients.
        """
        if profile_id:
            for column in ("team_member_id", "profile_id"):
                try:
                    assignments = (
                        self.db.table("client_assignments")
                        .select("agency_clients(id,name,status)")
                        .eq(column, profile_id)
                        .execute()
                    )
                    rows = assignments.data if isinstance(assignments.data, list) else []
                    nested = []
                    for row in rows:
                        client = row.get("agency_clients")
                        if isinstance(client, dict) and client.get("id") and client.get("name"):
                            nested.append(client)
                    # If user has any assignments, only show those.
                    if nested:
                        active = [c for c in nested if c.get("status") in (None, "active")]
                        return sorted(active, key=lambda c: str(c.get("name") or "").lower())
                except Exception:  # noqa: BLE001
                    continue

        response = (
            self.db.table("agency_clients")
            .select("id,name,status")
            .eq("status", "active")
            .order("name", desc=False)
            .limit(25)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        return [c for c in rows if isinstance(c, dict) and c.get("id") and c.get("name")]

    def get_client_name(self, client_id: str) -> Optional[str]:
        client_id = (client_id or "").strip()
        if not client_id:
            return None
        response = (
            self.db.table("agency_clients").select("name").eq("id", client_id).limit(1).execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            return None
        name = rows[0].get("name")
        return str(name) if name else None

    def get_profile_clickup_user_id(self, profile_id: str) -> Optional[str]:
        profile_id = (profile_id or "").strip()
        if not profile_id:
            return None
        response = (
            self.db.table("profiles")
            .select("clickup_user_id")
            .eq("id", profile_id)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            return None
        value = rows[0].get("clickup_user_id")
        return str(value) if value else None

    def get_brand_destination_for_client(self, client_id: str) -> Optional[dict[str, Any]]:
        """
        Pick a brand under the given agency client that has ClickUp destination fields.

        Returns a dict with: id, name, clickup_space_id, clickup_list_id.
        """
        client_id = (client_id or "").strip()
        if not client_id:
            return None

        response = (
            self.db.table("brands")
            .select("id,name,clickup_space_id,clickup_list_id")
            .eq("client_id", client_id)
            .order("updated_at", desc=True)
            .limit(25)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        candidates = [r for r in rows if isinstance(r, dict)]

        # Prefer entries with a list id, but space id is required for our ClickUp helper.
        with_space = [b for b in candidates if b.get("clickup_space_id")]
        if not with_space:
            return None
        with_list = [b for b in with_space if b.get("clickup_list_id")]
        return (with_list[0] if with_list else with_space[0])

    def get_all_brand_destinations_for_client(self, client_id: str) -> list[dict[str, Any]]:
        """Return all brands with ClickUp destination fields for a client."""
        client_id = (client_id or "").strip()
        if not client_id:
            return []

        response = (
            self.db.table("brands")
            .select("id,name,clickup_space_id,clickup_list_id")
            .eq("client_id", client_id)
            .order("updated_at", desc=True)
            .limit(50)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        return [
            r
            for r in rows
            if isinstance(r, dict) and (r.get("clickup_space_id") or r.get("clickup_list_id"))
        ]

    def find_client_matches(self, profile_id: Optional[str], query: str) -> list[dict[str, Any]]:
        query_norm = " ".join((query or "").strip().lower().split())
        if not query_norm:
            return []

        candidates: list[dict[str, Any]] = []
        try:
            candidates.extend(self.list_clients_for_picker(profile_id))
        except Exception:  # noqa: BLE001
            pass

        try:
            response = (
                self.db.table("agency_clients")
                .select("id,name,status")
                .eq("status", "active")
                .order("name", desc=False)
                .limit(200)
                .execute()
            )
            rows = response.data if isinstance(response.data, list) else []
            candidates.extend([c for c in rows if isinstance(c, dict)])
        except Exception:  # noqa: BLE001
            pass

        dedup: dict[str, dict[str, Any]] = {}
        for c in candidates:
            cid = str(c.get("id") or "")
            name = str(c.get("name") or "")
            if not cid or not name:
                continue
            dedup[cid] = {"id": cid, "name": name, "status": c.get("status")}

        def score(name: str) -> tuple[int, int]:
            n = " ".join(name.lower().split())
            if n == query_norm:
                return (0, len(n))
            if n.startswith(query_norm):
                return (1, len(n))
            if query_norm in n:
                return (2, len(n))
            return (3, len(n))

        matches = []
        for c in dedup.values():
            n = str(c.get("name") or "")
            if query_norm in " ".join(n.lower().split()):
                matches.append(c)

        matches.sort(key=lambda c: score(str(c.get("name") or "")))
        return matches


_supabase_admin_client: Client | None = None


def get_supabase_admin_client() -> Client:
    global _supabase_admin_client  # noqa: PLW0603
    if _supabase_admin_client:
        return _supabase_admin_client
    if not settings.supabase_url or not settings.supabase_service_role:
        raise PlaybookSessionConfigurationError("Supabase credentials not configured")
    _supabase_admin_client = create_client(settings.supabase_url, settings.supabase_service_role)
    return _supabase_admin_client


def get_playbook_session_service() -> PlaybookSessionService:
    return PlaybookSessionService(get_supabase_admin_client())
