"""Tests for WBR campaign scope service."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.wbr.campaign_scope import (
    get_scope_for_campaign,
    list_scope_for_profile,
    rebuild_campaign_scope_for_profile,
)
from app.services.wbr.profiles import WBRNotFoundError, WBRValidationError


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _chain_table(response_data: list[dict] | None = None) -> MagicMock:
    table = MagicMock()
    table.select.return_value = table
    table.insert.return_value = table
    table.update.return_value = table
    table.eq.return_value = table
    table.in_.return_value = table
    table.order.return_value = table
    table.limit.return_value = table
    table.range.return_value = table
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
    db.rpc = MagicMock()
    return db


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

PROFILE = {"id": "p1"}

# Row tree:
#   parent-row (pr1)
#     lr1 (leaf, active)
#     lr2 (leaf, INACTIVE)
#   lr3 (leaf, active, no parent)
ROWS_SIMPLE = [
    {"id": "pr1", "row_kind": "parent", "parent_row_id": None,  "active": True},
    {"id": "lr1", "row_kind": "leaf",   "parent_row_id": "pr1", "active": True},
    {"id": "lr2", "row_kind": "leaf",   "parent_row_id": "pr1", "active": False},
    {"id": "lr3", "row_kind": "leaf",   "parent_row_id": None,  "active": True},
]


def _db_for_rebuild(
    *,
    campaign_map: list[dict],
    rows: list[dict],
    asin_row_map: list[dict],
    insert_returns: list[dict] | None = None,
    rpc_result: int | str | None = None,
) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Build a mock DB for the safe-rebuild sequence.

    Scope table call order:
      1. insert staged inactive rows
      2. rpc activate_search_term_campaign_scope(...)

    Returns (db, insert_table, rpc_call).
    """
    inserted = insert_returns if insert_returns is not None else [{"id": "s1"}]
    insert_table = _chain_table(inserted)

    db = _multi_table_db(
        {
            "wbr_profiles":               [_chain_table([PROFILE])],
            "wbr_pacvue_campaign_map":    [_chain_table(campaign_map)],
            "wbr_rows":                   [_chain_table(rows)],
            "wbr_asin_row_map":           [_chain_table(asin_row_map)],
            "search_term_campaign_scope": [insert_table],
        }
    )
    rpc_call = MagicMock()
    rpc_response = MagicMock()
    rpc_response.data = len(inserted) if rpc_result is None else rpc_result
    rpc_call.execute.return_value = rpc_response
    db.rpc.return_value = rpc_call
    return db, insert_table, rpc_call


# ---------------------------------------------------------------------------
# TestRebuildCampaignScope
# ---------------------------------------------------------------------------


class TestRebuildCampaignScope:
    def test_campaign_with_direct_leaf_row_resolves_asin_scope(self):
        """A campaign mapped directly to an active leaf row produces a scope row."""
        db, insert_table, rpc_call = _db_for_rebuild(
            campaign_map=[{"campaign_name": "SP-Widget", "row_id": "lr3"}],
            rows=ROWS_SIMPLE,
            asin_row_map=[{"child_asin": "B000000001", "row_id": "lr3"}],
            insert_returns=[{"id": "s1"}],
        )

        result = rebuild_campaign_scope_for_profile(db, "p1")

        assert result["rebuilt"] == 1
        assert result["campaigns_skipped_no_asin"] == 0

        # New rows inserted as inactive first
        payload = insert_table.insert.call_args.args[0][0]
        assert payload["active"] is False
        assert payload["campaign_name"] == "SP-Widget"
        assert "B000000001" in payload["resolved_child_asins"]

        db.rpc.assert_called_once_with(
            "activate_search_term_campaign_scope",
            {"p_profile_id": "p1", "p_scope_ids": ["s1"]},
        )
        rpc_call.execute.assert_called_once()

    def test_campaign_via_parent_row_resolves_active_leaf_descendants(self):
        """Campaign mapped to a parent row: only active leaf descendants are resolved."""
        db, insert_table, _ = _db_for_rebuild(
            campaign_map=[{"campaign_name": "SP-Widget", "row_id": "pr1"}],
            rows=ROWS_SIMPLE,
            asin_row_map=[
                {"child_asin": "B000000001", "row_id": "lr1"},
                {"child_asin": "B000000002", "row_id": "lr2"},  # lr2 is inactive
            ],
            insert_returns=[{"id": "s1"}],
        )

        result = rebuild_campaign_scope_for_profile(db, "p1")

        assert result["rebuilt"] == 1
        payload = insert_table.insert.call_args.args[0][0]
        assert "lr1" in payload["resolved_row_ids"]
        assert "lr2" not in payload["resolved_row_ids"]
        assert "B000000001" in payload["resolved_child_asins"]
        assert "B000000002" not in payload["resolved_child_asins"]

    def test_duplicate_asins_across_rows_are_deduped(self):
        """Same ASIN mapped to multiple leaves under a campaign appears once."""
        db, insert_table, _ = _db_for_rebuild(
            campaign_map=[{"campaign_name": "SP-Widget", "row_id": "pr1"}],
            rows=[
                {"id": "pr1", "row_kind": "parent", "parent_row_id": None,  "active": True},
                {"id": "lr1", "row_kind": "leaf",   "parent_row_id": "pr1", "active": True},
                {"id": "lr3", "row_kind": "leaf",   "parent_row_id": "pr1", "active": True},
            ],
            asin_row_map=[
                {"child_asin": "B000000001", "row_id": "lr1"},
                {"child_asin": "B000000001", "row_id": "lr3"},  # duplicate
            ],
            insert_returns=[{"id": "s1"}],
        )

        result = rebuild_campaign_scope_for_profile(db, "p1")

        assert result["rebuilt"] == 1
        payload = insert_table.insert.call_args.args[0][0]
        assert payload["resolved_child_asins"].count("B000000001") == 1

    def test_campaign_with_no_asin_mappings_is_skipped(self):
        """Campaign whose resolved leaves have no ASIN mappings is skipped."""
        # No payloads → scope table is never called at all
        db = _multi_table_db(
            {
                "wbr_profiles":            [_chain_table([PROFILE])],
                "wbr_pacvue_campaign_map": [_chain_table([{"campaign_name": "SP-Widget", "row_id": "lr3"}])],
                "wbr_rows":                [_chain_table(ROWS_SIMPLE)],
                "wbr_asin_row_map":        [_chain_table([])],
                # search_term_campaign_scope NOT listed — would error if called
            }
        )

        result = rebuild_campaign_scope_for_profile(db, "p1")

        assert result["rebuilt"] == 0
        assert result["campaigns_skipped_no_asin"] == 1

    def test_inactive_campaign_map_rows_are_ignored(self):
        """No active campaign map rows → no inserts and no deactivation."""
        db = _multi_table_db(
            {
                "wbr_profiles":            [_chain_table([PROFILE])],
                "wbr_pacvue_campaign_map": [_chain_table([])],  # no active campaigns
                "wbr_rows":                [_chain_table(ROWS_SIMPLE)],
                "wbr_asin_row_map":        [_chain_table([{"child_asin": "B000000001", "row_id": "lr3"}])],
                # search_term_campaign_scope NOT listed — would error if called
            }
        )

        result = rebuild_campaign_scope_for_profile(db, "p1")

        assert result["rebuilt"] == 0
        assert result["campaigns_skipped_no_asin"] == 0

    def test_empty_payloads_do_not_deactivate_existing_scope(self):
        """If no scope rows would be inserted, existing active rows are preserved."""
        # Router has no scope table entry — any call to it would raise StopIteration
        db = _multi_table_db(
            {
                "wbr_profiles":            [_chain_table([PROFILE])],
                "wbr_pacvue_campaign_map": [_chain_table([])],
                "wbr_rows":                [_chain_table(ROWS_SIMPLE)],
                "wbr_asin_row_map":        [_chain_table([])],
            }
        )

        result = rebuild_campaign_scope_for_profile(db, "p1")

        # Scope table was never touched
        tables_called = [c.args[0] for c in db.table.call_args_list]
        assert "search_term_campaign_scope" not in tables_called
        assert result["rebuilt"] == 0

    def test_insert_failure_does_not_deactivate_existing_scope(self):
        """If insert returns wrong row count, deactivation is never reached."""
        # insert_table returns empty list — simulates a failed insert
        insert_table = _chain_table([])  # 0 rows back for 1 payload → triggers error

        db = _multi_table_db(
            {
                "wbr_profiles":            [_chain_table([PROFILE])],
                "wbr_pacvue_campaign_map": [_chain_table([{"campaign_name": "SP-Widget", "row_id": "lr3"}])],
                "wbr_rows":                [_chain_table(ROWS_SIMPLE)],
                "wbr_asin_row_map":        [_chain_table([{"child_asin": "B000000001", "row_id": "lr3"}])],
                "search_term_campaign_scope": [insert_table],
            }
        )
        db.rpc = MagicMock()

        with pytest.raises(WBRValidationError, match="row count mismatch"):
            rebuild_campaign_scope_for_profile(db, "p1")

        db.rpc.assert_not_called()

    def test_rebuild_inserts_then_calls_atomic_swap_rpc(self):
        """Ordering: stage inserts first, then call the atomic swap RPC."""
        call_order: list[str] = []

        def _resp(data):
            r = MagicMock()
            r.data = data
            return r

        insert_table = _chain_table()
        insert_table.execute.side_effect = lambda: (call_order.append("insert"), _resp([{"id": "s1"}]))[1]

        db = _multi_table_db(
            {
                "wbr_profiles":            [_chain_table([PROFILE])],
                "wbr_pacvue_campaign_map": [_chain_table([{"campaign_name": "SP-Widget", "row_id": "lr3"}])],
                "wbr_rows":                [_chain_table(ROWS_SIMPLE)],
                "wbr_asin_row_map":        [_chain_table([{"child_asin": "B000000001", "row_id": "lr3"}])],
                "search_term_campaign_scope": [insert_table],
            }
        )
        rpc_call = MagicMock()
        rpc_call.execute.side_effect = lambda: (call_order.append("swap"), _resp(1))[1]
        db.rpc.return_value = rpc_call

        rebuild_campaign_scope_for_profile(db, "p1")

        assert call_order == ["insert", "swap"]


    def test_atomic_swap_rpc_failure_raises(self):
        """If the atomic swap RPC fails, the error surfaces after staging inserts."""
        db, _, _ = _db_for_rebuild(
            campaign_map=[{"campaign_name": "SP-Widget", "row_id": "lr3"}],
            rows=ROWS_SIMPLE,
            asin_row_map=[{"child_asin": "B000000001", "row_id": "lr3"}],
            insert_returns=[{"id": "s1"}],
            rpc_result=0,
        )

        with pytest.raises(WBRValidationError, match="activate"):
            rebuild_campaign_scope_for_profile(db, "p1")

    def test_unknown_profile_raises_not_found(self):
        db = _multi_table_db({"wbr_profiles": [_chain_table([])]})
        with pytest.raises(WBRNotFoundError, match="p1"):
            rebuild_campaign_scope_for_profile(db, "p1")


# ---------------------------------------------------------------------------
# TestGetScopeForCampaign
# ---------------------------------------------------------------------------


class TestGetScopeForCampaign:
    def test_returns_scope_row_when_found(self):
        scope_row = {"id": "s1", "campaign_name": "SP-Widget", "resolved_child_asins": ["B000000001"]}
        db = _multi_table_db(
            {
                "wbr_profiles":               [_chain_table([PROFILE])],
                "search_term_campaign_scope": [_chain_table([scope_row])],
            }
        )
        result = get_scope_for_campaign(db, "p1", "SP-Widget")
        assert result == scope_row

    def test_returns_none_when_not_found(self):
        db = _multi_table_db(
            {
                "wbr_profiles":               [_chain_table([PROFILE])],
                "search_term_campaign_scope": [_chain_table([])],
            }
        )
        result = get_scope_for_campaign(db, "p1", "SP-Widget")
        assert result is None

    def test_raises_for_unknown_profile(self):
        db = _multi_table_db({"wbr_profiles": [_chain_table([])]})
        with pytest.raises(WBRNotFoundError, match="p1"):
            get_scope_for_campaign(db, "p1", "SP-Widget")


# ---------------------------------------------------------------------------
# TestListScopeForProfile
# ---------------------------------------------------------------------------


class TestListScopeForProfile:
    def test_returns_scope_rows_for_valid_profile(self):
        rows = [
            {"id": "s1", "campaign_name": "Alpha"},
            {"id": "s2", "campaign_name": "Beta"},
        ]
        db = _multi_table_db(
            {
                "wbr_profiles":               [_chain_table([PROFILE])],
                "search_term_campaign_scope": [_chain_table(rows)],
            }
        )
        result = list_scope_for_profile(db, "p1")
        assert len(result) == 2
        assert result[0]["campaign_name"] == "Alpha"

    def test_returns_empty_list_when_no_scope_rows(self):
        db = _multi_table_db(
            {
                "wbr_profiles":               [_chain_table([PROFILE])],
                "search_term_campaign_scope": [_chain_table([])],
            }
        )
        result = list_scope_for_profile(db, "p1")
        assert result == []

    def test_raises_for_unknown_profile(self):
        db = _multi_table_db({"wbr_profiles": [_chain_table([])]})
        with pytest.raises(WBRNotFoundError, match="p1"):
            list_scope_for_profile(db, "p1")
