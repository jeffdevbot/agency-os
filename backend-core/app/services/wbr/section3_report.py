"""WBR Section 3 report builder – Inventory + Returns."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
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


class Section3ReportService:
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
                "qa": self._empty_qa(),
            }

        rows = self._list_active_rows(profile_id)
        row_by_id = {str(row["id"]): row for row in rows if row.get("id")}
        leaf_ids = {str(row["id"]) for row in rows if row.get("row_kind") == "leaf"}
        mappings = self._list_active_asin_mappings(profile_id)
        mapping_by_asin = {
            str(item["child_asin"]).strip().upper(): str(item["row_id"])
            for item in mappings
            if item.get("child_asin") and item.get("row_id") and str(item["row_id"]) in leaf_ids
        }
        excluded_asins = self._list_active_asin_exclusions(profile_id)

        # Fetch latest inventory snapshot
        inventory_facts = self._list_latest_inventory(profile_id)

        # Fetch returns for the last 2 completed weeks
        returns_week_buckets = week_buckets[-2:] if len(week_buckets) >= 2 else week_buckets
        returns_date_from = returns_week_buckets[0].start
        returns_date_to = returns_week_buckets[-1].end
        returns_facts = self._list_returns(
            profile_id,
            date_from=returns_date_from,
            date_to=returns_date_to,
        )

        # Fetch Section 1 unit sales for WOS denominator (last 4 weeks)
        # and for return % denominator (last 2 weeks)
        sales_date_from = week_buckets[0].start
        sales_date_to = week_buckets[-1].end
        business_facts = self._list_business_facts(
            profile_id,
            date_from=sales_date_from,
            date_to=sales_date_to,
        )

        # Build date -> week index mapping
        week_index_by_date: dict[date, int] = {}
        for index, bucket in enumerate(week_buckets):
            cursor = bucket.start
            while cursor <= bucket.end:
                week_index_by_date[cursor] = index
                cursor += timedelta(days=1)

        # Returns week indices within the full bucket list
        returns_week_indices = list(range(len(week_buckets)))[-2:] if len(week_buckets) >= 2 else list(range(len(week_buckets)))

        # ---- Accumulate per-leaf inventory ----
        leaf_inventory: dict[str, dict[str, int]] = {
            row_id: {
                "instock": 0,
                "working": 0,
                "reserved_plus_fc_transfer": 0,
                "receiving_plus_intransit": 0,
            }
            for row_id in leaf_ids
        }

        unmapped_inventory_asins: set[str] = set()
        for fact in inventory_facts:
            asin = str(fact.get("child_asin") or "").strip().upper()
            row_id = mapping_by_asin.get(asin)
            if not row_id:
                if asin and asin in excluded_asins:
                    continue
                if asin:
                    unmapped_inventory_asins.add(asin)
                continue
            inv = leaf_inventory[row_id]
            inv["instock"] += int(fact.get("instock") or 0)
            inv["working"] += int(fact.get("working") or 0)
            inv["reserved_plus_fc_transfer"] += int(fact.get("reserved_plus_fc_transfer") or 0)
            inv["receiving_plus_intransit"] += int(fact.get("receiving_plus_intransit") or 0)

        # ---- Accumulate per-leaf returns by week ----
        leaf_returns: dict[str, dict[int, int]] = {
            row_id: {wi: 0 for wi in returns_week_indices}
            for row_id in leaf_ids
        }

        for fact in returns_facts:
            asin = str(fact.get("child_asin") or "").strip().upper()
            row_id = mapping_by_asin.get(asin)
            if not row_id:
                if asin and asin in excluded_asins:
                    continue
                continue
            return_date = date.fromisoformat(str(fact["return_date"]))
            week_index = week_index_by_date.get(return_date)
            if week_index is None or week_index not in returns_week_indices:
                continue
            leaf_returns[row_id][week_index] += int(fact.get("return_units") or 0)

        # ---- Accumulate per-leaf unit sales by week (for WOS + return %) ----
        leaf_unit_sales: dict[str, list[int]] = {
            row_id: [0] * len(week_buckets) for row_id in leaf_ids
        }

        for fact in business_facts:
            report_date = date.fromisoformat(str(fact["report_date"]))
            week_index = week_index_by_date.get(report_date)
            if week_index is None:
                continue
            asin = str(fact.get("child_asin") or "").strip().upper()
            row_id = mapping_by_asin.get(asin)
            if not row_id:
                if asin and asin in excluded_asins:
                    continue
                continue
            leaf_unit_sales[row_id][week_index] += int(fact.get("unit_sales") or 0)

        # ---- Roll up parent rows ----
        parent_children: dict[str, list[str]] = {}
        for row in rows:
            if row.get("row_kind") != "leaf":
                continue
            parent_id = str(row.get("parent_row_id") or "").strip()
            if parent_id and parent_id in row_by_id:
                parent_children.setdefault(parent_id, []).append(str(row["id"]))

        # Initialize parent inventory/returns/sales
        all_inventory: dict[str, dict[str, int]] = {}
        all_returns: dict[str, dict[int, int]] = {}
        all_unit_sales: dict[str, list[int]] = {}

        for row_id in row_by_id:
            if row_id in leaf_ids:
                all_inventory[row_id] = leaf_inventory[row_id]
                all_returns[row_id] = leaf_returns[row_id]
                all_unit_sales[row_id] = leaf_unit_sales[row_id]
            else:
                all_inventory[row_id] = {
                    "instock": 0,
                    "working": 0,
                    "reserved_plus_fc_transfer": 0,
                    "receiving_plus_intransit": 0,
                }
                all_returns[row_id] = {wi: 0 for wi in returns_week_indices}
                all_unit_sales[row_id] = [0] * len(week_buckets)

        for parent_id, child_ids in parent_children.items():
            for child_id in child_ids:
                child_inv = all_inventory[child_id]
                parent_inv = all_inventory[parent_id]
                parent_inv["instock"] += child_inv["instock"]
                parent_inv["working"] += child_inv["working"]
                parent_inv["reserved_plus_fc_transfer"] += child_inv["reserved_plus_fc_transfer"]
                parent_inv["receiving_plus_intransit"] += child_inv["receiving_plus_intransit"]

                for wi in returns_week_indices:
                    all_returns[parent_id][wi] += all_returns[child_id][wi]

                for wi in range(len(week_buckets)):
                    all_unit_sales[parent_id][wi] += all_unit_sales[child_id][wi]

        # ---- Build response rows ----
        ordered_rows = sorted(
            rows,
            key=lambda row: (int(row.get("sort_order") or 0), str(row.get("row_label") or "").lower()),
        )

        response_rows = []
        for row in ordered_rows:
            row_id = str(row["id"])
            inv = all_inventory[row_id]
            ret = all_returns[row_id]
            sales = all_unit_sales[row_id]

            # WOS: (instock + reserved_fc_transfer + receiving_intransit) / avg weekly unit sales (all weeks)
            total_supply = inv["instock"] + inv["reserved_plus_fc_transfer"] + inv["receiving_plus_intransit"]
            total_unit_sales_all_weeks = sum(sales)
            weeks_with_data = len(week_buckets)
            avg_weekly_sales = total_unit_sales_all_weeks / weeks_with_data if weeks_with_data > 0 else 0
            weeks_of_stock = None if avg_weekly_sales == 0 else round(total_supply / avg_weekly_sales, 0)

            # Returns: last 2 completed weeks
            returns_week_1 = ret.get(returns_week_indices[-1], 0) if returns_week_indices else 0
            returns_week_2 = ret.get(returns_week_indices[-2], 0) if len(returns_week_indices) >= 2 else 0

            # Return %: avg returns last 2 weeks / avg unit sales last 2 weeks
            returns_total_2w = sum(ret.get(wi, 0) for wi in returns_week_indices)
            sales_total_2w = sum(sales[wi] for wi in returns_week_indices)
            num_return_weeks = len(returns_week_indices)
            avg_returns_2w = returns_total_2w / num_return_weeks if num_return_weeks > 0 else 0
            avg_sales_2w = sales_total_2w / num_return_weeks if num_return_weeks > 0 else 0
            return_rate = None if avg_sales_2w == 0 else round(avg_returns_2w / avg_sales_2w, 4)

            response_rows.append(
                {
                    "id": row_id,
                    "row_label": row.get("row_label"),
                    "row_kind": row.get("row_kind"),
                    "parent_row_id": row.get("parent_row_id"),
                    "sort_order": row.get("sort_order"),
                    "instock": inv["instock"],
                    "working": inv["working"],
                    "reserved_plus_fc_transfer": inv["reserved_plus_fc_transfer"],
                    "receiving_plus_intransit": inv["receiving_plus_intransit"],
                    "weeks_of_stock": weeks_of_stock,
                    "returns_week_1": returns_week_1,
                    "returns_week_2": returns_week_2,
                    "return_rate": return_rate,
                    # Denominator fields so the frontend can recompute WOS /
                    # return-rate totals from the visible (filtered) row set.
                    "_unit_sales_4w": total_unit_sales_all_weeks,
                    "_unit_sales_2w": sales_total_2w,
                }
            )

        # ---- Compute totals from top-level rows ----
        top_level_ids = {str(row["id"]) for row in rows if not row.get("parent_row_id")}
        total_supply = 0
        total_unit_sales_all = 0
        total_returns_2w = 0
        total_sales_2w = 0
        for row_id in top_level_ids:
            inv = all_inventory.get(row_id)
            if inv:
                total_supply += inv["instock"] + inv["reserved_plus_fc_transfer"] + inv["receiving_plus_intransit"]
            sales = all_unit_sales.get(row_id)
            if sales:
                total_unit_sales_all += sum(sales)
                total_sales_2w += sum(sales[wi] for wi in returns_week_indices)
            ret = all_returns.get(row_id)
            if ret:
                total_returns_2w += sum(ret.get(wi, 0) for wi in returns_week_indices)

        weeks_count = len(week_buckets)
        total_avg_weekly_sales = total_unit_sales_all / weeks_count if weeks_count > 0 else 0
        total_weeks_of_stock = None if total_avg_weekly_sales == 0 else round(total_supply / total_avg_weekly_sales, 0)

        num_ret_weeks = len(returns_week_indices)
        total_avg_returns = total_returns_2w / num_ret_weeks if num_ret_weeks > 0 else 0
        total_avg_sales = total_sales_2w / num_ret_weeks if num_ret_weeks > 0 else 0
        total_return_rate = None if total_avg_sales == 0 else round(total_avg_returns / total_avg_sales, 4)

        # Build returns week labels
        returns_weeks = [
            {
                "start": week_buckets[wi].start.isoformat(),
                "end": week_buckets[wi].end.isoformat(),
                "label": week_buckets[wi].label,
            }
            for wi in returns_week_indices
        ]

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
            "returns_weeks": returns_weeks,
            "rows": response_rows,
            "totals": {
                "weeks_of_stock": total_weeks_of_stock,
                "return_rate": total_return_rate,
            },
            "qa": {
                "active_row_count": len(rows),
                "mapped_asin_count": len(mapping_by_asin),
                "unmapped_inventory_asin_count": len(unmapped_inventory_asins),
                "inventory_fact_count": len(inventory_facts),
                "returns_fact_count": len(returns_facts),
                "business_fact_count": len(business_facts),
            },
        }

    def _empty_qa(self) -> dict[str, int]:
        return {
            "active_row_count": 0,
            "mapped_asin_count": 0,
            "unmapped_inventory_asin_count": 0,
            "inventory_fact_count": 0,
            "returns_fact_count": 0,
            "business_fact_count": 0,
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

    def _list_active_asin_exclusions(self, profile_id: str) -> set[str]:
        rows = self._select_all(
            "wbr_asin_exclusions",
            "child_asin",
            [
                ("eq", "profile_id", profile_id),
                ("eq", "active", True),
            ],
        )
        return {
            str(row["child_asin"]).strip().upper()
            for row in rows
            if isinstance(row, dict) and row.get("child_asin")
        }

    def _list_latest_inventory(self, profile_id: str) -> list[dict[str, Any]]:
        """Fetch the most recent inventory snapshot for the profile."""
        # Find the latest snapshot_date
        latest_response = (
            self.db.table("wbr_inventory_asin_snapshots")
            .select("snapshot_date")
            .eq("profile_id", profile_id)
            .order("snapshot_date", desc=True)
            .limit(1)
            .execute()
        )
        latest_rows = latest_response.data if isinstance(latest_response.data, list) else []
        if not latest_rows:
            return []

        snapshot_date = latest_rows[0]["snapshot_date"]
        return self._select_all(
            "wbr_inventory_asin_snapshots",
            "child_asin,instock,working,reserved_plus_fc_transfer,receiving_plus_intransit,source_row_count",
            [
                ("eq", "profile_id", profile_id),
                ("eq", "snapshot_date", snapshot_date),
            ],
        )

    def _list_returns(self, profile_id: str, *, date_from: date, date_to: date) -> list[dict[str, Any]]:
        return self._select_all(
            "wbr_returns_asin_daily",
            "return_date,child_asin,return_units",
            [
                ("eq", "profile_id", profile_id),
                ("gte", "return_date", date_from.isoformat()),
                ("lte", "return_date", date_to.isoformat()),
            ],
        )

    def _list_business_facts(self, profile_id: str, *, date_from: date, date_to: date) -> list[dict[str, Any]]:
        return self._select_all(
            "wbr_business_asin_daily",
            "report_date,child_asin,unit_sales",
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

            # Stable ordering is required when paginating large result sets,
            # otherwise PostgREST can return overlapping windows.
            response = query.order("id").range(offset, offset + page_size - 1).execute()
            batch = response.data if isinstance(response.data, list) else []
            rows.extend(batch)

            if len(batch) < page_size:
                break
            offset += page_size

        return rows
