from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

import app.services.wbr.sync_runs as sync_runs_module
from app.services.wbr.sync_runs import WBRSyncRunService


def _chain_table(response_data: list[dict] | None = None) -> MagicMock:
    table = MagicMock()
    table.select.return_value = table
    table.eq.return_value = table
    table.in_.return_value = table
    table.order.return_value = table
    table.limit.return_value = table
    resp = MagicMock()
    resp.data = response_data if response_data is not None else []
    table.execute.return_value = resp
    return table


def _db_with_tables(**tables: MagicMock) -> MagicMock:
    db = MagicMock()
    db.table.side_effect = lambda name: tables[name]
    return db


class _FakeDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 3, 25, 12, 0, 0, tzinfo=tz or UTC)


def test_get_sync_coverage_reports_missing_and_inflight_business_ranges(monkeypatch):
    monkeypatch.setattr(sync_runs_module, "datetime", _FakeDateTime)
    db = _db_with_tables(
        wbr_profiles=_chain_table([{"id": "profile-1", "backfill_start_date": "2026-03-01"}]),
        wbr_sync_runs=_chain_table(
            [
                {"status": "success", "date_from": "2026-03-01", "date_to": "2026-03-07"},
                {"status": "running", "date_from": "2026-03-08", "date_to": "2026-03-10"},
                {"status": "success", "date_from": "2026-03-12", "date_to": "2026-03-20"},
            ]
        ),
    )
    svc = WBRSyncRunService(db)

    coverage = svc.get_sync_coverage("profile-1", source_type="windsor_business")

    assert coverage["window_start"] == "2026-03-01"
    assert coverage["window_end"] == "2026-03-25"
    assert coverage["covered_day_count"] == 16
    assert coverage["in_flight_day_count"] == 3
    assert coverage["missing_day_count"] == 6
    assert coverage["covered_ranges"] == [
        {"date_from": "2026-03-01", "date_to": "2026-03-07"},
        {"date_from": "2026-03-12", "date_to": "2026-03-20"},
    ]
    assert coverage["in_flight_ranges"] == [{"date_from": "2026-03-08", "date_to": "2026-03-10"}]
    assert coverage["missing_ranges"] == [
        {"date_from": "2026-03-11", "date_to": "2026-03-11"},
        {"date_from": "2026-03-21", "date_to": "2026-03-25"},
    ]


def test_get_sync_coverage_clips_amazon_ads_runs_to_retention_window(monkeypatch):
    monkeypatch.setattr(sync_runs_module, "datetime", _FakeDateTime)
    db = _db_with_tables(
        wbr_profiles=_chain_table([{"id": "profile-1", "backfill_start_date": "2025-01-01"}]),
        wbr_sync_runs=_chain_table(
            [
                {"status": "success", "date_from": "2026-01-01", "date_to": "2026-02-01"},
                {"status": "success", "date_from": "2026-02-05", "date_to": "2026-02-10"},
                {"status": "running", "date_from": "2026-03-20", "date_to": "2026-03-25"},
            ]
        ),
    )
    svc = WBRSyncRunService(db)

    coverage = svc.get_sync_coverage("profile-1", source_type="amazon_ads")

    assert coverage["window_start"] == "2026-01-25"
    assert coverage["window_end"] == "2026-03-25"
    assert coverage["window_label"] == "Current Amazon Ads retention window"
    assert coverage["covered_ranges"] == [
        {"date_from": "2026-01-25", "date_to": "2026-02-01"},
        {"date_from": "2026-02-05", "date_to": "2026-02-10"},
    ]
    assert coverage["in_flight_ranges"] == [{"date_from": "2026-03-20", "date_to": "2026-03-25"}]
    assert coverage["missing_ranges"] == [
        {"date_from": "2026-02-02", "date_to": "2026-02-04"},
        {"date_from": "2026-02-11", "date_to": "2026-03-19"},
    ]


def test_get_sync_coverage_rejects_unsupported_source_type():
    db = _db_with_tables(wbr_profiles=_chain_table([{"id": "profile-1"}]))
    svc = WBRSyncRunService(db)

    with pytest.raises(sync_runs_module.WBRValidationError, match="coverage source_type"):
        svc.get_sync_coverage("profile-1", source_type="windsor_returns")
