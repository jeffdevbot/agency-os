from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock


async def _fake_year_comparison(*_args, **_kwargs):
    return {
        "current_year": 2026,
        "prior_year": 2025,
        "periods": {
            "current_start": "2026-01-01",
            "current_end": "2026-02-01",
            "prior_start": "2025-01-01",
            "prior_end": "2025-02-01",
        },
        "reports": {
            "current": {
                "profile": {"id": "pp1", "currency_code": "USD"},
                "months": ["2026-01-01", "2026-02-01"],
                "line_items": [
                    {
                        "key": "total_net_revenue",
                        "label": "Total Net Revenue",
                        "category": "summary",
                        "is_derived": True,
                        "months": {"2026-01-01": "100.00", "2026-02-01": "110.00"},
                    }
                ],
                "warnings": [{"type": "missing_cogs", "message": "Missing COGS", "months": ["2026-02-01"]}],
            },
            "prior": {
                "profile": {"id": "pp1", "currency_code": "USD"},
                "months": ["2025-01-01", "2025-02-01"],
                "line_items": [
                    {
                        "key": "total_net_revenue",
                        "label": "Total Net Revenue",
                        "category": "summary",
                        "is_derived": True,
                        "months": {"2025-01-01": "80.00", "2025-02-01": "90.00"},
                    }
                ],
                "warnings": [],
            },
        },
        "indexes": {
            "current": {
                "total_net_revenue": {
                    "key": "total_net_revenue",
                    "label": "Total Net Revenue",
                    "category": "summary",
                    "is_derived": True,
                    "months": {"2026-01-01": "100.00", "2026-02-01": "110.00"},
                }
            },
            "prior": {
                "total_net_revenue": {
                    "key": "total_net_revenue",
                    "label": "Total Net Revenue",
                    "category": "summary",
                    "is_derived": True,
                    "months": {"2025-01-01": "80.00", "2025-02-01": "90.00"},
                }
            },
        },
        "warnings": [{"type": "missing_cogs", "message": "Missing COGS", "months": ["2026-02-01"]}],
    }


def test_build_yoy_report_shapes_current_and_prior(monkeypatch):
    from app.services.pnl.yoy_report import PNLYoYReportService

    monkeypatch.setattr(
        "app.services.pnl.yoy_report.PNLComparisonService",
        MagicMock(return_value=MagicMock(build_year_comparison_async=AsyncMock(side_effect=_fake_year_comparison))),
    )

    service = PNLYoYReportService(object())
    result = asyncio.run(service.build_yoy_report_async("pp1", year=2026))

    assert result["current_year"] == 2026
    assert result["prior_year"] == 2025
    assert result["months"] == ["Jan", "Feb"]
    assert result["current_month_keys"] == ["2026-01-01", "2026-02-01"]
    assert result["prior_month_keys"] == ["2025-01-01", "2025-02-01"]
    assert result["line_items"][0]["current"]["2026-02-01"] == "110.00"
    assert result["line_items"][0]["prior"]["2025-02-01"] == "90.00"
    assert result["warnings"][0]["year"] == 2026
