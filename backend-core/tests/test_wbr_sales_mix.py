"""Tests for the Sales Mix report service."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.services.wbr.profiles import WBRNotFoundError, WBRValidationError
from app.services.wbr.sales_mix import SalesMixService


def _chain_table(response_data: list[dict] | None = None) -> MagicMock:
    table = MagicMock()
    for attr in ("select", "insert", "update", "delete", "eq", "in_", "gte", "lte", "order", "limit", "range"):
        getattr(table, attr).return_value = table
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


def _last_full_window(weeks: int) -> tuple[date, date]:
    """Return the last `weeks` complete Sunday-start weeks ending yesterday-or-earlier.

    Mirrors the snapping the service does so we can produce dates that
    will end up inside the bucket window even when the test runs in the
    middle of a week."""

    today = date.today()
    weekday = (today.weekday() + 1) % 7  # Sun=0
    current_week_start = today - timedelta(days=weekday)
    last_week_end = current_week_start - timedelta(days=1)
    date_to = last_week_end
    date_from = last_week_end - timedelta(days=7 * weeks - 1)
    return date_from, date_to


PROFILE = {
    "id": "p1",
    "display_name": "Test Brand",
    "marketplace_code": "US",
    "week_start_day": "sunday",
}


def _build_db(
    *,
    rows: list[dict] | None = None,
    mappings: list[dict] | None = None,
    exclusions: list[dict] | None = None,
    asin_map: list[dict] | None = None,
    ads_facts: list[dict] | None = None,
    business_facts: list[dict] | None = None,
) -> MagicMock:
    return _multi_table_db(
        {
            "wbr_profiles": [_chain_table([PROFILE])],
            "wbr_rows": [_chain_table(rows or [])],
            "wbr_pacvue_campaign_map": [_chain_table(mappings or [])],
            "wbr_campaign_exclusions": [_chain_table(exclusions or [])],
            "wbr_asin_row_map": [_chain_table(asin_map or [])],
            "wbr_ads_campaign_daily": [_chain_table(ads_facts or [])],
            "wbr_business_asin_daily": [_chain_table(business_facts or [])],
        }
    )


class TestBuildReport:
    def test_classifies_brand_vs_category_via_def_goal(self):
        date_from, date_to = _last_full_window(2)
        sample_day = date_to.isoformat()
        db = _build_db(
            rows=[
                {"id": "leaf-brand", "row_kind": "leaf", "active": True, "row_label": "Hero", "parent_row_id": None, "sort_order": 10},
                {"id": "leaf-cat", "row_kind": "leaf", "active": True, "row_label": "Cat", "parent_row_id": None, "sort_order": 20},
            ],
            mappings=[
                {"campaign_name": "Brand Camp", "row_id": "leaf-brand", "goal_code": "Def"},
                {"campaign_name": "Cat Camp", "row_id": "leaf-cat", "goal_code": "Perf"},
            ],
            ads_facts=[
                {
                    "report_date": sample_day,
                    "campaign_name": "Brand Camp",
                    "campaign_type": "sponsored_products",
                    "spend": "10",
                    "sales": "100",
                    "orders": 1,
                },
                {
                    "report_date": sample_day,
                    "campaign_name": "Cat Camp",
                    "campaign_type": "sponsored_products",
                    "spend": "20",
                    "sales": "150",
                    "orders": 2,
                },
                {
                    "report_date": sample_day,
                    "campaign_name": "Mystery Camp",
                    "campaign_type": "sponsored_products",
                    "spend": "5",
                    "sales": "30",
                    "orders": 0,
                },
            ],
            business_facts=[
                {"report_date": sample_day, "child_asin": "ASINA", "sales": "400"},
            ],
        )
        svc = SalesMixService(db)
        report = svc.build_report("p1", date_from=date_from, date_to=date_to)

        totals = report["totals"]
        assert Decimal(totals["brand_sales"]) == Decimal("100.00")
        assert Decimal(totals["category_sales"]) == Decimal("150.00")
        assert Decimal(totals["unmapped_ad_sales"]) == Decimal("30.00")
        assert Decimal(totals["ad_sales"]) == Decimal("280.00")
        assert Decimal(totals["business_sales"]) == Decimal("400.00")
        # organic = business - ad = 400 - 280 = 120
        assert Decimal(totals["organic_sales"]) == Decimal("120.00")

    def test_organic_clamped_at_zero_when_ads_exceed_business(self):
        date_from, date_to = _last_full_window(1)
        sample_day = date_to.isoformat()
        db = _build_db(
            ads_facts=[
                {
                    "report_date": sample_day,
                    "campaign_name": "Some Camp",
                    "campaign_type": "sponsored_products",
                    "spend": "0",
                    "sales": "500",
                    "orders": 0,
                }
            ],
            business_facts=[
                {"report_date": sample_day, "child_asin": "ASIN", "sales": "100"},
            ],
        )
        report = SalesMixService(db).build_report(
            "p1", date_from=date_from, date_to=date_to
        )
        assert Decimal(report["totals"]["organic_sales"]) == Decimal("0.00")

    def test_ad_type_filter_excludes_other_types(self):
        date_from, date_to = _last_full_window(1)
        sample_day = date_to.isoformat()
        db = _build_db(
            ads_facts=[
                {
                    "report_date": sample_day,
                    "campaign_name": "SP A",
                    "campaign_type": "sponsored_products",
                    "spend": "10",
                    "sales": "100",
                    "orders": 1,
                },
                {
                    "report_date": sample_day,
                    "campaign_name": "SB A",
                    "campaign_type": "sponsored_brands",
                    "spend": "20",
                    "sales": "200",
                    "orders": 2,
                },
            ],
        )
        report = SalesMixService(db).build_report(
            "p1",
            date_from=date_from,
            date_to=date_to,
            ad_types=["sponsored_products"],
        )
        # Only SP fact should contribute
        assert Decimal(report["totals"]["ad_sales"]) == Decimal("100.00")

    def test_unknown_ad_type_raises(self):
        date_from, date_to = _last_full_window(1)
        db = _build_db()
        svc = SalesMixService(db)
        with pytest.raises(WBRValidationError, match="Unknown ad_type"):
            svc.build_report(
                "p1",
                date_from=date_from,
                date_to=date_to,
                ad_types=["bogus"],
            )

    def test_parent_row_filter_drops_unmapped_and_other_parents(self):
        date_from, date_to = _last_full_window(1)
        sample_day = date_to.isoformat()
        db = _build_db(
            rows=[
                {"id": "parent-A", "row_kind": "parent", "active": True, "row_label": "A", "parent_row_id": None, "sort_order": 10},
                {"id": "leaf-A", "row_kind": "leaf", "active": True, "row_label": "A1", "parent_row_id": "parent-A", "sort_order": 11},
                {"id": "leaf-B", "row_kind": "leaf", "active": True, "row_label": "B1", "parent_row_id": "parent-B", "sort_order": 21},
                {"id": "parent-B", "row_kind": "parent", "active": True, "row_label": "B", "parent_row_id": None, "sort_order": 20},
            ],
            mappings=[
                {"campaign_name": "Camp A", "row_id": "leaf-A", "goal_code": "Perf"},
                {"campaign_name": "Camp B", "row_id": "leaf-B", "goal_code": "Perf"},
            ],
            ads_facts=[
                {
                    "report_date": sample_day,
                    "campaign_name": "Camp A",
                    "campaign_type": "sponsored_products",
                    "spend": "1",
                    "sales": "100",
                    "orders": 1,
                },
                {
                    "report_date": sample_day,
                    "campaign_name": "Camp B",
                    "campaign_type": "sponsored_products",
                    "spend": "1",
                    "sales": "999",
                    "orders": 1,
                },
                {
                    "report_date": sample_day,
                    "campaign_name": "Mystery",
                    "campaign_type": "sponsored_products",
                    "spend": "1",
                    "sales": "555",
                    "orders": 1,
                },
            ],
        )
        report = SalesMixService(db).build_report(
            "p1",
            date_from=date_from,
            date_to=date_to,
            parent_row_ids=["parent-A"],
        )
        # Only Camp A's $100 should contribute; Camp B (other parent)
        # and Mystery (unmapped) are out of scope.
        assert Decimal(report["totals"]["ad_sales"]) == Decimal("100.00")
        assert Decimal(report["totals"]["unmapped_ad_sales"]) == Decimal("0.00")

    def test_coverage_warning_triggers_below_threshold(self):
        date_from, date_to = _last_full_window(1)
        sample_day = date_to.isoformat()
        # Mostly unmapped: 90 sales unmapped, 10 mapped → 10% coverage.
        db = _build_db(
            rows=[
                {"id": "leaf-1", "row_kind": "leaf", "active": True, "row_label": "Hero", "parent_row_id": None, "sort_order": 10}
            ],
            mappings=[{"campaign_name": "Mapped", "row_id": "leaf-1", "goal_code": "Perf"}],
            ads_facts=[
                {
                    "report_date": sample_day,
                    "campaign_name": "Mapped",
                    "campaign_type": "sponsored_products",
                    "spend": "1",
                    "sales": "10",
                    "orders": 0,
                },
                {
                    "report_date": sample_day,
                    "campaign_name": "Unmapped",
                    "campaign_type": "sponsored_products",
                    "spend": "1",
                    "sales": "90",
                    "orders": 0,
                },
            ],
        )
        report = SalesMixService(db).build_report(
            "p1", date_from=date_from, date_to=date_to
        )
        assert report["coverage"]["first_low_coverage_week"] is not None
        assert any("coverage" in warning.lower() for warning in report["coverage"]["warnings"])

    def test_rejects_inverted_date_range(self):
        db = _build_db()
        svc = SalesMixService(db)
        with pytest.raises(WBRValidationError, match="date_to must be"):
            svc.build_report(
                "p1",
                date_from=date(2026, 4, 10),
                date_to=date(2026, 4, 1),
            )

    def test_missing_profile_raises_not_found(self):
        db = _multi_table_db({"wbr_profiles": [_chain_table([])]})
        svc = SalesMixService(db)
        date_from, date_to = _last_full_window(1)
        with pytest.raises(WBRNotFoundError):
            svc.build_report("missing", date_from=date_from, date_to=date_to)

    def test_excluded_unmapped_campaign_dropped_entirely(self):
        date_from, date_to = _last_full_window(1)
        sample_day = date_to.isoformat()
        db = _build_db(
            exclusions=[{"campaign_name": "Noisy"}],
            ads_facts=[
                {
                    "report_date": sample_day,
                    "campaign_name": "Noisy",
                    "campaign_type": "sponsored_products",
                    "spend": "5",
                    "sales": "777",
                    "orders": 1,
                },
                {
                    "report_date": sample_day,
                    "campaign_name": "Real Mapped",
                    "campaign_type": "sponsored_products",
                    "spend": "1",
                    "sales": "100",
                    "orders": 1,
                },
            ],
            rows=[
                {"id": "leaf-1", "row_kind": "leaf", "active": True, "row_label": "Hero", "parent_row_id": None, "sort_order": 10}
            ],
            mappings=[{"campaign_name": "Real Mapped", "row_id": "leaf-1", "goal_code": "Perf"}],
        )
        report = SalesMixService(db).build_report(
            "p1", date_from=date_from, date_to=date_to
        )
        # Excluded campaigns (when unmapped) are dropped entirely — they
        # don't show up in any total. Matches Section 2 behavior.
        assert Decimal(report["totals"]["unmapped_ad_sales"]) == Decimal("0.00")
        assert Decimal(report["totals"]["ad_sales"]) == Decimal("100.00")
        assert Decimal(report["totals"]["category_sales"]) == Decimal("100.00")

    def test_window_capped_at_max_days(self):
        db = _build_db()
        svc = SalesMixService(db)
        with pytest.raises(WBRValidationError, match="730 days"):
            svc.build_report(
                "p1",
                date_from=date(2023, 1, 1),
                date_to=date(2026, 1, 1),
            )
