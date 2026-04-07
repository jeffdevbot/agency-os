"""Analyst-query service layer — read-only data access for MCP tools (Slice 0 + 1).

These functions take an explicit `db` argument so they can be tested without
monkeypatching.  MCP wrappers are responsible for obtaining the admin client
and calling in here.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any

from .pnl.profiles import PNLNotFoundError, PNLProfileService, PNLValidationError
from .pnl.report import PNLReportService

MAX_ASIN_COUNT = 50
MAX_DATE_WINDOW_DAYS = 366

_PAGE_SIZE = 1000


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class AnalystQueryError(Exception):
    """Structured error returned to the MCP tool layer.

    Mirrors the ClickUpToolError pattern so wrappers can return a consistent
    ``{"error": error_type, "message": message}`` payload.
    """

    def __init__(self, error_type: str, message: str) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.message = message


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _parse_date(value: str) -> date:
    """Parse an ISO date string or raise AnalystQueryError."""
    try:
        return date.fromisoformat(str(value or "").strip())
    except ValueError:
        raise AnalystQueryError(
            "validation_error",
            f"Invalid date '{value}'. Expected YYYY-MM-DD.",
        )


def _get_profile(db: Any, profile_id: str) -> dict[str, Any]:
    """Return the wbr_profiles row or raise AnalystQueryError."""
    response = (
        db.table("wbr_profiles")
        .select("id, client_id, marketplace_code, status")
        .eq("id", profile_id)
        .limit(1)
        .execute()
    )
    rows = response.data if isinstance(response.data, list) else []
    if not rows:
        raise AnalystQueryError(
            "not_found",
            f"WBR profile '{profile_id}' not found.",
        )
    return rows[0]


def _select_all(
    db: Any,
    table_name: str,
    columns: str,
    filters: list[tuple[str, str, Any]],
    *,
    page_size: int = _PAGE_SIZE,
) -> list[dict[str, Any]]:
    """Paginated select — mirrors Section1ReportService._select_all.

    Filters are ``(op, field, value)`` tuples where *op* is a Supabase query
    method name: ``"eq"``, ``"gte"``, ``"lte"``, ``"in_"``, etc.
    """
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = db.table(table_name).select(columns)
        for op, field, value in filters:
            query = getattr(query, op)(field, value)
        response = query.order("id").range(offset, offset + page_size - 1).execute()
        batch = response.data if isinstance(response.data, list) else []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def _latest_available_date(db: Any, table: str, profile_id: str) -> str | None:
    """Return the max report_date for *table* / *profile_id*, or None."""
    response = (
        db.table(table)
        .select("report_date")
        .eq("profile_id", profile_id)
        .order("report_date", desc=True)
        .limit(1)
        .execute()
    )
    rows = response.data if isinstance(response.data, list) else []
    if not rows:
        return None
    return str(rows[0].get("report_date") or "").strip() or None


def _latest_sync_run(db: Any, profile_id: str, source_type: str) -> dict[str, Any] | None:
    """Return the most recent successful sync run row, or None."""
    response = (
        db.table("wbr_sync_runs")
        .select("id, source_type, status, finished_at, started_at")
        .eq("profile_id", profile_id)
        .eq("source_type", source_type)
        .eq("status", "success")
        .order("finished_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = response.data if isinstance(response.data, list) else []
    return rows[0] if rows else None


def _find_descendant_leaf_ids(
    rows: list[dict[str, Any]], root_id: str
) -> set[str]:
    """Return the IDs of all leaf-kind rows that descend from *root_id*.

    Uses BFS so arbitrary nesting depth is handled.  A ``visited`` guard
    prevents infinite loops on malformed data.
    """
    children: dict[str, list[str]] = {}
    row_kind_by_id: dict[str, str] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        rid = str(r.get("id") or "").strip()
        parent = str(r.get("parent_row_id") or "").strip()
        kind = str(r.get("row_kind") or "").strip()
        if rid:
            row_kind_by_id[rid] = kind
            if parent:
                children.setdefault(parent, []).append(rid)

    leaf_ids: set[str] = set()
    queue = list(children.get(root_id, []))
    visited: set[str] = set()
    while queue:
        current = queue.pop()
        if current in visited:
            continue
        visited.add(current)
        kind = row_kind_by_id.get(current, "")
        if kind == "leaf":
            leaf_ids.add(current)
        else:
            # Non-leaf: recurse into its children
            queue.extend(children.get(current, []))

    return leaf_ids


# ---------------------------------------------------------------------------
# get_asin_sales_window
# ---------------------------------------------------------------------------


def get_asin_sales_window(
    db: Any,
    profile_id: str,
    child_asins: list[str],
    date_from: str,
    date_to: str,
    *,
    include_latest_available: bool = True,
) -> dict[str, Any]:
    """Return per-ASIN sales totals for a window within a WBR profile.

    Validates:
    - profile exists
    - ASIN list is non-empty and within MAX_ASIN_COUNT
    - date_from <= date_to
    - window <= MAX_DATE_WINDOW_DAYS

    Always includes freshness metadata.

    When *include_latest_available* is True and the requested *date_to* exceeds
    the profile-wide latest available date, ``latest_available_by_asin`` is
    populated with each ASIN's own most-recent row (not the profile-wide latest
    date), so mixed-vintage ASIN sets produce accurate per-ASIN snapshots.

    Algorithm for per-ASIN latest rows:
    1. Compute per-ASIN max date directly from the windowed facts already
       fetched — the window extends to ``date_to`` which is beyond the data
       horizon, so every available row for each ASIN is already present.
    2. For ASINs that have *no* rows in the window (``date_from`` may be after
       their last available row), fall back to a single targeted DB query per
       such ASIN.
    """
    _get_profile(db, profile_id)

    normalized_asins = [
        str(a or "").strip().upper()
        for a in (child_asins or [])
        if str(a or "").strip()
    ]
    if not normalized_asins:
        raise AnalystQueryError("validation_error", "child_asins must not be empty.")
    if len(normalized_asins) > MAX_ASIN_COUNT:
        raise AnalystQueryError(
            "validation_error",
            f"Too many ASINs requested ({len(normalized_asins)}). "
            f"Limit is {MAX_ASIN_COUNT}.",
        )

    from_date = _parse_date(date_from)
    to_date = _parse_date(date_to)
    if from_date > to_date:
        raise AnalystQueryError(
            "validation_error",
            f"date_from ({date_from}) must not be after date_to ({date_to}).",
        )
    window_days = (to_date - from_date).days + 1
    if window_days > MAX_DATE_WINDOW_DAYS:
        raise AnalystQueryError(
            "validation_error",
            f"Date window is {window_days} days. Limit is {MAX_DATE_WINDOW_DAYS} days.",
        )

    # Profile-wide latest date for the summary freshness block.
    profile_latest_date_str = _latest_available_date(
        db, "wbr_business_asin_daily", profile_id
    )

    facts = _select_all(
        db,
        "wbr_business_asin_daily",
        "report_date, child_asin, unit_sales, sales, page_views",
        [
            ("eq", "profile_id", profile_id),
            ("gte", "report_date", from_date.isoformat()),
            ("lte", "report_date", to_date.isoformat()),
            ("in_", "child_asin", normalized_asins),
        ],
    )

    # Aggregate totals and track per-ASIN latest date.
    totals: dict[str, dict[str, Any]] = {a: {} for a in normalized_asins}
    asin_max_date: dict[str, str] = {}
    asin_latest_fact: dict[str, dict[str, Any]] = {}

    for fact in facts:
        if not isinstance(fact, dict):
            continue
        asin = str(fact.get("child_asin") or "").strip().upper()
        if asin not in totals:
            continue
        rd = str(fact.get("report_date") or "").strip()

        acc = totals[asin]
        acc["unit_sales"] = int(acc.get("unit_sales") or 0) + int(fact.get("unit_sales") or 0)
        acc["sales"] = Decimal(str(acc.get("sales") or "0")) + Decimal(
            str(fact.get("sales") or "0")
        )
        acc["page_views"] = int(acc.get("page_views") or 0) + int(
            fact.get("page_views") or 0
        )

        if rd and (asin not in asin_max_date or rd > asin_max_date[asin]):
            asin_max_date[asin] = rd
            asin_latest_fact[asin] = fact

    # Determine whether the requested window exceeds available data.
    profile_latest_date = (
        date.fromisoformat(profile_latest_date_str) if profile_latest_date_str else None
    )
    beyond_data = profile_latest_date is not None and to_date > profile_latest_date
    freshness_note = (
        f"Requested end date {date_to} has no landed data yet. "
        f"Latest available: {profile_latest_date_str}."
        if beyond_data
        else None
    )

    # Build per-ASIN result rows.
    asin_rows: list[dict[str, Any]] = []
    latest_available_by_asin: dict[str, Any] = {}
    asins_without_window_data = set(normalized_asins) - set(asin_max_date.keys())

    # For ASINs with no window data, fall back to a targeted lookback query.
    if include_latest_available and beyond_data and asins_without_window_data:
        for asin in asins_without_window_data:
            fallback_resp = (
                db.table("wbr_business_asin_daily")
                .select("report_date, child_asin, unit_sales, sales, page_views")
                .eq("profile_id", profile_id)
                .eq("child_asin", asin)
                .order("report_date", desc=True)
                .limit(1)
                .execute()
            )
            fallback_rows = (
                fallback_resp.data if isinstance(fallback_resp.data, list) else []
            )
            if fallback_rows:
                asin_latest_fact[asin] = fallback_rows[0]
                asin_max_date[asin] = str(fallback_rows[0].get("report_date") or "").strip()

    for asin in normalized_asins:
        acc = totals[asin]
        row: dict[str, Any] = {
            "child_asin": asin,
            "unit_sales": int(acc.get("unit_sales") or 0),
            "sales": format(
                Decimal(str(acc.get("sales") or "0")).quantize(Decimal("0.01")), "f"
            ),
            "page_views": int(acc.get("page_views") or 0),
        }
        asin_rows.append(row)

        if include_latest_available and beyond_data and asin in asin_latest_fact:
            lf = asin_latest_fact[asin]
            latest_available_by_asin[asin] = {
                "report_date": str(lf.get("report_date") or "").strip(),
                "unit_sales": int(lf.get("unit_sales") or 0),
                "sales": format(
                    Decimal(str(lf.get("sales") or "0")).quantize(Decimal("0.01")), "f"
                ),
                "page_views": int(lf.get("page_views") or 0),
            }

    result: dict[str, Any] = {
        "profile_id": profile_id,
        "date_from": date_from,
        "date_to": date_to,
        "asins": asin_rows,
        "freshness": {
            "latest_available_date": profile_latest_date_str,
            "note": freshness_note,
        },
    }
    if include_latest_available and beyond_data:
        result["latest_available_by_asin"] = [
            {"child_asin": asin, **snap}
            for asin, snap in latest_available_by_asin.items()
        ]
    return result


# ---------------------------------------------------------------------------
# list_child_asins_for_row
# ---------------------------------------------------------------------------


def list_child_asins_for_row(
    db: Any,
    profile_id: str,
    row_id: str,
) -> dict[str, Any]:
    """Return child ASINs mapped to a WBR row, with product title and scope status.

    Resolves parent rows to their active descendant leaves so the result always
    reflects which ASINs actually contribute to a row (including nested groups).
    """
    _get_profile(db, profile_id)

    # Validate that the row exists and belongs to this profile.
    row_resp = (
        db.table("wbr_rows")
        .select("id, row_kind, row_label")
        .eq("id", row_id)
        .eq("profile_id", profile_id)
        .eq("active", True)
        .limit(1)
        .execute()
    )
    row_rows = row_resp.data if isinstance(row_resp.data, list) else []
    if not row_rows:
        raise AnalystQueryError(
            "not_found",
            f"Row '{row_id}' not found for profile '{profile_id}'.",
        )
    row_kind = str(row_rows[0].get("row_kind") or "").strip()
    row_label = str(row_rows[0].get("row_label") or "").strip()

    # Determine the set of leaf row IDs whose ASINs we want.
    if row_kind == "leaf":
        target_row_ids = {row_id}
        resolved_via = "direct_mapping"
    else:
        # Parent/group row: collect all active leaf descendants.
        all_profile_rows = _select_all(
            db,
            "wbr_rows",
            "id, row_kind, parent_row_id",
            [("eq", "profile_id", profile_id), ("eq", "active", True)],
        )
        target_row_ids = _find_descendant_leaf_ids(all_profile_rows, row_id)
        resolved_via = "descendant_leaves"

    if not target_row_ids:
        return {
            "profile_id": profile_id,
            "row_id": row_id,
            "row_kind": row_kind,
            "row_label": row_label,
            "resolved_via": resolved_via,
            "note": "No active descendant leaf rows found for this parent row.",
            "child_asins": [],
            "total": 0,
        }

    # Load all active mappings for this profile, then filter to target rows.
    all_mappings = _select_all(
        db,
        "wbr_asin_row_map",
        "child_asin, row_id",
        [("eq", "profile_id", profile_id), ("eq", "active", True)],
    )
    mappings_for_target = [
        m
        for m in all_mappings
        if isinstance(m, dict)
        and str(m.get("row_id") or "").strip() in target_row_ids
    ]

    # Deduplicate by child_asin (same ASIN mapped under multiple leaf rows).
    seen: set[str] = set()
    unique_mappings: list[dict[str, Any]] = []
    for m in mappings_for_target:
        asin = str(m.get("child_asin") or "").strip().upper()
        if asin and asin not in seen:
            seen.add(asin)
            unique_mappings.append(m)

    # Load exclusion flags and reasons.
    exclusions = _select_all(
        db,
        "wbr_asin_exclusions",
        "child_asin, exclusion_reason",
        [("eq", "profile_id", profile_id), ("eq", "active", True)],
    )
    exclusion_by_asin: dict[str, str | None] = {
        str(e.get("child_asin") or "").strip().upper(): (
            str(e.get("exclusion_reason") or "").strip() or None
        )
        for e in exclusions
        if isinstance(e, dict) and str(e.get("child_asin") or "").strip()
    }

    # Load catalog metadata.
    catalog = _select_all(
        db,
        "wbr_profile_child_asins",
        "child_asin, child_product_name, child_sku, category",
        [("eq", "profile_id", profile_id), ("eq", "active", True)],
    )
    catalog_by_asin: dict[str, dict[str, Any]] = {}
    for c in catalog:
        if not isinstance(c, dict):
            continue
        a = str(c.get("child_asin") or "").strip().upper()
        if a:
            catalog_by_asin[a] = c

    result_asins: list[dict[str, Any]] = []
    for m in unique_mappings:
        asin = str(m.get("child_asin") or "").strip().upper()
        if not asin:
            continue
        cat = catalog_by_asin.get(asin, {})
        is_excluded = asin in exclusion_by_asin
        scope_status = "excluded" if is_excluded else "included"
        exclusion_reason = exclusion_by_asin.get(asin) if is_excluded else None
        result_asins.append(
            {
                "child_asin": asin,
                "title": str(cat.get("child_product_name") or "").strip() or None,
                "child_sku": str(cat.get("child_sku") or "").strip() or None,
                "category": str(cat.get("category") or "").strip() or None,
                "scope_status": scope_status,
                "exclusion_reason": exclusion_reason,
            }
        )

    note: str | None
    if row_kind == "leaf":
        note = None
    elif result_asins:
        note = (
            f"This row resolved to {len(result_asins)} ASIN(s) via its descendant leaf rows."
        )
    else:
        note = "No active descendant leaf rows found for this parent row."

    return {
        "profile_id": profile_id,
        "row_id": row_id,
        "row_kind": row_kind,
        "row_label": row_label,
        "resolved_via": resolved_via,
        "note": note,
        "child_asins": result_asins,
        "total": len(result_asins),
    }


# ---------------------------------------------------------------------------
# get_sync_freshness_status
# ---------------------------------------------------------------------------


def get_sync_freshness_status(db: Any, profile_id: str) -> dict[str, Any]:
    """Return sync freshness metadata for a WBR profile."""
    profile = _get_profile(db, profile_id)

    biz_sync = _latest_sync_run(db, profile_id, "windsor_business")
    ads_sync = _latest_sync_run(db, profile_id, "amazon_ads")
    biz_latest = _latest_available_date(db, "wbr_business_asin_daily", profile_id)
    ads_latest = _latest_available_date(db, "wbr_ads_campaign_daily", profile_id)

    warnings: list[str] = []
    if biz_sync is None:
        warnings.append("No successful Windsor business sync found for this profile.")
    if ads_sync is None:
        warnings.append("No successful Amazon Ads sync found for this profile.")
    if biz_latest is None:
        warnings.append("No business fact data found for this profile.")
    if ads_latest is None:
        warnings.append("No ads fact data found for this profile.")

    def _sync_summary(run: dict[str, Any] | None) -> dict[str, Any]:
        if run is None:
            return {"found": False}
        return {
            "found": True,
            "finished_at": str(run.get("finished_at") or "").strip() or None,
            "started_at": str(run.get("started_at") or "").strip() or None,
        }

    return {
        "profile_id": profile_id,
        "marketplace_code": str(profile.get("marketplace_code") or "").strip() or None,
        "business_sync": _sync_summary(biz_sync),
        "ads_sync": _sync_summary(ads_sync),
        "latest_business_fact_date": biz_latest,
        "latest_ads_fact_date": ads_latest,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Slice 2 constants and helpers
# ---------------------------------------------------------------------------

MAX_RESULT_ROWS = 200
MAX_CAMPAIGN_NAMES = 50

_ALLOWED_BUSINESS_GROUP_BY = frozenset({"day", "child_asin", "row"})
_ALLOWED_ADS_GROUP_BY = frozenset({"day", "campaign", "campaign_type", "row"})
_ALLOWED_SEARCH_TERM_GROUP_BY = frozenset(
    {"day", "search_term", "keyword", "campaign", "keyword_type"}
)
_ALLOWED_BUSINESS_METRICS = frozenset({"unit_sales", "sales", "page_views"})
_DEFAULT_BUSINESS_METRICS: tuple[str, ...] = ("unit_sales", "sales", "page_views")
_ALLOWED_ADS_METRICS = frozenset({"spend", "sales", "impressions", "clicks", "orders"})
_DEFAULT_ADS_METRICS: tuple[str, ...] = ("spend", "sales", "impressions", "clicks", "orders")
_ALLOWED_SEARCH_TERM_METRICS = _ALLOWED_ADS_METRICS
_DEFAULT_SEARCH_TERM_METRICS: tuple[str, ...] = _DEFAULT_ADS_METRICS
_ALLOWED_SEARCH_TERM_SORT_BY = frozenset(
    {"spend", "sales", "impressions", "clicks", "orders", "acos", "roas", "ctr", "cvr", "cpc"}
)
_DECIMAL_METRICS = frozenset({"sales", "spend"})
_UNMAPPED_BUCKET = "__unmapped__"


def _acc_metrics(acc: dict[str, Any], source: dict[str, Any], metrics: list[str]) -> None:
    for m in metrics:
        if m in _DECIMAL_METRICS:
            acc[m] = Decimal(str(acc.get(m) or "0")) + Decimal(str(source.get(m) or "0"))
        else:
            acc[m] = int(acc.get(m) or 0) + int(source.get(m) or 0)


def _fmt_metrics(acc: dict[str, Any], metrics: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for m in metrics:
        if m in _DECIMAL_METRICS:
            out[m] = format(Decimal(str(acc.get(m) or "0")).quantize(Decimal("0.01")), "f")
        else:
            out[m] = int(acc.get(m) or 0)
    return out


def _quantize_decimal(value: Decimal, precision: str) -> str:
    return format(value.quantize(Decimal(precision)), "f")


def _safe_ratio(numerator: Any, denominator: Any) -> Decimal | None:
    numerator_decimal = Decimal(str(numerator or "0"))
    denominator_decimal = Decimal(str(denominator or "0"))
    if denominator_decimal <= 0:
        return None
    return numerator_decimal / denominator_decimal


def _fmt_ratio(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return _quantize_decimal(value, "0.0001")


def _search_term_rank_metrics(acc: dict[str, Any]) -> dict[str, str | None]:
    spend = Decimal(str(acc.get("spend") or "0"))
    sales = Decimal(str(acc.get("sales") or "0"))
    impressions = Decimal(str(acc.get("impressions") or "0"))
    clicks = Decimal(str(acc.get("clicks") or "0"))
    orders = Decimal(str(acc.get("orders") or "0"))

    return {
        "acos": _fmt_ratio(_safe_ratio(spend, sales)),
        "roas": _fmt_ratio(_safe_ratio(sales, spend)),
        "ctr": _fmt_ratio(_safe_ratio(clicks, impressions)),
        "cvr": _fmt_ratio(_safe_ratio(orders, clicks)),
        "cpc": _fmt_ratio(_safe_ratio(spend, clicks)),
    }


def _search_term_sort_value(acc: dict[str, Any], sort_by: str) -> tuple[int, Decimal]:
    if sort_by in _ALLOWED_SEARCH_TERM_METRICS:
        return (0, Decimal(str(acc.get(sort_by) or "0")))

    if sort_by == "acos":
        ratio = _safe_ratio(acc.get("spend"), acc.get("sales"))
    elif sort_by == "roas":
        ratio = _safe_ratio(acc.get("sales"), acc.get("spend"))
    elif sort_by == "ctr":
        ratio = _safe_ratio(acc.get("clicks"), acc.get("impressions"))
    elif sort_by == "cvr":
        ratio = _safe_ratio(acc.get("orders"), acc.get("clicks"))
    else:  # cpc
        ratio = _safe_ratio(acc.get("spend"), acc.get("clicks"))

    if ratio is None:
        return (1, Decimal("-1"))
    return (0, ratio)


def _search_term_sort_key(acc: dict[str, Any], sort_by: str, label: str) -> tuple[int, Decimal, str]:
    missing_flag, value = _search_term_sort_value(acc, sort_by)
    return (missing_flag, -value, label.lower())


def _validate_date_window(date_from: str, date_to: str) -> tuple[date, date]:
    from_date = _parse_date(date_from)
    to_date = _parse_date(date_to)
    if from_date > to_date:
        raise AnalystQueryError(
            "validation_error",
            f"date_from ({date_from}) must not be after date_to ({date_to}).",
        )
    window_days = (to_date - from_date).days + 1
    if window_days > MAX_DATE_WINDOW_DAYS:
        raise AnalystQueryError(
            "validation_error",
            f"Date window is {window_days} days. Limit is {MAX_DATE_WINDOW_DAYS} days.",
        )
    return from_date, to_date


def _resolve_target_row_ids(db: Any, profile_id: str, row_id: str) -> set[str]:
    """Return the set of active leaf row IDs for *row_id* (leaf or ancestor).

    Raises AnalystQueryError if the row does not exist for the given profile.
    """
    row_resp = (
        db.table("wbr_rows")
        .select("id, row_kind")
        .eq("id", row_id)
        .eq("profile_id", profile_id)
        .eq("active", True)
        .limit(1)
        .execute()
    )
    resp_rows = row_resp.data if isinstance(row_resp.data, list) else []
    if not resp_rows:
        raise AnalystQueryError(
            "not_found",
            f"Row '{row_id}' not found for profile '{profile_id}'.",
        )
    row_kind = str(resp_rows[0].get("row_kind") or "").strip()
    if row_kind == "leaf":
        return {row_id}
    all_profile_rows = _select_all(
        db,
        "wbr_rows",
        "id, row_kind, parent_row_id",
        [("eq", "profile_id", profile_id), ("eq", "active", True)],
    )
    return _find_descendant_leaf_ids(all_profile_rows, row_id)


def _asin_set_for_row(db: Any, profile_id: str, row_id: str) -> set[str]:
    """Return active child ASINs mapped to a WBR row (leaf or ancestor)."""
    target_ids = _resolve_target_row_ids(db, profile_id, row_id)
    if not target_ids:
        return set()
    mappings = _select_all(
        db,
        "wbr_asin_row_map",
        "child_asin, row_id",
        [("eq", "profile_id", profile_id), ("eq", "active", True)],
    )
    return {
        str(m.get("child_asin") or "").strip().upper()
        for m in mappings
        if isinstance(m, dict)
        and str(m.get("child_asin") or "").strip()
        and str(m.get("row_id") or "").strip() in target_ids
    }


def _campaign_set_for_row(db: Any, profile_id: str, row_id: str) -> set[str]:
    """Return campaign names mapped to a WBR row (leaf or ancestor)."""
    target_ids = _resolve_target_row_ids(db, profile_id, row_id)
    if not target_ids:
        return set()
    mappings = _select_all(
        db,
        "wbr_pacvue_campaign_map",
        "campaign_name, row_id",
        [("eq", "profile_id", profile_id), ("eq", "active", True)],
    )
    return {
        str(m.get("campaign_name") or "").strip()
        for m in mappings
        if isinstance(m, dict)
        and str(m.get("campaign_name") or "").strip()
        and str(m.get("row_id") or "").strip() in target_ids
    }


# ---------------------------------------------------------------------------
# Empty-result helpers (used when a row scope resolves to nothing)
# ---------------------------------------------------------------------------


def _empty_business_facts_result(
    profile_id: str,
    date_from: str,
    date_to: str,
    group_by: str,
    metrics: list[str],
) -> dict[str, Any]:
    return {
        "profile_id": profile_id,
        "date_from": date_from,
        "date_to": date_to,
        "group_by": group_by,
        "metrics": list(metrics),
        "rows": [],
        "totals": _fmt_metrics({}, metrics),
        "row_count": 0,
        "truncated": False,
        "freshness": {"latest_available_date": None, "note": None},
        "warnings": [],
    }


def _empty_ads_facts_result(
    profile_id: str,
    date_from: str,
    date_to: str,
    group_by: str,
    metrics: list[str],
) -> dict[str, Any]:
    return {
        "profile_id": profile_id,
        "date_from": date_from,
        "date_to": date_to,
        "group_by": group_by,
        "metrics": list(metrics),
        "rows": [],
        "totals": _fmt_metrics({}, metrics),
        "row_count": 0,
        "truncated": False,
        "freshness": {"latest_available_date": None, "note": None},
        "warnings": [],
    }


def _empty_search_term_facts_result(
    profile_id: str,
    date_from: str,
    date_to: str,
    group_by: str,
    metrics: list[str],
    sort_by: str,
) -> dict[str, Any]:
    return {
        "profile_id": profile_id,
        "date_from": date_from,
        "date_to": date_to,
        "group_by": group_by,
        "metrics": list(metrics),
        "sort_by": sort_by,
        "rows": [],
        "totals": {
            **_fmt_metrics({}, metrics),
            **_search_term_rank_metrics({}),
        },
        "row_count": 0,
        "truncated": False,
        "freshness": {"latest_available_date": None, "note": None},
        "warnings": [],
    }


# ---------------------------------------------------------------------------
# query_business_facts
# ---------------------------------------------------------------------------


def query_business_facts(
    db: Any,
    profile_id: str,
    date_from: str,
    date_to: str,
    group_by: str,
    *,
    child_asins: list[str] | None = None,
    row_id: str | None = None,
    metrics: list[str] | None = None,
    limit: int = MAX_RESULT_ROWS,
) -> dict[str, Any]:
    """Flexible business-fact drill-down grouped by day, child_asin, or row.

    Supports row-based ASIN resolution via active descendant leaves.
    When no ASIN scope is given, all facts for the profile are returned.
    """
    _get_profile(db, profile_id)
    from_date, to_date = _validate_date_window(date_from, date_to)

    group_by = str(group_by or "").strip().lower()
    if group_by not in _ALLOWED_BUSINESS_GROUP_BY:
        raise AnalystQueryError(
            "validation_error",
            f"group_by must be one of {sorted(_ALLOWED_BUSINESS_GROUP_BY)}. Got '{group_by}'.",
        )

    effective_metrics = list(_DEFAULT_BUSINESS_METRICS)
    if metrics is not None:
        bad = [m for m in metrics if m not in _ALLOWED_BUSINESS_METRICS]
        if bad:
            raise AnalystQueryError(
                "validation_error",
                f"Unknown metric(s): {bad}. Allowed: {sorted(_ALLOWED_BUSINESS_METRICS)}.",
            )
        effective_metrics = [m for m in metrics if m] or list(_DEFAULT_BUSINESS_METRICS)

    limit = min(max(1, int(limit)), MAX_RESULT_ROWS)

    # Resolve ASIN scope.
    explicit_asins: set[str] = {
        str(a or "").strip().upper() for a in (child_asins or []) if str(a or "").strip()
    }
    row_asins: set[str] = _asin_set_for_row(db, profile_id, row_id) if row_id else set()
    all_asins = explicit_asins | row_asins
    # If a row_id was given but resolved to no ASINs and no explicit ASINs were
    # provided, return empty rather than falling through to a profile-wide query.
    if row_id and not all_asins:
        return _empty_business_facts_result(
            profile_id, date_from, date_to, group_by, effective_metrics
        )
    if all_asins and len(all_asins) > MAX_ASIN_COUNT:
        raise AnalystQueryError(
            "validation_error",
            f"Resolved {len(all_asins)} ASINs exceeds limit of {MAX_ASIN_COUNT}.",
        )

    # For "row" grouping, pre-load the ASIN→row and row→label lookups.
    asin_to_row_id: dict[str, str] = {}
    row_label_by_id: dict[str, str] = {}
    if group_by == "row":
        for m in _select_all(
            db,
            "wbr_asin_row_map",
            "child_asin, row_id",
            [("eq", "profile_id", profile_id), ("eq", "active", True)],
        ):
            a = str(m.get("child_asin") or "").strip().upper()
            r = str(m.get("row_id") or "").strip()
            if a and r:
                asin_to_row_id[a] = r
        for r in _select_all(
            db,
            "wbr_rows",
            "id, row_label",
            [("eq", "profile_id", profile_id), ("eq", "active", True)],
        ):
            rid = str(r.get("id") or "").strip()
            if rid:
                row_label_by_id[rid] = str(r.get("row_label") or "").strip()

    profile_latest_date_str = _latest_available_date(db, "wbr_business_asin_daily", profile_id)

    query_filters: list[tuple[str, str, Any]] = [
        ("eq", "profile_id", profile_id),
        ("gte", "report_date", from_date.isoformat()),
        ("lte", "report_date", to_date.isoformat()),
    ]
    if all_asins:
        query_filters.append(("in_", "child_asin", sorted(all_asins)))

    select_cols = ", ".join(["report_date", "child_asin"] + effective_metrics)
    facts = _select_all(db, "wbr_business_asin_daily", select_cols, query_filters)

    # Group in Python.
    groups: dict[str, dict[str, Any]] = {}
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        asin = str(fact.get("child_asin") or "").strip().upper()
        rd = str(fact.get("report_date") or "").strip()
        if group_by == "day":
            key = rd
        elif group_by == "child_asin":
            key = asin
        else:  # "row"
            key = asin_to_row_id.get(asin, _UNMAPPED_BUCKET)
        if key not in groups:
            groups[key] = {}
        _acc_metrics(groups[key], fact, effective_metrics)

    # Totals over all groups (computed before truncation).
    totals_acc: dict[str, Any] = {}
    for acc in groups.values():
        _acc_metrics(totals_acc, acc, effective_metrics)

    # Build ordered output rows.
    if group_by == "day":
        output_rows: list[dict[str, Any]] = [
            {"date": k, **_fmt_metrics(groups[k], effective_metrics)}
            for k in sorted(groups)
        ]
    elif group_by == "child_asin":
        output_rows = [
            {"child_asin": k, **_fmt_metrics(groups[k], effective_metrics)}
            for k in sorted(groups)
        ]
    else:  # "row"
        def _row_sort_biz(k: str) -> tuple[int, str]:
            if k == _UNMAPPED_BUCKET:
                return (1, "")
            return (0, row_label_by_id.get(k, k).lower())

        output_rows = []
        for k in sorted(groups, key=_row_sort_biz):
            if k == _UNMAPPED_BUCKET:
                output_rows.append(
                    {
                        "row_id": None,
                        "row_label": "Unmapped / Legacy",
                        **_fmt_metrics(groups[k], effective_metrics),
                    }
                )
            else:
                output_rows.append(
                    {
                        "row_id": k,
                        "row_label": row_label_by_id.get(k, k),
                        **_fmt_metrics(groups[k], effective_metrics),
                    }
                )

    truncated = len(output_rows) > limit
    if truncated:
        output_rows = output_rows[:limit]

    # Freshness metadata.
    profile_latest_date = (
        date.fromisoformat(profile_latest_date_str) if profile_latest_date_str else None
    )
    freshness_note = (
        f"Requested end date {date_to} has no landed data yet. "
        f"Latest available: {profile_latest_date_str}."
        if profile_latest_date and to_date > profile_latest_date
        else None
    )

    warnings: list[str] = []
    if truncated:
        warnings.append(
            f"Result truncated to {limit} rows. Use a narrower date range or scope to see all data."
        )

    return {
        "profile_id": profile_id,
        "date_from": date_from,
        "date_to": date_to,
        "group_by": group_by,
        "metrics": effective_metrics,
        "rows": output_rows,
        "totals": _fmt_metrics(totals_acc, effective_metrics),
        "row_count": len(output_rows),
        "truncated": truncated,
        "freshness": {
            "latest_available_date": profile_latest_date_str,
            "note": freshness_note,
        },
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# query_ads_facts
# ---------------------------------------------------------------------------


def query_ads_facts(
    db: Any,
    profile_id: str,
    date_from: str,
    date_to: str,
    group_by: str,
    *,
    campaign_names: list[str] | None = None,
    row_id: str | None = None,
    metrics: list[str] | None = None,
    limit: int = MAX_RESULT_ROWS,
) -> dict[str, Any]:
    """Flexible ads-fact drill-down grouped by day, campaign, campaign_type, or row."""
    _get_profile(db, profile_id)
    from_date, to_date = _validate_date_window(date_from, date_to)

    group_by = str(group_by or "").strip().lower()
    if group_by not in _ALLOWED_ADS_GROUP_BY:
        raise AnalystQueryError(
            "validation_error",
            f"group_by must be one of {sorted(_ALLOWED_ADS_GROUP_BY)}. Got '{group_by}'.",
        )

    effective_metrics = list(_DEFAULT_ADS_METRICS)
    if metrics is not None:
        bad = [m for m in metrics if m not in _ALLOWED_ADS_METRICS]
        if bad:
            raise AnalystQueryError(
                "validation_error",
                f"Unknown metric(s): {bad}. Allowed: {sorted(_ALLOWED_ADS_METRICS)}.",
            )
        effective_metrics = [m for m in metrics if m] or list(_DEFAULT_ADS_METRICS)

    limit = min(max(1, int(limit)), MAX_RESULT_ROWS)

    # Campaign scope.
    explicit_campaigns: set[str] = {
        str(c or "").strip() for c in (campaign_names or []) if str(c or "").strip()
    }
    if explicit_campaigns and len(explicit_campaigns) > MAX_CAMPAIGN_NAMES:
        raise AnalystQueryError(
            "validation_error",
            f"Too many campaign names ({len(explicit_campaigns)}). "
            f"Limit is {MAX_CAMPAIGN_NAMES}.",
        )
    row_campaigns: set[str] = (
        _campaign_set_for_row(db, profile_id, row_id) if row_id else set()
    )
    all_campaigns = explicit_campaigns | row_campaigns
    # If a row_id was given but resolved to no campaigns and no explicit
    # campaign names were provided, return empty rather than a profile-wide query.
    if row_id and not all_campaigns:
        return _empty_ads_facts_result(
            profile_id, date_from, date_to, group_by, effective_metrics
        )

    # For "row" grouping, pre-load campaign→row and row→label lookups.
    campaign_to_row_id: dict[str, str] = {}
    row_label_by_id: dict[str, str] = {}
    if group_by == "row":
        for m in _select_all(
            db,
            "wbr_pacvue_campaign_map",
            "campaign_name, row_id",
            [("eq", "profile_id", profile_id), ("eq", "active", True)],
        ):
            cn = str(m.get("campaign_name") or "").strip()
            r = str(m.get("row_id") or "").strip()
            if cn and r:
                campaign_to_row_id[cn] = r
        for r in _select_all(
            db,
            "wbr_rows",
            "id, row_label",
            [("eq", "profile_id", profile_id), ("eq", "active", True)],
        ):
            rid = str(r.get("id") or "").strip()
            if rid:
                row_label_by_id[rid] = str(r.get("row_label") or "").strip()

    ads_latest_date_str = _latest_available_date(db, "wbr_ads_campaign_daily", profile_id)

    query_filters: list[tuple[str, str, Any]] = [
        ("eq", "profile_id", profile_id),
        ("gte", "report_date", from_date.isoformat()),
        ("lte", "report_date", to_date.isoformat()),
    ]
    if all_campaigns:
        query_filters.append(("in_", "campaign_name", sorted(all_campaigns)))

    select_cols = ", ".join(
        ["report_date", "campaign_name", "campaign_type"] + effective_metrics
    )
    facts = _select_all(db, "wbr_ads_campaign_daily", select_cols, query_filters)

    # Group in Python.
    groups: dict[str, dict[str, Any]] = {}
    group_campaign_type: dict[str, str] = {}  # first-seen campaign_type per key

    for fact in facts:
        if not isinstance(fact, dict):
            continue
        cn = str(fact.get("campaign_name") or "").strip()
        ct = str(fact.get("campaign_type") or "").strip() or "unknown"
        rd = str(fact.get("report_date") or "").strip()

        if group_by == "day":
            key = rd
        elif group_by == "campaign":
            key = cn or "(unnamed)"
            if key not in group_campaign_type:
                group_campaign_type[key] = ct
        elif group_by == "campaign_type":
            key = ct
        else:  # "row"
            key = campaign_to_row_id.get(cn, _UNMAPPED_BUCKET)

        if key not in groups:
            groups[key] = {}
        _acc_metrics(groups[key], fact, effective_metrics)

    # Totals over all groups (before truncation).
    totals_acc: dict[str, Any] = {}
    for acc in groups.values():
        _acc_metrics(totals_acc, acc, effective_metrics)

    # Build ordered output rows.
    if group_by == "day":
        output_rows: list[dict[str, Any]] = [
            {"date": k, **_fmt_metrics(groups[k], effective_metrics)}
            for k in sorted(groups)
        ]
    elif group_by == "campaign":
        # Sort by spend descending (most useful first).
        def _campaign_spend(k: str) -> Decimal:
            return Decimal(str(groups[k].get("spend") or "0"))

        output_rows = [
            {
                "campaign_name": k,
                "campaign_type": group_campaign_type.get(k, "unknown"),
                **_fmt_metrics(groups[k], effective_metrics),
            }
            for k in sorted(groups, key=_campaign_spend, reverse=True)
        ]
    elif group_by == "campaign_type":
        output_rows = [
            {"campaign_type": k, **_fmt_metrics(groups[k], effective_metrics)}
            for k in sorted(groups)
        ]
    else:  # "row"
        def _row_sort_ads(k: str) -> tuple[int, str]:
            if k == _UNMAPPED_BUCKET:
                return (1, "")
            return (0, row_label_by_id.get(k, k).lower())

        output_rows = []
        for k in sorted(groups, key=_row_sort_ads):
            if k == _UNMAPPED_BUCKET:
                output_rows.append(
                    {
                        "row_id": None,
                        "row_label": "Unmapped / Legacy",
                        **_fmt_metrics(groups[k], effective_metrics),
                    }
                )
            else:
                output_rows.append(
                    {
                        "row_id": k,
                        "row_label": row_label_by_id.get(k, k),
                        **_fmt_metrics(groups[k], effective_metrics),
                    }
                )

    truncated = len(output_rows) > limit
    if truncated:
        output_rows = output_rows[:limit]

    ads_latest_date = (
        date.fromisoformat(ads_latest_date_str) if ads_latest_date_str else None
    )
    freshness_note = (
        f"Requested end date {date_to} has no landed data yet. "
        f"Latest available: {ads_latest_date_str}."
        if ads_latest_date and to_date > ads_latest_date
        else None
    )

    return {
        "profile_id": profile_id,
        "date_from": date_from,
        "date_to": date_to,
        "group_by": group_by,
        "metrics": effective_metrics,
        "rows": output_rows,
        "totals": _fmt_metrics(totals_acc, effective_metrics),
        "row_count": len(output_rows),
        "truncated": truncated,
        "freshness": {
            "latest_available_date": ads_latest_date_str,
            "note": freshness_note,
        },
        "warnings": [],
    }


# ---------------------------------------------------------------------------
# query_search_term_facts
# ---------------------------------------------------------------------------


def _query_search_term_facts_python(
    db: Any,
    profile_id: str,
    date_from: str,
    date_to: str,
    group_by: str,
    *,
    ad_product: str | None = None,
    campaign_type: str | None = None,
    keyword_type: str | None = None,
    match_type: str | None = None,
    campaign_name_contains: str | None = None,
    search_term_contains: str | None = None,
    keyword_contains: str | None = None,
    row_id: str | None = None,
    metrics: list[str] | None = None,
    sort_by: str = "spend",
    limit: int = MAX_RESULT_ROWS,
) -> dict[str, Any]:
    """Python fallback for STR drill-down grouped by day, search term, keyword, campaign, or keyword type."""
    _get_profile(db, profile_id)
    from_date, to_date = _validate_date_window(date_from, date_to)

    group_by = str(group_by or "").strip().lower()
    if group_by not in _ALLOWED_SEARCH_TERM_GROUP_BY:
        raise AnalystQueryError(
            "validation_error",
            f"group_by must be one of {sorted(_ALLOWED_SEARCH_TERM_GROUP_BY)}. Got '{group_by}'.",
        )

    effective_metrics = list(_DEFAULT_SEARCH_TERM_METRICS)
    if metrics is not None:
        bad = [m for m in metrics if m not in _ALLOWED_SEARCH_TERM_METRICS]
        if bad:
            raise AnalystQueryError(
                "validation_error",
                f"Unknown metric(s): {bad}. Allowed: {sorted(_ALLOWED_SEARCH_TERM_METRICS)}.",
            )
        effective_metrics = [m for m in metrics if m] or list(_DEFAULT_SEARCH_TERM_METRICS)
    accumulator_metrics = list(_DEFAULT_SEARCH_TERM_METRICS)

    sort_by = str(sort_by or "spend").strip().lower()
    if sort_by not in _ALLOWED_SEARCH_TERM_SORT_BY:
        raise AnalystQueryError(
            "validation_error",
            f"sort_by must be one of {sorted(_ALLOWED_SEARCH_TERM_SORT_BY)}. Got '{sort_by}'.",
        )

    limit = min(max(1, int(limit)), MAX_RESULT_ROWS)

    scoped_campaigns: set[str] = (
        _campaign_set_for_row(db, profile_id, row_id) if row_id else set()
    )
    if row_id and not scoped_campaigns:
        return _empty_search_term_facts_result(
            profile_id, date_from, date_to, group_by, effective_metrics, sort_by
        )

    query_filters: list[tuple[str, str, Any]] = [
        ("eq", "profile_id", profile_id),
        ("gte", "report_date", from_date.isoformat()),
        ("lte", "report_date", to_date.isoformat()),
    ]

    normalized_ad_product = str(ad_product or "").strip()
    normalized_campaign_type = str(campaign_type or "").strip()
    normalized_keyword_type = str(keyword_type or "").strip()
    normalized_match_type = str(match_type or "").strip()
    normalized_campaign_contains = str(campaign_name_contains or "").strip()
    normalized_search_term_contains = str(search_term_contains or "").strip()
    normalized_keyword_contains = str(keyword_contains or "").strip()

    if normalized_ad_product:
        query_filters.append(("eq", "ad_product", normalized_ad_product))
    if normalized_campaign_type:
        query_filters.append(("eq", "campaign_type", normalized_campaign_type))
    if normalized_keyword_type:
        query_filters.append(("eq", "keyword_type", normalized_keyword_type))
    if normalized_match_type:
        query_filters.append(("eq", "match_type", normalized_match_type))
    if normalized_campaign_contains:
        query_filters.append(("ilike", "campaign_name", f"%{normalized_campaign_contains}%"))
    if normalized_search_term_contains:
        query_filters.append(("ilike", "search_term", f"%{normalized_search_term_contains}%"))
    if normalized_keyword_contains:
        query_filters.append(("ilike", "keyword", f"%{normalized_keyword_contains}%"))
    if scoped_campaigns:
        query_filters.append(("in_", "campaign_name", sorted(scoped_campaigns)))

    facts = _select_all(
        db,
        "search_term_daily_facts",
        "report_date, campaign_name, keyword, keyword_type, search_term, spend, sales, impressions, clicks, orders",
        query_filters,
    )

    groups: dict[str, dict[str, Any]] = {}
    label_meta: dict[str, dict[str, Any]] = {}

    for fact in facts:
        if not isinstance(fact, dict):
            continue

        report_date_value = str(fact.get("report_date") or "").strip()
        campaign_name_value = str(fact.get("campaign_name") or "").strip() or "(unnamed)"
        search_term_value = str(fact.get("search_term") or "").strip() or "(blank)"
        keyword_value = str(fact.get("keyword") or "").strip() or "(blank)"
        keyword_type_value = str(fact.get("keyword_type") or "").strip() or "unclassified"

        if group_by == "day":
            key = report_date_value
            label_meta[key] = {"date": report_date_value}
        elif group_by == "campaign":
            key = campaign_name_value
            label_meta[key] = {"campaign_name": campaign_name_value}
        elif group_by == "keyword":
            key = keyword_value
            label_meta[key] = {
                "keyword": keyword_value,
                "keyword_type": keyword_type_value if keyword_type_value != "unclassified" else None,
            }
        elif group_by == "keyword_type":
            key = keyword_type_value
            label_meta[key] = {"keyword_type": keyword_type_value}
        else:
            key = search_term_value
            label_meta[key] = {"search_term": search_term_value}

        groups.setdefault(key, {})
        _acc_metrics(groups[key], fact, accumulator_metrics)

    totals_acc: dict[str, Any] = {}
    for acc in groups.values():
        _acc_metrics(totals_acc, acc, accumulator_metrics)

    if group_by == "day":
        output_rows: list[dict[str, Any]] = [
            {
                **label_meta[key],
                **_fmt_metrics(groups[key], effective_metrics),
                **_search_term_rank_metrics(groups[key]),
            }
            for key in sorted(groups)
        ]
    else:
        sorted_keys = sorted(
            groups,
            key=lambda key: _search_term_sort_key(groups[key], sort_by, str(key)),
        )
        output_rows = [
            {
                **label_meta[key],
                **_fmt_metrics(groups[key], effective_metrics),
                **_search_term_rank_metrics(groups[key]),
            }
            for key in sorted_keys
        ]

    truncated = len(output_rows) > limit
    if truncated:
        output_rows = output_rows[:limit]

    search_term_latest_date_str = _latest_available_date(db, "search_term_daily_facts", profile_id)
    search_term_latest_date = (
        date.fromisoformat(search_term_latest_date_str) if search_term_latest_date_str else None
    )
    freshness_note = (
        f"Requested end date {date_to} has no landed search-term data yet. "
        f"Latest available: {search_term_latest_date_str}."
        if search_term_latest_date and to_date > search_term_latest_date
        else None
    )

    warnings: list[str] = []
    if truncated:
        warnings.append(
            f"Result truncated to {limit} rows. Add filters or narrow the date range to inspect more groups."
        )

    return {
        "profile_id": profile_id,
        "date_from": date_from,
        "date_to": date_to,
        "group_by": group_by,
        "metrics": effective_metrics,
        "sort_by": sort_by,
        "rows": output_rows,
        "totals": {
            **_fmt_metrics(totals_acc, effective_metrics),
            **_search_term_rank_metrics(totals_acc),
        },
        "row_count": len(output_rows),
        "truncated": truncated,
        "freshness": {
            "latest_available_date": search_term_latest_date_str,
            "note": freshness_note,
        },
        "warnings": warnings,
    }


def query_search_term_facts(
    db: Any,
    profile_id: str,
    date_from: str,
    date_to: str,
    group_by: str,
    *,
    ad_product: str | None = None,
    campaign_type: str | None = None,
    keyword_type: str | None = None,
    match_type: str | None = None,
    campaign_name_contains: str | None = None,
    search_term_contains: str | None = None,
    keyword_contains: str | None = None,
    row_id: str | None = None,
    metrics: list[str] | None = None,
    sort_by: str = "spend",
    limit: int = MAX_RESULT_ROWS,
) -> dict[str, Any]:
    """Flexible STR drill-down grouped by day, search term, keyword, campaign, or keyword type."""
    _get_profile(db, profile_id)
    from_date, to_date = _validate_date_window(date_from, date_to)

    group_by = str(group_by or "").strip().lower()
    if group_by not in _ALLOWED_SEARCH_TERM_GROUP_BY:
        raise AnalystQueryError(
            "validation_error",
            f"group_by must be one of {sorted(_ALLOWED_SEARCH_TERM_GROUP_BY)}. Got '{group_by}'.",
        )

    effective_metrics = list(_DEFAULT_SEARCH_TERM_METRICS)
    if metrics is not None:
        bad = [m for m in metrics if m not in _ALLOWED_SEARCH_TERM_METRICS]
        if bad:
            raise AnalystQueryError(
                "validation_error",
                f"Unknown metric(s): {bad}. Allowed: {sorted(_ALLOWED_SEARCH_TERM_METRICS)}.",
            )
        effective_metrics = [m for m in metrics if m] or list(_DEFAULT_SEARCH_TERM_METRICS)

    sort_by = str(sort_by or "spend").strip().lower()
    if sort_by not in _ALLOWED_SEARCH_TERM_SORT_BY:
        raise AnalystQueryError(
            "validation_error",
            f"sort_by must be one of {sorted(_ALLOWED_SEARCH_TERM_SORT_BY)}. Got '{sort_by}'.",
        )

    limit = min(max(1, int(limit)), MAX_RESULT_ROWS)

    scoped_campaigns: set[str] = (
        _campaign_set_for_row(db, profile_id, row_id) if row_id else set()
    )
    if row_id and not scoped_campaigns:
        return _empty_search_term_facts_result(
            profile_id, date_from, date_to, group_by, effective_metrics, sort_by
        )

    if not hasattr(db, "rpc"):
        return _query_search_term_facts_python(
            db,
            profile_id,
            date_from,
            date_to,
            group_by,
            ad_product=ad_product,
            campaign_type=campaign_type,
            keyword_type=keyword_type,
            match_type=match_type,
            campaign_name_contains=campaign_name_contains,
            search_term_contains=search_term_contains,
            keyword_contains=keyword_contains,
            row_id=row_id,
            metrics=effective_metrics,
            sort_by=sort_by,
            limit=limit,
        )

    rpc_payload = {
        "p_profile_id": profile_id,
        "p_date_from": from_date.isoformat(),
        "p_date_to": to_date.isoformat(),
        "p_group_by": group_by,
        "p_ad_product": str(ad_product or "").strip() or None,
        "p_campaign_type": str(campaign_type or "").strip() or None,
        "p_keyword_type": str(keyword_type or "").strip() or None,
        "p_match_type": str(match_type or "").strip() or None,
        "p_campaign_name_contains": str(campaign_name_contains or "").strip() or None,
        "p_search_term_contains": str(search_term_contains or "").strip() or None,
        "p_keyword_contains": str(keyword_contains or "").strip() or None,
        "p_campaign_names": sorted(scoped_campaigns) if scoped_campaigns else None,
        "p_sort_by": sort_by,
        "p_limit": limit,
    }

    try:
        response = db.rpc("query_search_term_facts_ranked", rpc_payload).execute()
        rpc_rows = response.data if isinstance(response.data, list) else []
    except Exception:
        return _query_search_term_facts_python(
            db,
            profile_id,
            date_from,
            date_to,
            group_by,
            ad_product=ad_product,
            campaign_type=campaign_type,
            keyword_type=keyword_type,
            match_type=match_type,
            campaign_name_contains=campaign_name_contains,
            search_term_contains=search_term_contains,
            keyword_contains=keyword_contains,
            row_id=row_id,
            metrics=effective_metrics,
            sort_by=sort_by,
            limit=limit,
        )

    output_rows: list[dict[str, Any]] = []
    for row in rpc_rows:
        if not isinstance(row, dict):
            continue

        grouped_row: dict[str, Any] = {}
        group_value = str(row.get("group_value") or "").strip()
        if group_by == "day":
            grouped_row["date"] = group_value
        elif group_by == "campaign":
            grouped_row["campaign_name"] = group_value
        elif group_by == "keyword":
            grouped_row["keyword"] = group_value
            grouped_row["keyword_type"] = str(row.get("keyword_type_label") or "").strip() or None
        elif group_by == "keyword_type":
            grouped_row["keyword_type"] = group_value
        else:
            grouped_row["search_term"] = group_value

        for metric in effective_metrics:
            if metric in _DECIMAL_METRICS:
                grouped_row[metric] = _quantize_decimal(Decimal(str(row.get(metric) or "0")), "0.01")
            else:
                grouped_row[metric] = int(row.get(metric) or 0)

        grouped_row.update(
            {
                "acos": _fmt_ratio(
                    Decimal(str(row["acos"])) if row.get("acos") is not None else None
                ),
                "roas": _fmt_ratio(
                    Decimal(str(row["roas"])) if row.get("roas") is not None else None
                ),
                "ctr": _fmt_ratio(
                    Decimal(str(row["ctr"])) if row.get("ctr") is not None else None
                ),
                "cvr": _fmt_ratio(
                    Decimal(str(row["cvr"])) if row.get("cvr") is not None else None
                ),
                "cpc": _fmt_ratio(
                    Decimal(str(row["cpc"])) if row.get("cpc") is not None else None
                ),
            }
        )
        output_rows.append(grouped_row)

    first_row = rpc_rows[0] if rpc_rows and isinstance(rpc_rows[0], dict) else {}
    total_group_count = int(first_row.get("total_group_count") or 0) if first_row else 0
    truncated = total_group_count > len(output_rows)

    search_term_latest_date_str = _latest_available_date(db, "search_term_daily_facts", profile_id)
    search_term_latest_date = (
        date.fromisoformat(search_term_latest_date_str) if search_term_latest_date_str else None
    )
    freshness_note = (
        f"Requested end date {date_to} has no landed search-term data yet. "
        f"Latest available: {search_term_latest_date_str}."
        if search_term_latest_date and to_date > search_term_latest_date
        else None
    )

    warnings: list[str] = []
    if truncated:
        warnings.append(
            f"Result truncated to {limit} rows. Add filters or narrow the date range to inspect more groups."
        )

    return {
        "profile_id": profile_id,
        "date_from": date_from,
        "date_to": date_to,
        "group_by": group_by,
        "metrics": effective_metrics,
        "sort_by": sort_by,
        "rows": output_rows,
        "totals": {
            **{
                metric: (
                    _quantize_decimal(Decimal(str(first_row.get(f"total_{metric}") or "0")), "0.01")
                    if metric in _DECIMAL_METRICS
                    else int(first_row.get(f"total_{metric}") or 0)
                )
                for metric in effective_metrics
            },
            "acos": _fmt_ratio(
                _safe_ratio(first_row.get("total_spend"), first_row.get("total_sales"))
            ),
            "roas": _fmt_ratio(
                _safe_ratio(first_row.get("total_sales"), first_row.get("total_spend"))
            ),
            "ctr": _fmt_ratio(
                _safe_ratio(first_row.get("total_clicks"), first_row.get("total_impressions"))
            ),
            "cvr": _fmt_ratio(
                _safe_ratio(first_row.get("total_orders"), first_row.get("total_clicks"))
            ),
            "cpc": _fmt_ratio(
                _safe_ratio(first_row.get("total_spend"), first_row.get("total_clicks"))
            ),
        },
        "row_count": len(output_rows),
        "truncated": truncated,
        "freshness": {
            "latest_available_date": search_term_latest_date_str,
            "note": freshness_note,
        },
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# query_catalog_context
# ---------------------------------------------------------------------------


def query_catalog_context(
    db: Any,
    profile_id: str,
    *,
    child_asins: list[str] | None = None,
    row_id: str | None = None,
) -> dict[str, Any]:
    """Return product catalog detail for child ASINs in a WBR profile: title, SKU, category, size, and fulfillment method.

    Pass child_asins to look up specific ASINs, row_id to expand a WBR row to
    its constituent products, or omit both to retrieve the full profile catalog.
    """
    _get_profile(db, profile_id)

    explicit_asins: set[str] = {
        str(a or "").strip().upper() for a in (child_asins or []) if str(a or "").strip()
    }
    row_asins: set[str] = _asin_set_for_row(db, profile_id, row_id) if row_id else set()
    all_asins = explicit_asins | row_asins
    # If a row_id was given but resolved to no ASINs and no explicit ASINs were
    # provided, return empty rather than falling through to a profile-wide query.
    if row_id and not all_asins:
        return {"profile_id": profile_id, "child_asins": [], "total": 0, "truncated": False}

    if all_asins and len(all_asins) > MAX_ASIN_COUNT:
        raise AnalystQueryError(
            "validation_error",
            f"Resolved {len(all_asins)} ASINs exceeds limit of {MAX_ASIN_COUNT}.",
        )

    query_filters: list[tuple[str, str, Any]] = [
        ("eq", "profile_id", profile_id),
        ("eq", "active", True),
    ]
    if all_asins:
        query_filters.append(("in_", "child_asin", sorted(all_asins)))

    catalog_rows = _select_all(db, "wbr_profile_child_asins", "*", query_filters)

    def _s(v: Any) -> str | None:
        s = str(v or "").strip()
        return s or None

    result_rows = sorted(
        [
            {
                "child_asin": str(r.get("child_asin") or "").strip().upper(),
                "parent_asin": _s(r.get("parent_asin")),
                "child_sku": _s(r.get("child_sku")),
                "child_product_name": _s(r.get("child_product_name")),
                "parent_title": _s(r.get("parent_title")),
                "category": _s(r.get("category")),
                "size": _s(r.get("size")),
                "source_item_style": _s(r.get("source_item_style")),
                "fulfillment_method": _s(r.get("fulfillment_method")),
            }
            for r in catalog_rows
            if isinstance(r, dict) and str(r.get("child_asin") or "").strip()
        ],
        key=lambda row: (
            str(row.get("child_product_name") or "").lower(),
            str(row.get("child_asin") or "").lower(),
        ),
    )

    truncated = len(result_rows) > MAX_RESULT_ROWS
    if truncated:
        result_rows = result_rows[:MAX_RESULT_ROWS]

    return {
        "profile_id": profile_id,
        "child_asins": result_rows,
        "total": len(result_rows),
        "truncated": truncated,
    }


# ---------------------------------------------------------------------------
# query_monthly_pnl_detail — Slice 3
# ---------------------------------------------------------------------------

MAX_PNL_MONTHS = 24
MAX_PNL_RESULT_ROWS = 50

_ALLOWED_PNL_GROUP_BY = frozenset({"line_item", "month"})
_ALLOWED_PNL_SECTIONS = frozenset({"revenue", "refunds", "cogs", "expenses", "summary"})

# section → category values present in PNLReportService line_items
_PNL_SECTION_CATEGORIES: dict[str, frozenset[str]] = {
    "revenue": frozenset({"revenue"}),
    "refunds": frozenset({"refunds"}),
    "cogs": frozenset({"cogs"}),
    "expenses": frozenset({"expenses"}),
    "summary": frozenset({"summary", "bottom_line"}),
}

# Canonical summary line keys surfaced for group_by="month" and always in totals
_PNL_SUMMARY_KEYS: tuple[str, ...] = (
    "total_net_revenue",
    "gross_profit",
    "total_expenses",
    "net_earnings",
)


def _parse_pnl_month(value: str) -> str:
    """Accept YYYY-MM or YYYY-MM-01 and return YYYY-MM-01."""
    s = str(value or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}", s):
        return f"{s}-01"
    if re.fullmatch(r"\d{4}-\d{2}-01", s):
        return s
    raise AnalystQueryError(
        "validation_error",
        f"Invalid month format '{value}'. Expected YYYY-MM.",
    )


def _pnl_month_range(start_iso: str, end_iso: str) -> list[str]:
    """Return list of YYYY-MM-01 strings from start to end inclusive."""
    start = date.fromisoformat(start_iso)
    end = date.fromisoformat(end_iso)
    months: list[str] = []
    y, m = start.year, start.month
    while date(y, m, 1) <= end:
        months.append(date(y, m, 1).isoformat())
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def _pnl_canonical_totals(line_items: list[dict[str, Any]]) -> dict[str, str]:
    """Extract canonical P&L period totals from all months of given line_items."""
    item_by_key = {
        str(item.get("key") or ""): item
        for item in line_items
        if isinstance(item, dict)
    }
    totals: dict[str, str] = {}
    for key in _PNL_SUMMARY_KEYS:
        item = item_by_key.get(key)
        amt = (
            sum(Decimal(str(v or "0")) for v in (item.get("months") or {}).values())
            if item
            else Decimal("0")
        )
        totals[key] = format(amt.quantize(Decimal("0.01")), "f")
    return totals


def _format_pnl_by_line_item(
    profile_id: str,
    period_months: list[str],
    currency_code: str | None,
    section: str | None,
    line_items: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    limit: int,
) -> dict[str, Any]:
    allowed_cats = _PNL_SECTION_CATEGORIES.get(section) if section else None
    rows_acc: list[dict[str, Any]] = []
    for item in line_items:
        if not isinstance(item, dict):
            continue
        cat = str(item.get("category") or "").strip()
        if allowed_cats is not None and cat not in allowed_cats:
            continue
        months_data = item.get("months") or {}
        total = sum(Decimal(str(v or "0")) for v in months_data.values())
        rows_acc.append(
            {
                "key": str(item.get("key") or ""),
                "label": str(item.get("label") or ""),
                "category": cat,
                "is_derived": bool(item.get("is_derived")),
                "amount": format(total.quantize(Decimal("0.01")), "f"),
            }
        )

    totals = _pnl_canonical_totals(line_items)
    truncated = len(rows_acc) > limit
    if truncated:
        rows_acc = rows_acc[:limit]

    return {
        "profile_id": profile_id,
        "period_months": period_months,
        "currency_code": currency_code,
        "section": section,
        "group_by": "line_item",
        "rows": rows_acc,
        "totals": totals,
        "row_count": len(rows_acc),
        "truncated": truncated,
        "warnings": warnings,
    }


def _format_pnl_by_month(
    profile_id: str,
    period_months: list[str],
    currency_code: str | None,
    line_items: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    limit: int,
) -> dict[str, Any]:
    item_by_key = {
        str(item.get("key") or ""): item
        for item in line_items
        if isinstance(item, dict)
    }
    totals_acc: dict[str, Decimal] = {k: Decimal("0") for k in _PNL_SUMMARY_KEYS}
    rows_out: list[dict[str, Any]] = []

    for month in period_months:
        row: dict[str, Any] = {"month": month}
        for key in _PNL_SUMMARY_KEYS:
            item = item_by_key.get(key)
            amt = (
                Decimal(str((item.get("months") or {}).get(month) or "0"))
                if item
                else Decimal("0")
            )
            row[key] = format(amt.quantize(Decimal("0.01")), "f")
            totals_acc[key] += amt
        rows_out.append(row)

    totals = {k: format(v.quantize(Decimal("0.01")), "f") for k, v in totals_acc.items()}
    truncated = len(rows_out) > limit
    if truncated:
        rows_out = rows_out[:limit]

    return {
        "profile_id": profile_id,
        "period_months": period_months,
        "currency_code": currency_code,
        "section": None,  # section is not meaningful for month grouping
        "group_by": "month",
        "rows": rows_out,
        "totals": totals,
        "row_count": len(rows_out),
        "truncated": truncated,
        "warnings": warnings,
    }


async def query_monthly_pnl_detail(
    db: Any,
    profile_id: str,
    *,
    year_month: str | None = None,
    month_from: str | None = None,
    month_to: str | None = None,
    section: str | None = None,
    group_by: str = "line_item",
    limit: int = MAX_PNL_RESULT_ROWS,
) -> dict[str, Any]:
    """Bounded Monthly P&L drill-down for ad hoc analyst questions.

    Delegates to PNLReportService — no second calculation engine.
    Pass year_month for a single month or month_from + month_to for a range
    (max MAX_PNL_MONTHS months).
    """
    # Profile validation
    try:
        profile = PNLProfileService(db).get_profile(profile_id)
    except PNLNotFoundError as exc:
        raise AnalystQueryError("not_found", str(exc)) from exc

    # Parameter validation
    group_by = str(group_by or "").strip().lower()
    if group_by not in _ALLOWED_PNL_GROUP_BY:
        raise AnalystQueryError(
            "validation_error",
            f"group_by must be one of {sorted(_ALLOWED_PNL_GROUP_BY)}. Got '{group_by}'.",
        )

    if section is not None:
        section = str(section or "").strip().lower()
        if section not in _ALLOWED_PNL_SECTIONS:
            raise AnalystQueryError(
                "validation_error",
                f"section must be one of {sorted(_ALLOWED_PNL_SECTIONS)}. Got '{section}'.",
            )
        if group_by == "month":
            raise AnalystQueryError(
                "validation_error",
                "section is only supported when group_by='line_item'.",
            )

    has_year_month = year_month is not None
    has_range = month_from is not None or month_to is not None
    if has_year_month and has_range:
        raise AnalystQueryError(
            "validation_error",
            "Provide year_month for a single month, or month_from + month_to for a "
            "range, not both.",
        )
    if not has_year_month and not has_range:
        raise AnalystQueryError(
            "validation_error",
            "Provide year_month (single month) or both month_from and month_to.",
        )
    if has_range and (month_from is None or month_to is None):
        raise AnalystQueryError(
            "validation_error",
            "Both month_from and month_to are required for a range query.",
        )

    if has_year_month:
        start_month_iso = _parse_pnl_month(year_month)  # type: ignore[arg-type]
        end_month_iso = start_month_iso
    else:
        start_month_iso = _parse_pnl_month(month_from)  # type: ignore[arg-type]
        end_month_iso = _parse_pnl_month(month_to)  # type: ignore[arg-type]
        if start_month_iso > end_month_iso:
            raise AnalystQueryError(
                "validation_error",
                f"month_from ({month_from}) must not be after month_to ({month_to}).",
            )
        n_months = len(_pnl_month_range(start_month_iso, end_month_iso))
        if n_months > MAX_PNL_MONTHS:
            raise AnalystQueryError(
                "validation_error",
                f"Month range is {n_months} months. Limit is {MAX_PNL_MONTHS}.",
            )

    limit = min(max(1, int(limit)), MAX_PNL_RESULT_ROWS)

    # Build report via the existing P&L engine.
    try:
        report = await PNLReportService(db).build_report_async(
            profile_id,
            filter_mode="range",
            start_month=start_month_iso,
            end_month=end_month_iso,
        )
    except PNLNotFoundError as exc:
        raise AnalystQueryError("not_found", str(exc)) from exc
    except PNLValidationError as exc:
        raise AnalystQueryError("validation_error", str(exc)) from exc

    period_months = list(report.get("months") or [])
    line_items = list(report.get("line_items") or [])
    warnings = list(report.get("warnings") or [])
    currency_code = str(profile.get("currency_code") or "").strip().upper() or None

    if group_by == "month":
        return _format_pnl_by_month(
            profile_id, period_months, currency_code, line_items, warnings, limit
        )
    return _format_pnl_by_line_item(
        profile_id, period_months, currency_code, section, line_items, warnings, limit
    )
