"""Tests for WBR profile & row service layer."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from postgrest.exceptions import APIError as PostgrestAPIError

from app.services.wbr.profiles import (
    WBRNotFoundError,
    WBRValidationError,
    WBRProfileService,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _chain_table(response_data: list[dict] | None = None) -> MagicMock:
    """Return a mock table that chains .select/.eq/.order/.limit/.execute."""
    table = MagicMock()
    table.select.return_value = table
    table.insert.return_value = table
    table.update.return_value = table
    table.delete.return_value = table
    table.eq.return_value = table
    table.order.return_value = table
    table.limit.return_value = table
    resp = MagicMock()
    resp.data = response_data if response_data is not None else []
    table.execute.return_value = resp
    return table


def _chain_table_that_raises(exc: Exception) -> MagicMock:
    """Return a mock table whose .execute() raises *exc*."""
    table = MagicMock()
    table.select.return_value = table
    table.insert.return_value = table
    table.update.return_value = table
    table.delete.return_value = table
    table.eq.return_value = table
    table.order.return_value = table
    table.limit.return_value = table
    table.execute.side_effect = exc
    return table


def _db_with_tables(**tables: MagicMock) -> MagicMock:
    db = MagicMock()
    db.table.side_effect = lambda name: tables[name]
    return db


def _rotating_db(table_name: str, *tables: MagicMock) -> MagicMock:
    """Return a db where successive calls to db.table(table_name) rotate through *tables*."""
    it = iter(tables)

    def router(name):
        if name == table_name:
            return next(it)
        raise KeyError(name)

    db = MagicMock()
    db.table.side_effect = router
    return db


def _multi_table_db(mapping: dict[str, list[MagicMock]]) -> MagicMock:
    """Each table name maps to a list of mocks returned in order."""
    iters = {k: iter(v) for k, v in mapping.items()}

    def router(name):
        return next(iters[name])

    db = MagicMock()
    db.table.side_effect = router
    return db


def _pg_error(message: str) -> PostgrestAPIError:
    return PostgrestAPIError({"message": message, "code": "23505", "details": "", "hint": ""})


# ==================================================================
# Profile tests
# ==================================================================


class TestListProfiles:
    def test_returns_profiles_for_client(self):
        rows = [{"id": "p1", "client_id": "c1", "marketplace_code": "US"}]
        db = _db_with_tables(wbr_profiles=_chain_table(rows))
        svc = WBRProfileService(db)
        assert svc.list_profiles("c1") == rows

    def test_returns_empty_list_when_none(self):
        db = _db_with_tables(wbr_profiles=_chain_table([]))
        svc = WBRProfileService(db)
        assert svc.list_profiles("c1") == []


class TestGetProfile:
    def test_returns_profile(self):
        profile = {"id": "p1", "display_name": "US Profile"}
        db = _db_with_tables(wbr_profiles=_chain_table([profile]))
        svc = WBRProfileService(db)
        assert svc.get_profile("p1") == profile

    def test_raises_not_found(self):
        db = _db_with_tables(wbr_profiles=_chain_table([]))
        svc = WBRProfileService(db)
        with pytest.raises(WBRNotFoundError, match="not found"):
            svc.get_profile("missing")


class TestCreateProfile:
    def test_creates_and_returns_profile(self):
        created = {"id": "p1", "client_id": "c1", "marketplace_code": "US"}
        db = _rotating_db(
            "wbr_profiles",
            _chain_table([]),       # uniqueness check
            _chain_table([created]),  # insert
        )
        svc = WBRProfileService(db)
        result = svc.create_profile(
            {"client_id": "c1", "marketplace_code": "us", "display_name": "US"},
            user_id="u1",
        )
        assert result == created

    def test_rejects_duplicate(self):
        db = _db_with_tables(wbr_profiles=_chain_table([{"id": "p1"}]))
        svc = WBRProfileService(db)
        with pytest.raises(WBRValidationError, match="already exists"):
            svc.create_profile({"client_id": "c1", "marketplace_code": "US", "display_name": "US"})

    def test_normalizes_marketplace_code_to_uppercase(self):
        db = _rotating_db(
            "wbr_profiles",
            _chain_table([]),  # uniqueness check
            _chain_table([{"id": "p1", "marketplace_code": "US"}]),  # insert
        )
        svc = WBRProfileService(db)
        payload = {"client_id": "c1", "marketplace_code": "  us  ", "display_name": "US"}
        svc.create_profile(payload)
        assert payload["marketplace_code"] == "US"

    def test_rejects_invalid_week_start_day(self):
        db = _db_with_tables(wbr_profiles=_chain_table([]))
        svc = WBRProfileService(db)
        with pytest.raises(WBRValidationError, match="week_start_day"):
            svc.create_profile({
                "client_id": "c1", "marketplace_code": "US",
                "display_name": "US", "week_start_day": "friday",
            })

    def test_rejects_invalid_status(self):
        db = _db_with_tables(wbr_profiles=_chain_table([]))
        svc = WBRProfileService(db)
        with pytest.raises(WBRValidationError, match="status"):
            svc.create_profile({
                "client_id": "c1", "marketplace_code": "US",
                "display_name": "US", "status": "deleted",
            })

    def test_translates_pg_unique_constraint(self):
        """Supabase constraint error on insert becomes WBRValidationError."""
        check_table = _chain_table([])  # uniqueness check passes
        insert_table = _chain_table_that_raises(
            _pg_error("duplicate key value violates unique constraint \"uq_wbr_profiles_client_marketplace\"")
        )
        db = _rotating_db("wbr_profiles", check_table, insert_table)
        svc = WBRProfileService(db)
        with pytest.raises(WBRValidationError, match="already exists"):
            svc.create_profile({"client_id": "c1", "marketplace_code": "US", "display_name": "US"})


class TestUpdateProfile:
    def test_updates_and_returns(self):
        db = _rotating_db(
            "wbr_profiles",
            _chain_table([{"id": "p1", "display_name": "Old"}]),  # get
            _chain_table([{"id": "p1", "display_name": "Updated"}]),  # update
        )
        svc = WBRProfileService(db)
        result = svc.update_profile("p1", {"display_name": "Updated"}, user_id="u1")
        assert result["display_name"] == "Updated"

    def test_raises_not_found(self):
        db = _db_with_tables(wbr_profiles=_chain_table([]))
        svc = WBRProfileService(db)
        with pytest.raises(WBRNotFoundError, match="not found"):
            svc.update_profile("missing", {"display_name": "x"})

    def test_normalizes_marketplace_code_on_update(self):
        db = _rotating_db(
            "wbr_profiles",
            _chain_table([{"id": "p1"}]),  # get
            _chain_table([{"id": "p1", "marketplace_code": "UK"}]),  # update
        )
        svc = WBRProfileService(db)
        updates = {"marketplace_code": "uk"}
        svc.update_profile("p1", updates)
        assert updates["marketplace_code"] == "UK"


# ==================================================================
# Row tests
# ==================================================================


class TestListRows:
    def test_returns_active_rows(self):
        rows = [{"id": "r1", "row_label": "Organic", "active": True}]
        db = _multi_table_db({
            "wbr_profiles": [_chain_table([{"id": "p1"}])],
            "wbr_rows": [_chain_table(rows)],
        })
        svc = WBRProfileService(db)
        assert svc.list_rows("p1") == rows

    def test_raises_not_found_for_missing_profile(self):
        db = _db_with_tables(wbr_profiles=_chain_table([]))
        svc = WBRProfileService(db)
        with pytest.raises(WBRNotFoundError, match="not found"):
            svc.list_rows("missing")


class TestCreateRow:
    def test_creates_row(self):
        created = {"id": "r1", "profile_id": "p1", "row_label": "PPC", "row_kind": "leaf"}
        db = _multi_table_db({
            "wbr_profiles": [_chain_table([{"id": "p1"}])],
            "wbr_rows": [_chain_table([created])],
        })
        svc = WBRProfileService(db)
        result = svc.create_row("p1", {"row_label": "PPC", "row_kind": "leaf"}, user_id="u1")
        assert result == created

    def test_raises_not_found_for_missing_profile(self):
        db = _db_with_tables(wbr_profiles=_chain_table([]))
        svc = WBRProfileService(db)
        with pytest.raises(WBRNotFoundError, match="not found"):
            svc.create_row("missing", {"row_label": "x", "row_kind": "leaf"})

    def test_translates_duplicate_row_constraint(self):
        profile_table = _chain_table([{"id": "p1"}])
        insert_table = _chain_table_that_raises(
            _pg_error("duplicate key value violates unique constraint \"uq_wbr_rows_profile_kind_label_active\"")
        )
        db = _multi_table_db({
            "wbr_profiles": [profile_table],
            "wbr_rows": [insert_table],
        })
        svc = WBRProfileService(db)
        with pytest.raises(WBRValidationError, match="active row with this label"):
            svc.create_row("p1", {"row_label": "PPC", "row_kind": "leaf"})

    def test_translates_hierarchy_trigger_error(self):
        """parent_row_id on a parent-kind row: guard passes (parent is active),
        but the DB trigger rejects it."""
        profile_table = _chain_table([{"id": "p1"}])
        parent_row = _chain_table([{"id": "r99", "active": True, "row_kind": "parent"}])
        insert_table = _chain_table_that_raises(
            _pg_error("Parent rows cannot have a parent_row_id in WBR v1")
        )
        db = _multi_table_db({
            "wbr_profiles": [profile_table],
            "wbr_rows": [parent_row, insert_table],  # guard lookup, then insert
        })
        svc = WBRProfileService(db)
        with pytest.raises(WBRValidationError, match="parent_row_id"):
            svc.create_row("p1", {"row_label": "X", "row_kind": "parent", "parent_row_id": "r99"})

    def test_rejects_inactive_parent_on_create(self):
        """Cannot create a leaf row under an inactive parent."""
        profile_table = _chain_table([{"id": "p1"}])
        inactive_parent = _chain_table([{"id": "r99", "active": False, "row_kind": "parent"}])
        db = _multi_table_db({
            "wbr_profiles": [profile_table],
            "wbr_rows": [inactive_parent],
        })
        svc = WBRProfileService(db)
        with pytest.raises(WBRValidationError, match="inactive parent"):
            svc.create_row("p1", {"row_label": "X", "row_kind": "leaf", "parent_row_id": "r99"})

    def test_allows_null_parent_row_id(self):
        """Leaf rows with no parent_row_id should be created without parent check."""
        created = {"id": "r1", "profile_id": "p1", "row_label": "Solo", "row_kind": "leaf"}
        db = _multi_table_db({
            "wbr_profiles": [_chain_table([{"id": "p1"}])],
            "wbr_rows": [_chain_table([created])],
        })
        svc = WBRProfileService(db)
        result = svc.create_row("p1", {"row_label": "Solo", "row_kind": "leaf"})
        assert result == created


class TestUpdateRow:
    def test_updates_row(self):
        db = _rotating_db(
            "wbr_rows",
            _chain_table([{"id": "r1", "row_kind": "leaf", "active": True}]),  # get
            _chain_table([{"id": "r1", "row_label": "Updated"}]),  # update
        )
        svc = WBRProfileService(db)
        result = svc.update_row("r1", {"row_label": "Updated"})
        assert result["row_label"] == "Updated"

    def test_raises_not_found(self):
        db = _db_with_tables(wbr_rows=_chain_table([]))
        svc = WBRProfileService(db)
        with pytest.raises(WBRNotFoundError, match="not found"):
            svc.update_row("missing", {"row_label": "x"})

    def test_deactivating_parent_with_active_children_raises(self):
        """PATCH with active=false on parent that has active children → 400."""
        parent = {"id": "r1", "row_kind": "parent", "active": True}
        children_check = _chain_table([{"id": "child1"}])  # active child exists
        db = _rotating_db(
            "wbr_rows",
            _chain_table([parent]),  # _get_row
            children_check,          # _guard_parent_deactivation
        )
        svc = WBRProfileService(db)
        with pytest.raises(WBRValidationError, match="active child rows"):
            svc.update_row("r1", {"active": False})

    def test_deactivating_leaf_row_via_patch_succeeds(self):
        """PATCH active=false on a leaf row should succeed without child check."""
        leaf = {"id": "r1", "row_kind": "leaf", "active": True}
        db = _rotating_db(
            "wbr_rows",
            _chain_table([leaf]),                          # _get_row
            _chain_table([{"id": "r1", "active": False}]),  # update
        )
        svc = WBRProfileService(db)
        result = svc.update_row("r1", {"active": False})
        assert result["active"] is False

    def test_rejects_assigning_inactive_parent_on_update(self):
        """Updating parent_row_id to an inactive parent should fail."""
        existing = {"id": "r1", "row_kind": "leaf", "active": True, "parent_row_id": None}
        inactive_parent = {"id": "r99", "active": False, "row_kind": "parent"}
        db = _rotating_db(
            "wbr_rows",
            _chain_table([existing]),        # _get_row for r1
            _chain_table([inactive_parent]),  # _guard_inactive_parent → _get_row for r99
        )
        svc = WBRProfileService(db)
        with pytest.raises(WBRValidationError, match="inactive parent"):
            svc.update_row("r1", {"parent_row_id": "r99"})

    def test_rejects_active_row_already_under_inactive_parent(self):
        """An active row whose existing parent is now inactive cannot be updated
        (e.g. label change) while still linked to inactive parent."""
        existing = {"id": "r1", "row_kind": "leaf", "active": True, "parent_row_id": "r99"}
        inactive_parent = {"id": "r99", "active": False, "row_kind": "parent"}
        db = _rotating_db(
            "wbr_rows",
            _chain_table([existing]),        # _get_row for r1
            _chain_table([inactive_parent]),  # _guard_inactive_parent → _get_row for r99
        )
        svc = WBRProfileService(db)
        with pytest.raises(WBRValidationError, match="inactive parent"):
            svc.update_row("r1", {"row_label": "Renamed"})

    def test_allows_inactive_row_to_keep_inactive_parent(self):
        """An inactive row can keep its historical linkage to an inactive parent."""
        existing = {"id": "r1", "row_kind": "leaf", "active": False, "parent_row_id": "r99"}
        db = _rotating_db(
            "wbr_rows",
            _chain_table([existing]),                               # _get_row
            _chain_table([{"id": "r1", "row_label": "Renamed"}]),   # update
        )
        svc = WBRProfileService(db)
        result = svc.update_row("r1", {"row_label": "Renamed"})
        assert result["row_label"] == "Renamed"


class TestSoftDeleteRow:
    def test_deactivates_active_leaf_row(self):
        leaf = {"id": "r1", "row_kind": "leaf", "active": True}
        db = _rotating_db(
            "wbr_rows",
            _chain_table([leaf]),                          # _get_row
            _chain_table([{"id": "r1", "active": False}]),  # update
        )
        svc = WBRProfileService(db)
        result = svc.soft_delete_row("r1", user_id="u1")
        assert result["active"] is False

    def test_raises_when_already_inactive(self):
        db = _db_with_tables(wbr_rows=_chain_table([{"id": "r1", "active": False}]))
        svc = WBRProfileService(db)
        with pytest.raises(WBRValidationError, match="already inactive"):
            svc.soft_delete_row("r1")

    def test_raises_not_found(self):
        db = _db_with_tables(wbr_rows=_chain_table([]))
        svc = WBRProfileService(db)
        with pytest.raises(WBRNotFoundError, match="not found"):
            svc.soft_delete_row("missing")

    def test_rejects_deactivating_parent_with_active_children(self):
        parent = {"id": "r1", "row_kind": "parent", "active": True}
        children_check = _chain_table([{"id": "child1"}])
        db = _rotating_db(
            "wbr_rows",
            _chain_table([parent]),  # _get_row
            children_check,          # _guard_parent_deactivation
        )
        svc = WBRProfileService(db)
        with pytest.raises(WBRValidationError, match="active child rows"):
            svc.soft_delete_row("r1")

    def test_allows_deactivating_parent_with_no_active_children(self):
        parent = {"id": "r1", "row_kind": "parent", "active": True}
        db = _rotating_db(
            "wbr_rows",
            _chain_table([parent]),                        # _get_row
            _chain_table([]),                              # _guard (no active children)
            _chain_table([{"id": "r1", "active": False}]),  # update
        )
        svc = WBRProfileService(db)
        result = svc.soft_delete_row("r1")
        assert result["active"] is False


class TestHardDeleteRow:
    def test_deletes_leaf_row_permanently(self):
        leaf = {"id": "r1", "row_kind": "leaf", "active": True}
        db = _multi_table_db({
            "wbr_rows": [
                _chain_table([leaf]),  # _get_row
                _chain_table([]),      # delete
            ],
            "wbr_asin_row_map": [_chain_table([])],
            "wbr_pacvue_campaign_map": [_chain_table([])],
        })
        svc = WBRProfileService(db)
        result = svc.hard_delete_row("r1")
        assert result == leaf

    def test_rejects_permanent_delete_for_parent_with_children(self):
        parent = {"id": "r1", "row_kind": "parent", "active": True}
        db = _rotating_db(
            "wbr_rows",
            _chain_table([parent]),  # _get_row
            _chain_table([{"id": "child1"}]),  # _guard_parent_hard_delete
        )
        svc = WBRProfileService(db)
        with pytest.raises(WBRValidationError, match="still has child rows"):
            svc.hard_delete_row("r1")

    def test_rejects_permanent_delete_when_asin_mapping_exists(self):
        leaf = {"id": "r1", "row_kind": "leaf", "active": True}
        db = _multi_table_db({
            "wbr_rows": [_chain_table([leaf])],
            "wbr_asin_row_map": [_chain_table([{"id": "m1"}])],
            "wbr_pacvue_campaign_map": [],
        })
        svc = WBRProfileService(db)
        with pytest.raises(WBRValidationError, match="ASIN mappings"):
            svc.hard_delete_row("r1")

    def test_rejects_permanent_delete_when_campaign_mapping_exists(self):
        leaf = {"id": "r1", "row_kind": "leaf", "active": True}
        db = _multi_table_db({
            "wbr_rows": [_chain_table([leaf])],
            "wbr_asin_row_map": [_chain_table([])],
            "wbr_pacvue_campaign_map": [_chain_table([{"id": "m1"}])],
        })
        svc = WBRProfileService(db)
        with pytest.raises(WBRValidationError, match="campaign mappings"):
            svc.hard_delete_row("r1")
