from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.routers import ngram
from app.services.ngram.native import NativeNgramCampaignSummary, NativeNgramPreflightSummary, NativeNgramTotals


class _FakeNativeNgramService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def build_summary_from_search_term_facts(
        self,
        *,
        profile_id: str,
        ad_product: str,
        date_from,
        date_to,
        respect_legacy_exclusions: bool,
    ) -> NativeNgramPreflightSummary:
        self.calls.append(
            {
                "profile_id": profile_id,
                "ad_product": ad_product,
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
                "respect_legacy_exclusions": respect_legacy_exclusions,
            }
        )
        return NativeNgramPreflightSummary(
            ad_product="SPONSORED_PRODUCTS",
            profile_id=profile_id,
            profile_display_name="Whoosh US",
            marketplace_code="US",
            date_from=date_from.isoformat(),
            date_to=date_to.isoformat(),
            raw_rows=120,
            eligible_rows=80,
            excluded_asin_rows=30,
            excluded_incomplete_rows=10,
            unique_campaigns=4,
            unique_search_terms=50,
            campaigns_included=3,
            campaigns_skipped=1,
            report_dates_present=14,
            coverage_start=date_from.isoformat(),
            coverage_end=date_to.isoformat(),
            imported_totals=NativeNgramTotals(
                impressions=1000,
                clicks=100,
                spend=55.25,
                orders=9,
                sales=320.10,
            ),
            workbook_input_totals=NativeNgramTotals(
                impressions=700,
                clicks=80,
                spend=41.10,
                orders=6,
                sales=220.00,
            ),
            campaigns=[
                NativeNgramCampaignSummary(
                    campaign_name="Screen Shine - Pro | SPM | MKW | Br.M | 2 - computer | Perf",
                    search_terms=24,
                    spend=91.5,
                )
            ],
            warnings=["1 campaign(s) will be skipped by the legacy Ex./SDI/SDV exclusions."],
        )


def _override_user():
    return {"sub": "user-123", "email": "tester@example.com"}


def test_native_summary_route_returns_summary_payload(monkeypatch):
    fake_service = _FakeNativeNgramService()
    app.dependency_overrides[ngram.require_user] = _override_user
    app.dependency_overrides[ngram._get_native_service] = lambda: fake_service

    try:
        with TestClient(app) as client:
            response = client.post(
                "/ngram/native-summary",
                json={
                    "profile_id": "profile-1",
                    "ad_product": "SPONSORED_PRODUCTS",
                    "date_from": "2026-03-01",
                    "date_to": "2026-03-14",
                    "respect_legacy_exclusions": True,
                },
            )
    finally:
        app.dependency_overrides.pop(ngram.require_user, None)
        app.dependency_overrides.pop(ngram._get_native_service, None)

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["summary"]["eligible_rows"] == 80
    assert data["summary"]["workbook_input_totals"]["clicks"] == 80
    assert data["summary"]["campaigns"] == [
        {
            "campaign_name": "Screen Shine - Pro | SPM | MKW | Br.M | 2 - computer | Perf",
            "search_terms": 24,
            "spend": 91.5,
        }
    ]
    assert data["summary"]["warnings"] == [
        "1 campaign(s) will be skipped by the legacy Ex./SDI/SDV exclusions."
    ]
    assert fake_service.calls == [
        {
            "profile_id": "profile-1",
            "ad_product": "SPONSORED_PRODUCTS",
            "date_from": "2026-03-01",
            "date_to": "2026-03-14",
            "respect_legacy_exclusions": True,
        }
    ]


def test_native_summary_route_rejects_invalid_date_range(monkeypatch):
    fake_service = _FakeNativeNgramService()
    app.dependency_overrides[ngram.require_user] = _override_user
    app.dependency_overrides[ngram._get_native_service] = lambda: fake_service

    try:
        with TestClient(app) as client:
            response = client.post(
                "/ngram/native-summary",
                json={
                    "profile_id": "profile-1",
                    "ad_product": "SPONSORED_PRODUCTS",
                    "date_from": "2026-03-14",
                    "date_to": "2026-03-01",
                    "respect_legacy_exclusions": True,
                },
            )
    finally:
        app.dependency_overrides.pop(ngram.require_user, None)
        app.dependency_overrides.pop(ngram._get_native_service, None)

    assert response.status_code == 400
    assert response.json()["detail"] == "date_from must be on or before date_to"
