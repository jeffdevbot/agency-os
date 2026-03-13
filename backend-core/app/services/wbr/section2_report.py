from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from supabase import Client

from .profiles import WBRNotFoundError


@dataclass(frozen=True)
class WeekBucket:
    start: date
    end: date
    label: str


def _previous_full_weeks(week_start_day: str, weeks: int) -> list[WeekBucket]:
    if weeks <= 0:
        return []

    today = datetime.now(UTC).date()
    if week_start_day == "monday":
        current_week_start = today - timedelta(days=today.weekday())
    else:
        current_week_start = today - timedelta(days=(today.weekday() + 1) % 7)

    previous_week_end = current_week_start - timedelta(days=1)
    buckets: list[WeekBucket] = []
    for offset in range(weeks):
        end = previous_week_end - timedelta(days=offset * 7)
        start = end - timedelta(days=6)
        buckets.append(
            WeekBucket(
                start=start,
                end=end,
                label=f"{start.strftime('%d-%b')} to {end.strftime('%d-%b')}",
            )
        )
    return list(reversed(buckets))


def _decimal_to_string(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


class Section2ReportService:
    def __init__(self, db: Client) -> None:
        self.db = db

    def build_report(self, profile_id: str, *, weeks: int = 4) -> dict[str, Any]:
        profile = self._get_profile(profile_id)
        week_buckets = _previous_full_weeks(str(profile.get("week_start_day") or "sunday"), weeks)
        if not week_buckets:
            return {
                "profile": profile,
                "weeks": [],
                "rows": [],
                "qa": {
                    "active_row_count": 0,
                    "mapped_campaign_count": 0,
                    "unmapped_campaign_count": 0,
                    "unmapped_fact_rows": 0,
                    "fact_row_count": 0,
                },
            }

        rows = self._list_active_rows(profile_id)
        row_by_id = {str(row["id"]): row for row in rows if row.get("id")}
        leaf_ids = {str(row["id"]) for row in rows if row.get("row_kind") == "leaf"}
        mappings = self._list_active_campaign_mappings(profile_id)
        mapping_by_campaign = {
            str(item["campaign_name"]): str(item["row_id"])
            for item in mappings
            if item.get("campaign_name") and item.get("row_id") and str(item["row_id"]) in leaf_ids
        }
        asin_mappings = self._list_active_asin_mappings(profile_id)
        mapping_by_asin = {
            str(item["child_asin"]).strip().upper(): str(item["row_id"])
            for item in asin_mappings
            if item.get("child_asin") and item.get("row_id") and str(item["row_id"]) in leaf_ids
        }

        facts = self._list_facts(
            profile_id,
            date_from=week_buckets[0].start,
            date_to=week_buckets[-1].end,
        )
        business_facts = self._list_business_facts(
            profile_id,
            date_from=week_buckets[0].start,
            date_to=week_buckets[-1].end,
        )

        week_index_by_date: dict[date, int] = {}
        for index, bucket in enumerate(week_buckets):
            cursor = bucket.start
            while cursor <= bucket.end:
                week_index_by_date[cursor] = index
                cursor += timedelta(days=1)

        leaf_values: dict[str, list[dict[str, Decimal | int]]] = {
            row_id: [
                {
                    "impressions": 0,
                    "clicks": 0,
                    "ad_spend": Decimal("0.00"),
                    "ad_orders": 0,
                    "ad_sales": Decimal("0.00"),
                    "business_sales": Decimal("0.00"),
                }
                for _ in week_buckets
            ]
            for row_id in leaf_ids
        }

        unmapped_campaigns: set[str] = set()
        unmapped_fact_rows = 0

        for fact in facts:
            report_date = date.fromisoformat(str(fact["report_date"]))
            week_index = week_index_by_date.get(report_date)
            if week_index is None:
                continue

            campaign_name = str(fact.get("campaign_name") or "").strip()
            row_id = mapping_by_campaign.get(campaign_name)
            if not row_id:
                unmapped_fact_rows += 1
                if campaign_name:
                    unmapped_campaigns.add(campaign_name)
                continue

            leaf_week = leaf_values[row_id][week_index]
            leaf_week["impressions"] = int(leaf_week["impressions"]) + int(fact.get("impressions") or 0)
            leaf_week["clicks"] = int(leaf_week["clicks"]) + int(fact.get("clicks") or 0)
            leaf_week["ad_spend"] = Decimal(str(leaf_week["ad_spend"])) + Decimal(str(fact.get("spend") or "0"))
            leaf_week["ad_orders"] = int(leaf_week["ad_orders"]) + int(fact.get("orders") or 0)
            leaf_week["ad_sales"] = Decimal(str(leaf_week["ad_sales"])) + Decimal(str(fact.get("sales") or "0"))

        for fact in business_facts:
            report_date = date.fromisoformat(str(fact["report_date"]))
            week_index = week_index_by_date.get(report_date)
            if week_index is None:
                continue

            child_asin = str(fact.get("child_asin") or "").strip().upper()
            row_id = mapping_by_asin.get(child_asin)
            if not row_id:
                continue

            leaf_week = leaf_values[row_id][week_index]
            leaf_week["business_sales"] = Decimal(str(leaf_week["business_sales"])) + Decimal(str(fact.get("sales") or "0"))

        row_totals: dict[str, list[dict[str, Decimal | int]]] = {
            row_id: [
                {
                    "impressions": 0,
                    "clicks": 0,
                    "ad_spend": Decimal("0.00"),
                    "ad_orders": 0,
                    "ad_sales": Decimal("0.00"),
                    "business_sales": Decimal("0.00"),
                }
                for _ in week_buckets
            ]
            for row_id in row_by_id
        }
        for row_id, values in leaf_values.items():
            row_totals[row_id] = values

        parent_children: dict[str, list[str]] = {}
        for row in rows:
            if row.get("row_kind") != "leaf":
                continue
            parent_id = str(row.get("parent_row_id") or "").strip()
            if parent_id and parent_id in row_totals:
                parent_children.setdefault(parent_id, []).append(str(row["id"]))

        for parent_id, child_ids in parent_children.items():
            parent_weeks = row_totals[parent_id]
            for week_index in range(len(week_buckets)):
                for child_id in child_ids:
                    child_week = row_totals[child_id][week_index]
                    parent_weeks[week_index]["impressions"] = int(parent_weeks[week_index]["impressions"]) + int(
                        child_week["impressions"]
                    )
                    parent_weeks[week_index]["clicks"] = int(parent_weeks[week_index]["clicks"]) + int(
                        child_week["clicks"]
                    )
                    parent_weeks[week_index]["ad_spend"] = Decimal(str(parent_weeks[week_index]["ad_spend"])) + Decimal(
                        str(child_week["ad_spend"])
                    )
                    parent_weeks[week_index]["ad_orders"] = int(parent_weeks[week_index]["ad_orders"]) + int(
                        child_week["ad_orders"]
                    )
                    parent_weeks[week_index]["ad_sales"] = Decimal(str(parent_weeks[week_index]["ad_sales"])) + Decimal(
                        str(child_week["ad_sales"])
                    )
                    parent_weeks[week_index]["business_sales"] = Decimal(
                        str(parent_weeks[week_index]["business_sales"])
                    ) + Decimal(str(child_week["business_sales"]))

        ordered_rows = sorted(
            rows,
            key=lambda row: (int(row.get("sort_order") or 0), str(row.get("row_label") or "").lower()),
        )

        response_rows = []
        for row in ordered_rows:
            row_id = str(row["id"])
            week_values = row_totals[row_id]
            response_rows.append(
                {
                    "id": row_id,
                    "row_label": row.get("row_label"),
                    "row_kind": row.get("row_kind"),
                    "parent_row_id": row.get("parent_row_id"),
                    "sort_order": row.get("sort_order"),
                    "weeks": [
                        {
                            "impressions": int(values["impressions"]),
                            "clicks": int(values["clicks"]),
                            "ctr_pct": 0
                            if int(values["impressions"]) == 0
                            else round(int(values["clicks"]) / int(values["impressions"]), 4),
                            "ad_spend": _decimal_to_string(Decimal(str(values["ad_spend"]))),
                            "cpc": "0.00"
                            if int(values["clicks"]) == 0
                            else _decimal_to_string(
                                Decimal(str(values["ad_spend"])) / Decimal(str(int(values["clicks"])))
                            ),
                            "ad_orders": int(values["ad_orders"]),
                            "ad_conversion_rate": 0
                            if int(values["clicks"]) == 0
                            else round(int(values["ad_orders"]) / int(values["clicks"]), 4),
                            "ad_sales": _decimal_to_string(Decimal(str(values["ad_sales"]))),
                            "acos_pct": 0
                            if Decimal(str(values["ad_sales"])) == 0
                            else round(
                                float(Decimal(str(values["ad_spend"])) / Decimal(str(values["ad_sales"]))),
                                4,
                            ),
                            "business_sales": _decimal_to_string(Decimal(str(values["business_sales"]))),
                            "tacos_pct": 0
                            if Decimal(str(values["business_sales"])) == 0
                            else round(
                                float(Decimal(str(values["ad_spend"])) / Decimal(str(values["business_sales"]))),
                                4,
                            ),
                        }
                        for values in week_values
                    ],
                }
            )

        return {
            "profile": profile,
            "weeks": [
                {
                    "start": bucket.start.isoformat(),
                    "end": bucket.end.isoformat(),
                    "label": bucket.label,
                }
                for bucket in week_buckets
            ],
            "rows": response_rows,
            "qa": {
                "active_row_count": len(rows),
                "mapped_campaign_count": len(mapping_by_campaign),
                "unmapped_campaign_count": len(unmapped_campaigns),
                "unmapped_campaign_samples": sorted(unmapped_campaigns)[:10],
                "unmapped_fact_rows": unmapped_fact_rows,
                "fact_row_count": len(facts),
            },
        }

    def _get_profile(self, profile_id: str) -> dict[str, Any]:
        response = self.db.table("wbr_profiles").select("*").eq("id", profile_id).limit(1).execute()
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise WBRNotFoundError(f"Profile {profile_id} not found")
        return rows[0]

    def _list_active_rows(self, profile_id: str) -> list[dict[str, Any]]:
        response = (
            self.db.table("wbr_rows")
            .select("*")
            .eq("profile_id", profile_id)
            .eq("active", True)
            .execute()
        )
        return response.data if isinstance(response.data, list) else []

    def _list_active_campaign_mappings(self, profile_id: str) -> list[dict[str, Any]]:
        response = (
            self.db.table("wbr_pacvue_campaign_map")
            .select("campaign_name,row_id")
            .eq("profile_id", profile_id)
            .eq("active", True)
            .execute()
        )
        return response.data if isinstance(response.data, list) else []

    def _list_active_asin_mappings(self, profile_id: str) -> list[dict[str, Any]]:
        response = (
            self.db.table("wbr_asin_row_map")
            .select("child_asin,row_id")
            .eq("profile_id", profile_id)
            .eq("active", True)
            .execute()
        )
        return response.data if isinstance(response.data, list) else []

    def _list_facts(self, profile_id: str, *, date_from: date, date_to: date) -> list[dict[str, Any]]:
        response = (
            self.db.table("wbr_ads_campaign_daily")
            .select("*")
            .eq("profile_id", profile_id)
            .gte("report_date", date_from.isoformat())
            .lte("report_date", date_to.isoformat())
            .execute()
        )
        return response.data if isinstance(response.data, list) else []

    def _list_business_facts(self, profile_id: str, *, date_from: date, date_to: date) -> list[dict[str, Any]]:
        response = (
            self.db.table("wbr_business_asin_daily")
            .select("report_date,child_asin,sales")
            .eq("profile_id", profile_id)
            .gte("report_date", date_from.isoformat())
            .lte("report_date", date_to.isoformat())
            .execute()
        )
        return response.data if isinstance(response.data, list) else []
