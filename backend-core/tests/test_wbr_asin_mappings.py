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
    table.eq.return_value = table
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
                "wbr_rows": [_chain_table([{"id": "r1", "row_label": "Screen Shine | Go", "active": True}])],
            }
        )

        svc = AsinMappingService(db)
        items = svc.list_child_asins("p1")

        assert len(items) == 1
        assert items[0]["mapped_row_id"] == "r1"
        assert items[0]["mapped_row_label"] == "Screen Shine | Go"

    def test_set_child_asin_mapping_creates_new_manual_mapping(self):
        db = _multi_table_db(
            {
                "wbr_profiles": [_chain_table([{"id": "p1"}])],
                "wbr_profile_child_asins": [_chain_table([{"child_asin": "B012345678"}])],
                "wbr_asin_row_map": [
                    _chain_table([]),  # active mapping lookup
                    _chain_table([{"id": "m1", "child_asin": "B012345678", "row_id": "r1"}]),  # insert
                ],
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
