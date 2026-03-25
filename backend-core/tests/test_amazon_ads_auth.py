"""Tests for Amazon Ads OAuth state signing, callback, connection, discovery, and select-profile."""

from __future__ import annotations

import json
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import wbr
from app.services.wbr.amazon_ads_auth import (
    STATE_MAX_AGE_SECONDS,
    create_signed_state,
    verify_signed_state,
)
from app.services.wbr.profiles import WBRNotFoundError, WBRValidationError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    """Ensure required env vars are set for all tests."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-jwt-secret-at-least-32-chars-long")
    monkeypatch.setenv("AMAZON_ADS_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("AMAZON_ADS_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("AMAZON_ADS_REDIRECT_URI", "https://backend.test/amazon-ads/callback")
    monkeypatch.setenv("FRONTEND_URL", "https://app.test")


def _override_admin():
    return {"sub": "user-123"}


# ---------------------------------------------------------------------------
# Unit tests: signed state
# ---------------------------------------------------------------------------


class TestSignedState:
    def test_create_and_verify_roundtrip(self):
        state = create_signed_state(
            profile_id="prof-1",
            initiated_by="user-1",
            return_path="/reports/test/us/wbr/sync/ads-api",
        )
        payload = verify_signed_state(state)
        assert payload["pid"] == "prof-1"
        assert payload["uid"] == "user-1"
        assert payload["ret"] == "/reports/test/us/wbr/sync/ads-api"
        assert "nonce" in payload
        assert "iat" in payload

    def test_tampered_signature_rejected(self):
        state = create_signed_state(
            profile_id="prof-1", initiated_by="user-1", return_path="/test"
        )
        parts = state.split(".")
        tampered = parts[0] + "." + "a" * 64
        with pytest.raises(WBRValidationError, match="signature"):
            verify_signed_state(tampered)

    def test_tampered_body_rejected(self):
        state = create_signed_state(
            profile_id="prof-1", initiated_by="user-1", return_path="/test"
        )
        parts = state.split(".")
        # Alter a character in the body portion
        body = parts[0]
        altered = body[:-1] + ("A" if body[-1] != "A" else "B")
        tampered = altered + "." + parts[1]
        with pytest.raises(WBRValidationError):
            verify_signed_state(tampered)

    def test_expired_state_rejected(self, monkeypatch):
        state = create_signed_state(
            profile_id="prof-1", initiated_by="user-1", return_path="/test"
        )
        # Advance time past expiry
        future = time.time() + STATE_MAX_AGE_SECONDS + 60
        monkeypatch.setattr(time, "time", lambda: future)
        with pytest.raises(WBRValidationError, match="expired"):
            verify_signed_state(state)

    def test_missing_dot_rejected(self):
        with pytest.raises(WBRValidationError, match="format"):
            verify_signed_state("no-dot-here")

    def test_empty_state_rejected(self):
        with pytest.raises(WBRValidationError, match="format"):
            verify_signed_state("")

    def test_unique_nonces(self):
        s1 = create_signed_state(profile_id="p", initiated_by=None, return_path="/")
        s2 = create_signed_state(profile_id="p", initiated_by=None, return_path="/")
        assert s1 != s2


# ---------------------------------------------------------------------------
# Router tests: helpers
# ---------------------------------------------------------------------------


class _FakeProfileService:
    """Minimal stub that supports get_profile and update_profile."""

    def __init__(self, profile: dict | None = None):
        self._profile = profile or {
            "id": "prof-1",
            "client_id": "client-1",
            "marketplace_code": "US",
            "display_name": "Test WBR",
            "week_start_day": "sunday",
            "status": "active",
            "windsor_account_id": None,
            "amazon_ads_profile_id": None,
            "amazon_ads_account_id": None,
            "amazon_ads_country_code": None,
            "amazon_ads_currency_code": None,
            "amazon_ads_marketplace_string_id": None,
            "backfill_start_date": None,
            "daily_rewrite_days": 14,
        }
        self.last_update = None

    def get_profile(self, profile_id: str) -> dict:
        if profile_id != self._profile["id"]:
            raise WBRNotFoundError(f"Profile {profile_id} not found")
        return self._profile

    def update_profile(self, profile_id: str, updates: dict, user_id: str | None = None) -> dict:
        if profile_id != self._profile["id"]:
            raise WBRNotFoundError(f"Profile {profile_id} not found")
        self.last_update = {"profile_id": profile_id, "updates": updates, "user_id": user_id}
        return {**self._profile, **updates}


class _FakeSupabase:
    """Minimal stub for Supabase client used in connection endpoints.

    Accepts either ``connection_rows`` (legacy: same rows for all tables) or
    ``tables`` (dict mapping table_name -> row_list) for table-specific stubs.
    """

    def __init__(
        self,
        connection_rows: list | None = None,
        *,
        tables: dict[str, list] | None = None,
    ):
        self._connection_rows = connection_rows or []
        self._tables = tables
        self.inserts: list[dict] = []
        self.updates: list[dict] = []

    def table(self, name: str):
        rows = self._tables[name] if self._tables and name in self._tables else self._connection_rows
        return _FakeTable(name, list(rows), self)


class _FakeTable:
    def __init__(self, name: str, rows: list, parent: _FakeSupabase):
        self._name = name
        self._rows = rows
        self._parent = parent
        self._filters_eq: dict = {}
        self._pending_op: str | None = None
        self._pending_data: dict | None = None

    def select(self, *args, **kwargs):
        self._pending_op = "select"
        return self

    def eq(self, col, val):
        self._filters_eq[col] = val
        return self

    def limit(self, n):
        return self

    def insert(self, data, **kwargs):
        self._pending_op = "insert"
        self._pending_data = data
        return self

    def update(self, data, **kwargs):
        self._pending_op = "update"
        self._pending_data = data
        return self

    def upsert(self, data, **kwargs):
        self._pending_op = "upsert"
        self._pending_data = data
        return self

    def execute(self):
        if self._pending_op == "insert":
            self._parent.inserts.append(self._pending_data)
        elif self._pending_op == "update":
            self._parent.updates.append(self._pending_data)
        # Apply eq filters for select operations
        filtered = self._rows
        if self._pending_op == "select" and self._filters_eq:
            filtered = [
                row for row in filtered
                if all(row.get(col) == val for col, val in self._filters_eq.items())
            ]
        resp = MagicMock()
        resp.data = filtered
        return resp


# ---------------------------------------------------------------------------
# Router tests: connect endpoint
# ---------------------------------------------------------------------------


class TestConnectEndpoint:
    def test_returns_authorization_url(self, monkeypatch):
        fake_svc = _FakeProfileService()
        monkeypatch.setattr(wbr, "_get_service", lambda: fake_svc)
        app.dependency_overrides[wbr.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.post(
                    "/admin/wbr/profiles/prof-1/amazon-ads/connect",
                    json={"return_path": "/reports/test/us/wbr/sync/ads-api"},
                )
            assert resp.status_code == 200
            body = resp.json()
            assert body["ok"] is True
            url = body["authorization_url"]
            assert "amazon.com" in url
            assert "client_id=test-client-id" in url
            assert "state=" in url
        finally:
            app.dependency_overrides.pop(wbr.require_admin_user, None)

    def test_404_for_unknown_profile(self, monkeypatch):
        fake_svc = _FakeProfileService()
        monkeypatch.setattr(wbr, "_get_service", lambda: fake_svc)
        app.dependency_overrides[wbr.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.post(
                    "/admin/wbr/profiles/unknown/amazon-ads/connect",
                    json={"return_path": "/test"},
                )
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(wbr.require_admin_user, None)


# ---------------------------------------------------------------------------
# Router tests: connection status
# ---------------------------------------------------------------------------


class TestConnectionStatusEndpoint:
    def test_not_connected(self, monkeypatch):
        fake_svc = _FakeProfileService()
        monkeypatch.setattr(wbr, "_get_service", lambda: fake_svc)
        monkeypatch.setattr(
            wbr,
            "_get_supabase",
            lambda: _FakeSupabase(
                tables={
                    "report_api_connections": [],
                    "wbr_amazon_ads_connections": [],
                }
            ),
        )
        app.dependency_overrides[wbr.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.get("/admin/wbr/profiles/prof-1/amazon-ads/connection")
            assert resp.status_code == 200
            body = resp.json()
            assert body["connected"] is False
            assert body["connection"] is None
        finally:
            app.dependency_overrides.pop(wbr.require_admin_user, None)

    def test_connected_via_shared(self, monkeypatch):
        shared_conn = {
            "client_id": "client-1",
            "provider": "amazon_ads",
            "connection_status": "connected",
            "connected_at": "2026-03-18T12:00:00Z",
            "last_validated_at": None,
            "last_error": None,
            "updated_at": "2026-03-18T12:00:00Z",
            "access_meta": {"lwa_account_hint": "test@example.com"},
        }
        fake_svc = _FakeProfileService()
        monkeypatch.setattr(wbr, "_get_service", lambda: fake_svc)
        monkeypatch.setattr(
            wbr,
            "_get_supabase",
            lambda: _FakeSupabase(
                tables={
                    "report_api_connections": [shared_conn],
                    "wbr_amazon_ads_connections": [],
                }
            ),
        )
        app.dependency_overrides[wbr.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.get("/admin/wbr/profiles/prof-1/amazon-ads/connection")
            assert resp.status_code == 200
            body = resp.json()
            assert body["connected"] is True
            assert body["source"] == "shared"
            assert body["connection"]["profile_id"] == "prof-1"
            assert body["connection"]["lwa_account_hint"] == "test@example.com"
        finally:
            app.dependency_overrides.pop(wbr.require_admin_user, None)

    def test_connected_falls_back_to_legacy(self, monkeypatch):
        conn = {
            "profile_id": "prof-1",
            "connected_at": "2026-03-13T12:00:00Z",
            "lwa_account_hint": None,
            "created_at": "2026-03-13T12:00:00Z",
            "updated_at": "2026-03-13T12:00:00Z",
        }
        fake_svc = _FakeProfileService()
        monkeypatch.setattr(wbr, "_get_service", lambda: fake_svc)
        monkeypatch.setattr(
            wbr,
            "_get_supabase",
            lambda: _FakeSupabase(
                tables={
                    "report_api_connections": [],
                    "wbr_amazon_ads_connections": [conn],
                }
            ),
        )
        app.dependency_overrides[wbr.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.get("/admin/wbr/profiles/prof-1/amazon-ads/connection")
            assert resp.status_code == 200
            body = resp.json()
            assert body["connected"] is True
            assert body["source"] == "legacy"
            assert body["connection"]["profile_id"] == "prof-1"
        finally:
            app.dependency_overrides.pop(wbr.require_admin_user, None)

    def test_shared_error_is_not_reported_as_connected(self, monkeypatch):
        shared_conn = {
            "client_id": "client-1",
            "provider": "amazon_ads",
            "connection_status": "error",
            "connected_at": "2026-03-18T12:00:00Z",
            "last_validated_at": None,
            "last_error": "token refresh failed",
            "updated_at": "2026-03-18T12:00:00Z",
            "access_meta": {"lwa_account_hint": "test@example.com"},
        }
        fake_svc = _FakeProfileService()
        monkeypatch.setattr(wbr, "_get_service", lambda: fake_svc)
        monkeypatch.setattr(
            wbr,
            "_get_supabase",
            lambda: _FakeSupabase(
                tables={
                    "report_api_connections": [shared_conn],
                    "wbr_amazon_ads_connections": [],
                }
            ),
        )
        app.dependency_overrides[wbr.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.get("/admin/wbr/profiles/prof-1/amazon-ads/connection")
            assert resp.status_code == 200
            body = resp.json()
            assert body["source"] == "shared"
            assert body["connected"] is False
            assert body["connection"]["connection_status"] == "error"
        finally:
            app.dependency_overrides.pop(wbr.require_admin_user, None)


# ---------------------------------------------------------------------------
# Router tests: select-profile
# ---------------------------------------------------------------------------


class TestSelectProfileEndpoint:
    def test_writes_both_fields(self, monkeypatch):
        fake_svc = _FakeProfileService()
        monkeypatch.setattr(wbr, "_get_service", lambda: fake_svc)
        app.dependency_overrides[wbr.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.post(
                    "/admin/wbr/profiles/prof-1/amazon-ads/select-profile",
                    json={
                        "amazon_ads_profile_id": "1234567890",
                        "amazon_ads_account_id": "ACCT-999",
                        "amazon_ads_country_code": "US",
                        "amazon_ads_currency_code": "USD",
                        "amazon_ads_marketplace_string_id": "ATVPDKIKX0DER",
                    },
                )
            assert resp.status_code == 200
            assert fake_svc.last_update is not None
            updates = fake_svc.last_update["updates"]
            assert updates["amazon_ads_profile_id"] == "1234567890"
            assert updates["amazon_ads_account_id"] == "ACCT-999"
            assert updates["amazon_ads_country_code"] == "US"
            assert updates["amazon_ads_currency_code"] == "USD"
            assert updates["amazon_ads_marketplace_string_id"] == "ATVPDKIKX0DER"
        finally:
            app.dependency_overrides.pop(wbr.require_admin_user, None)

    def test_clears_account_id_when_absent(self, monkeypatch):
        """When no account_id is provided, it should be explicitly set to None."""
        fake_svc = _FakeProfileService(
            profile={
                "id": "prof-1",
                "client_id": "client-1",
                "marketplace_code": "US",
                "display_name": "Test",
                "week_start_day": "sunday",
                "status": "active",
                "windsor_account_id": None,
                "amazon_ads_profile_id": "old-profile",
                "amazon_ads_account_id": "old-account",
                "amazon_ads_country_code": "CA",
                "amazon_ads_currency_code": "CAD",
                "amazon_ads_marketplace_string_id": "A2EUQ1WTGCTBG2",
                "backfill_start_date": None,
                "daily_rewrite_days": 14,
            }
        )
        monkeypatch.setattr(wbr, "_get_service", lambda: fake_svc)
        app.dependency_overrides[wbr.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.post(
                    "/admin/wbr/profiles/prof-1/amazon-ads/select-profile",
                    json={"amazon_ads_profile_id": "new-profile"},
                )
            assert resp.status_code == 200
            updates = fake_svc.last_update["updates"]
            assert updates["amazon_ads_profile_id"] == "new-profile"
            assert updates["amazon_ads_account_id"] is None
            assert updates["amazon_ads_country_code"] is None
            assert updates["amazon_ads_currency_code"] is None
            assert updates["amazon_ads_marketplace_string_id"] is None
        finally:
            app.dependency_overrides.pop(wbr.require_admin_user, None)

    def test_404_for_unknown_profile(self, monkeypatch):
        fake_svc = _FakeProfileService()
        monkeypatch.setattr(wbr, "_get_service", lambda: fake_svc)
        app.dependency_overrides[wbr.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.post(
                    "/admin/wbr/profiles/unknown/amazon-ads/select-profile",
                    json={"amazon_ads_profile_id": "123"},
                )
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(wbr.require_admin_user, None)


# ---------------------------------------------------------------------------
# Router tests: callback
# ---------------------------------------------------------------------------


class TestCallbackEndpoint:
    def test_callback_invalid_state_returns_400(self):
        with TestClient(app) as client:
            resp = client.get(
                "/amazon-ads/callback?code=test-code&state=invalid-state",
                follow_redirects=False,
            )
        assert resp.status_code == 400

    def test_callback_expired_state_returns_400(self, monkeypatch):
        state = create_signed_state(
            profile_id="prof-1",
            initiated_by="user-1",
            return_path="/test",
        )
        # Fast-forward time past expiry
        future = time.time() + STATE_MAX_AGE_SECONDS + 60
        monkeypatch.setattr(time, "time", lambda: future)

        with TestClient(app) as client:
            resp = client.get(
                f"/amazon-ads/callback?code=test-code&state={state}",
                follow_redirects=False,
            )
        assert resp.status_code == 400

    def test_callback_happy_path_inserts_new_connection(self, monkeypatch):
        """First-time connection: should INSERT a new row."""
        state = create_signed_state(
            profile_id="prof-1",
            initiated_by="user-1",
            return_path="/reports/test/us/wbr/sync/ads-api",
        )

        mock_exchange = AsyncMock(return_value={
            "access_token": "Atza|test",
            "refresh_token": "Atzr|test-refresh",
            "token_type": "bearer",
            "expires_in": 3600,
        })
        monkeypatch.setattr(
            "app.routers.amazon_ads_oauth.exchange_authorization_code",
            mock_exchange,
        )

        from app.routers import amazon_ads_oauth
        fake_db = _FakeSupabase([])  # no existing row
        monkeypatch.setattr(amazon_ads_oauth, "_get_supabase", lambda: fake_db)

        with TestClient(app) as client:
            resp = client.get(
                f"/amazon-ads/callback?code=auth-code-123&state={state}",
                follow_redirects=False,
            )

        assert resp.status_code == 302
        location = resp.headers["location"]
        assert "https://app.test/reports/test/us/wbr/sync/ads-api" in location
        mock_exchange.assert_called_once_with("auth-code-123")
        assert len(fake_db.inserts) == 1
        assert fake_db.inserts[0]["profile_id"] == "prof-1"
        assert fake_db.inserts[0]["amazon_ads_refresh_token"] == "Atzr|test-refresh"
        assert len(fake_db.updates) == 0

    def test_callback_happy_path_accepts_api_prefixed_route(self, monkeypatch):
        """Production redirect URI currently uses /api/amazon-ads/callback."""
        state = create_signed_state(
            profile_id="prof-1",
            initiated_by="user-1",
            return_path="/reports/test/us/wbr/sync/ads-api",
        )

        mock_exchange = AsyncMock(return_value={
            "access_token": "Atza|test",
            "refresh_token": "Atzr|test-refresh",
            "token_type": "bearer",
            "expires_in": 3600,
        })
        monkeypatch.setattr(
            "app.routers.amazon_ads_oauth.exchange_authorization_code",
            mock_exchange,
        )

        from app.routers import amazon_ads_oauth
        fake_db = _FakeSupabase([])
        monkeypatch.setattr(amazon_ads_oauth, "_get_supabase", lambda: fake_db)

        with TestClient(app) as client:
            resp = client.get(
                f"/api/amazon-ads/callback?code=auth-code-789&state={state}",
                follow_redirects=False,
            )

        assert resp.status_code == 302
        assert len(fake_db.inserts) == 1
        mock_exchange.assert_called_once_with("auth-code-789")

    def test_callback_updates_existing_connection(self, monkeypatch):
        """Re-connection: should UPDATE the existing row, not insert."""
        state = create_signed_state(
            profile_id="prof-1",
            initiated_by="user-1",
            return_path="/reports/test/us/wbr/sync/ads-api",
        )

        mock_exchange = AsyncMock(return_value={
            "access_token": "Atza|test",
            "refresh_token": "Atzr|new-refresh",
            "token_type": "bearer",
            "expires_in": 3600,
        })
        monkeypatch.setattr(
            "app.routers.amazon_ads_oauth.exchange_authorization_code",
            mock_exchange,
        )

        from app.routers import amazon_ads_oauth
        existing_row = [{"id": "conn-1", "profile_id": "prof-1"}]
        fake_db = _FakeSupabase(existing_row)
        monkeypatch.setattr(amazon_ads_oauth, "_get_supabase", lambda: fake_db)

        with TestClient(app) as client:
            resp = client.get(
                f"/amazon-ads/callback?code=auth-code-456&state={state}",
                follow_redirects=False,
            )

        assert resp.status_code == 302
        assert len(fake_db.updates) == 1
        assert fake_db.updates[0]["amazon_ads_refresh_token"] == "Atzr|new-refresh"
        assert "connected_at" in fake_db.updates[0]
        assert len(fake_db.inserts) == 0

    def test_callback_missing_profile_id_in_state(self):
        """State with empty profile_id should fail."""
        state = create_signed_state(
            profile_id="",
            initiated_by="user-1",
            return_path="/test",
        )
        with TestClient(app) as client:
            resp = client.get(
                f"/amazon-ads/callback?code=test&state={state}",
                follow_redirects=False,
            )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Router tests: discover profiles
# ---------------------------------------------------------------------------


class TestDiscoverProfilesEndpoint:
    def test_no_connection_returns_400(self, monkeypatch):
        fake_svc = _FakeProfileService()
        monkeypatch.setattr(wbr, "_get_service", lambda: fake_svc)
        monkeypatch.setattr(
            wbr,
            "_get_supabase",
            lambda: _FakeSupabase(
                tables={
                    "report_api_connections": [],
                    "wbr_amazon_ads_connections": [],
                }
            ),
        )
        app.dependency_overrides[wbr.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.get("/admin/wbr/profiles/prof-1/amazon-ads/profiles")
            assert resp.status_code == 400
            assert "Connect first" in resp.json()["detail"]
        finally:
            app.dependency_overrides.pop(wbr.require_admin_user, None)
