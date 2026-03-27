from __future__ import annotations

from typing import Any

from supabase import Client

_SELECT_COLUMNS = (
    "id,report_date,campaign_type,campaign_name,campaign_name_head,"
    "ad_group_name,keyword_id,keyword,keyword_type,targeting,"
    "search_term,match_type,impressions,clicks,spend,"
    "orders,sales,currency_code"
)

_DEFAULT_LIMIT = 500
_MAX_LIMIT = 2000


class SearchTermFactsService:
    def __init__(self, db: Client) -> None:
        self.db = db

    def list_facts(
        self,
        profile_id: str,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        campaign_type: str | None = None,
        campaign_name_contains: str | None = None,
        search_term_contains: str | None = None,
        limit: int = _DEFAULT_LIMIT,
        offset: int = 0,
    ) -> dict[str, Any]:
        limit = max(1, min(limit, _MAX_LIMIT))
        fetch_limit = limit + 1  # extra row to detect has_more

        query = (
            self.db.table("search_term_daily_facts")
            .select(_SELECT_COLUMNS)
            .eq("profile_id", profile_id)
            .order("report_date", desc=True)
            .order("campaign_name")
            .order("search_term")
        )

        if date_from:
            query = query.gte("report_date", date_from)
        if date_to:
            query = query.lte("report_date", date_to)
        if campaign_type:
            query = query.eq("campaign_type", campaign_type)
        if campaign_name_contains:
            query = query.ilike("campaign_name", f"%{campaign_name_contains}%")
        if search_term_contains:
            query = query.ilike("search_term", f"%{search_term_contains}%")

        query = query.range(offset, offset + fetch_limit - 1)
        resp = query.execute()
        rows: list[dict[str, Any]] = resp.data if isinstance(resp.data, list) else []

        has_more = len(rows) > limit
        return {
            "facts": rows[:limit],
            "limit": limit,
            "offset": offset,
            "has_more": has_more,
        }
