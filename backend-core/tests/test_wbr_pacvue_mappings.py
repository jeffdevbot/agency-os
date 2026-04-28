"""Tests for the Pacvue mapping management service."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.wbr.pacvue_mappings import PacvueMappingService
from app.services.wbr.profiles import WBRNotFoundError, WBRValidationError


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


PROFILE = {"id": "p1", "week_start_day": "sunday"}
LEAF_ROW = {"id": "row-1", "row_label": "Brand | Hero", "row_kind": "leaf", "active": True}


class TestUpsertManualMapping:
    def test_inserts_new_manual_mapping_with_normalized_goal(self):
        db = _multi_table_db(
            {
                "wbr_profiles": [_chain_table([PROFILE])],
                "wbr_rows": [_chain_table([LEAF_ROW])],
                "wbr_pacvue_campaign_map": [
                    _chain_table([]),  # deactivate-prior step
                    _chain_table([{"id": "m1", "campaign_name": "Camp X"}]),  # insert
                ],
            }
        )
        svc = PacvueMappingService(db)
        result = svc.upsert_manual_mapping(
            profile_id="p1",
            campaign_name="Camp X",
            row_id="row-1",
            goal_code="perf",
            user_id="u1",
        )
        assert result["id"] == "m1"

    def test_rejects_unknown_goal_code(self):
        db = _multi_table_db(
            {
                "wbr_profiles": [_chain_table([PROFILE])],
            }
        )
        svc = PacvueMappingService(db)
        with pytest.raises(WBRValidationError, match="Unsupported goal_code"):
            svc.upsert_manual_mapping(
                profile_id="p1",
                campaign_name="Camp X",
                row_id="row-1",
                goal_code="bogus",
            )

    def test_rejects_inactive_or_non_leaf_row(self):
        inactive_row = {"id": "row-1", "row_label": "Brand | Hero", "row_kind": "leaf", "active": False}
        db = _multi_table_db(
            {
                "wbr_profiles": [_chain_table([PROFILE])],
                "wbr_rows": [_chain_table([inactive_row])],
            }
        )
        svc = PacvueMappingService(db)
        with pytest.raises(WBRValidationError, match="inactive"):
            svc.upsert_manual_mapping(
                profile_id="p1",
                campaign_name="Camp X",
                row_id="row-1",
                goal_code="Perf",
            )

    def test_rejects_missing_profile(self):
        db = _multi_table_db({"wbr_profiles": [_chain_table([])]})
        svc = PacvueMappingService(db)
        with pytest.raises(WBRNotFoundError):
            svc.upsert_manual_mapping(
                profile_id="missing",
                campaign_name="Camp X",
                row_id="row-1",
                goal_code="Perf",
            )

    def test_rejects_blank_campaign_name(self):
        db = _multi_table_db({"wbr_profiles": [_chain_table([PROFILE])]})
        svc = PacvueMappingService(db)
        with pytest.raises(WBRValidationError, match="campaign_name"):
            svc.upsert_manual_mapping(
                profile_id="p1",
                campaign_name="   ",
                row_id="row-1",
                goal_code="Perf",
            )


class TestSetExclusion:
    def test_creates_new_exclusion_when_none_exists(self):
        existing_lookup = _chain_table([])
        insert_table = _chain_table([{"id": "x1"}])
        db = _multi_table_db(
            {
                "wbr_profiles": [_chain_table([PROFILE])],
                "wbr_campaign_exclusions": [existing_lookup, insert_table],
            }
        )
        svc = PacvueMappingService(db)
        result = svc.set_exclusion(
            profile_id="p1",
            campaign_name="Camp X",
            excluded=True,
            reason="dormant",
            user_id="u1",
        )
        assert result == {"campaign_name": "Camp X", "active": True, "changed": True}

    def test_no_op_when_already_excluded(self):
        existing_lookup = _chain_table([{"id": "x1", "active": True}])
        db = _multi_table_db(
            {
                "wbr_profiles": [_chain_table([PROFILE])],
                "wbr_campaign_exclusions": [existing_lookup],
            }
        )
        svc = PacvueMappingService(db)
        result = svc.set_exclusion(profile_id="p1", campaign_name="Camp X", excluded=True)
        assert result["changed"] is False
        assert result["active"] is True

    def test_clears_existing_exclusion(self):
        existing_lookup = _chain_table([{"id": "x1", "active": True}])
        update_table = _chain_table([])
        db = _multi_table_db(
            {
                "wbr_profiles": [_chain_table([PROFILE])],
                "wbr_campaign_exclusions": [existing_lookup, update_table],
            }
        )
        svc = PacvueMappingService(db)
        result = svc.set_exclusion(profile_id="p1", campaign_name="Camp X", excluded=False)
        assert result == {"campaign_name": "Camp X", "active": False, "changed": True}


class TestDeactivateMapping:
    def test_deactivates_active_mapping(self):
        update_table = _chain_table([{"id": "m1"}, {"id": "m2"}])
        db = _multi_table_db(
            {
                "wbr_profiles": [_chain_table([PROFILE])],
                "wbr_pacvue_campaign_map": [update_table],
            }
        )
        svc = PacvueMappingService(db)
        deactivated = svc.deactivate_mapping(profile_id="p1", campaign_name="Camp X")
        assert deactivated == 2

    def test_rejects_blank_campaign_name(self):
        db = _multi_table_db({"wbr_profiles": [_chain_table([PROFILE])]})
        svc = PacvueMappingService(db)
        with pytest.raises(WBRValidationError):
            svc.deactivate_mapping(profile_id="p1", campaign_name="   ")
