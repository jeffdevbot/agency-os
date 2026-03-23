from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from app.services.pnl.email_brief import PNLEmailBriefService


def _line(key: str, label: str, category: str, months: dict[str, str]) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "category": category,
        "months": months,
    }


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows
        self._filters: list[tuple[str, object]] = []
        self._limit: int | None = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        self._filters.append((key, value))
        return self

    def limit(self, value):
        self._limit = value
        return self

    def execute(self):
        rows = self._rows
        for key, value in self._filters:
            rows = [row for row in rows if row.get(key) == value]
        if self._limit is not None:
            rows = rows[: self._limit]

        class _Resp:
            data = rows

        return _Resp()


class _FakeDB:
    def __init__(self, *, clients, active_months):
        self._clients = clients
        self._active_months = active_months

    def table(self, name):
        if name == "agency_clients":
            return _FakeQuery(self._clients)
        if name == "monthly_pnl_import_months":
            return _FakeQuery(self._active_months)
        raise AssertionError(f"unexpected table {name}")


class _FakePNLProfileService:
    def __init__(self, _db):
        pass

    def list_profiles(self, client_id):
        assert client_id == "c1"
        return [
            {
                "id": "pp1",
                "client_id": "c1",
                "marketplace_code": "US",
                "currency_code": "USD",
                "status": "active",
            }
        ]


class _FakePNLProfileServiceNoYoy(_FakePNLProfileService):
    pass


class _FakePNLReportService:
    def __init__(self, _db):
        pass

    async def build_report_async(self, profile_id, *, filter_mode, start_month, end_month):
        assert profile_id == "pp1"
        assert filter_mode == "range"
        reports = {
            ("2026-02-01", "2026-02-01"): {
                "profile": {"id": "pp1"},
                "months": ["2026-02-01"],
                "line_items": [
                    _line("total_gross_revenue", "Total Gross Revenue", "summary", {"2026-02-01": "100.00"}),
                    _line("total_refunds", "Total Refunds", "summary", {"2026-02-01": "-10.00"}),
                    _line("total_net_revenue", "Total Net Revenue", "summary", {"2026-02-01": "90.00"}),
                    _line("gross_profit", "Gross Profit", "summary", {"2026-02-01": "70.00"}),
                    _line("advertising", "Advertising", "expenses", {"2026-02-01": "-15.00"}),
                    _line("net_earnings", "Net Earnings", "bottom_line", {"2026-02-01": "25.00"}),
                    _line("fba_monthly_storage_fees", "FBA Monthly Storage Fees", "expenses", {"2026-02-01": "-5.00"}),
                ],
                "warnings": [],
            },
            ("2026-01-01", "2026-02-01"): {
                "profile": {"id": "pp1"},
                "months": ["2026-01-01", "2026-02-01"],
                "line_items": [
                    _line("total_gross_revenue", "Total Gross Revenue", "summary", {"2026-01-01": "80.00", "2026-02-01": "100.00"}),
                    _line("total_refunds", "Total Refunds", "summary", {"2026-01-01": "-12.00", "2026-02-01": "-10.00"}),
                    _line("total_net_revenue", "Total Net Revenue", "summary", {"2026-01-01": "68.00", "2026-02-01": "90.00"}),
                    _line("gross_profit", "Gross Profit", "summary", {"2026-01-01": "52.00", "2026-02-01": "70.00"}),
                    _line("advertising", "Advertising", "expenses", {"2026-01-01": "-18.00", "2026-02-01": "-15.00"}),
                    _line("net_earnings", "Net Earnings", "bottom_line", {"2026-01-01": "10.00", "2026-02-01": "25.00"}),
                    _line("fba_monthly_storage_fees", "FBA Monthly Storage Fees", "expenses", {"2026-01-01": "-3.00", "2026-02-01": "-5.00"}),
                ],
                "warnings": [],
            },
            ("2026-01-01", "2026-01-01"): {
                "profile": {"id": "pp1"},
                "months": ["2026-01-01"],
                "line_items": [
                    _line("total_gross_revenue", "Total Gross Revenue", "summary", {"2026-01-01": "80.00"}),
                    _line("total_refunds", "Total Refunds", "summary", {"2026-01-01": "-12.00"}),
                    _line("total_net_revenue", "Total Net Revenue", "summary", {"2026-01-01": "68.00"}),
                    _line("gross_profit", "Gross Profit", "summary", {"2026-01-01": "52.00"}),
                    _line("advertising", "Advertising", "expenses", {"2026-01-01": "-18.00"}),
                    _line("net_earnings", "Net Earnings", "bottom_line", {"2026-01-01": "10.00"}),
                    _line("fba_monthly_storage_fees", "FBA Monthly Storage Fees", "expenses", {"2026-01-01": "-3.00"}),
                ],
                "warnings": [],
            },
            ("2025-02-01", "2025-02-01"): {
                "profile": {"id": "pp1"},
                "months": ["2025-02-01"],
                "line_items": [
                    _line("total_gross_revenue", "Total Gross Revenue", "summary", {"2025-02-01": "75.00"}),
                    _line("total_refunds", "Total Refunds", "summary", {"2025-02-01": "-12.00"}),
                    _line("total_net_revenue", "Total Net Revenue", "summary", {"2025-02-01": "63.00"}),
                    _line("gross_profit", "Gross Profit", "summary", {"2025-02-01": "48.00"}),
                    _line("advertising", "Advertising", "expenses", {"2025-02-01": "-14.00"}),
                    _line("net_earnings", "Net Earnings", "bottom_line", {"2025-02-01": "12.00"}),
                    _line("fba_monthly_storage_fees", "FBA Monthly Storage Fees", "expenses", {"2025-02-01": "-2.00"}),
                ],
                "warnings": [],
            },
            ("2025-01-01", "2025-02-01"): {
                "profile": {"id": "pp1"},
                "months": ["2025-01-01", "2025-02-01"],
                "line_items": [
                    _line("total_gross_revenue", "Total Gross Revenue", "summary", {"2025-01-01": "60.00", "2025-02-01": "75.00"}),
                    _line("total_refunds", "Total Refunds", "summary", {"2025-01-01": "-8.00", "2025-02-01": "-12.00"}),
                    _line("total_net_revenue", "Total Net Revenue", "summary", {"2025-01-01": "52.00", "2025-02-01": "63.00"}),
                    _line("gross_profit", "Gross Profit", "summary", {"2025-01-01": "39.00", "2025-02-01": "48.00"}),
                    _line("advertising", "Advertising", "expenses", {"2025-01-01": "-11.00", "2025-02-01": "-14.00"}),
                    _line("net_earnings", "Net Earnings", "bottom_line", {"2025-01-01": "7.00", "2025-02-01": "12.00"}),
                    _line("fba_monthly_storage_fees", "FBA Monthly Storage Fees", "expenses", {"2025-01-01": "-1.00", "2025-02-01": "-2.00"}),
                ],
                "warnings": [],
            },
        }
        return reports[(start_month, end_month)]


def test_build_client_brief_prefers_yoy_when_available(monkeypatch):
    fake_db = _FakeDB(
        clients=[{"id": "c1", "name": "Whoosh"}],
        active_months=[
            {"profile_id": "pp1", "entry_month": "2025-01-01", "is_active": True},
            {"profile_id": "pp1", "entry_month": "2025-02-01", "is_active": True},
            {"profile_id": "pp1", "entry_month": "2026-01-01", "is_active": True},
            {"profile_id": "pp1", "entry_month": "2026-02-01", "is_active": True},
        ],
    )

    monkeypatch.setattr("app.services.pnl.email_brief.PNLProfileService", _FakePNLProfileService)
    monkeypatch.setattr("app.services.pnl.comparison.PNLReportService", _FakePNLReportService)

    svc = PNLEmailBriefService(fake_db)
    result = asyncio.run(
        svc.build_client_brief_async("c1", "2026-02-01")
    )

    assert result["client"]["client_name"] == "Whoosh"
    assert result["comparison_mode_used"] == "yoy_preferred"
    assert result["marketplace_scope"] == ["US"]
    assert result["overall_summary_points"][0] == "Best latest-month Net Earnings margin: US at 27.8%."

    section = result["sections"][0]
    assert section["comparison_mode_used"] == "yoy_preferred"
    assert section["latest_month_has_yoy"] is True
    assert section["ytd_has_yoy"] is True
    assert section["has_previous_month"] is True
    assert section["financial_health"] == {
        "verdict": "Excellent",
        "reason": "Net Earnings margin is strong at 27.8%.",
    }

    snapshot = {metric["key"]: metric for metric in section["snapshot_metrics"]}
    assert snapshot["total_net_revenue"]["latest_month_yoy_percent_change"] == "42.86"
    assert snapshot["advertising_pct_of_net_revenue"]["latest_month_value"] == "16.67"
    assert snapshot["advertising_pct_of_net_revenue"]["latest_month_yoy_pp_change"] == "-5.56"
    assert snapshot["net_earnings_pct_of_net_revenue"]["latest_month_value"] == "27.78"
    assert snapshot["net_earnings_pct_of_net_revenue"]["latest_month_yoy_pp_change"] == "8.73"

    assert any(driver["title"] == "Net Earnings margin" for driver in section["positive_drivers"])
    assert any(driver["title"] == "Monthly storage burden" for driver in section["negative_drivers"])
    assert section["data_quality_notes"] == []


def test_build_client_brief_falls_back_to_mom_when_yoy_unavailable(monkeypatch):
    fake_db = _FakeDB(
        clients=[{"id": "c1", "name": "Whoosh"}],
        active_months=[
            {"profile_id": "pp1", "entry_month": "2026-01-01", "is_active": True},
            {"profile_id": "pp1", "entry_month": "2026-02-01", "is_active": True},
        ],
    )

    monkeypatch.setattr("app.services.pnl.email_brief.PNLProfileService", _FakePNLProfileServiceNoYoy)
    monkeypatch.setattr("app.services.pnl.comparison.PNLReportService", _FakePNLReportService)

    svc = PNLEmailBriefService(fake_db)
    result = asyncio.run(
        svc.build_client_brief_async("c1", "2026-02-01")
    )

    section = result["sections"][0]
    assert section["comparison_mode_used"] == "mom_fallback"
    assert section["latest_month_has_yoy"] is False
    assert section["ytd_has_yoy"] is False
    assert section["has_previous_month"] is True
    assert "Latest-month YoY is unavailable for Feb 2026." in section["data_quality_notes"]
    assert "YTD YoY is unavailable for Feb 2026." in section["data_quality_notes"]
