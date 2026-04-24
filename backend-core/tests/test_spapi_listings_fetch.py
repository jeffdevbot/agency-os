from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from app.services.wbr.profiles import WBRValidationError
from app.services.wbr.spapi_listings_fetch import (
    REPORT_TYPE_MERCHANT_LISTINGS,
    SpApiListingsFetchService,
)


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

    def execute(self):
        rows = list(self.db.tables.get(self.name, []))
        for key, value in self.filters.items():
            rows = [row for row in rows if row.get(key) == value]
        if self.limit_value is not None:
            rows = rows[: self.limit_value]
        return _Response(rows)


class _FakeDb:
    def __init__(self, tables: dict[str, list[dict[str, Any]]]):
        self.tables = tables

    def table(self, name: str):
        return _FakeTable(self, name)


class _FakeReportsClient:
    def __init__(self, rows: list[dict[str, Any]]):
        self.rows = rows
        self.calls: list[dict[str, Any]] = []

    async def fetch_report_rows(
        self,
        report_type: str,
        *,
        marketplace_ids: list[str],
        data_start_time: datetime,
        data_end_time: datetime,
        report_options: dict[str, str] | None = None,
        format: str = "tsv",
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
        return self.rows


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
            "report_api_connections": (
                []
                if connection is None
                else [
                    {
                        "client_id": "client-1",
                        "provider": "amazon_spapi",
                        **connection,
                    }
                ]
            ),
        }
    )


def _listing_rows() -> list[dict[str, Any]]:
    return [
        {
            "asin1": "B000TEST01",
            "asin2": "B000PARENT1",
            "seller-sku": "SKU-1",
            "item-name": "Test Product",
            "price": "19.99",
            "quantity": "7",
            "status": "Active",
            "fulfillment-channel": "AMAZON_NA",
            "open-date": "2026-04-01",
            "listing-id": "LISTING-1",
        },
        {
            "asin1": "B000TEST02",
            "asin2": "B000PARENT2",
            "seller-sku": "SKU-2",
            "item-name": "Second Product",
            "price": "29.99",
            "quantity": "3",
            "status": "Active",
            "fulfillment-channel": "DEFAULT",
            "open-date": "2026-04-02",
            "listing-id": "LISTING-2",
        },
    ]


@pytest.mark.asyncio
async def test_fetch_listings_raw_returns_raw_rows() -> None:
    fake_client = _FakeReportsClient(_listing_rows())
    service = SpApiListingsFetchService(
        _base_db(connection={"refresh_token": "refresh-token", "region_code": "NA"}),
        client_factory=lambda refresh_token, region_code: fake_client,
    )

    rows = await service.fetch_listings_raw(profile_id="profile-1")

    assert rows == _listing_rows()
    assert fake_client.calls[0]["report_type"] == REPORT_TYPE_MERCHANT_LISTINGS
    assert fake_client.calls[0]["marketplace_ids"] == ["A2EUQ1WTGCTBG2"]
    assert fake_client.calls[0]["format"] == "tsv"


@pytest.mark.asyncio
async def test_fetch_listings_returns_normalized_preview() -> None:
    fake_client = _FakeReportsClient(_listing_rows())
    service = SpApiListingsFetchService(
        _base_db(connection={"refresh_token": "refresh-token", "region_code": "NA"}),
        client_factory=lambda refresh_token, region_code: fake_client,
    )

    result = await service.fetch_listings(profile_id="profile-1")

    assert result["profile_id"] == "profile-1"
    assert result["marketplace_code"] == "CA"
    assert result["marketplace_id"] == "A2EUQ1WTGCTBG2"
    assert result["rows_fetched"] == 2
    assert result["rows_parsed"] == 2
    assert result["duplicate_rows_merged"] == 0
    assert result["unmapped_columns"] == ["listing-id", "open-date"]
    assert result["sample_records"][0]["child_asin"] == "B000TEST01"
    assert result["sample_records"][0]["parent_asin"] == "B000PARENT1"
    assert result["sample_records"][0]["child_sku"] == "SKU-1"
    assert result["sample_records"][0]["child_product_name"] == "Test Product"
    assert result["sample_records"][0]["price"] == "19.99"
    assert result["sample_records"][0]["quantity"] == "7"
    assert result["sample_records"][0]["status"] == "Active"
    assert result["sample_records"][0]["fulfillment_method"] == "AMAZON_NA"
    assert result["sample_records"][0]["raw_payload"]["open-date"] == "2026-04-01"
    assert fake_client.calls[0]["report_type"] == REPORT_TYPE_MERCHANT_LISTINGS
    assert fake_client.calls[0]["marketplace_ids"] == ["A2EUQ1WTGCTBG2"]
    assert fake_client.calls[0]["format"] == "tsv"


@pytest.mark.asyncio
async def test_fetch_listings_missing_connection_raises_validation_error() -> None:
    service = SpApiListingsFetchService(_base_db())

    with pytest.raises(WBRValidationError, match="No Amazon Seller API connection"):
        await service.fetch_listings(profile_id="profile-1")


@pytest.mark.asyncio
async def test_fetch_listings_missing_marketplace_mapping_raises_validation_error() -> None:
    fake_client = _FakeReportsClient(_listing_rows())
    service = SpApiListingsFetchService(
        _base_db(
            marketplace_code="ZZ",
            connection={"refresh_token": "refresh-token", "region_code": "NA"},
        ),
        client_factory=lambda refresh_token, region_code: fake_client,
    )

    with pytest.raises(WBRValidationError, match="Marketplace ZZ is not mapped"):
        await service.fetch_listings(profile_id="profile-1")
    assert fake_client.calls == []


@pytest.mark.asyncio
async def test_fetch_listings_maps_native_asin2_to_parent_asin() -> None:
    fake_client = _FakeReportsClient(
        [
            {
                "asin1": "B000TEST01",
                "asin2": "B000PARENT1",
            }
        ]
    )
    service = SpApiListingsFetchService(
        _base_db(connection={"refresh_token": "refresh-token", "region_code": "NA"}),
        client_factory=lambda refresh_token, region_code: fake_client,
    )

    result = await service.fetch_listings(profile_id="profile-1")

    assert result["sample_records"][0]["parent_asin"] == "B000PARENT1"
