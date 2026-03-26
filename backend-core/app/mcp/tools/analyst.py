"""Analyst-query MCP tools — read-only (Slice 0 + Slice 1).

Wrappers are thin: input is forwarded to the service layer, errors are
caught and returned as structured dicts so Claude can read the failure
reason rather than seeing a server error.
"""

from __future__ import annotations

import logging
from typing import Any

from ...auth import _get_supabase_admin_client
from ...services.analyst_query_tools import (
    AnalystQueryError,
    get_asin_sales_window as _get_asin_sales_window,
    get_sync_freshness_status as _get_sync_freshness_status,
    list_child_asins_for_row as _list_child_asins_for_row,
    query_ads_facts as _query_ads_facts,
    query_business_facts as _query_business_facts,
    query_catalog_context as _query_catalog_context,
    query_monthly_pnl_detail as _query_monthly_pnl_detail,
)
from ..auth import get_current_pilot_user

_logger = logging.getLogger(__name__)


def _log_tool_outcome(tool_name: str, outcome: str, **extra: Any) -> None:
    user = get_current_pilot_user()
    suffix = " ".join(f"{key}={value}" for key, value in extra.items())
    if suffix:
        suffix = f" {suffix}"
    _logger.info(
        "MCP tool invocation | tool=%s user_id=%s outcome=%s%s",
        tool_name,
        user.user_id if user else None,
        outcome,
        suffix,
    )


def register_analyst_tools(mcp: Any) -> None:
    @mcp.tool(
        name="get_asin_sales_window",
        description=(
            "Return per-ASIN sales totals (units, revenue, page views) for one or "
            "more child ASINs over a date window in a WBR profile. Includes freshness "
            "metadata and a note when the requested end date has no landed data yet. "
            "Use after list_wbr_profiles to get profile_id."
        ),
        structured_output=True,
    )
    def get_asin_sales_window(
        profile_id: str,
        child_asins: list[str],
        date_from: str,
        date_to: str,
        include_latest_available: bool = True,
    ) -> dict[str, Any]:
        _log_tool_outcome("get_asin_sales_window", "started", profile_id=profile_id)
        db = _get_supabase_admin_client()
        try:
            result = _get_asin_sales_window(
                db,
                profile_id,
                child_asins,
                date_from,
                date_to,
                include_latest_available=include_latest_available,
            )
        except AnalystQueryError as exc:
            _log_tool_outcome("get_asin_sales_window", "error", error=str(exc))
            return {"error": exc.error_type, "message": exc.message}
        _log_tool_outcome(
            "get_asin_sales_window",
            "success",
            profile_id=profile_id,
            asins=len(result.get("asins", [])),
        )
        return result

    @mcp.tool(
        name="list_child_asins_for_row",
        description=(
            "List child ASINs mapped to a WBR row, with product title, SKU, category, "
            "and scope status (included/excluded). Use to answer row-composition "
            "questions such as 'What products make up this WBR line?'"
        ),
        structured_output=True,
    )
    def list_child_asins_for_row(
        profile_id: str,
        row_id: str,
    ) -> dict[str, Any]:
        _log_tool_outcome(
            "list_child_asins_for_row", "started", profile_id=profile_id, row_id=row_id
        )
        db = _get_supabase_admin_client()
        try:
            result = _list_child_asins_for_row(db, profile_id, row_id)
        except AnalystQueryError as exc:
            _log_tool_outcome("list_child_asins_for_row", "error", error=str(exc))
            return {"error": exc.error_type, "message": exc.message}
        _log_tool_outcome(
            "list_child_asins_for_row",
            "success",
            profile_id=profile_id,
            total=result.get("total", 0),
        )
        return result

    @mcp.tool(
        name="get_sync_freshness_status",
        description=(
            "Return sync freshness status for a WBR profile: latest Windsor business "
            "sync, latest Amazon Ads sync, latest available fact dates, and warnings "
            "when data may be incomplete or delayed. Call this when the user asks "
            "whether data is current or why a date is missing."
        ),
        structured_output=True,
    )
    def get_sync_freshness_status(profile_id: str) -> dict[str, Any]:
        _log_tool_outcome("get_sync_freshness_status", "started", profile_id=profile_id)
        db = _get_supabase_admin_client()
        try:
            result = _get_sync_freshness_status(db, profile_id)
        except AnalystQueryError as exc:
            _log_tool_outcome("get_sync_freshness_status", "error", error=str(exc))
            return {"error": exc.error_type, "message": exc.message}
        _log_tool_outcome("get_sync_freshness_status", "success", profile_id=profile_id)
        return result

    @mcp.tool(
        name="query_business_facts",
        description=(
            "Flexible drill-down over Windsor/WBR business facts (units, sales, page views). "
            "group_by: 'day' | 'child_asin' | 'row'. "
            "Pass child_asins or row_id to scope the query; omit both for all profile facts. "
            "row_id resolves parent rows to their active descendant ASINs. "
            "Returns grouped rows, totals, freshness metadata, and a truncation flag. "
            "Use after list_wbr_profiles to get profile_id."
        ),
        structured_output=True,
    )
    def query_business_facts(
        profile_id: str,
        date_from: str,
        date_to: str,
        group_by: str,
        child_asins: list[str] | None = None,
        row_id: str | None = None,
        metrics: list[str] | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        _log_tool_outcome("query_business_facts", "started", profile_id=profile_id)
        db = _get_supabase_admin_client()
        try:
            result = _query_business_facts(
                db,
                profile_id,
                date_from,
                date_to,
                group_by,
                child_asins=child_asins,
                row_id=row_id,
                metrics=metrics,
                limit=limit,
            )
        except AnalystQueryError as exc:
            _log_tool_outcome("query_business_facts", "error", error=str(exc))
            return {"error": exc.error_type, "message": exc.message}
        _log_tool_outcome(
            "query_business_facts",
            "success",
            profile_id=profile_id,
            row_count=result.get("row_count", 0),
        )
        return result

    @mcp.tool(
        name="query_ads_facts",
        description=(
            "Flexible drill-down over Amazon Ads campaign facts (spend, sales, "
            "impressions, clicks, orders). "
            "group_by: 'day' | 'campaign' | 'campaign_type' | 'row'. "
            "Pass campaign_names or row_id to scope the query; omit both for all profile ad facts. "
            "Campaign results are sorted by spend descending. "
            "Returns grouped rows, totals, freshness metadata, and a truncation flag. "
            "Use after list_wbr_profiles to get profile_id."
        ),
        structured_output=True,
    )
    def query_ads_facts(
        profile_id: str,
        date_from: str,
        date_to: str,
        group_by: str,
        campaign_names: list[str] | None = None,
        row_id: str | None = None,
        metrics: list[str] | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        _log_tool_outcome("query_ads_facts", "started", profile_id=profile_id)
        db = _get_supabase_admin_client()
        try:
            result = _query_ads_facts(
                db,
                profile_id,
                date_from,
                date_to,
                group_by,
                campaign_names=campaign_names,
                row_id=row_id,
                metrics=metrics,
                limit=limit,
            )
        except AnalystQueryError as exc:
            _log_tool_outcome("query_ads_facts", "error", error=str(exc))
            return {"error": exc.error_type, "message": exc.message}
        _log_tool_outcome(
            "query_ads_facts",
            "success",
            profile_id=profile_id,
            row_count=result.get("row_count", 0),
        )
        return result

    @mcp.tool(
        name="query_catalog_context",
        description=(
            "Return product catalog detail for child ASINs in a WBR profile: "
            "title, SKU, category, size, and fulfillment method. "
            "Pass child_asins to look up specific ASINs, row_id to expand a WBR row "
            "to its constituent products, or omit both for the full profile catalog. "
            "row_id resolves parent rows to their active descendant ASINs. "
            "Use after list_wbr_profiles to get profile_id."
        ),
        structured_output=True,
    )
    def query_catalog_context(
        profile_id: str,
        child_asins: list[str] | None = None,
        row_id: str | None = None,
    ) -> dict[str, Any]:
        _log_tool_outcome("query_catalog_context", "started", profile_id=profile_id)
        db = _get_supabase_admin_client()
        try:
            result = _query_catalog_context(
                db,
                profile_id,
                child_asins=child_asins,
                row_id=row_id,
            )
        except AnalystQueryError as exc:
            _log_tool_outcome("query_catalog_context", "error", error=str(exc))
            return {"error": exc.error_type, "message": exc.message}
        _log_tool_outcome(
            "query_catalog_context",
            "success",
            profile_id=profile_id,
            total=result.get("total", 0),
        )
        return result

    @mcp.tool(
        name="query_monthly_pnl_detail",
        description=(
            "Drill into Monthly P&L line items for a profile and period. "
            "group_by: 'line_item' (each P&L row summed across months) or "
            "'month' (net revenue, gross profit, expenses, net earnings per month). "
            "Filter to one section: 'revenue', 'refunds', 'cogs', 'expenses', "
            "or 'summary'. Use list_monthly_pnl_profiles to get profile_id."
        ),
        structured_output=True,
    )
    async def query_monthly_pnl_detail(
        profile_id: str,
        group_by: str = "line_item",
        year_month: str | None = None,
        month_from: str | None = None,
        month_to: str | None = None,
        section: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        _log_tool_outcome("query_monthly_pnl_detail", "started", profile_id=profile_id)
        db = _get_supabase_admin_client()
        try:
            result = await _query_monthly_pnl_detail(
                db,
                profile_id,
                year_month=year_month,
                month_from=month_from,
                month_to=month_to,
                section=section,
                group_by=group_by,
                limit=limit,
            )
        except AnalystQueryError as exc:
            _log_tool_outcome("query_monthly_pnl_detail", "error", error=str(exc))
            return {"error": exc.error_type, "message": exc.message}
        _log_tool_outcome(
            "query_monthly_pnl_detail",
            "success",
            profile_id=profile_id,
            row_count=result.get("row_count", 0),
        )
        return result
