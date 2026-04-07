"""Analyst-query MCP tools — read-only (Slice 0 + Slice 1).

Wrappers are thin: input is forwarded to the service layer, errors are
caught and returned as structured dicts so Claude can read the failure
reason rather than seeing a server error.
"""

from __future__ import annotations

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
    query_search_term_facts as _query_search_term_facts,
)
from ..auth import get_current_pilot_user
from ..event_logging import start_mcp_tool_invocation


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
        invocation = start_mcp_tool_invocation("get_asin_sales_window", is_mutation=False)
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
            invocation.error(
                error_type=exc.error_type,
                profile_id=profile_id,
                asin_count=len(child_asins),
            )
            return {"error": exc.error_type, "message": exc.message}
        invocation.success(
            profile_id=profile_id,
            asin_count=len(result.get("asins", [])),
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
        invocation = start_mcp_tool_invocation("list_child_asins_for_row", is_mutation=False)
        db = _get_supabase_admin_client()
        try:
            result = _list_child_asins_for_row(db, profile_id, row_id)
        except AnalystQueryError as exc:
            invocation.error(error_type=exc.error_type, profile_id=profile_id, row_id=row_id)
            return {"error": exc.error_type, "message": exc.message}
        invocation.success(profile_id=profile_id, row_id=row_id, result_count=result.get("total", 0))
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
        invocation = start_mcp_tool_invocation("get_sync_freshness_status", is_mutation=False)
        db = _get_supabase_admin_client()
        try:
            result = _get_sync_freshness_status(db, profile_id)
        except AnalystQueryError as exc:
            invocation.error(error_type=exc.error_type, profile_id=profile_id)
            return {"error": exc.error_type, "message": exc.message}
        invocation.success(profile_id=profile_id)
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
        invocation = start_mcp_tool_invocation("query_business_facts", is_mutation=False)
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
            invocation.error(
                error_type=exc.error_type,
                profile_id=profile_id,
                group_by=group_by,
                row_id=row_id,
                child_asin_count=len(child_asins or []),
                limit=limit,
            )
            return {"error": exc.error_type, "message": exc.message}
        invocation.success(
            profile_id=profile_id,
            group_by=group_by,
            row_count=result.get("row_count", 0),
            row_id=row_id,
            child_asin_count=len(child_asins or []),
            limit=limit,
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
        invocation = start_mcp_tool_invocation("query_ads_facts", is_mutation=False)
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
            invocation.error(
                error_type=exc.error_type,
                profile_id=profile_id,
                group_by=group_by,
                row_id=row_id,
                campaign_count=len(campaign_names or []),
                limit=limit,
            )
            return {"error": exc.error_type, "message": exc.message}
        invocation.success(
            profile_id=profile_id,
            group_by=group_by,
            row_count=result.get("row_count", 0),
            row_id=row_id,
            campaign_count=len(campaign_names or []),
            limit=limit,
        )
        return result

    @mcp.tool(
        name="query_search_term_facts",
        description=(
            "Flexible drill-down over ingested Amazon Ads search-term facts. "
            "group_by: 'day' | 'search_term' | 'keyword' | 'campaign' | 'keyword_type'. "
            "Use this for bounded keyword or search-term ranking questions after resolving a WBR profile. "
            "Supports read-only filters like ad product, campaign type, row scope, and contains filters."
        ),
        structured_output=True,
    )
    def query_search_term_facts(
        profile_id: str,
        date_from: str,
        date_to: str,
        group_by: str,
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
        limit: int = 25,
    ) -> dict[str, Any]:
        invocation = start_mcp_tool_invocation("query_search_term_facts", is_mutation=False)
        db = _get_supabase_admin_client()
        try:
            result = _query_search_term_facts(
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
                metrics=metrics,
                sort_by=sort_by,
                limit=limit,
            )
        except AnalystQueryError as exc:
            invocation.error(
                error_type=exc.error_type,
                profile_id=profile_id,
                group_by=group_by,
                sort_by=sort_by,
                row_id=row_id,
                limit=limit,
                ad_product=ad_product,
                campaign_type=campaign_type,
                keyword_type=keyword_type,
                match_type=match_type,
            )
            return {"error": exc.error_type, "message": exc.message}
        invocation.success(
            profile_id=profile_id,
            group_by=group_by,
            sort_by=sort_by,
            row_id=row_id,
            limit=limit,
            ad_product=ad_product,
            campaign_type=campaign_type,
            keyword_type=keyword_type,
            match_type=match_type,
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
        invocation = start_mcp_tool_invocation("query_catalog_context", is_mutation=False)
        db = _get_supabase_admin_client()
        try:
            result = _query_catalog_context(
                db,
                profile_id,
                child_asins=child_asins,
                row_id=row_id,
            )
        except AnalystQueryError as exc:
            invocation.error(
                error_type=exc.error_type,
                profile_id=profile_id,
                row_id=row_id,
                child_asin_count=len(child_asins or []),
            )
            return {"error": exc.error_type, "message": exc.message}
        invocation.success(
            profile_id=profile_id,
            row_id=row_id,
            child_asin_count=len(child_asins or []),
            result_count=result.get("total", 0),
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
        invocation = start_mcp_tool_invocation("query_monthly_pnl_detail", is_mutation=False)
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
            invocation.error(
                error_type=exc.error_type,
                profile_id=profile_id,
                group_by=group_by,
                year_month=year_month,
                month_from=month_from,
                month_to=month_to,
                section=section,
                limit=limit,
            )
            return {"error": exc.error_type, "message": exc.message}
        invocation.success(
            profile_id=profile_id,
            group_by=group_by,
            year_month=year_month,
            month_from=month_from,
            month_to=month_to,
            section=section,
            row_count=result.get("row_count", 0),
        )
        return result
