from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import app.services.wbr.amazon_ads_sync as base_sync_module
from app.main import app
from app.routers import wbr
from app.services.wbr.amazon_ads_search_terms import AmazonAdsSearchTermSyncService
from app.services.wbr.profiles import WBRValidationError


def _override_admin():
    return {"sub": "user-123"}


def test_aggregate_rows_merges_duplicate_search_terms_and_parses_campaign_context():
    svc = AmazonAdsSearchTermSyncService(MagicMock())

    facts = svc._aggregate_rows(
        [
            {
                "date": "2026-03-02",
                "campaignId": "111",
                "campaignName": "Screen Shine - Duo XL | SBV | PP | MKW | Br.M | 10 - whiteboard | Perf",
                "adGroupId": "ag-1",
                "adGroupName": "Main Group",
                "searchTerm": "whiteboard cleaner",
                "matchType": "BROAD",
                "impressions": "100",
                "clicks": "10",
                "cost": "12.34",
                "purchases": "2",
                "sales": "44.56",
                "currencyCode": "USD",
                "__campaign_type": "sponsored_brands",
            },
            {
                "date": "2026-03-02",
                "campaignId": "222",
                "campaignName": "Screen Shine - Duo XL | SBV | PP | MKW | Br.M | 10 - whiteboard | Perf",
                "adGroupId": "ag-2",
                "adGroupName": "Main Group",
                "searchTerm": "whiteboard cleaner",
                "matchType": "BROAD",
                "impressions": "50",
                "clicks": "4",
                "cost": "1.66",
                "purchases": "1",
                "sales": "20.00",
                "currencyCode": "USD",
                "__campaign_type": "sponsored_brands",
            },
        ],
        marketplace_code="US",
    )

    assert len(facts) == 1
    assert facts[0].report_date == date(2026, 3, 2)
    assert facts[0].campaign_type == "sponsored_brands"
    assert facts[0].campaign_name_head == "Screen Shine - Duo XL"
    assert facts[0].campaign_name_parts[:3] == ["Screen Shine - Duo XL", "SBV", "PP"]
    assert facts[0].campaign_id is None
    assert facts[0].ad_group_id is None
    assert facts[0].ad_group_name == "Main Group"
    assert facts[0].search_term == "whiteboard cleaner"
    assert facts[0].match_type == "BROAD"
    assert facts[0].impressions == 150
    assert facts[0].clicks == 14
    assert facts[0].orders == 3
    assert facts[0].spend == Decimal("14.00")
    assert facts[0].sales == Decimal("64.56")
    assert facts[0].currency_code == "USD"


def test_aggregate_rows_keeps_sp_sb_sd_facts_distinct():
    svc = AmazonAdsSearchTermSyncService(MagicMock())

    facts = svc._aggregate_rows(
        [
            {
                "date": "2026-03-02",
                "campaignName": "Screen Shine - 90ct Wipes | SPA | Los. | Rsrch",
                "searchTerm": "screen cleaner",
                "impressions": "100",
                "clicks": "10",
                "cost": "12.34",
                "purchases7d": "2",
                "sales7d": "44.56",
                "__campaign_type": "sponsored_products",
            },
            {
                "date": "2026-03-02",
                "campaignName": "Screen Shine - 90ct Wipes | SBV | PP | MKW",
                "searchTerm": "screen cleaner",
                "impressions": "50",
                "clicks": "4",
                "cost": "1.66",
                "purchases": "1",
                "sales": "20.00",
                "__campaign_type": "sponsored_brands",
            },
            {
                "date": "2026-03-02",
                "campaignName": "Screen Shine - 90ct Wipes | SD | Retargeting",
                "searchTerm": "screen cleaner",
                "impressions": "25",
                "clicks": "3",
                "cost": "0.99",
                "purchases": "1",
                "sales": "12.00",
                "__campaign_type": "sponsored_display",
            },
        ],
        marketplace_code="US",
    )

    assert [fact.campaign_type for fact in facts] == [
        "sponsored_brands",
        "sponsored_display",
        "sponsored_products",
    ]


def test_run_backfill_chunks_requested_range(monkeypatch):
    svc = AmazonAdsSearchTermSyncService(MagicMock())

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
    monkeypatch.setattr(svc, "_require_refresh_token", lambda profile_id, **kwargs: "refresh-token")

    calls: list[tuple[date, date, str]] = []

    async def fake_enqueue_chunk(
        *,
        profile_id,
        amazon_ads_profile_id,
        refresh_token,
        region_code,
        marketplace_code,
        date_from,
        date_to,
        ad_product,
        job_type,
        user_id,
    ):
        assert region_code == "NA"
        calls.append((date_from, date_to, job_type))
        return {"run": {"id": f"{date_from.isoformat()}-{date_to.isoformat()}"}, "rows_fetched": 0, "rows_loaded": 0}

    monkeypatch.setattr(svc, "_enqueue_chunk", fake_enqueue_chunk)

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
    svc = AmazonAdsSearchTermSyncService(MagicMock())

    class _FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 3, 13, 12, 0, 0, tzinfo=tz or UTC)

    monkeypatch.setattr(base_sync_module, "datetime", _FakeDateTime)
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
    monkeypatch.setattr(svc, "_require_refresh_token", lambda profile_id, **kwargs: "refresh-token")

    observed: dict[str, date] = {}

    async def fake_enqueue_chunk(
        *,
        profile_id,
        amazon_ads_profile_id,
        refresh_token,
        region_code,
        marketplace_code,
        date_from,
        date_to,
        ad_product,
        job_type,
        user_id,
    ):
        assert region_code == "NA"
        observed["date_from"] = date_from
        observed["date_to"] = date_to
        observed["job_type"] = job_type
        return {"run": {"id": "run-1"}, "rows_fetched": 0, "rows_loaded": 0}

    monkeypatch.setattr(svc, "_enqueue_chunk", fake_enqueue_chunk)

    result = asyncio.run(svc.run_daily_refresh(profile_id="profile-1", user_id="user-1"))

    assert result["job_type"] == "daily_refresh"
    assert observed["date_from"] == date(2026, 2, 28)
    assert observed["date_to"] == date(2026, 3, 13)


def test_run_backfill_requires_selected_ads_profile(monkeypatch):
    svc = AmazonAdsSearchTermSyncService(MagicMock())
    monkeypatch.setattr(svc, "_get_profile", lambda profile_id: {"id": profile_id, "amazon_ads_profile_id": None})

    with pytest.raises(WBRValidationError, match="amazon_ads_profile_id"):
        asyncio.run(
            svc.run_backfill(
                profile_id="profile-1",
                date_from=date(2026, 3, 1),
                date_to=date(2026, 3, 7),
                user_id="user-1",
            )
        )


def test_replace_fact_window_deletes_only_selected_ad_product():
    db = MagicMock()
    delete_query = db.table.return_value.delete.return_value
    delete_query.eq.return_value = delete_query
    delete_query.gte.return_value = delete_query
    delete_query.lte.return_value = delete_query

    svc = AmazonAdsSearchTermSyncService(db)

    svc._replace_fact_window(
        profile_id="profile-1",
        sync_run_id="run-1",
        date_from=date(2026, 3, 25),
        date_to=date(2026, 3, 26),
        ad_product="SPONSORED_PRODUCTS",
        facts=[],
    )

    db.table.assert_called_once_with("search_term_daily_facts")
    delete_query.eq.assert_any_call("profile_id", "profile-1")
    delete_query.eq.assert_any_call("ad_product", "SPONSORED_PRODUCTS")
    delete_query.gte.assert_called_once_with("report_date", "2026-03-25")
    delete_query.lte.assert_called_once_with("report_date", "2026-03-26")
    delete_query.execute.assert_called_once()


def test_finalize_completed_run_scopes_fact_replacement_to_requested_ad_product(monkeypatch):
    svc = AmazonAdsSearchTermSyncService(MagicMock())

    async def fake_download_report_rows(location: str):
        assert location == "https://example.test/report.json"
        return [
            {
                "date": "2026-03-25",
                "campaignName": "Screen Shine - 90ct Wipes | SPA | Los. | Rsrch",
                "searchTerm": "screen cleaner",
                "impressions": "100",
                "clicks": "10",
                "cost": "12.34",
                "purchases7d": "2",
                "sales7d": "44.56",
            }
        ]

    monkeypatch.setattr(svc, "_download_report_rows", fake_download_report_rows)

    observed: dict[str, object] = {}

    def fake_replace_fact_window(*, profile_id, sync_run_id, date_from, date_to, ad_product, facts):
        observed["profile_id"] = profile_id
        observed["sync_run_id"] = sync_run_id
        observed["date_from"] = date_from
        observed["date_to"] = date_to
        observed["ad_product"] = ad_product
        observed["facts"] = facts

    monkeypatch.setattr(svc, "_replace_fact_window", fake_replace_fact_window)
    monkeypatch.setattr(svc, "_update_sync_run_request_meta", lambda **kwargs: None)
    monkeypatch.setattr(
        svc,
        "_finalize_sync_run",
        lambda **kwargs: {"id": kwargs["run_id"], "status": kwargs["status"], "rows_loaded": kwargs["rows_loaded"]},
    )

    run = {
        "id": "run-1",
        "profile_id": "profile-1",
        "date_from": "2026-03-25",
        "date_to": "2026-03-26",
    }
    request_meta = {"marketplace_code": "US", "ad_product": "SPONSORED_BRANDS"}
    report_jobs = [
        {
            "location": "https://example.test/report.json",
            "campaign_type": "sponsored_brands",
            "ad_product": "SPONSORED_BRANDS",
            "report_type_id": "sbSearchTerm",
        }
    ]

    result = asyncio.run(svc._finalize_completed_run(run, request_meta, report_jobs))

    assert result["status"] == "success"
    assert observed["profile_id"] == "profile-1"
    assert observed["sync_run_id"] == "run-1"
    assert observed["date_from"] == date(2026, 3, 25)
    assert observed["date_to"] == date(2026, 3, 26)
    assert observed["ad_product"] == "SPONSORED_BRANDS"
    facts = observed["facts"]
    assert isinstance(facts, list)
    assert len(facts) == 1
    assert facts[0].ad_product == "SPONSORED_BRANDS"


class _FakeSearchTermSyncService:
    def __init__(self):
        self.last_backfill = None
        self.last_daily_refresh = None

    async def run_backfill(self, *, profile_id, date_from, date_to, ad_product=None, chunk_days, user_id):
        self.last_backfill = {
            "profile_id": profile_id,
            "date_from": date_from,
            "date_to": date_to,
            "ad_product": ad_product,
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

    async def run_daily_refresh(self, *, profile_id, ad_product=None, user_id=None):
        self.last_daily_refresh = {"profile_id": profile_id, "ad_product": ad_product, "user_id": user_id}
        return {
            "profile_id": profile_id,
            "job_type": "daily_refresh",
            "date_from": "2026-03-01",
            "date_to": "2026-03-13",
            "chunk": {"run": {"id": "run-1"}, "rows_fetched": 0, "rows_loaded": 0},
        }


def test_search_term_backfill_endpoint_calls_service(monkeypatch):
    fake_svc = _FakeSearchTermSyncService()
    monkeypatch.setattr(wbr, "_get_amazon_ads_search_term_sync_service", lambda: fake_svc)
    app.dependency_overrides[wbr.require_admin_user] = _override_admin

    try:
        with TestClient(app) as client:
            resp = client.post(
                "/admin/wbr/profiles/prof-1/sync-runs/search-terms/backfill",
                json={"date_from": "2026-03-01", "date_to": "2026-03-15", "chunk_days": 7},
            )
        assert resp.status_code == 200
        assert fake_svc.last_backfill is not None
        assert fake_svc.last_backfill["profile_id"] == "prof-1"
        assert fake_svc.last_backfill["chunk_days"] == 7
        assert fake_svc.last_backfill["user_id"] == "user-123"
    finally:
        app.dependency_overrides.pop(wbr.require_admin_user, None)


def test_search_term_daily_refresh_endpoint_calls_service(monkeypatch):
    fake_svc = _FakeSearchTermSyncService()
    monkeypatch.setattr(wbr, "_get_amazon_ads_search_term_sync_service", lambda: fake_svc)
    app.dependency_overrides[wbr.require_admin_user] = _override_admin

    try:
        with TestClient(app) as client:
            resp = client.post("/admin/wbr/profiles/prof-1/sync-runs/search-terms/daily-refresh")
        assert resp.status_code == 200
        assert fake_svc.last_daily_refresh is not None
        assert fake_svc.last_daily_refresh["profile_id"] == "prof-1"
        assert fake_svc.last_daily_refresh["user_id"] == "user-123"
    finally:
        app.dependency_overrides.pop(wbr.require_admin_user, None)
