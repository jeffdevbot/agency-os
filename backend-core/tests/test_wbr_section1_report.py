from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import app.services.wbr.section1_report as report_module
from app.services.wbr.section1_report import Section1ReportService


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
                            "row_label": "Screen Shine | Pro",
                            "row_kind": "parent",
                            "parent_row_id": None,
                            "sort_order": 1,
                            "active": True,
                        },
                        {
                            "id": "leaf-1",
                            "row_label": "Screen Shine | Pro",
                            "row_kind": "leaf",
                            "parent_row_id": "parent-1",
                            "sort_order": 2,
                            "active": True,
                        },
                        {
                            "id": "leaf-2",
                            "row_label": "Screen Shine | Pro 2",
                            "row_kind": "leaf",
                            "parent_row_id": "parent-1",
                            "sort_order": 3,
                            "active": True,
                        },
                        {
                            "id": "leaf-3",
                            "row_label": "Screen Shine | Pocket",
                            "row_kind": "leaf",
                            "parent_row_id": None,
                            "sort_order": 4,
                            "active": True,
                        },
                    ]
                )
            ],
            "wbr_asin_row_map": [
                _chain_table(
                    [
                        {"child_asin": "ASIN1", "row_id": "leaf-1"},
                        {"child_asin": "ASIN2", "row_id": "leaf-2"},
                        {"child_asin": "ASIN3", "row_id": "leaf-3"},
                    ]
                )
            ],
            "wbr_business_asin_daily": [
                _chain_table(
                    [
                        {
                            "report_date": "2026-03-02",
                            "child_asin": "ASIN1",
                            "page_views": 100,
                            "unit_sales": 10,
                            "sales": "250.00",
                        },
                        {
                            "report_date": "2026-03-03",
                            "child_asin": "ASIN2",
                            "page_views": 50,
                            "unit_sales": 5,
                            "sales": "125.00",
                        },
                        {
                            "report_date": "2026-03-04",
                            "child_asin": "ASIN3",
                            "page_views": 25,
                            "unit_sales": 2,
                            "sales": "40.00",
                        },
                    ]
                )
            ],
        }
    )

    report = Section1ReportService(db).build_report("profile-1", weeks=1)

    assert report["weeks"] == [
        {"start": "2026-03-02", "end": "2026-03-08", "label": "02-Mar to 08-Mar"}
    ]
    assert report["qa"]["mapped_asin_count"] == 3
    assert report["qa"]["unmapped_asin_count"] == 0

    rows_by_id = {row["id"]: row for row in report["rows"]}
    assert rows_by_id["leaf-1"]["weeks"][0]["page_views"] == 100
    assert rows_by_id["leaf-1"]["weeks"][0]["unit_sales"] == 10
    assert rows_by_id["leaf-1"]["weeks"][0]["sales"] == "250.00"
    assert rows_by_id["parent-1"]["weeks"][0]["page_views"] == 150
    assert rows_by_id["parent-1"]["weeks"][0]["unit_sales"] == 15
    assert rows_by_id["parent-1"]["weeks"][0]["sales"] == "375.00"
    assert rows_by_id["leaf-3"]["weeks"][0]["sales"] == "40.00"


def test_build_report_counts_unmapped_activity(monkeypatch):
    class _FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 3, 13, 12, 0, 0, tzinfo=tz or UTC)

    monkeypatch.setattr(report_module, "datetime", _FakeDateTime)

    db = _multi_table_db(
        {
            "wbr_profiles": [_chain_table([{"id": "profile-1", "week_start_day": "sunday"}])],
            "wbr_rows": [_chain_table([])],
            "wbr_asin_row_map": [_chain_table([])],
            "wbr_business_asin_daily": [
                _chain_table(
                    [
                        {
                            "report_date": "2026-03-05",
                            "child_asin": "UNMAPPED1",
                            "page_views": 12,
                            "unit_sales": 1,
                            "sales": "9.99",
                        }
                    ]
                )
            ],
        }
    )

    report = Section1ReportService(db).build_report("profile-1", weeks=1)

    assert report["weeks"] == [
        {"start": "2026-03-01", "end": "2026-03-07", "label": "01-Mar to 07-Mar"}
    ]
    assert report["qa"]["unmapped_asin_count"] == 1
    assert report["qa"]["unmapped_fact_rows"] == 1
    assert report["qa"]["fact_row_count"] == 1


def test_build_report_paginates_business_facts(monkeypatch):
    class _FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 3, 13, 12, 0, 0, tzinfo=tz or UTC)

    monkeypatch.setattr(report_module, "datetime", _FakeDateTime)

    first_page = [
        {
            "report_date": "2026-03-02",
            "child_asin": "ASIN1",
            "page_views": 1,
            "unit_sales": 1,
            "sales": "2.00",
        }
        for _ in range(1000)
    ]
    second_page = [
        {
            "report_date": "2026-02-24",
            "child_asin": "ASIN1",
            "page_views": 1,
            "unit_sales": 0,
            "sales": "0.00",
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
            "wbr_business_asin_daily": [_chain_table(first_page), _chain_table(second_page)],
        }
    )

    report = Section1ReportService(db).build_report("profile-1", weeks=4)

    row = report["rows"][0]
    assert row["weeks"][2]["page_views"] == 100
    assert row["weeks"][3]["page_views"] == 1000
    assert row["weeks"][3]["unit_sales"] == 1000
    assert row["weeks"][3]["sales"] == "2000.00"
    assert report["qa"]["fact_row_count"] == 1100
