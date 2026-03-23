from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
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
    monkeypatch.setattr(svc, "_require_refresh_token", lambda profile_id, **kwargs: "refresh-token")

    calls: list[tuple[date, date, str]] = []

    async def fake_enqueue_chunk(*, profile_id, amazon_ads_profile_id, refresh_token, marketplace_code, date_from, date_to, job_type, user_id):
        calls.append((date_from, date_to, job_type))
        return {
            "run": {"id": f"{date_from.isoformat()}-{date_to.isoformat()}"},
            "rows_fetched": 0,
            "rows_loaded": 0,
        }

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


def test_run_backfill_rejects_future_end_date(monkeypatch):
    svc = AmazonAdsSyncService(MagicMock())

    class _FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 3, 13, 12, 0, 0, tzinfo=tz or UTC)

    monkeypatch.setattr(sync_module, "datetime", _FakeDateTime)

    with pytest.raises(WBRValidationError, match="less than or equal to today"):
        asyncio.run(
            svc.run_backfill(
                profile_id="profile-1",
                date_from=date(2026, 3, 1),
                date_to=date(2026, 3, 15),
                chunk_days=7,
                user_id="user-1",
            )
        )


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
    monkeypatch.setattr(svc, "_require_refresh_token", lambda profile_id, **kwargs: "refresh-token")

    observed: dict[str, date] = {}

    async def fake_enqueue_chunk(*, profile_id, amazon_ads_profile_id, refresh_token, marketplace_code, date_from, date_to, job_type, user_id):
        observed["date_from"] = date_from
        observed["date_to"] = date_to
        observed["job_type"] = job_type
        return {"run": {"id": "run-1"}, "rows_fetched": 0, "rows_loaded": 0}

    monkeypatch.setattr(svc, "_enqueue_chunk", fake_enqueue_chunk)

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


def test_process_pending_runs_polls_due_jobs_and_updates_request_meta(monkeypatch):
    svc = AmazonAdsSyncService(MagicMock())
    now = datetime(2026, 3, 14, 14, 0, tzinfo=UTC)
    run = {
        "id": "run-1",
        "profile_id": "profile-1",
        "status": "running",
        "request_meta": {
            "async_reports_v1": True,
            "amazon_ads_profile_id": "ads-prof-1",
            "report_jobs": [
                {
                    "report_id": "rep-1",
                    "status": "pending",
                    "poll_attempts": 0,
                    "next_poll_at": (now - timedelta(seconds=1)).isoformat(),
                    "campaign_type": "sponsored_products",
                }
            ],
        },
    }

    monkeypatch.setattr(svc, "_list_running_sync_runs", lambda limit=20: [run])
    monkeypatch.setattr(sync_module, "datetime", type("_FakeDateTime", (datetime,), {"now": classmethod(lambda cls, tz=None: now)}))
    monkeypatch.setattr(svc, "_require_refresh_token", lambda profile_id, **kwargs: "refresh-token")

    async def fake_refresh_access_token(refresh_token):
        return "access-token"

    async def fake_get_report_status_once(*, access_token, amazon_ads_profile_id, report_id):
        assert access_token == "access-token"
        assert amazon_ads_profile_id == "ads-prof-1"
        assert report_id == "rep-1"
        return sync_module.AmazonAdsReportStatus(report_id=report_id, status="IN_PROGRESS", location=None)

    updates: list[dict[str, object]] = []
    monkeypatch.setattr(sync_module, "refresh_access_token", fake_refresh_access_token)
    monkeypatch.setattr(svc, "_get_report_status_once", fake_get_report_status_once)
    monkeypatch.setattr(
        svc,
        "_update_sync_run_request_meta",
        lambda *, run_id, request_meta: updates.append({"run_id": run_id, "request_meta": request_meta}),
    )

    result = asyncio.run(svc.process_pending_runs())

    assert result["runs_processed"] == 1
    assert updates
    updated_jobs = updates[0]["request_meta"]["report_jobs"]
    assert updated_jobs[0]["status"] == "processing"
    assert updated_jobs[0]["poll_attempts"] == 1


def test_process_pending_runs_finalizes_completed_run(monkeypatch):
    svc = AmazonAdsSyncService(MagicMock())
    run = {
        "id": "run-1",
        "profile_id": "profile-1",
        "date_from": "2026-03-01",
        "date_to": "2026-03-14",
        "status": "running",
        "request_meta": {
            "async_reports_v1": True,
            "marketplace_code": "US",
            "report_jobs": [
                {
                    "report_id": "rep-1",
                    "status": "completed",
                    "location": "https://download.example/report-1",
                    "campaign_type": "sponsored_products",
                    "ad_product": "SPONSORED_PRODUCTS",
                    "report_type_id": "spCampaigns",
                }
            ],
        },
    }

    monkeypatch.setattr(svc, "_list_running_sync_runs", lambda limit=20: [run])

    async def fake_finalize_completed_run(run_arg, request_meta_arg, report_jobs_arg):
        assert run_arg["id"] == "run-1"
        assert request_meta_arg["marketplace_code"] == "US"
        assert report_jobs_arg[0]["report_id"] == "rep-1"
        return {"run_id": "run-1", "status": "success", "rows_fetched": 10, "rows_loaded": 3}

    monkeypatch.setattr(svc, "_finalize_completed_run", fake_finalize_completed_run)

    result = asyncio.run(svc.process_pending_runs())

    assert result["runs_processed"] == 1
    assert result["results"][0]["status"] == "success"


def test_refresh_snapshot_after_ads_finalize_creates_snapshot_and_records_meta(monkeypatch):
    svc = AmazonAdsSyncService(MagicMock())
    updates: list[dict[str, object]] = []

    class _FakeSnapshotService:
        def __init__(self, db):
            self.db = db

        def create_snapshot(self, profile_id, *, snapshot_kind, created_by):
            assert profile_id == "profile-1"
            assert snapshot_kind == "manual"
            assert created_by == "user-1"
            return {"id": "snap-1", "week_ending": "2026-03-15"}

    monkeypatch.setattr(sync_module, "WBRSnapshotService", _FakeSnapshotService)
    monkeypatch.setattr(
        svc,
        "_update_sync_run_request_meta",
        lambda *, run_id, request_meta: updates.append({"run_id": run_id, "request_meta": request_meta}),
    )

    result = svc._refresh_snapshot_after_ads_finalize(
        profile_id="profile-1",
        run_id="run-1",
        user_id="user-1",
    )

    assert result == {"status": "success", "snapshot_id": "snap-1", "week_ending": "2026-03-15"}
    assert updates == [
        {
            "run_id": "run-1",
            "request_meta": {
                "snapshot_refresh": {
                    "status": "success",
                    "snapshot_id": "snap-1",
                    "week_ending": "2026-03-15",
                }
            },
        }
    ]


def test_process_pending_runs_marks_single_run_error_and_continues(monkeypatch):
    svc = AmazonAdsSyncService(MagicMock())
    run = {
        "id": "run-1",
        "profile_id": "profile-1",
        "status": "running",
        "rows_fetched": 0,
        "rows_loaded": 0,
        "request_meta": {
            "async_reports_v1": True,
            "report_jobs": [
                {
                    "report_id": "rep-1",
                    "status": "processing",
                    "poll_attempts": 1,
                    "next_poll_at": datetime(2026, 3, 14, 14, 5, tzinfo=UTC).isoformat(),
                }
            ],
        },
    }

    monkeypatch.setattr(svc, "_list_running_sync_runs", lambda limit=20: [run])

    async def fake_process_pending_run(_run):
        raise WBRValidationError("boom")

    updates: list[dict[str, object]] = []

    monkeypatch.setattr(svc, "_process_pending_run", fake_process_pending_run)
    monkeypatch.setattr(
        svc,
        "_update_sync_run_request_meta",
        lambda *, run_id, request_meta: updates.append({"run_id": run_id, "request_meta": request_meta}),
    )
    monkeypatch.setattr(
        svc,
        "_finalize_sync_run",
        lambda *, run_id, status, rows_fetched, rows_loaded, error_message: {
            "id": run_id,
            "status": status,
            "rows_fetched": rows_fetched,
            "rows_loaded": rows_loaded,
            "error_message": error_message,
        },
    )

    result = asyncio.run(svc.process_pending_runs())

    assert result["runs_processed"] == 1
    assert result["results"][0]["status"] == "error"
    assert result["results"][0]["run"]["error_message"] == "boom"
    assert updates
    assert updates[0]["request_meta"]["last_worker_error"] == "boom"
    assert updates[0]["request_meta"]["report_progress"]["phase"] == "failed"


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
            "chunk": {"run": {"id": "run-1"}, "rows_fetched": 0, "rows_loaded": 0},
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


# ---------------------------------------------------------------------------
# Tests: _require_refresh_token shared-first lookup
# ---------------------------------------------------------------------------


class _MultiTableFakeSupabase:
    """Stub supporting table-specific rows for _require_refresh_token tests."""

    def __init__(self, tables: dict[str, list[dict]] | None = None):
        self._tables = {name: list(rows) for name, rows in (tables or {}).items()}

    def table(self, name: str):
        return _MultiTableFakeTable(self._tables.get(name, []))


class _MultiTableFakeTable:
    def __init__(self, rows: list[dict]):
        self._rows = rows
        self._filters: dict[str, object] = {}

    def select(self, *args, **kwargs):
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def limit(self, n):
        return self

    def execute(self):
        filtered = self._rows
        for col, val in self._filters.items():
            filtered = [row for row in filtered if row.get(col) == val]
        return type("Resp", (), {"data": filtered})()


class TestRequireRefreshTokenSharedFirst:
    def test_prefers_shared_token_when_present(self):
        db = _MultiTableFakeSupabase(
            {
                "wbr_profiles": [
                    {"id": "prof-1", "client_id": "client-1", "amazon_ads_profile_id": "ads-1"},
                ],
                "report_api_connections": [
                    {
                        "client_id": "client-1",
                        "provider": "amazon_ads",
                        "connection_status": "connected",
                        "refresh_token": "shared-refresh-token",
                    },
                ],
                "wbr_amazon_ads_connections": [
                    {"profile_id": "prof-1", "amazon_ads_refresh_token": "legacy-refresh-token"},
                ],
            }
        )
        svc = AmazonAdsSyncService(db)
        token = svc._require_refresh_token("prof-1")
        assert token == "shared-refresh-token"

    def test_falls_back_to_legacy_when_shared_missing(self):
        db = _MultiTableFakeSupabase(
            {
                "wbr_profiles": [
                    {"id": "prof-1", "client_id": "client-1", "amazon_ads_profile_id": "ads-1"},
                ],
                "report_api_connections": [],
                "wbr_amazon_ads_connections": [
                    {"profile_id": "prof-1", "amazon_ads_refresh_token": "legacy-refresh-token"},
                ],
            }
        )
        svc = AmazonAdsSyncService(db)
        token = svc._require_refresh_token("prof-1")
        assert token == "legacy-refresh-token"

    def test_falls_back_to_legacy_when_shared_token_empty(self):
        db = _MultiTableFakeSupabase(
            {
                "wbr_profiles": [
                    {"id": "prof-1", "client_id": "client-1", "amazon_ads_profile_id": "ads-1"},
                ],
                "report_api_connections": [
                    {
                        "client_id": "client-1",
                        "provider": "amazon_ads",
                        "connection_status": "connected",
                        "refresh_token": "",
                    },
                ],
                "wbr_amazon_ads_connections": [
                    {"profile_id": "prof-1", "amazon_ads_refresh_token": "legacy-refresh-token"},
                ],
            }
        )
        svc = AmazonAdsSyncService(db)
        token = svc._require_refresh_token("prof-1")
        assert token == "legacy-refresh-token"

    def test_falls_back_to_legacy_when_shared_connection_not_healthy(self):
        db = _MultiTableFakeSupabase(
            {
                "wbr_profiles": [
                    {"id": "prof-1", "client_id": "client-1", "amazon_ads_profile_id": "ads-1"},
                ],
                "report_api_connections": [
                    {
                        "client_id": "client-1",
                        "provider": "amazon_ads",
                        "connection_status": "error",
                        "refresh_token": "shared-refresh-token",
                    },
                ],
                "wbr_amazon_ads_connections": [
                    {"profile_id": "prof-1", "amazon_ads_refresh_token": "legacy-refresh-token"},
                ],
            }
        )
        svc = AmazonAdsSyncService(db)
        token = svc._require_refresh_token("prof-1")
        assert token == "legacy-refresh-token"

    def test_raises_when_neither_has_token(self):
        db = _MultiTableFakeSupabase(
            {
                "wbr_profiles": [
                    {"id": "prof-1", "client_id": "client-1", "amazon_ads_profile_id": "ads-1"},
                ],
                "report_api_connections": [],
                "wbr_amazon_ads_connections": [],
            }
        )
        svc = AmazonAdsSyncService(db)
        with pytest.raises(WBRValidationError, match="Connect first"):
            svc._require_refresh_token("prof-1")
