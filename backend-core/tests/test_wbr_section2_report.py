from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import app.services.wbr.section2_report as report_module
from app.services.wbr.section2_report import Section2ReportService


def _chain_table(response_data: list[dict] | None = None) -> MagicMock:
    table = MagicMock()
    table.select.return_value = table
    table.eq.return_value = table
    table.gte.return_value = table
    table.lte.return_value = table
    table.range.return_value = table
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


def test_build_report_rolls_up_leafs_and_parents(monkeypatch):
    class _FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 3, 13, 12, 0, 0, tzinfo=tz or UTC)

    monkeypatch.setattr(report_module, "datetime", _FakeDateTime)

    db = _multi_table_db(
        {
            "wbr_profiles": [
                _chain_table(
                    [
                        {
                            "id": "profile-1",
                            "display_name": "Whoosh US",
                            "week_start_day": "monday",
                        }
                    ]
                )
            ],
            "wbr_rows": [
                _chain_table(
                    [
                        {
                            "id": "parent-1",
                            "row_label": "Screen Shine | Duo",
                            "row_kind": "parent",
                            "parent_row_id": None,
                            "sort_order": 1,
                            "active": True,
                        },
                        {
                            "id": "leaf-1",
                            "row_label": "Screen Shine | Duo",
                            "row_kind": "leaf",
                            "parent_row_id": "parent-1",
                            "sort_order": 2,
                            "active": True,
                        },
                        {
                            "id": "leaf-2",
                            "row_label": "Screen Shine | Duo XL",
                            "row_kind": "leaf",
                            "parent_row_id": "parent-1",
                            "sort_order": 3,
                            "active": True,
                        },
                    ]
                )
            ],
            "wbr_pacvue_campaign_map": [
                _chain_table(
                    [
                        {"campaign_name": "Campaign A", "row_id": "leaf-1"},
                        {"campaign_name": "Campaign B", "row_id": "leaf-2"},
                    ]
                )
            ],
            "wbr_asin_row_map": [
                _chain_table(
                    [
                        {"child_asin": "B001", "row_id": "leaf-1"},
                        {"child_asin": "B002", "row_id": "leaf-2"},
                    ]
                )
            ],
            "wbr_ads_campaign_daily": [
                _chain_table(
                    [
                        {
                            "report_date": "2026-03-02",
                            "campaign_name": "Campaign A",
                            "impressions": 1000,
                            "clicks": 50,
                            "spend": "125.00",
                            "orders": 10,
                            "sales": "300.00",
                        },
                        {
                            "report_date": "2026-03-03",
                            "campaign_name": "Campaign B",
                            "impressions": 500,
                            "clicks": 20,
                            "spend": "50.00",
                            "orders": 4,
                            "sales": "120.00",
                        },
                    ]
                )
            ],
            "wbr_business_asin_daily": [
                _chain_table(
                    [
                        {
                            "report_date": "2026-03-02",
                            "child_asin": "B001",
                            "sales": "1000.00",
                        },
                        {
                            "report_date": "2026-03-03",
                            "child_asin": "B002",
                            "sales": "200.00",
                        },
                    ]
                )
            ],
        }
    )

    report = Section2ReportService(db).build_report("profile-1", weeks=1)

    assert report["weeks"] == [
        {"start": "2026-03-02", "end": "2026-03-08", "label": "02-Mar to 08-Mar"}
    ]
    assert report["qa"]["mapped_campaign_count"] == 2
    assert report["qa"]["unmapped_campaign_count"] == 0

    rows_by_id = {row["id"]: row for row in report["rows"]}
    assert rows_by_id["leaf-1"]["weeks"][0]["impressions"] == 1000
    assert rows_by_id["leaf-1"]["weeks"][0]["clicks"] == 50
    assert rows_by_id["leaf-1"]["weeks"][0]["ad_spend"] == "125.00"
    assert rows_by_id["leaf-1"]["weeks"][0]["ad_orders"] == 10
    assert rows_by_id["leaf-1"]["weeks"][0]["ad_sales"] == "300.00"
    assert rows_by_id["leaf-1"]["weeks"][0]["ctr_pct"] == 0.05
    assert rows_by_id["leaf-1"]["weeks"][0]["cpc"] == "2.50"
    assert rows_by_id["leaf-1"]["weeks"][0]["ad_conversion_rate"] == 0.2
    assert rows_by_id["leaf-1"]["weeks"][0]["acos_pct"] == round(125 / 300, 4)
    assert rows_by_id["leaf-1"]["weeks"][0]["tacos_pct"] == round(125 / 1000, 4)
    assert rows_by_id["parent-1"]["weeks"][0]["impressions"] == 1500
    assert rows_by_id["parent-1"]["weeks"][0]["clicks"] == 70
    assert rows_by_id["parent-1"]["weeks"][0]["ad_spend"] == "175.00"
    assert rows_by_id["parent-1"]["weeks"][0]["ad_orders"] == 14
    assert rows_by_id["parent-1"]["weeks"][0]["ad_sales"] == "420.00"
    assert rows_by_id["parent-1"]["weeks"][0]["business_sales"] == "1200.00"
    assert rows_by_id["parent-1"]["weeks"][0]["tacos_pct"] == round(175 / 1200, 4)


def test_build_report_counts_unmapped_campaign_activity(monkeypatch):
    class _FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 3, 13, 12, 0, 0, tzinfo=tz or UTC)

    monkeypatch.setattr(report_module, "datetime", _FakeDateTime)

    db = _multi_table_db(
        {
            "wbr_profiles": [_chain_table([{"id": "profile-1", "week_start_day": "sunday"}])],
            "wbr_rows": [_chain_table([])],
            "wbr_pacvue_campaign_map": [_chain_table([])],
            "wbr_asin_row_map": [_chain_table([])],
            "wbr_ads_campaign_daily": [
                _chain_table(
                    [
                        {
                            "report_date": "2026-03-05",
                            "campaign_name": "Unmapped Campaign",
                            "impressions": 250,
                            "clicks": 5,
                            "spend": "10.00",
                            "orders": 1,
                            "sales": "20.00",
                        }
                    ]
                )
            ],
            "wbr_business_asin_daily": [_chain_table([])],
        }
    )

    report = Section2ReportService(db).build_report("profile-1", weeks=1)

    assert report["weeks"] == [
        {"start": "2026-03-01", "end": "2026-03-07", "label": "01-Mar to 07-Mar"}
    ]
    assert report["qa"]["unmapped_campaign_count"] == 1
    assert report["qa"]["unmapped_campaign_samples"] == ["Unmapped Campaign"]
    assert report["qa"]["unmapped_fact_rows"] == 1
    assert report["qa"]["fact_row_count"] == 1


def test_build_report_pages_through_large_ads_fact_sets(monkeypatch):
    class _FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 3, 13, 12, 0, 0, tzinfo=tz or UTC)

    monkeypatch.setattr(report_module, "datetime", _FakeDateTime)

    first_page = [
        {
            "report_date": "2026-02-10",
            "campaign_name": "Campaign A",
            "impressions": 1,
            "clicks": 0,
            "spend": "1.00",
            "orders": 0,
            "sales": "2.00",
        }
        for _ in range(1000)
    ]
    second_page = [
        {
            "report_date": "2026-02-17",
            "campaign_name": "Campaign A",
            "impressions": 1,
            "clicks": 0,
            "spend": "1.00",
            "orders": 0,
            "sales": "2.00",
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
            "wbr_pacvue_campaign_map": [_chain_table([{"campaign_name": "Campaign A", "row_id": "leaf-1"}])],
            "wbr_asin_row_map": [_chain_table([])],
            "wbr_ads_campaign_daily": [_chain_table(first_page), _chain_table(second_page)],
            "wbr_business_asin_daily": [_chain_table([])],
        }
    )

    report = Section2ReportService(db).build_report("profile-1", weeks=4)

    row = report["rows"][0]
    assert row["weeks"][0]["impressions"] == 1000
    assert row["weeks"][0]["ad_spend"] == "1000.00"
    assert row["weeks"][1]["impressions"] == 100
    assert row["weeks"][1]["ad_spend"] == "100.00"
    assert report["qa"]["fact_row_count"] == 1100
