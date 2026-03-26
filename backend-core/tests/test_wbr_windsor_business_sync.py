from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

import app.services.wbr.windsor_business_sync as sync_module
from app.services.wbr.windsor_business_sync import WindsorBusinessSyncService


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeConflictTable:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self._filters: list[tuple[str, Any]] = []
        self._update_payload: dict[str, Any] | None = None
        self._insert_payload: dict[str, Any] | None = None

    def select(self, _fields: str):
        return self

    def eq(self, field: str, value: Any):
        self._filters.append((field, value))
        return self

    def update(self, payload: dict[str, Any]):
        self._update_payload = payload
        return self

    def insert(self, payload: dict[str, Any]):
        self._insert_payload = payload
        return self

    def execute(self):
        filtered = [
            row for row in self._rows
            if all(row.get(field) == value for field, value in self._filters)
        ]
        if self._update_payload is not None:
            for row in filtered:
                row.update(self._update_payload)
            return _FakeResponse([dict(row) for row in filtered])
        if self._insert_payload is not None:
            inserted = dict(self._insert_payload)
            inserted.setdefault("id", f"row-{len(self._rows) + 1}")
            self._rows.append(inserted)
            return _FakeResponse([dict(inserted)])
        return _FakeResponse([dict(row) for row in filtered])


class _FakeConflictDB:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows or []

    def table(self, name: str):
        if name != "wbr_business_parent_asin_conflicts":
            raise AssertionError(f"Unexpected table access: {name}")
        return _FakeConflictTable(self.rows)


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


def test_aggregate_rows_flags_parent_asin_conflict_without_changing_sums():
    svc = WindsorBusinessSyncService(MagicMock())

    facts = svc._aggregate_rows(
        [
            {
                "account_id": "ACC-US",
                "date": "2026-02-05",
                "sales_and_traffic_report_by_date__childasin": "B0C6TX3MMQ",
                "sales_and_traffic_report_by_date__parentasin": "B0GM33T73K",
                "sales_and_traffic_report_by_date__trafficbyasin_pageviews": "83",
                "sales_and_traffic_report_by_date__salesbyasin_unitsordered": "0",
                "sales_and_traffic_report_by_date__salesbyasin_orderedproductsales_amount": "0",
                "sales_and_traffic_report_by_date__salesbyasin_orderedproductsales_currencycode": "USD",
            },
            {
                "account_id": "ACC-US",
                "date": "2026-02-05",
                "sales_and_traffic_report_by_date__childasin": "B0C6TX3MMQ",
                "sales_and_traffic_report_by_date__parentasin": "B0C89H78GJ",
                "sales_and_traffic_report_by_date__trafficbyasin_pageviews": "0",
                "sales_and_traffic_report_by_date__salesbyasin_unitsordered": "1",
                "sales_and_traffic_report_by_date__salesbyasin_orderedproductsales_amount": "17.99",
                "sales_and_traffic_report_by_date__salesbyasin_orderedproductsales_currencycode": "USD",
            },
        ],
        expected_account_id="ACC-US",
    )

    assert len(facts) == 1
    assert facts[0].page_views == 83
    assert facts[0].unit_sales == 1
    assert str(facts[0].sales) == "17.99"
    assert facts[0].parent_asin == "B0GM33T73K"
    assert facts[0].source_row_count == 2
    assert facts[0].source_payload["parent_asin_conflict"] is True
    assert facts[0].source_payload["distinct_parent_asins"] == ["B0C89H78GJ", "B0GM33T73K"]


def test_record_parent_asin_conflicts_tracks_first_last_and_overlap_days(monkeypatch):
    db = _FakeConflictDB(
        rows=[
            {
                "id": "existing-1",
                "profile_id": "profile-1",
                "sync_run_id": "run-old",
                "report_date": "2026-02-05",
                "child_asin": "B0C6TX3MMQ",
                "stored_parent_asin": "B0GM33T73K",
                "distinct_parent_asins": ["B0C89H78GJ", "B0GM33T73K"],
                "source_row_count": 2,
                "first_detected_date": "2026-02-05",
                "last_detected_date": "2026-02-05",
                "overlap_day_count": 1,
                "source_payload": {"parent_asin_conflict": True},
                "created_at": "2026-03-26T10:00:00+00:00",
                "updated_at": "2026-03-26T10:00:00+00:00",
            }
        ]
    )
    svc = WindsorBusinessSyncService(db)

    class _FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 3, 26, 6, 30, 0, tzinfo=tz or UTC)

    monkeypatch.setattr(sync_module, "datetime", _FakeDateTime)

    svc._record_parent_asin_conflicts(
        profile_id="profile-1",
        sync_run_id="run-new",
        conflicts=[
            sync_module.ParentAsinConflict(
                report_date=date(2026, 2, 6),
                child_asin="B0C6TX3MMQ",
                stored_parent_asin="B0GM33T73K",
                distinct_parent_asins=["B0C89H78GJ", "B0GM33T73K"],
                source_row_count=3,
                source_payload={"parent_asin_conflict": True, "distinct_parent_asins": ["B0C89H78GJ", "B0GM33T73K"]},
            )
        ],
    )

    assert len(db.rows) == 2
    by_date = {row["report_date"]: row for row in db.rows}
    assert by_date["2026-02-05"]["first_detected_date"] == "2026-02-05"
    assert by_date["2026-02-05"]["last_detected_date"] == "2026-02-06"
    assert by_date["2026-02-05"]["overlap_day_count"] == 2
    assert by_date["2026-02-06"]["first_detected_date"] == "2026-02-05"
    assert by_date["2026-02-06"]["last_detected_date"] == "2026-02-06"
    assert by_date["2026-02-06"]["overlap_day_count"] == 2
    assert by_date["2026-02-06"]["source_row_count"] == 3


def test_run_chunk_records_parent_conflict_summary_without_breaking_fact_load(monkeypatch):
    svc = WindsorBusinessSyncService(MagicMock())
    conflict_rows = [
        {
            "account_id": "ACC-US",
            "date": "2026-02-05",
            "sales_and_traffic_report_by_date__childasin": "B0C6TX3MMQ",
            "sales_and_traffic_report_by_date__parentasin": "B0GM33T73K",
            "sales_and_traffic_report_by_date__trafficbyasin_pageviews": "83",
            "sales_and_traffic_report_by_date__salesbyasin_unitsordered": "0",
            "sales_and_traffic_report_by_date__salesbyasin_orderedproductsales_amount": "0",
            "sales_and_traffic_report_by_date__salesbyasin_orderedproductsales_currencycode": "USD",
        },
        {
            "account_id": "ACC-US",
            "date": "2026-02-05",
            "sales_and_traffic_report_by_date__childasin": "B0C6TX3MMQ",
            "sales_and_traffic_report_by_date__parentasin": "B0C89H78GJ",
            "sales_and_traffic_report_by_date__trafficbyasin_pageviews": "0",
            "sales_and_traffic_report_by_date__salesbyasin_unitsordered": "1",
            "sales_and_traffic_report_by_date__salesbyasin_orderedproductsales_amount": "17.99",
            "sales_and_traffic_report_by_date__salesbyasin_orderedproductsales_currencycode": "USD",
        },
    ]
    updates: list[dict[str, Any]] = []
    recorded: list[dict[str, Any]] = []

    async def fake_fetch_rows(**kwargs):
        return conflict_rows

    monkeypatch.setattr(svc, "_fetch_rows", fake_fetch_rows)
    monkeypatch.setattr(svc, "_replace_fact_window", lambda **kwargs: None)
    monkeypatch.setattr(
        svc,
        "_record_parent_asin_conflicts",
        lambda **kwargs: recorded.append(kwargs),
    )
    monkeypatch.setattr(
        svc,
        "_update_sync_run_request_meta",
        lambda *, run_id, request_meta: updates.append({"run_id": run_id, "request_meta": request_meta}),
    )
    monkeypatch.setattr(
        svc,
        "_create_sync_run",
        lambda **kwargs: {"id": "run-1"},
    )
    monkeypatch.setattr(
        svc,
        "_finalize_sync_run",
        lambda **kwargs: {"id": kwargs["run_id"], "status": kwargs["status"]},
    )

    result = asyncio.run(
        svc._run_chunk(
            profile_id="profile-1",
            account_id="ACC-US",
            date_from=date(2026, 2, 5),
            date_to=date(2026, 2, 5),
            job_type="daily_refresh",
            user_id="user-1",
        )
    )

    assert result["rows_fetched"] == 2
    assert result["rows_loaded"] == 1
    assert len(recorded) == 1
    assert len(recorded[0]["conflicts"]) == 1
    assert updates == [
        {
            "run_id": "run-1",
            "request_meta": {
                "parent_asin_conflicts": {
                    "count": 1,
                    "child_asins": ["B0C6TX3MMQ"],
                }
            },
        }
    ]


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


def test_run_backfill_rejects_future_end_date(monkeypatch):
    svc = WindsorBusinessSyncService(MagicMock())

    class _FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 3, 13, 12, 0, 0, tzinfo=tz or UTC)

    monkeypatch.setattr(sync_module, "datetime", _FakeDateTime)

    with pytest.raises(sync_module.WBRValidationError, match="less than or equal to today"):
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


def test_refresh_snapshot_after_windsor_daily_refresh_defers_when_ads_finalize_is_pending(monkeypatch):
    svc = WindsorBusinessSyncService(MagicMock())
    updates: list[dict[str, object]] = []

    monkeypatch.setattr(
        svc,
        "_update_sync_run_request_meta",
        lambda *, run_id, request_meta: updates.append({"run_id": run_id, "request_meta": request_meta}),
    )

    result = svc._refresh_snapshot_after_windsor_daily_refresh(
        profile={
            "id": "profile-1",
            "ads_api_auto_sync_enabled": True,
            "amazon_ads_profile_id": "ads-prof-1",
        },
        run={"id": "run-1"},
        user_id="user-1",
    )

    assert result == {"status": "deferred", "reason": "awaiting_amazon_ads_finalize"}
    assert updates == [
        {
            "run_id": "run-1",
            "request_meta": {"snapshot_refresh": {"status": "deferred", "reason": "awaiting_amazon_ads_finalize"}},
        }
    ]


def test_refresh_snapshot_after_windsor_daily_refresh_creates_snapshot_without_ads_sync(monkeypatch):
    svc = WindsorBusinessSyncService(MagicMock())
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

    result = svc._refresh_snapshot_after_windsor_daily_refresh(
        profile={
            "id": "profile-1",
            "ads_api_auto_sync_enabled": False,
            "amazon_ads_profile_id": None,
        },
        run={"id": "run-1"},
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
