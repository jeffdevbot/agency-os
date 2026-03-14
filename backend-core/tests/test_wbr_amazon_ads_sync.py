from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import app.services.wbr.amazon_ads_sync as sync_module
from app.main import app
from app.routers import wbr
from app.services.wbr.amazon_ads_sync import AmazonAdsSyncService
from app.services.wbr.profiles import WBRValidationError


def _override_admin():
    return {"sub": "user-123"}


def test_aggregate_rows_merges_duplicate_campaign_days():
    svc = AmazonAdsSyncService(MagicMock())

    facts = svc._aggregate_rows(
        [
            {
                "date": "2026-03-02",
                "campaignId": "111",
                "campaignName": "Brand | Exact",
                "impressions": "100",
                "clicks": "10",
                "cost": "12.34",
                "purchases7d": "2",
                "sales7d": "44.56",
                "currencyCode": "USD",
            },
            {
                "date": "2026-03-02",
                "campaignId": "222",
                "campaignName": "Brand | Exact",
                "impressions": "50",
                "clicks": "4",
                "cost": "1.66",
                "purchases7d": "1",
                "sales7d": "20.00",
                "currencyCode": "USD",
            },
        ],
        marketplace_code="US",
    )

    assert len(facts) == 1
    assert facts[0].report_date == date(2026, 3, 2)
    assert facts[0].campaign_name == "Brand | Exact"
    assert facts[0].campaign_id is None
    assert facts[0].campaign_type == "sponsored_products"
    assert facts[0].impressions == 150
    assert facts[0].clicks == 14
    assert facts[0].orders == 3
    assert facts[0].spend == Decimal("14.00")
    assert facts[0].sales == Decimal("64.56")
    assert facts[0].currency_code == "USD"


def test_aggregate_rows_accepts_numeric_dates_and_nested_campaign_shape():
    svc = AmazonAdsSyncService(MagicMock())

    facts = svc._aggregate_rows(
        [
            {
                "startDate": "20260303",
                "campaign": {
                    "campaignId": "999",
                    "campaignName": "Nested Campaign",
                },
                "impressions": "42",
                "clicks": "6",
                "cost": "3.50",
                "purchases7d": "1",
                "sales7d": "15.00",
            }
        ],
        marketplace_code="US",
    )

    assert len(facts) == 1
    assert facts[0].report_date == date(2026, 3, 3)
    assert facts[0].campaign_id == "999"
    assert facts[0].campaign_name == "Nested Campaign"
    assert facts[0].spend == Decimal("3.50")
    assert facts[0].sales == Decimal("15.00")


def test_aggregate_rows_keeps_ad_products_distinct_and_parses_brands_and_display_metrics():
    svc = AmazonAdsSyncService(MagicMock())

    facts = svc._aggregate_rows(
        [
            {
                "date": "2026-03-02",
                "campaignId": "111",
                "campaignName": "Brand Campaign",
                "impressions": "100",
                "clicks": "10",
                "cost": "12.34",
                "purchases": "2",
                "sales": "44.56",
                "__campaign_type": "sponsored_brands",
            },
            {
                "date": "2026-03-02",
                "campaignId": "222",
                "campaignName": "Brand Campaign",
                "impressions": "50",
                "clicks": "4",
                "cost": "1.66",
                "purchases": "1",
                "sales": "20.00",
                "__campaign_type": "sponsored_display",
            },
        ],
        marketplace_code="US",
    )

    assert len(facts) == 2
    assert facts[0].campaign_type == "sponsored_brands"
    assert facts[0].orders == 2
    assert facts[0].sales == Decimal("44.56")
    assert facts[1].campaign_type == "sponsored_display"
    assert facts[1].orders == 1
    assert facts[1].sales == Decimal("20.00")


def test_preview_helpers_capture_first_row_shape():
    svc = AmazonAdsSyncService(MagicMock())

    rows = [
        {
            "campaignName": "Campaign A",
            "date": "2026-03-03",
            "metrics": {"clicks": 5, "impressions": 100},
        }
    ]

    assert "campaignName" in svc._preview_first_row_keys(rows)
    preview = svc._preview_first_row(rows)
    assert preview["campaignName"] == "Campaign A"
    assert preview["metrics"]["clicks"] == 5


def test_run_backfill_chunks_requested_range(monkeypatch):
    svc = AmazonAdsSyncService(MagicMock())

    monkeypatch.setattr(
        svc,
        "_get_profile",
        lambda profile_id: {
            "id": profile_id,
            "amazon_ads_profile_id": "ads-prof-1",
            "marketplace_code": "US",
        },
    )
    monkeypatch.setattr(svc, "_require_amazon_ads_profile_id", lambda profile: "ads-prof-1")
    monkeypatch.setattr(svc, "_require_refresh_token", lambda profile_id: "refresh-token")

    calls: list[tuple[date, date, str]] = []

    async def fake_run_chunk(*, profile_id, amazon_ads_profile_id, refresh_token, marketplace_code, date_from, date_to, job_type, user_id):
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
    svc = AmazonAdsSyncService(MagicMock())

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
            "amazon_ads_profile_id": "ads-prof-1",
            "marketplace_code": "US",
            "daily_rewrite_days": 14,
        },
    )
    monkeypatch.setattr(svc, "_require_amazon_ads_profile_id", lambda profile: "ads-prof-1")
    monkeypatch.setattr(svc, "_require_refresh_token", lambda profile_id: "refresh-token")

    observed: dict[str, date] = {}

    async def fake_run_chunk(*, profile_id, amazon_ads_profile_id, refresh_token, marketplace_code, date_from, date_to, job_type, user_id):
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


def test_run_backfill_requires_selected_ads_profile(monkeypatch):
    svc = AmazonAdsSyncService(MagicMock())
    monkeypatch.setattr(svc, "_get_profile", lambda profile_id: {"id": profile_id, "amazon_ads_profile_id": None})

    try:
        asyncio.run(
            svc.run_backfill(
                profile_id="profile-1",
                date_from=date(2026, 3, 1),
                date_to=date(2026, 3, 7),
                user_id="user-1",
            )
        )
        assert False, "Expected WBRValidationError"
    except WBRValidationError as exc:
        assert "amazon_ads_profile_id" in str(exc)


class _FakeAmazonAdsSyncService:
    def __init__(self):
        self.last_backfill = None
        self.last_daily_refresh = None

    async def run_backfill(self, *, profile_id, date_from, date_to, chunk_days, user_id):
        self.last_backfill = {
            "profile_id": profile_id,
            "date_from": date_from,
            "date_to": date_to,
            "chunk_days": chunk_days,
            "user_id": user_id,
        }
        return {
            "profile_id": profile_id,
            "job_type": "backfill",
            "chunk_days": chunk_days,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "chunks": [],
        }

    async def run_daily_refresh(self, *, profile_id, user_id):
        self.last_daily_refresh = {"profile_id": profile_id, "user_id": user_id}
        return {
            "profile_id": profile_id,
            "job_type": "daily_refresh",
            "date_from": "2026-03-01",
            "date_to": "2026-03-13",
            "chunk": {"run": {"id": "run-1"}, "rows_fetched": 2, "rows_loaded": 2},
        }


def test_amazon_ads_backfill_endpoint_calls_service(monkeypatch):
    fake_svc = _FakeAmazonAdsSyncService()
    monkeypatch.setattr(wbr, "_get_amazon_ads_sync_service", lambda: fake_svc)
    app.dependency_overrides[wbr.require_admin_user] = _override_admin

    try:
        with TestClient(app) as client:
            resp = client.post(
                "/admin/wbr/profiles/prof-1/sync-runs/amazon-ads/backfill",
                json={"date_from": "2026-03-01", "date_to": "2026-03-15", "chunk_days": 7},
            )
        assert resp.status_code == 200
        assert fake_svc.last_backfill is not None
        assert fake_svc.last_backfill["profile_id"] == "prof-1"
        assert fake_svc.last_backfill["chunk_days"] == 7
        assert fake_svc.last_backfill["user_id"] == "user-123"
    finally:
        app.dependency_overrides.pop(wbr.require_admin_user, None)


def test_amazon_ads_daily_refresh_endpoint_calls_service(monkeypatch):
    fake_svc = _FakeAmazonAdsSyncService()
    monkeypatch.setattr(wbr, "_get_amazon_ads_sync_service", lambda: fake_svc)
    app.dependency_overrides[wbr.require_admin_user] = _override_admin

    try:
        with TestClient(app) as client:
            resp = client.post("/admin/wbr/profiles/prof-1/sync-runs/amazon-ads/daily-refresh")
        assert resp.status_code == 200
        assert fake_svc.last_daily_refresh is not None
        assert fake_svc.last_daily_refresh["profile_id"] == "prof-1"
        assert fake_svc.last_daily_refresh["user_id"] == "user-123"
    finally:
        app.dependency_overrides.pop(wbr.require_admin_user, None)
