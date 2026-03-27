from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.routers import wbr


class _FakeSearchTermFactsService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def list_facts(
        self,
        profile_id: str,
        *,
        date_from=None,
        date_to=None,
        campaign_type=None,
        campaign_name_contains=None,
        search_term_contains=None,
        limit=500,
        offset=0,
    ) -> dict:
        self.calls.append({
            "profile_id": profile_id,
            "date_from": date_from,
            "date_to": date_to,
            "campaign_type": campaign_type,
            "campaign_name_contains": campaign_name_contains,
            "search_term_contains": search_term_contains,
            "limit": limit,
            "offset": offset,
        })
        return {
            "facts": [
                {
                    "id": "fact-1",
                    "report_date": "2026-03-01",
                    "campaign_type": "sponsored_products",
                    "campaign_name": "Test Campaign",
                    "campaign_name_head": "Test",
                    "ad_group_name": "Ad Group 1",
                    "search_term": "running shoes",
                    "match_type": "broad",
                    "impressions": 1000,
                    "clicks": 50,
                    "spend": "12.50",
                    "orders": 3,
                    "sales": "90.00",
                    "currency_code": "USD",
                }
            ],
            "limit": limit,
            "offset": offset,
            "has_more": False,
        }


def _override_admin():
    return {"sub": "user-123"}


def test_list_search_term_facts_basic(monkeypatch):
    fake_svc = _FakeSearchTermFactsService()
    monkeypatch.setattr(wbr, "_get_search_term_facts_service", lambda: fake_svc)
    app.dependency_overrides[wbr.require_admin_user] = _override_admin

    try:
        with TestClient(app) as client:
            response = client.get("/admin/wbr/profiles/profile-1/search-term-facts")
    finally:
        app.dependency_overrides.pop(wbr.require_admin_user, None)

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert len(data["facts"]) == 1
    assert data["facts"][0]["search_term"] == "running shoes"
    assert data["has_more"] is False
    assert fake_svc.calls[0]["profile_id"] == "profile-1"
    assert fake_svc.calls[0]["date_from"] is None
    assert fake_svc.calls[0]["limit"] == 500


def test_list_search_term_facts_with_filters(monkeypatch):
    fake_svc = _FakeSearchTermFactsService()
    monkeypatch.setattr(wbr, "_get_search_term_facts_service", lambda: fake_svc)
    app.dependency_overrides[wbr.require_admin_user] = _override_admin

    try:
        with TestClient(app) as client:
            response = client.get(
                "/admin/wbr/profiles/profile-2/search-term-facts",
                params={
                    "date_from": "2026-01-01",
                    "date_to": "2026-03-01",
                    "campaign_type": "sponsored_products",
                    "campaign_name_contains": "shoes",
                    "search_term_contains": "running",
                    "limit": 100,
                    "offset": 50,
                },
            )
    finally:
        app.dependency_overrides.pop(wbr.require_admin_user, None)

    assert response.status_code == 200
    call = fake_svc.calls[0]
    assert call["profile_id"] == "profile-2"
    assert call["date_from"] == "2026-01-01"
    assert call["date_to"] == "2026-03-01"
    assert call["campaign_type"] == "sponsored_products"
    assert call["campaign_name_contains"] == "shoes"
    assert call["search_term_contains"] == "running"
    assert call["limit"] == 100
    assert call["offset"] == 50


def test_list_search_term_facts_requires_admin(monkeypatch):
    fake_svc = _FakeSearchTermFactsService()
    monkeypatch.setattr(wbr, "_get_search_term_facts_service", lambda: fake_svc)
    # No auth override — should reject

    with TestClient(app) as client:
        response = client.get("/admin/wbr/profiles/profile-1/search-term-facts")

    assert response.status_code in (401, 403)
