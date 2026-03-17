from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from supabase import Client

from .profiles import WBRNotFoundError

_PAGE_SIZE = 1000


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


class Section1ReportService:
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
                    "mapped_asin_count": 0,
                    "unmapped_asin_count": 0,
                    "unmapped_fact_rows": 0,
                    "fact_row_count": 0,
                },
            }

        rows = self._list_active_rows(profile_id)
        row_by_id = {str(row["id"]): row for row in rows if row.get("id")}
        leaf_ids = {str(row["id"]) for row in rows if row.get("row_kind") == "leaf"}
        mappings = self._list_active_asin_mappings(profile_id)
        mapping_by_asin = {
            str(item["child_asin"]): str(item["row_id"])
            for item in mappings
            if item.get("child_asin") and item.get("row_id") and str(item["row_id"]) in leaf_ids
        }

        facts = self._list_facts(
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
                    "page_views": 0,
                    "unit_sales": 0,
                    "sales": Decimal("0.00"),
                }
                for _ in week_buckets
            ]
            for row_id in leaf_ids
        }

        unmapped_asins: set[str] = set()
        unmapped_fact_rows = 0

        for fact in facts:
            report_date = date.fromisoformat(str(fact["report_date"]))
            week_index = week_index_by_date.get(report_date)
            if week_index is None:
                continue

            child_asin = str(fact.get("child_asin") or "").strip().upper()
            row_id = mapping_by_asin.get(child_asin)
            if not row_id:
                unmapped_fact_rows += 1
                if child_asin:
                    unmapped_asins.add(child_asin)
                continue

            leaf_week = leaf_values[row_id][week_index]
            leaf_week["page_views"] = int(leaf_week["page_views"]) + int(fact.get("page_views") or 0)
            leaf_week["unit_sales"] = int(leaf_week["unit_sales"]) + int(fact.get("unit_sales") or 0)
            leaf_week["sales"] = Decimal(str(leaf_week["sales"])) + Decimal(str(fact.get("sales") or "0"))

        row_totals: dict[str, list[dict[str, Decimal | int]]] = {
            row_id: [
                {
                    "page_views": 0,
                    "unit_sales": 0,
                    "sales": Decimal("0.00"),
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
                    parent_weeks[week_index]["page_views"] = int(parent_weeks[week_index]["page_views"]) + int(
                        child_week["page_views"]
                    )
                    parent_weeks[week_index]["unit_sales"] = int(parent_weeks[week_index]["unit_sales"]) + int(
                        child_week["unit_sales"]
                    )
                    parent_weeks[week_index]["sales"] = Decimal(str(parent_weeks[week_index]["sales"])) + Decimal(
                        str(child_week["sales"])
                    )

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
                            "page_views": int(values["page_views"]),
                            "unit_sales": int(values["unit_sales"]),
                            "sales": _decimal_to_string(Decimal(str(values["sales"]))),
                            "conversion_rate": 0
                            if int(values["page_views"]) == 0
                            else round(int(values["unit_sales"]) / int(values["page_views"]), 4),
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
                "mapped_asin_count": len(mapping_by_asin),
                "unmapped_asin_count": len(unmapped_asins),
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

    def _list_active_asin_mappings(self, profile_id: str) -> list[dict[str, Any]]:
        return self._select_all(
            "wbr_asin_row_map",
            "child_asin,row_id",
            [
                ("eq", "profile_id", profile_id),
                ("eq", "active", True),
            ],
        )

    def _list_facts(self, profile_id: str, *, date_from: date, date_to: date) -> list[dict[str, Any]]:
        return self._select_all(
            "wbr_business_asin_daily",
            "*",
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
        page_size: int = _PAGE_SIZE,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0

        while True:
            query = self.db.table(table_name).select(columns)
            for op, field, value in filters:
                query = getattr(query, op)(field, value)

            response = query.range(offset, offset + page_size - 1).execute()
            batch = response.data if isinstance(response.data, list) else []
            rows.extend(batch)

            if len(batch) < page_size:
                break
            offset += page_size

        return rows
