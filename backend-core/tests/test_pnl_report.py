"""Tests for the Monthly P&L report service and router endpoint."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import pnl
from app.services.pnl.report import (
    PNLReportService,
    _month_range,
    _resolve_months,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _chain_table(response_data: list[dict] | None = None) -> MagicMock:
    table = MagicMock()
    table.select.return_value = table
    table.insert.return_value = table
    table.update.return_value = table
    table.delete.return_value = table
    table.eq.return_value = table
    table.neq.return_value = table
    table.gte.return_value = table
    table.lte.return_value = table
    table.order.return_value = table
    table.limit.return_value = table
    resp = MagicMock()
    resp.data = response_data if response_data is not None else []
    table.execute.return_value = resp
    return table


def _db_with_tables(**tables: MagicMock) -> MagicMock:
    db = MagicMock()
    db.table.side_effect = lambda name: tables.get(name, _chain_table())
    return db


def _override_admin():
    return {"sub": "user-123"}


# ── Pure function tests ──────────────────────────────────────────────


class TestResolveMonths:
    def test_ytd(self):
        with patch("app.services.pnl.report.datetime") as mock_dt:
            mock_dt.now.return_value = MagicMock(
                date=MagicMock(return_value=date(2026, 3, 15))
            )
            mock_dt.now.return_value.date.return_value = date(2026, 3, 15)
            start, end = _resolve_months("ytd", None, None)
        assert start == date(2026, 1, 1)
        assert end == date(2026, 3, 1)

    def test_last_3(self):
        with patch("app.services.pnl.report.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 3, 15)
            start, end = _resolve_months("last_3", None, None)
        assert start == date(2025, 12, 1)
        assert end == date(2026, 3, 1)

    def test_last_12(self):
        with patch("app.services.pnl.report.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 3, 15)
            start, end = _resolve_months("last_12", None, None)
        assert start == date(2025, 3, 1)
        assert end == date(2026, 3, 1)

    def test_range(self):
        start, end = _resolve_months("range", "2025-06-01", "2025-12-01")
        assert start == date(2025, 6, 1)
        assert end == date(2025, 12, 1)

    def test_range_missing_params(self):
        from app.services.pnl.profiles import PNLValidationError
        with pytest.raises(PNLValidationError, match="required"):
            _resolve_months("range", None, None)

    def test_unknown_filter(self):
        from app.services.pnl.profiles import PNLValidationError
        with pytest.raises(PNLValidationError, match="Unknown"):
            _resolve_months("weekly", None, None)


class TestMonthRange:
    def test_single_month(self):
        result = _month_range(date(2026, 1, 1), date(2026, 1, 1))
        assert result == ["2026-01-01"]

    def test_multi_month(self):
        result = _month_range(date(2026, 1, 1), date(2026, 3, 1))
        assert result == ["2026-01-01", "2026-02-01", "2026-03-01"]

    def test_cross_year(self):
        result = _month_range(date(2025, 11, 1), date(2026, 2, 1))
        assert result == ["2025-11-01", "2025-12-01", "2026-01-01", "2026-02-01"]

    def test_empty_range(self):
        result = _month_range(date(2026, 3, 1), date(2026, 1, 1))
        assert result == []


# ── Report service tests ─────────────────────────────────────────────


FAKE_PROFILE = {
    "id": "p1",
    "client_id": "c1",
    "marketplace_code": "US",
    "currency_code": "USD",
    "status": "active",
}

FAKE_LEDGER_ENTRIES = [
    {"entry_month": "2026-01-01", "ledger_bucket": "product_sales", "amount": "100.00", "import_month_id": "im1"},
    {"entry_month": "2026-01-01", "ledger_bucket": "shipping_credits", "amount": "10.00", "import_month_id": "im1"},
    {"entry_month": "2026-01-01", "ledger_bucket": "refunds", "amount": "-20.00", "import_month_id": "im1"},
    {"entry_month": "2026-01-01", "ledger_bucket": "referral_fees", "amount": "-15.00", "import_month_id": "im1"},
    {"entry_month": "2026-01-01", "ledger_bucket": "fba_fees", "amount": "-8.00", "import_month_id": "im1"},
    {"entry_month": "2026-01-01", "ledger_bucket": "advertising", "amount": "-25.00", "import_month_id": "im1"},
    {"entry_month": "2026-01-01", "ledger_bucket": "non_pnl_transfer", "amount": "-500.00", "import_month_id": "im1"},
    {"entry_month": "2026-02-01", "ledger_bucket": "product_sales", "amount": "200.00", "import_month_id": "im2"},
    {"entry_month": "2026-02-01", "ledger_bucket": "referral_fees", "amount": "-30.00", "import_month_id": "im2"},
]

FAKE_ACTIVE_MONTHS = [
    {"id": "im1", "entry_month": "2026-01-01", "unmapped_amount": "5.00"},
    {"id": "im2", "entry_month": "2026-02-01", "unmapped_amount": "0"},
]


class TestPNLReportService:
    def _make_service(self):
        profiles_table = _chain_table([FAKE_PROFILE])
        ledger_table = _chain_table(FAKE_LEDGER_ENTRIES)
        active_months_table = _chain_table(FAKE_ACTIVE_MONTHS)
        cogs_table = _chain_table([
            {"entry_month": "2026-01-01", "cogs_amount": "30.00"},
        ])

        call_count = {"import_months": 0}

        def import_months_factory():
            call_count["import_months"] += 1
            if call_count["import_months"] == 1:
                # _active_import_month_ids call
                return _chain_table([{"id": "im1"}, {"id": "im2"}])
            elif call_count["import_months"] == 2:
                # _load_unmapped_totals call
                return _chain_table(FAKE_ACTIVE_MONTHS)
            else:
                # _load_active_months call
                return _chain_table([
                    {"entry_month": "2026-01-01"},
                    {"entry_month": "2026-02-01"},
                ])

        db = MagicMock()

        def table_router(name):
            if name == "monthly_pnl_profiles":
                return profiles_table
            elif name == "monthly_pnl_ledger_entries":
                return ledger_table
            elif name == "monthly_pnl_cogs_monthly":
                return cogs_table
            elif name == "monthly_pnl_import_months":
                return import_months_factory()
            return _chain_table()

        db.table.side_effect = table_router
        return PNLReportService(db)

    def test_report_structure(self):
        svc = self._make_service()
        report = svc.build_report(
            "p1", filter_mode="range", start_month="2026-01-01", end_month="2026-02-01"
        )
        assert report["profile"]["id"] == "p1"
        assert report["months"] == ["2026-01-01", "2026-02-01"]
        assert len(report["line_items"]) > 0
        assert isinstance(report["warnings"], list)

    def test_report_line_item_keys(self):
        svc = self._make_service()
        report = svc.build_report(
            "p1", filter_mode="range", start_month="2026-01-01", end_month="2026-02-01"
        )
        keys = [li["key"] for li in report["line_items"]]
        assert "product_sales" in keys
        assert "total_gross_revenue" in keys
        assert "refunds" in keys
        assert "total_refunds" in keys
        assert "total_net_revenue" in keys
        assert "cogs" in keys
        assert "gross_profit" in keys
        assert "total_expenses" in keys
        assert "net_earnings" in keys

    def test_revenue_totals(self):
        svc = self._make_service()
        report = svc.build_report(
            "p1", filter_mode="range", start_month="2026-01-01", end_month="2026-02-01"
        )
        items = {li["key"]: li for li in report["line_items"]}

        # January: product_sales=100, shipping=10 → gross=110
        assert items["product_sales"]["months"]["2026-01-01"] == "100.00"
        assert items["shipping_credits"]["months"]["2026-01-01"] == "10.00"
        assert items["total_gross_revenue"]["months"]["2026-01-01"] == "110.00"

        # February: product_sales=200 → gross=200
        assert items["product_sales"]["months"]["2026-02-01"] == "200.00"
        assert items["total_gross_revenue"]["months"]["2026-02-01"] == "200.00"

    def test_net_revenue(self):
        svc = self._make_service()
        report = svc.build_report(
            "p1", filter_mode="range", start_month="2026-01-01", end_month="2026-02-01"
        )
        items = {li["key"]: li for li in report["line_items"]}
        # Jan: gross=110, refunds=-20, promos=0 → net=90
        assert items["total_net_revenue"]["months"]["2026-01-01"] == "90.00"

    def test_gross_profit_with_cogs(self):
        svc = self._make_service()
        report = svc.build_report(
            "p1", filter_mode="range", start_month="2026-01-01", end_month="2026-02-01"
        )
        items = {li["key"]: li for li in report["line_items"]}
        # Jan: net_rev=90, cogs=30 → gross_profit=60
        assert items["gross_profit"]["months"]["2026-01-01"] == "60.00"
        # Feb: net_rev=200, cogs=0 → gross_profit=200
        assert items["gross_profit"]["months"]["2026-02-01"] == "200.00"

    def test_expenses_and_net_earnings(self):
        svc = self._make_service()
        report = svc.build_report(
            "p1", filter_mode="range", start_month="2026-01-01", end_month="2026-02-01"
        )
        items = {li["key"]: li for li in report["line_items"]}
        # Jan expenses: referral=-15, fba=-8, advertising=-25 → total=-48
        assert items["total_expenses"]["months"]["2026-01-01"] == "-48.00"
        # Jan net_earnings: gross_profit=60 + expenses=-48 → 12
        assert items["net_earnings"]["months"]["2026-01-01"] == "12.00"

    def test_non_pnl_buckets_excluded(self):
        svc = self._make_service()
        report = svc.build_report(
            "p1", filter_mode="range", start_month="2026-01-01", end_month="2026-02-01"
        )
        keys = [li["key"] for li in report["line_items"]]
        assert "non_pnl_transfer" not in keys
        assert "unmapped" not in keys

    def test_derived_lines_flagged(self):
        svc = self._make_service()
        report = svc.build_report(
            "p1", filter_mode="range", start_month="2026-01-01", end_month="2026-02-01"
        )
        items = {li["key"]: li for li in report["line_items"]}
        assert items["total_gross_revenue"]["is_derived"] is True
        assert items["product_sales"]["is_derived"] is False

    def test_warnings_missing_cogs(self):
        svc = self._make_service()
        report = svc.build_report(
            "p1", filter_mode="range", start_month="2026-01-01", end_month="2026-02-01"
        )
        cogs_warning = next(
            (w for w in report["warnings"] if w["type"] == "missing_cogs"), None
        )
        assert cogs_warning is not None
        # Feb has no COGS
        assert "2026-02-01" in cogs_warning["months"]
        assert "2026-01-01" not in cogs_warning["months"]

    def test_warnings_unmapped(self):
        svc = self._make_service()
        report = svc.build_report(
            "p1", filter_mode="range", start_month="2026-01-01", end_month="2026-02-01"
        )
        unmapped_warning = next(
            (w for w in report["warnings"] if w["type"] == "unmapped_rows"), None
        )
        assert unmapped_warning is not None
        assert "2026-01-01" in unmapped_warning["months"]

    def test_profile_not_found(self):
        db = _db_with_tables(monthly_pnl_profiles=_chain_table([]))
        svc = PNLReportService(db)
        with pytest.raises(Exception, match="not found"):
            svc.build_report("nonexistent", filter_mode="range",
                             start_month="2026-01-01", end_month="2026-01-01")

    def test_empty_report_no_months(self):
        db = _db_with_tables(monthly_pnl_profiles=_chain_table([FAKE_PROFILE]))
        svc = PNLReportService(db)
        # End before start → empty month range
        report = svc.build_report(
            "p1", filter_mode="range", start_month="2026-03-01", end_month="2026-01-01"
        )
        assert report["months"] == []
        assert report["line_items"] == []


# ── Router tests ─────────────────────────────────────────────────────


class TestReportRouter:
    def test_report_endpoint_success(self, monkeypatch):
        fake_svc = MagicMock()
        fake_svc.build_report.return_value = {
            "profile": FAKE_PROFILE,
            "months": ["2026-01-01"],
            "line_items": [{"key": "product_sales", "label": "Product Sales",
                            "category": "revenue", "is_derived": False,
                            "months": {"2026-01-01": "100.00"}}],
            "warnings": [],
        }
        monkeypatch.setattr(pnl, "_get_report_service", lambda: fake_svc)
        app.dependency_overrides[pnl.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.get(
                    "/admin/pnl/profiles/p1/report",
                    params={"filter_mode": "range", "start_month": "2026-01-01", "end_month": "2026-01-01"},
                )
        finally:
            app.dependency_overrides.pop(pnl.require_admin_user, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert len(data["line_items"]) == 1

    def test_report_endpoint_not_found(self, monkeypatch):
        from app.services.pnl.profiles import PNLNotFoundError

        fake_svc = MagicMock()
        fake_svc.build_report.side_effect = PNLNotFoundError("not found")
        monkeypatch.setattr(pnl, "_get_report_service", lambda: fake_svc)
        app.dependency_overrides[pnl.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.get("/admin/pnl/profiles/bad/report")
        finally:
            app.dependency_overrides.pop(pnl.require_admin_user, None)

        assert resp.status_code == 404

    def test_report_endpoint_validation_error(self, monkeypatch):
        from app.services.pnl.profiles import PNLValidationError

        fake_svc = MagicMock()
        fake_svc.build_report.side_effect = PNLValidationError("bad filter")
        monkeypatch.setattr(pnl, "_get_report_service", lambda: fake_svc)
        app.dependency_overrides[pnl.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.get("/admin/pnl/profiles/p1/report",
                                  params={"filter_mode": "range"})
        finally:
            app.dependency_overrides.pop(pnl.require_admin_user, None)

        assert resp.status_code == 400

    def test_report_default_filter_ytd(self, monkeypatch):
        fake_svc = MagicMock()
        fake_svc.build_report.return_value = {
            "profile": FAKE_PROFILE,
            "months": [],
            "line_items": [],
            "warnings": [],
        }
        monkeypatch.setattr(pnl, "_get_report_service", lambda: fake_svc)
        app.dependency_overrides[pnl.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.get("/admin/pnl/profiles/p1/report")
        finally:
            app.dependency_overrides.pop(pnl.require_admin_user, None)

        assert resp.status_code == 200
        # Verify service was called with ytd default
        call_kwargs = fake_svc.build_report.call_args
        assert call_kwargs.kwargs["filter_mode"] == "ytd"
