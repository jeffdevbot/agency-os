"""Pacvue campaign mapping management service.

Powers the admin sync UI: list unmapped campaigns over the report window with
metrics, list all current mappings, and manually upsert / deactivate mappings.
The list endpoints share their date-window and exclusion logic with
``Section2ReportService`` so numbers reconcile with the rendered report.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from supabase import Client

from .pacvue_imports import PACVUE_GOAL_CODES
from .profiles import WBRNotFoundError, WBRValidationError
from .section2_report import _previous_full_weeks

_PAGE_SIZE = 1000
_BATCH_SIZE = 500


@dataclass(frozen=True)
class _CampaignAgg:
    fact_rows: int = 0
    impressions: int = 0
    clicks: int = 0
    spend: Decimal = Decimal("0")
    orders: int = 0
    sales: Decimal = Decimal("0")
    first_seen: date | None = None
    last_seen: date | None = None


def _decimal_str(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


class PacvueMappingService:
    def __init__(self, db: Client) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Read paths
    # ------------------------------------------------------------------

    def list_unmapped(self, profile_id: str, *, weeks: int = 4) -> dict[str, Any]:
        profile = self._get_profile(profile_id)
        window = self._window(profile, weeks=weeks)
        if not window:
            return {"date_from": None, "date_to": None, "items": []}

        date_from, date_to = window
        active_map = self._list_active_mapped_names(profile_id)
        excluded = self._list_active_exclusion_names(profile_id)
        aggs = self._aggregate_facts(profile_id, date_from=date_from, date_to=date_to)

        items: list[dict[str, Any]] = []
        for campaign_name, agg in aggs.items():
            if campaign_name in active_map:
                continue
            if campaign_name in excluded:
                continue
            items.append(_serialize_campaign_metrics(campaign_name, agg))

        items.sort(
            key=lambda item: (-Decimal(item["spend"]), -item["orders"], item["campaign_name"].lower())
        )
        return {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "items": items,
        }

    def list_mappings(self, profile_id: str, *, weeks: int = 4) -> dict[str, Any]:
        profile = self._get_profile(profile_id)
        window = self._window(profile, weeks=weeks)
        date_from, date_to = window if window else (None, None)

        leaf_rows = self._list_active_leaf_rows(profile_id)
        leaf_label_by_id = {str(row["id"]): row.get("row_label") for row in leaf_rows}

        mappings = self._select_all(
            "wbr_pacvue_campaign_map",
            "id,campaign_name,raw_tag,row_id,leaf_row_label,goal_code,import_batch_id,active,updated_at",
            [
                ("eq", "profile_id", profile_id),
                ("eq", "active", True),
            ],
        )

        aggs: dict[str, _CampaignAgg] = {}
        if date_from and date_to:
            aggs = self._aggregate_facts(profile_id, date_from=date_from, date_to=date_to)

        items: list[dict[str, Any]] = []
        for row in mappings:
            campaign_name = str(row.get("campaign_name") or "")
            if not campaign_name:
                continue
            row_id = str(row.get("row_id") or "") if row.get("row_id") else None
            leaf_label = leaf_label_by_id.get(row_id) if row_id else row.get("leaf_row_label")
            agg = aggs.get(campaign_name, _CampaignAgg())
            metrics = _serialize_campaign_metrics(campaign_name, agg)
            metrics.update(
                {
                    "id": str(row["id"]) if row.get("id") else None,
                    "row_id": row_id,
                    "leaf_row_label": leaf_label,
                    "goal_code": row.get("goal_code"),
                    "raw_tag": row.get("raw_tag"),
                    "import_batch_id": row.get("import_batch_id"),
                    "is_manual": row.get("import_batch_id") is None,
                    "updated_at": row.get("updated_at"),
                }
            )
            items.append(metrics)

        items.sort(
            key=lambda item: (
                str(item.get("leaf_row_label") or "").lower(),
                str(item.get("goal_code") or "").lower(),
                str(item.get("campaign_name") or "").lower(),
            )
        )

        return {
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "items": items,
        }

    def list_leaf_rows(self, profile_id: str) -> list[dict[str, Any]]:
        rows = self._list_active_leaf_rows(profile_id)
        items = [
            {
                "id": str(row["id"]),
                "row_label": row.get("row_label"),
                "parent_row_id": row.get("parent_row_id"),
                "sort_order": row.get("sort_order"),
            }
            for row in rows
            if row.get("id")
        ]
        items.sort(
            key=lambda item: (
                int(item.get("sort_order") or 0),
                str(item.get("row_label") or "").lower(),
            )
        )
        return items

    # ------------------------------------------------------------------
    # Write paths
    # ------------------------------------------------------------------

    def upsert_manual_mapping(
        self,
        *,
        profile_id: str,
        campaign_name: str,
        row_id: str,
        goal_code: str,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        self._get_profile(profile_id)
        campaign_name = (campaign_name or "").strip()
        if not campaign_name:
            raise WBRValidationError("campaign_name is required")

        normalized_goal = PACVUE_GOAL_CODES.get((goal_code or "").lower())
        if not normalized_goal:
            raise WBRValidationError(
                f'Unsupported goal_code "{goal_code}". Expected one of: '
                + ", ".join(sorted(set(PACVUE_GOAL_CODES.values())))
            )

        leaf_row = self._get_active_leaf_row(profile_id, row_id)

        # Deactivate any current active mapping(s) for this campaign before
        # inserting the manual entry. Mirrors the per-campaign overwrite that
        # the Pacvue importer applies.
        (
            self.db.table("wbr_pacvue_campaign_map")
            .update({"active": False})
            .eq("profile_id", profile_id)
            .eq("active", True)
            .eq("campaign_name", campaign_name)
            .execute()
        )

        leaf_label = leaf_row.get("row_label")
        payload: dict[str, Any] = {
            "profile_id": profile_id,
            "import_batch_id": None,
            "campaign_name": campaign_name,
            "raw_tag": f"{leaf_label} / {normalized_goal}",
            "row_id": str(leaf_row["id"]),
            "leaf_row_label": leaf_label,
            "goal_code": normalized_goal,
            "raw_payload": {"source": "manual", "user_id": user_id},
            "active": True,
        }
        response = self.db.table("wbr_pacvue_campaign_map").insert(payload).execute()
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise WBRValidationError("Failed to save manual campaign mapping")
        return rows[0]

    def deactivate_mapping(
        self,
        *,
        profile_id: str,
        campaign_name: str,
    ) -> int:
        self._get_profile(profile_id)
        campaign_name = (campaign_name or "").strip()
        if not campaign_name:
            raise WBRValidationError("campaign_name is required")

        response = (
            self.db.table("wbr_pacvue_campaign_map")
            .update({"active": False})
            .eq("profile_id", profile_id)
            .eq("active", True)
            .eq("campaign_name", campaign_name)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        return len(rows)

    def set_exclusion(
        self,
        *,
        profile_id: str,
        campaign_name: str,
        excluded: bool,
        reason: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        self._get_profile(profile_id)
        campaign_name = (campaign_name or "").strip()
        if not campaign_name:
            raise WBRValidationError("campaign_name is required")

        existing_response = (
            self.db.table("wbr_campaign_exclusions")
            .select("id, active")
            .eq("profile_id", profile_id)
            .eq("campaign_name", campaign_name)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        existing = existing_response.data if isinstance(existing_response.data, list) else []

        if not excluded:
            if not existing:
                return {"campaign_name": campaign_name, "active": False, "changed": False}
            updates: dict[str, Any] = {"active": False}
            if user_id:
                updates["updated_by"] = user_id
            (
                self.db.table("wbr_campaign_exclusions")
                .update(updates)
                .eq("id", existing[0]["id"])
                .execute()
            )
            return {"campaign_name": campaign_name, "active": False, "changed": True}

        if existing:
            return {"campaign_name": campaign_name, "active": True, "changed": False}

        payload: dict[str, Any] = {
            "profile_id": profile_id,
            "campaign_name": campaign_name,
            "exclusion_source": "manual",
            "exclusion_reason": (reason or None),
            "active": True,
        }
        if user_id:
            payload["created_by"] = user_id
            payload["updated_by"] = user_id
        response = self.db.table("wbr_campaign_exclusions").insert(payload).execute()
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise WBRValidationError("Failed to save campaign exclusion")
        return {"campaign_name": campaign_name, "active": True, "changed": True}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_profile(self, profile_id: str) -> dict[str, Any]:
        response = (
            self.db.table("wbr_profiles")
            .select("id, week_start_day")
            .eq("id", profile_id)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise WBRNotFoundError(f"Profile {profile_id} not found")
        return rows[0]

    def _window(
        self,
        profile: dict[str, Any],
        *,
        weeks: int,
    ) -> tuple[date, date] | None:
        week_buckets = _previous_full_weeks(
            str(profile.get("week_start_day") or "sunday"), weeks
        )
        if not week_buckets:
            return None
        return week_buckets[0].start, week_buckets[-1].end

    def _list_active_mapped_names(self, profile_id: str) -> set[str]:
        rows = self._select_all(
            "wbr_pacvue_campaign_map",
            "campaign_name",
            [
                ("eq", "profile_id", profile_id),
                ("eq", "active", True),
            ],
        )
        return {
            str(row["campaign_name"]).strip()
            for row in rows
            if isinstance(row, dict) and row.get("campaign_name")
        }

    def _list_active_exclusion_names(self, profile_id: str) -> set[str]:
        rows = self._select_all(
            "wbr_campaign_exclusions",
            "campaign_name",
            [
                ("eq", "profile_id", profile_id),
                ("eq", "active", True),
            ],
        )
        return {
            str(row["campaign_name"]).strip()
            for row in rows
            if isinstance(row, dict) and row.get("campaign_name")
        }

    def _list_active_leaf_rows(self, profile_id: str) -> list[dict[str, Any]]:
        response = (
            self.db.table("wbr_rows")
            .select("id, row_label, parent_row_id, sort_order")
            .eq("profile_id", profile_id)
            .eq("row_kind", "leaf")
            .eq("active", True)
            .execute()
        )
        return response.data if isinstance(response.data, list) else []

    def _get_active_leaf_row(self, profile_id: str, row_id: str) -> dict[str, Any]:
        if not row_id:
            raise WBRValidationError("row_id is required")
        response = (
            self.db.table("wbr_rows")
            .select("id, row_label, row_kind, active")
            .eq("id", row_id)
            .eq("profile_id", profile_id)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise WBRValidationError(f"Row {row_id} not found for this profile")
        row = rows[0]
        if row.get("row_kind") != "leaf":
            raise WBRValidationError("Selected row must be a leaf row")
        if not row.get("active", False):
            raise WBRValidationError("Selected row is inactive")
        return row

    def _aggregate_facts(
        self,
        profile_id: str,
        *,
        date_from: date,
        date_to: date,
    ) -> dict[str, _CampaignAgg]:
        rows = self._select_all(
            "wbr_ads_campaign_daily",
            "campaign_name,report_date,impressions,clicks,spend,orders,sales",
            [
                ("eq", "profile_id", profile_id),
                ("gte", "report_date", date_from.isoformat()),
                ("lte", "report_date", date_to.isoformat()),
            ],
        )
        aggs: dict[str, _CampaignAgg] = {}
        for row in rows:
            name = str(row.get("campaign_name") or "").strip()
            if not name:
                continue
            try:
                report_date = date.fromisoformat(str(row["report_date"]))
            except (TypeError, ValueError):
                report_date = None
            current = aggs.get(name, _CampaignAgg())
            first_seen = current.first_seen
            last_seen = current.last_seen
            if report_date is not None:
                first_seen = report_date if first_seen is None or report_date < first_seen else first_seen
                last_seen = report_date if last_seen is None or report_date > last_seen else last_seen
            aggs[name] = _CampaignAgg(
                fact_rows=current.fact_rows + 1,
                impressions=current.impressions + int(row.get("impressions") or 0),
                clicks=current.clicks + int(row.get("clicks") or 0),
                spend=current.spend + Decimal(str(row.get("spend") or "0")),
                orders=current.orders + int(row.get("orders") or 0),
                sales=current.sales + Decimal(str(row.get("sales") or "0")),
                first_seen=first_seen,
                last_seen=last_seen,
            )
        return aggs

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
            response = query.order("id").range(offset, offset + page_size - 1).execute()
            batch = response.data if isinstance(response.data, list) else []
            rows.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
        return rows


def _serialize_campaign_metrics(campaign_name: str, agg: _CampaignAgg) -> dict[str, Any]:
    return {
        "campaign_name": campaign_name,
        "fact_rows": agg.fact_rows,
        "impressions": agg.impressions,
        "clicks": agg.clicks,
        "spend": _decimal_str(agg.spend),
        "orders": agg.orders,
        "sales": _decimal_str(agg.sales),
        "first_seen": agg.first_seen.isoformat() if agg.first_seen else None,
        "last_seen": agg.last_seen.isoformat() if agg.last_seen else None,
    }
