from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from unittest.mock import MagicMock

import pytest

import app.services.wbr.windsor_business_sync as sync_module
from app.services.wbr.windsor_business_sync import WindsorBusinessSyncService


def test_aggregate_rows_merges_duplicate_asin_days():
    svc = WindsorBusinessSyncService(MagicMock())

    facts = svc._aggregate_rows(
        [
            {
                "account_id": "ACC-US",
                "date": "2026-03-02",
                "sales_and_traffic_report_by_date__childasin": "B001234567",
                "sales_and_traffic_report_by_date__parentasin": "PARENT1",
                "sales_and_traffic_report_by_date__trafficbyasin_pageviews": "10",
                "sales_and_traffic_report_by_date__salesbyasin_unitsordered": "2",
                "sales_and_traffic_report_by_date__salesbyasin_orderedproductsales_amount": "19.99",
                "sales_and_traffic_report_by_date__salesbyasin_orderedproductsales_currencycode": "USD",
            },
            {
                "account_id": "ACC-US",
                "date": "2026-03-02",
                "sales_and_traffic_report_by_date__childasin": "B001234567",
                "sales_and_traffic_report_by_date__parentasin": "",
                "sales_and_traffic_report_by_date__trafficbyasin_pageviews": "5",
                "sales_and_traffic_report_by_date__salesbyasin_unitsordered": "1",
                "sales_and_traffic_report_by_date__salesbyasin_orderedproductsales_amount": "10.00",
                "sales_and_traffic_report_by_date__salesbyasin_orderedproductsales_currencycode": "USD",
            },
            {
                "account_id": "OTHER-US",
                "date": "2026-03-02",
                "sales_and_traffic_report_by_date__childasin": "B001234567",
                "sales_and_traffic_report_by_date__trafficbyasin_pageviews": "99",
            },
        ],
        expected_account_id="ACC-US",
    )

    assert len(facts) == 1
    assert facts[0].report_date == date(2026, 3, 2)
    assert facts[0].child_asin == "B001234567"
    assert facts[0].parent_asin == "PARENT1"
    assert facts[0].page_views == 15
    assert facts[0].unit_sales == 3
    assert str(facts[0].sales) == "29.99"
    assert facts[0].source_row_count == 2


def test_run_backfill_chunks_requested_range(monkeypatch):
    svc = WindsorBusinessSyncService(MagicMock())

    monkeypatch.setattr(svc, "_get_profile", lambda profile_id: {"id": profile_id, "windsor_account_id": "ACC-US"})
    monkeypatch.setattr(svc, "_require_windsor_account_id", lambda profile: "ACC-US")

    calls: list[tuple[date, date, str]] = []

    async def fake_run_chunk(*, profile_id, account_id, date_from, date_to, job_type, user_id):
        calls.append((date_from, date_to, job_type))
        return {
            "run": {"id": f"{date_from.isoformat()}-{date_to.isoformat()}"},
            "rows_fetched": 1,
            "rows_loaded": 1,
        }

    monkeypatch.setattr(svc, "_run_chunk", fake_run_chunk)

    result = asyncio.run(
        svc.run_backfill(
            profile_id="profile-1",
            date_from=date(2026, 3, 1),
            date_to=date(2026, 3, 15),
            chunk_days=7,
            user_id="user-1",
        )
    )

    assert result["chunk_days"] == 7
    assert len(result["chunks"]) == 3
    assert calls == [
        (date(2026, 3, 1), date(2026, 3, 7), "backfill"),
        (date(2026, 3, 8), date(2026, 3, 14), "backfill"),
        (date(2026, 3, 15), date(2026, 3, 15), "backfill"),
    ]


def test_run_daily_refresh_uses_profile_rewrite_window(monkeypatch):
    svc = WindsorBusinessSyncService(MagicMock())

    class _FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 3, 13, 12, 0, 0, tzinfo=tz or UTC)

    monkeypatch.setattr(sync_module, "datetime", _FakeDateTime)
    monkeypatch.setattr(
        svc,
        "_get_profile",
        lambda profile_id: {
            "id": profile_id,
            "windsor_account_id": "ACC-US",
            "daily_rewrite_days": 14,
        },
    )
    monkeypatch.setattr(svc, "_require_windsor_account_id", lambda profile: "ACC-US")

    observed: dict[str, date] = {}

    async def fake_run_chunk(*, profile_id, account_id, date_from, date_to, job_type, user_id):
        observed["date_from"] = date_from
        observed["date_to"] = date_to
        observed["job_type"] = job_type
        return {"run": {"id": "run-1"}, "rows_fetched": 2, "rows_loaded": 2}

    monkeypatch.setattr(svc, "_run_chunk", fake_run_chunk)

    result = asyncio.run(svc.run_daily_refresh(profile_id="profile-1", user_id="user-1"))

    assert result["job_type"] == "daily_refresh"
    assert observed["date_from"] == date(2026, 2, 28)
    assert observed["date_to"] == date(2026, 3, 13)
    assert observed["job_type"] == "daily_refresh"
