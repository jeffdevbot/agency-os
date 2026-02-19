"""C10E: Actor-scoped durable preference memory for AgencyClaw.

Stores per-user defaults (e.g., default_client_id) that persist across
sessions.  One row per profile_id in ``agencyclaw_user_preferences``.

Pure precedence resolver included — no LLM call, no side effects.
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from supabase import Client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class UserPreferences(TypedDict):
    profile_id: str
    default_client_id: str | None
    preferences: dict[str, Any]


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class PreferenceMemoryService:
    """CRUD for ``agencyclaw_user_preferences``."""

    def __init__(self, supabase_client: Client) -> None:
        self.db = supabase_client

    def get_preferences(self, profile_id: str) -> UserPreferences | None:
        """Fetch preferences for a profile.  Returns None if no row."""
        profile_id = (profile_id or "").strip()
        if not profile_id:
            return None

        response = (
            self.db.table("agencyclaw_user_preferences")
            .select("profile_id,default_client_id,preferences")
            .eq("profile_id", profile_id)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            return None

        row = rows[0]
        return UserPreferences(
            profile_id=str(row.get("profile_id") or ""),
            default_client_id=str(row["default_client_id"]) if row.get("default_client_id") else None,
            preferences=row.get("preferences") if isinstance(row.get("preferences"), dict) else {},
        )

    def get_default_client_id(self, profile_id: str) -> str | None:
        """Convenience: fetch just the default_client_id."""
        prefs = self.get_preferences(profile_id)
        if prefs is None:
            return None
        return prefs["default_client_id"]

    def set_default_client(self, profile_id: str, client_id: str) -> None:
        """Upsert default_client_id for profile."""
        profile_id = (profile_id or "").strip()
        client_id = (client_id or "").strip()
        if not profile_id or not client_id:
            return

        self.db.table("agencyclaw_user_preferences").upsert(
            {
                "profile_id": profile_id,
                "default_client_id": client_id,
            },
            on_conflict="profile_id",
        ).execute()

    def clear_default_client(self, profile_id: str) -> None:
        """Set default_client_id to NULL."""
        profile_id = (profile_id or "").strip()
        if not profile_id:
            return

        # Only update if row exists
        self.db.table("agencyclaw_user_preferences").update(
            {"default_client_id": None}
        ).eq("profile_id", profile_id).execute()


# ---------------------------------------------------------------------------
# Precedence resolver (pure function)
# ---------------------------------------------------------------------------


def resolve_client_with_preferences(
    *,
    pending_client_id: str | None = None,
    pref_client_id: str | None = None,
    session_client_id: str | None = None,
) -> str | None:
    """Return the highest-precedence client_id, or None.

    Precedence (highest wins):
    1. Explicit message hint — handled upstream by find_client_matches
    2. Pending thread context
    3. Actor preferences (durable)
    4. Session active client (ephemeral)
    """
    return pending_client_id or pref_client_id or session_client_id
