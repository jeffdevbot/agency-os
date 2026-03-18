"""Tests for the Monthly P&L report service and router endpoint."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

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
    table.range.return_value = table
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


class _ImportMonthsTable:
    def __init__(self, rows: list[dict]):
        self._rows = rows
        self._selection = ""

    def select(self, fields):
        self._selection = fields
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def gte(self, *_args, **_kwargs):
        return self

    def lte(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def execute(self):
        response = MagicMock()
        if self._selection == "id":
            response.data = [{"id": row["id"]} for row in self._rows]
        elif "id, entry_month" in self._selection:
            response.data = [
                {"id": row["id"], "entry_month": row["entry_month"]}
                for row in self._rows
            ]
        elif "unmapped_amount" in self._selection:
            response.data = self._rows
        else:
            response.data = [{"entry_month": row["entry_month"]} for row in self._rows]
        return response


# ── Pure function tests ──────────────────────────────────────────────


class TestResolveMonths:
    def test_ytd(self):
        with patch("app.services.pnl.report.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 3, 15)
            start, end = _resolve_months("ytd", None, None)
        assert start == date(2026, 1, 1)
        assert end == date(2026, 3, 1)

    def test_last_3_returns_3_months(self):
        """last_3 = current month + previous 2 → 3 months total."""
        with patch("app.services.pnl.report.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 3, 15)
            start, end = _resolve_months("last_3", None, None)
        # Mar (current) + Feb + Jan = 3 months
        assert start == date(2026, 1, 1)
        assert end == date(2026, 3, 1)
        assert len(_month_range(start, end)) == 3

    def test_last_6_returns_6_months(self):
        """last_6 = current month + previous 5 → 6 months total."""
        with patch("app.services.pnl.report.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 3, 15)
            start, end = _resolve_months("last_6", None, None)
        # Mar back to Oct 2025 = 6 months
        assert start == date(2025, 10, 1)
        assert end == date(2026, 3, 1)
        assert len(_month_range(start, end)) == 6

    def test_last_12_returns_12_months(self):
        """last_12 = current month + previous 11 → 12 months total."""
        with patch("app.services.pnl.report.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 3, 15)
            start, end = _resolve_months("last_12", None, None)
        # Mar 2026 back to Apr 2025 = 12 months
        assert start == date(2025, 4, 1)
        assert end == date(2026, 3, 1)
        assert len(_month_range(start, end)) == 12

    def test_last_year_returns_previous_calendar_year(self):
        with patch("app.services.pnl.report.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 3, 15)
            start, end = _resolve_months("last_year", None, None)
        assert start == date(2025, 1, 1)
        assert end == date(2025, 12, 1)
        assert len(_month_range(start, end)) == 12

    def test_last_3_january_wraps_year(self):
        """last_3 in January should wrap to previous year."""
        with patch("app.services.pnl.report.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 1, 10)
            start, end = _resolve_months("last_3", None, None)
        assert start == date(2025, 11, 1)
        assert end == date(2026, 1, 1)
        assert len(_month_range(start, end)) == 3

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
    {"entry_month": "2026-01-01", "ledger_bucket": "fba_inventory_credit", "amount": "5.00", "import_month_id": "im1"},
    {"entry_month": "2026-01-01", "ledger_bucket": "promotional_rebates", "amount": "-3.00", "import_month_id": "im1"},
    {"entry_month": "2026-01-01", "ledger_bucket": "referral_fees", "amount": "-15.00", "import_month_id": "im1"},
    {"entry_month": "2026-01-01", "ledger_bucket": "fba_fees", "amount": "-8.00", "import_month_id": "im1"},
    {"entry_month": "2026-01-01", "ledger_bucket": "advertising", "amount": "-25.00", "import_month_id": "im1"},
    {"entry_month": "2026-01-01", "ledger_bucket": "promotions_fees", "amount": "-4.00", "import_month_id": "im1"},
    {"entry_month": "2026-01-01", "ledger_bucket": "marketplace_withheld_tax", "amount": "-12.00", "import_month_id": "im1"},
    {"entry_month": "2026-01-01", "ledger_bucket": "non_pnl_transfer", "amount": "-500.00", "import_month_id": "im1"},
    {"entry_month": "2026-02-01", "ledger_bucket": "product_sales", "amount": "200.00", "import_month_id": "im2"},
    {"entry_month": "2026-02-01", "ledger_bucket": "referral_fees", "amount": "-30.00", "import_month_id": "im2"},
]

FAKE_ACTIVE_MONTHS = [
    {"id": "im1", "entry_month": "2026-01-01", "unmapped_amount": "5.00"},
    {"id": "im2", "entry_month": "2026-02-01", "unmapped_amount": "0"},
]

FAKE_SKU_UNITS = [
    {"import_month_id": "im1", "entry_month": "2026-01-01", "sku": "SKU1", "net_units": 1},
    {"import_month_id": "im2", "entry_month": "2026-02-01", "sku": "SKU2", "net_units": 2},
]

FAKE_SKU_COGS = [
    {"sku": "SKU1", "unit_cost": "30.0000"},
]

FAKE_MANUAL_EXPENSE_SETTINGS: list[dict] = []
FAKE_MANUAL_EXPENSES: list[dict] = []


class TestPNLReportService:
    def _make_service(
        self,
        *,
        manual_settings: list[dict] | None = None,
        manual_expenses: list[dict] | None = None,
    ):
        profiles_table = _chain_table([FAKE_PROFILE])
        summary_table = _chain_table([
            {
                "import_month_id": row["import_month_id"],
                "entry_month": row["entry_month"],
                "ledger_bucket": row["ledger_bucket"],
                "amount": row["amount"],
            }
            for row in FAKE_LEDGER_ENTRIES
        ])
        sku_units_table = _chain_table(FAKE_SKU_UNITS)
        sku_cogs_table = _chain_table(FAKE_SKU_COGS)
        manual_settings_table = _chain_table(
            manual_settings if manual_settings is not None else FAKE_MANUAL_EXPENSE_SETTINGS
        )
        manual_expenses_table = _chain_table(
            manual_expenses if manual_expenses is not None else FAKE_MANUAL_EXPENSES
        )

        class ImportMonthsTable:
            def __init__(self):
                self._selection = ""

            def select(self, fields):
                self._selection = fields
                return self

            def eq(self, *_args, **_kwargs):
                return self

            def gte(self, *_args, **_kwargs):
                return self

            def lte(self, *_args, **_kwargs):
                return self

            def order(self, *_args, **_kwargs):
                return self

            def execute(self):
                response = MagicMock()
                if self._selection == "id":
                    response.data = [{"id": "im1"}, {"id": "im2"}]
                elif "id, entry_month" in self._selection:
                    response.data = [
                        {"id": "im1", "entry_month": "2026-01-01"},
                        {"id": "im2", "entry_month": "2026-02-01"},
                    ]
                elif "unmapped_amount" in self._selection:
                    response.data = FAKE_ACTIVE_MONTHS
                else:
                    response.data = [
                        {"entry_month": "2026-01-01"},
                        {"entry_month": "2026-02-01"},
                    ]
                return response

        import_months_table = ImportMonthsTable()

        db = MagicMock()

        def table_router(name):
            if name == "monthly_pnl_profiles":
                return profiles_table
            elif name == "monthly_pnl_import_month_bucket_totals":
                return summary_table
            elif name == "monthly_pnl_import_month_sku_units":
                return sku_units_table
            elif name == "monthly_pnl_sku_cogs":
                return sku_cogs_table
            elif name == "monthly_pnl_manual_expense_settings":
                return manual_settings_table
            elif name == "monthly_pnl_manual_expenses":
                return manual_expenses_table
            elif name == "monthly_pnl_import_months":
                return import_months_table
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

    def test_report_raises_when_summary_and_rpc_are_unavailable(self):
        profiles_table = _chain_table([FAKE_PROFILE])
        ledger_table = MagicMock()
        ledger_table.select.side_effect = AssertionError("raw-ledger fallback should never run")

        sku_units_table = _chain_table([])
        sku_cogs_table = _chain_table([])

        import_months_table = _ImportMonthsTable(
            [{"id": "im1", "entry_month": "2026-01-01", "unmapped_amount": "0"}]
        )

        db = MagicMock()

        def table_router(name):
            if name == "monthly_pnl_profiles":
                return profiles_table
            if name == "monthly_pnl_import_month_bucket_totals":
                return _chain_table([])
            if name == "monthly_pnl_ledger_entries":
                return ledger_table
            if name == "monthly_pnl_import_month_sku_units":
                return sku_units_table
            if name == "monthly_pnl_sku_cogs":
                return sku_cogs_table
            if name == "monthly_pnl_import_months":
                return import_months_table
            return _chain_table()

        db.table.side_effect = table_router
        db.rpc.side_effect = RuntimeError("rpc failed")

        svc = PNLReportService(db)
        with pytest.raises(RuntimeError, match="Failed to load Monthly P&L ledger totals"):
            svc.build_report(
                "p1", filter_mode="range", start_month="2026-01-01", end_month="2026-01-01"
            )

    def test_report_uses_bucket_totals_rpc_when_available(self):
        profiles_table = _chain_table([FAKE_PROFILE])
        sku_units_table = _chain_table([])
        sku_cogs_table = _chain_table([])

        import_months_table = _ImportMonthsTable(
            [{"id": "im1", "entry_month": "2026-01-01", "unmapped_amount": "0"}]
        )

        ledger_table = MagicMock()
        ledger_table.select.side_effect = AssertionError("ledger fallback should not run")

        rpc_chain = MagicMock()
        rpc_chain.execute.return_value = MagicMock(data=[
            {"entry_month": "2026-01-01", "ledger_bucket": "product_sales", "amount": "100.00"},
            {"entry_month": "2026-01-01", "ledger_bucket": "advertising", "amount": "-25.00"},
        ])

        db = MagicMock()

        def table_router(name):
            if name == "monthly_pnl_profiles":
                return profiles_table
            if name == "monthly_pnl_ledger_entries":
                return ledger_table
            if name == "monthly_pnl_import_month_sku_units":
                return sku_units_table
            if name == "monthly_pnl_sku_cogs":
                return sku_cogs_table
            if name == "monthly_pnl_import_months":
                return import_months_table
            return _chain_table()

        db.table.side_effect = table_router
        db.rpc.return_value = rpc_chain

        svc = PNLReportService(db)
        report = svc.build_report(
            "p1", filter_mode="range", start_month="2026-01-01", end_month="2026-01-01"
        )

        items = {li["key"]: li for li in report["line_items"]}
        assert items["product_sales"]["months"]["2026-01-01"] == "100.00"
        assert items["advertising"]["months"]["2026-01-01"] == "-25.00"
        db.rpc.assert_called_once()

    def test_report_uses_summary_table_before_rpc(self):
        profiles_table = _chain_table([FAKE_PROFILE])
        sku_units_table = _chain_table([])
        sku_cogs_table = _chain_table([])
        summary_table = _chain_table([
            {
                "import_month_id": "im1",
                "entry_month": "2026-01-01",
                "ledger_bucket": "product_sales",
                "amount": "120.00",
            },
            {
                "import_month_id": "im1",
                "entry_month": "2026-01-01",
                "ledger_bucket": "advertising",
                "amount": "-20.00",
            },
        ])

        import_months_table = _ImportMonthsTable(
            [{"id": "im1", "entry_month": "2026-01-01", "unmapped_amount": "0"}]
        )

        ledger_table = MagicMock()
        ledger_table.select.side_effect = AssertionError("ledger fallback should not run")

        db = MagicMock()

        def table_router(name):
            if name == "monthly_pnl_profiles":
                return profiles_table
            if name == "monthly_pnl_import_month_bucket_totals":
                return summary_table
            if name == "monthly_pnl_ledger_entries":
                return ledger_table
            if name == "monthly_pnl_import_month_sku_units":
                return sku_units_table
            if name == "monthly_pnl_sku_cogs":
                return sku_cogs_table
            if name == "monthly_pnl_import_months":
                return import_months_table
            return _chain_table()

        db.table.side_effect = table_router
        db.rpc.side_effect = AssertionError("rpc should not run when summary rows exist")

        svc = PNLReportService(db)
        report = svc.build_report(
            "p1", filter_mode="range", start_month="2026-01-01", end_month="2026-01-01"
        )

        items = {li["key"]: li for li in report["line_items"]}
        assert items["product_sales"]["months"]["2026-01-01"] == "120.00"
        assert items["advertising"]["months"]["2026-01-01"] == "-20.00"

    def test_report_line_item_keys(self):
        svc = self._make_service()
        report = svc.build_report(
            "p1", filter_mode="range", start_month="2026-01-01", end_month="2026-02-01"
        )
        keys = [li["key"] for li in report["line_items"]]
        assert "product_sales" in keys
        assert "promotional_rebate_refunds" in keys
        assert "fba_liquidation_proceeds" in keys
        assert "total_gross_revenue" in keys
        assert "refunds" in keys
        assert "fba_inventory_credit" in keys
        assert "promotional_rebates" in keys
        assert "a_to_z_guarantee_claims" in keys
        assert "chargebacks" in keys
        assert "total_refunds" in keys
        assert "total_net_revenue" in keys
        assert "cogs" in keys
        assert "gross_profit" in keys
        assert "inbound_shipping_and_duties" in keys
        assert "liquidation_fees" in keys
        assert "promotions_fees" in keys
        assert "total_expenses" in keys
        assert "net_earnings" in keys

    def test_manual_model_buckets_roll_into_correct_sections(self):
        profiles_table = _chain_table([FAKE_PROFILE])
        sku_units_table = _chain_table([])
        sku_cogs_table = _chain_table([])

        import_months_table = _ImportMonthsTable(
            [{"id": "im1", "entry_month": "2026-01-01", "unmapped_amount": "0"}]
        )

        rpc_chain = MagicMock()
        rpc_chain.execute.return_value = MagicMock(data=[
            {"entry_month": "2026-01-01", "ledger_bucket": "product_sales", "amount": "100.00"},
            {"entry_month": "2026-01-01", "ledger_bucket": "promotional_rebate_refunds", "amount": "2.00"},
            {"entry_month": "2026-01-01", "ledger_bucket": "fba_liquidation_proceeds", "amount": "15.00"},
            {"entry_month": "2026-01-01", "ledger_bucket": "refunds", "amount": "-10.00"},
            {"entry_month": "2026-01-01", "ledger_bucket": "a_to_z_guarantee_claims", "amount": "-3.00"},
            {"entry_month": "2026-01-01", "ledger_bucket": "chargebacks", "amount": "-4.00"},
            {"entry_month": "2026-01-01", "ledger_bucket": "inbound_shipping_and_duties", "amount": "-7.00"},
            {"entry_month": "2026-01-01", "ledger_bucket": "liquidation_fees", "amount": "-1.50"},
        ])

        db = MagicMock()

        def table_router(name):
            if name == "monthly_pnl_profiles":
                return profiles_table
            if name == "monthly_pnl_import_month_sku_units":
                return sku_units_table
            if name == "monthly_pnl_sku_cogs":
                return sku_cogs_table
            if name == "monthly_pnl_import_months":
                return import_months_table
            return _chain_table()

        db.table.side_effect = table_router
        db.rpc.return_value = rpc_chain

        svc = PNLReportService(db)
        report = svc.build_report(
            "p1", filter_mode="range", start_month="2026-01-01", end_month="2026-01-01"
        )

        items = {li["key"]: li for li in report["line_items"]}
        assert items["promotional_rebate_refunds"]["category"] == "revenue"
        assert items["fba_liquidation_proceeds"]["category"] == "revenue"
        assert items["a_to_z_guarantee_claims"]["category"] == "refunds"
        assert items["chargebacks"]["category"] == "refunds"
        assert items["inbound_shipping_and_duties"]["category"] == "expenses"
        assert items["liquidation_fees"]["category"] == "expenses"
        assert items["total_gross_revenue"]["months"]["2026-01-01"] == "117.00"
        assert items["total_refunds"]["months"]["2026-01-01"] == "-17.00"
        assert items["total_expenses"]["months"]["2026-01-01"] == "-8.50"

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

    def test_refund_section_includes_all_adjustment_buckets(self):
        """fba_inventory_credit and promotional_rebates belong in refunds, not expenses/promos."""
        svc = self._make_service()
        report = svc.build_report(
            "p1", filter_mode="range", start_month="2026-01-01", end_month="2026-02-01"
        )
        items = {li["key"]: li for li in report["line_items"]}

        # Refund section items: refunds=-20, fba_inventory_credit=5, promotional_rebates=-3
        assert items["refunds"]["months"]["2026-01-01"] == "-20.00"
        assert items["fba_inventory_credit"]["months"]["2026-01-01"] == "5.00"
        assert items["promotional_rebates"]["months"]["2026-01-01"] == "-3.00"

        # Both belong to "refunds" category
        assert items["fba_inventory_credit"]["category"] == "refunds"
        assert items["promotional_rebates"]["category"] == "refunds"

    def test_total_refunds_sums_all_refund_buckets(self):
        """Total Refunds = refunds + refund adjustments + claims + chargebacks."""
        svc = self._make_service()
        report = svc.build_report(
            "p1", filter_mode="range", start_month="2026-01-01", end_month="2026-02-01"
        )
        items = {li["key"]: li for li in report["line_items"]}

        # Jan total_refunds = -20 + 5 + 0 + 0 + (-3) + 0 = -18
        assert items["total_refunds"]["months"]["2026-01-01"] == "-18.00"

    def test_net_revenue(self):
        """Net Revenue = Gross Revenue + Total Refunds/Adjustments."""
        svc = self._make_service()
        report = svc.build_report(
            "p1", filter_mode="range", start_month="2026-01-01", end_month="2026-02-01"
        )
        items = {li["key"]: li for li in report["line_items"]}
        # Jan: gross=110, refunds_total=-18 → net=92
        assert items["total_net_revenue"]["months"]["2026-01-01"] == "92.00"

    def test_gross_profit_with_cogs(self):
        """Gross Profit = Net Revenue - (net sold units × fixed SKU cost)."""
        svc = self._make_service()
        report = svc.build_report(
            "p1", filter_mode="range", start_month="2026-01-01", end_month="2026-02-01"
        )
        items = {li["key"]: li for li in report["line_items"]}
        # Jan: net_rev=92, cogs=30 → gross_profit=62
        assert items["cogs"]["months"]["2026-01-01"] == "30.00"
        assert items["gross_profit"]["months"]["2026-01-01"] == "62.00"
        # Feb: net_rev=200, cogs=0 → gross_profit=200
        assert items["gross_profit"]["months"]["2026-02-01"] == "200.00"

    def test_expenses_and_net_earnings(self):
        svc = self._make_service()
        report = svc.build_report(
            "p1", filter_mode="range", start_month="2026-01-01", end_month="2026-02-01"
        )
        items = {li["key"]: li for li in report["line_items"]}
        # Jan expenses: referral=-15, fba=-8, advertising=-25, promotions=-4 → total=-52
        # marketplace_withheld_tax is excluded as pass-through tax.
        assert items["total_expenses"]["months"]["2026-01-01"] == "-52.00"
        # Jan net_earnings: gross_profit=62 + expenses=-52 → 10
        assert items["net_earnings"]["months"]["2026-01-01"] == "10.00"

    def test_enabled_other_expenses_render_and_roll_into_totals(self):
        svc = self._make_service(
            manual_settings=[
                {"expense_key": "fbm_fulfillment_fees", "is_enabled": True},
                {"expense_key": "agency_fees", "is_enabled": True},
                {"expense_key": "freight", "is_enabled": True},
            ],
            manual_expenses=[
                {"entry_month": "2026-01-01", "expense_key": "fbm_fulfillment_fees", "amount": "11.00"},
                {"entry_month": "2026-02-01", "expense_key": "agency_fees", "amount": "7.50"},
                {"entry_month": "2026-01-01", "expense_key": "freight", "amount": "5.25"},
            ],
        )
        report = svc.build_report(
            "p1", filter_mode="range", start_month="2026-01-01", end_month="2026-02-01"
        )

        items = {li["key"]: li for li in report["line_items"]}
        keys = [li["key"] for li in report["line_items"]]

        assert items["fbm_fulfillment_fees"]["months"]["2026-01-01"] == "-11.00"
        assert items["agency_fees"]["months"]["2026-02-01"] == "-7.50"
        assert items["freight"]["months"]["2026-01-01"] == "-5.25"
        assert items["total_expenses"]["months"]["2026-01-01"] == "-68.25"
        assert items["total_expenses"]["months"]["2026-02-01"] == "-37.50"
        assert items["net_earnings"]["months"]["2026-02-01"] == "162.50"
        assert keys.index("fba_fees") < keys.index("fbm_fulfillment_fees") < keys.index("other_transaction_fees")
        assert keys.index("agency_fees") < keys.index("freight") < keys.index("total_expenses")

    def test_disabled_other_expenses_do_not_render(self):
        svc = self._make_service(
            manual_settings=[
                {"expense_key": "fbm_fulfillment_fees", "is_enabled": False},
                {"expense_key": "agency_fees", "is_enabled": False},
                {"expense_key": "freight", "is_enabled": False},
            ],
            manual_expenses=[
                {"entry_month": "2026-01-01", "expense_key": "fbm_fulfillment_fees", "amount": "11.00"},
                {"entry_month": "2026-02-01", "expense_key": "agency_fees", "amount": "7.50"},
                {"entry_month": "2026-01-01", "expense_key": "freight", "amount": "5.25"},
            ],
        )
        report = svc.build_report(
            "p1", filter_mode="range", start_month="2026-01-01", end_month="2026-02-01"
        )

        items = {li["key"]: li for li in report["line_items"]}
        assert "fbm_fulfillment_fees" not in items
        assert "agency_fees" not in items
        assert "freight" not in items
        assert items["total_expenses"]["months"]["2026-01-01"] == "-52.00"

    def test_fba_inventory_credit_not_in_expenses(self):
        """fba_inventory_credit moved to refunds section, should not appear as an expense."""
        svc = self._make_service()
        report = svc.build_report(
            "p1", filter_mode="range", start_month="2026-01-01", end_month="2026-02-01"
        )
        expense_keys = [
            li["key"] for li in report["line_items"] if li["category"] == "expenses"
        ]
        assert "fba_inventory_credit" not in expense_keys

    def test_non_pnl_buckets_excluded(self):
        svc = self._make_service()
        report = svc.build_report(
            "p1", filter_mode="range", start_month="2026-01-01", end_month="2026-02-01"
        )
        keys = [li["key"] for li in report["line_items"]]
        items = {li["key"]: li for li in report["line_items"]}
        assert "non_pnl_transfer" not in keys
        assert "unmapped" not in keys
        assert "marketplace_withheld_tax" not in keys
        assert "payout_amount" in keys
        assert items["payout_amount"]["months"]["2026-01-01"] == "500.00"
        assert items["payout_amount"]["months"]["2026-02-01"] == "0.00"

    def test_derived_lines_flagged(self):
        svc = self._make_service()
        report = svc.build_report(
            "p1", filter_mode="range", start_month="2026-01-01", end_month="2026-02-01"
        )
        items = {li["key"]: li for li in report["line_items"]}
        assert items["total_gross_revenue"]["is_derived"] is True
        assert items["total_refunds"]["is_derived"] is True
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
        assert "SKU2" in cogs_warning["skus"]

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
        fake_svc.build_report_async = AsyncMock(return_value={
            "profile": FAKE_PROFILE,
            "months": ["2026-01-01"],
            "line_items": [{"key": "product_sales", "label": "Product Sales",
                            "category": "revenue", "is_derived": False,
                            "months": {"2026-01-01": "100.00"}}],
            "warnings": [],
        })
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
        fake_svc.build_report_async = AsyncMock(side_effect=PNLNotFoundError("not found"))
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
        fake_svc.build_report_async = AsyncMock(side_effect=PNLValidationError("bad filter"))
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
        fake_svc.build_report_async = AsyncMock(return_value={
            "profile": FAKE_PROFILE,
            "months": [],
            "line_items": [],
            "warnings": [],
        })
        monkeypatch.setattr(pnl, "_get_report_service", lambda: fake_svc)
        app.dependency_overrides[pnl.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.get("/admin/pnl/profiles/p1/report")
        finally:
            app.dependency_overrides.pop(pnl.require_admin_user, None)

        assert resp.status_code == 200
        # Verify service was called with ytd default
        call_kwargs = fake_svc.build_report_async.call_args
        assert call_kwargs.kwargs["filter_mode"] == "ytd"

    def test_report_range_params_passed_to_service(self, monkeypatch):
        """Backend correctly passes start_month/end_month to service for range mode."""
        fake_svc = MagicMock()
        fake_svc.build_report_async = AsyncMock(return_value={
            "profile": FAKE_PROFILE,
            "months": ["2025-06-01"],
            "line_items": [],
            "warnings": [],
        })
        monkeypatch.setattr(pnl, "_get_report_service", lambda: fake_svc)
        app.dependency_overrides[pnl.require_admin_user] = _override_admin

        try:
            with TestClient(app) as client:
                resp = client.get(
                    "/admin/pnl/profiles/p1/report",
                    params={
                        "filter_mode": "range",
                        "start_month": "2025-06-01",
                        "end_month": "2025-09-01",
                    },
                )
        finally:
            app.dependency_overrides.pop(pnl.require_admin_user, None)

        assert resp.status_code == 200
        call_kwargs = fake_svc.build_report_async.call_args
        assert call_kwargs.kwargs["filter_mode"] == "range"
        assert call_kwargs.kwargs["start_month"] == "2025-06-01"
        assert call_kwargs.kwargs["end_month"] == "2025-09-01"
