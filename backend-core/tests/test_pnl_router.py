"""Tests for the Monthly P&L admin router endpoints."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

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

    def test_list_cogs_skus(self, monkeypatch):
        fake_svc = MagicMock()
        fake_svc.list_sku_cogs.return_value = [
            {
                "sku": "SKU1",
                "unit_cost": "1.8600",
                "months": {"2026-01-01": 4},
                "total_units": 4,
                "missing_cost": False,
            }
        ]
        monkeypatch.setattr(pnl, "_get_profile_service", lambda: fake_svc)
        app.dependency_overrides[pnl.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.get("/admin/pnl/profiles/p1/cogs-skus")
        finally:
            app.dependency_overrides.pop(pnl.require_admin_user, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["skus"] == [
            {
                "sku": "SKU1",
                "unit_cost": "1.8600",
                "months": {"2026-01-01": 4},
                "total_units": 4,
                "missing_cost": False,
            }
        ]
        fake_svc.list_sku_cogs.assert_called_once_with("p1")

    def test_save_cogs_skus(self, monkeypatch):
        fake_svc = MagicMock()
        monkeypatch.setattr(pnl, "_get_profile_service", lambda: fake_svc)
        app.dependency_overrides[pnl.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.put(
                    "/admin/pnl/profiles/p1/cogs-skus",
                    json={"entries": [{"sku": "SKU1", "unit_cost": "1.8600"}]},
                )
        finally:
            app.dependency_overrides.pop(pnl.require_admin_user, None)

        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        fake_svc.save_sku_cogs.assert_called_once_with(
            "p1",
            [{"sku": "SKU1", "unit_cost": "1.8600"}],
        )

    def test_save_cogs_skus_validation_error_returns_400(self, monkeypatch):
        from app.services.pnl.profiles import PNLValidationError

        fake_svc = MagicMock()
        fake_svc.save_sku_cogs.side_effect = PNLValidationError("invalid cogs")
        monkeypatch.setattr(pnl, "_get_profile_service", lambda: fake_svc)
        app.dependency_overrides[pnl.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.put(
                    "/admin/pnl/profiles/p1/cogs-skus",
                    json={"entries": [{"sku": "SKU1", "unit_cost": "oops"}]},
                )
        finally:
            app.dependency_overrides.pop(pnl.require_admin_user, None)

        assert resp.status_code == 400
        assert "invalid cogs" in resp.json()["detail"]

    def test_list_other_expenses(self, monkeypatch):
        fake_svc = MagicMock()
        fake_svc.list_other_expenses.return_value = {
            "expense_types": [
                {"key": "fbm_fulfillment_fees", "label": "FBM Fulfillment Fees", "enabled": True},
                {"key": "agency_fees", "label": "Agency Fees", "enabled": False},
                {"key": "freight", "label": "Freight", "enabled": False},
            ],
            "months": [
                {
                    "entry_month": "2026-01-01",
                    "values": {
                        "fbm_fulfillment_fees": "12.00",
                        "agency_fees": None,
                        "freight": None,
                    },
                }
            ],
        }
        monkeypatch.setattr(pnl, "_get_profile_service", lambda: fake_svc)
        app.dependency_overrides[pnl.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.get(
                    "/admin/pnl/profiles/p1/other-expenses",
                    params={"start_month": "2026-01-01", "end_month": "2026-02-01"},
                )
        finally:
            app.dependency_overrides.pop(pnl.require_admin_user, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["expense_types"][0]["key"] == "fbm_fulfillment_fees"
        fake_svc.list_other_expenses.assert_called_once_with("p1", "2026-01-01", "2026-02-01")

    def test_save_other_expenses(self, monkeypatch):
        fake_svc = MagicMock()
        monkeypatch.setattr(pnl, "_get_profile_service", lambda: fake_svc)
        app.dependency_overrides[pnl.require_admin_user] = _override_admin

        payload = {
            "start_month": "2026-01-01",
            "end_month": "2026-02-01",
            "expense_types": [
                {"key": "fbm_fulfillment_fees", "enabled": True},
                {"key": "agency_fees", "enabled": False},
                {"key": "freight", "enabled": True},
            ],
            "months": [
                {
                    "entry_month": "2026-01-01",
                    "values": {
                        "fbm_fulfillment_fees": "12.00",
                        "agency_fees": None,
                        "freight": "88.00",
                    },
                }
            ],
        }

        try:
            with TestClient(app) as client:
                resp = client.put("/admin/pnl/profiles/p1/other-expenses", json=payload)
        finally:
            app.dependency_overrides.pop(pnl.require_admin_user, None)

        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        fake_svc.save_other_expenses.assert_called_once_with(
            "p1",
            "2026-01-01",
            "2026-02-01",
            payload["expense_types"],
            payload["months"],
        )

    def test_export_pnl_workbook(self, monkeypatch):
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        temp_file.write(b"fake-xlsx")
        temp_file.flush()
        temp_file.close()

        fake_svc = MagicMock()
        fake_svc.build_export_async = MagicMock()

        async def _build_export_async(*args, **kwargs):
            return temp_file.name, "whoosh-us-pnl.xlsx"

        fake_svc.build_export_async.side_effect = _build_export_async
        monkeypatch.setattr(pnl, "_get_workbook_export_service", lambda: fake_svc)
        app.dependency_overrides[pnl.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.get(
                    "/admin/pnl/profiles/p1/export.xlsx",
                    params={
                        "filter_mode": "range",
                        "start_month": "2026-01-01",
                        "end_month": "2026-02-01",
                        "show_totals": "false",
                    },
                )
        finally:
            app.dependency_overrides.pop(pnl.require_admin_user, None)
            Path(temp_file.name).unlink(missing_ok=True)

        assert resp.status_code == 200
        assert (
            resp.headers["content-type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert "whoosh-us-pnl.xlsx" in resp.headers["content-disposition"]
        assert fake_svc.build_export_async.call_count == 1


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


class TestWindsorCompare:
    def test_get_windsor_compare(self, monkeypatch):
        fake_svc = MagicMock()
        fake_svc.compare_month = AsyncMock(
            return_value={
                "profile": {"id": "p1", "marketplace_code": "US"},
                "entry_month": "2026-02-01",
                "date_from": "2026-02-01",
                "date_to": "2026-02-28",
                "windsor_account_id": "acct-us",
                "csv_baseline": {"active_imports": [], "bucket_totals": {"product_sales": "100.00"}},
                "windsor": {
                    "row_count": 1,
                    "mapped_row_count": 1,
                    "ignored_row_count": 0,
                    "unmapped_row_count": 0,
                    "ignored_amount": "0.00",
                    "unmapped_amount": "0.00",
                    "bucket_totals": {"product_sales": "100.00"},
                    "marketplace_totals": [],
                    "top_unmapped_combos": [],
                    "top_ignored_combos": [],
                },
                "comparison": {
                    "bucket_deltas": [
                        {
                            "bucket": "product_sales",
                            "csv_amount": "100.00",
                            "windsor_amount": "100.00",
                            "delta_amount": "0.00",
                        }
                    ]
                },
            }
        )
        monkeypatch.setattr(pnl, "_get_windsor_compare_service", lambda: fake_svc)
        app.dependency_overrides[pnl.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.get(
                    "/admin/pnl/profiles/p1/windsor-compare",
                    params={"entry_month": "2026-02-01"},
                )
        finally:
            app.dependency_overrides.pop(pnl.require_admin_user, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["windsor_account_id"] == "acct-us"
        assert data["comparison"]["bucket_deltas"][0]["bucket"] == "product_sales"
        fake_svc.compare_month.assert_awaited_once_with("p1", "2026-02-01", "all")

    def test_get_windsor_compare_validation_error_returns_400(self, monkeypatch):
        from app.services.pnl.profiles import PNLValidationError

        fake_svc = MagicMock()
        fake_svc.compare_month = AsyncMock(side_effect=PNLValidationError("bad month"))
        monkeypatch.setattr(pnl, "_get_windsor_compare_service", lambda: fake_svc)
        app.dependency_overrides[pnl.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.get(
                    "/admin/pnl/profiles/p1/windsor-compare",
                    params={"entry_month": "2026-02-01"},
                )
        finally:
            app.dependency_overrides.pop(pnl.require_admin_user, None)

        assert resp.status_code == 400
        assert "bad month" in resp.json()["detail"]
