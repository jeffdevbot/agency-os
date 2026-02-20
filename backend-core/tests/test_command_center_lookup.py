"""Tests for C11A: Command Center read-only lookup functions.

Covers:
- Client lookup: with query, empty query, no results
- Brand listing: all, filtered by client, empty
- Mapping audit: finds missing, all mapped
- Slack formatters: output content, empty states
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.services.agencyclaw.command_center_lookup import (
    audit_brand_mappings,
    format_brand_list,
    format_client_list,
    format_mapping_audit,
    list_brands,
    lookup_clients,
)


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _mock_db(
    rows: list[dict[str, Any]] | None = None,
    *,
    assignment_rows: list[dict[str, Any]] | None = None,
) -> MagicMock:
    """Build a mock Supabase client that returns ``rows`` on queries."""
    db = MagicMock()
    response = MagicMock()
    response.data = rows if rows is not None else []

    # Main chain
    table = MagicMock()
    db.table.return_value = table
    table.select.return_value = table
    table.eq.return_value = table
    table.ilike.return_value = table
    table.order.return_value = table
    table.limit.return_value = table
    table.execute.return_value = response

    return db


def _brand_row(
    name: str = "Brand A",
    client_name: str = "Client X",
    client_id: str = "c1",
    space_id: str | None = "space-1",
    list_id: str | None = "list-1",
) -> dict[str, Any]:
    return {
        "id": f"b-{name.lower().replace(' ', '-')}",
        "name": name,
        "client_id": client_id,
        "clickup_space_id": space_id,
        "clickup_list_id": list_id,
        "agency_clients": {"name": client_name},
    }


def _client_row(name: str = "Distex", status: str = "active") -> dict[str, Any]:
    return {"id": f"c-{name.lower()}", "name": name, "status": status}


# ---------------------------------------------------------------------------
# Client lookup tests
# ---------------------------------------------------------------------------


class TestLookupClients:
    def test_with_query_returns_matches(self):
        rows = [_client_row("Distex"), _client_row("Acme")]
        db = _mock_db(rows)

        result = lookup_clients(db, profile_id=None, query="dist")

        assert len(result) == 2
        assert result[0]["name"] == "Distex"
        db.table.assert_called_with("agency_clients")

    def test_empty_query_lists_active(self):
        """Empty query with no assignments falls back to all active clients."""
        db = MagicMock()

        # First call (assignments) returns empty
        assign_response = MagicMock()
        assign_response.data = []

        # Second call (active clients) returns data
        active_response = MagicMock()
        active_response.data = [_client_row("Distex")]

        table_mock = MagicMock()
        db.table.return_value = table_mock
        table_mock.select.return_value = table_mock
        table_mock.eq.return_value = table_mock
        table_mock.order.return_value = table_mock
        table_mock.limit.return_value = table_mock

        # First execute (assignments) empty, then active clients
        table_mock.execute.side_effect = [assign_response, assign_response, active_response]

        result = lookup_clients(db, profile_id="p1", query="")

        assert len(result) == 1
        assert result[0]["name"] == "Distex"

    def test_no_results_empty_list(self):
        db = _mock_db([])

        result = lookup_clients(db, profile_id="p1", query="nonexistent")

        assert result == []

    def test_none_profile_lists_all_active(self):
        rows = [_client_row("Alpha"), _client_row("Beta")]
        db = _mock_db(rows)

        result = lookup_clients(db, profile_id=None, query="")

        assert len(result) == 2

    def test_query_with_profile_id_filters_accessible_clients(self):
        """Query path should remain scoped to accessible/assigned clients."""
        db = MagicMock()

        assignments_response = MagicMock()
        assignments_response.data = [
            {"agency_clients": _client_row("Distex")},
            {"agency_clients": _client_row("Revant")},
        ]

        table_mock = MagicMock()
        db.table.return_value = table_mock
        table_mock.select.return_value = table_mock
        table_mock.eq.return_value = table_mock
        table_mock.order.return_value = table_mock
        table_mock.limit.return_value = table_mock
        table_mock.execute.return_value = assignments_response

        result = lookup_clients(db, profile_id="p1", query="rev")

        assert len(result) == 1
        assert result[0]["name"] == "Revant"

    def test_query_with_profile_id_returns_empty_when_no_match(self):
        db = MagicMock()

        assignments_response = MagicMock()
        assignments_response.data = [
            {"agency_clients": _client_row("Distex")},
        ]

        table_mock = MagicMock()
        db.table.return_value = table_mock
        table_mock.select.return_value = table_mock
        table_mock.eq.return_value = table_mock
        table_mock.order.return_value = table_mock
        table_mock.limit.return_value = table_mock
        table_mock.execute.return_value = assignments_response

        result = lookup_clients(db, profile_id="p1", query="axis")

        assert result == []


# ---------------------------------------------------------------------------
# Brand listing tests
# ---------------------------------------------------------------------------


class TestListBrands:
    def test_returns_brands_with_client_names(self):
        rows = [
            _brand_row("Brand A", "Client X"),
            _brand_row("Brand B", "Client Y", client_id="c2"),
        ]
        db = _mock_db(rows)

        result = list_brands(db)

        assert len(result) == 2
        assert result[0]["name"] == "Brand A"
        assert result[0]["client_name"] == "Client X"
        assert result[0]["clickup_space_id"] == "space-1"

    def test_filtered_by_client(self):
        rows = [_brand_row("Brand A", "Client X")]
        db = _mock_db(rows)

        result = list_brands(db, client_id="c1")

        assert len(result) == 1
        # Verify .eq was called (for client_id filter)
        db.table.return_value.eq.assert_called()

    def test_empty_brands(self):
        db = _mock_db([])

        result = list_brands(db)

        assert result == []

    def test_handles_missing_agency_clients_join(self):
        """Brand row with no agency_clients join data."""
        row = {
            "id": "b1",
            "name": "Orphan Brand",
            "client_id": "c1",
            "clickup_space_id": None,
            "clickup_list_id": None,
            "agency_clients": None,
        }
        db = _mock_db([row])

        result = list_brands(db)

        assert len(result) == 1
        assert result[0]["client_name"] == ""


# ---------------------------------------------------------------------------
# Mapping audit tests
# ---------------------------------------------------------------------------


class TestAuditBrandMappings:
    def test_finds_missing_both(self):
        rows = [_brand_row("No Map", space_id=None, list_id=None)]
        db = _mock_db(rows)

        result = audit_brand_mappings(db)

        assert len(result) == 1
        assert "clickup_space_id" in result[0]["missing_fields"]
        assert "clickup_list_id" in result[0]["missing_fields"]

    def test_finds_missing_list_only(self):
        rows = [_brand_row("Space Only", space_id="sp1", list_id=None)]
        db = _mock_db(rows)

        result = audit_brand_mappings(db)

        assert len(result) == 1
        assert result[0]["missing_fields"] == ["clickup_list_id"]

    def test_finds_missing_space_only(self):
        rows = [_brand_row("List Only", space_id=None, list_id="li1")]
        db = _mock_db(rows)

        result = audit_brand_mappings(db)

        assert len(result) == 1
        assert result[0]["missing_fields"] == ["clickup_space_id"]

    def test_all_mapped_returns_empty(self):
        rows = [_brand_row("Full", space_id="sp1", list_id="li1")]
        db = _mock_db(rows)

        result = audit_brand_mappings(db)

        assert result == []

    def test_mixed_mapped_and_unmapped(self):
        rows = [
            _brand_row("Mapped", space_id="sp1", list_id="li1"),
            _brand_row("Missing", space_id=None, list_id=None),
        ]
        db = _mock_db(rows)

        result = audit_brand_mappings(db)

        assert len(result) == 1
        assert result[0]["name"] == "Missing"


# ---------------------------------------------------------------------------
# Formatter tests
# ---------------------------------------------------------------------------


class TestFormatClientList:
    def test_output_has_bullet_list(self):
        clients = [_client_row("Distex"), _client_row("Acme")]
        text = format_client_list(clients)

        assert "*Clients*" in text
        assert "Distex" in text
        assert "Acme" in text
        assert "  - " in text

    def test_empty_clients(self):
        text = format_client_list([])

        assert "No clients found" in text

    def test_inactive_status_shown(self):
        clients = [{"id": "c1", "name": "Old Corp", "status": "inactive"}]
        text = format_client_list(clients)

        assert "inactive" in text


class TestFormatBrandList:
    def test_output_shows_mapping_status(self):
        brands = [
            {"name": "Full", "client_name": "X", "clickup_space_id": "s", "clickup_list_id": "l"},
            {"name": "None", "client_name": "Y", "clickup_space_id": None, "clickup_list_id": None},
        ]
        text = format_brand_list(brands)

        assert "*Brands*" in text
        assert "space + list" in text
        assert "no mapping" in text

    def test_empty_brands(self):
        text = format_brand_list([])

        assert "No brands found" in text

    def test_space_only_mapping(self):
        brands = [{"name": "B", "client_name": "", "clickup_space_id": "s", "clickup_list_id": None}]
        text = format_brand_list(brands)

        assert "space only" in text

    def test_list_only_mapping(self):
        brands = [{"name": "B", "client_name": "", "clickup_space_id": None, "clickup_list_id": "l"}]
        text = format_brand_list(brands)

        assert "list only" in text


class TestFormatMappingAudit:
    def test_output_groups_by_client(self):
        missing = [
            {"name": "B1", "client_name": "Client A", "missing_fields": ["clickup_space_id"]},
            {"name": "B2", "client_name": "Client A", "missing_fields": ["clickup_list_id"]},
            {"name": "B3", "client_name": "Client B", "missing_fields": ["clickup_space_id", "clickup_list_id"]},
        ]
        text = format_mapping_audit(missing)

        assert "*ClickUp Mapping Audit*" in text
        assert "3 brand(s)" in text
        assert "*Client A:*" in text
        assert "*Client B:*" in text

    def test_empty_audit(self):
        text = format_mapping_audit([])

        assert "All brands have ClickUp mappings" in text
        assert "Nothing to fix" in text
