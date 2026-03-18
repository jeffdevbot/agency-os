"""Tests for WBR ASIN mapping service."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.wbr.asin_mappings import AsinMappingService
from app.services.wbr.profiles import WBRValidationError


def _chain_table(response_data: list[dict] | None = None) -> MagicMock:
    table = MagicMock()
    table.select.return_value = table
    table.insert.return_value = table
    table.update.return_value = table
    table.in_.return_value = table
    table.eq.return_value = table
    table.range.return_value = table
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


class TestAsinMappingService:
    def test_list_child_asins_merges_mapping_and_row_labels(self):
        db = _multi_table_db(
            {
                "wbr_profiles": [_chain_table([{"id": "p1"}])],
                "wbr_profile_child_asins": [_chain_table([{"id": "a1", "profile_id": "p1", "child_asin": "B012345678", "child_sku": "SKU-1", "child_product_name": "Widget A", "active": True}])],
                "wbr_asin_row_map": [_chain_table([{"child_asin": "B012345678", "row_id": "r1"}])],
                "wbr_asin_exclusions": [_chain_table([])],
                "wbr_rows": [_chain_table([{"id": "r1", "row_label": "Screen Shine | Go", "active": True}])],
            }
        )

        svc = AsinMappingService(db)
        items = svc.list_child_asins("p1")

        assert len(items) == 1
        assert items[0]["mapped_row_id"] == "r1"
        assert items[0]["mapped_row_label"] == "Screen Shine | Go"
        assert items[0]["scope_status"] == "included"
        assert items[0]["is_excluded"] is False

    def test_set_child_asin_mapping_creates_new_manual_mapping(self):
        db = _multi_table_db(
            {
                "wbr_profiles": [_chain_table([{"id": "p1"}])],
                "wbr_profile_child_asins": [_chain_table([{"child_asin": "B012345678"}])],
                "wbr_asin_row_map": [
                    _chain_table([]),  # active mapping lookup
                    _chain_table([{"id": "m1", "child_asin": "B012345678", "row_id": "r1"}]),  # insert
                ],
                "wbr_asin_exclusions": [_chain_table([])],
                "wbr_rows": [_chain_table([{"id": "r1", "profile_id": "p1", "row_kind": "leaf", "row_label": "Screen Shine | Go", "active": True}])],
            }
        )

        svc = AsinMappingService(db)
        mapping = svc.set_child_asin_mapping(
            profile_id="p1",
            child_asin="B012345678",
            row_id="r1",
            user_id="u1",
        )

        assert mapping["mapped_row_id"] == "r1"
        assert mapping["mapped_row_label"] == "Screen Shine | Go"

    def test_set_child_asin_mapping_clears_existing_mapping(self):
        db = _multi_table_db(
            {
                "wbr_profiles": [_chain_table([{"id": "p1"}])],
                "wbr_profile_child_asins": [_chain_table([{"child_asin": "B012345678"}])],
                "wbr_asin_row_map": [
                    _chain_table([{"id": "m1", "child_asin": "B012345678", "row_id": "r1"}]),  # active mapping lookup
                    _chain_table([{"id": "m1", "active": False}]),  # deactivate
                ],
                "wbr_asin_exclusions": [_chain_table([])],
            }
        )

        svc = AsinMappingService(db)
        mapping = svc.set_child_asin_mapping(
            profile_id="p1",
            child_asin="B012345678",
            row_id=None,
            user_id="u1",
        )

        assert mapping["mapped_row_id"] is None

    def test_rejects_non_leaf_row_targets(self):
        db = _multi_table_db(
            {
                "wbr_profiles": [_chain_table([{"id": "p1"}])],
                "wbr_profile_child_asins": [_chain_table([{"child_asin": "B012345678"}])],
                "wbr_asin_row_map": [_chain_table([])],
                "wbr_asin_exclusions": [_chain_table([])],
                "wbr_rows": [_chain_table([{"id": "r1", "profile_id": "p1", "row_kind": "parent", "row_label": "Parent"}])],
            }
        )

        svc = AsinMappingService(db)

        with pytest.raises(WBRValidationError, match="leaf rows"):
            svc.set_child_asin_mapping(
                profile_id="p1",
                child_asin="B012345678",
                row_id="r1",
                user_id="u1",
            )

    def test_export_child_asin_mapping_csv_includes_single_row_label_column(self):
        db = _multi_table_db(
            {
                "wbr_profiles": [_chain_table([{"id": "p1"}])],
                "wbr_profile_child_asins": [
                    _chain_table(
                        [
                            {
                                "id": "a1",
                                "profile_id": "p1",
                                "child_asin": "B012345678",
                                "child_sku": "SKU-1",
                                "child_product_name": "Widget A",
                                "active": True,
                            }
                        ]
                    )
                ],
                "wbr_asin_row_map": [_chain_table([{"child_asin": "B012345678", "row_id": "r1"}])],
                "wbr_asin_exclusions": [_chain_table([])],
                "wbr_rows": [_chain_table([{"id": "r1", "row_label": "Screen Shine | Go", "active": True}])],
            }
        )

        svc = AsinMappingService(db)
        csv_text = svc.export_child_asin_mapping_csv("p1")

        assert "child_asin,child_sku,child_product_name,row_label,scope_status,exclusion_reason" in csv_text
        assert "B012345678,SKU-1,Widget A,Screen Shine | Go,included," in csv_text

    def test_import_child_asin_mapping_csv_applies_updates_and_clears(self):
        csv_text = (
            "child_asin,mapped_row_id,mapped_row_label\n"
            "B012345678,r1,\n"
            "B012345679,,\n"
        ).encode("utf-8")

        db = _multi_table_db(
            {
                "wbr_profiles": [
                    _chain_table([{"id": "p1"}]),
                ],
                "wbr_profile_child_asins": [
                    _chain_table(
                        [
                            {"child_asin": "B012345678", "active": True},
                            {"child_asin": "B012345679", "active": True},
                        ]
                    ),
                ],
                "wbr_rows": [
                    _chain_table([{"id": "r1", "row_label": "Row 1", "active": True}]),
                ],
                "wbr_asin_row_map": [
                    _chain_table([
                        {"id": "m1", "child_asin": "B012345678", "row_id": "r1"},
                        {"id": "m2", "child_asin": "B012345679", "row_id": "r2"},
                    ]),
                    _chain_table([{"id": "m2", "active": False}]),
                ],
                "wbr_asin_exclusions": [
                    _chain_table([]),
                ],
            }
        )

        svc = AsinMappingService(db)
        summary = svc.import_child_asin_mapping_csv(
            profile_id="p1",
            file_name="asin-mapping.csv",
            file_bytes=csv_text,
            user_id="u1",
        )

        assert summary == {
            "rows_read": 2,
            "rows_updated": 0,
            "rows_cleared": 1,
            "rows_excluded": 0,
            "rows_unchanged": 1,
        }

    def test_import_child_asin_mapping_csv_rejects_duplicate_child_asins(self):
        csv_text = (
            "child_asin,mapped_row_label\n"
            "B012345678,Row 1\n"
            "B012345678,Row 1\n"
        ).encode("utf-8")

        db = _multi_table_db(
            {
                "wbr_profiles": [
                    _chain_table([{"id": "p1"}]),
                ],
                "wbr_profile_child_asins": [
                    _chain_table([{"child_asin": "B012345678", "active": True}]),
                ],
                "wbr_rows": [
                    _chain_table([{"id": "r1", "row_label": "Row 1", "active": True}]),
                ],
                "wbr_asin_exclusions": [_chain_table([])],
            }
        )

        svc = AsinMappingService(db)

        with pytest.raises(WBRValidationError, match="duplicate child_asin"):
            svc.import_child_asin_mapping_csv(
                profile_id="p1",
                file_name="asin-mapping.csv",
                file_bytes=csv_text,
                user_id="u1",
            )

    def test_import_child_asin_mapping_csv_accepts_exported_current_row_columns(self):
        csv_text = (
            "child_asin,current_row_label\n"
            "B012345678,Row 1\n"
        ).encode("utf-8")

        db = _multi_table_db(
            {
                "wbr_profiles": [
                    _chain_table([{"id": "p1"}]),
                ],
                "wbr_profile_child_asins": [
                    _chain_table([{"child_asin": "B012345678", "active": True}]),
                ],
                "wbr_asin_row_map": [
                    _chain_table([{"id": "m1", "child_asin": "B012345678", "row_id": "r1"}]),
                ],
                "wbr_asin_exclusions": [_chain_table([])],
                "wbr_rows": [
                    _chain_table([{"id": "r1", "row_label": "Row 1", "active": True}]),
                ],
            }
        )

        svc = AsinMappingService(db)
        summary = svc.import_child_asin_mapping_csv(
            profile_id="p1",
            file_name="asin-mapping.csv",
            file_bytes=csv_text,
            user_id="u1",
        )

        assert summary == {
            "rows_read": 1,
            "rows_updated": 0,
            "rows_cleared": 0,
            "rows_excluded": 0,
            "rows_unchanged": 1,
        }

    def test_import_child_asin_mapping_csv_batches_many_updates(self):
        rows = "\n".join(
            f"B{i:09d},Row 1" for i in range(1, 504)
        )
        csv_text = f"child_asin,mapped_row_label\n{rows}\n".encode("utf-8")

        child_asins = [{"child_asin": f"B{i:09d}", "active": True} for i in range(1, 504)]
        mappings = [{"id": f"m{i}", "child_asin": f"B{i:09d}", "row_id": "r2"} for i in range(1, 504)]
        deactivate_first = _chain_table([{"id": "m1", "active": False}])
        deactivate_second = _chain_table([{"id": "m501", "active": False}])
        insert_first = _chain_table([{"id": f"n{i}"} for i in range(1, 501)])
        insert_second = _chain_table([{"id": "n501"}, {"id": "n502"}, {"id": "n503"}])

        db = _multi_table_db(
            {
                "wbr_profiles": [_chain_table([{"id": "p1"}])],
                "wbr_profile_child_asins": [_chain_table(child_asins)],
                "wbr_rows": [_chain_table([{"id": "r1", "row_label": "Row 1", "active": True}])],
                "wbr_asin_row_map": [
                    _chain_table(mappings),
                    deactivate_first,
                    deactivate_second,
                    insert_first,
                    insert_second,
                ],
                "wbr_asin_exclusions": [_chain_table([])],
            }
        )

        svc = AsinMappingService(db)
        summary = svc.import_child_asin_mapping_csv(
            profile_id="p1",
            file_name="asin-mapping.csv",
            file_bytes=csv_text,
            user_id="u1",
        )

        assert summary == {
            "rows_read": 503,
            "rows_updated": 503,
            "rows_cleared": 0,
            "rows_excluded": 0,
            "rows_unchanged": 0,
        }
        deactivate_first.in_.assert_called_once()
        deactivate_second.in_.assert_called_once()

    def test_list_child_asins_marks_excluded_scope(self):
        db = _multi_table_db(
            {
                "wbr_profiles": [_chain_table([{"id": "p1"}])],
                "wbr_profile_child_asins": [
                    _chain_table(
                        [
                            {
                                "id": "a1",
                                "profile_id": "p1",
                                "child_asin": "B012345678",
                                "child_sku": "SKU-1",
                                "child_product_name": "Widget A",
                                "active": True,
                            }
                        ]
                    )
                ],
                "wbr_asin_row_map": [_chain_table([])],
                "wbr_rows": [_chain_table([])],
                "wbr_asin_exclusions": [_chain_table([{"child_asin": "B012345678", "exclusion_reason": "Out of scope"}])],
            }
        )

        items = AsinMappingService(db).list_child_asins("p1")

        assert items[0]["scope_status"] == "excluded"
        assert items[0]["is_excluded"] is True
        assert items[0]["exclusion_reason"] == "Out of scope"

    def test_import_child_asin_mapping_csv_supports_exclusions(self):
        csv_text = (
            "child_asin,scope_status,exclusion_reason,mapped_row_label\n"
            "B012345678,excluded,Not agency managed,\n"
        ).encode("utf-8")

        db = _multi_table_db(
            {
                "wbr_profiles": [_chain_table([{"id": "p1"}])],
                "wbr_profile_child_asins": [_chain_table([{"child_asin": "B012345678", "active": True}])],
                "wbr_rows": [_chain_table([{"id": "r1", "row_label": "Row 1", "active": True}])],
                "wbr_asin_row_map": [
                    _chain_table([{"id": "m1", "child_asin": "B012345678", "row_id": "r1"}]),
                    _chain_table([{"id": "m1", "active": False}]),
                ],
                "wbr_asin_exclusions": [
                    _chain_table([]),
                    _chain_table([{"id": "e1"}]),
                ],
            }
        )

        summary = AsinMappingService(db).import_child_asin_mapping_csv(
            profile_id="p1",
            file_name="asin-mapping.csv",
            file_bytes=csv_text,
            user_id="u1",
        )

        assert summary == {
            "rows_read": 1,
            "rows_updated": 0,
            "rows_cleared": 0,
            "rows_excluded": 1,
            "rows_unchanged": 0,
        }

    def test_import_child_asin_mapping_csv_allows_unknown_asin_when_excluded(self):
        csv_text = (
            "child_asin,scope_status,exclusion_reason\n"
            "B099999999,excluded,Out of scope\n"
        ).encode("utf-8")

        db = _multi_table_db(
            {
                "wbr_profiles": [_chain_table([{"id": "p1"}])],
                "wbr_profile_child_asins": [_chain_table([])],
                "wbr_rows": [_chain_table([])],
                "wbr_asin_row_map": [_chain_table([])],
                "wbr_asin_exclusions": [
                    _chain_table([]),
                    _chain_table([{"id": "e1"}]),
                ],
            }
        )

        summary = AsinMappingService(db).import_child_asin_mapping_csv(
            profile_id="p1",
            file_name="asin-mapping.csv",
            file_bytes=csv_text,
            user_id="u1",
        )

        assert summary == {
            "rows_read": 1,
            "rows_updated": 0,
            "rows_cleared": 0,
            "rows_excluded": 1,
            "rows_unchanged": 0,
        }

    def test_import_child_asin_mapping_csv_clears_existing_exclusion_when_mapping_restored(self):
        csv_text = (
            "child_asin,mapped_row_label\n"
            "B012345678,Row 1\n"
        ).encode("utf-8")

        db = _multi_table_db(
            {
                "wbr_profiles": [_chain_table([{"id": "p1"}])],
                "wbr_profile_child_asins": [_chain_table([{"child_asin": "B012345678", "active": True}])],
                "wbr_rows": [_chain_table([{"id": "r1", "row_label": "Row 1", "active": True}])],
                "wbr_asin_row_map": [
                    _chain_table([]),
                    _chain_table([{"id": "m1"}]),
                ],
                "wbr_asin_exclusions": [
                    _chain_table([{"id": "e1", "child_asin": "B012345678"}]),
                    _chain_table([{"id": "e1", "active": False}]),
                ],
            }
        )

        summary = AsinMappingService(db).import_child_asin_mapping_csv(
            profile_id="p1",
            file_name="asin-mapping.csv",
            file_bytes=csv_text,
            user_id="u1",
        )

        assert summary == {
            "rows_read": 1,
            "rows_updated": 1,
            "rows_cleared": 0,
            "rows_excluded": 0,
            "rows_unchanged": 0,
        }

    def test_import_child_asin_mapping_csv_paginates_active_child_asins(self):
        csv_text = (
            "child_asin,mapped_row_label,scope_status\n"
            "B099999999,Row 1,included\n"
        ).encode("utf-8")

        first_page_child_asins = [{"child_asin": f"B{i:09d}", "active": True} for i in range(1, 1001)]
        second_page_child_asins = [{"child_asin": "B099999999", "active": True}]

        db = _multi_table_db(
            {
                "wbr_profiles": [_chain_table([{"id": "p1"}])],
                "wbr_profile_child_asins": [
                    _chain_table(first_page_child_asins),
                    _chain_table(second_page_child_asins),
                ],
                "wbr_rows": [
                    _chain_table([{"id": "r1", "row_label": "Row 1", "active": True}]),
                ],
                "wbr_asin_row_map": [
                    _chain_table([]),
                    _chain_table([{"id": "m1"}]),
                ],
                "wbr_asin_exclusions": [
                    _chain_table([]),
                ],
            }
        )

        summary = AsinMappingService(db).import_child_asin_mapping_csv(
            profile_id="p1",
            file_name="asin-mapping.csv",
            file_bytes=csv_text,
            user_id="u1",
        )

        assert summary == {
            "rows_read": 1,
            "rows_updated": 1,
            "rows_cleared": 0,
            "rows_excluded": 0,
            "rows_unchanged": 0,
        }
