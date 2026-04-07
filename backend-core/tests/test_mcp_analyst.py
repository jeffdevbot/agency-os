"""Tests for analyst-query MCP tools — Slice 0 + Slice 1.

Covers:
- service-layer validation and happy paths
- freshness note when date_to has no landed data
- MCP wrapper structured success and structured error
- server registration smoke test
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.mcp.server import create_mcp_server
from app.mcp.tools.analyst import register_analyst_tools
from app.services.analyst_query_tools import (
    AnalystQueryError,
    MAX_ASIN_COUNT,
    MAX_DATE_WINDOW_DAYS,
    MAX_PNL_MONTHS,
    MAX_RESULT_ROWS,
    get_asin_sales_window,
    get_sync_freshness_status,
    list_child_asins_for_row,
    query_ads_facts,
    query_business_facts,
    query_catalog_context,
    query_monthly_pnl_detail,
)


# ---------------------------------------------------------------------------
# Fake DB helpers
# ---------------------------------------------------------------------------


class _FakeQuery:
    """Minimal Supabase query-chain fake that supports the ops used by the
    analyst service layer."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = list(rows)
        self._filters: list[tuple[str, str, Any]] = []
        self._order_key: str | None = None
        self._order_desc: bool = False
        self._limit_val: int | None = None
        self._range_start: int | None = None
        self._range_end: int | None = None

    def select(self, *_args: Any, **_kwargs: Any) -> "_FakeQuery":
        return self

    def eq(self, key: str, value: Any) -> "_FakeQuery":
        self._filters.append(("eq", key, value))
        return self

    def gte(self, key: str, value: Any) -> "_FakeQuery":
        self._filters.append(("gte", key, value))
        return self

    def lte(self, key: str, value: Any) -> "_FakeQuery":
        self._filters.append(("lte", key, value))
        return self

    def in_(self, key: str, values: list[Any]) -> "_FakeQuery":
        self._filters.append(("in_", key, list(values)))
        return self

    def order(self, key: str, *_args: Any, desc: bool = False, **_kwargs: Any) -> "_FakeQuery":
        self._order_key = key
        self._order_desc = desc
        return self

    def limit(self, value: int) -> "_FakeQuery":
        self._limit_val = value
        return self

    def range(self, start: int, end: int) -> "_FakeQuery":
        self._range_start = start
        self._range_end = end
        return self

    def execute(self) -> Any:
        rows = list(self._rows)
        for op, key, value in self._filters:
            if op == "eq":
                rows = [r for r in rows if r.get(key) == value]
            elif op == "gte":
                rows = [r for r in rows if str(r.get(key) or "") >= str(value)]
            elif op == "lte":
                rows = [r for r in rows if str(r.get(key) or "") <= str(value)]
            elif op == "in_":
                rows = [r for r in rows if r.get(key) in value]

        if self._order_key:
            rows = sorted(
                rows,
                key=lambda r: str(r.get(self._order_key) or ""),
                reverse=self._order_desc,
            )
        if self._limit_val is not None:
            rows = rows[: self._limit_val]
        if self._range_start is not None and self._range_end is not None:
            rows = rows[self._range_start : self._range_end + 1]

        class _Resp:
            data = rows

        return _Resp()


class _FakeDB:
    """Multi-table fake Supabase DB for analyst query tests."""

    def __init__(self, tables: dict[str, list[dict[str, Any]]]) -> None:
        self._tables = tables

    def table(self, name: str) -> _FakeQuery:
        rows = self._tables.get(name, [])
        return _FakeQuery(rows)


# ---------------------------------------------------------------------------
# Shared fixtures / constants
# ---------------------------------------------------------------------------

_PROFILE_ID = "profile-001"
_ROW_ID_LEAF = "row-leaf-001"
_ROW_ID_PARENT = "row-parent-001"

_BASE_PROFILE = {
    "id": _PROFILE_ID,
    "client_id": "client-001",
    "marketplace_code": "US",
    "status": "active",
}

_DAILY_FACTS = [
    {
        "id": f"f{i}",
        "profile_id": _PROFILE_ID,
        "report_date": f"2026-03-{i + 10:02d}",
        "child_asin": "B0001",
        "unit_sales": 5,
        "sales": "50.00",
        "page_views": 100,
    }
    for i in range(7)  # 2026-03-10 through 2026-03-16
] + [
    {
        "id": f"g{i}",
        "profile_id": _PROFILE_ID,
        "report_date": f"2026-03-{i + 10:02d}",
        "child_asin": "B0002",
        "unit_sales": 3,
        "sales": "30.00",
        "page_views": 60,
    }
    for i in range(7)
]

# Ads campaign facts: "Brand SP" (sponsored_products) + "Brand SB" (sponsored_brands),
# 7 days each (2026-03-10 through 2026-03-16). Latest date stays at 2026-03-16.
_ADS_FACTS = [
    {
        "id": f"ad{i}",
        "profile_id": _PROFILE_ID,
        "report_date": f"2026-03-{i + 10:02d}",
        "campaign_name": "Brand SP",
        "campaign_type": "sponsored_products",
        "impressions": 100,
        "clicks": 10,
        "spend": "50.00",
        "orders": 2,
        "sales": "200.00",
    }
    for i in range(7)
] + [
    {
        "id": f"ae{i}",
        "profile_id": _PROFILE_ID,
        "report_date": f"2026-03-{i + 10:02d}",
        "campaign_name": "Brand SB",
        "campaign_type": "sponsored_brands",
        "impressions": 50,
        "clicks": 5,
        "spend": "25.00",
        "orders": 1,
        "sales": "100.00",
    }
    for i in range(7)
]

# Campaign map: "Brand SP" → ROW_ID_LEAF; "Brand SB" is intentionally unmapped.
_CAMPAIGN_MAP = [
    {
        "id": "cmap-1",
        "profile_id": _PROFILE_ID,
        "campaign_name": "Brand SP",
        "row_id": _ROW_ID_LEAF,
        "active": True,
    },
]


def _base_db(**overrides: list[dict[str, Any]]) -> _FakeDB:
    """Return a _FakeDB with sensible defaults, optionally overridden per table."""
    tables: dict[str, list[dict[str, Any]]] = {
        "wbr_profiles": [_BASE_PROFILE],
        "wbr_business_asin_daily": list(_DAILY_FACTS),
        "wbr_asin_row_map": [
            {
                "id": "map-1",
                "profile_id": _PROFILE_ID,
                "child_asin": "B0001",
                "row_id": _ROW_ID_LEAF,
                "active": True,
            },
            {
                "id": "map-2",
                "profile_id": _PROFILE_ID,
                "child_asin": "B0002",
                "row_id": _ROW_ID_LEAF,
                "active": True,
            },
        ],
        "wbr_rows": [
            {
                "id": _ROW_ID_LEAF,
                "profile_id": _PROFILE_ID,
                "row_label": "Screen Shine Pro",
                "row_kind": "leaf",
                "parent_row_id": _ROW_ID_PARENT,
                "sort_order": 1,
                "active": True,
            },
            {
                "id": _ROW_ID_PARENT,
                "profile_id": _PROFILE_ID,
                "row_label": "Screen Shine Group",
                "row_kind": "group",
                "parent_row_id": None,
                "sort_order": 0,
                "active": True,
            },
        ],
        "wbr_profile_child_asins": [
            {
                "id": "ca-1",
                "profile_id": _PROFILE_ID,
                "child_asin": "B0001",
                "child_sku": "SKU-001",
                "child_product_name": "Screen Shine Pro 8oz",
                "category": "Cleaning Supplies",
                "fulfillment_method": "FBA",
                "active": True,
            },
            {
                "id": "ca-2",
                "profile_id": _PROFILE_ID,
                "child_asin": "B0002",
                "child_sku": "SKU-002",
                "child_product_name": "Screen Shine Pro 16oz",
                "category": "Cleaning Supplies",
                "fulfillment_method": "FBA",
                "active": True,
            },
        ],
        "wbr_asin_exclusions": [],
        "wbr_sync_runs": [
            {
                "id": "sync-biz-1",
                "profile_id": _PROFILE_ID,
                "source_type": "windsor_business",
                "status": "success",
                "finished_at": "2026-03-17T03:00:00+00:00",
                "started_at": "2026-03-17T02:55:00+00:00",
            },
            {
                "id": "sync-ads-1",
                "profile_id": _PROFILE_ID,
                "source_type": "amazon_ads",
                "status": "success",
                "finished_at": "2026-03-17T04:00:00+00:00",
                "started_at": "2026-03-17T03:55:00+00:00",
            },
        ],
        "wbr_ads_campaign_daily": list(_ADS_FACTS),
        "wbr_pacvue_campaign_map": list(_CAMPAIGN_MAP),
    }
    tables.update(overrides)
    return _FakeDB(tables)


# ===========================================================================
# Service-layer tests — get_asin_sales_window
# ===========================================================================


def test_get_asin_sales_window_valid_query():
    """Happy path: two ASINs, full week of data, sums correctly."""
    db = _base_db()
    result = get_asin_sales_window(
        db, _PROFILE_ID, ["B0001", "B0002"], "2026-03-10", "2026-03-16"
    )

    assert result["profile_id"] == _PROFILE_ID
    assert result["date_from"] == "2026-03-10"
    assert result["date_to"] == "2026-03-16"

    asins_by_id = {row["child_asin"]: row for row in result["asins"]}

    # 7 days × 5 units = 35 for B0001
    assert asins_by_id["B0001"]["unit_sales"] == 35
    assert asins_by_id["B0001"]["sales"] == "350.00"
    assert asins_by_id["B0001"]["page_views"] == 700

    # 7 days × 3 units = 21 for B0002
    assert asins_by_id["B0002"]["unit_sales"] == 21

    # No freshness gap (date_to <= latest available 2026-03-16)
    assert result["freshness"]["note"] is None
    assert result["freshness"]["latest_available_date"] == "2026-03-16"

    # No latest_available_by_asin because there's no freshness gap
    assert "latest_available_by_asin" not in result


def test_get_asin_sales_window_freshness_note_when_date_to_beyond_data():
    """When date_to > latest available date, freshness note is set."""
    db = _base_db()
    result = get_asin_sales_window(
        db, _PROFILE_ID, ["B0001"], "2026-03-10", "2026-03-20"
    )

    assert result["freshness"]["note"] is not None
    assert "2026-03-20" in result["freshness"]["note"]
    assert "2026-03-16" in result["freshness"]["note"]


def test_get_asin_sales_window_include_latest_available_adds_snapshot():
    """When freshness gap exists and include_latest_available=True, snapshot is returned."""
    db = _base_db()
    result = get_asin_sales_window(
        db, _PROFILE_ID, ["B0001"], "2026-03-10", "2026-03-25", include_latest_available=True
    )

    assert result["freshness"]["note"] is not None
    assert "latest_available_by_asin" in result
    snaps = {row["child_asin"]: row for row in result["latest_available_by_asin"]}
    assert "B0001" in snaps
    assert snaps["B0001"]["report_date"] == "2026-03-16"


def test_get_asin_sales_window_no_latest_available_when_flag_false():
    """include_latest_available=False suppresses snapshot even when gap exists."""
    db = _base_db()
    result = get_asin_sales_window(
        db, _PROFILE_ID, ["B0001"], "2026-03-10", "2026-03-25", include_latest_available=False
    )

    assert result["freshness"]["note"] is not None
    assert "latest_available_by_asin" not in result


def test_get_asin_sales_window_raises_on_empty_asin_list():
    db = _base_db()
    with pytest.raises(AnalystQueryError, match="must not be empty"):
        get_asin_sales_window(db, _PROFILE_ID, [], "2026-03-10", "2026-03-16")


def test_get_asin_sales_window_raises_on_too_many_asins():
    db = _base_db()
    asins = [f"B{i:04d}" for i in range(MAX_ASIN_COUNT + 1)]
    with pytest.raises(AnalystQueryError, match="Too many ASINs"):
        get_asin_sales_window(db, _PROFILE_ID, asins, "2026-03-10", "2026-03-16")


def test_get_asin_sales_window_raises_on_reversed_dates():
    db = _base_db()
    with pytest.raises(AnalystQueryError, match="must not be after"):
        get_asin_sales_window(db, _PROFILE_ID, ["B0001"], "2026-03-16", "2026-03-10")


def test_get_asin_sales_window_raises_on_window_too_large():
    db = _base_db()
    with pytest.raises(AnalystQueryError, match="Limit is"):
        get_asin_sales_window(
            db, _PROFILE_ID, ["B0001"], "2024-01-01", "2026-01-01"
        )


def test_get_asin_sales_window_raises_on_invalid_date_format():
    db = _base_db()
    with pytest.raises(AnalystQueryError, match="Invalid date"):
        get_asin_sales_window(db, _PROFILE_ID, ["B0001"], "not-a-date", "2026-03-16")


def test_get_asin_sales_window_raises_on_unknown_profile():
    db = _base_db(wbr_profiles=[])
    with pytest.raises(AnalystQueryError, match="not found"):
        get_asin_sales_window(db, "bad-profile-id", ["B0001"], "2026-03-10", "2026-03-16")


def test_get_asin_sales_window_mixed_asin_freshness():
    """Per-ASIN latest snapshots use each ASIN's own latest date, not the profile-wide max."""
    # B0001 has data 2026-03-10 through 2026-03-16; B0002 only through 2026-03-12.
    facts_mixed = [
        {
            "id": f"f{i}",
            "profile_id": _PROFILE_ID,
            "report_date": f"2026-03-{i + 10:02d}",
            "child_asin": "B0001",
            "unit_sales": 5,
            "sales": "50.00",
            "page_views": 100,
        }
        for i in range(7)  # 2026-03-10 to 2026-03-16
    ] + [
        {
            "id": f"g{i}",
            "profile_id": _PROFILE_ID,
            "report_date": f"2026-03-{i + 10:02d}",
            "child_asin": "B0002",
            "unit_sales": 3,
            "sales": "30.00",
            "page_views": 60,
        }
        for i in range(3)  # 2026-03-10 to 2026-03-12
    ]
    db = _base_db(wbr_business_asin_daily=facts_mixed)
    result = get_asin_sales_window(
        db, _PROFILE_ID, ["B0001", "B0002"], "2026-03-10", "2026-03-20",
        include_latest_available=True,
    )

    assert result["freshness"]["note"] is not None
    assert "latest_available_by_asin" in result
    snaps = {row["child_asin"]: row for row in result["latest_available_by_asin"]}
    # Each ASIN gets its own latest date, not the profile-wide max.
    assert snaps["B0001"]["report_date"] == "2026-03-16"
    assert snaps["B0002"]["report_date"] == "2026-03-12"


# ===========================================================================
# Service-layer tests — list_child_asins_for_row
# ===========================================================================


def test_list_child_asins_for_row_valid_leaf_row():
    """Happy path: leaf row with two mapped ASINs."""
    db = _base_db()
    result = list_child_asins_for_row(db, _PROFILE_ID, _ROW_ID_LEAF)

    assert result["profile_id"] == _PROFILE_ID
    assert result["row_id"] == _ROW_ID_LEAF
    assert result["row_label"] == "Screen Shine Pro"
    assert result["row_kind"] == "leaf"
    assert result["total"] == 2
    assert result["note"] is None

    assert result["resolved_via"] == "direct_mapping"
    asins_by_id = {row["child_asin"]: row for row in result["child_asins"]}
    assert "B0001" in asins_by_id
    assert asins_by_id["B0001"]["title"] == "Screen Shine Pro 8oz"
    assert asins_by_id["B0001"]["child_sku"] == "SKU-001"
    assert asins_by_id["B0001"]["scope_status"] == "included"
    assert asins_by_id["B0001"]["exclusion_reason"] is None


def test_list_child_asins_for_row_excluded_asin_shows_status():
    """An excluded ASIN is still returned but with scope_status=excluded."""
    db = _base_db(
        wbr_asin_exclusions=[
            {
                "id": "ex-1",
                "profile_id": _PROFILE_ID,
                "child_asin": "B0001",
                "exclusion_reason": "duplicate parent ASIN",
                "active": True,
            }
        ]
    )
    result = list_child_asins_for_row(db, _PROFILE_ID, _ROW_ID_LEAF)

    asins_by_id = {row["child_asin"]: row for row in result["child_asins"]}
    assert asins_by_id["B0001"]["scope_status"] == "excluded"
    assert asins_by_id["B0001"]["exclusion_reason"] == "duplicate parent ASIN"
    assert asins_by_id["B0002"]["scope_status"] == "included"


def test_list_child_asins_for_row_parent_row_resolves_descendants():
    """Non-leaf rows resolve ASINs from descendant leaf rows."""
    db = _base_db()
    result = list_child_asins_for_row(db, _PROFILE_ID, _ROW_ID_PARENT)

    assert result["resolved_via"] == "descendant_leaves"
    assert result["total"] == 2
    asin_ids = {r["child_asin"] for r in result["child_asins"]}
    assert "B0001" in asin_ids
    assert "B0002" in asin_ids
    assert result["note"] is not None
    assert "leaf" in result["note"].lower()


def test_list_child_asins_for_row_raises_on_row_not_found():
    db = _base_db()
    with pytest.raises(AnalystQueryError, match="not found"):
        list_child_asins_for_row(db, _PROFILE_ID, "nonexistent-row-id")


def test_list_child_asins_for_row_raises_on_row_wrong_profile():
    """Row belongs to a different profile — should fail clean."""
    db = _base_db()
    # The row_id exists but with profile_id=profile-001; querying with wrong
    # profile should return no rows from wbr_rows eq filter.
    with pytest.raises(AnalystQueryError, match="not found"):
        list_child_asins_for_row(db, "other-profile-id", _ROW_ID_LEAF)


def test_list_child_asins_for_row_raises_on_unknown_profile():
    db = _base_db(wbr_profiles=[])
    with pytest.raises(AnalystQueryError, match="not found"):
        list_child_asins_for_row(db, "bad-profile-id", _ROW_ID_LEAF)


def test_list_child_asins_for_row_rejects_inactive_row():
    """Inactive row IDs should not be accepted as valid composition roots."""
    db = _base_db(
        wbr_rows=[
            {
                "id": _ROW_ID_LEAF,
                "profile_id": _PROFILE_ID,
                "row_label": "Screen Shine Pro",
                "row_kind": "leaf",
                "parent_row_id": _ROW_ID_PARENT,
                "sort_order": 1,
                "active": False,
            },
            {
                "id": _ROW_ID_PARENT,
                "profile_id": _PROFILE_ID,
                "row_label": "Screen Shine Group",
                "row_kind": "group",
                "parent_row_id": None,
                "sort_order": 0,
                "active": True,
            },
        ],
    )
    with pytest.raises(AnalystQueryError) as exc_info:
        list_child_asins_for_row(db, _PROFILE_ID, _ROW_ID_LEAF)
    assert exc_info.value.error_type == "not_found"


def test_list_child_asins_for_row_ignores_inactive_exclusions():
    """Inactive exclusion rows must not mark an ASIN excluded."""
    db = _base_db(
        wbr_asin_exclusions=[
            {
                "id": "ex-inactive",
                "profile_id": _PROFILE_ID,
                "child_asin": "B0001",
                "exclusion_reason": "old exclusion",
                "active": False,
            }
        ]
    )
    result = list_child_asins_for_row(db, _PROFILE_ID, _ROW_ID_LEAF)

    asins_by_id = {row["child_asin"]: row for row in result["child_asins"]}
    assert asins_by_id["B0001"]["scope_status"] == "included"
    assert asins_by_id["B0001"]["exclusion_reason"] is None


def test_list_child_asins_for_row_inactive_leaf_excluded():
    """Inactive leaf rows do not contribute ASINs to parent-row composition."""
    _ROW_ID_LEAF_INACTIVE = "row-leaf-inactive"
    db = _base_db(
        wbr_rows=[
            {
                "id": _ROW_ID_LEAF,
                "profile_id": _PROFILE_ID,
                "row_label": "Active Leaf",
                "row_kind": "leaf",
                "parent_row_id": _ROW_ID_PARENT,
                "sort_order": 1,
                "active": True,
            },
            {
                "id": _ROW_ID_LEAF_INACTIVE,
                "profile_id": _PROFILE_ID,
                "row_label": "Inactive Leaf",
                "row_kind": "leaf",
                "parent_row_id": _ROW_ID_PARENT,
                "sort_order": 2,
                "active": False,
            },
            {
                "id": _ROW_ID_PARENT,
                "profile_id": _PROFILE_ID,
                "row_label": "Parent Group",
                "row_kind": "group",
                "parent_row_id": None,
                "sort_order": 0,
                "active": True,
            },
        ],
        wbr_asin_row_map=[
            {"id": "map-1", "profile_id": _PROFILE_ID, "child_asin": "B0001",
             "row_id": _ROW_ID_LEAF, "active": True},
            # B0003 is mapped to the inactive leaf — must not appear in results.
            {"id": "map-2", "profile_id": _PROFILE_ID, "child_asin": "B0003",
             "row_id": _ROW_ID_LEAF_INACTIVE, "active": True},
        ],
    )
    result = list_child_asins_for_row(db, _PROFILE_ID, _ROW_ID_PARENT)

    asin_ids = {r["child_asin"] for r in result["child_asins"]}
    assert "B0001" in asin_ids
    assert "B0003" not in asin_ids  # inactive leaf must be excluded


def test_list_child_asins_for_row_parent_no_leaf_descendants():
    """Parent row with no descendant leaf rows returns empty result with a note."""
    _ROW_ID_EMPTY_PARENT = "row-empty-parent-001"
    db = _base_db(
        wbr_rows=[
            {
                "id": _ROW_ID_EMPTY_PARENT,
                "profile_id": _PROFILE_ID,
                "row_label": "Empty Group",
                "row_kind": "group",
                "parent_row_id": None,
                "sort_order": 0,
                "active": True,
            },
        ],
    )
    result = list_child_asins_for_row(db, _PROFILE_ID, _ROW_ID_EMPTY_PARENT)

    assert result["resolved_via"] == "descendant_leaves"
    assert result["total"] == 0
    assert result["child_asins"] == []
    assert result["note"] is not None
    assert "no active descendant" in result["note"].lower()


def test_list_child_asins_for_row_deduplication():
    """Same ASIN appearing via multiple descendant leaf rows is deduplicated."""
    _ROW_ID_LEAF2 = "row-leaf-002"
    db = _base_db(
        wbr_rows=[
            {
                "id": _ROW_ID_LEAF,
                "profile_id": _PROFILE_ID,
                "row_label": "Leaf 1",
                "row_kind": "leaf",
                "parent_row_id": _ROW_ID_PARENT,
                "sort_order": 1,
                "active": True,
            },
            {
                "id": _ROW_ID_LEAF2,
                "profile_id": _PROFILE_ID,
                "row_label": "Leaf 2",
                "row_kind": "leaf",
                "parent_row_id": _ROW_ID_PARENT,
                "sort_order": 2,
                "active": True,
            },
            {
                "id": _ROW_ID_PARENT,
                "profile_id": _PROFILE_ID,
                "row_label": "Parent Group",
                "row_kind": "group",
                "parent_row_id": None,
                "sort_order": 0,
                "active": True,
            },
        ],
        wbr_asin_row_map=[
            # B0001 appears in both leaf rows — must be deduplicated.
            {"id": "map-1", "profile_id": _PROFILE_ID, "child_asin": "B0001",
             "row_id": _ROW_ID_LEAF, "active": True},
            {"id": "map-2", "profile_id": _PROFILE_ID, "child_asin": "B0001",
             "row_id": _ROW_ID_LEAF2, "active": True},
            {"id": "map-3", "profile_id": _PROFILE_ID, "child_asin": "B0002",
             "row_id": _ROW_ID_LEAF2, "active": True},
        ],
    )
    result = list_child_asins_for_row(db, _PROFILE_ID, _ROW_ID_PARENT)

    assert result["resolved_via"] == "descendant_leaves"
    assert result["total"] == 2
    asin_list = [r["child_asin"] for r in result["child_asins"]]
    assert asin_list.count("B0001") == 1  # deduplicated
    assert "B0002" in asin_list


# ===========================================================================
# Service-layer tests — get_sync_freshness_status
# ===========================================================================


def test_get_sync_freshness_status_full_happy_path():
    """Both syncs present, fact dates available, no warnings."""
    db = _base_db()
    result = get_sync_freshness_status(db, _PROFILE_ID)

    assert result["profile_id"] == _PROFILE_ID
    assert result["marketplace_code"] == "US"
    assert result["business_sync"]["found"] is True
    assert result["business_sync"]["finished_at"] == "2026-03-17T03:00:00+00:00"
    assert result["ads_sync"]["found"] is True
    assert result["ads_sync"]["finished_at"] == "2026-03-17T04:00:00+00:00"
    assert result["latest_business_fact_date"] == "2026-03-16"
    assert result["latest_ads_fact_date"] == "2026-03-16"
    assert result["warnings"] == []


def test_get_sync_freshness_status_no_syncs_produces_warnings():
    """Missing sync runs produce warnings for both source types."""
    db = _base_db(wbr_sync_runs=[])
    result = get_sync_freshness_status(db, _PROFILE_ID)

    assert result["business_sync"]["found"] is False
    assert result["ads_sync"]["found"] is False
    assert len(result["warnings"]) >= 2
    assert any("Windsor" in w for w in result["warnings"])
    assert any("Ads" in w in w for w in result["warnings"])


def test_get_sync_freshness_status_no_fact_data_produces_warnings():
    """Missing fact rows produce warnings."""
    db = _base_db(wbr_business_asin_daily=[], wbr_ads_campaign_daily=[])
    result = get_sync_freshness_status(db, _PROFILE_ID)

    assert result["latest_business_fact_date"] is None
    assert result["latest_ads_fact_date"] is None
    assert any("business fact" in w for w in result["warnings"])
    assert any("ads fact" in w for w in result["warnings"])


def test_get_sync_freshness_status_raises_on_unknown_profile():
    db = _base_db(wbr_profiles=[])
    with pytest.raises(AnalystQueryError, match="not found"):
        get_sync_freshness_status(db, "bad-profile-id")


def test_get_sync_freshness_status_shape():
    """Result always has expected top-level keys."""
    db = _base_db()
    result = get_sync_freshness_status(db, _PROFILE_ID)
    for key in (
        "profile_id",
        "marketplace_code",
        "business_sync",
        "ads_sync",
        "latest_business_fact_date",
        "latest_ads_fact_date",
        "warnings",
    ):
        assert key in result, f"missing key: {key}"


# ===========================================================================
# MCP wrapper tests
# ===========================================================================


def _make_mock_mcp() -> Any:
    """Return a simple object that records @mcp.tool() registrations."""
    registered: list[dict[str, Any]] = []

    class _MockMCP:
        _registered = registered

        def tool(self, *, name: str, description: str, structured_output: bool = False):
            def decorator(fn: Any) -> Any:
                registered.append({"name": name, "fn": fn})
                return fn

            return decorator

    return _MockMCP()


def test_mcp_wrapper_get_asin_sales_window_success(monkeypatch):
    """Wrapper returns service result on success."""
    fake_db = _base_db()
    monkeypatch.setattr(
        "app.mcp.tools.analyst._get_supabase_admin_client", lambda: fake_db
    )
    monkeypatch.setattr(
        "app.mcp.tools.analyst.get_current_pilot_user", lambda: None
    )

    mock_mcp = _make_mock_mcp()
    register_analyst_tools(mock_mcp)

    fn = next(r["fn"] for r in mock_mcp._registered if r["name"] == "get_asin_sales_window")
    result = fn(
        profile_id=_PROFILE_ID,
        child_asins=["B0001"],
        date_from="2026-03-10",
        date_to="2026-03-16",
    )

    assert "error" not in result
    assert result["profile_id"] == _PROFILE_ID
    assert len(result["asins"]) == 1


def test_mcp_wrapper_get_asin_sales_window_structured_error(monkeypatch):
    """Wrapper returns structured error dict on AnalystQueryError."""
    fake_db = _base_db(wbr_profiles=[])
    monkeypatch.setattr(
        "app.mcp.tools.analyst._get_supabase_admin_client", lambda: fake_db
    )
    monkeypatch.setattr(
        "app.mcp.tools.analyst.get_current_pilot_user", lambda: None
    )

    mock_mcp = _make_mock_mcp()
    register_analyst_tools(mock_mcp)

    fn = next(r["fn"] for r in mock_mcp._registered if r["name"] == "get_asin_sales_window")
    result = fn(
        profile_id="nonexistent",
        child_asins=["B0001"],
        date_from="2026-03-10",
        date_to="2026-03-16",
    )

    assert result["error"] == "not_found"
    assert "not found" in result["message"].lower()


def test_mcp_wrapper_list_child_asins_for_row_success(monkeypatch):
    """Wrapper returns service result on success."""
    fake_db = _base_db()
    monkeypatch.setattr(
        "app.mcp.tools.analyst._get_supabase_admin_client", lambda: fake_db
    )
    monkeypatch.setattr(
        "app.mcp.tools.analyst.get_current_pilot_user", lambda: None
    )

    mock_mcp = _make_mock_mcp()
    register_analyst_tools(mock_mcp)

    fn = next(r["fn"] for r in mock_mcp._registered if r["name"] == "list_child_asins_for_row")
    result = fn(profile_id=_PROFILE_ID, row_id=_ROW_ID_LEAF)

    assert "error" not in result
    assert result["total"] == 2


def test_mcp_wrapper_list_child_asins_for_row_structured_error(monkeypatch):
    """Wrapper returns structured error dict on AnalystQueryError."""
    fake_db = _base_db(wbr_profiles=[])
    monkeypatch.setattr(
        "app.mcp.tools.analyst._get_supabase_admin_client", lambda: fake_db
    )
    monkeypatch.setattr(
        "app.mcp.tools.analyst.get_current_pilot_user", lambda: None
    )

    mock_mcp = _make_mock_mcp()
    register_analyst_tools(mock_mcp)

    fn = next(r["fn"] for r in mock_mcp._registered if r["name"] == "list_child_asins_for_row")
    result = fn(profile_id="nonexistent", row_id=_ROW_ID_LEAF)

    assert result["error"] == "not_found"
    assert "message" in result


def test_mcp_wrapper_get_sync_freshness_status_success(monkeypatch):
    """Wrapper returns service result on success."""
    fake_db = _base_db()
    monkeypatch.setattr(
        "app.mcp.tools.analyst._get_supabase_admin_client", lambda: fake_db
    )
    monkeypatch.setattr(
        "app.mcp.tools.analyst.get_current_pilot_user", lambda: None
    )

    mock_mcp = _make_mock_mcp()
    register_analyst_tools(mock_mcp)

    fn = next(r["fn"] for r in mock_mcp._registered if r["name"] == "get_sync_freshness_status")
    result = fn(profile_id=_PROFILE_ID)

    assert "error" not in result
    assert result["business_sync"]["found"] is True


def test_mcp_wrapper_get_sync_freshness_status_structured_error(monkeypatch):
    """Wrapper returns structured error dict on AnalystQueryError."""
    fake_db = _base_db(wbr_profiles=[])
    monkeypatch.setattr(
        "app.mcp.tools.analyst._get_supabase_admin_client", lambda: fake_db
    )
    monkeypatch.setattr(
        "app.mcp.tools.analyst.get_current_pilot_user", lambda: None
    )

    mock_mcp = _make_mock_mcp()
    register_analyst_tools(mock_mcp)

    fn = next(r["fn"] for r in mock_mcp._registered if r["name"] == "get_sync_freshness_status")
    result = fn(profile_id="nonexistent")

    assert result["error"] == "not_found"
    assert "message" in result


# ===========================================================================
# Registration smoke test
# ===========================================================================


def test_analyst_tools_registered_in_server(monkeypatch):
    """create_mcp_server() registers all analyst tools (Slice 1 + Slice 2)."""
    monkeypatch.setattr("app.config.settings.supabase_jwt_secret", "test-secret")
    monkeypatch.setattr("app.config.settings.mcp_public_base_url", "http://localhost/mcp")

    server = create_mcp_server()
    tool_names = {tool.name for tool in server._tool_manager.list_tools()}

    for name in (
        "get_asin_sales_window",
        "list_child_asins_for_row",
        "get_sync_freshness_status",
        "query_business_facts",
        "query_ads_facts",
        "query_catalog_context",
        "query_monthly_pnl_detail",
    ):
        assert name in tool_names, f"tool not registered: {name}"


# ===========================================================================
# Service-layer tests — query_business_facts
# ===========================================================================


def test_query_business_facts_group_by_day():
    """group_by=day returns one row per day with combined ASIN totals."""
    db = _base_db()
    result = query_business_facts(
        db, _PROFILE_ID, "2026-03-10", "2026-03-16", "day"
    )

    assert result["group_by"] == "day"
    assert result["row_count"] == 7
    assert result["truncated"] is False
    assert result["freshness"]["note"] is None

    rows_by_date = {r["date"]: r for r in result["rows"]}
    # Each day: B0001 (5 units, 50.00) + B0002 (3 units, 30.00)
    assert rows_by_date["2026-03-10"]["unit_sales"] == 8
    assert rows_by_date["2026-03-10"]["sales"] == "80.00"
    assert rows_by_date["2026-03-10"]["page_views"] == 160

    # Totals: 7 days × 8 units = 56, 7 × 80.00 = 560.00
    assert result["totals"]["unit_sales"] == 56
    assert result["totals"]["sales"] == "560.00"


def test_query_business_facts_group_by_asin():
    """group_by=child_asin returns one row per ASIN, sorted alphabetically."""
    db = _base_db()
    result = query_business_facts(
        db, _PROFILE_ID, "2026-03-10", "2026-03-16", "child_asin"
    )

    assert result["group_by"] == "child_asin"
    assert result["row_count"] == 2
    rows_by_asin = {r["child_asin"]: r for r in result["rows"]}

    assert rows_by_asin["B0001"]["unit_sales"] == 35
    assert rows_by_asin["B0001"]["sales"] == "350.00"
    assert rows_by_asin["B0002"]["unit_sales"] == 21
    assert rows_by_asin["B0002"]["sales"] == "210.00"


def test_query_business_facts_group_by_row():
    """group_by=row aggregates ASINs under their WBR row."""
    db = _base_db()
    result = query_business_facts(
        db, _PROFILE_ID, "2026-03-10", "2026-03-16", "row"
    )

    assert result["group_by"] == "row"
    assert result["row_count"] == 1  # both ASINs map to ROW_ID_LEAF

    row = result["rows"][0]
    assert row["row_id"] == _ROW_ID_LEAF
    assert row["row_label"] == "Screen Shine Pro"
    assert row["unit_sales"] == 56
    assert row["sales"] == "560.00"


def test_query_business_facts_group_by_row_unmapped_asin():
    """ASINs with no row mapping collect in the 'Unmapped / Legacy' bucket."""
    # Add a fact for B0009 which is not in wbr_asin_row_map.
    extra_facts = list(_DAILY_FACTS) + [
        {
            "id": "fx0",
            "profile_id": _PROFILE_ID,
            "report_date": "2026-03-16",
            "child_asin": "B0009",
            "unit_sales": 1,
            "sales": "10.00",
            "page_views": 20,
        }
    ]
    db = _base_db(wbr_business_asin_daily=extra_facts)
    result = query_business_facts(
        db, _PROFILE_ID, "2026-03-16", "2026-03-16", "row"
    )

    row_labels = {r["row_label"] for r in result["rows"]}
    assert "Screen Shine Pro" in row_labels
    assert "Unmapped / Legacy" in row_labels

    unmapped = next(r for r in result["rows"] if r["row_id"] is None)
    assert unmapped["unit_sales"] == 1


def test_query_business_facts_via_row_id_scope():
    """row_id parameter scopes the query to the row's descendant ASINs."""
    # Add a third ASIN not under ROW_ID_LEAF/PARENT to verify it's excluded.
    extra_facts = list(_DAILY_FACTS) + [
        {
            "id": "fx1",
            "profile_id": _PROFILE_ID,
            "report_date": "2026-03-16",
            "child_asin": "B0099",
            "unit_sales": 99,
            "sales": "990.00",
            "page_views": 0,
        }
    ]
    db = _base_db(wbr_business_asin_daily=extra_facts)
    result = query_business_facts(
        db, _PROFILE_ID, "2026-03-16", "2026-03-16", "child_asin",
        row_id=_ROW_ID_LEAF,
    )

    asin_ids = {r["child_asin"] for r in result["rows"]}
    assert "B0001" in asin_ids
    assert "B0002" in asin_ids
    assert "B0099" not in asin_ids  # not under ROW_ID_LEAF


def test_query_business_facts_freshness_note():
    """Freshness note is set when date_to exceeds latest available date."""
    db = _base_db()
    result = query_business_facts(
        db, _PROFILE_ID, "2026-03-10", "2026-03-25", "day"
    )

    assert result["freshness"]["note"] is not None
    assert "2026-03-25" in result["freshness"]["note"]


def test_query_business_facts_truncation():
    """limit parameter caps rows; truncated flag and warning are set."""
    db = _base_db()
    result = query_business_facts(
        db, _PROFILE_ID, "2026-03-10", "2026-03-16", "day", limit=3
    )

    assert result["row_count"] == 3
    assert result["truncated"] is True
    assert len(result["warnings"]) >= 1
    # Totals are computed over all groups, not just the returned rows.
    assert result["totals"]["unit_sales"] == 56


def test_query_business_facts_custom_metrics():
    """Requesting a subset of metrics returns only those columns."""
    db = _base_db()
    result = query_business_facts(
        db, _PROFILE_ID, "2026-03-10", "2026-03-16", "child_asin",
        metrics=["unit_sales"],
    )

    for row in result["rows"]:
        assert "unit_sales" in row
        assert "sales" not in row
        assert "page_views" not in row


def test_query_business_facts_raises_bad_group_by():
    db = _base_db()
    with pytest.raises(AnalystQueryError) as exc_info:
        query_business_facts(db, _PROFILE_ID, "2026-03-10", "2026-03-16", "week")
    assert exc_info.value.error_type == "validation_error"


def test_query_business_facts_raises_bad_metric():
    db = _base_db()
    with pytest.raises(AnalystQueryError) as exc_info:
        query_business_facts(
            db, _PROFILE_ID, "2026-03-10", "2026-03-16", "day",
            metrics=["unit_sales", "bad_metric"],
        )
    assert exc_info.value.error_type == "validation_error"


def test_query_business_facts_raises_reversed_dates():
    db = _base_db()
    with pytest.raises(AnalystQueryError) as exc_info:
        query_business_facts(db, _PROFILE_ID, "2026-03-16", "2026-03-10", "day")
    assert exc_info.value.error_type == "validation_error"


def test_query_business_facts_raises_unknown_profile():
    db = _base_db(wbr_profiles=[])
    with pytest.raises(AnalystQueryError) as exc_info:
        query_business_facts(db, "bad-profile", "2026-03-10", "2026-03-16", "day")
    assert exc_info.value.error_type == "not_found"


# ===========================================================================
# Service-layer tests — query_ads_facts
# ===========================================================================


def test_query_ads_facts_group_by_day():
    """group_by=day returns one row per day with combined campaign totals."""
    db = _base_db()
    result = query_ads_facts(
        db, _PROFILE_ID, "2026-03-10", "2026-03-16", "day"
    )

    assert result["group_by"] == "day"
    assert result["row_count"] == 7
    assert result["truncated"] is False

    rows_by_date = {r["date"]: r for r in result["rows"]}
    # Each day: Brand SP (50.00 spend) + Brand SB (25.00 spend) = 75.00
    assert rows_by_date["2026-03-10"]["spend"] == "75.00"
    assert rows_by_date["2026-03-10"]["impressions"] == 150
    assert rows_by_date["2026-03-10"]["orders"] == 3

    # Grand totals: 7 × 75.00 = 525.00 spend
    assert result["totals"]["spend"] == "525.00"


def test_query_ads_facts_group_by_campaign_sorted_by_spend():
    """group_by=campaign returns campaigns sorted by spend descending."""
    db = _base_db()
    result = query_ads_facts(
        db, _PROFILE_ID, "2026-03-10", "2026-03-16", "campaign"
    )

    assert result["group_by"] == "campaign"
    assert result["row_count"] == 2

    # Brand SP (7×50=350) before Brand SB (7×25=175)
    assert result["rows"][0]["campaign_name"] == "Brand SP"
    assert result["rows"][0]["spend"] == "350.00"
    assert result["rows"][0]["campaign_type"] == "sponsored_products"

    assert result["rows"][1]["campaign_name"] == "Brand SB"
    assert result["rows"][1]["spend"] == "175.00"


def test_query_ads_facts_group_by_campaign_type():
    """group_by=campaign_type returns one row per campaign type."""
    db = _base_db()
    result = query_ads_facts(
        db, _PROFILE_ID, "2026-03-10", "2026-03-16", "campaign_type"
    )

    assert result["group_by"] == "campaign_type"
    assert result["row_count"] == 2

    rows_by_type = {r["campaign_type"]: r for r in result["rows"]}
    assert rows_by_type["sponsored_products"]["spend"] == "350.00"
    assert rows_by_type["sponsored_brands"]["spend"] == "175.00"


def test_query_ads_facts_group_by_row():
    """group_by=row maps campaigns to WBR rows; unmapped campaigns bucket separately."""
    db = _base_db()
    result = query_ads_facts(
        db, _PROFILE_ID, "2026-03-10", "2026-03-16", "row"
    )

    assert result["group_by"] == "row"
    assert result["row_count"] == 2  # ROW_ID_LEAF + unmapped

    rows_by_label = {r["row_label"]: r for r in result["rows"]}
    # Brand SP → ROW_ID_LEAF
    assert "Screen Shine Pro" in rows_by_label
    assert rows_by_label["Screen Shine Pro"]["spend"] == "350.00"
    assert rows_by_label["Screen Shine Pro"]["row_id"] == _ROW_ID_LEAF

    # Brand SB → unmapped
    assert "Unmapped / Legacy" in rows_by_label
    assert rows_by_label["Unmapped / Legacy"]["spend"] == "175.00"
    assert rows_by_label["Unmapped / Legacy"]["row_id"] is None


def test_query_ads_facts_campaign_name_filter():
    """Providing campaign_names restricts the query to those campaigns."""
    db = _base_db()
    result = query_ads_facts(
        db, _PROFILE_ID, "2026-03-10", "2026-03-16", "campaign",
        campaign_names=["Brand SP"],
    )

    assert result["row_count"] == 1
    assert result["rows"][0]["campaign_name"] == "Brand SP"
    assert result["totals"]["spend"] == "350.00"


def test_query_ads_facts_row_id_scopes_to_mapped_campaigns():
    """row_id restricts facts to campaigns mapped under that row."""
    db = _base_db()
    result = query_ads_facts(
        db, _PROFILE_ID, "2026-03-10", "2026-03-16", "campaign",
        row_id=_ROW_ID_LEAF,
    )

    # Only Brand SP is mapped to ROW_ID_LEAF
    campaign_names = {r["campaign_name"] for r in result["rows"]}
    assert campaign_names == {"Brand SP"}
    assert result["totals"]["spend"] == "350.00"


def test_query_ads_facts_freshness_note():
    """Freshness note is set when date_to exceeds latest available ads date."""
    db = _base_db()
    result = query_ads_facts(
        db, _PROFILE_ID, "2026-03-10", "2026-03-25", "day"
    )

    assert result["freshness"]["note"] is not None
    assert "2026-03-25" in result["freshness"]["note"]


def test_query_ads_facts_raises_bad_group_by():
    db = _base_db()
    with pytest.raises(AnalystQueryError) as exc_info:
        query_ads_facts(db, _PROFILE_ID, "2026-03-10", "2026-03-16", "asin")
    assert exc_info.value.error_type == "validation_error"


def test_query_ads_facts_raises_bad_metric():
    db = _base_db()
    with pytest.raises(AnalystQueryError) as exc_info:
        query_ads_facts(
            db, _PROFILE_ID, "2026-03-10", "2026-03-16", "day",
            metrics=["spend", "unit_sales"],  # unit_sales not allowed for ads
        )
    assert exc_info.value.error_type == "validation_error"


def test_query_ads_facts_raises_unknown_profile():
    db = _base_db(wbr_profiles=[])
    with pytest.raises(AnalystQueryError) as exc_info:
        query_ads_facts(db, "bad-profile", "2026-03-10", "2026-03-16", "day")
    assert exc_info.value.error_type == "not_found"


# ===========================================================================
# Service-layer tests — query_catalog_context
# ===========================================================================


def test_query_catalog_context_explicit_asins():
    """Requesting specific ASINs returns only those catalog rows."""
    db = _base_db()
    result = query_catalog_context(db, _PROFILE_ID, child_asins=["B0001"])

    assert result["profile_id"] == _PROFILE_ID
    assert result["total"] == 1
    assert result["truncated"] is False

    row = result["child_asins"][0]
    assert row["child_asin"] == "B0001"
    assert row["child_product_name"] == "Screen Shine Pro 8oz"
    assert row["child_sku"] == "SKU-001"
    assert row["category"] == "Cleaning Supplies"
    assert row["fulfillment_method"] == "FBA"
    # Fields not in base fixture return None, not raise
    assert "parent_asin" in row


def test_query_catalog_context_via_row_id():
    """row_id expands to descendant ASINs and returns their catalog rows."""
    db = _base_db()
    result = query_catalog_context(db, _PROFILE_ID, row_id=_ROW_ID_LEAF)

    assert result["total"] == 2
    asin_ids = {r["child_asin"] for r in result["child_asins"]}
    assert "B0001" in asin_ids
    assert "B0002" in asin_ids


def test_query_catalog_context_parent_row_id():
    """Parent row_id resolves all descendant ASINs."""
    db = _base_db()
    result = query_catalog_context(db, _PROFILE_ID, row_id=_ROW_ID_PARENT)

    assert result["total"] == 2
    asin_ids = {r["child_asin"] for r in result["child_asins"]}
    assert asin_ids == {"B0001", "B0002"}


def test_query_catalog_context_all_profile():
    """With no filter, all active catalog rows for the profile are returned."""
    db = _base_db()
    result = query_catalog_context(db, _PROFILE_ID)

    assert result["total"] == 2
    assert result["truncated"] is False


def test_query_catalog_context_sorted_by_product_name():
    """Results are sorted by child_product_name ascending."""
    db = _base_db()
    result = query_catalog_context(db, _PROFILE_ID)

    names = [r["child_product_name"] for r in result["child_asins"]]
    assert names == sorted(names)


def test_query_catalog_context_raises_unknown_profile():
    db = _base_db(wbr_profiles=[])
    with pytest.raises(AnalystQueryError) as exc_info:
        query_catalog_context(db, "bad-profile")
    assert exc_info.value.error_type == "not_found"


def test_query_catalog_context_raises_row_not_found():
    db = _base_db()
    with pytest.raises(AnalystQueryError) as exc_info:
        query_catalog_context(db, _PROFILE_ID, row_id="nonexistent-row")
    assert exc_info.value.error_type == "not_found"


# ===========================================================================
# MCP wrapper tests — Slice 2
# ===========================================================================


def test_mcp_wrapper_query_business_facts_success(monkeypatch):
    """query_business_facts wrapper returns service result on success."""
    fake_db = _base_db()
    monkeypatch.setattr(
        "app.mcp.tools.analyst._get_supabase_admin_client", lambda: fake_db
    )
    monkeypatch.setattr("app.mcp.tools.analyst.get_current_pilot_user", lambda: None)

    mock_mcp = _make_mock_mcp()
    register_analyst_tools(mock_mcp)

    fn = next(r["fn"] for r in mock_mcp._registered if r["name"] == "query_business_facts")
    result = fn(
        profile_id=_PROFILE_ID,
        date_from="2026-03-10",
        date_to="2026-03-16",
        group_by="day",
    )

    assert "error" not in result
    assert result["row_count"] == 7


def test_mcp_wrapper_query_business_facts_error(monkeypatch):
    """query_business_facts wrapper returns structured error on failure."""
    fake_db = _base_db(wbr_profiles=[])
    monkeypatch.setattr(
        "app.mcp.tools.analyst._get_supabase_admin_client", lambda: fake_db
    )
    monkeypatch.setattr("app.mcp.tools.analyst.get_current_pilot_user", lambda: None)

    mock_mcp = _make_mock_mcp()
    register_analyst_tools(mock_mcp)

    fn = next(r["fn"] for r in mock_mcp._registered if r["name"] == "query_business_facts")
    result = fn(
        profile_id="nonexistent",
        date_from="2026-03-10",
        date_to="2026-03-16",
        group_by="day",
    )

    assert result["error"] == "not_found"
    assert "message" in result


def test_mcp_wrapper_query_ads_facts_success(monkeypatch):
    """query_ads_facts wrapper returns service result on success."""
    fake_db = _base_db()
    monkeypatch.setattr(
        "app.mcp.tools.analyst._get_supabase_admin_client", lambda: fake_db
    )
    monkeypatch.setattr("app.mcp.tools.analyst.get_current_pilot_user", lambda: None)

    mock_mcp = _make_mock_mcp()
    register_analyst_tools(mock_mcp)

    fn = next(r["fn"] for r in mock_mcp._registered if r["name"] == "query_ads_facts")
    result = fn(
        profile_id=_PROFILE_ID,
        date_from="2026-03-10",
        date_to="2026-03-16",
        group_by="campaign",
    )

    assert "error" not in result
    assert result["row_count"] == 2


def test_mcp_wrapper_query_ads_facts_error(monkeypatch):
    """query_ads_facts wrapper returns structured error on failure."""
    fake_db = _base_db(wbr_profiles=[])
    monkeypatch.setattr(
        "app.mcp.tools.analyst._get_supabase_admin_client", lambda: fake_db
    )
    monkeypatch.setattr("app.mcp.tools.analyst.get_current_pilot_user", lambda: None)

    mock_mcp = _make_mock_mcp()
    register_analyst_tools(mock_mcp)

    fn = next(r["fn"] for r in mock_mcp._registered if r["name"] == "query_ads_facts")
    result = fn(
        profile_id="nonexistent",
        date_from="2026-03-10",
        date_to="2026-03-16",
        group_by="day",
    )

    assert result["error"] == "not_found"
    assert "message" in result


def test_mcp_wrapper_query_catalog_context_success(monkeypatch):
    """query_catalog_context wrapper returns service result on success."""
    fake_db = _base_db()
    monkeypatch.setattr(
        "app.mcp.tools.analyst._get_supabase_admin_client", lambda: fake_db
    )
    monkeypatch.setattr("app.mcp.tools.analyst.get_current_pilot_user", lambda: None)

    mock_mcp = _make_mock_mcp()
    register_analyst_tools(mock_mcp)

    fn = next(r["fn"] for r in mock_mcp._registered if r["name"] == "query_catalog_context")
    result = fn(profile_id=_PROFILE_ID, child_asins=["B0001"])

    assert "error" not in result
    assert result["total"] == 1


def test_mcp_wrapper_query_catalog_context_error(monkeypatch):
    """query_catalog_context wrapper returns structured error on failure."""
    fake_db = _base_db(wbr_profiles=[])
    monkeypatch.setattr(
        "app.mcp.tools.analyst._get_supabase_admin_client", lambda: fake_db
    )
    monkeypatch.setattr("app.mcp.tools.analyst.get_current_pilot_user", lambda: None)

    mock_mcp = _make_mock_mcp()
    register_analyst_tools(mock_mcp)

    fn = next(r["fn"] for r in mock_mcp._registered if r["name"] == "query_catalog_context")
    result = fn(profile_id="nonexistent")

    assert result["error"] == "not_found"
    assert "message" in result


# ===========================================================================
# Bug-fix regression tests — empty row scope and inactive row_id
# ===========================================================================

_ROW_ID_EMPTY = "row-empty-001"  # exists, active, but has no ASIN/campaign mappings
_ROW_ID_INACTIVE = "row-inactive-001"  # inactive leaf


def _db_with_empty_row() -> _FakeDB:
    """DB where ROW_ID_EMPTY is an active leaf with no ASIN or campaign mappings."""
    tables = _base_db()._tables.copy()
    tables["wbr_rows"] = list(tables["wbr_rows"]) + [
        {
            "id": _ROW_ID_EMPTY,
            "profile_id": _PROFILE_ID,
            "row_label": "Empty Row",
            "row_kind": "leaf",
            "parent_row_id": None,
            "sort_order": 99,
            "active": True,
        }
    ]
    # No entries added to wbr_asin_row_map or wbr_pacvue_campaign_map for ROW_ID_EMPTY.
    return _FakeDB(tables)


def _db_with_inactive_row() -> _FakeDB:
    """DB where ROW_ID_INACTIVE exists but is inactive."""
    tables = _base_db()._tables.copy()
    tables["wbr_rows"] = list(tables["wbr_rows"]) + [
        {
            "id": _ROW_ID_INACTIVE,
            "profile_id": _PROFILE_ID,
            "row_label": "Retired Row",
            "row_kind": "leaf",
            "parent_row_id": None,
            "sort_order": 99,
            "active": False,
        }
    ]
    return _FakeDB(tables)


# --- High: empty scope should return zero rows, not all profile data ---


def test_query_business_facts_row_id_with_no_asin_mappings_returns_empty():
    """row_id that resolves to no ASINs must return 0 rows, not profile-wide data."""
    result = query_business_facts(
        _db_with_empty_row(),
        _PROFILE_ID,
        "2026-03-10",
        "2026-03-16",
        "day",
        row_id=_ROW_ID_EMPTY,
    )
    assert result["row_count"] == 0
    assert result["rows"] == []
    assert result["truncated"] is False


def test_query_ads_facts_row_id_with_no_campaign_mappings_returns_empty():
    """row_id that resolves to no campaigns must return 0 rows, not profile-wide data."""
    result = query_ads_facts(
        _db_with_empty_row(),
        _PROFILE_ID,
        "2026-03-10",
        "2026-03-16",
        "day",
        row_id=_ROW_ID_EMPTY,
    )
    assert result["row_count"] == 0
    assert result["rows"] == []
    assert result["truncated"] is False


def test_query_catalog_context_row_id_with_no_asin_mappings_returns_empty():
    """row_id that resolves to no ASINs must return empty catalog, not the full profile."""
    result = query_catalog_context(
        _db_with_empty_row(),
        _PROFILE_ID,
        row_id=_ROW_ID_EMPTY,
    )
    assert result["total"] == 0
    assert result["child_asins"] == []


# --- Medium: inactive row_id must be rejected ---


def test_query_business_facts_inactive_row_id_raises_not_found():
    """An inactive row_id must not be accepted as a valid scope root."""
    with pytest.raises(AnalystQueryError) as exc_info:
        query_business_facts(
            _db_with_inactive_row(),
            _PROFILE_ID,
            "2026-03-10",
            "2026-03-16",
            "day",
            row_id=_ROW_ID_INACTIVE,
        )
    assert exc_info.value.error_type == "not_found"


def test_query_ads_facts_inactive_row_id_raises_not_found():
    """An inactive row_id must not be accepted as a valid scope root."""
    with pytest.raises(AnalystQueryError) as exc_info:
        query_ads_facts(
            _db_with_inactive_row(),
            _PROFILE_ID,
            "2026-03-10",
            "2026-03-16",
            "day",
            row_id=_ROW_ID_INACTIVE,
        )
    assert exc_info.value.error_type == "not_found"


def test_query_catalog_context_inactive_row_id_raises_not_found():
    """An inactive row_id must not be accepted as a valid scope root."""
    with pytest.raises(AnalystQueryError) as exc_info:
        query_catalog_context(
            _db_with_inactive_row(),
            _PROFILE_ID,
            row_id=_ROW_ID_INACTIVE,
        )
    assert exc_info.value.error_type == "not_found"


# ===========================================================================
# Service-layer tests — query_monthly_pnl_detail (Slice 3)
# ===========================================================================

_PNL_PROFILE_ID = "pnl-profile-001"
_PNL_PROFILE = {
    "id": _PNL_PROFILE_ID,
    "client_id": "client-001",
    "currency_code": "USD",
    "status": "active",
    "marketplace_code": "US",
}

# Controlled report structure returned by the mocked PNLReportService.
_PNL_LINE_ITEMS = [
    {
        "key": "product_sales",
        "label": "Product Sales",
        "category": "revenue",
        "is_derived": False,
        "months": {"2026-01-01": "5000.00", "2026-02-01": "6000.00"},
    },
    {
        "key": "total_gross_revenue",
        "label": "Total Gross Revenue",
        "category": "summary",
        "is_derived": True,
        "months": {"2026-01-01": "5000.00", "2026-02-01": "6000.00"},
    },
    {
        "key": "refunds",
        "label": "Product Refunds",
        "category": "refunds",
        "is_derived": False,
        "months": {"2026-01-01": "-200.00", "2026-02-01": "-300.00"},
    },
    {
        "key": "total_refunds",
        "label": "Total Refunds & Adjustments",
        "category": "summary",
        "is_derived": True,
        "months": {"2026-01-01": "-200.00", "2026-02-01": "-300.00"},
    },
    {
        "key": "total_net_revenue",
        "label": "Total Net Revenue",
        "category": "summary",
        "is_derived": True,
        "months": {"2026-01-01": "4800.00", "2026-02-01": "5700.00"},
    },
    {
        "key": "cogs",
        "label": "Cost of Goods Sold",
        "category": "cogs",
        "is_derived": False,
        "months": {"2026-01-01": "-1000.00", "2026-02-01": "-1200.00"},
    },
    {
        "key": "gross_profit",
        "label": "Gross Profit",
        "category": "summary",
        "is_derived": True,
        "months": {"2026-01-01": "3800.00", "2026-02-01": "4500.00"},
    },
    {
        "key": "referral_fees",
        "label": "Referral Fees",
        "category": "expenses",
        "is_derived": False,
        "months": {"2026-01-01": "-500.00", "2026-02-01": "-600.00"},
    },
    {
        "key": "advertising",
        "label": "Advertising",
        "category": "expenses",
        "is_derived": False,
        "months": {"2026-01-01": "-400.00", "2026-02-01": "-500.00"},
    },
    {
        "key": "total_expenses",
        "label": "Total Expenses",
        "category": "summary",
        "is_derived": True,
        "months": {"2026-01-01": "-900.00", "2026-02-01": "-1100.00"},
    },
    {
        "key": "net_earnings",
        "label": "Net Earnings",
        "category": "bottom_line",
        "is_derived": True,
        "months": {"2026-01-01": "2900.00", "2026-02-01": "3400.00"},
    },
]

_PNL_REPORT = {
    "months": ["2026-01-01", "2026-02-01"],
    "line_items": _PNL_LINE_ITEMS,
    "warnings": [],
    "profile": _PNL_PROFILE,
}


def _pnl_db(profiles: list[dict[str, Any]] | None = None) -> _FakeDB:
    """Fake DB with a monthly_pnl_profiles table for P&L analyst tests."""
    tables = _base_db()._tables.copy()
    tables["monthly_pnl_profiles"] = [_PNL_PROFILE] if profiles is None else profiles
    return _FakeDB(tables)


# --- Happy-path service tests ---


@pytest.mark.asyncio
async def test_query_monthly_pnl_detail_group_by_line_item(monkeypatch):
    """group_by=line_item returns one row per P&L line summed across months."""
    from app.services.pnl.report import PNLReportService

    monkeypatch.setattr(
        PNLReportService, "build_report_async", AsyncMock(return_value=_PNL_REPORT)
    )
    result = await query_monthly_pnl_detail(
        _pnl_db(),
        _PNL_PROFILE_ID,
        month_from="2026-01",
        month_to="2026-02",
    )
    assert result["group_by"] == "line_item"
    assert result["period_months"] == ["2026-01-01", "2026-02-01"]
    assert result["currency_code"] == "USD"
    assert result["row_count"] == len(_PNL_LINE_ITEMS)
    assert result["truncated"] is False
    # product_sales: 5000 + 6000 = 11000
    ps = next(r for r in result["rows"] if r["key"] == "product_sales")
    assert ps["amount"] == "11000.00"
    assert ps["category"] == "revenue"
    assert ps["is_derived"] is False


@pytest.mark.asyncio
async def test_query_monthly_pnl_detail_section_filter_expenses(monkeypatch):
    """section='expenses' returns only expense-category line items."""
    from app.services.pnl.report import PNLReportService

    monkeypatch.setattr(
        PNLReportService, "build_report_async", AsyncMock(return_value=_PNL_REPORT)
    )
    result = await query_monthly_pnl_detail(
        _pnl_db(),
        _PNL_PROFILE_ID,
        month_from="2026-01",
        month_to="2026-02",
        section="expenses",
    )
    assert result["section"] == "expenses"
    assert all(r["category"] == "expenses" for r in result["rows"])
    # Only referral_fees and advertising have category="expenses"
    assert result["row_count"] == 2
    keys = {r["key"] for r in result["rows"]}
    assert keys == {"referral_fees", "advertising"}


@pytest.mark.asyncio
async def test_query_monthly_pnl_detail_section_filter_revenue(monkeypatch):
    """section='revenue' returns only revenue-category line items."""
    from app.services.pnl.report import PNLReportService

    monkeypatch.setattr(
        PNLReportService, "build_report_async", AsyncMock(return_value=_PNL_REPORT)
    )
    result = await query_monthly_pnl_detail(
        _pnl_db(),
        _PNL_PROFILE_ID,
        month_from="2026-01",
        month_to="2026-02",
        section="revenue",
    )
    assert result["row_count"] == 1
    assert result["rows"][0]["key"] == "product_sales"


@pytest.mark.asyncio
async def test_query_monthly_pnl_detail_group_by_month(monkeypatch):
    """group_by=month returns canonical summary metrics per month."""
    from app.services.pnl.report import PNLReportService

    monkeypatch.setattr(
        PNLReportService, "build_report_async", AsyncMock(return_value=_PNL_REPORT)
    )
    result = await query_monthly_pnl_detail(
        _pnl_db(),
        _PNL_PROFILE_ID,
        month_from="2026-01",
        month_to="2026-02",
        group_by="month",
    )
    assert result["group_by"] == "month"
    assert result["section"] is None  # section not meaningful for month grouping
    assert result["row_count"] == 2
    jan = next(r for r in result["rows"] if r["month"] == "2026-01-01")
    assert jan["total_net_revenue"] == "4800.00"
    assert jan["gross_profit"] == "3800.00"
    assert jan["total_expenses"] == "-900.00"
    assert jan["net_earnings"] == "2900.00"
    # Totals: sum across both months
    assert result["totals"]["total_net_revenue"] == "10500.00"  # 4800+5700
    assert result["totals"]["net_earnings"] == "6300.00"        # 2900+3400


@pytest.mark.asyncio
async def test_query_monthly_pnl_detail_single_year_month(monkeypatch):
    """year_month input narrows report to exactly one month."""
    from app.services.pnl.report import PNLReportService

    single_report = {
        "months": ["2026-01-01"],
        "line_items": [
            {
                "key": "total_net_revenue",
                "label": "Total Net Revenue",
                "category": "summary",
                "is_derived": True,
                "months": {"2026-01-01": "4800.00"},
            },
            {
                "key": "gross_profit",
                "label": "Gross Profit",
                "category": "summary",
                "is_derived": True,
                "months": {"2026-01-01": "3800.00"},
            },
            {
                "key": "total_expenses",
                "label": "Total Expenses",
                "category": "summary",
                "is_derived": True,
                "months": {"2026-01-01": "-900.00"},
            },
            {
                "key": "net_earnings",
                "label": "Net Earnings",
                "category": "bottom_line",
                "is_derived": True,
                "months": {"2026-01-01": "2900.00"},
            },
        ],
        "warnings": [],
        "profile": _PNL_PROFILE,
    }
    monkeypatch.setattr(
        PNLReportService, "build_report_async", AsyncMock(return_value=single_report)
    )
    result = await query_monthly_pnl_detail(
        _pnl_db(), _PNL_PROFILE_ID, year_month="2026-01", group_by="month"
    )
    assert result["period_months"] == ["2026-01-01"]
    assert result["row_count"] == 1
    assert result["rows"][0]["net_earnings"] == "2900.00"


@pytest.mark.asyncio
async def test_query_monthly_pnl_detail_truncation(monkeypatch):
    """limit truncates rows but totals still reflect the full period."""
    from app.services.pnl.report import PNLReportService

    monkeypatch.setattr(
        PNLReportService, "build_report_async", AsyncMock(return_value=_PNL_REPORT)
    )
    result = await query_monthly_pnl_detail(
        _pnl_db(),
        _PNL_PROFILE_ID,
        month_from="2026-01",
        month_to="2026-02",
        limit=3,
    )
    assert result["truncated"] is True
    assert result["row_count"] == 3
    # totals still reflect all 4 canonical summary lines
    assert result["totals"]["net_earnings"] == "6300.00"


@pytest.mark.asyncio
async def test_query_monthly_pnl_detail_empty_period(monkeypatch):
    """Empty line_items returns zero rows without error."""
    from app.services.pnl.report import PNLReportService

    empty_report = {"months": ["2026-01-01"], "line_items": [], "warnings": [], "profile": _PNL_PROFILE}
    monkeypatch.setattr(
        PNLReportService, "build_report_async", AsyncMock(return_value=empty_report)
    )
    result = await query_monthly_pnl_detail(
        _pnl_db(), _PNL_PROFILE_ID, year_month="2026-01"
    )
    assert result["row_count"] == 0
    assert result["rows"] == []
    assert result["truncated"] is False


@pytest.mark.asyncio
async def test_query_monthly_pnl_detail_warnings_forwarded(monkeypatch):
    """Warnings from the report service are passed through."""
    from app.services.pnl.report import PNLReportService

    report_with_warning = dict(_PNL_REPORT)
    report_with_warning["warnings"] = [
        {"type": "missing_cogs", "message": "COGS missing", "months": ["2026-01-01"], "skus": ["SKU-A"]}
    ]
    monkeypatch.setattr(
        PNLReportService, "build_report_async", AsyncMock(return_value=report_with_warning)
    )
    result = await query_monthly_pnl_detail(
        _pnl_db(), _PNL_PROFILE_ID, year_month="2026-01"
    )
    assert len(result["warnings"]) == 1
    assert result["warnings"][0]["type"] == "missing_cogs"


# --- Validation error tests ---


@pytest.mark.asyncio
async def test_query_monthly_pnl_detail_raises_unknown_profile():
    """Unknown profile_id raises not_found."""
    with pytest.raises(AnalystQueryError) as exc_info:
        await query_monthly_pnl_detail(
            _pnl_db(profiles=[]),
            "nonexistent-profile",
            year_month="2026-01",
        )
    assert exc_info.value.error_type == "not_found"


@pytest.mark.asyncio
async def test_query_monthly_pnl_detail_raises_bad_group_by():
    """Invalid group_by value raises validation_error."""
    with pytest.raises(AnalystQueryError) as exc_info:
        await query_monthly_pnl_detail(
            _pnl_db(), _PNL_PROFILE_ID, year_month="2026-01", group_by="section"
        )
    assert exc_info.value.error_type == "validation_error"


@pytest.mark.asyncio
async def test_query_monthly_pnl_detail_raises_bad_section():
    """Invalid section value raises validation_error."""
    with pytest.raises(AnalystQueryError) as exc_info:
        await query_monthly_pnl_detail(
            _pnl_db(), _PNL_PROFILE_ID, year_month="2026-01", section="total"
        )
    assert exc_info.value.error_type == "validation_error"


@pytest.mark.asyncio
async def test_query_monthly_pnl_detail_rejects_section_with_month_grouping():
    """section is not supported when group_by=month because month output is summary-only."""
    with pytest.raises(AnalystQueryError) as exc_info:
        await query_monthly_pnl_detail(
            _pnl_db(),
            _PNL_PROFILE_ID,
            month_from="2026-01",
            month_to="2026-02",
            group_by="month",
            section="expenses",
        )
    assert exc_info.value.error_type == "validation_error"


@pytest.mark.asyncio
async def test_query_monthly_pnl_detail_raises_bad_month_format():
    """Bad month format raises validation_error."""
    with pytest.raises(AnalystQueryError) as exc_info:
        await query_monthly_pnl_detail(
            _pnl_db(), _PNL_PROFILE_ID, year_month="26-01"
        )
    assert exc_info.value.error_type == "validation_error"


@pytest.mark.asyncio
async def test_query_monthly_pnl_detail_raises_reversed_months():
    """month_from after month_to raises validation_error."""
    with pytest.raises(AnalystQueryError) as exc_info:
        await query_monthly_pnl_detail(
            _pnl_db(), _PNL_PROFILE_ID, month_from="2026-06", month_to="2026-01"
        )
    assert exc_info.value.error_type == "validation_error"


@pytest.mark.asyncio
async def test_query_monthly_pnl_detail_raises_range_too_large():
    """Month range exceeding MAX_PNL_MONTHS raises validation_error."""
    with pytest.raises(AnalystQueryError) as exc_info:
        await query_monthly_pnl_detail(
            _pnl_db(),
            _PNL_PROFILE_ID,
            month_from="2024-01",
            month_to="2026-06",  # 30 months > MAX_PNL_MONTHS=24
        )
    assert exc_info.value.error_type == "validation_error"
    assert str(MAX_PNL_MONTHS) in exc_info.value.message


@pytest.mark.asyncio
async def test_query_monthly_pnl_detail_raises_both_month_inputs():
    """Providing both year_month and month_from raises validation_error."""
    with pytest.raises(AnalystQueryError) as exc_info:
        await query_monthly_pnl_detail(
            _pnl_db(),
            _PNL_PROFILE_ID,
            year_month="2026-01",
            month_from="2026-01",
        )
    assert exc_info.value.error_type == "validation_error"


@pytest.mark.asyncio
async def test_query_monthly_pnl_detail_raises_no_month_input():
    """Providing no month input raises validation_error."""
    with pytest.raises(AnalystQueryError) as exc_info:
        await query_monthly_pnl_detail(_pnl_db(), _PNL_PROFILE_ID)
    assert exc_info.value.error_type == "validation_error"


@pytest.mark.asyncio
async def test_query_monthly_pnl_detail_raises_partial_range():
    """Providing month_from but not month_to raises validation_error."""
    with pytest.raises(AnalystQueryError) as exc_info:
        await query_monthly_pnl_detail(
            _pnl_db(), _PNL_PROFILE_ID, month_from="2026-01"
        )
    assert exc_info.value.error_type == "validation_error"


# --- MCP wrapper tests ---


@pytest.mark.asyncio
async def test_mcp_wrapper_query_monthly_pnl_detail_success(monkeypatch):
    """query_monthly_pnl_detail wrapper returns result on success."""
    from app.services.pnl.report import PNLReportService

    monkeypatch.setattr(
        PNLReportService, "build_report_async", AsyncMock(return_value=_PNL_REPORT)
    )
    fake_db = _pnl_db()
    monkeypatch.setattr(
        "app.mcp.tools.analyst._get_supabase_admin_client", lambda: fake_db
    )
    monkeypatch.setattr("app.mcp.tools.analyst.get_current_pilot_user", lambda: None)

    mock_mcp = _make_mock_mcp()
    register_analyst_tools(mock_mcp)

    fn = next(r["fn"] for r in mock_mcp._registered if r["name"] == "query_monthly_pnl_detail")
    result = await fn(
        profile_id=_PNL_PROFILE_ID,
        month_from="2026-01",
        month_to="2026-02",
    )
    assert "error" not in result
    assert result["row_count"] == len(_PNL_LINE_ITEMS)


@pytest.mark.asyncio
async def test_mcp_wrapper_query_monthly_pnl_detail_error(monkeypatch):
    """query_monthly_pnl_detail wrapper returns structured error on failure."""
    fake_db = _pnl_db(profiles=[])
    monkeypatch.setattr(
        "app.mcp.tools.analyst._get_supabase_admin_client", lambda: fake_db
    )
    monkeypatch.setattr("app.mcp.tools.analyst.get_current_pilot_user", lambda: None)

    mock_mcp = _make_mock_mcp()
    register_analyst_tools(mock_mcp)

    fn = next(r["fn"] for r in mock_mcp._registered if r["name"] == "query_monthly_pnl_detail")
    result = await fn(profile_id="nonexistent", year_month="2026-01")

    assert result["error"] == "not_found"
    assert "message" in result
