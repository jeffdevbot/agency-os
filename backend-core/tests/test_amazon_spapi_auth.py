"""Tests for Amazon Seller API OAuth state signing, callback, and router endpoints."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import report_api_access
from app.services.reports.amazon_spapi_auth import (
    STATE_MAX_AGE_SECONDS,
    create_spapi_signed_state,
    verify_spapi_signed_state,
)
from app.services.wbr.profiles import WBRValidationError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    """Ensure required env vars are set for all tests."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-jwt-secret-at-least-32-chars-long")
    monkeypatch.setenv("AMAZON_SPAPI_LWA_CLIENT_ID", "test-spapi-client-id")
    monkeypatch.setenv("AMAZON_SPAPI_LWA_CLIENT_SECRET", "test-spapi-client-secret")
    monkeypatch.setenv("AMAZON_SPAPI_APP_ID", "amzn1.sp.solution.test-app-id")
    monkeypatch.setenv("FRONTEND_URL", "https://app.test")


def _override_admin():
    return {"sub": "user-123"}


# ---------------------------------------------------------------------------
# Stub Supabase
# ---------------------------------------------------------------------------


class _FakeTable:
    def __init__(self, rows: list[dict]):
        self._rows = rows
        self._filters_eq: dict = {}
        self._pending_op: str | None = None
        self._pending_data: dict | None = None
        self._parent: _FakeSupabase | None = None

    def select(self, *args, **kwargs):
        self._pending_op = "select"
        return self

    def eq(self, col, val):
        self._filters_eq[col] = val
        return self

    def neq(self, col, val):
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, n):
        return self

    def insert(self, data):
        self._pending_op = "insert"
        self._pending_data = data
        return self

    def update(self, data):
        self._pending_op = "update"
        self._pending_data = data
        return self

    def execute(self):
        if self._pending_op == "insert" and self._parent:
            self._parent.inserts.append(self._pending_data)
        elif self._pending_op == "update" and self._parent:
            self._parent.updates.append(self._pending_data)
        filtered = self._rows
        if self._pending_op == "select" and self._filters_eq:
            filtered = [
                row
                for row in filtered
                if all(row.get(col) == val for col, val in self._filters_eq.items())
            ]
        resp = MagicMock()
        resp.data = filtered
        return resp


class _FakeSupabase:
    def __init__(self, tables: dict[str, list[dict]] | None = None):
        self._tables = {name: list(rows) for name, rows in (tables or {}).items()}
        self.inserts: list[dict] = []
        self.updates: list[dict] = []

    def table(self, name: str):
        rows = self._tables.get(name, [])
        t = _FakeTable(rows)
        t._parent = self
        return t


# ---------------------------------------------------------------------------
# Unit tests: signed state
# ---------------------------------------------------------------------------


class TestSpApiSignedState:
    def test_create_and_verify_roundtrip(self):
        state = create_spapi_signed_state(
            client_id="client-1",
            initiated_by="user-1",
            return_path="/reports/api-access",
        )
        payload = verify_spapi_signed_state(state)
        assert payload["cid"] == "client-1"
        assert payload["uid"] == "user-1"
        assert payload["ret"] == "/reports/api-access"
        assert payload["prv"] == "amazon_spapi"
        assert "nonce" in payload
        assert "iat" in payload

    def test_tampered_signature_rejected(self):
        state = create_spapi_signed_state(
            client_id="client-1",
            initiated_by=None,
            return_path="/",
        )
        body, sig = state.rsplit(".", 1)
        tampered = body + "." + ("0" * len(sig))
        with pytest.raises(WBRValidationError, match="signature"):
            verify_spapi_signed_state(tampered)

    def test_expired_state_rejected(self):
        state = create_spapi_signed_state(
            client_id="client-1",
            initiated_by=None,
            return_path="/",
        )
        with patch("app.services.reports.amazon_spapi_auth.time") as mock_time:
            mock_time.time.return_value = time.time() + STATE_MAX_AGE_SECONDS + 60
            with pytest.raises(WBRValidationError, match="expired"):
                verify_spapi_signed_state(state)

    def test_invalid_format_rejected(self):
        with pytest.raises(WBRValidationError, match="format"):
            verify_spapi_signed_state("no-dot-separator")


# ---------------------------------------------------------------------------
# Unit tests: build_seller_auth_url
# ---------------------------------------------------------------------------


class TestBuildSellerAuthUrl:
    def test_url_contains_app_id_and_state(self):
        from app.services.reports.amazon_spapi_auth import build_seller_auth_url

        url = build_seller_auth_url(state="test-state-value")
        assert "sellercentral.amazon.com/apps/authorize/consent" in url
        assert "amzn1.sp.solution.test-app-id" in url
        assert "test-state-value" in url
        assert "version=beta" not in url

    def test_draft_app_includes_version_beta(self, monkeypatch):
        from app.services.reports.amazon_spapi_auth import build_seller_auth_url

        monkeypatch.setenv("AMAZON_SPAPI_DRAFT_APP", "true")
        url = build_seller_auth_url(state="test-state")
        assert "version=beta" in url


# ---------------------------------------------------------------------------
# Router tests: SP-API callback
# ---------------------------------------------------------------------------


class TestSpApiCallback:
    def test_successful_callback_stores_and_redirects(self, monkeypatch):
        state = create_spapi_signed_state(
            client_id="client-1",
            initiated_by="user-1",
            return_path="/reports/api-access",
        )

        fake_token_data = {"refresh_token": "sp-refresh-token-123", "access_token": "sp-access-123"}
        mock_exchange = AsyncMock(return_value=fake_token_data)
        monkeypatch.setattr(
            "app.routers.amazon_spapi_oauth.exchange_spapi_auth_code",
            mock_exchange,
        )

        fake_db = _FakeSupabase(
            tables={
                "report_api_connections": [],
            }
        )
        monkeypatch.setattr(
            "app.routers.amazon_spapi_oauth._get_supabase", lambda: fake_db
        )

        with TestClient(app, follow_redirects=False) as client:
            resp = client.get(
                "/amazon-spapi/callback",
                params={
                    "state": state,
                    "selling_partner_id": "SELLER123",
                    "spapi_oauth_code": "auth-code-456",
                },
            )
        assert resp.status_code == 302
        assert "/reports/api-access" in resp.headers["location"]
        mock_exchange.assert_awaited_once_with("auth-code-456")
        assert len(fake_db.inserts) == 1
        inserted = fake_db.inserts[0]
        assert inserted["client_id"] == "client-1"
        assert inserted["provider"] == "amazon_spapi"
        assert inserted["refresh_token"] == "sp-refresh-token-123"
        assert inserted["external_account_id"] == "SELLER123"
        assert inserted["region_code"] == "NA"

    def test_error_from_amazon_redirects_with_error(self, monkeypatch):
        state = create_spapi_signed_state(
            client_id="client-1",
            initiated_by=None,
            return_path="/reports/api-access",
        )
        monkeypatch.setenv("FRONTEND_URL", "https://app.test")
        with TestClient(app, follow_redirects=False) as client:
            resp = client.get(
                "/amazon-spapi/callback",
                params={
                    "state": state,
                    "error": "access_denied",
                    "error_description": "User denied",
                },
            )
        assert resp.status_code == 302
        assert "spapi_error=access_denied" in resp.headers["location"]

    def test_invalid_state_returns_400(self):
        with TestClient(app) as client:
            resp = client.get(
                "/amazon-spapi/callback",
                params={
                    "state": "bad-state",
                    "selling_partner_id": "SELLER",
                    "spapi_oauth_code": "code",
                },
            )
        assert resp.status_code == 400

    def test_missing_selling_partner_id_returns_400(self, monkeypatch):
        state = create_spapi_signed_state(
            client_id="client-1",
            initiated_by=None,
            return_path="/",
        )
        with TestClient(app) as client:
            resp = client.get(
                "/amazon-spapi/callback",
                params={
                    "state": state,
                    "selling_partner_id": "",
                    "spapi_oauth_code": "code",
                },
            )
        assert resp.status_code == 400

    def test_missing_oauth_code_returns_400(self, monkeypatch):
        state = create_spapi_signed_state(
            client_id="client-1",
            initiated_by=None,
            return_path="/",
        )
        with TestClient(app) as client:
            resp = client.get(
                "/amazon-spapi/callback",
                params={
                    "state": state,
                    "selling_partner_id": "SELLER",
                    "spapi_oauth_code": "",
                },
            )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Router tests: SP-API connect endpoint
# ---------------------------------------------------------------------------


class TestSpApiConnectEndpoint:
    def test_returns_authorization_url(self, monkeypatch):
        app.dependency_overrides[report_api_access.require_admin_user] = _override_admin
        try:
            with TestClient(app) as client:
                resp = client.post(
                    "/admin/reports/api-access/amazon-spapi/connect",
                    json={"client_id": "client-1"},
                )
            assert resp.status_code == 200
            body = resp.json()
            assert body["ok"] is True
            assert "sellercentral.amazon.com" in body["authorization_url"]
            assert "amzn1.sp.solution.test-app-id" in body["authorization_url"]
        finally:
            app.dependency_overrides.pop(report_api_access.require_admin_user, None)


# ---------------------------------------------------------------------------
# Router tests: SP-API connections list endpoint
# ---------------------------------------------------------------------------


class TestSpApiConnectionsListEndpoint:
    def test_returns_connections(self, monkeypatch):
        fake_db = _FakeSupabase(
            tables={
                "agency_clients": [
                    {"id": "client-1", "name": "Test Client", "status": "active"},
                ],
                "report_api_connections": [
                    {
                        "id": "conn-1",
                        "client_id": "client-1",
                        "provider": "amazon_spapi",
                        "connection_status": "connected",
                        "external_account_id": "SELLER123",
                        "region_code": "NA",
                        "access_meta": {},
                        "connected_at": "2026-03-18T12:00:00Z",
                        "last_validated_at": None,
                        "last_error": None,
                        "updated_at": "2026-03-18T12:00:00Z",
                    },
                ],
            }
        )
        monkeypatch.setattr(report_api_access, "_get_supabase", lambda: fake_db)
        app.dependency_overrides[report_api_access.require_admin_user] = _override_admin
        try:
            with TestClient(app) as client:
                resp = client.get(
                    "/admin/reports/api-access/amazon-spapi/connections",
                )
            assert resp.status_code == 200
            body = resp.json()
            assert body["ok"] is True
            connections = body["connections"]
            assert len(connections) == 1
            assert connections[0]["client_id"] == "client-1"
            assert connections[0]["connected"] is True
            assert connections[0]["connection"]["external_account_id"] == "SELLER123"
        finally:
            app.dependency_overrides.pop(report_api_access.require_admin_user, None)


# ---------------------------------------------------------------------------
# Router tests: SP-API validate endpoint
# ---------------------------------------------------------------------------


class TestSpApiValidateEndpoint:
    def test_successful_validation(self, monkeypatch):
        fake_db = _FakeSupabase(
            tables={
                "report_api_connections": [
                    {
                        "id": "conn-1",
                        "client_id": "client-1",
                        "provider": "amazon_spapi",
                        "connection_status": "connected",
                        "refresh_token": "stored-refresh-token",
                        "external_account_id": "SELLER123",
                        "region_code": "NA",
                        "access_meta": {},
                        "connected_at": "2026-03-18T12:00:00Z",
                        "last_validated_at": None,
                        "last_error": None,
                        "updated_at": "2026-03-18T12:00:00Z",
                    },
                ],
            }
        )
        monkeypatch.setattr(report_api_access, "_get_supabase", lambda: fake_db)

        mock_refresh = AsyncMock(return_value="fresh-access-token")
        monkeypatch.setattr(
            report_api_access, "refresh_spapi_access_token", mock_refresh
        )

        mock_participations = AsyncMock(
            return_value=[
                {
                    "marketplace": {"id": "ATVPDKIKX0DER", "name": "Amazon.com"},
                    "participation": {"isParticipating": True},
                },
                {
                    "marketplace": {"id": "A2EUQ1WTGCTBG2", "name": "Amazon.ca"},
                    "participation": {"isParticipating": True},
                },
            ]
        )
        monkeypatch.setattr(
            report_api_access, "get_marketplace_participations", mock_participations
        )

        app.dependency_overrides[report_api_access.require_admin_user] = _override_admin
        try:
            with TestClient(app) as client:
                resp = client.post(
                    "/admin/reports/api-access/amazon-spapi/validate",
                    json={"client_id": "client-1"},
                )
            assert resp.status_code == 200
            body = resp.json()
            assert body["ok"] is True
            assert body["marketplace_count"] == 2
            assert "ATVPDKIKX0DER" in body["marketplace_ids"]
            assert "A2EUQ1WTGCTBG2" in body["marketplace_ids"]
            mock_refresh.assert_awaited_once_with("stored-refresh-token")
            mock_participations.assert_awaited_once_with("fresh-access-token")
            # Should have called update on the connection
            assert len(fake_db.updates) == 1
        finally:
            app.dependency_overrides.pop(report_api_access.require_admin_user, None)

    def test_no_connection_returns_404(self, monkeypatch):
        fake_db = _FakeSupabase(
            tables={
                "report_api_connections": [],
            }
        )
        monkeypatch.setattr(report_api_access, "_get_supabase", lambda: fake_db)
        app.dependency_overrides[report_api_access.require_admin_user] = _override_admin
        try:
            with TestClient(app) as client:
                resp = client.post(
                    "/admin/reports/api-access/amazon-spapi/validate",
                    json={"client_id": "client-1"},
                )
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(report_api_access.require_admin_user, None)

    def test_token_refresh_failure_returns_error(self, monkeypatch):
        fake_db = _FakeSupabase(
            tables={
                "report_api_connections": [
                    {
                        "id": "conn-1",
                        "client_id": "client-1",
                        "provider": "amazon_spapi",
                        "connection_status": "connected",
                        "refresh_token": "bad-token",
                        "external_account_id": "SELLER123",
                        "region_code": "NA",
                        "access_meta": {},
                        "connected_at": "2026-03-18T12:00:00Z",
                        "last_validated_at": None,
                        "last_error": None,
                        "updated_at": "2026-03-18T12:00:00Z",
                    },
                ],
            }
        )
        monkeypatch.setattr(report_api_access, "_get_supabase", lambda: fake_db)

        mock_refresh = AsyncMock(side_effect=WBRValidationError("token refresh failed"))
        monkeypatch.setattr(
            report_api_access, "refresh_spapi_access_token", mock_refresh
        )

        app.dependency_overrides[report_api_access.require_admin_user] = _override_admin
        try:
            with TestClient(app) as client:
                resp = client.post(
                    "/admin/reports/api-access/amazon-spapi/validate",
                    json={"client_id": "client-1"},
                )
            assert resp.status_code == 200
            body = resp.json()
            assert body["ok"] is False
            assert body["step"] == "token_refresh"
            # Should have updated connection status to error
            assert len(fake_db.updates) == 1
        finally:
            app.dependency_overrides.pop(report_api_access.require_admin_user, None)


# ---------------------------------------------------------------------------
# Router tests: SP-API finance smoke test endpoint
# ---------------------------------------------------------------------------

_SPAPI_CONNECTION_ROW = {
    "id": "conn-1",
    "client_id": "client-1",
    "provider": "amazon_spapi",
    "connection_status": "connected",
    "refresh_token": "stored-refresh-token",
    "external_account_id": "SELLER123",
    "region_code": "NA",
    "access_meta": {},
    "connected_at": "2026-03-18T12:00:00Z",
    "last_validated_at": None,
    "last_error": None,
    "updated_at": "2026-03-18T12:00:00Z",
}


class TestSpApiFinanceSmokeTest:
    def test_successful_full_flow(self, monkeypatch):
        fake_db = _FakeSupabase(
            tables={"report_api_connections": [_SPAPI_CONNECTION_ROW]}
        )
        monkeypatch.setattr(report_api_access, "_get_supabase", lambda: fake_db)

        mock_refresh = AsyncMock(return_value="fresh-access-token")
        monkeypatch.setattr(
            report_api_access, "refresh_spapi_access_token", mock_refresh
        )

        mock_groups = AsyncMock(
            return_value=[
                {
                    "FinancialEventGroupId": "FEG-123",
                    "ProcessingStatus": "Closed",
                    "FundTransferStatus": "Successful",
                    "OriginalTotal": {"CurrencyCode": "USD", "CurrencyAmount": 1234.56},
                    "ConvertedTotal": {"CurrencyCode": "USD", "CurrencyAmount": 1234.56},
                    "FundTransferDate": "2026-03-15T00:00:00Z",
                    "TraceId": "TRACE-ABC",
                    "AccountTail": "1234",
                    "BeginningBalance": {"CurrencyCode": "USD", "CurrencyAmount": 0},
                    "FinancialEventGroupStart": "2026-03-01T00:00:00Z",
                    "FinancialEventGroupEnd": "2026-03-15T00:00:00Z",
                },
            ]
        )
        monkeypatch.setattr(
            report_api_access, "list_financial_event_groups", mock_groups
        )

        mock_txns = AsyncMock(
            return_value=[
                {
                    "transactionId": "TXN-1",
                    "transactionType": "Shipment",
                    "transactionStatus": "RELEASED",
                    "totalAmount": {"currencyCode": "USD", "currencyAmount": 50.00},
                    "description": "Order payment",
                    "relatedIdentifiers": [
                        {
                            "relatedIdentifierName": "ORDER_ID",
                            "relatedIdentifierValue": "111-222-333",
                        }
                    ],
                    "postingDate": "2026-03-10T00:00:00Z",
                    "marketplaceDetails": {
                        "marketplaceId": "ATVPDKIKX0DER",
                        "marketplaceName": "Amazon.com",
                    },
                },
            ]
        )
        monkeypatch.setattr(
            report_api_access, "list_transactions", mock_txns
        )

        app.dependency_overrides[report_api_access.require_admin_user] = _override_admin
        try:
            with TestClient(app) as client:
                resp = client.post(
                    "/admin/reports/api-access/amazon-spapi/finance-smoke-test",
                    json={"client_id": "client-1"},
                )
            assert resp.status_code == 200
            body = resp.json()
            assert body["ok"] is True
            assert body["target_group_id"] == "FEG-123"
            assert body["group_count"] == 1
            assert body["transaction_count"] == 1
            assert body["groups"][0]["FinancialEventGroupId"] == "FEG-123"
            assert body["transactions"][0]["transactionId"] == "TXN-1"
            mock_refresh.assert_awaited_once_with("stored-refresh-token")
            mock_groups.assert_awaited_once()
            mock_txns.assert_awaited_once()
            # Verify the listTransactions call used the right group ID
            call_kwargs = mock_txns.await_args
            assert call_kwargs[1]["financial_event_group_id"] == "FEG-123"
        finally:
            app.dependency_overrides.pop(report_api_access.require_admin_user, None)

    def test_no_connection_returns_404(self, monkeypatch):
        fake_db = _FakeSupabase(tables={"report_api_connections": []})
        monkeypatch.setattr(report_api_access, "_get_supabase", lambda: fake_db)
        app.dependency_overrides[report_api_access.require_admin_user] = _override_admin
        try:
            with TestClient(app) as client:
                resp = client.post(
                    "/admin/reports/api-access/amazon-spapi/finance-smoke-test",
                    json={"client_id": "client-1"},
                )
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(report_api_access.require_admin_user, None)

    def test_token_refresh_failure(self, monkeypatch):
        fake_db = _FakeSupabase(
            tables={"report_api_connections": [_SPAPI_CONNECTION_ROW]}
        )
        monkeypatch.setattr(report_api_access, "_get_supabase", lambda: fake_db)
        mock_refresh = AsyncMock(
            side_effect=WBRValidationError("SP-API token refresh failed (401)")
        )
        monkeypatch.setattr(
            report_api_access, "refresh_spapi_access_token", mock_refresh
        )
        app.dependency_overrides[report_api_access.require_admin_user] = _override_admin
        try:
            with TestClient(app) as client:
                resp = client.post(
                    "/admin/reports/api-access/amazon-spapi/finance-smoke-test",
                    json={"client_id": "client-1"},
                )
            assert resp.status_code == 200
            body = resp.json()
            assert body["ok"] is False
            assert body["step"] == "token_refresh"
        finally:
            app.dependency_overrides.pop(report_api_access.require_admin_user, None)

    def test_groups_api_failure(self, monkeypatch):
        fake_db = _FakeSupabase(
            tables={"report_api_connections": [_SPAPI_CONNECTION_ROW]}
        )
        monkeypatch.setattr(report_api_access, "_get_supabase", lambda: fake_db)
        monkeypatch.setattr(
            report_api_access,
            "refresh_spapi_access_token",
            AsyncMock(return_value="token"),
        )
        monkeypatch.setattr(
            report_api_access,
            "list_financial_event_groups",
            AsyncMock(side_effect=WBRValidationError("listFinancialEventGroups failed (403)")),
        )
        app.dependency_overrides[report_api_access.require_admin_user] = _override_admin
        try:
            with TestClient(app) as client:
                resp = client.post(
                    "/admin/reports/api-access/amazon-spapi/finance-smoke-test",
                    json={"client_id": "client-1"},
                )
            assert resp.status_code == 200
            body = resp.json()
            assert body["ok"] is False
            assert body["step"] == "list_financial_event_groups"
        finally:
            app.dependency_overrides.pop(report_api_access.require_admin_user, None)

    def test_empty_groups_returns_ok_with_note(self, monkeypatch):
        fake_db = _FakeSupabase(
            tables={"report_api_connections": [_SPAPI_CONNECTION_ROW]}
        )
        monkeypatch.setattr(report_api_access, "_get_supabase", lambda: fake_db)
        monkeypatch.setattr(
            report_api_access,
            "refresh_spapi_access_token",
            AsyncMock(return_value="token"),
        )
        monkeypatch.setattr(
            report_api_access,
            "list_financial_event_groups",
            AsyncMock(return_value=[]),
        )
        app.dependency_overrides[report_api_access.require_admin_user] = _override_admin
        try:
            with TestClient(app) as client:
                resp = client.post(
                    "/admin/reports/api-access/amazon-spapi/finance-smoke-test",
                    json={"client_id": "client-1"},
                )
            assert resp.status_code == 200
            body = resp.json()
            assert body["ok"] is True
            assert "No financial event groups" in body["note"]
        finally:
            app.dependency_overrides.pop(report_api_access.require_admin_user, None)

    def test_transactions_api_failure(self, monkeypatch):
        fake_db = _FakeSupabase(
            tables={"report_api_connections": [_SPAPI_CONNECTION_ROW]}
        )
        monkeypatch.setattr(report_api_access, "_get_supabase", lambda: fake_db)
        monkeypatch.setattr(
            report_api_access,
            "refresh_spapi_access_token",
            AsyncMock(return_value="token"),
        )
        monkeypatch.setattr(
            report_api_access,
            "list_financial_event_groups",
            AsyncMock(
                return_value=[{"FinancialEventGroupId": "FEG-1", "ProcessingStatus": "Closed"}]
            ),
        )
        monkeypatch.setattr(
            report_api_access,
            "list_transactions",
            AsyncMock(side_effect=WBRValidationError("listTransactions failed (429)")),
        )
        app.dependency_overrides[report_api_access.require_admin_user] = _override_admin
        try:
            with TestClient(app) as client:
                resp = client.post(
                    "/admin/reports/api-access/amazon-spapi/finance-smoke-test",
                    json={"client_id": "client-1"},
                )
            assert resp.status_code == 200
            body = resp.json()
            assert body["ok"] is False
            assert body["step"] == "list_transactions"
            assert body["target_group_id"] == "FEG-1"
            # Groups should still be in the response
            assert len(body["groups"]) == 1
        finally:
            app.dependency_overrides.pop(report_api_access.require_admin_user, None)
