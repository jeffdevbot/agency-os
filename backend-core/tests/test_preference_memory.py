"""Tests for C10E: Durable preference memory (actor-scoped).

Covers:
- get_default_client_id returns id when row exists
- get_default_client_id returns None when no row
- set_default_client calls upsert with correct payload
- clear_default_client nullifies default_client_id
- set/clear with empty profile_id is a no-op
- get_preferences returns correct UserPreferences
- Precedence resolver: pending > pref > session
- Precedence resolver: all None returns None
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.services.agencyclaw.preference_memory import (
    PreferenceMemoryService,
    UserPreferences,
    resolve_client_with_preferences,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_db(
    select_rows: list[dict[str, Any]] | None = None,
) -> MagicMock:
    """Build a mock Supabase client that returns ``select_rows`` on select queries."""
    db = MagicMock()
    response = MagicMock()
    response.data = select_rows or []

    # Chain: db.table(...).select(...).eq(...).limit(...).execute()
    table = MagicMock()
    db.table.return_value = table
    table.select.return_value = table
    table.eq.return_value = table
    table.limit.return_value = table
    table.execute.return_value = response
    table.upsert.return_value = table
    table.update.return_value = table

    return db


# ---------------------------------------------------------------------------
# CRUD tests
# ---------------------------------------------------------------------------


class TestGetDefaultClientId:
    def test_returns_id_when_row_exists(self):
        db = _mock_db([{
            "profile_id": "p1",
            "default_client_id": "c1",
            "preferences": {},
        }])
        svc = PreferenceMemoryService(db)

        assert svc.get_default_client_id("p1") == "c1"

    def test_returns_none_when_no_row(self):
        db = _mock_db([])
        svc = PreferenceMemoryService(db)

        assert svc.get_default_client_id("p1") is None

    def test_returns_none_when_default_client_is_null(self):
        db = _mock_db([{
            "profile_id": "p1",
            "default_client_id": None,
            "preferences": {},
        }])
        svc = PreferenceMemoryService(db)

        assert svc.get_default_client_id("p1") is None

    def test_empty_profile_id_returns_none(self):
        db = _mock_db()
        svc = PreferenceMemoryService(db)

        assert svc.get_default_client_id("") is None
        db.table.assert_not_called()

    def test_whitespace_profile_id_returns_none(self):
        db = _mock_db()
        svc = PreferenceMemoryService(db)

        assert svc.get_default_client_id("  ") is None
        db.table.assert_not_called()


class TestSetDefaultClient:
    def test_calls_upsert(self):
        db = _mock_db()
        svc = PreferenceMemoryService(db)

        svc.set_default_client("p1", "c1")

        db.table.assert_called_with("agencyclaw_user_preferences")
        db.table.return_value.upsert.assert_called_once_with(
            {"profile_id": "p1", "default_client_id": "c1"},
            on_conflict="profile_id",
        )

    def test_empty_profile_noop(self):
        db = _mock_db()
        svc = PreferenceMemoryService(db)

        svc.set_default_client("", "c1")
        db.table.assert_not_called()

    def test_empty_client_noop(self):
        db = _mock_db()
        svc = PreferenceMemoryService(db)

        svc.set_default_client("p1", "")
        db.table.assert_not_called()


class TestClearDefaultClient:
    def test_calls_update_with_none(self):
        db = _mock_db()
        svc = PreferenceMemoryService(db)

        svc.clear_default_client("p1")

        db.table.assert_called_with("agencyclaw_user_preferences")
        db.table.return_value.update.assert_called_once_with({"default_client_id": None})

    def test_empty_profile_noop(self):
        db = _mock_db()
        svc = PreferenceMemoryService(db)

        svc.clear_default_client("")
        db.table.assert_not_called()


class TestGetPreferences:
    def test_returns_typed_dict(self):
        db = _mock_db([{
            "profile_id": "p1",
            "default_client_id": "c1",
            "preferences": {"theme": "dark"},
        }])
        svc = PreferenceMemoryService(db)

        prefs = svc.get_preferences("p1")

        assert prefs is not None
        assert prefs["profile_id"] == "p1"
        assert prefs["default_client_id"] == "c1"
        assert prefs["preferences"] == {"theme": "dark"}

    def test_returns_none_when_no_row(self):
        db = _mock_db([])
        svc = PreferenceMemoryService(db)

        assert svc.get_preferences("p1") is None

    def test_coerces_non_dict_preferences(self):
        db = _mock_db([{
            "profile_id": "p1",
            "default_client_id": None,
            "preferences": "not a dict",
        }])
        svc = PreferenceMemoryService(db)

        prefs = svc.get_preferences("p1")
        assert prefs is not None
        assert prefs["preferences"] == {}


# ---------------------------------------------------------------------------
# Precedence resolver tests
# ---------------------------------------------------------------------------


class TestResolvePrecedence:
    def test_pending_wins_over_pref(self):
        result = resolve_client_with_preferences(
            pending_client_id="c_pending",
            pref_client_id="c_pref",
            session_client_id="c_session",
        )
        assert result == "c_pending"

    def test_pref_wins_over_session(self):
        result = resolve_client_with_preferences(
            pending_client_id=None,
            pref_client_id="c_pref",
            session_client_id="c_session",
        )
        assert result == "c_pref"

    def test_session_fallback(self):
        result = resolve_client_with_preferences(
            pending_client_id=None,
            pref_client_id=None,
            session_client_id="c_session",
        )
        assert result == "c_session"

    def test_all_none(self):
        result = resolve_client_with_preferences(
            pending_client_id=None,
            pref_client_id=None,
            session_client_id=None,
        )
        assert result is None

    def test_empty_strings_treated_as_falsy(self):
        result = resolve_client_with_preferences(
            pending_client_id="",
            pref_client_id="",
            session_client_id="c_session",
        )
        assert result == "c_session"

    def test_pending_none_pref_set(self):
        result = resolve_client_with_preferences(
            pref_client_id="c_pref",
        )
        assert result == "c_pref"


# ---------------------------------------------------------------------------
# Classifier integration tests
# ---------------------------------------------------------------------------


class TestClassifierPreferenceCommands:
    """Verify _classify_message recognizes set/clear preference commands."""

    def test_set_default_client(self):
        from app.api.routes.slack import _classify_message

        intent, params = _classify_message("set my default client to Distex")
        assert intent == "set_default_client"
        assert params["client_name"] == "distex"

    def test_set_default_client_short(self):
        from app.api.routes.slack import _classify_message

        intent, params = _classify_message("set default client Acme Corp")
        assert intent == "set_default_client"
        assert params["client_name"] == "acme corp"

    def test_clear_defaults(self):
        from app.api.routes.slack import _classify_message

        intent, _params = _classify_message("clear my defaults")
        assert intent == "clear_defaults"

    def test_clear_default_client(self):
        from app.api.routes.slack import _classify_message

        intent, _params = _classify_message("clear my default client")
        assert intent == "clear_defaults"

    def test_clear_defaults_short(self):
        from app.api.routes.slack import _classify_message

        intent, _params = _classify_message("clear defaults")
        assert intent == "clear_defaults"
