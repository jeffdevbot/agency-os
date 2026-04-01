from __future__ import annotations

import csv
import io

from typing import Any

from supabase import Client

_SELECT_COLUMNS = (
    "id,report_date,ad_product,report_type_id,campaign_type,campaign_name,campaign_name_head,"
    "ad_group_name,keyword_id,keyword,keyword_type,targeting,"
    "search_term,match_type,impressions,clicks,spend,"
    "orders,sales,currency_code"
)

_DEFAULT_LIMIT = 500
_MAX_LIMIT = 2000


class SearchTermFactsService:
    def __init__(self, db: Client) -> None:
        self.db = db

    def _build_query(
        self,
        profile_id: str,
        *,
        ad_product: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        campaign_type: str | None = None,
        campaign_name_contains: str | None = None,
        search_term_contains: str | None = None,
    ):
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
        if ad_product:
            query = query.eq("ad_product", ad_product)
        if campaign_type:
            query = query.eq("campaign_type", campaign_type)
        if campaign_name_contains:
            query = query.ilike("campaign_name", f"%{campaign_name_contains}%")
        if search_term_contains:
            query = query.ilike("search_term", f"%{search_term_contains}%")

        return query

    def list_facts(
        self,
        profile_id: str,
        *,
        ad_product: str | None = None,
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

        query = self._build_query(
            profile_id,
            ad_product=ad_product,
            date_from=date_from,
            date_to=date_to,
            campaign_type=campaign_type,
            campaign_name_contains=campaign_name_contains,
            search_term_contains=search_term_contains,
        )

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

    def export_facts_csv(
        self,
        profile_id: str,
        *,
        ad_product: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        campaign_type: str | None = None,
        campaign_name_contains: str | None = None,
        search_term_contains: str | None = None,
    ) -> str:
        query = self._build_query(
            profile_id,
            ad_product=ad_product,
            date_from=date_from,
            date_to=date_to,
            campaign_type=campaign_type,
            campaign_name_contains=campaign_name_contains,
            search_term_contains=search_term_contains,
        )
        resp = query.execute()
        rows: list[dict[str, Any]] = resp.data if isinstance(resp.data, list) else []

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "report_date",
                "ad_product",
                "report_type_id",
                "campaign_type",
                "campaign_name",
                "campaign_name_head",
                "ad_group_name",
                "keyword_id",
                "keyword",
                "keyword_type",
                "targeting",
                "search_term",
                "match_type",
                "impressions",
                "clicks",
                "spend",
                "orders",
                "sales",
                "currency_code",
            ]
        )

        for row in rows:
            writer.writerow(
                [
                    row.get("report_date"),
                    row.get("ad_product"),
                    row.get("report_type_id"),
                    row.get("campaign_type"),
                    row.get("campaign_name"),
                    row.get("campaign_name_head"),
                    row.get("ad_group_name"),
                    row.get("keyword_id"),
                    row.get("keyword"),
                    row.get("keyword_type"),
                    row.get("targeting"),
                    row.get("search_term"),
                    row.get("match_type"),
                    row.get("impressions"),
                    row.get("clicks"),
                    row.get("spend"),
                    row.get("orders"),
                    row.get("sales"),
                    row.get("currency_code"),
                ]
            )

        return output.getvalue()
