from __future__ import annotations

import asyncio
from datetime import date

from app.services.pnl.comparison import PNLComparisonService


def _line(key: str, label: str, category: str, months: dict[str, str]) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "category": category,
        "months": months,
    }


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
                    _line("total_net_revenue", "Total Net Revenue", "summary", {"2026-02-01": "90.00"}),
                ],
                "warnings": [],
            },
            ("2026-01-01", "2026-02-01"): {
                "profile": {"id": "pp1"},
                "months": ["2026-01-01", "2026-02-01"],
                "line_items": [
                    _line("total_net_revenue", "Total Net Revenue", "summary", {"2026-01-01": "68.00", "2026-02-01": "90.00"}),
                ],
                "warnings": [{"type": "missing_cogs", "message": "Missing COGS", "months": ["2026-02-01"]}],
            },
            ("2026-01-01", "2026-01-01"): {
                "profile": {"id": "pp1"},
                "months": ["2026-01-01"],
                "line_items": [
                    _line("total_net_revenue", "Total Net Revenue", "summary", {"2026-01-01": "68.00"}),
                ],
                "warnings": [],
            },
            ("2025-02-01", "2025-02-01"): {
                "profile": {"id": "pp1"},
                "months": ["2025-02-01"],
                "line_items": [
                    _line("total_net_revenue", "Total Net Revenue", "summary", {"2025-02-01": "63.00"}),
                ],
                "warnings": [{"type": "missing_cogs", "message": "Missing COGS", "months": ["2026-02-01"]}],
            },
            ("2025-01-01", "2025-02-01"): {
                "profile": {"id": "pp1"},
                "months": ["2025-01-01", "2025-02-01"],
                "line_items": [
                    _line("total_net_revenue", "Total Net Revenue", "summary", {"2025-01-01": "52.00", "2025-02-01": "63.00"}),
                ],
                "warnings": [],
            },
        }
        return reports[(start_month, end_month)]


def test_build_month_comparison_prefers_yoy(monkeypatch):
    monkeypatch.setattr("app.services.pnl.comparison.PNLReportService", _FakePNLReportService)

    svc = PNLComparisonService(object())
    result = asyncio.run(
        svc.build_month_comparison_async(
            "pp1",
            report_month_date=date(2026, 2, 1),
            active_months={"2025-01-01", "2025-02-01", "2026-01-01", "2026-02-01"},
            comparison_mode="auto",
        )
    )

    assert result["comparison_mode_used"] == "yoy_preferred"
    assert result["latest_month_has_yoy"] is True
    assert result["ytd_has_yoy"] is True
    assert result["has_previous_month"] is True
    assert result["periods"]["latest_month_prior_year"] == "2025-02-01"
    assert result["reports"]["latest"]["months"] == ["2026-02-01"]
    assert result["indexes"]["ytd"]["total_net_revenue"]["label"] == "Total Net Revenue"
    assert result["warnings"] == [{"type": "missing_cogs", "message": "Missing COGS", "months": ["2026-02-01"]}]


def test_build_month_comparison_falls_back_to_mom(monkeypatch):
    monkeypatch.setattr("app.services.pnl.comparison.PNLReportService", _FakePNLReportService)

    svc = PNLComparisonService(object())
    result = asyncio.run(
        svc.build_month_comparison_async(
            "pp1",
            report_month_date=date(2026, 2, 1),
            active_months={"2026-01-01", "2026-02-01"},
            comparison_mode="auto",
        )
    )

    assert result["comparison_mode_used"] == "mom_fallback"
    assert result["latest_month_has_yoy"] is False
    assert result["ytd_has_yoy"] is False
    assert result["has_previous_month"] is True
    assert result["periods"]["latest_month_prior_year"] is None
    assert result["reports"]["latest_prior_year"] is None
    assert result["reports"]["ytd_prior_year"] is None


def test_build_year_comparison_uses_last_active_month(monkeypatch):
    class _FakeYearReportService:
        def __init__(self, _db):
            pass

        async def build_report_async(self, profile_id, *, filter_mode, start_month, end_month):
            assert profile_id == "pp1"
            assert filter_mode == "range"
            reports = {
                ("2025-01-01", "2025-03-01"): {
                    "profile": {"id": "pp1"},
                    "months": ["2025-01-01", "2025-02-01", "2025-03-01"],
                    "line_items": [
                        _line("total_net_revenue", "Total Net Revenue", "summary", {
                            "2025-01-01": "40.00",
                            "2025-02-01": "50.00",
                            "2025-03-01": "60.00",
                        }),
                    ],
                    "warnings": [],
                },
                ("2024-01-01", "2024-03-01"): {
                    "profile": {"id": "pp1"},
                    "months": ["2024-01-01", "2024-02-01", "2024-03-01"],
                    "line_items": [
                        _line("total_net_revenue", "Total Net Revenue", "summary", {
                            "2024-01-01": "35.00",
                            "2024-02-01": "45.00",
                            "2024-03-01": "55.00",
                        }),
                    ],
                    "warnings": [],
                },
            }
            return reports[(start_month, end_month)]

    class _FakeQuery:
        def select(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def execute(self):
            class _Resp:
                data = [
                    {"entry_month": "2025-01-01"},
                    {"entry_month": "2025-02-01"},
                    {"entry_month": "2025-03-01"},
                ]

            return _Resp()

    class _FakeDB:
        def table(self, _name):
            return _FakeQuery()

    monkeypatch.setattr("app.services.pnl.comparison.PNLReportService", _FakeYearReportService)

    svc = PNLComparisonService(_FakeDB())
    result = asyncio.run(
        svc.build_year_comparison_async("pp1", year=2025)
    )

    assert result["current_year"] == 2025
    assert result["prior_year"] == 2024
    assert result["periods"]["current_end"] == "2025-03-01"
    assert result["periods"]["prior_end"] == "2024-03-01"
