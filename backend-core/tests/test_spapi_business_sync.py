from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from app.services.wbr.profiles import WBRValidationError
from app.services.wbr.spapi_business_sync import (
    COMPARE_TABLE,
    MARKETPLACE_IDS_BY_CODE,
    REPORT_TYPE_SALES_AND_TRAFFIC,
    SpApiBusinessCompareService,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sp_api"


class _Response:
    def __init__(self, data: list[dict[str, Any]]):
        self.data = data


class _FakeTable:
    def __init__(self, db: _FakeDb, name: str):
        self.db = db
        self.name = name
        self.filters: dict[str, Any] = {}
        self.limit_value: int | None = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key: str, value: Any):
        self.filters[key] = value
        return self

    def limit(self, value: int):
        self.limit_value = value
        return self

    def upsert(self, data, **kwargs):
        self.db.upserts.append(
            {
                "table": self.name,
                "data": data,
                "kwargs": kwargs,
            }
        )
        return _PendingResponse(data if isinstance(data, list) else [data])

    def execute(self):
        rows = list(self.db.tables.get(self.name, []))
        for key, value in self.filters.items():
            rows = [row for row in rows if row.get(key) == value]
        if self.limit_value is not None:
            rows = rows[: self.limit_value]
        return _Response(rows)


class _PendingResponse:
    def __init__(self, rows: list[dict[str, Any]]):
        self.rows = rows

    def execute(self):
        return _Response(self.rows)


class _FakeDb:
    def __init__(self, tables: dict[str, list[dict[str, Any]]]):
        self.tables = tables
        self.upserts: list[dict[str, Any]] = []

    def table(self, name: str):
        return _FakeTable(self, name)


class _FakeReportsClient:
    def __init__(self, rows_by_day: dict[str, list[dict[str, Any]]]):
        self.rows_by_day = rows_by_day
        self.calls: list[dict[str, Any]] = []

    async def fetch_report_rows(
        self,
        report_type: str,
        *,
        marketplace_ids: list[str],
        data_start_time: datetime,
        data_end_time: datetime,
        report_options: dict[str, str] | None = None,
        format: str = "json",
    ) -> list[dict[str, Any]]:
        self.calls.append(
            {
                "report_type": report_type,
                "marketplace_ids": marketplace_ids,
                "data_start_time": data_start_time,
                "data_end_time": data_end_time,
                "report_options": report_options,
                "format": format,
            }
        )
        return self.rows_by_day.get(data_start_time.date().isoformat(), [])


def _base_db(
    *,
    marketplace_code: str = "CA",
    connection: dict[str, Any] | None = None,
) -> _FakeDb:
    return _FakeDb(
        {
            "wbr_profiles": [
                {
                    "id": "profile-1",
                    "client_id": "client-1",
                    "marketplace_code": marketplace_code,
                    "status": "active",
                }
            ],
            "report_api_connections": [
                connection
                if connection is not None
                else {
                    "client_id": "client-1",
                    "provider": "amazon_spapi",
                    "refresh_token": "refresh-token",
                    "region_code": "NA",
                }
            ],
        }
    )


def _fixture_day_rows() -> list[dict[str, Any]]:
    return [json.loads((FIXTURE_DIR / "business_compare_day.json").read_text())]


def _fixture_day_rows_without_currency() -> list[dict[str, Any]]:
    rows = deepcopy(_fixture_day_rows())
    for item in rows[0]["salesAndTrafficByAsin"]:
        item["salesByAsin"]["orderedProductSales"].pop("currencyCode", None)
    return rows


@pytest.mark.asyncio
async def test_run_compare_writes_three_day_window() -> None:
    fake_client = _FakeReportsClient(
        {
            "2026-01-01": _fixture_day_rows(),
            "2026-01-02": _fixture_day_rows(),
            "2026-01-03": _fixture_day_rows(),
        }
    )
    db = _base_db()
    service = SpApiBusinessCompareService(
        db,
        client_factory=lambda refresh_token, region_code: fake_client,
        create_report_spacing_s=0,
    )

    summary = await service.run_compare(
        profile_id="profile-1",
        date_from=date(2026, 1, 1),
        date_to=date(2026, 1, 3),
    )

    assert summary["rows_fetched"] == 6
    assert summary["rows_written"] == 6
    assert summary["reports_requested"] == 3
    assert len(fake_client.calls) == 3
    assert fake_client.calls[0]["report_type"] == REPORT_TYPE_SALES_AND_TRAFFIC
    assert fake_client.calls[0]["marketplace_ids"] == ["A2EUQ1WTGCTBG2"]
    assert fake_client.calls[0]["report_options"] == {
        "asinGranularity": "CHILD",
        "dateGranularity": "DAY",
    }

    assert len(db.upserts) == 1
    assert db.upserts[0]["table"] == COMPARE_TABLE
    assert db.upserts[0]["kwargs"] == {
        "on_conflict": "profile_id,report_date,child_asin"
    }
    rows = db.upserts[0]["data"]
    assert len(rows) == 6
    first = rows[0]
    assert first["profile_id"] == "profile-1"
    assert first["sync_run_id"] is None
    assert first["report_date"] == "2026-01-01"
    assert first["child_asin"] == "B000TEST01"
    assert first["parent_asin"] == "PARENT1"
    assert first["currency_code"] == "CAD"
    assert first["page_views"] == 15
    assert first["unit_sales"] == 3
    assert first["sales"] == "34.50"
    assert first["source_row_count"] == 1
    assert first["source_payload"]["childAsin"] == "B000TEST01"


@pytest.mark.asyncio
async def test_run_compare_skips_day_with_zero_asin_rows() -> None:
    fake_client = _FakeReportsClient(
        {
            "2026-01-01": _fixture_day_rows(),
            "2026-01-02": [{"salesAndTrafficByAsin": []}],
            "2026-01-03": _fixture_day_rows(),
        }
    )
    db = _base_db()
    service = SpApiBusinessCompareService(
        db,
        client_factory=lambda refresh_token, region_code: fake_client,
        create_report_spacing_s=0,
    )

    summary = await service.run_compare(
        profile_id="profile-1",
        date_from=date(2026, 1, 1),
        date_to=date(2026, 1, 3),
    )

    assert summary["rows_written"] == 4
    assert summary["reports_requested"] == 3
    assert summary["warnings"] == ["No ASIN rows returned for 2026-01-02"]
    assert len(db.upserts[0]["data"]) == 4


@pytest.mark.asyncio
async def test_unknown_marketplace_raises_before_sp_api_call() -> None:
    fake_client = _FakeReportsClient({})
    db = _base_db(marketplace_code="BR")
    service = SpApiBusinessCompareService(
        db,
        client_factory=lambda refresh_token, region_code: fake_client,
        create_report_spacing_s=0,
    )

    with pytest.raises(WBRValidationError, match="not mapped"):
        await service.run_compare(
            profile_id="profile-1",
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 1),
        )

    assert fake_client.calls == []
    assert db.upserts == []


@pytest.mark.asyncio
async def test_missing_connection_raises_clear_error() -> None:
    fake_client = _FakeReportsClient({})
    db = _base_db()
    db.tables["report_api_connections"] = []
    service = SpApiBusinessCompareService(
        db,
        client_factory=lambda refresh_token, region_code: fake_client,
        create_report_spacing_s=0,
    )

    with pytest.raises(WBRValidationError, match="No Amazon Seller API connection"):
        await service.run_compare(
            profile_id="profile-1",
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 1),
        )

    assert fake_client.calls == []


@pytest.mark.asyncio
async def test_empty_refresh_token_raises_clear_error() -> None:
    fake_client = _FakeReportsClient({})
    db = _base_db(
        connection={
            "client_id": "client-1",
            "provider": "amazon_spapi",
            "refresh_token": "",
            "region_code": "NA",
        }
    )
    service = SpApiBusinessCompareService(
        db,
        client_factory=lambda refresh_token, region_code: fake_client,
        create_report_spacing_s=0,
    )

    with pytest.raises(WBRValidationError, match="no refresh token"):
        await service.run_compare(
            profile_id="profile-1",
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 1),
        )

    assert fake_client.calls == []


def test_transform_handles_sales_and_traffic_json_shape() -> None:
    service = SpApiBusinessCompareService(_base_db(), create_report_spacing_s=0)

    facts = service._transform_report_rows(
        _fixture_day_rows(),
        report_date=date(2026, 1, 1),
        default_currency_code="CAD",
    )

    assert len(facts) == 2
    first, second = facts
    assert first.child_asin == "B000TEST01"
    assert first.parent_asin == "PARENT1"
    assert first.currency_code == "CAD"
    assert first.sales == Decimal("34.50")
    assert first.unit_sales == 3
    assert first.page_views == 15
    assert second.child_asin == "B000TEST02"
    assert second.page_views == 7


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("marketplace_code", "expected_marketplace_id", "expected_currency"),
    [
        ("CA", "A2EUQ1WTGCTBG2", "CAD"),
        ("MX", "A1AM78C64UM0Y8", "MXN"),
        ("UK", "A1F83G8C2ARO7P", "GBP"),
        ("GB", "A1F83G8C2ARO7P", "GBP"),
        ("AU", "A39IBJ37TRP1C6", "AUD"),
        ("DE", "A1PA6795UKMFR9", "EUR"),
        ("FR", "A13V1IB3VIYZZH", "EUR"),
        ("IT", "APJ6JRA9NG5V4", "EUR"),
        ("ES", "A1RKKUPIHCS9HS", "EUR"),
        ("NL", "A1805IZSGTT6HS", "EUR"),
        ("BE", "AMEN7PMS3EDWL", "EUR"),
        ("IE", "A28R8C7NBKEWEA", "EUR"),
        ("SE", "A2NODRKZP88ZB9", "SEK"),
        ("PL", "A1C3SOZRARQ6R3", "PLN"),
    ],
)
async def test_missing_sp_api_currency_falls_back_to_marketplace_currency(
    marketplace_code: str,
    expected_marketplace_id: str,
    expected_currency: str,
) -> None:
    fake_client = _FakeReportsClient({"2026-01-01": _fixture_day_rows_without_currency()})
    db = _base_db(marketplace_code=marketplace_code)
    service = SpApiBusinessCompareService(
        db,
        client_factory=lambda refresh_token, region_code: fake_client,
        create_report_spacing_s=0,
    )

    summary = await service.run_compare(
        profile_id="profile-1",
        date_from=date(2026, 1, 1),
        date_to=date(2026, 1, 1),
    )

    assert summary["rows_written"] == 2
    assert fake_client.calls[0]["marketplace_ids"] == [expected_marketplace_id]
    assert all(row["currency_code"] == expected_currency for row in db.upserts[0]["data"])


def test_expected_new_marketplace_codes_are_mapped() -> None:
    for marketplace_code in ("UK", "GB", "AU", "DE", "FR", "IT", "ES", "NL", "BE", "IE", "SE", "PL"):
        assert marketplace_code in MARKETPLACE_IDS_BY_CODE
