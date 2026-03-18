from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.main import app
from app.routers import amazon_ads_oauth, report_api_access
from app.services.wbr.amazon_ads_auth import create_signed_state


def _override_admin():
    return {"sub": "user-123"}


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-jwt-secret-at-least-32-chars-long")
    monkeypatch.setenv("AMAZON_ADS_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("AMAZON_ADS_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("AMAZON_ADS_REDIRECT_URI", "https://backend.test/amazon-ads/callback")
    monkeypatch.setenv("FRONTEND_URL", "https://app.test")


class _FakeSupabase:
    def __init__(self, tables: dict[str, list[dict]] | None = None):
        self.tables = {name: list(rows) for name, rows in (tables or {}).items()}
        self.inserts: dict[str, list[dict]] = {}
        self.updates: dict[str, list[dict]] = {}

    def table(self, name: str):
        return _FakeTable(self, name)


class _FakeTable:
    def __init__(self, db: _FakeSupabase, name: str):
        self._db = db
        self._name = name
        self._filters_eq: dict[str, object] = {}
        self._filters_neq: dict[str, object] = {}
        self._pending_op = "select"
        self._pending_data: dict | None = None
        self._order_key: str | None = None
        self._desc = False
        self._limit: int | None = None

    def select(self, *args, **kwargs):
        self._pending_op = "select"
        return self

    def eq(self, col, val):
        self._filters_eq[col] = val
        return self

    def neq(self, col, val):
        self._filters_neq[col] = val
        return self

    def limit(self, n):
        self._limit = n
        return self

    def order(self, key, desc=False):
        self._order_key = key
        self._desc = desc
        return self

    def insert(self, data, **kwargs):
        self._pending_op = "insert"
        self._pending_data = dict(data)
        return self

    def update(self, data, **kwargs):
        self._pending_op = "update"
        self._pending_data = dict(data)
        return self

    def execute(self):
        if self._pending_op == "insert":
            payload = dict(self._pending_data or {})
            self._db.tables.setdefault(self._name, []).append(payload)
            self._db.inserts.setdefault(self._name, []).append(payload)
            return type("Resp", (), {"data": [payload]})()

        rows = [dict(row) for row in self._db.tables.get(self._name, [])]
        for col, val in self._filters_eq.items():
            rows = [row for row in rows if row.get(col) == val]
        for col, val in self._filters_neq.items():
            rows = [row for row in rows if row.get(col) != val]
        if self._order_key:
            rows.sort(key=lambda row: row.get(self._order_key) or "", reverse=self._desc)
        if self._limit is not None:
            rows = rows[: self._limit]

        if self._pending_op == "update":
            payload = dict(self._pending_data or {})
            updated_rows: list[dict] = []
            for row in self._db.tables.get(self._name, []):
                if all(row.get(col) == val for col, val in self._filters_eq.items()) and all(
                    row.get(col) != val for col, val in self._filters_neq.items()
                ):
                    row.update(payload)
                    updated_rows.append(dict(row))
            self._db.updates.setdefault(self._name, []).append(payload)
            return type("Resp", (), {"data": updated_rows})()

        return type("Resp", (), {"data": rows})()


class TestReportApiAccessRouter:
    def test_list_amazon_ads_connections_prefers_shared_over_legacy(self, monkeypatch):
        fake_db = _FakeSupabase(
            {
                "agency_clients": [
                    {"id": "client-1", "name": "Alpha", "status": "active"},
                    {"id": "client-2", "name": "Beta", "status": "active"},
                ],
                "wbr_profiles": [
                    {
                        "id": "prof-1",
                        "client_id": "client-1",
                        "marketplace_code": "US",
                        "display_name": "Alpha US",
                        "status": "active",
                        "amazon_ads_profile_id": "ads-1",
                        "amazon_ads_account_id": "acct-1",
                        "created_at": "2026-03-18T10:00:00+00:00",
                    },
                    {
                        "id": "prof-2",
                        "client_id": "client-2",
                        "marketplace_code": "CA",
                        "display_name": "Beta CA",
                        "status": "active",
                        "amazon_ads_profile_id": None,
                        "amazon_ads_account_id": None,
                        "created_at": "2026-03-18T11:00:00+00:00",
                    },
                ],
                "report_api_connections": [
                    {
                        "id": "shared-1",
                        "client_id": "client-1",
                        "provider": "amazon_ads",
                        "connection_status": "connected",
                        "external_account_id": None,
                        "region_code": None,
                        "access_meta": {"lwa_account_hint": "alpha@example.com"},
                        "connected_at": "2026-03-18T12:00:00+00:00",
                        "last_validated_at": None,
                        "last_error": None,
                        "updated_at": "2026-03-18T12:00:00+00:00",
                        "created_at": "2026-03-18T12:00:00+00:00",
                    }
                ],
                "wbr_amazon_ads_connections": [
                    {
                        "profile_id": "prof-2",
                        "connected_at": "2026-03-18T09:00:00+00:00",
                        "updated_at": "2026-03-18T09:00:00+00:00",
                        "lwa_account_hint": "beta@example.com",
                        "created_at": "2026-03-18T09:00:00+00:00",
                    }
                ],
            }
        )
        monkeypatch.setattr(report_api_access, "_get_supabase", lambda: fake_db)
        app.dependency_overrides[report_api_access.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                response = client.get("/admin/reports/api-access/amazon-ads/connections")
            assert response.status_code == 200
            body = response.json()
            assert body["ok"] is True
            rows = body["connections"]
            assert rows[0]["client_name"] == "Alpha"
            assert rows[0]["source"] == "shared"
            assert rows[0]["shared_connection"]["lwa_account_hint"] == "alpha@example.com"
            assert rows[1]["client_name"] == "Beta"
            assert rows[1]["source"] == "legacy"
            assert rows[1]["legacy_connection"]["profile_id"] == "prof-2"
        finally:
            app.dependency_overrides.pop(report_api_access.require_admin_user, None)

    def test_connect_endpoint_returns_authorization_url(self, monkeypatch):
        fake_db = _FakeSupabase(
            {
                "wbr_profiles": [
                    {
                        "id": "prof-1",
                        "client_id": "client-1",
                        "marketplace_code": "US",
                        "display_name": "Alpha US",
                        "status": "active",
                        "amazon_ads_profile_id": None,
                        "amazon_ads_account_id": None,
                        "created_at": "2026-03-18T10:00:00+00:00",
                    }
                ]
            }
        )
        monkeypatch.setattr(report_api_access, "_get_supabase", lambda: fake_db)
        app.dependency_overrides[report_api_access.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/admin/reports/api-access/amazon-ads/connect",
                    json={"profile_id": "prof-1", "return_path": "/reports/api-access"},
                )
            assert response.status_code == 200
            body = response.json()
            assert body["ok"] is True
            assert "amazon.com" in body["authorization_url"]
            assert body["profile"]["client_id"] == "client-1"
        finally:
            app.dependency_overrides.pop(report_api_access.require_admin_user, None)


class TestAmazonAdsCallbackSharedWrite:
    def test_callback_dual_writes_shared_connection_when_profile_has_client(self, monkeypatch):
        state = create_signed_state(
            profile_id="prof-1",
            initiated_by="user-1",
            return_path="/reports/api-access",
        )
        fake_db = _FakeSupabase(
            {
                "wbr_profiles": [
                    {
                        "id": "prof-1",
                        "client_id": "client-1",
                        "marketplace_code": "US",
                        "display_name": "Alpha US",
                        "status": "active",
                        "amazon_ads_profile_id": None,
                        "amazon_ads_account_id": None,
                        "created_at": "2026-03-18T10:00:00+00:00",
                    }
                ],
                "wbr_amazon_ads_connections": [],
                "report_api_connections": [],
            }
        )
        monkeypatch.setattr(
            amazon_ads_oauth,
            "exchange_authorization_code",
            AsyncMock(
                return_value={
                    "access_token": "Atza|test",
                    "refresh_token": "Atzr|shared-refresh",
                    "token_type": "bearer",
                    "expires_in": 3600,
                }
            ),
        )
        monkeypatch.setattr(amazon_ads_oauth, "_get_supabase", lambda: fake_db)

        with TestClient(app) as client:
            response = client.get(
                f"/amazon-ads/callback?code=auth-code-123&state={state}",
                follow_redirects=False,
            )

        assert response.status_code == 302
        assert fake_db.inserts["wbr_amazon_ads_connections"][0]["profile_id"] == "prof-1"
        shared_insert = fake_db.inserts["report_api_connections"][0]
        assert shared_insert["client_id"] == "client-1"
        assert shared_insert["provider"] == "amazon_ads"
        assert shared_insert["refresh_token"] == "Atzr|shared-refresh"
