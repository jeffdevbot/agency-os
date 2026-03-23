"""Monthly P&L Year-over-Year report adapter."""

from __future__ import annotations

from datetime import date
from typing import Any

from supabase import Client

from .comparison import PNLComparisonService


class PNLYoYReportService:
    def __init__(self, db: Client) -> None:
        self.db = db
        self.comparison_service = PNLComparisonService(db)

    async def build_yoy_report_async(self, profile_id: str, *, year: int) -> dict[str, Any]:
        comparison = await self.comparison_service.build_year_comparison_async(profile_id, year=year)
        current_report = comparison["reports"]["current"]
        prior_report = comparison["reports"]["prior"]
        current_index = comparison["indexes"]["current"]
        prior_index = comparison["indexes"]["prior"]
        current_month_keys = list(current_report.get("months") or [])
        prior_month_keys = list(prior_report.get("months") or [])

        month_labels = [
            date.fromisoformat(month_iso).strftime("%b")
            for month_iso in current_month_keys
        ]

        ordered_keys: list[str] = []
        seen: set[str] = set()
        for report in (current_report, prior_report):
            for item in report.get("line_items") or []:
                if not isinstance(item, dict):
                    continue
                key = str(item.get("key") or "").strip()
                if key and key not in seen:
                    seen.add(key)
                    ordered_keys.append(key)

        line_items: list[dict[str, Any]] = []
        for key in ordered_keys:
            current_row = current_index.get(key)
            prior_row = prior_index.get(key)
            row = current_row or prior_row or {}
            line_items.append({
                "key": key,
                "label": str(row.get("label") or key),
                "category": str(row.get("category") or ""),
                "is_derived": bool(row.get("is_derived")),
                "current": (current_row or {}).get("months") or {},
                "prior": (prior_row or {}).get("months") or {},
            })

        warnings: list[dict[str, Any]] = []
        for warning in current_report.get("warnings") or []:
            if isinstance(warning, dict):
                warnings.append({**warning, "year": comparison["current_year"]})
        for warning in prior_report.get("warnings") or []:
            if isinstance(warning, dict):
                warnings.append({**warning, "year": comparison["prior_year"]})

        return {
            "profile": current_report["profile"],
            "current_year": comparison["current_year"],
            "prior_year": comparison["prior_year"],
            "months": month_labels,
            "current_month_keys": current_month_keys,
            "prior_month_keys": prior_month_keys,
            "line_items": line_items,
            "warnings": warnings,
            "periods": comparison["periods"],
        }
