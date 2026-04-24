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

    def test_list_amazon_ads_connections_marks_shared_error_as_not_connected(self, monkeypatch):
        fake_db = _FakeSupabase(
            {
                "agency_clients": [
                    {"id": "client-1", "name": "Alpha", "status": "active"},
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
                    }
                ],
                "report_api_connections": [
                    {
                        "id": "shared-1",
                        "client_id": "client-1",
                        "provider": "amazon_ads",
                        "connection_status": "error",
                        "external_account_id": None,
                        "region_code": None,
                        "access_meta": {"lwa_account_hint": "alpha@example.com"},
                        "connected_at": "2026-03-18T12:00:00+00:00",
                        "last_validated_at": None,
                        "last_error": "token refresh failed",
                        "updated_at": "2026-03-18T12:00:00+00:00",
                        "created_at": "2026-03-18T12:00:00+00:00",
                    }
                ],
                "wbr_amazon_ads_connections": [
                    {
                        "profile_id": "prof-1",
                        "connected_at": "2026-03-18T09:00:00+00:00",
                        "updated_at": "2026-03-18T09:00:00+00:00",
                        "lwa_account_hint": "legacy@example.com",
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
            row = body["connections"][0]
            assert row["source"] == "shared"
            assert row["connected"] is False
            assert row["shared_connection"]["connection_status"] == "error"
            assert row["legacy_connection"]["connection_status"] == "connected"
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
            assert body["region_code"] == "NA"
            assert body["profile"]["client_id"] == "client-1"
        finally:
            app.dependency_overrides.pop(report_api_access.require_admin_user, None)

    def test_connect_endpoint_accepts_ads_region(self, monkeypatch):
        fake_db = _FakeSupabase(
            {
                "wbr_profiles": [
                    {
                        "id": "prof-1",
                        "client_id": "client-1",
                        "marketplace_code": "UK",
                        "display_name": "Alpha UK",
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
                    json={
                        "profile_id": "prof-1",
                        "region": "EU",
                        "return_path": "/reports/api-access",
                    },
                )
            assert response.status_code == 200
            body = response.json()
            assert body["region_code"] == "EU"
        finally:
            app.dependency_overrides.pop(report_api_access.require_admin_user, None)

    def test_amazon_ads_validate_success_updates_region_connection(self, monkeypatch):
        fake_db = _FakeSupabase(
            {
                "report_api_connections": [
                    {
                        "id": "conn-1",
                        "client_id": "client-1",
                        "provider": "amazon_ads",
                        "connection_status": "connected",
                        "region_code": "EU",
                        "refresh_token": "refresh-token",
                        "access_meta": {},
                    }
                ]
            }
        )
        seen_regions: list[str] = []
        monkeypatch.setattr(report_api_access, "_get_supabase", lambda: fake_db)
        monkeypatch.setattr(
            report_api_access,
            "refresh_ads_access_token",
            AsyncMock(return_value="access-token"),
        )

        async def fake_list_profiles(access_token: str, *, region_code: str):
            assert access_token == "access-token"
            seen_regions.append(region_code)
            return [{"profileId": "ads-prof-1"}, {"profileId": "ads-prof-2"}]

        monkeypatch.setattr(report_api_access, "list_advertising_profiles", fake_list_profiles)
        app.dependency_overrides[report_api_access.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/admin/reports/api-access/amazon-ads/validate",
                    json={"client_id": "client-1", "region": "EU"},
                )
            assert response.status_code == 200
            body = response.json()
            assert body["ok"] is True
            assert body["status"] == "connected"
            assert body["region_code"] == "EU"
            assert body["profile_count"] == 2
            assert seen_regions == ["EU"]

            row = fake_db.tables["report_api_connections"][0]
            assert row["connection_status"] == "connected"
            assert row["last_error"] is None
            assert row["last_validated_at"]
        finally:
            app.dependency_overrides.pop(report_api_access.require_admin_user, None)

    def test_amazon_ads_validate_error_marks_connection_error(self, monkeypatch):
        fake_db = _FakeSupabase(
            {
                "report_api_connections": [
                    {
                        "id": "conn-1",
                        "client_id": "client-1",
                        "provider": "amazon_ads",
                        "connection_status": "connected",
                        "region_code": "NA",
                        "refresh_token": "refresh-token",
                    }
                ]
            }
        )
        monkeypatch.setattr(report_api_access, "_get_supabase", lambda: fake_db)
        monkeypatch.setattr(
            report_api_access,
            "refresh_ads_access_token",
            AsyncMock(side_effect=report_api_access.WBRValidationError("401 unauthorized")),
        )
        app.dependency_overrides[report_api_access.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/admin/reports/api-access/amazon-ads/validate",
                    json={"client_id": "client-1", "region": "NA"},
                )
            assert response.status_code == 200
            body = response.json()
            assert body["ok"] is False
            assert body["status"] == "error"
            assert body["step"] == "token_refresh"
            assert "401 unauthorized" in body["error"]
            row = fake_db.tables["report_api_connections"][0]
            assert row["connection_status"] == "error"
            assert "Token refresh failed" in row["last_error"]
        finally:
            app.dependency_overrides.pop(report_api_access.require_admin_user, None)

    def test_amazon_ads_validate_revoked_returns_clean_error(self, monkeypatch):
        fake_db = _FakeSupabase(
            {
                "report_api_connections": [
                    {
                        "id": "conn-1",
                        "client_id": "client-1",
                        "provider": "amazon_ads",
                        "connection_status": "revoked",
                        "region_code": "NA",
                        "refresh_token": None,
                    }
                ]
            }
        )
        monkeypatch.setattr(report_api_access, "_get_supabase", lambda: fake_db)
        app.dependency_overrides[report_api_access.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/admin/reports/api-access/amazon-ads/validate",
                    json={"client_id": "client-1", "region": "NA"},
                )
            assert response.status_code == 400
            assert "revoked" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(report_api_access.require_admin_user, None)

    def test_amazon_ads_disconnect_soft_revokes_and_is_idempotent(self, monkeypatch):
        fake_db = _FakeSupabase(
            {
                "report_api_connections": [
                    {
                        "id": "conn-1",
                        "client_id": "client-1",
                        "provider": "amazon_ads",
                        "connection_status": "connected",
                        "region_code": "NA",
                        "refresh_token": "refresh-token",
                    }
                ]
            }
        )
        monkeypatch.setattr(report_api_access, "_get_supabase", lambda: fake_db)
        app.dependency_overrides[report_api_access.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                first = client.post(
                    "/admin/reports/api-access/amazon-ads/disconnect",
                    json={"client_id": "client-1", "region": "NA"},
                )
                second = client.post(
                    "/admin/reports/api-access/amazon-ads/disconnect",
                    json={"client_id": "client-1", "region": "NA"},
                )
            assert first.status_code == 200
            assert first.json() == {"status": "revoked", "affected": 1}
            assert second.status_code == 200
            assert second.json() == {"status": "revoked", "affected": 0}
            row = fake_db.tables["report_api_connections"][0]
            assert row["connection_status"] == "revoked"
            assert row["refresh_token"] is None
        finally:
            app.dependency_overrides.pop(report_api_access.require_admin_user, None)

    def test_disconnect_nonexistent_tuple_is_graceful(self, monkeypatch):
        fake_db = _FakeSupabase({"report_api_connections": []})
        monkeypatch.setattr(report_api_access, "_get_supabase", lambda: fake_db)
        app.dependency_overrides[report_api_access.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/admin/reports/api-access/amazon-ads/disconnect",
                    json={"client_id": "client-1", "region": "FE"},
                )
            assert response.status_code == 200
            assert response.json() == {"status": "revoked", "affected": 0}
        finally:
            app.dependency_overrides.pop(report_api_access.require_admin_user, None)

    def test_spapi_disconnect_soft_revokes_and_is_idempotent(self, monkeypatch):
        fake_db = _FakeSupabase(
            {
                "report_api_connections": [
                    {
                        "id": "conn-1",
                        "client_id": "client-1",
                        "provider": "amazon_spapi",
                        "connection_status": "connected",
                        "region_code": "NA",
                        "refresh_token": "refresh-token",
                    }
                ]
            }
        )
        monkeypatch.setattr(report_api_access, "_get_supabase", lambda: fake_db)
        app.dependency_overrides[report_api_access.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                first = client.post(
                    "/admin/reports/api-access/amazon-spapi/disconnect",
                    json={"client_id": "client-1", "region": "NA"},
                )
                second = client.post(
                    "/admin/reports/api-access/amazon-spapi/disconnect",
                    json={"client_id": "client-1", "region": "NA"},
                )
            assert first.status_code == 200
            assert first.json() == {"status": "revoked", "affected": 1}
            assert second.status_code == 200
            assert second.json() == {"status": "revoked", "affected": 0}
            row = fake_db.tables["report_api_connections"][0]
            assert row["connection_status"] == "revoked"
            assert row["refresh_token"] is None
        finally:
            app.dependency_overrides.pop(report_api_access.require_admin_user, None)

    def test_spapi_preview_listings_endpoint_returns_service_preview(self, monkeypatch):
        fake_db = _FakeSupabase({})

        class FakeListingsService:
            def __init__(self, db):
                assert db is fake_db

            async def fetch_listings(self, *, profile_id: str):
                assert profile_id == "prof-1"
                return {
                    "profile_id": profile_id,
                    "marketplace_code": "CA",
                    "marketplace_id": "A2EUQ1WTGCTBG2",
                    "rows_fetched": 2,
                    "rows_parsed": 2,
                    "duplicate_rows_merged": 0,
                    "unmapped_columns": ["listing-id", "open-date"],
                    "sample_records": [{"child_asin": "B000TEST01"}],
                }

        monkeypatch.setattr(report_api_access, "_get_supabase", lambda: fake_db)
        monkeypatch.setattr(report_api_access, "SpApiListingsFetchService", FakeListingsService)
        app.dependency_overrides[report_api_access.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/admin/reports/api-access/amazon-spapi/preview-listings",
                    json={"profile_id": "prof-1"},
                )
            assert response.status_code == 200
            body = response.json()
            assert body["ok"] is True
            assert body["rows_fetched"] == 2
            assert body["sample_records"][0]["child_asin"] == "B000TEST01"
        finally:
            app.dependency_overrides.pop(report_api_access.require_admin_user, None)

    def test_spapi_import_listings_endpoint_returns_import_result(self, monkeypatch):
        fake_db = _FakeSupabase({})

        class FakeListingImportService:
            def __init__(self, db):
                assert db is fake_db

            async def import_from_spapi(self, *, profile_id: str, user_id: str | None):
                assert profile_id == "prof-1"
                assert user_id == "user-123"
                return {
                    "batch": {
                        "id": "batch-1",
                        "profile_id": profile_id,
                        "source_provider": "amazon_spapi",
                        "import_status": "success",
                    },
                    "summary": {
                        "source_type": "amazon_spapi",
                        "source_provider": "amazon_spapi",
                        "rows_read": 2,
                        "rows_loaded": 2,
                        "duplicate_rows_merged": 0,
                    },
                }

        monkeypatch.setattr(report_api_access, "_get_supabase", lambda: fake_db)
        monkeypatch.setattr(report_api_access, "ListingImportService", FakeListingImportService)
        app.dependency_overrides[report_api_access.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/admin/reports/api-access/amazon-spapi/import-listings",
                    json={"profile_id": "prof-1"},
                )
            assert response.status_code == 200
            body = response.json()
            assert body["ok"] is True
            assert body["batch"]["source_provider"] == "amazon_spapi"
            assert body["summary"]["rows_loaded"] == 2
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
        assert shared_insert["region_code"] == "NA"

    def test_callback_dual_writes_shared_connection_with_region_from_state(self, monkeypatch):
        state = create_signed_state(
            profile_id="prof-1",
            initiated_by="user-1",
            return_path="/reports/api-access",
            region_code="EU",
        )
        fake_db = _FakeSupabase(
            {
                "wbr_profiles": [
                    {
                        "id": "prof-1",
                        "client_id": "client-1",
                        "marketplace_code": "UK",
                        "display_name": "Alpha UK",
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
        shared_insert = fake_db.inserts["report_api_connections"][0]
        assert shared_insert["region_code"] == "EU"

    def test_callback_reconnect_updates_revoked_regional_connection(self, monkeypatch):
        state = create_signed_state(
            profile_id="prof-1",
            initiated_by="user-1",
            return_path="/reports/api-access",
            region_code="NA",
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
                "report_api_connections": [
                    {
                        "id": "shared-1",
                        "client_id": "client-1",
                        "provider": "amazon_ads",
                        "connection_status": "revoked",
                        "region_code": "NA",
                        "refresh_token": None,
                    }
                ],
            }
        )
        monkeypatch.setattr(
            amazon_ads_oauth,
            "exchange_authorization_code",
            AsyncMock(
                return_value={
                    "access_token": "Atza|test",
                    "refresh_token": "Atzr|new-refresh",
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
        shared_row = fake_db.tables["report_api_connections"][0]
        assert shared_row["connection_status"] == "connected"
        assert shared_row["refresh_token"] == "Atzr|new-refresh"
