"""Tests for the Monthly P&L admin router endpoints."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.routers import pnl


def _override_admin():
    return {"sub": "user-123"}


SAMPLE_CSV = (
    '"date/time","type","order id","sku","description","product sales","total",'
    '"Transaction Release Date"\n'
    '"Jan 15, 2026","Order","111","SKU1","Widget","10.00","10.00","Jan 20, 2026"\n'
).encode("utf-8")


class TestProfileEndpoints:
    def test_list_profiles(self, monkeypatch):
        fake_svc = MagicMock()
        fake_svc.list_profiles.return_value = [{"id": "p1", "marketplace_code": "US"}]
        monkeypatch.setattr(pnl, "_get_profile_service", lambda: fake_svc)
        app.dependency_overrides[pnl.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.get("/admin/pnl/profiles", params={"client_id": "c1"})
        finally:
            app.dependency_overrides.pop(pnl.require_admin_user, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert len(data["profiles"]) == 1

    def test_create_profile(self, monkeypatch):
        fake_svc = MagicMock()
        fake_svc.create_profile.return_value = {"id": "p1", "marketplace_code": "US"}
        monkeypatch.setattr(pnl, "_get_profile_service", lambda: fake_svc)
        app.dependency_overrides[pnl.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.post("/admin/pnl/profiles", json={
                    "client_id": "c1",
                    "marketplace_code": "US",
                })
        finally:
            app.dependency_overrides.pop(pnl.require_admin_user, None)

        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_get_profile_not_found(self, monkeypatch):
        from app.services.pnl.profiles import PNLNotFoundError

        fake_svc = MagicMock()
        fake_svc.get_profile.side_effect = PNLNotFoundError("not found")
        monkeypatch.setattr(pnl, "_get_profile_service", lambda: fake_svc)
        app.dependency_overrides[pnl.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.get("/admin/pnl/profiles/nonexistent")
        finally:
            app.dependency_overrides.pop(pnl.require_admin_user, None)

        assert resp.status_code == 404

    def test_create_duplicate_profile_returns_400(self, monkeypatch):
        """Fix #4: duplicate (client_id, marketplace) should return 400, not 500."""
        from app.services.pnl.profiles import PNLValidationError

        fake_svc = MagicMock()
        fake_svc.create_profile.side_effect = PNLValidationError(
            "A P&L profile already exists for this client and marketplace"
        )
        monkeypatch.setattr(pnl, "_get_profile_service", lambda: fake_svc)
        app.dependency_overrides[pnl.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.post("/admin/pnl/profiles", json={
                    "client_id": "c1",
                    "marketplace_code": "US",
                })
        finally:
            app.dependency_overrides.pop(pnl.require_admin_user, None)

        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"].lower()

    def test_list_cogs_months(self, monkeypatch):
        fake_svc = MagicMock()
        fake_svc.list_cogs_month_totals.return_value = [
            {"entry_month": "2026-01-01", "amount": "1200.00", "has_data": True}
        ]
        monkeypatch.setattr(pnl, "_get_profile_service", lambda: fake_svc)
        app.dependency_overrides[pnl.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.get("/admin/pnl/profiles/p1/cogs-monthly")
        finally:
            app.dependency_overrides.pop(pnl.require_admin_user, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["months"] == [
            {"entry_month": "2026-01-01", "amount": "1200.00", "has_data": True}
        ]

    def test_save_cogs_months(self, monkeypatch):
        fake_svc = MagicMock()
        fake_svc.save_cogs_month_totals.return_value = [
            {"entry_month": "2026-01-01", "amount": "1200.00", "has_data": True}
        ]
        monkeypatch.setattr(pnl, "_get_profile_service", lambda: fake_svc)
        app.dependency_overrides[pnl.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.put(
                    "/admin/pnl/profiles/p1/cogs-monthly",
                    json={"entries": [{"entry_month": "2026-01-01", "amount": "1200.00"}]},
                )
        finally:
            app.dependency_overrides.pop(pnl.require_admin_user, None)

        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        fake_svc.save_cogs_month_totals.assert_called_once_with(
            "p1",
            [{"entry_month": "2026-01-01", "amount": "1200.00"}],
        )

    def test_save_cogs_months_validation_error_returns_400(self, monkeypatch):
        from app.services.pnl.profiles import PNLValidationError

        fake_svc = MagicMock()
        fake_svc.save_cogs_month_totals.side_effect = PNLValidationError("invalid cogs")
        monkeypatch.setattr(pnl, "_get_profile_service", lambda: fake_svc)
        app.dependency_overrides[pnl.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.put(
                    "/admin/pnl/profiles/p1/cogs-monthly",
                    json={"entries": [{"entry_month": "2026-01-01", "amount": "oops"}]},
                )
        finally:
            app.dependency_overrides.pop(pnl.require_admin_user, None)

        assert resp.status_code == 400
        assert "invalid cogs" in resp.json()["detail"]


class TestTransactionUpload:
    def test_rejects_non_csv_file(self, monkeypatch):
        app.dependency_overrides[pnl.require_admin_user] = _override_admin
        try:
            with TestClient(app) as client:
                resp = client.post(
                    "/admin/pnl/profiles/p1/transaction-upload",
                    files={"file": ("report.xlsx", b"data", "application/octet-stream")},
                )
        finally:
            app.dependency_overrides.pop(pnl.require_admin_user, None)

        assert resp.status_code == 400
        assert "csv" in resp.json()["detail"].lower()

    def test_rejects_empty_file(self, monkeypatch):
        app.dependency_overrides[pnl.require_admin_user] = _override_admin
        try:
            with TestClient(app) as client:
                resp = client.post(
                    "/admin/pnl/profiles/p1/transaction-upload",
                    files={"file": ("report.csv", b"", "text/csv")},
                )
        finally:
            app.dependency_overrides.pop(pnl.require_admin_user, None)

        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()

    def test_successful_upload(self, monkeypatch):
        fake_svc = MagicMock()
        fake_svc.enqueue_file.return_value = {
            "import": {"id": "imp-1"},
            "months": [{"entry_month": "2026-01-01", "raw_row_count": 1}],
            "summary": {
                "total_raw_rows": 1,
                "total_months": 1,
                "period_start": "2026-01-01",
                "period_end": "2026-01-01",
                "import_scope": "single_month",
            },
        }
        monkeypatch.setattr(pnl, "_get_import_service", lambda: fake_svc)
        app.dependency_overrides[pnl.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.post(
                    "/admin/pnl/profiles/p1/transaction-upload",
                    files={"file": ("report.csv", SAMPLE_CSV, "text/csv")},
                )
        finally:
            app.dependency_overrides.pop(pnl.require_admin_user, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["summary"]["total_raw_rows"] == 1

    def test_duplicate_file_returns_409(self, monkeypatch):
        from app.services.pnl.profiles import PNLDuplicateFileError

        fake_svc = MagicMock()
        fake_svc.enqueue_file.side_effect = PNLDuplicateFileError("already imported")
        monkeypatch.setattr(pnl, "_get_import_service", lambda: fake_svc)
        app.dependency_overrides[pnl.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.post(
                    "/admin/pnl/profiles/p1/transaction-upload",
                    files={"file": ("report.csv", SAMPLE_CSV, "text/csv")},
                )
        finally:
            app.dependency_overrides.pop(pnl.require_admin_user, None)

        assert resp.status_code == 409

    def test_profile_not_found_returns_404(self, monkeypatch):
        from app.services.pnl.profiles import PNLNotFoundError

        fake_svc = MagicMock()
        fake_svc.enqueue_file.side_effect = PNLNotFoundError("not found")
        monkeypatch.setattr(pnl, "_get_import_service", lambda: fake_svc)
        app.dependency_overrides[pnl.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.post(
                    "/admin/pnl/profiles/p1/transaction-upload",
                    files={"file": ("report.csv", SAMPLE_CSV, "text/csv")},
                )
        finally:
            app.dependency_overrides.pop(pnl.require_admin_user, None)

        assert resp.status_code == 404
