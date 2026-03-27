"""
Unit tests for SearchTermFactsService.

These tests stub the Supabase client directly so they catch wrong column names,
missing filters, and off-by-one pagination — without a live database or the
FastAPI app import chain.
"""
from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from app.services.wbr.search_term_facts import SearchTermFactsService


def _make_db(rows: list[dict]) -> MagicMock:
    """Return a mock Supabase Client whose query chain yields `rows`."""
    resp = MagicMock()
    resp.data = rows

    # Every chained method returns the same mock so .eq().gte()... all work.
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.gte.return_value = query
    query.lte.return_value = query
    query.ilike.return_value = query
    query.order.return_value = query
    query.range.return_value = query
    query.execute.return_value = resp

    db = MagicMock()
    db.table.return_value = query
    return db, query


# ------------------------------------------------------------------
# Column name — the bug this test was written to catch
# ------------------------------------------------------------------

def test_list_facts_filters_on_profile_id_column():
    """Service must use 'profile_id', not 'wbr_profile_id'."""
    db, query = _make_db([])
    svc = SearchTermFactsService(db)

    svc.list_facts("pid-123")

    db.table.assert_called_once_with("search_term_daily_facts")
    # Collect every .eq(column, value) call
    eq_calls = [c for c in query.eq.call_args_list]
    eq_columns = [c.args[0] for c in eq_calls]

    assert "profile_id" in eq_columns, (
        f"Expected eq('profile_id', ...) but got eq calls: {eq_columns}"
    )
    assert "wbr_profile_id" not in eq_columns, (
        "Wrong column 'wbr_profile_id' used — should be 'profile_id'"
    )

    # Confirm the value passed is the profile_id argument
    profile_eq = next(c for c in eq_calls if c.args[0] == "profile_id")
    assert profile_eq.args[1] == "pid-123"


# ------------------------------------------------------------------
# Pagination
# ------------------------------------------------------------------

def test_list_facts_has_more_false_when_fewer_rows_than_limit():
    db, _ = _make_db([{"id": "r1"}, {"id": "r2"}])
    svc = SearchTermFactsService(db)

    result = svc.list_facts("pid-1", limit=10)

    assert result["has_more"] is False
    assert len(result["facts"]) == 2


def test_list_facts_has_more_true_when_extra_row_present():
    # Simulate limit=2: service fetches limit+1=3 rows
    db, _ = _make_db([{"id": "r1"}, {"id": "r2"}, {"id": "r3"}])
    svc = SearchTermFactsService(db)

    result = svc.list_facts("pid-1", limit=2)

    assert result["has_more"] is True
    assert len(result["facts"]) == 2  # extra row trimmed


def test_list_facts_range_uses_limit_plus_one():
    db, query = _make_db([])
    svc = SearchTermFactsService(db)

    svc.list_facts("pid-1", limit=50, offset=100)

    # range(start, end) where end = offset + (limit+1) - 1 = 150
    query.range.assert_called_once_with(100, 150)


# ------------------------------------------------------------------
# Optional filters are only applied when provided
# ------------------------------------------------------------------

def test_list_facts_no_optional_filters_by_default():
    db, query = _make_db([])
    svc = SearchTermFactsService(db)

    svc.list_facts("pid-1")

    eq_calls = [c.args[0] for c in query.eq.call_args_list]
    # Only the profile_id eq should be present
    assert eq_calls == ["profile_id"]
    assert query.gte.call_count == 0
    assert query.lte.call_count == 0
    assert query.ilike.call_count == 0


def test_list_facts_applies_date_filters():
    db, query = _make_db([])
    svc = SearchTermFactsService(db)

    svc.list_facts("pid-1", date_from="2026-01-01", date_to="2026-03-01")

    query.gte.assert_called_once_with("report_date", "2026-01-01")
    query.lte.assert_called_once_with("report_date", "2026-03-01")


def test_list_facts_applies_text_filters():
    db, query = _make_db([])
    svc = SearchTermFactsService(db)

    svc.list_facts("pid-1", campaign_name_contains="shoes", search_term_contains="run")

    ilike_calls = {c.args[0]: c.args[1] for c in query.ilike.call_args_list}
    assert ilike_calls["campaign_name"] == "%shoes%"
    assert ilike_calls["search_term"] == "%run%"


def test_list_facts_applies_campaign_type_filter():
    db, query = _make_db([])
    svc = SearchTermFactsService(db)

    svc.list_facts("pid-1", campaign_type="sponsored_products")

    eq_calls = {c.args[0]: c.args[1] for c in query.eq.call_args_list}
    assert eq_calls.get("campaign_type") == "sponsored_products"
