"""Sales Mix report service.

Splits weekly sales for a WBR profile two ways:

1. **Ads vs Organic** — ad sales come from ``wbr_ads_campaign_daily``.
   Organic = business sales (``wbr_business_asin_daily``) minus ad sales,
   clamped at zero.
2. **Brand vs Category** — campaigns whose active Pacvue mapping has
   ``goal_code = 'Def'`` are Brand. Everything mapped is Category.
   Unmapped ad sales are surfaced separately so they don't silently
   inflate Category.

The service supports an explicit date range, parent-row scoping, and
ad-type filtering, and emits per-week coverage flags so callers can warn
when a window predates reliable Pacvue mapping coverage (e.g. when an
account was just onboarded under a different campaign-naming scheme).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Iterable

from supabase import Client

from .profiles import WBRNotFoundError, WBRValidationError
from .section2_report import _normalize_campaign_type

BRAND_GOAL_CODE = "Def"
COVERAGE_WARN_THRESHOLD = Decimal("0.80")

AD_TYPE_KEYS = ("sponsored_products", "sponsored_brands", "sponsored_display")
AD_TYPE_LABEL_BY_KEY = {
    "sponsored_products": "Sponsored Products",
    "sponsored_brands": "Sponsored Brands",
    "sponsored_display": "Sponsored Display",
}


@dataclass(frozen=True)
class WeekBucket:
    start: date
    end: date
    label: str


def _decimal_str(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        return Decimal("0")
    return (numerator / denominator).quantize(Decimal("0.0001"))


def _weeks_in_range(
    week_start_day: str,
    date_from: date,
    date_to: date,
) -> list[WeekBucket]:
    """Return whole weeks that fully fall within [date_from, date_to] and
    have already ended (today excluded)."""

    if date_to < date_from:
        return []

    today = datetime.now(UTC).date()
    # Snap date_from down to its containing week-start day.
    if week_start_day == "monday":
        offset = date_from.weekday()  # Mon=0
    else:
        offset = (date_from.weekday() + 1) % 7  # Sun=0
    cursor = date_from - timedelta(days=offset)

    last_complete_week_end = today - timedelta(days=1)
    buckets: list[WeekBucket] = []
    while cursor <= date_to:
        end = cursor + timedelta(days=6)
        if end > date_to or end > last_complete_week_end:
            break
        if end >= date_from:
            buckets.append(
                WeekBucket(
                    start=cursor,
                    end=end,
                    label=f"{cursor.strftime('%d-%b')} to {end.strftime('%d-%b')}",
                )
            )
        cursor = end + timedelta(days=1)
    return buckets


class SalesMixService:
    def __init__(self, db: Client) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public read path
    # ------------------------------------------------------------------

    def build_report(
        self,
        profile_id: str,
        *,
        date_from: date,
        date_to: date,
        parent_row_ids: Iterable[str] | None = None,
        ad_types: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        if date_to < date_from:
            raise WBRValidationError("date_to must be on or after date_from")

        profile = self._get_profile(profile_id)
        week_buckets = _weeks_in_range(
            str(profile.get("week_start_day") or "sunday"),
            date_from,
            date_to,
        )

        rows = self._list_active_rows(profile_id)
        rows_by_id = {str(row["id"]): row for row in rows if row.get("id")}
        leaf_to_parent: dict[str, str | None] = {
            str(row["id"]): (str(row.get("parent_row_id")) if row.get("parent_row_id") else None)
            for row in rows
            if row.get("row_kind") == "leaf"
        }

        parent_id_set = {pid for pid in (parent_row_ids or []) if pid}
        scoped_leaf_ids = self._scope_leaves_by_parents(rows_by_id, leaf_to_parent, parent_id_set)

        ad_type_set = {key.strip().lower() for key in (ad_types or []) if key and key.strip()}
        if not ad_type_set:
            ad_type_set = set(AD_TYPE_KEYS)
        else:
            invalid = ad_type_set - set(AD_TYPE_KEYS)
            if invalid:
                raise WBRValidationError(
                    f"Unknown ad_type(s): {sorted(invalid)}. Expected: {list(AD_TYPE_KEYS)}"
                )

        mappings = self._list_active_campaign_mappings(profile_id)
        mapping_by_campaign = {
            str(item["campaign_name"]): {
                "row_id": str(item.get("row_id") or ""),
                "goal_code": str(item.get("goal_code") or ""),
            }
            for item in mappings
            if item.get("campaign_name")
        }
        excluded_campaigns = self._list_active_campaign_exclusions(profile_id)
        asin_to_row = self._list_active_asin_mappings(profile_id)

        # Initialise weekly aggregates.
        weekly_state: list[dict[str, Any]] = [
            {
                "ad_sales": Decimal("0"),
                "ad_spend": Decimal("0"),
                "ad_orders": 0,
                "brand_sales": Decimal("0"),
                "category_sales": Decimal("0"),
                "unmapped_ad_sales": Decimal("0"),
                "unmapped_ad_spend": Decimal("0"),
                "business_sales": Decimal("0"),
                "ad_type": {
                    key: {
                        "ad_sales": Decimal("0"),
                        "ad_spend": Decimal("0"),
                        "ad_orders": 0,
                    }
                    for key in AD_TYPE_KEYS
                },
            }
            for _ in week_buckets
        ]

        week_index_by_date: dict[date, int] = {}
        for index, bucket in enumerate(week_buckets):
            cursor = bucket.start
            while cursor <= bucket.end:
                week_index_by_date[cursor] = index
                cursor += timedelta(days=1)

        ads_data_present = [False] * len(week_buckets)
        ads_facts = self._list_ads_facts(profile_id, date_from=date_from, date_to=date_to)
        for fact in ads_facts:
            try:
                report_date = date.fromisoformat(str(fact["report_date"]))
            except (TypeError, ValueError):
                continue
            week_index = week_index_by_date.get(report_date)
            if week_index is None:
                continue

            campaign_type = _normalize_campaign_type(fact.get("campaign_type"))
            if campaign_type not in ad_type_set:
                continue

            campaign_name = str(fact.get("campaign_name") or "").strip()
            mapping = mapping_by_campaign.get(campaign_name)
            mapped_leaf = mapping["row_id"] if mapping else ""

            if scoped_leaf_ids is not None:
                if not mapped_leaf or mapped_leaf not in scoped_leaf_ids:
                    # When a parent-row scope is active, drop facts that
                    # fall outside it. Includes unmapped ads (we can't
                    # confidently attribute them to any parent).
                    continue

            ads_data_present[week_index] = True
            spend = Decimal(str(fact.get("spend") or "0"))
            sales = Decimal(str(fact.get("sales") or "0"))
            orders = int(fact.get("orders") or 0)

            bucket = weekly_state[week_index]
            bucket["ad_sales"] += sales
            bucket["ad_spend"] += spend
            bucket["ad_orders"] += orders
            ad_type_bucket = bucket["ad_type"][campaign_type]
            ad_type_bucket["ad_sales"] += sales
            ad_type_bucket["ad_spend"] += spend
            ad_type_bucket["ad_orders"] += orders

            if not mapping:
                if campaign_name in excluded_campaigns:
                    continue
                bucket["unmapped_ad_sales"] += sales
                bucket["unmapped_ad_spend"] += spend
                continue

            goal_code = (mapping["goal_code"] or "").strip()
            if goal_code == BRAND_GOAL_CODE:
                bucket["brand_sales"] += sales
            else:
                bucket["category_sales"] += sales

        business_facts = self._list_business_facts(profile_id, date_from=date_from, date_to=date_to)
        for fact in business_facts:
            try:
                report_date = date.fromisoformat(str(fact["report_date"]))
            except (TypeError, ValueError):
                continue
            week_index = week_index_by_date.get(report_date)
            if week_index is None:
                continue
            child_asin = str(fact.get("child_asin") or "").strip().upper()
            sales = Decimal(str(fact.get("sales") or "0"))

            if scoped_leaf_ids is not None:
                row_id = asin_to_row.get(child_asin)
                if not row_id or row_id not in scoped_leaf_ids:
                    continue

            weekly_state[week_index]["business_sales"] += sales

        # Compute derived fields per week.
        weekly_response: list[dict[str, Any]] = []
        totals = {
            "ad_sales": Decimal("0"),
            "ad_spend": Decimal("0"),
            "ad_orders": 0,
            "brand_sales": Decimal("0"),
            "category_sales": Decimal("0"),
            "unmapped_ad_sales": Decimal("0"),
            "unmapped_ad_spend": Decimal("0"),
            "business_sales": Decimal("0"),
            "organic_sales": Decimal("0"),
        }

        first_low_coverage_week: str | None = None
        first_no_data_week: str | None = None

        for index, bucket in enumerate(week_buckets):
            state = weekly_state[index]
            ad_sales = state["ad_sales"]
            business_sales = state["business_sales"]
            organic_sales = business_sales - ad_sales
            if organic_sales < 0:
                organic_sales = Decimal("0")
            mapped_ad_sales = state["brand_sales"] + state["category_sales"]
            mapping_pct = _ratio(mapped_ad_sales, ad_sales) if ad_sales > 0 else None
            data_present = ads_data_present[index]
            below_threshold = (
                mapping_pct is not None and mapping_pct < COVERAGE_WARN_THRESHOLD
            )
            if not data_present and first_no_data_week is None:
                first_no_data_week = bucket.start.isoformat()
            if below_threshold and first_low_coverage_week is None:
                first_low_coverage_week = bucket.start.isoformat()

            weekly_response.append(
                {
                    "week_index": index,
                    "start": bucket.start.isoformat(),
                    "end": bucket.end.isoformat(),
                    "label": bucket.label,
                    "ad_sales": _decimal_str(ad_sales),
                    "ad_spend": _decimal_str(state["ad_spend"]),
                    "ad_orders": state["ad_orders"],
                    "brand_sales": _decimal_str(state["brand_sales"]),
                    "category_sales": _decimal_str(state["category_sales"]),
                    "unmapped_ad_sales": _decimal_str(state["unmapped_ad_sales"]),
                    "unmapped_ad_spend": _decimal_str(state["unmapped_ad_spend"]),
                    "business_sales": _decimal_str(business_sales),
                    "organic_sales": _decimal_str(organic_sales),
                    "ad_type_breakdown": [
                        {
                            "ad_type": key,
                            "label": AD_TYPE_LABEL_BY_KEY[key],
                            "ad_sales": _decimal_str(state["ad_type"][key]["ad_sales"]),
                            "ad_spend": _decimal_str(state["ad_type"][key]["ad_spend"]),
                            "ad_orders": state["ad_type"][key]["ad_orders"],
                        }
                        for key in AD_TYPE_KEYS
                    ],
                    "coverage": {
                        "data_present": data_present,
                        "mapping_coverage_pct": (
                            float(mapping_pct) if mapping_pct is not None else None
                        ),
                        "below_threshold": bool(below_threshold),
                    },
                }
            )

            totals["ad_sales"] += ad_sales
            totals["ad_spend"] += state["ad_spend"]
            totals["ad_orders"] += state["ad_orders"]
            totals["brand_sales"] += state["brand_sales"]
            totals["category_sales"] += state["category_sales"]
            totals["unmapped_ad_sales"] += state["unmapped_ad_sales"]
            totals["unmapped_ad_spend"] += state["unmapped_ad_spend"]
            totals["business_sales"] += business_sales
            totals["organic_sales"] += organic_sales

        total_mapping_pct = (
            _ratio(totals["brand_sales"] + totals["category_sales"], totals["ad_sales"])
            if totals["ad_sales"] > 0
            else None
        )
        total_ad_sales_pct = (
            _ratio(totals["ad_sales"], totals["business_sales"])
            if totals["business_sales"] > 0
            else None
        )

        coverage_warnings: list[str] = []
        if first_no_data_week:
            coverage_warnings.append(
                f"No ad-fact rows on or before {first_no_data_week}; earlier weeks may be empty."
            )
        if first_low_coverage_week:
            coverage_warnings.append(
                f"Mapping coverage drops below "
                f"{int(COVERAGE_WARN_THRESHOLD * 100)}% on {first_low_coverage_week}; "
                "Brand vs Category split may be unreliable for that week and earlier."
            )

        parent_row_options = self._list_parent_rows(rows)

        return {
            "profile": {
                "id": profile.get("id"),
                "display_name": profile.get("display_name"),
                "marketplace_code": profile.get("marketplace_code"),
                "week_start_day": profile.get("week_start_day"),
            },
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "filters": {
                "parent_row_ids": sorted(parent_id_set),
                "ad_types": sorted(ad_type_set),
            },
            "parent_row_options": parent_row_options,
            "ad_type_options": [
                {"key": key, "label": AD_TYPE_LABEL_BY_KEY[key]} for key in AD_TYPE_KEYS
            ],
            "weeks": [
                {
                    "start": bucket.start.isoformat(),
                    "end": bucket.end.isoformat(),
                    "label": bucket.label,
                }
                for bucket in week_buckets
            ],
            "weekly": weekly_response,
            "totals": {
                "ad_sales": _decimal_str(totals["ad_sales"]),
                "ad_spend": _decimal_str(totals["ad_spend"]),
                "ad_orders": totals["ad_orders"],
                "brand_sales": _decimal_str(totals["brand_sales"]),
                "category_sales": _decimal_str(totals["category_sales"]),
                "unmapped_ad_sales": _decimal_str(totals["unmapped_ad_sales"]),
                "unmapped_ad_spend": _decimal_str(totals["unmapped_ad_spend"]),
                "business_sales": _decimal_str(totals["business_sales"]),
                "organic_sales": _decimal_str(totals["organic_sales"]),
                "mapping_coverage_pct": (
                    float(total_mapping_pct) if total_mapping_pct is not None else None
                ),
                "ads_share_of_business_pct": (
                    float(total_ad_sales_pct) if total_ad_sales_pct is not None else None
                ),
            },
            "coverage": {
                "first_low_coverage_week": first_low_coverage_week,
                "first_no_data_week": first_no_data_week,
                "warn_threshold_pct": float(COVERAGE_WARN_THRESHOLD),
                "warnings": coverage_warnings,
            },
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _scope_leaves_by_parents(
        self,
        rows_by_id: dict[str, dict[str, Any]],
        leaf_to_parent: dict[str, str | None],
        parent_ids: set[str],
    ) -> set[str] | None:
        if not parent_ids:
            return None
        # Confirm each parent_id is a real row on this profile.
        invalid = parent_ids - set(rows_by_id.keys())
        if invalid:
            raise WBRValidationError(
                f"Unknown parent_row_id(s): {sorted(invalid)}"
            )
        scoped: set[str] = set()
        for leaf_id, parent_id in leaf_to_parent.items():
            if leaf_id in parent_ids or (parent_id and parent_id in parent_ids):
                scoped.add(leaf_id)
        return scoped

    def _list_parent_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items = [
            {
                "id": str(row["id"]),
                "row_label": row.get("row_label"),
                "sort_order": row.get("sort_order"),
            }
            for row in rows
            if row.get("id") and row.get("row_kind") in {"parent", "section1_only", "section2_only", "section3_only"}
        ]
        # Fall back to "any non-leaf, active" if no explicit kinds match the filter above.
        if not items:
            items = [
                {
                    "id": str(row["id"]),
                    "row_label": row.get("row_label"),
                    "sort_order": row.get("sort_order"),
                }
                for row in rows
                if row.get("id") and row.get("row_kind") != "leaf"
            ]
        items.sort(key=lambda item: (int(item.get("sort_order") or 0), str(item.get("row_label") or "").lower()))
        return items

    def _get_profile(self, profile_id: str) -> dict[str, Any]:
        response = (
            self.db.table("wbr_profiles")
            .select("id, display_name, marketplace_code, week_start_day")
            .eq("id", profile_id)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise WBRNotFoundError(f"Profile {profile_id} not found")
        return rows[0]

    def _list_active_rows(self, profile_id: str) -> list[dict[str, Any]]:
        response = (
            self.db.table("wbr_rows")
            .select("id, row_label, row_kind, parent_row_id, sort_order, active")
            .eq("profile_id", profile_id)
            .eq("active", True)
            .execute()
        )
        return response.data if isinstance(response.data, list) else []

    def _list_active_campaign_mappings(self, profile_id: str) -> list[dict[str, Any]]:
        return self._select_all(
            "wbr_pacvue_campaign_map",
            "campaign_name,row_id,goal_code",
            [
                ("eq", "profile_id", profile_id),
                ("eq", "active", True),
            ],
        )

    def _list_active_campaign_exclusions(self, profile_id: str) -> set[str]:
        rows = self._select_all(
            "wbr_campaign_exclusions",
            "campaign_name",
            [
                ("eq", "profile_id", profile_id),
                ("eq", "active", True),
            ],
        )
        return {
            str(row["campaign_name"])
            for row in rows
            if isinstance(row, dict) and row.get("campaign_name")
        }

    def _list_active_asin_mappings(self, profile_id: str) -> dict[str, str]:
        rows = self._select_all(
            "wbr_asin_row_map",
            "child_asin,row_id",
            [
                ("eq", "profile_id", profile_id),
                ("eq", "active", True),
            ],
        )
        return {
            str(row["child_asin"]).strip().upper(): str(row["row_id"])
            for row in rows
            if isinstance(row, dict) and row.get("child_asin") and row.get("row_id")
        }

    def _list_ads_facts(
        self,
        profile_id: str,
        *,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        return self._select_all(
            "wbr_ads_campaign_daily",
            "report_date,campaign_name,campaign_type,impressions,clicks,spend,orders,sales",
            [
                ("eq", "profile_id", profile_id),
                ("gte", "report_date", date_from.isoformat()),
                ("lte", "report_date", date_to.isoformat()),
            ],
        )

    def _list_business_facts(
        self,
        profile_id: str,
        *,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        return self._select_all(
            "wbr_business_asin_daily",
            "report_date,child_asin,sales",
            [
                ("eq", "profile_id", profile_id),
                ("gte", "report_date", date_from.isoformat()),
                ("lte", "report_date", date_to.isoformat()),
            ],
        )

    def _select_all(
        self,
        table_name: str,
        columns: str,
        filters: list[tuple[str, str, Any]],
        *,
        page_size: int = 1000,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            query = self.db.table(table_name).select(columns)
            for op, field, value in filters:
                query = getattr(query, op)(field, value)
            response = query.order("id").range(offset, offset + page_size - 1).execute()
            batch = response.data if isinstance(response.data, list) else []
            rows.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
        return rows
