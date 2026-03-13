"""Tests for WBR listings import parsing and service behavior."""

from __future__ import annotations

import io
from unittest.mock import MagicMock

import pytest
from openpyxl import Workbook

from app.services.wbr.listing_imports import ListingImportService, parse_listing_file
from app.services.wbr.profiles import WBRValidationError


def _build_workbook_bytes(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _chain_table(response_data: list[dict] | None = None) -> MagicMock:
    table = MagicMock()
    table.select.return_value = table
    table.insert.return_value = table
    table.update.return_value = table
    table.eq.return_value = table
    table.order.return_value = table
    table.limit.return_value = table
    resp = MagicMock()
    resp.data = response_data if response_data is not None else []
    table.execute.return_value = resp
    return table


def _multi_table_db(mapping: dict[str, list[MagicMock]]) -> MagicMock:
    iterators = {name: iter(tables) for name, tables in mapping.items()}

    def router(name: str) -> MagicMock:
        return next(iterators[name])

    db = MagicMock()
    db.table.side_effect = router
    return db


class TestParseListingFile:
    def test_parses_tab_delimited_all_listings_report(self):
        file_bytes = (
            "seller-sku\titem-name\tasin1\tfulfillment-channel\tzshop-category1\r\n"
            "SKU-1\tWidget A\tB012345678\tAMAZON_NA\tAccessories\r\n"
        ).encode("utf-8")

        parsed = parse_listing_file("all-listings-report.txt", file_bytes)

        assert parsed.source_type == "delimited"
        assert parsed.rows_read == 1
        assert parsed.records[0].child_asin == "B012345678"
        assert parsed.records[0].child_sku == "SKU-1"
        assert parsed.records[0].child_product_name == "Widget A"

    def test_detects_child_asin_from_product_id_fallback(self):
        file_bytes = (
            "seller-sku\tproduct-id\tproduct-id-type\titem-name\r\n"
            "SKU-1\tB012345678\tASIN\tWidget A\r\n"
        ).encode("utf-8")

        parsed = parse_listing_file("all-listings-report.txt", file_bytes)

        assert parsed.records[0].child_asin == "B012345678"

    def test_dedupes_child_asins_and_merges_non_empty_values(self):
        file_bytes = (
            "seller-sku\titem-name\tasin1\tfulfillment-channel\r\n"
            "SKU-1\t\tB012345678\t\r\n"
            "SKU-1\tWidget A\tB012345678\tAMAZON_NA\r\n"
        ).encode("utf-8")

        parsed = parse_listing_file("all-listings-report.txt", file_bytes)

        assert parsed.rows_read == 2
        assert parsed.duplicate_rows_merged == 1
        assert len(parsed.records) == 1
        assert parsed.records[0].child_product_name == "Widget A"
        assert parsed.records[0].fulfillment_method == "AMAZON_NA"

    def test_skips_total_footer_row(self):
        file_bytes = (
            "seller-sku\titem-name\tasin1\r\n"
            "SKU-1\tWidget A\tB012345678\r\n"
            "total:\t\t\r\n"
        ).encode("utf-8")

        parsed = parse_listing_file("all-listings-report.txt", file_bytes)

        assert parsed.rows_read == 1
        assert len(parsed.records) == 1

    def test_parses_workbook_with_manual_child_asin_headers(self):
        file_bytes = _build_workbook_bytes(
            [
                ["Report", "All Listings"],
                [],
                ["Child SKU", "Child Product Name", "Child ASIN", "Fulfillment Method"],
                ["SKU-1", "Widget A", "B012345678", "AMAZON_NA"],
            ]
        )

        parsed = parse_listing_file("all-listings-report.xlsx", file_bytes)

        assert parsed.source_type == "spreadsheet"
        assert parsed.header_row_index == 2
        assert parsed.records[0].child_asin == "B012345678"

    def test_parses_cp1252_tab_delimited_report(self):
        file_bytes = (
            "item-name\tseller-sku\tasin1\tfulfillment-channel\r\n"
            "WHOOSH’s Cleaner\tSKU-1\tB012345678\tAMAZON_NA\r\n"
        ).encode("cp1252")

        parsed = parse_listing_file("all-listings-report.txt", file_bytes)

        assert parsed.source_type == "delimited"
        assert parsed.rows_read == 1
        assert parsed.records[0].child_product_name == "WHOOSH’s Cleaner"


class TestListingImportService:
    def test_import_replaces_active_child_asin_snapshot(self):
        file_bytes = (
            "seller-sku\titem-name\tasin1\tfulfillment-channel\r\n"
            "SKU-1\tWidget A\tB012345678\tAMAZON_NA\r\n"
            "SKU-2\tWidget B\tB012345679\tDEFAULT\r\n"
        ).encode("utf-8")

        profile = {"id": "p1"}
        running_batch = {"id": "b1", "import_status": "running"}
        finished_batch = {"id": "b1", "import_status": "success", "rows_read": 2, "rows_loaded": 2}

        db = _multi_table_db(
            {
                "wbr_profiles": [_chain_table([profile])],
                "wbr_listing_import_batches": [
                    _chain_table([running_batch]),
                    _chain_table([finished_batch]),
                ],
                "wbr_profile_child_asins": [
                    _chain_table([]),               # deactivate old snapshot
                    _chain_table([{"id": "a1"}, {"id": "a2"}]),  # insert new snapshot
                ],
            }
        )

        svc = ListingImportService(db)
        result = svc.import_file(
            profile_id="p1",
            file_name="all-listings-report.txt",
            file_bytes=file_bytes,
            user_id="u1",
        )

        assert result["batch"]["import_status"] == "success"
        assert result["summary"]["rows_loaded"] == 2
        assert result["summary"]["duplicate_rows_merged"] == 0

    def test_rejects_unsupported_extensions(self):
        svc = ListingImportService(MagicMock())

        with pytest.raises(WBRValidationError, match="supports .txt, .tsv, .csv, .xlsx, and .xlsm"):
            svc.import_file(
                profile_id="p1",
                file_name="all-listings-report.pdf",
                file_bytes=b"pdf",
            )
