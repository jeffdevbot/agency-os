"""Tests for Monthly P&L transaction import pipeline.

Covers CSV parsing, normalization, mapping rule evaluation, ledger
expansion, month slicing, and the import orchestration service.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import MagicMock

from postgrest.exceptions import APIError as PostgrestAPIError
import pytest

from app.services.pnl.profiles import PNLDuplicateFileError, PNLNotFoundError, PNLValidationError
from app.services.pnl.sku_units import SkuUnitSourceRow, summarize_sku_units
from app.services.pnl.transaction_import import (
    LedgerEntry,
    MappingRule,
    MonthSlice,
    ParsedRawRow,
    TransactionImportService,
    expand_raw_row_to_ledger,
    find_matching_rule,
    parse_raw_rows,
    parse_transaction_csv,
)

# ── Fixtures ─────────────────────────────────────────────────────────

SAMPLE_CSV = (
    '"date/time","settlement id","type","order id","sku","description",'
    '"product sales","product sales tax","shipping credits","shipping credits tax",'
    '"gift wrap credits","giftwrap credits tax","promotional rebates",'
    '"promotional rebates tax","marketplace withheld tax","selling fees",'
    '"fba fees","other transaction fees","other","total",'
    '"Transaction Status","Transaction Release Date"\n'
    '"Jan 15, 2026 12:00:00 AM PST","12345","Order","111-AAA","SKU1","Widget",'
    '"10.00","0","2.50","0","0","0","-1.00","0","0","-1.50","-3.00","0","0","7.00",'
    '"Released","Jan 20, 2026"\n'
    '"Jan 16, 2026 12:00:00 AM PST","12345","Refund","111-BBB","SKU2","Gadget",'
    '"-5.00","0","-1.00","0","0","0","0.50","0","0","0.75","1.50","0","0","-3.25",'
    '"Released","Jan 22, 2026"\n'
    '"Feb 01, 2026 12:00:00 AM PST","12345","Service Fee","","","Cost of Advertising",'
    '"0","0","0","0","0","0","0","0","0","0","0","0","-50.00","-50.00",'
    '"Released","Feb 05, 2026"\n'
    '"Feb 10, 2026 12:00:00 AM PST","12345","Transfer","","","To your bank",'
    '"0","0","0","0","0","0","0","0","0","0","0","0","-500.00","-500.00",'
    '"Released","Feb 12, 2026"\n'
)

CA_SAMPLE_CSV = (
    '"Includes Amazon Marketplace, Fulfillment by Amazon (FBA), and Amazon Webstore transactions"\n'
    '"All amounts in CAD, unless specified"\n'
    '"date/time","settlement id","type","order id","sku","description","quantity","marketplace",'
    '"fulfillment","order city","order state","order postal","tax collection model","product sales",'
    '"product sales tax","shipping credits","shipping credits tax","gift wrap credits",'
    '"gift wrap credits tax","Regulatory fee","Tax on regulatory fee","promotional rebates",'
    '"promotional rebates tax","marketplace withheld tax","selling fees","fba fees",'
    '"other transaction fees","other","total","Transaction status","Transaction Release Date"\n'
    '"Feb 1, 2026 12:02:19 a.m. PST","25462286111","Order","701-9330206-0021017","1FGAMZDUO",'
    '"WHOOSH","1","amazon.ca","Amazon","Brantford","Ontario","N3T 0H","","19.99","2.60","0","0",'
    '"0","0","0","0","0","0","0","-3.39","-7.19","-0.09","0","11.92","Released",'
    '"Feb 1, 2026 12:02:19 a.m. PST"\n'
    '"Feb 1, 2026 4:55:06 p.m. PST","25462286111","Service Fee","","","Cost of advertising","","amazon.ca",'
    '"Amazon","","","","","0","0","0","0","0","0","0","0","0","0","0","0","0","-501.16",'
    '"-65.15","-566.31","Released","Feb 1, 2026 4:55:06 p.m. PST"\n'
)


def _make_rules() -> list[MappingRule]:
    return [
        MappingRule(
            id="rule-ad",
            profile_id=None,
            source_type="amazon_transaction_upload",
            match_spec={"type": "Service Fee", "description": "Cost of Advertising"},
            match_operator="exact_fields",
            target_bucket="advertising",
            priority=10,
        ),
        MappingRule(
            id="rule-transfer",
            profile_id=None,
            source_type="amazon_transaction_upload",
            match_spec={"type": "Transfer"},
            match_operator="exact_fields",
            target_bucket="non_pnl_transfer",
            priority=10,
        ),
        MappingRule(
            id="rule-subscription",
            profile_id=None,
            source_type="amazon_transaction_upload",
            match_spec={"type": "Service Fee", "description": "Subscription"},
            match_operator="exact_fields",
            target_bucket="subscription_fees",
            priority=10,
        ),
        MappingRule(
            id="rule-vine",
            profile_id=None,
            source_type="amazon_transaction_upload",
            match_spec={"type": "Amazon Fees", "description": "Vine Enrollment Fee"},
            match_operator="exact_fields",
            target_bucket="promotions_fees",
            priority=10,
        ),
        MappingRule(
            id="rule-price-discount",
            profile_id=None,
            source_type="amazon_transaction_upload",
            match_spec={"description": "Price Discount"},
            match_operator="starts_with",
            target_bucket="promotions_fees",
            priority=10,
        ),
        MappingRule(
            id="rule-chargeback",
            profile_id=None,
            source_type="amazon_transaction_upload",
            match_spec={"type": "Chargeback Refund"},
            match_operator="exact_fields",
            target_bucket="chargebacks",
            priority=20,
        ),
        MappingRule(
            id="rule-removal",
            profile_id=None,
            source_type="amazon_transaction_upload",
            match_spec={"type": "FBA Inventory Fee", "description": "FBA Removal Order"},
            match_operator="starts_with",
            target_bucket="fba_removal_order_fees",
            priority=10,
        ),
    ]


# ── CSV parsing tests ────────────────────────────────────────────────


class TestParseTransactionCSV:
    def test_parses_valid_csv(self):
        header_values, header_map, data_rows = parse_transaction_csv(SAMPLE_CSV.encode("utf-8"))
        assert "date_time" in header_map
        assert "type" in header_map
        assert "product_sales" in header_map
        assert len(data_rows) == 4

    def test_rejects_empty_file(self):
        with pytest.raises(PNLValidationError, match="empty"):
            parse_transaction_csv(b"")

    def test_rejects_file_without_required_headers(self):
        bad_csv = "col_a,col_b\n1,2\n"
        with pytest.raises(PNLValidationError, match="date/time and type"):
            parse_transaction_csv(bad_csv.encode("utf-8"))

    def test_handles_utf8_bom(self):
        bom_csv = b"\xef\xbb\xbf" + SAMPLE_CSV.encode("utf-8")
        header_values, header_map, data_rows = parse_transaction_csv(bom_csv)
        assert len(data_rows) == 4


class TestParseRawRows:
    def test_parses_ca_style_timestamps_and_extra_columns(self):
        header_values, header_map, data_rows = parse_transaction_csv(CA_SAMPLE_CSV.encode("utf-8"))
        raw_rows = parse_raw_rows(header_values, header_map, data_rows)

        assert len(raw_rows) == 2
        assert raw_rows[0].posted_at == datetime(2026, 2, 1, 0, 2, 19, tzinfo=UTC)
        assert raw_rows[0].release_at == datetime(2026, 2, 1, 0, 2, 19, tzinfo=UTC)
        assert raw_rows[0].entry_month == date(2026, 2, 1)
        assert raw_rows[0].quantity == 1
        assert raw_rows[1].posted_at == datetime(2026, 2, 1, 16, 55, 6, tzinfo=UTC)
        assert raw_rows[1].entry_month == date(2026, 2, 1)

    def test_parses_amazon_release_datetime_with_timezone_abbreviation(self):
        csv_with_release_ts = (
            '"date/time","type","order id","sku","description","product sales","total","Transaction Status","Transaction Release Date"\n'
            '"Dec 1, 2025 12:04:11 AM PST","Order","111","SKU1","Thing","17.19","17.19","Released","Dec 1, 2025 12:04:11 AM PST"\n'
        )
        header_values, header_map, data_rows = parse_transaction_csv(csv_with_release_ts.encode())
        raw_rows = parse_raw_rows(header_values, header_map, data_rows)

        assert len(raw_rows) == 1
        assert raw_rows[0].posted_at == datetime(2025, 12, 1, 0, 4, 11, tzinfo=UTC)
        assert raw_rows[0].release_at == datetime(2025, 12, 1, 0, 4, 11, tzinfo=UTC)
        assert raw_rows[0].entry_month == date(2025, 12, 1)

    def test_parses_order_row(self):
        header_values, header_map, data_rows = parse_transaction_csv(SAMPLE_CSV.encode("utf-8"))
        raw_rows = parse_raw_rows(header_values, header_map, data_rows)
        assert len(raw_rows) == 4

        order_row = raw_rows[0]
        assert order_row.raw_type == "Order"
        assert order_row.order_id == "111-AAA"
        assert order_row.sku == "SKU1"
        assert order_row.amounts["product_sales"] == Decimal("10.00")
        assert order_row.amounts["shipping_credits"] == Decimal("2.50")
        assert order_row.amounts["promotional_rebates"] == Decimal("-1.00")
        assert order_row.amounts["selling_fees"] == Decimal("-1.50")
        assert order_row.amounts["fba_fees"] == Decimal("-3.00")

    def test_parses_quantity_column(self):
        csv_with_quantity = (
            '"date/time","type","order id","sku","quantity","description","product sales","total"\n'
            '"Nov 1, 2025 2:24:35 AM PDT","Order","111","SKU1","2","Widget","25.98","14.72"\n'
            '"Nov 2, 2025 9:28:44 AM PST","Refund","222","SKU2","3","Widget","-86.37","-73.48"\n'
        )
        header_values, header_map, data_rows = parse_transaction_csv(csv_with_quantity.encode("utf-8"))
        raw_rows = parse_raw_rows(header_values, header_map, data_rows)

        assert raw_rows[0].quantity == 2
        assert raw_rows[1].quantity == 3

    def test_canonical_month_uses_posted_date(self):
        """date/time is canonical month; release date is only a fallback."""
        csv_cross_month = (
            '"date/time","type","order id","sku","description","product sales","total","Transaction Release Date"\n'
            '"Dec 31, 2025 11:59:59 PM PST","Order","111","SKU1","Thing","5.00","5.00","Jan 02, 2026 12:00:00 AM PST"\n'
        )
        header_values, header_map, data_rows = parse_transaction_csv(csv_cross_month.encode("utf-8"))
        raw_rows = parse_raw_rows(header_values, header_map, data_rows)

        assert raw_rows[0].entry_month == date(2025, 12, 1)

    def test_keeps_blank_type_rows_when_description_present(self):
        csv_blank_type = (
            '"date/time","type","description","other transaction fees","total"\n'
            '"Dec 10, 2025 12:00:00 AM PST","","Price Discount - 03eb6711","-245.00","-245.00"\n'
        )
        header_values, header_map, data_rows = parse_transaction_csv(csv_blank_type.encode("utf-8"))
        raw_rows = parse_raw_rows(header_values, header_map, data_rows)

        assert len(raw_rows) == 1
        assert raw_rows[0].raw_type is None
        assert raw_rows[0].raw_description == "Price Discount - 03eb6711"
        assert raw_rows[0].amounts["other_transaction_fees"] == Decimal("-245.00")

    def test_fallback_to_datetime_when_no_release(self):
        csv_no_release = (
            '"date/time","type","order id","sku","description","product sales","total"\n'
            '"Mar 10, 2026","Order","111","SKU1","Thing","5.00","5.00"\n'
        )
        header_values, header_map, data_rows = parse_transaction_csv(csv_no_release.encode())
        raw_rows = parse_raw_rows(header_values, header_map, data_rows)
        assert raw_rows[0].entry_month == date(2026, 3, 1)

    def test_rejects_file_with_no_data_rows(self):
        csv_headers_only = (
            '"date/time","type","order id","sku","description"\n'
        )
        header_values, header_map, data_rows = parse_transaction_csv(csv_headers_only.encode())
        with pytest.raises(PNLValidationError, match="no data rows"):
            parse_raw_rows(header_values, header_map, data_rows)


# ── Mapping rule tests ───────────────────────────────────────────────


class TestMappingRules:
    def test_exact_fields_match(self):
        rules = _make_rules()
        match = find_matching_rule(rules, "Service Fee", "Cost of Advertising")
        assert match is not None
        assert match.target_bucket == "advertising"

    def test_exact_fields_no_match(self):
        rules = _make_rules()
        match = find_matching_rule(rules, "Order", "Widget description")
        assert match is None

    def test_transfer_match(self):
        rules = _make_rules()
        match = find_matching_rule(rules, "Transfer", "To your bank")
        assert match is not None
        assert match.target_bucket == "non_pnl_transfer"

    def test_profile_specific_rule_beats_global(self):
        global_rule = MappingRule(
            id="global-1",
            profile_id=None,
            source_type="amazon_transaction_upload",
            match_spec={"type": "Service Fee", "description": "Cost of Advertising"},
            match_operator="exact_fields",
            target_bucket="advertising",
            priority=10,
        )
        profile_rule = MappingRule(
            id="profile-1",
            profile_id="profile-abc",
            source_type="amazon_transaction_upload",
            match_spec={"type": "Service Fee", "description": "Cost of Advertising"},
            match_operator="exact_fields",
            target_bucket="other_transaction_fees",  # different bucket
            priority=50,  # lower priority (higher number) than global
        )
        rules = [global_rule, profile_rule]
        match = find_matching_rule(rules, "Service Fee", "Cost of Advertising", profile_id="profile-abc")
        assert match is not None
        assert match.id == "profile-1"

    def test_exact_fields_match_is_case_insensitive(self):
        rules = _make_rules()

        advertising = find_matching_rule(rules, "Service Fee", "Cost of advertising")
        assert advertising is not None
        assert advertising.target_bucket == "advertising"

        amazon_fees_rule = MappingRule(
            id="rule-amazon-fees",
            profile_id=None,
            source_type="amazon_transaction_upload",
            match_spec={"type": "Amazon Fees"},
            match_operator="exact_fields",
            target_bucket="promotions_fees",
            priority=30,
        )
        coupon_fee = find_matching_rule([amazon_fees_rule], "Amazon fees", "Coupon participation fee")
        assert coupon_fee is not None
        assert coupon_fee.target_bucket == "promotions_fees"

    def test_contains_operator(self):
        rule = MappingRule(
            id="r1",
            profile_id=None,
            source_type="amazon_transaction_upload",
            match_spec={"description": "Reimbursement"},
            match_operator="contains",
            target_bucket="fba_inventory_credit",
            priority=10,
        )
        match = find_matching_rule([rule], "Adjustment", "FBA Inventory Reimbursement - Customer Return")
        assert match is not None
        assert match.target_bucket == "fba_inventory_credit"

    def test_starts_with_operator(self):
        rule = MappingRule(
            id="r1",
            profile_id=None,
            source_type="amazon_transaction_upload",
            match_spec={"type": "FBA Inventory"},
            match_operator="starts_with",
            target_bucket="fba_removal_order_fees",
            priority=10,
        )
        match = find_matching_rule([rule], "FBA Inventory Fee", "FBA Removal Order: Disposal")
        assert match is not None


# ── Ledger expansion tests ───────────────────────────────────────────


class TestLedgerExpansion:
    def test_order_row_expands_to_column_buckets(self):
        raw_row = ParsedRawRow(
            row_index=0,
            posted_at=datetime(2026, 1, 15, tzinfo=UTC),
            release_at=datetime(2026, 1, 20, tzinfo=UTC),
            order_id="111-AAA",
            sku="SKU1",
            raw_type="Order",
            raw_description="Widget",
            entry_month=date(2026, 1, 1),
            amounts={
                "product_sales": Decimal("10.00"),
                "shipping_credits": Decimal("2.50"),
                "selling_fees": Decimal("-1.50"),
                "fba_fees": Decimal("-3.00"),
            },
            raw_payload={},
        )
        entries = expand_raw_row_to_ledger(raw_row, _make_rules(), None)
        buckets = {e.ledger_bucket: e.amount for e in entries}

        assert buckets["product_sales"] == Decimal("10.00")
        assert buckets["shipping_credits"] == Decimal("2.50")
        assert buckets["referral_fees"] == Decimal("-1.50")
        assert buckets["fba_fees"] == Decimal("-3.00")

    def test_refund_other_and_product_sales_coalesce_into_single_refunds_bucket(self):
        raw_row = ParsedRawRow(
            row_index=7140,
            posted_at=datetime(2025, 11, 10, tzinfo=UTC),
            release_at=datetime(2025, 11, 11, tzinfo=UTC),
            order_id="111-REFUND",
            sku="SKU-REFUND",
            raw_type="Refund",
            raw_description="Refund with product sales and other",
            entry_month=date(2025, 11, 1),
            amounts={
                "product_sales": Decimal("-19.99"),
                "marketplace_withheld_tax": Decimal("1.77"),
                "selling_fees": Decimal("2.40"),
                "other": Decimal("4.00"),
            },
            raw_payload={},
        )

        entries = expand_raw_row_to_ledger(raw_row, _make_rules(), None)
        buckets = {e.ledger_bucket: e.amount for e in entries}

        assert len([e for e in entries if e.ledger_bucket == "refunds"]) == 1
        assert buckets["refunds"] == Decimal("-15.99")
        assert buckets["marketplace_withheld_tax"] == Decimal("1.77")
        assert buckets["referral_fees"] == Decimal("2.40")
        assert all(e.is_mapped for e in entries)

    def test_refund_row_maps_to_refund_buckets(self):
        raw_row = ParsedRawRow(
            row_index=1,
            posted_at=datetime(2026, 1, 16, tzinfo=UTC),
            release_at=datetime(2026, 1, 22, tzinfo=UTC),
            order_id="111-BBB",
            sku="SKU2",
            raw_type="Refund",
            raw_description="Gadget",
            entry_month=date(2026, 1, 1),
            amounts={
                "product_sales": Decimal("-5.00"),
                "shipping_credits": Decimal("-1.00"),
                "promotional_rebates": Decimal("0.50"),
                "selling_fees": Decimal("0.75"),
                "fba_fees": Decimal("1.50"),
            },
            raw_payload={},
        )
        entries = expand_raw_row_to_ledger(raw_row, _make_rules(), None)
        buckets = {e.ledger_bucket: e.amount for e in entries}

        assert buckets["refunds"] == Decimal("-5.00")
        assert buckets["shipping_credit_refunds"] == Decimal("-1.00")
        assert buckets["promotional_rebate_refunds"] == Decimal("0.50")
        assert buckets["referral_fees"] == Decimal("0.75")
        assert buckets["fba_fees"] == Decimal("1.50")


class TestSkuUnitAggregation:
    def test_summarize_sku_units_aggregates_orders_and_refunds(self):
        summary = summarize_sku_units(
            [
                SkuUnitSourceRow(
                    sku="SKU1",
                    quantity=2,
                    raw_type="Order",
                    product_sales=Decimal("25.98"),
                ),
                SkuUnitSourceRow(
                    sku="SKU1",
                    quantity=1,
                    raw_type="Refund",
                    product_sales=Decimal("-12.99"),
                ),
                SkuUnitSourceRow(
                    sku="SKU2",
                    quantity=1,
                    raw_type="Refund",
                    product_sales=Decimal("0"),
                ),
            ]
        )

        assert summary == {
            "SKU1": {
                "net_units": 1,
                "order_row_count": 1,
                "refund_row_count": 1,
            }
        }

    def test_insert_sku_unit_totals_aggregates_orders_and_refunds(self):
        db = MagicMock()
        sku_units_table = MagicMock()
        sku_units_table.insert.return_value = sku_units_table
        sku_units_table.execute.return_value = MagicMock(data=[{}])
        db.table.return_value = sku_units_table

        svc = TransactionImportService(db)
        svc._insert_sku_unit_totals(
            import_id="imp-1",
            import_month_id="im-1",
            profile_id="p1",
            entry_month=date(2025, 11, 1),
            raw_rows=[
                ParsedRawRow(
                    row_index=0,
                    posted_at=datetime(2025, 11, 1, tzinfo=UTC),
                    release_at=None,
                    order_id="111",
                    sku="SKU1",
                    raw_type="Order",
                    raw_description="Widget",
                    entry_month=date(2025, 11, 1),
                    amounts={"product_sales": Decimal("25.98")},
                    raw_payload={},
                    quantity=2,
                ),
                ParsedRawRow(
                    row_index=1,
                    posted_at=datetime(2025, 11, 2, tzinfo=UTC),
                    release_at=None,
                    order_id="222",
                    sku="SKU1",
                    raw_type="Refund",
                    raw_description="Widget",
                    entry_month=date(2025, 11, 1),
                    amounts={"product_sales": Decimal("-12.99")},
                    raw_payload={},
                    quantity=1,
                ),
                ParsedRawRow(
                    row_index=2,
                    posted_at=datetime(2025, 11, 2, tzinfo=UTC),
                    release_at=None,
                    order_id="333",
                    sku="SKU2",
                    raw_type="Refund",
                    raw_description="Shipping only refund",
                    entry_month=date(2025, 11, 1),
                    amounts={"shipping_credits": Decimal("-2.99")},
                    raw_payload={},
                    quantity=1,
                ),
            ],
        )

        payloads = sku_units_table.insert.call_args.args[0]
        assert payloads == [
            {
                "import_id": "imp-1",
                "import_month_id": "im-1",
                "profile_id": "p1",
                "entry_month": "2025-11-01",
                "sku": "SKU1",
                "net_units": 1,
                "order_row_count": 1,
                "refund_row_count": 1,
            }
        ]

    def test_service_fee_advertising_uses_rule(self):
        raw_row = ParsedRawRow(
            row_index=2,
            posted_at=datetime(2026, 2, 1, tzinfo=UTC),
            release_at=datetime(2026, 2, 5, tzinfo=UTC),
            order_id=None,
            sku=None,
            raw_type="Service Fee",
            raw_description="Cost of Advertising",
            entry_month=date(2026, 2, 1),
            amounts={"other": Decimal("-50.00")},
            raw_payload={},
        )
        entries = expand_raw_row_to_ledger(raw_row, _make_rules(), None)
        assert len(entries) == 1
        assert entries[0].ledger_bucket == "advertising"
        assert entries[0].amount == Decimal("-50.00")
        assert entries[0].is_mapped is True
        assert entries[0].mapping_rule_id == "rule-ad"

    def test_transfer_row_maps_to_non_pnl(self):
        raw_row = ParsedRawRow(
            row_index=3,
            posted_at=datetime(2026, 2, 10, tzinfo=UTC),
            release_at=datetime(2026, 2, 12, tzinfo=UTC),
            order_id=None,
            sku=None,
            raw_type="Transfer",
            raw_description="To your bank",
            entry_month=date(2026, 2, 1),
            amounts={"other": Decimal("-500.00")},
            raw_payload={},
        )
        entries = expand_raw_row_to_ledger(raw_row, _make_rules(), None)
        assert len(entries) == 1
        assert entries[0].ledger_bucket == "non_pnl_transfer"

    def test_amazon_fees_vine_maps_to_promotions_fees(self):
        raw_row = ParsedRawRow(
            row_index=4,
            posted_at=datetime(2026, 2, 10, tzinfo=UTC),
            release_at=datetime(2026, 2, 12, tzinfo=UTC),
            order_id=None,
            sku=None,
            raw_type="Amazon Fees",
            raw_description="Vine Enrollment Fee",
            entry_month=date(2026, 2, 1),
            amounts={"selling_fees": Decimal("-200.00")},
            raw_payload={},
        )
        entries = expand_raw_row_to_ledger(raw_row, _make_rules(), None)
        assert len(entries) == 1
        assert entries[0].ledger_bucket == "promotions_fees"
        assert entries[0].amount == Decimal("-200.00")
        assert entries[0].is_mapped is True
        assert entries[0].mapping_rule_id == "rule-vine"

    def test_blank_type_price_discount_maps_to_promotions_fees(self):
        raw_row = ParsedRawRow(
            row_index=5,
            posted_at=datetime(2025, 12, 10, tzinfo=UTC),
            release_at=datetime(2025, 12, 15, tzinfo=UTC),
            order_id=None,
            sku=None,
            raw_type=None,
            raw_description="Price Discount - 03eb6711",
            entry_month=date(2025, 12, 1),
            amounts={"other_transaction_fees": Decimal("-245.00")},
            raw_payload={},
        )
        entries = expand_raw_row_to_ledger(raw_row, _make_rules(), None)
        assert len(entries) == 1
        assert entries[0].ledger_bucket == "promotions_fees"
        assert entries[0].amount == Decimal("-245.00")
        assert entries[0].mapping_rule_id == "rule-price-discount"

    def test_chargeback_refund_sums_all_amount_columns(self):
        raw_row = ParsedRawRow(
            row_index=6,
            posted_at=datetime(2025, 12, 11, tzinfo=UTC),
            release_at=datetime(2025, 12, 16, tzinfo=UTC),
            order_id="111-CCC",
            sku="SKU3",
            raw_type="Chargeback Refund",
            raw_description=None,
            entry_month=date(2025, 12, 1),
            amounts={
                "product_sales": Decimal("-10.00"),
                "shipping_credits": Decimal("-1.00"),
                "promotional_rebates": Decimal("0.25"),
                "selling_fees": Decimal("0.50"),
                "other": Decimal("-0.75"),
            },
            raw_payload={},
        )
        entries = expand_raw_row_to_ledger(raw_row, _make_rules(), None)

        assert len(entries) == 1
        assert entries[0].ledger_bucket == "chargebacks"
        assert entries[0].amount == Decimal("-11.00")
        assert entries[0].is_mapped is True
        assert entries[0].mapping_rule_id == "rule-chargeback"

    def test_fba_removal_order_description_prefix_maps_to_removal_bucket(self):
        raw_row = ParsedRawRow(
            row_index=7,
            posted_at=datetime(2025, 12, 9, tzinfo=UTC),
            release_at=datetime(2025, 12, 9, tzinfo=UTC),
            order_id="114-7325620-2303403",
            sku=None,
            raw_type="FBA Inventory Fee",
            raw_description="FBA Removal Order: Disposal Fee",
            entry_month=date(2025, 12, 1),
            amounts={"other": Decimal("-3.95")},
            raw_payload={},
        )
        entries = expand_raw_row_to_ledger(raw_row, _make_rules(), None)

        assert len(entries) == 1
        assert entries[0].ledger_bucket == "fba_removal_order_fees"
        assert entries[0].amount == Decimal("-3.95")
        assert entries[0].mapping_rule_id == "rule-removal"

    def test_liquidations_split_into_proceeds_and_fees(self):
        raw_row = ParsedRawRow(
            row_index=8,
            posted_at=datetime(2025, 12, 12, tzinfo=UTC),
            release_at=datetime(2025, 12, 17, tzinfo=UTC),
            order_id=None,
            sku=None,
            raw_type="Liquidations",
            raw_description=None,
            entry_month=date(2025, 12, 1),
            amounts={
                "product_sales": Decimal("125.00"),
                "other_transaction_fees": Decimal("-7.50"),
                "other": Decimal("-1.25"),
            },
            raw_payload={},
        )
        entries = expand_raw_row_to_ledger(raw_row, _make_rules(), None)
        buckets = {e.ledger_bucket: e.amount for e in entries}

        assert buckets["fba_liquidation_proceeds"] == Decimal("125.00")
        assert buckets["liquidation_fees"] == Decimal("-7.50")
        assert buckets["unmapped"] == Decimal("-1.25")

    def test_refund_other_maps_to_refunds_bucket(self):
        raw_row = ParsedRawRow(
            row_index=9,
            posted_at=datetime(2025, 12, 15, tzinfo=UTC),
            release_at=datetime(2025, 12, 15, tzinfo=UTC),
            order_id="111-2295089-9668224",
            sku="1FGAMZDUO",
            raw_type="Refund",
            raw_description="WHOOSH! Screen Shine Duo",
            entry_month=date(2025, 12, 1),
            amounts={
                "product_sales": Decimal("-10.00"),
                "other": Decimal("3.60"),
            },
            raw_payload={},
        )
        entries = expand_raw_row_to_ledger(raw_row, _make_rules(), None)
        refunds_entries = [e for e in entries if e.ledger_bucket == "refunds"]

        assert len(refunds_entries) == 1
        assert refunds_entries[0].amount == Decimal("-6.40")
        assert len(entries) == 1

    def test_row_with_no_entry_month_produces_no_entries(self):
        raw_row = ParsedRawRow(
            row_index=0,
            posted_at=None,
            release_at=None,
            order_id=None,
            sku=None,
            raw_type="Order",
            raw_description=None,
            entry_month=None,
            amounts={"product_sales": Decimal("10.00")},
            raw_payload={},
        )
        entries = expand_raw_row_to_ledger(raw_row, _make_rules(), None)
        assert entries == []

    def test_other_column_on_order_row_maps_to_other_transaction_fees(self):
        raw_row = ParsedRawRow(
            row_index=0,
            posted_at=datetime(2026, 1, 1, tzinfo=UTC),
            release_at=datetime(2026, 1, 5, tzinfo=UTC),
            order_id="111",
            sku="SKU",
            raw_type="Order",
            raw_description="Thing",
            entry_month=date(2026, 1, 1),
            amounts={"product_sales": Decimal("10.00"), "other": Decimal("-2.00")},
            raw_payload={},
        )
        entries = expand_raw_row_to_ledger(raw_row, _make_rules(), None)
        other_fees = [e for e in entries if e.ledger_bucket == "other_transaction_fees"]
        assert len(other_fees) == 1
        assert other_fees[0].amount == Decimal("-2.00")
        assert other_fees[0].is_mapped is True

    def test_ca_regulatory_fee_columns_surface_as_unmapped(self):
        raw_row = ParsedRawRow(
            row_index=10,
            posted_at=datetime(2026, 2, 1, tzinfo=UTC),
            release_at=datetime(2026, 2, 1, tzinfo=UTC),
            order_id="701-CA-FEE",
            sku="SKU-CA",
            raw_type="Order",
            raw_description="CA regulatory fee sample",
            entry_month=date(2026, 2, 1),
            amounts={
                "product_sales": Decimal("19.99"),
                "regulatory_fee": Decimal("-0.45"),
                "tax_on_regulatory_fee": Decimal("-0.05"),
            },
            raw_payload={},
        )

        entries = expand_raw_row_to_ledger(raw_row, _make_rules(), None)
        buckets = {e.ledger_bucket: e.amount for e in entries}

        assert buckets["product_sales"] == Decimal("19.99")
        assert buckets["unmapped"] == Decimal("-0.50")


# ── Service integration tests (mocked DB) ────────────────────────────


def _chain_table(response_data: list[dict] | None = None) -> MagicMock:
    table = MagicMock()
    table.select.return_value = table
    table.insert.return_value = table
    table.update.return_value = table
    table.delete.return_value = table
    table.eq.return_value = table
    table.neq.return_value = table
    table.order.return_value = table
    table.limit.return_value = table
    resp = MagicMock()
    resp.data = response_data if response_data is not None else []
    table.execute.return_value = resp
    return table


def _chain_rpc() -> MagicMock:
    rpc = MagicMock()
    rpc.execute.return_value = MagicMock(data=None)
    return rpc


def _db_with_tables(**tables: MagicMock) -> MagicMock:
    db = MagicMock()
    db.table.side_effect = lambda name: tables.get(name, _chain_table())
    db.rpc.return_value = _chain_rpc()
    return db


def _pg_error(message: str) -> PostgrestAPIError:
    return PostgrestAPIError({"message": message, "code": "23505", "details": "", "hint": ""})


def _gateway_error() -> PostgrestAPIError:
    return PostgrestAPIError(
        {"message": "JSON could not be generated", "code": 502, "details": "", "hint": ""}
    )


class TestTransactionImportService:
    def test_enqueue_file_stages_source_and_returns_pending_months(self):
        profiles = _chain_table([{"id": "p1", "marketplace_code": "US"}])
        imports_no_dup = _chain_table([])
        imports_insert = _chain_table([{"id": "imp-queued", "import_status": "pending"}])
        rules = _chain_table([])

        created_import_payloads: list[dict] = []

        def insert_with_capture(payload):
            created_import_payloads.append(payload)
            return imports_insert

        imports_insert.insert = insert_with_capture

        call_counts: dict[str, int] = {}

        def table_router(name: str) -> MagicMock:
            call_counts.setdefault(name, 0)
            call_counts[name] += 1
            if name == "monthly_pnl_profiles":
                return profiles
            if name == "monthly_pnl_mapping_rules":
                return rules
            if name == "monthly_pnl_imports":
                if call_counts[name] == 1:
                    return imports_no_dup
                return imports_insert
            return _chain_table()

        storage_bucket = MagicMock()
        storage_bucket.upload.return_value = MagicMock()
        storage = MagicMock()
        storage.from_.return_value = storage_bucket

        csv_data = (
            '"date/time","type","order id","sku","description","product sales","total",'
            '"Transaction Release Date"\n'
            '"Jan 15, 2026","Order","111","SKU1","Widget","10.00","10.00","Jan 20, 2026"\n'
        ).encode("utf-8")

        db = MagicMock()
        db.table.side_effect = table_router
        db.rpc.return_value = _chain_rpc()
        db.storage = storage

        svc = TransactionImportService(db)
        result = svc.enqueue_file(profile_id="p1", file_name="test.csv", file_bytes=csv_data)

        assert result["import"]["import_status"] == "pending"
        assert result["months"][0]["entry_month"] == "2026-01-01"
        assert result["months"][0]["import_status"] == "pending"
        storage_bucket.upload.assert_called_once()
        assert created_import_payloads[0]["storage_path"].endswith("test.csv")
        assert created_import_payloads[0]["raw_meta"]["async_import_v1"] is True

    def test_rejects_running_duplicate_file(self):
        profiles = _chain_table([{"id": "p1", "marketplace_code": "US"}])
        imports = _chain_table([{"id": "existing-import", "import_status": "running"}])
        db = _db_with_tables(monthly_pnl_profiles=profiles, monthly_pnl_imports=imports)

        svc = TransactionImportService(db)
        with pytest.raises(PNLDuplicateFileError, match="already been imported"):
            svc.import_file(
                profile_id="p1",
                file_name="test.csv",
                file_bytes=SAMPLE_CSV.encode("utf-8"),
            )

    def test_rejects_missing_profile(self):
        profiles = _chain_table([])
        db = _db_with_tables(monthly_pnl_profiles=profiles)

        svc = TransactionImportService(db)
        with pytest.raises(PNLNotFoundError, match="not found"):
            svc.import_file(
                profile_id="nonexistent",
                file_name="test.csv",
                file_bytes=SAMPLE_CSV.encode("utf-8"),
            )

    def test_successful_import_returns_month_summaries(self):
        profiles = _chain_table([{"id": "p1", "marketplace_code": "US"}])
        imports_no_dup = _chain_table([])  # no duplicate
        imports_insert = _chain_table([{"id": "imp-1", "import_status": "pending"}])
        imports_update = _chain_table([{"id": "imp-1", "import_status": "running"}])
        imports_final = _chain_table([{
            "id": "imp-1", "import_status": "success",
            "finished_at": "2026-01-20T00:00:00+00:00",
        }])

        rules = _chain_table([
            {
                "id": "rule-ad",
                "profile_id": None,
                "source_type": "amazon_transaction_upload",
                "match_spec": {"type": "Service Fee", "description": "Cost of Advertising"},
                "match_operator": "exact_fields",
                "target_bucket": "advertising",
                "priority": 10,
            },
            {
                "id": "rule-transfer",
                "profile_id": None,
                "source_type": "amazon_transaction_upload",
                "match_spec": {"type": "Transfer"},
                "match_operator": "exact_fields",
                "target_bucket": "non_pnl_transfer",
                "priority": 10,
            },
        ])
        import_months_insert = _chain_table([{"id": "im-1"}])
        raw_rows_insert = _chain_table([{}])
        ledger_insert = _chain_table([{}])
        import_months_update = _chain_table([{"id": "im-1", "is_active": True}])

        call_counts: dict[str, int] = {}

        def table_router(name: str) -> MagicMock:
            call_counts.setdefault(name, 0)
            call_counts[name] += 1

            if name == "monthly_pnl_profiles":
                return profiles
            if name == "monthly_pnl_mapping_rules":
                return rules
            if name == "monthly_pnl_imports":
                count = call_counts[name]
                if count == 1:
                    return imports_no_dup  # duplicate check
                elif count == 2:
                    return imports_insert  # create
                elif count <= 4:
                    return imports_update  # status updates (running, success)
                else:
                    return imports_final  # re-read for response
            if name == "monthly_pnl_import_months":
                count = call_counts[name]
                # insert per month (1, 3), update per month (2, 4)
                if count in (1, 3):
                    return import_months_insert
                else:
                    return import_months_update
            if name == "monthly_pnl_raw_rows":
                return raw_rows_insert
            if name == "monthly_pnl_ledger_entries":
                return ledger_insert
            return _chain_table()

        db = MagicMock()
        db.table.side_effect = table_router
        db.rpc.return_value = _chain_rpc()

        svc = TransactionImportService(db)
        result = svc.import_file(
            profile_id="p1",
            file_name="test.csv",
            file_bytes=SAMPLE_CSV.encode("utf-8"),
        )

        assert result["summary"]["total_raw_rows"] == 4
        assert result["summary"]["total_months"] == 2
        assert result["summary"]["period_start"] == "2026-01-01"
        assert result["summary"]["period_end"] == "2026-02-01"
        assert len(result["months"]) == 2

        # Activation should use RPC, not two separate updates
        assert db.rpc.call_count == 2  # one per month slice
        rpc_calls = db.rpc.call_args_list
        assert rpc_calls[0][0][0] == "pnl_activate_month_slice"
        assert rpc_calls[1][0][0] == "pnl_activate_month_slice"

        # Response should reflect final import state (re-read)
        assert result["import"]["import_status"] == "success"
        assert result["import"]["finished_at"] is not None

    def test_allows_retry_after_errored_import(self):
        """Same-SHA file with status 'error' should not be blocked."""
        profiles = _chain_table([{"id": "p1", "marketplace_code": "US"}])
        imports_dup_check = _chain_table([{"id": "old-imp", "import_status": "error"}])
        imports_insert = _chain_table([{"id": "imp-retry", "import_status": "pending"}])
        imports_update = _chain_table([{"id": "imp-retry", "import_status": "running"}])
        imports_final = _chain_table([{"id": "imp-retry", "import_status": "success"}])
        rules = _chain_table([])
        import_months_insert = _chain_table([{"id": "im-1"}])
        import_months_update = _chain_table([{}])
        raw_rows_insert = _chain_table([{}])
        ledger_insert = _chain_table([{}])

        call_counts: dict[str, int] = {}

        def table_router(name: str) -> MagicMock:
            call_counts.setdefault(name, 0)
            call_counts[name] += 1
            if name == "monthly_pnl_profiles":
                return profiles
            if name == "monthly_pnl_mapping_rules":
                return rules
            if name == "monthly_pnl_imports":
                count = call_counts[name]
                if count == 1:
                    return imports_dup_check
                elif count == 2:
                    return imports_insert
                elif count <= 4:
                    return imports_update
                else:
                    return imports_final
            if name == "monthly_pnl_import_months":
                count = call_counts[name]
                if count == 1:
                    return import_months_insert
                else:
                    return import_months_update
            if name == "monthly_pnl_raw_rows":
                return raw_rows_insert
            if name == "monthly_pnl_ledger_entries":
                return ledger_insert
            return _chain_table()

        csv_data = (
            '"date/time","type","order id","sku","description","product sales","total",'
            '"Transaction Release Date"\n'
            '"Jan 15, 2026","Order","111","SKU1","Widget","10.00","10.00","Jan 20, 2026"\n'
        ).encode("utf-8")

        db = MagicMock()
        db.table.side_effect = table_router
        db.rpc.return_value = _chain_rpc()

        svc = TransactionImportService(db)
        result = svc.import_file(
            profile_id="p1",
            file_name="test.csv",
            file_bytes=csv_data,
        )
        assert result["summary"]["total_raw_rows"] == 1

    def test_marks_stale_running_duplicate_as_error_and_allows_retry(self):
        profiles = _chain_table([{"id": "p1", "marketplace_code": "US"}])
        imports_dup_check = _chain_table([{
            "id": "stale-imp",
            "import_status": "running",
            "created_at": "2026-01-10T00:00:00+00:00",
            "started_at": "2026-01-10T00:00:00+00:00",
        }])
        imports_insert = _chain_table([{"id": "imp-retry", "import_status": "pending"}])
        imports_update = _chain_table([{"id": "imp-retry", "import_status": "running"}])
        imports_final = _chain_table([{"id": "imp-retry", "import_status": "success"}])
        rules = _chain_table([])
        import_months_insert = _chain_table([{"id": "im-1"}])
        import_months_update = _chain_table([{}])
        raw_rows_insert = _chain_table([{}])
        ledger_insert = _chain_table([{}])

        call_counts: dict[str, int] = {}

        def table_router(name: str) -> MagicMock:
            call_counts.setdefault(name, 0)
            call_counts[name] += 1
            if name == "monthly_pnl_profiles":
                return profiles
            if name == "monthly_pnl_mapping_rules":
                return rules
            if name == "monthly_pnl_imports":
                count = call_counts[name]
                if count == 1:
                    return imports_dup_check
                elif count == 2:
                    return imports_insert
                elif count <= 4:
                    return imports_update
                else:
                    return imports_final
            if name == "monthly_pnl_import_months":
                count = call_counts[name]
                if count == 1:
                    return import_months_insert
                return import_months_update
            if name == "monthly_pnl_raw_rows":
                return raw_rows_insert
            if name == "monthly_pnl_ledger_entries":
                return ledger_insert
            return _chain_table()

        csv_data = (
            '"date/time","type","order id","sku","description","product sales","total",'
            '"Transaction Release Date"\n'
            '"Jan 15, 2026","Order","111","SKU1","Widget","10.00","10.00","Jan 20, 2026"\n'
        ).encode("utf-8")

        db = MagicMock()
        db.table.side_effect = table_router
        db.rpc.return_value = _chain_rpc()

        svc = TransactionImportService(db)
        svc._mark_import_stale_error = MagicMock()
        result = svc.import_file(
            profile_id="p1",
            file_name="test.csv",
            file_bytes=csv_data,
        )

        assert result["summary"]["total_raw_rows"] == 1
        svc._mark_import_stale_error.assert_called_once_with("stale-imp")

    def test_allows_reimport_after_success_and_deactivates_stale_months(self):
        """A successful import can be replaced by re-uploading the same file."""
        profiles = _chain_table([{"id": "p1", "marketplace_code": "US"}])
        imports_dup_check = _chain_table([{
            "id": "old-imp",
            "import_status": "success",
            "created_at": "2026-01-10T00:00:00+00:00",
        }])
        imports_insert = _chain_table([{"id": "imp-new", "import_status": "pending"}])
        imports_update = _chain_table([{}])
        imports_final = _chain_table([{"id": "imp-new", "import_status": "success"}])
        rules = _chain_table([])
        import_months_insert = _chain_table([{"id": "im-new"}])
        raw_rows_insert = _chain_table([{}])
        ledger_insert = _chain_table([{}])

        stale_month_updates: list[dict] = []
        import_months_update = _chain_table([{}])
        original_update = import_months_update.update

        def tracking_update(payload):
            stale_month_updates.append(payload)
            return original_update(payload)

        import_months_update.update = tracking_update
        old_import_active_months = _chain_table([
            {"id": "old-dec", "entry_month": "2025-12-01"},
            {"id": "old-jan", "entry_month": "2026-01-01"},
        ])

        created_import_payloads: list[dict] = []

        def insert_with_capture(payload):
            created_import_payloads.append(payload)
            return imports_insert

        imports_insert.insert = insert_with_capture

        call_counts: dict[str, int] = {}

        def table_router(name: str) -> MagicMock:
            call_counts.setdefault(name, 0)
            call_counts[name] += 1
            if name == "monthly_pnl_profiles":
                return profiles
            if name == "monthly_pnl_mapping_rules":
                return rules
            if name == "monthly_pnl_imports":
                count = call_counts[name]
                if count == 1:
                    return imports_dup_check
                if count == 2:
                    return imports_insert
                if count <= 4:
                    return imports_update
                return imports_final
            if name == "monthly_pnl_import_months":
                count = call_counts[name]
                if count == 1:
                    return import_months_insert
                if count == 2:
                    return import_months_update
                if count == 3:
                    return old_import_active_months
                return import_months_update
            if name == "monthly_pnl_raw_rows":
                return raw_rows_insert
            if name == "monthly_pnl_ledger_entries":
                return ledger_insert
            return _chain_table()

        csv_data = (
            '"date/time","type","order id","sku","description","product sales","total","Transaction Release Date"\n'
            '"Dec 15, 2025","Order","111","SKU1","Widget","10.00","10.00","Jan 02, 2026"\n'
        ).encode("utf-8")

        db = MagicMock()
        db.table.side_effect = table_router
        db.rpc.return_value = _chain_rpc()

        svc = TransactionImportService(db)
        result = svc.import_file(
            profile_id="p1",
            file_name="test.csv",
            file_bytes=csv_data,
        )

        assert result["summary"]["total_raw_rows"] == 1
        assert created_import_payloads[0]["supersedes_import_id"] == "old-imp"
        assert {"is_active": False} in stale_month_updates

    def test_reimport_retries_after_legacy_unique_index_conflict(self):
        """Re-import should recover if the old SHA unique index is still present."""
        profiles = _chain_table([{"id": "p1", "marketplace_code": "US"}])
        imports_dup_check = _chain_table([{
            "id": "old-imp",
            "import_status": "success",
            "created_at": "2026-01-10T00:00:00+00:00",
        }])
        imports_update = _chain_table([{}])
        imports_final = _chain_table([{"id": "imp-new", "import_status": "success"}])
        rules = _chain_table([])
        import_months_insert = _chain_table([{"id": "im-new"}])
        import_months_update = _chain_table([{}])
        raw_rows_insert = _chain_table([{}])
        ledger_insert = _chain_table([{}])

        class InsertConflictThenSuccess:
            def __init__(self):
                self.calls = 0

            def insert(self, _payload):
                self.calls += 1
                return self

            def execute(self):
                if self.calls == 1:
                    raise _pg_error(
                        'duplicate key value violates unique constraint "uq_monthly_pnl_imports_profile_source_sha256"'
                    )
                return MagicMock(data=[{"id": "imp-new", "import_status": "pending"}])

            def update(self, _payload):
                return self

            def eq(self, *_args, **_kwargs):
                return self

            def select(self, *_args, **_kwargs):
                return self

            def order(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

        imports_insert = InsertConflictThenSuccess()
        cleared_hash_payloads: list[dict] = []
        old_import_active_months = _chain_table([])

        def update_capture(payload):
            cleared_hash_payloads.append(payload)
            return imports_update

        import_update_capture = _chain_table([{}])
        import_update_capture.update = update_capture

        call_counts: dict[str, int] = {}

        def table_router(name: str) -> MagicMock:
            call_counts.setdefault(name, 0)
            call_counts[name] += 1
            if name == "monthly_pnl_profiles":
                return profiles
            if name == "monthly_pnl_mapping_rules":
                return rules
            if name == "monthly_pnl_imports":
                count = call_counts[name]
                if count == 1:
                    return imports_dup_check
                if count in (2, 4):
                    return imports_insert
                if count == 3:
                    return import_update_capture
                if count <= 6:
                    return imports_update
                return imports_final
            if name == "monthly_pnl_import_months":
                count = call_counts[name]
                if count == 1:
                    return import_months_insert
                if count == 2:
                    return import_months_update
                if count == 3:
                    return old_import_active_months
                return import_months_update
            if name == "monthly_pnl_raw_rows":
                return raw_rows_insert
            if name == "monthly_pnl_ledger_entries":
                return ledger_insert
            return _chain_table()

        csv_data = (
            '"date/time","type","order id","sku","description","product sales","total","Transaction Release Date"\n'
            '"Dec 15, 2025","Order","111","SKU1","Widget","10.00","10.00","Jan 02, 2026"\n'
        ).encode("utf-8")

        db = MagicMock()
        db.table.side_effect = table_router
        db.rpc.return_value = _chain_rpc()

        svc = TransactionImportService(db)
        result = svc.import_file(
            profile_id="p1",
            file_name="test.csv",
            file_bytes=csv_data,
        )

        assert result["import"]["import_status"] == "success"
        assert {"source_file_sha256": None} in cleared_hash_payloads

    def test_insert_ledger_entries_retries_and_splits_on_transient_gateway_errors(self, monkeypatch):
        class FlakyLedgerInsertTable:
            def __init__(self):
                self.chunk_sizes: list[int] = []
                self.current_chunk_size = 0

            def insert(self, payload):
                self.current_chunk_size = len(payload)
                self.chunk_sizes.append(self.current_chunk_size)
                return self

            def execute(self):
                if self.current_chunk_size > 100:
                    raise _gateway_error()
                return MagicMock(data=[{}])

        flaky_table = FlakyLedgerInsertTable()
        db = MagicMock()
        db.table.return_value = flaky_table
        svc = TransactionImportService(db)

        monkeypatch.setattr("app.services.pnl.transaction_import.time.sleep", lambda *_args: None)

        entries = [
            LedgerEntry(
                entry_month=date(2025, 8, 1),
                posted_at=None,
                order_id=f"order-{index}",
                sku="SKU1",
                raw_type="Order",
                raw_description="Widget",
                ledger_bucket="product_sales",
                amount=Decimal("1.00"),
                is_mapped=True,
                mapping_rule_id=None,
                source_row_index=index,
            )
            for index in range(250)
        ]

        svc._insert_ledger_entries(
            import_id="imp-1",
            import_month_id="im-1",
            profile_id="p1",
            entry_month=date(2025, 8, 1),
            entries=entries,
        )

        assert flaky_table.chunk_sizes[:4] == [250, 250, 125, 125]
        assert any(chunk_size <= 100 for chunk_size in flaky_table.chunk_sizes)

    def test_import_month_starts_as_pending(self):
        """Import month should be created with 'pending', not 'success'."""
        profiles = _chain_table([{"id": "p1", "marketplace_code": "US"}])
        imports_no_dup = _chain_table([])
        imports_insert = _chain_table([{"id": "imp-1"}])
        imports_update = _chain_table([{}])
        imports_final = _chain_table([{"id": "imp-1", "import_status": "success"}])
        rules = _chain_table([])
        import_months_insert = _chain_table([{"id": "im-1"}])
        import_months_update = _chain_table([{}])
        raw_rows_insert = _chain_table([{}])
        ledger_insert = _chain_table([{}])

        call_counts: dict[str, int] = {}
        import_month_insert_payloads: list[dict] = []

        def table_router(name: str) -> MagicMock:
            call_counts.setdefault(name, 0)
            call_counts[name] += 1
            if name == "monthly_pnl_profiles":
                return profiles
            if name == "monthly_pnl_mapping_rules":
                return rules
            if name == "monthly_pnl_imports":
                count = call_counts[name]
                if count == 1:
                    return imports_no_dup
                elif count == 2:
                    return imports_insert
                elif count <= 4:
                    return imports_update
                else:
                    return imports_final
            if name == "monthly_pnl_import_months":
                count = call_counts[name]
                if count == 1:
                    mock = _chain_table([{"id": "im-1"}])
                    original_insert = mock.insert
                    def capturing_insert(payload):
                        import_month_insert_payloads.append(payload)
                        return original_insert(payload)
                    mock.insert = capturing_insert
                    return mock
                else:
                    return import_months_update
            if name == "monthly_pnl_raw_rows":
                return raw_rows_insert
            if name == "monthly_pnl_ledger_entries":
                return ledger_insert
            return _chain_table()

        csv_data = (
            '"date/time","type","order id","sku","description","product sales","total",'
            '"Transaction Release Date"\n'
            '"Jan 15, 2026","Order","111","SKU1","Widget","10.00","10.00","Jan 20, 2026"\n'
        ).encode("utf-8")

        db = MagicMock()
        db.table.side_effect = table_router
        db.rpc.return_value = _chain_rpc()

        svc = TransactionImportService(db)
        svc.import_file(profile_id="p1", file_name="test.csv", file_bytes=csv_data)

        assert len(import_month_insert_payloads) == 1
        assert import_month_insert_payloads[0]["import_status"] == "pending"

    def test_activation_failure_marks_month_slice_error(self):
        """Activation RPC failure → month slice becomes 'error', not 'pending'."""
        profiles = _chain_table([{"id": "p1", "marketplace_code": "US"}])
        imports_no_dup = _chain_table([])
        imports_insert = _chain_table([{"id": "imp-1"}])
        imports_update = _chain_table([{}])
        rules = _chain_table([])
        import_months_insert = _chain_table([{"id": "im-1"}])
        raw_rows_insert = _chain_table([{}])
        ledger_insert = _chain_table([{}])

        # Track update calls on import_months
        import_month_status_updates: list[dict] = []
        import_months_update = _chain_table([{}])
        original_update = import_months_update.update
        def tracking_update(payload):
            import_month_status_updates.append(payload)
            return original_update(payload)
        import_months_update.update = tracking_update

        call_counts: dict[str, int] = {}

        def table_router(name: str) -> MagicMock:
            call_counts.setdefault(name, 0)
            call_counts[name] += 1
            if name == "monthly_pnl_profiles":
                return profiles
            if name == "monthly_pnl_mapping_rules":
                return rules
            if name == "monthly_pnl_imports":
                count = call_counts[name]
                if count == 1:
                    return imports_no_dup
                elif count == 2:
                    return imports_insert
                else:
                    return imports_update
            if name == "monthly_pnl_import_months":
                count = call_counts[name]
                if count == 1:
                    return import_months_insert
                else:
                    return import_months_update
            if name == "monthly_pnl_raw_rows":
                return raw_rows_insert
            if name == "monthly_pnl_ledger_entries":
                return ledger_insert
            return _chain_table()

        csv_data = (
            '"date/time","type","order id","sku","description","product sales","total",'
            '"Transaction Release Date"\n'
            '"Jan 15, 2026","Order","111","SKU1","Widget","10.00","10.00","Jan 20, 2026"\n'
        ).encode("utf-8")

        db = MagicMock()
        db.table.side_effect = table_router
        rpc_mock = MagicMock()
        rpc_mock.execute.side_effect = RuntimeError("RPC activation failed")
        db.rpc.return_value = rpc_mock

        svc = TransactionImportService(db)
        with pytest.raises(RuntimeError, match="RPC activation failed"):
            svc.import_file(profile_id="p1", file_name="test.csv", file_bytes=csv_data)

        # Month slice should be set to 'error', never to 'success'
        statuses = [u["import_status"] for u in import_month_status_updates]
        assert "error" in statuses
        assert "success" not in statuses

    def test_insert_failure_marks_month_slice_error(self):
        """Raw-row insert failure → month slice becomes 'error'."""
        profiles = _chain_table([{"id": "p1", "marketplace_code": "US"}])
        imports_no_dup = _chain_table([])
        imports_insert = _chain_table([{"id": "imp-1"}])
        imports_update = _chain_table([{}])
        rules = _chain_table([])
        import_months_insert = _chain_table([{"id": "im-1"}])

        # Track update calls on import_months
        import_month_status_updates: list[dict] = []
        import_months_update = _chain_table([{}])
        original_update = import_months_update.update
        def tracking_update(payload):
            import_month_status_updates.append(payload)
            return original_update(payload)
        import_months_update.update = tracking_update

        # Make raw_rows insert fail
        raw_rows_fail = _chain_table([])
        raw_rows_fail.insert.return_value = raw_rows_fail
        raw_rows_fail.execute.side_effect = RuntimeError("raw row insert failed")

        ledger_insert = _chain_table([{}])

        call_counts: dict[str, int] = {}

        def table_router(name: str) -> MagicMock:
            call_counts.setdefault(name, 0)
            call_counts[name] += 1
            if name == "monthly_pnl_profiles":
                return profiles
            if name == "monthly_pnl_mapping_rules":
                return rules
            if name == "monthly_pnl_imports":
                count = call_counts[name]
                if count == 1:
                    return imports_no_dup
                elif count == 2:
                    return imports_insert
                else:
                    return imports_update
            if name == "monthly_pnl_import_months":
                count = call_counts[name]
                if count == 1:
                    return import_months_insert
                else:
                    return import_months_update
            if name == "monthly_pnl_raw_rows":
                return raw_rows_fail
            if name == "monthly_pnl_ledger_entries":
                return ledger_insert
            return _chain_table()

        csv_data = (
            '"date/time","type","order id","sku","description","product sales","total",'
            '"Transaction Release Date"\n'
            '"Jan 15, 2026","Order","111","SKU1","Widget","10.00","10.00","Jan 20, 2026"\n'
        ).encode("utf-8")

        db = MagicMock()
        db.table.side_effect = table_router
        db.rpc.return_value = _chain_rpc()

        svc = TransactionImportService(db)
        with pytest.raises(RuntimeError, match="raw row insert failed"):
            svc.import_file(profile_id="p1", file_name="test.csv", file_bytes=csv_data)

        # Month slice should be set to 'error'
        statuses = [u["import_status"] for u in import_month_status_updates]
        assert "error" in statuses
        assert "success" not in statuses

    def test_successful_path_month_slice_ends_success(self):
        """Happy path: month slice ends at 'success' after activation."""
        profiles = _chain_table([{"id": "p1", "marketplace_code": "US"}])
        imports_no_dup = _chain_table([])
        imports_insert = _chain_table([{"id": "imp-1"}])
        imports_update = _chain_table([{}])
        imports_final = _chain_table([{"id": "imp-1", "import_status": "success"}])
        rules = _chain_table([])
        import_months_insert = _chain_table([{"id": "im-1"}])

        import_month_status_updates: list[dict] = []
        import_months_update = _chain_table([{}])
        original_update = import_months_update.update
        def tracking_update(payload):
            import_month_status_updates.append(payload)
            return original_update(payload)
        import_months_update.update = tracking_update

        raw_rows_insert = _chain_table([{}])
        ledger_insert = _chain_table([{}])

        call_counts: dict[str, int] = {}

        def table_router(name: str) -> MagicMock:
            call_counts.setdefault(name, 0)
            call_counts[name] += 1
            if name == "monthly_pnl_profiles":
                return profiles
            if name == "monthly_pnl_mapping_rules":
                return rules
            if name == "monthly_pnl_imports":
                count = call_counts[name]
                if count == 1:
                    return imports_no_dup
                elif count == 2:
                    return imports_insert
                elif count <= 4:
                    return imports_update
                else:
                    return imports_final
            if name == "monthly_pnl_import_months":
                count = call_counts[name]
                if count == 1:
                    return import_months_insert
                else:
                    return import_months_update
            if name == "monthly_pnl_raw_rows":
                return raw_rows_insert
            if name == "monthly_pnl_ledger_entries":
                return ledger_insert
            return _chain_table()

        csv_data = (
            '"date/time","type","order id","sku","description","product sales","total",'
            '"Transaction Release Date"\n'
            '"Jan 15, 2026","Order","111","SKU1","Widget","10.00","10.00","Jan 20, 2026"\n'
        ).encode("utf-8")

        db = MagicMock()
        db.table.side_effect = table_router
        db.rpc.return_value = _chain_rpc()

        svc = TransactionImportService(db)
        result = svc.import_file(profile_id="p1", file_name="test.csv", file_bytes=csv_data)

        # Month slice should have exactly one 'success' update, no 'error'
        statuses = [u["import_status"] for u in import_month_status_updates]
        assert statuses == ["success"]
        assert result["months"][0]["is_active"] is True


# ── Multi-month slicing test ─────────────────────────────────────────


class TestMultiMonthSlicing:
    def test_rows_are_grouped_by_canonical_month(self):
        header_values, header_map, data_rows = parse_transaction_csv(SAMPLE_CSV.encode("utf-8"))
        raw_rows = parse_raw_rows(header_values, header_map, data_rows)

        months: dict[date, list[ParsedRawRow]] = {}
        for rr in raw_rows:
            if rr.entry_month:
                months.setdefault(rr.entry_month, []).append(rr)

        assert date(2026, 1, 1) in months
        assert date(2026, 2, 1) in months
        assert len(months[date(2026, 1, 1)]) == 2  # Order + Refund
        assert len(months[date(2026, 2, 1)]) == 2  # Service Fee + Transfer
