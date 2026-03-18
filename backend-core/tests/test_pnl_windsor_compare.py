"""Tests for compare-only Windsor settlement analysis."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.pnl.profiles import PNLValidationError
from app.services.pnl.windsor_compare import (
    FIELD_AMOUNT,
    FIELD_AMOUNT_DESCRIPTION,
    FIELD_AMOUNT_TYPE,
    FIELD_MARKETPLACE_NAME,
    FIELD_TRANSACTION_TYPE,
    WindsorSettlementCompareService,
    _classify_windsor_row,
)


def _chain_table(response_data: list[dict] | None = None) -> MagicMock:
    table = MagicMock()
    table.select.return_value = table
    table.eq.return_value = table
    table.order.return_value = table
    table.limit.return_value = table
    table.in_.return_value = table
    resp = MagicMock()
    resp.data = response_data if response_data is not None else []
    table.execute.return_value = resp
    return table


def _db_with_tables(**tables: MagicMock) -> MagicMock:
    db = MagicMock()
    db.table.side_effect = lambda name: tables.get(name, _chain_table())
    return db


class TestClassifyWindsorRow:
    def test_maps_core_buckets(self):
        assert _classify_windsor_row(
            {
                FIELD_TRANSACTION_TYPE: "Order",
                FIELD_AMOUNT_TYPE: "ItemPrice",
                FIELD_AMOUNT_DESCRIPTION: "Principal",
            },
            Decimal("10.00"),
        ).bucket == "product_sales"
        assert _classify_windsor_row(
            {
                FIELD_TRANSACTION_TYPE: "Refund",
                FIELD_AMOUNT_TYPE: "ItemPrice",
                FIELD_AMOUNT_DESCRIPTION: "Shipping",
            },
            Decimal("-2.00"),
        ).bucket == "shipping_credit_refunds"
        assert _classify_windsor_row(
            {
                FIELD_TRANSACTION_TYPE: "ServiceFee",
                FIELD_AMOUNT_TYPE: "Cost of Advertising",
                FIELD_AMOUNT_DESCRIPTION: "TransactionTotalAmount",
            },
            Decimal("-5.00"),
        ).bucket == "advertising"

    def test_ignores_sales_tax_and_marks_unknown_as_unmapped(self):
        ignored = _classify_windsor_row(
            {
                FIELD_TRANSACTION_TYPE: "Order",
                FIELD_AMOUNT_TYPE: "ItemPrice",
                FIELD_AMOUNT_DESCRIPTION: "Tax",
            },
            Decimal("1.20"),
        )
        assert ignored.classification == "ignored"

        unmapped = _classify_windsor_row(
            {
                FIELD_TRANSACTION_TYPE: "Mystery",
                FIELD_AMOUNT_TYPE: "Unknown",
                FIELD_AMOUNT_DESCRIPTION: "Weird",
            },
            Decimal("3.00"),
        )
        assert unmapped.classification == "unmapped"

    def test_maps_refund_itemprice_adjustments_into_refunds(self):
        assert _classify_windsor_row(
            {
                FIELD_TRANSACTION_TYPE: "Refund",
                FIELD_AMOUNT_TYPE: "ItemPrice",
                FIELD_AMOUNT_DESCRIPTION: "RestockingFee",
            },
            Decimal("8.00"),
        ).bucket == "refunds"
        assert _classify_windsor_row(
            {
                FIELD_TRANSACTION_TYPE: "Refund",
                FIELD_AMOUNT_TYPE: "ItemPrice",
                FIELD_AMOUNT_DESCRIPTION: "Goodwill",
            },
            Decimal("-3.00"),
        ).bucket == "refunds"


class TestWindsorSettlementCompareService:
    @pytest.mark.asyncio
    async def test_compare_month_returns_bucket_deltas_and_drilldowns(self):
        db = _db_with_tables(
            monthly_pnl_profiles=_chain_table(
                [
                    {
                        "id": "p1",
                        "client_id": "c1",
                        "marketplace_code": "US",
                        "currency_code": "USD",
                    }
                ]
            ),
            wbr_profiles=_chain_table([{"id": "w1", "windsor_account_id": "acct-us"}]),
            monthly_pnl_import_months=_chain_table(
                [{"id": "im1", "import_id": "imp1", "entry_month": "2026-02-01"}]
            ),
            monthly_pnl_imports=_chain_table(
                [
                    {
                        "id": "imp1",
                        "source_type": "csv_upload",
                        "source_filename": "whoosh-feb.csv",
                        "import_status": "success",
                        "created_at": "2026-03-17T12:00:00Z",
                        "finished_at": "2026-03-17T12:02:00Z",
                    }
                ]
            ),
            monthly_pnl_import_month_bucket_totals=_chain_table(
                [
                    {"import_month_id": "im1", "ledger_bucket": "product_sales", "amount": "100.00"},
                    {"import_month_id": "im1", "ledger_bucket": "shipping_credits", "amount": "5.00"},
                    {"import_month_id": "im1", "ledger_bucket": "refunds", "amount": "-10.00"},
                    {"import_month_id": "im1", "ledger_bucket": "advertising", "amount": "-7.00"},
                    {"import_month_id": "im1", "ledger_bucket": "referral_fees", "amount": "-15.00"},
                    {
                        "import_month_id": "im1",
                        "ledger_bucket": "fba_removal_order_fees",
                        "amount": "-1.00",
                    },
                ]
            ),
        )
        svc = WindsorSettlementCompareService(db)
        svc._fetch_rows = AsyncMock(
            return_value=[
                {
                    FIELD_TRANSACTION_TYPE: "Order",
                    FIELD_AMOUNT_TYPE: "ItemPrice",
                    FIELD_AMOUNT_DESCRIPTION: "Principal",
                    FIELD_AMOUNT: "100.00",
                    FIELD_MARKETPLACE_NAME: "Amazon.com",
                },
                {
                    FIELD_TRANSACTION_TYPE: "Order",
                    FIELD_AMOUNT_TYPE: "ItemPrice",
                    FIELD_AMOUNT_DESCRIPTION: "Shipping",
                    FIELD_AMOUNT: "5.00",
                    FIELD_MARKETPLACE_NAME: "Amazon.com",
                },
                {
                    FIELD_TRANSACTION_TYPE: "Refund",
                    FIELD_AMOUNT_TYPE: "ItemPrice",
                    FIELD_AMOUNT_DESCRIPTION: "Principal",
                    FIELD_AMOUNT: "-10.00",
                    FIELD_MARKETPLACE_NAME: "Amazon.com",
                },
                {
                    FIELD_TRANSACTION_TYPE: "ServiceFee",
                    FIELD_AMOUNT_TYPE: "Cost of Advertising",
                    FIELD_AMOUNT_DESCRIPTION: "TransactionTotalAmount",
                    FIELD_AMOUNT: "-7.00",
                    FIELD_MARKETPLACE_NAME: "Amazon.com",
                },
                {
                    FIELD_TRANSACTION_TYPE: "Order",
                    FIELD_AMOUNT_TYPE: "ItemFees",
                    FIELD_AMOUNT_DESCRIPTION: "Commission",
                    FIELD_AMOUNT: "-15.00",
                    FIELD_MARKETPLACE_NAME: "Amazon.com",
                },
                {
                    FIELD_TRANSACTION_TYPE: "other-transaction",
                    FIELD_AMOUNT_TYPE: "other-transaction",
                    FIELD_AMOUNT_DESCRIPTION: "DisposalComplete",
                    FIELD_AMOUNT: "-3.00",
                    FIELD_MARKETPLACE_NAME: "Amazon.ca",
                },
                {
                    FIELD_TRANSACTION_TYPE: "Order",
                    FIELD_AMOUNT_TYPE: "ItemPrice",
                    FIELD_AMOUNT_DESCRIPTION: "Tax",
                    FIELD_AMOUNT: "8.00",
                    FIELD_MARKETPLACE_NAME: "Amazon.com",
                },
                {
                    FIELD_TRANSACTION_TYPE: "Mystery",
                    FIELD_AMOUNT_TYPE: "Unknown",
                    FIELD_AMOUNT_DESCRIPTION: "Weird",
                    FIELD_AMOUNT: "2.00",
                    FIELD_MARKETPLACE_NAME: "Non-Amazon US",
                },
            ]
        )

        result = await svc.compare_month("p1", "2026-02-01")

        assert result["windsor_account_id"] == "acct-us"
        assert result["csv_baseline"]["active_imports"][0]["source_filename"] == "whoosh-feb.csv"
        assert result["windsor"]["row_count"] == 8
        assert result["windsor"]["mapped_row_count"] == 6
        assert result["windsor"]["ignored_row_count"] == 1
        assert result["windsor"]["unmapped_row_count"] == 1
        assert result["windsor"]["ignored_amount"] == "8.00"
        assert result["windsor"]["unmapped_amount"] == "2.00"
        assert result["windsor"]["bucket_totals"]["fba_removal_order_fees"] == "-3.00"
        product_sales_drilldown = next(
            row for row in result["windsor"]["mapped_bucket_drilldowns"] if row["bucket"] == "product_sales"
        )
        assert product_sales_drilldown["combo_totals"] == [
            {
                "transaction_type": "Order",
                "amount_type": "ItemPrice",
                "amount_description": "Principal",
                "classification": "mapped",
                "bucket": "product_sales",
                "reason": None,
                "row_count": 1,
                "amount": "100.00",
            }
        ]
        assert product_sales_drilldown["marketplace_totals"] == [
            {"marketplace_name": "Amazon.com", "row_count": 1, "amount": "100.00"}
        ]
        assert result["comparison"]["bucket_deltas"][0] == {
            "bucket": "fba_removal_order_fees",
            "csv_amount": "-1.00",
            "windsor_amount": "-3.00",
            "delta_amount": "-2.00",
        }
        assert result["windsor"]["marketplace_totals"][0]["marketplace_name"] == "Amazon.com"
        assert result["windsor"]["top_unmapped_combos"][0]["transaction_type"] == "Mystery"
        svc._fetch_rows.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_compare_month_filters_to_amazon_com_scope(self):
        db = _db_with_tables(
            monthly_pnl_profiles=_chain_table(
                [{"id": "p1", "client_id": "c1", "marketplace_code": "US", "currency_code": "USD"}]
            ),
            wbr_profiles=_chain_table([{"id": "w1", "windsor_account_id": "acct-us"}]),
            monthly_pnl_import_months=_chain_table(
                [{"id": "im1", "import_id": "imp1", "entry_month": "2026-02-01"}]
            ),
            monthly_pnl_imports=_chain_table([{"id": "imp1"}]),
            monthly_pnl_import_month_bucket_totals=_chain_table(
                [{"import_month_id": "im1", "ledger_bucket": "product_sales", "amount": "100.00"}]
            ),
        )
        svc = WindsorSettlementCompareService(db)
        svc._fetch_rows = AsyncMock(
            return_value=[
                {
                    FIELD_TRANSACTION_TYPE: "Order",
                    FIELD_AMOUNT_TYPE: "ItemPrice",
                    FIELD_AMOUNT_DESCRIPTION: "Principal",
                    FIELD_AMOUNT: "100.00",
                    FIELD_MARKETPLACE_NAME: "Amazon.com",
                },
                {
                    FIELD_TRANSACTION_TYPE: "Order",
                    FIELD_AMOUNT_TYPE: "ItemPrice",
                    FIELD_AMOUNT_DESCRIPTION: "Principal",
                    FIELD_AMOUNT: "50.00",
                    FIELD_MARKETPLACE_NAME: "Amazon.ca",
                },
                {
                    FIELD_TRANSACTION_TYPE: "Order",
                    FIELD_AMOUNT_TYPE: "ItemPrice",
                    FIELD_AMOUNT_DESCRIPTION: "Principal",
                    FIELD_AMOUNT: "25.00",
                    FIELD_MARKETPLACE_NAME: "Non-Amazon US",
                },
            ]
        )

        result = await svc.compare_month("p1", "2026-02-01", "amazon_com_only")

        assert result["marketplace_scope"] == "amazon_com_only"
        assert result["windsor"]["row_count"] == 1
        assert result["windsor"]["bucket_totals"]["product_sales"] == "100.00"
        assert result["windsor"]["marketplace_totals"] == [
            {"marketplace_name": "Amazon.com", "row_count": 1, "amount": "100.00"}
        ]
        assert result["scope_diagnostics"]["excluded_row_count"] == 2
        assert result["scope_diagnostics"]["blank_marketplace_row_count"] == 0
        assert result["scope_diagnostics"]["excluded_bucket_totals"] == [
            {"bucket": "product_sales", "amount": "75.00"}
        ]

    @pytest.mark.asyncio
    async def test_compare_month_reports_blank_marketplace_rows_excluded_by_scope(self):
        db = _db_with_tables(
            monthly_pnl_profiles=_chain_table(
                [{"id": "p1", "client_id": "c1", "marketplace_code": "US", "currency_code": "USD"}]
            ),
            wbr_profiles=_chain_table([{"id": "w1", "windsor_account_id": "acct-us"}]),
            monthly_pnl_import_months=_chain_table(
                [{"id": "im1", "import_id": "imp1", "entry_month": "2026-02-01"}]
            ),
            monthly_pnl_imports=_chain_table([{"id": "imp1"}]),
            monthly_pnl_import_month_bucket_totals=_chain_table(
                [
                    {"import_month_id": "im1", "ledger_bucket": "advertising", "amount": "-25.00"},
                    {"import_month_id": "im1", "ledger_bucket": "fba_monthly_storage_fees", "amount": "-7.00"},
                ]
            ),
        )
        svc = WindsorSettlementCompareService(db)
        svc._fetch_rows = AsyncMock(
            return_value=[
                {
                    FIELD_TRANSACTION_TYPE: "ServiceFee",
                    FIELD_AMOUNT_TYPE: "Cost of Advertising",
                    FIELD_AMOUNT_DESCRIPTION: "TransactionTotalAmount",
                    FIELD_AMOUNT: "-25.00",
                    FIELD_MARKETPLACE_NAME: "",
                },
                {
                    FIELD_TRANSACTION_TYPE: "other-transaction",
                    FIELD_AMOUNT_TYPE: "other-transaction",
                    FIELD_AMOUNT_DESCRIPTION: "Storage Fee",
                    FIELD_AMOUNT: "-7.00",
                    FIELD_MARKETPLACE_NAME: "",
                },
                {
                    FIELD_TRANSACTION_TYPE: "Order",
                    FIELD_AMOUNT_TYPE: "ItemPrice",
                    FIELD_AMOUNT_DESCRIPTION: "Principal",
                    FIELD_AMOUNT: "100.00",
                    FIELD_MARKETPLACE_NAME: "Amazon.com",
                },
            ]
        )

        result = await svc.compare_month("p1", "2026-02-01", "amazon_com_only")

        assert result["windsor"]["row_count"] == 1
        assert result["scope_diagnostics"]["excluded_row_count"] == 2
        assert result["scope_diagnostics"]["excluded_amount"] == "-32.00"
        assert result["scope_diagnostics"]["blank_marketplace_row_count"] == 2
        assert result["scope_diagnostics"]["blank_marketplace_amount"] == "-32.00"
        assert result["scope_diagnostics"]["excluded_bucket_totals"] == [
            {"bucket": "advertising", "amount": "-25.00"},
            {"bucket": "fba_monthly_storage_fees", "amount": "-7.00"},
        ]
        assert result["scope_diagnostics"]["top_blank_marketplace_combos"] == [
            {
                "transaction_type": "ServiceFee",
                "amount_type": "Cost of Advertising",
                "amount_description": "TransactionTotalAmount",
                "classification": "mapped",
                "bucket": "advertising",
                "reason": None,
                "row_count": 1,
                "amount": "-25.00",
            },
            {
                "transaction_type": "other-transaction",
                "amount_type": "other-transaction",
                "amount_description": "Storage Fee",
                "classification": "mapped",
                "bucket": "fba_monthly_storage_fees",
                "reason": None,
                "row_count": 1,
                "amount": "-7.00",
            },
        ]

    def test_compare_month_requires_active_csv_month(self):
        db = _db_with_tables(
            monthly_pnl_profiles=_chain_table(
                [{"id": "p1", "client_id": "c1", "marketplace_code": "US", "currency_code": "USD"}]
            ),
            wbr_profiles=_chain_table([{"id": "w1", "windsor_account_id": "acct-us"}]),
            monthly_pnl_import_months=_chain_table([]),
        )
        svc = WindsorSettlementCompareService(db)

        with pytest.raises(PNLValidationError, match="No active Monthly P&L import month exists"):
            svc._load_csv_baseline("p1", "2026-02-01")

    def test_compare_month_rejects_invalid_marketplace_scope(self):
        db = _db_with_tables(
            monthly_pnl_profiles=_chain_table(
                [{"id": "p1", "client_id": "c1", "marketplace_code": "US", "currency_code": "USD"}]
            ),
        )
        svc = WindsorSettlementCompareService(db)

        with pytest.raises(PNLValidationError, match="marketplace_scope must be one of"):
            svc._parse_marketplace_scope("bad-scope")
