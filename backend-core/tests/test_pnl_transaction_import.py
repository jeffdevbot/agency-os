"""Tests for Monthly P&L transaction import pipeline.

Covers CSV parsing, normalization, mapping rule evaluation, ledger
expansion, month slicing, and the import orchestration service.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.services.pnl.profiles import PNLDuplicateFileError, PNLNotFoundError, PNLValidationError
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

    def test_canonical_month_uses_release_date(self):
        """Transaction Release Date is the canonical month, not date/time."""
        header_values, header_map, data_rows = parse_transaction_csv(SAMPLE_CSV.encode("utf-8"))
        raw_rows = parse_raw_rows(header_values, header_map, data_rows)

        # Row 0: date/time = Jan 15, release = Jan 20 → both January → Jan 2026
        assert raw_rows[0].entry_month == date(2026, 1, 1)
        # Row 2: date/time = Feb 01, release = Feb 05 → Feb 2026
        assert raw_rows[2].entry_month == date(2026, 2, 1)

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
        assert match.target_bucket == "other_transaction_fees"

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

    def test_other_column_on_order_row_is_unmapped(self):
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
        unmapped = [e for e in entries if not e.is_mapped]
        assert len(unmapped) == 1
        assert unmapped[0].ledger_bucket == "unmapped"
        assert unmapped[0].amount == Decimal("-2.00")


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


class TestTransactionImportService:
    def test_rejects_duplicate_file(self):
        profiles = _chain_table([{"id": "p1", "marketplace_code": "US"}])
        imports = _chain_table([{"id": "existing-import", "import_status": "success"}])
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

    def test_duplicate_blocks_on_success_status(self):
        """Same-SHA file with status 'success' should still be blocked."""
        profiles = _chain_table([{"id": "p1", "marketplace_code": "US"}])
        imports = _chain_table([{"id": "existing-import", "import_status": "success"}])
        db = _db_with_tables(monthly_pnl_profiles=profiles, monthly_pnl_imports=imports)

        svc = TransactionImportService(db)
        with pytest.raises(PNLDuplicateFileError, match="already been imported"):
            svc.import_file(
                profile_id="p1",
                file_name="test.csv",
                file_bytes=SAMPLE_CSV.encode("utf-8"),
            )

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
