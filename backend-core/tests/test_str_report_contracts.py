"""
Tests for the STR ingestion report-contract refactor.

These tests validate the specific behaviors changed in the refactor:
  1. spSearchTerm uses groupBy=["searchTerm"], NOT "campaign"
  2. Only SP is in the active SEARCH_TERM_REPORT_DEFINITIONS (SB/SD disabled)
  3. _build_initial_report_jobs includes group_by in each job dict
  4. _report_definition_from_job reads group_by correctly (and falls back safely)
  5. AmazonAdsReportDefinition carries group_by through _create_campaign_report
  6. New keyword fields (keyword_id, keyword, keyword_type, targeting) are parsed
     and included in SearchTermDailyFact
  7. keyword_id is part of the dedup key — distinct keywords with the same
     search_term are NOT merged

No imports of app.main / app.routers here — service and dataclass only.
"""
from __future__ import annotations

import asyncio
from dataclasses import fields
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.wbr.amazon_ads_search_terms import (
    AmazonAdsSearchTermSyncService,
    SEARCH_TERM_REPORT_DEFINITIONS,
    SearchTermDailyFact,
)
from app.services.wbr.amazon_ads_sync import (
    AmazonAdsReportDefinition,
    AmazonAdsSyncService,
    AMAZON_ADS_REPORT_DEFINITIONS,
)


# ------------------------------------------------------------------
# 1 + 2 — SP-only definitions, correct groupBy
# ------------------------------------------------------------------

def test_sp_search_term_definition_uses_search_term_group_by():
    """The spSearchTerm report definition must use groupBy=["searchTerm"]."""
    sp_defs = [d for d in SEARCH_TERM_REPORT_DEFINITIONS if d.report_type_id == "spSearchTerm"]
    assert len(sp_defs) == 1, "Expected exactly one spSearchTerm definition"
    assert sp_defs[0].group_by == ["searchTerm"], (
        f"spSearchTerm must use groupBy=['searchTerm'], got {sp_defs[0].group_by!r}"
    )


def test_only_sp_is_active_in_search_term_report_definitions():
    """SB and SD are intentionally disabled — only SP should be present."""
    ad_products = {d.ad_product for d in SEARCH_TERM_REPORT_DEFINITIONS}
    assert ad_products == {"SPONSORED_PRODUCTS"}, (
        f"Expected only SPONSORED_PRODUCTS, got {ad_products!r}. "
        "SB/SD must not be re-enabled until their API contracts are verified."
    )
    report_type_ids = {d.report_type_id for d in SEARCH_TERM_REPORT_DEFINITIONS}
    assert "sbSearchTerm" not in report_type_ids, "sbSearchTerm must not be active"
    assert "sdSearchTerm" not in report_type_ids, "sdSearchTerm must not be active"


def test_campaign_report_definitions_still_use_campaign_group_by():
    """Existing WBR campaign reports must still use groupBy=["campaign"]."""
    for defn in AMAZON_ADS_REPORT_DEFINITIONS:
        assert defn.group_by == ["campaign"], (
            f"{defn.report_type_id} expected group_by=['campaign'], got {defn.group_by!r}"
        )


# ------------------------------------------------------------------
# 3 — _build_initial_report_jobs includes group_by
# ------------------------------------------------------------------

def test_build_initial_report_jobs_includes_group_by():
    svc = AmazonAdsSearchTermSyncService(MagicMock())
    jobs = svc._build_initial_report_jobs(queued_at="2026-03-27T00:00:00+00:00")

    assert len(jobs) == len(SEARCH_TERM_REPORT_DEFINITIONS)
    for job in jobs:
        assert "group_by" in job, "Each job dict must include group_by"
        assert job["group_by"] == ["searchTerm"], (
            f"SP search-term job must have group_by=['searchTerm'], got {job['group_by']!r}"
        )


def test_base_build_initial_report_jobs_includes_group_by():
    svc = AmazonAdsSyncService(MagicMock())
    jobs = svc._build_initial_report_jobs(queued_at="2026-03-27T00:00:00+00:00")

    for job in jobs:
        assert "group_by" in job, "Campaign sync job dict must include group_by"
        assert job["group_by"] == ["campaign"]


# ------------------------------------------------------------------
# 4 — _report_definition_from_job reads group_by
# ------------------------------------------------------------------

def test_report_definition_from_job_reads_group_by():
    svc = AmazonAdsSyncService(MagicMock())
    job = {
        "ad_product": "SPONSORED_PRODUCTS",
        "report_type_id": "spSearchTerm",
        "campaign_type": "sponsored_products",
        "group_by": ["searchTerm"],
        "columns": ["date", "searchTerm"],
    }
    defn = svc._report_definition_from_job(job)
    assert defn.group_by == ["searchTerm"]


def test_report_definition_from_job_falls_back_to_campaign_when_missing():
    """Old stored jobs without group_by must default to ["campaign"] for backward compat."""
    svc = AmazonAdsSyncService(MagicMock())
    job = {
        "ad_product": "SPONSORED_PRODUCTS",
        "report_type_id": "spCampaigns",
        "campaign_type": "sponsored_products",
        # no group_by key
        "columns": ["date", "campaignName"],
    }
    defn = svc._report_definition_from_job(job)
    assert defn.group_by == ["campaign"], (
        "Old job dicts without group_by must default to ['campaign'] for backward compat"
    )


# ------------------------------------------------------------------
# 5 — _create_campaign_report uses report_definition.group_by
# ------------------------------------------------------------------

def test_create_campaign_report_uses_definition_group_by(monkeypatch):
    """groupBy in the API payload must come from the definition, not a hardcoded value."""
    monkeypatch.setenv("AMAZON_ADS_CLIENT_ID", "test-client-id")
    svc = AmazonAdsSyncService(MagicMock())
    captured: list[dict] = []

    async def fake_post(url, *, json=None, headers=None):
        captured.append(json or {})
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"reportId": "r-123"}
        return mock_resp

    sp_str_definition = AmazonAdsReportDefinition(
        ad_product="SPONSORED_PRODUCTS",
        report_type_id="spSearchTerm",
        campaign_type="sponsored_products",
        group_by=["searchTerm"],
        columns=["date", "searchTerm"],
    )

    from datetime import date

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = fake_post
        mock_client_cls.return_value = mock_client

        asyncio.run(
            svc._create_campaign_report(
                access_token="token",
                amazon_ads_profile_id="ads-123",
                date_from=date(2026, 3, 1),
                date_to=date(2026, 3, 7),
                report_definition=sp_str_definition,
            )
        )

    assert len(captured) == 1
    config = captured[0]["configuration"]
    assert config["groupBy"] == ["searchTerm"], (
        f"Expected groupBy=['searchTerm'] for spSearchTerm, got {config['groupBy']!r}"
    )
    assert config["reportTypeId"] == "spSearchTerm"


def test_create_campaign_report_uses_campaign_group_by_for_campaign_reports(monkeypatch):
    """Campaign reports must still send groupBy=["campaign"]."""
    monkeypatch.setenv("AMAZON_ADS_CLIENT_ID", "test-client-id")
    svc = AmazonAdsSyncService(MagicMock())
    captured: list[dict] = []

    async def fake_post(url, *, json=None, headers=None):
        captured.append(json or {})
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"reportId": "r-456"}
        return mock_resp

    campaign_definition = AmazonAdsReportDefinition(
        ad_product="SPONSORED_PRODUCTS",
        report_type_id="spCampaigns",
        campaign_type="sponsored_products",
        group_by=["campaign"],
        columns=["date", "campaignId"],
    )

    from datetime import date

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = fake_post
        mock_client_cls.return_value = mock_client

        asyncio.run(
            svc._create_campaign_report(
                access_token="token",
                amazon_ads_profile_id="ads-123",
                date_from=date(2026, 3, 1),
                date_to=date(2026, 3, 7),
                report_definition=campaign_definition,
            )
        )

    assert captured[0]["configuration"]["groupBy"] == ["campaign"]


# ------------------------------------------------------------------
# 6 — New keyword fields are parsed from report rows
# ------------------------------------------------------------------

def test_aggregate_rows_parses_keyword_fields():
    svc = AmazonAdsSearchTermSyncService(MagicMock())

    facts = svc._aggregate_rows(
        [
            {
                "date": "2026-03-01",
                "campaignName": "Test Campaign",
                "adGroupId": "ag-1",
                "adGroupName": "AG 1",
                "keywordId": "kw-999",
                "keyword": "running shoes",
                "keywordType": "EXACT",
                "targeting": "keyword:running shoes:EXACT",
                "searchTerm": "best running shoes",
                "matchType": "EXACT",
                "impressions": "200",
                "clicks": "5",
                "cost": "3.00",
                "purchases7d": "1",
                "sales7d": "30.00",
                "__campaign_type": "sponsored_products",
            }
        ],
        marketplace_code="US",
    )

    assert len(facts) == 1
    f = facts[0]
    assert f.keyword_id == "kw-999"
    assert f.keyword == "running shoes"
    assert f.keyword_type == "EXACT"
    assert f.targeting == "keyword:running shoes:EXACT"
    assert f.search_term == "best running shoes"


def test_aggregate_rows_keyword_fields_nullable_for_auto_targeting():
    """Auto-targeting rows have no keyword — all keyword fields should be None."""
    svc = AmazonAdsSearchTermSyncService(MagicMock())

    facts = svc._aggregate_rows(
        [
            {
                "date": "2026-03-01",
                "campaignName": "Auto Campaign",
                "searchTerm": "wireless earbuds",
                "matchType": "AUTO",
                "impressions": "50",
                "clicks": "2",
                "cost": "1.00",
                "purchases7d": "0",
                "sales7d": "0",
                "__campaign_type": "sponsored_products",
            }
        ],
        marketplace_code="US",
    )

    assert len(facts) == 1
    f = facts[0]
    assert f.keyword_id is None
    assert f.keyword is None
    assert f.keyword_type is None
    assert f.targeting is None


# ------------------------------------------------------------------
# 7 — keyword_id is part of the dedup key
# ------------------------------------------------------------------

def test_aggregate_rows_same_search_term_different_keyword_id_not_merged():
    """
    Two rows with the same search_term but different keyword_id must NOT be merged.
    This is the correct Amazon spSearchTerm semantics: the same shopper query can
    trigger multiple distinct keywords in the same campaign.
    """
    svc = AmazonAdsSearchTermSyncService(MagicMock())

    facts = svc._aggregate_rows(
        [
            {
                "date": "2026-03-01",
                "campaignName": "Brand Campaign",
                "adGroupName": "AG 1",
                "keywordId": "kw-1",
                "keyword": "running shoe",
                "keywordType": "BROAD",
                "searchTerm": "best running shoes",
                "matchType": "BROAD",
                "impressions": "100",
                "clicks": "5",
                "cost": "2.00",
                "purchases7d": "1",
                "sales7d": "30.00",
                "__campaign_type": "sponsored_products",
            },
            {
                "date": "2026-03-01",
                "campaignName": "Brand Campaign",
                "adGroupName": "AG 1",
                "keywordId": "kw-2",
                "keyword": "running shoes",
                "keywordType": "PHRASE",
                "searchTerm": "best running shoes",
                "matchType": "PHRASE",
                "impressions": "80",
                "clicks": "3",
                "cost": "1.50",
                "purchases7d": "0",
                "sales7d": "0",
                "__campaign_type": "sponsored_products",
            },
        ],
        marketplace_code="US",
    )

    assert len(facts) == 2, (
        "Rows with different keyword_id must be stored as distinct facts"
    )
    keyword_ids = {f.keyword_id for f in facts}
    assert keyword_ids == {"kw-1", "kw-2"}


def test_aggregate_rows_same_keyword_id_same_search_term_does_merge():
    """Duplicate rows with identical keyword_id + search_term should still merge (dedup)."""
    svc = AmazonAdsSearchTermSyncService(MagicMock())

    facts = svc._aggregate_rows(
        [
            {
                "date": "2026-03-01",
                "campaignName": "Brand Campaign",
                "adGroupName": "AG 1",
                "keywordId": "kw-1",
                "keyword": "running shoe",
                "keywordType": "BROAD",
                "searchTerm": "best running shoes",
                "matchType": "BROAD",
                "impressions": "100",
                "clicks": "5",
                "cost": "2.00",
                "purchases7d": "1",
                "sales7d": "30.00",
                "__campaign_type": "sponsored_products",
            },
            {
                "date": "2026-03-01",
                "campaignName": "Brand Campaign",
                "adGroupName": "AG 1",
                "keywordId": "kw-1",
                "keyword": "running shoe",
                "keywordType": "BROAD",
                "searchTerm": "best running shoes",
                "matchType": "BROAD",
                "impressions": "20",
                "clicks": "1",
                "cost": "0.50",
                "purchases7d": "0",
                "sales7d": "0",
                "__campaign_type": "sponsored_products",
            },
        ],
        marketplace_code="US",
    )

    assert len(facts) == 1
    assert facts[0].impressions == 120
    assert facts[0].clicks == 6


# ------------------------------------------------------------------
# 8 — SearchTermDailyFact dataclass has the new fields
# ------------------------------------------------------------------

def test_search_term_daily_fact_has_keyword_fields():
    """Verify the dataclass fields exist so storage calls don't silently skip them."""
    field_names = {f.name for f in fields(SearchTermDailyFact)}
    for expected in ("keyword_id", "keyword", "keyword_type", "targeting"):
        assert expected in field_names, f"SearchTermDailyFact is missing field: {expected}"
