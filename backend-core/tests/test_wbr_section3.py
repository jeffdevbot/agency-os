"""Tests for WBR Section 3 – inventory aggregation, returns aggregation, WOS, return %."""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import MagicMock

import pytest

import app.services.wbr.section3_report as report_module
from app.services.wbr.windsor_inventory_sync import WindsorInventorySyncService
from app.services.wbr.windsor_returns_sync import WindsorReturnsSyncService
from app.services.wbr.section3_report import Section3ReportService, _previous_full_weeks


def _chain_table(response_data: list[dict] | None = None) -> MagicMock:
    table = MagicMock()
    table.select.return_value = table
    table.eq.return_value = table
    table.gte.return_value = table
    table.lte.return_value = table
    table.range.return_value = table
    table.order.return_value = table
    table.limit.return_value = table
    table.execute.return_value = MagicMock(data=response_data if response_data is not None else [])
    return table


def _multi_table_db(mapping: dict[str, list[MagicMock]]) -> MagicMock:
    iterators = {name: iter(tables) for name, tables in mapping.items()}

    def router(name: str) -> MagicMock:
        return next(iterators[name])

    db = MagicMock()
    db.table.side_effect = router
    return db


# ---- Inventory aggregation tests ----


def test_inventory_aggregation_merges_restock_and_afn():
    svc = WindsorInventorySyncService(MagicMock())

    afn_rows = [
        {
            "account_id": "ACC-US",
            "fba_myi_unsuppressed_inventory_data__asin": "B001",
            "fba_myi_unsuppressed_inventory_data__afn_reserved_quantity": "10",
        },
    ]
    restock_rows = [
        {
            "account_id": "ACC-US",
            "restock_inventory_recommendations_report__asin": "B001",
            "restock_inventory_recommendations_report__available": "100",
            "restock_inventory_recommendations_report__working": "5",
            "restock_inventory_recommendations_report__fc_transfer": "3",
            "restock_inventory_recommendations_report__fc_processing": "2",
            "restock_inventory_recommendations_report__receiving": "15",
            "restock_inventory_recommendations_report__shipped": "8",
            "restock_inventory_recommendations_report__condition": "New",
        },
    ]

    facts, afn_only = svc._aggregate_inventory(
        afn_rows=afn_rows,
        restock_rows=restock_rows,
        expected_account_id="ACC-US",
    )

    assert len(facts) == 1
    assert afn_only == []
    f = facts[0]
    assert f.child_asin == "B001"
    assert f.instock == 100
    assert f.working == 5
    assert f.reserved_quantity == 10
    assert f.fc_transfer == 3
    assert f.fc_processing == 2
    assert f.reserved_plus_fc_transfer == 10 + 3 + 2  # reserved + fc_transfer + fc_processing
    assert f.receiving == 15
    assert f.intransit == 8
    assert f.receiving_plus_intransit == 15 + 8
    assert f.source_row_count == 2  # 1 AFN + 1 restock


def test_inventory_aggregation_filters_non_new_condition():
    svc = WindsorInventorySyncService(MagicMock())

    restock_rows = [
        {
            "account_id": "ACC-US",
            "restock_inventory_recommendations_report__asin": "B001",
            "restock_inventory_recommendations_report__available": "100",
            "restock_inventory_recommendations_report__condition": "New",
        },
        {
            "account_id": "ACC-US",
            "restock_inventory_recommendations_report__asin": "B001",
            "restock_inventory_recommendations_report__available": "50",
            "restock_inventory_recommendations_report__condition": "Used",
        },
    ]

    facts, afn_only = svc._aggregate_inventory(
        afn_rows=[],
        restock_rows=restock_rows,
        expected_account_id="ACC-US",
    )

    assert len(facts) == 1
    assert facts[0].instock == 100  # only the New row
    assert afn_only == []


def test_inventory_aggregation_sums_duplicate_asins():
    svc = WindsorInventorySyncService(MagicMock())

    restock_rows = [
        {
            "account_id": "ACC-US",
            "restock_inventory_recommendations_report__asin": "B001",
            "restock_inventory_recommendations_report__available": "60",
            "restock_inventory_recommendations_report__working": "0",
            "restock_inventory_recommendations_report__fc_transfer": "0",
            "restock_inventory_recommendations_report__fc_processing": "0",
            "restock_inventory_recommendations_report__receiving": "0",
            "restock_inventory_recommendations_report__shipped": "0",
            "restock_inventory_recommendations_report__condition": "New",
        },
        {
            "account_id": "ACC-US",
            "restock_inventory_recommendations_report__asin": "B001",
            "restock_inventory_recommendations_report__available": "40",
            "restock_inventory_recommendations_report__working": "0",
            "restock_inventory_recommendations_report__fc_transfer": "0",
            "restock_inventory_recommendations_report__fc_processing": "0",
            "restock_inventory_recommendations_report__receiving": "0",
            "restock_inventory_recommendations_report__shipped": "0",
            "restock_inventory_recommendations_report__condition": "New",
        },
    ]

    facts, afn_only = svc._aggregate_inventory(
        afn_rows=[],
        restock_rows=restock_rows,
        expected_account_id="ACC-US",
    )

    assert len(facts) == 1
    assert facts[0].instock == 100
    assert facts[0].source_row_count == 2
    assert afn_only == []


def test_inventory_aggregation_skips_wrong_account():
    svc = WindsorInventorySyncService(MagicMock())

    afn_rows = [
        {
            "account_id": "OTHER-US",
            "fba_myi_unsuppressed_inventory_data__asin": "B001",
            "fba_myi_unsuppressed_inventory_data__afn_reserved_quantity": "999",
        },
    ]

    facts, afn_only = svc._aggregate_inventory(
        afn_rows=afn_rows,
        restock_rows=[],
        expected_account_id="ACC-US",
    )

    # Wrong-account AFN rows are ignored entirely (not counted as afn_only).
    assert len(facts) == 0
    assert afn_only == []


def test_inventory_aggregation_afn_only_asin_excluded():
    """v1 rule: AFN-only ASINs (no New restock row) are excluded from facts
    but tracked in afn_only_asins for QA visibility."""
    svc = WindsorInventorySyncService(MagicMock())

    afn_rows = [
        {
            "account_id": "ACC-US",
            "fba_myi_unsuppressed_inventory_data__asin": "B099",
            "fba_myi_unsuppressed_inventory_data__afn_reserved_quantity": "50",
        },
    ]

    facts, afn_only = svc._aggregate_inventory(
        afn_rows=afn_rows,
        restock_rows=[],
        expected_account_id="ACC-US",
    )

    assert len(facts) == 0
    assert afn_only == ["B099"]


def test_inventory_aggregation_afn_reserved_excluded_for_used_only_asin():
    """An ASIN that appears in AFN but only has Used restock rows should be
    excluded entirely – reserved quantity must not leak in."""
    svc = WindsorInventorySyncService(MagicMock())

    afn_rows = [
        {
            "account_id": "ACC-US",
            "fba_myi_unsuppressed_inventory_data__asin": "B001",
            "fba_myi_unsuppressed_inventory_data__afn_reserved_quantity": "20",
        },
    ]
    restock_rows = [
        {
            "account_id": "ACC-US",
            "restock_inventory_recommendations_report__asin": "B001",
            "restock_inventory_recommendations_report__available": "100",
            "restock_inventory_recommendations_report__condition": "Used",
        },
    ]

    facts, afn_only = svc._aggregate_inventory(
        afn_rows=afn_rows,
        restock_rows=restock_rows,
        expected_account_id="ACC-US",
    )

    # B001 has Used restock only → excluded from facts.
    # AFN reserved for B001 is tracked as afn_only since no New restock exists.
    assert len(facts) == 0
    assert afn_only == ["B001"]


def test_inventory_aggregation_empty_condition_treated_as_new():
    """Restock rows with no condition field should be included."""
    svc = WindsorInventorySyncService(MagicMock())

    restock_rows = [
        {
            "account_id": "ACC-US",
            "restock_inventory_recommendations_report__asin": "B001",
            "restock_inventory_recommendations_report__available": "50",
        },
    ]

    facts, afn_only = svc._aggregate_inventory(
        afn_rows=[],
        restock_rows=restock_rows,
        expected_account_id="ACC-US",
    )

    assert len(facts) == 1
    assert facts[0].instock == 50
    assert afn_only == []


def test_inventory_aggregation_mixed_included_and_excluded():
    """v1 inclusion rule end-to-end: B001 (New restock + AFN) is included
    with reserved enriched from AFN; B099 (AFN-only, no restock) is excluded
    but tracked in afn_only."""
    svc = WindsorInventorySyncService(MagicMock())

    afn_rows = [
        {
            "account_id": "ACC-US",
            "fba_myi_unsuppressed_inventory_data__asin": "B001",
            "fba_myi_unsuppressed_inventory_data__afn_reserved_quantity": "10",
        },
        {
            "account_id": "ACC-US",
            "fba_myi_unsuppressed_inventory_data__asin": "B099",
            "fba_myi_unsuppressed_inventory_data__afn_reserved_quantity": "30",
        },
    ]
    restock_rows = [
        {
            "account_id": "ACC-US",
            "restock_inventory_recommendations_report__asin": "B001",
            "restock_inventory_recommendations_report__available": "200",
            "restock_inventory_recommendations_report__condition": "New",
        },
    ]

    facts, afn_only = svc._aggregate_inventory(
        afn_rows=afn_rows,
        restock_rows=restock_rows,
        expected_account_id="ACC-US",
    )

    assert len(facts) == 1
    assert facts[0].child_asin == "B001"
    assert facts[0].instock == 200
    assert facts[0].reserved_quantity == 10  # enriched from AFN
    assert facts[0].source_row_count == 2   # 1 AFN + 1 restock

    assert afn_only == ["B099"]


def test_inventory_aggregation_no_restock_with_afn_reserved():
    """ASIN with New restock but no AFN row → reserved_quantity is 0."""
    svc = WindsorInventorySyncService(MagicMock())

    restock_rows = [
        {
            "account_id": "ACC-US",
            "restock_inventory_recommendations_report__asin": "B001",
            "restock_inventory_recommendations_report__available": "50",
            "restock_inventory_recommendations_report__condition": "New",
        },
    ]

    facts, afn_only = svc._aggregate_inventory(
        afn_rows=[],
        restock_rows=restock_rows,
        expected_account_id="ACC-US",
    )

    assert len(facts) == 1
    assert facts[0].reserved_quantity == 0
    assert afn_only == []


# ---- Returns aggregation tests ----


def test_returns_aggregation_sums_by_date_asin():
    svc = WindsorReturnsSyncService(MagicMock())

    rows = [
        {
            "account_id": "ACC-US",
            "fba_fulfillment_customer_returns_data__asin": "B001",
            "fba_fulfillment_customer_returns_data__quantity": "2",
            "fba_fulfillment_customer_returns_data__return_date": "2026-03-05",
        },
        {
            "account_id": "ACC-US",
            "fba_fulfillment_customer_returns_data__asin": "B001",
            "fba_fulfillment_customer_returns_data__quantity": "1",
            "fba_fulfillment_customer_returns_data__return_date": "2026-03-05",
        },
        {
            "account_id": "ACC-US",
            "fba_fulfillment_customer_returns_data__asin": "B001",
            "fba_fulfillment_customer_returns_data__quantity": "3",
            "fba_fulfillment_customer_returns_data__return_date": "2026-03-06",
        },
    ]

    facts = svc._aggregate_returns(rows, expected_account_id="ACC-US")

    assert len(facts) == 2
    day5 = next(f for f in facts if f.return_date == date(2026, 3, 5))
    assert day5.return_units == 3
    assert day5.source_row_count == 2

    day6 = next(f for f in facts if f.return_date == date(2026, 3, 6))
    assert day6.return_units == 3
    assert day6.source_row_count == 1


def test_returns_aggregation_normalizes_asin_case():
    svc = WindsorReturnsSyncService(MagicMock())

    rows = [
        {
            "account_id": "ACC-US",
            "fba_fulfillment_customer_returns_data__asin": "b001",
            "fba_fulfillment_customer_returns_data__quantity": "1",
            "fba_fulfillment_customer_returns_data__return_date": "2026-03-05",
        },
    ]

    facts = svc._aggregate_returns(rows, expected_account_id="ACC-US")
    assert facts[0].child_asin == "B001"


def test_returns_aggregation_falls_back_to_date_field():
    svc = WindsorReturnsSyncService(MagicMock())

    rows = [
        {
            "account_id": "ACC-US",
            "fba_fulfillment_customer_returns_data__asin": "B001",
            "fba_fulfillment_customer_returns_data__quantity": "1",
            "date": "2026-03-05",
        },
    ]

    facts = svc._aggregate_returns(rows, expected_account_id="ACC-US")
    assert len(facts) == 1
    assert facts[0].return_date == date(2026, 3, 5)


# ---- WOS formula tests ----


def test_wos_formula():
    """
    WOS = (instock + reserved_fc_transfer + receiving_intransit) / avg weekly unit sales (4 weeks)
    """
    # Total supply = 100 + 15 + 23 = 138
    # Unit sales across 4 weeks: 10, 20, 30, 40 = 100 total, avg 25/week
    # WOS = 138 / 25 = 5.52, rounded to 6
    instock = 100
    reserved_plus_fc_transfer = 15
    receiving_plus_intransit = 23
    total_supply = instock + reserved_plus_fc_transfer + receiving_plus_intransit

    weekly_sales = [10, 20, 30, 40]
    avg_weekly = sum(weekly_sales) / len(weekly_sales)
    wos = round(total_supply / avg_weekly, 0)

    assert total_supply == 138
    assert avg_weekly == 25.0
    assert wos == 6.0


def test_wos_zero_sales_returns_none():
    """When avg weekly unit sales is 0, WOS should be None."""
    total_supply = 100
    avg_weekly = 0
    wos = None if avg_weekly == 0 else round(total_supply / avg_weekly, 0)
    assert wos is None


# ---- Return % formula tests ----


def test_return_rate_formula():
    """
    Return % = avg returns (2 weeks) / avg unit sales (2 weeks)
    """
    returns_w1 = 5
    returns_w2 = 3
    sales_w1 = 100
    sales_w2 = 80

    avg_returns = (returns_w1 + returns_w2) / 2
    avg_sales = (sales_w1 + sales_w2) / 2

    return_rate = round(avg_returns / avg_sales, 4)

    assert avg_returns == 4.0
    assert avg_sales == 90.0
    assert return_rate == 0.0444


def test_return_rate_zero_sales_returns_none():
    """When avg unit sales is 0, return % should be None."""
    avg_returns = 5.0
    avg_sales = 0.0
    return_rate = None if avg_sales == 0 else round(avg_returns / avg_sales, 4)
    assert return_rate is None


def test_return_rate_over_100_percent_allowed():
    """Low-volume SKUs with delayed returns can exceed 100%."""
    returns_w1 = 10
    returns_w2 = 8
    sales_w1 = 2
    sales_w2 = 3

    avg_returns = (returns_w1 + returns_w2) / 2
    avg_sales = (sales_w1 + sales_w2) / 2
    return_rate = round(avg_returns / avg_sales, 4)

    assert return_rate > 1.0  # > 100%
    assert return_rate == 3.6


# ---- Week bucket generation ----


def test_previous_full_weeks_returns_correct_count():
    buckets = _previous_full_weeks("sunday", 4)
    assert len(buckets) == 4
    for bucket in buckets:
        delta = bucket.end - bucket.start
        assert delta.days == 6  # each bucket is 7 days


def test_previous_full_weeks_monday_start():
    buckets = _previous_full_weeks("monday", 2)
    assert len(buckets) == 2
    for bucket in buckets:
        assert bucket.start.weekday() == 0  # Monday


def test_build_report_paginates_business_facts(monkeypatch):
    class _FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 3, 13, 12, 0, 0, tzinfo=tz or UTC)

    monkeypatch.setattr(report_module, "datetime", _FakeDateTime)

    first_page = [
        {
            "report_date": "2026-03-02",
            "child_asin": "ASIN1",
            "unit_sales": 1,
        }
        for _ in range(1000)
    ]
    second_page = [
        {
            "report_date": "2026-02-24",
            "child_asin": "ASIN1",
            "unit_sales": 1,
        }
        for _ in range(100)
    ]

    db = _multi_table_db(
        {
            "wbr_profiles": [_chain_table([{"id": "profile-1", "week_start_day": "monday"}])],
            "wbr_rows": [
                _chain_table(
                    [
                        {
                            "id": "leaf-1",
                            "row_label": "Screen Shine | Pro",
                            "row_kind": "leaf",
                            "parent_row_id": None,
                            "sort_order": 1,
                            "active": True,
                        }
                    ]
                )
            ],
            "wbr_asin_row_map": [_chain_table([{"child_asin": "ASIN1", "row_id": "leaf-1"}])],
            "wbr_asin_exclusions": [_chain_table([])],
            "wbr_inventory_asin_snapshots": [_chain_table([{"snapshot_date": "2026-03-16"}]), _chain_table([])],
            "wbr_returns_asin_daily": [_chain_table([])],
            "wbr_business_asin_daily": [_chain_table(first_page), _chain_table(second_page)],
        }
    )

    report = Section3ReportService(db).build_report("profile-1", weeks=4)

    row = report["rows"][0]
    assert row["_unit_sales_4w"] == 1100
    assert row["_unit_sales_2w"] == 1100


def test_build_report_ignores_excluded_inventory_and_sales(monkeypatch):
    class _FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 3, 13, 12, 0, 0, tzinfo=tz or UTC)

    monkeypatch.setattr(report_module, "datetime", _FakeDateTime)

    db = _multi_table_db(
        {
            "wbr_profiles": [_chain_table([{"id": "profile-1", "week_start_day": "monday"}])],
            "wbr_rows": [_chain_table([])],
            "wbr_asin_row_map": [_chain_table([])],
            "wbr_asin_exclusions": [_chain_table([{"child_asin": "EXCLUDED1"}])],
            "wbr_inventory_asin_snapshots": [
                _chain_table([{"snapshot_date": "2026-03-16"}]),
                _chain_table(
                    [
                        {
                            "child_asin": "EXCLUDED1",
                            "instock": 10,
                            "working": 1,
                            "reserved_plus_fc_transfer": 2,
                            "receiving_plus_intransit": 3,
                            "source_row_count": 1,
                        }
                    ]
                ),
            ],
            "wbr_returns_asin_daily": [
                _chain_table(
                    [
                        {
                            "return_date": "2026-03-08",
                            "child_asin": "EXCLUDED1",
                            "return_units": 2,
                        }
                    ]
                )
            ],
            "wbr_business_asin_daily": [
                _chain_table(
                    [
                        {
                            "report_date": "2026-03-05",
                            "child_asin": "EXCLUDED1",
                            "unit_sales": 5,
                        }
                    ]
                )
            ],
        }
    )

    report = Section3ReportService(db).build_report("profile-1", weeks=4)

    assert report["qa"]["unmapped_inventory_asin_count"] == 0
    assert report["qa"]["inventory_fact_count"] == 1
    assert report["qa"]["returns_fact_count"] == 1
    assert report["qa"]["business_fact_count"] == 1
    assert report["rows"] == []
