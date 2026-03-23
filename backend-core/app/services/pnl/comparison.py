"""Shared Monthly P&L comparison layer.

This service owns reusable comparison-window logic for Monthly P&L so that
multiple surfaces can share the same definition of YoY and MoM availability.
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

from supabase import Client

from .profiles import PNLNotFoundError, PNLValidationError
from .report import PNLReportService, _month_range


def previous_month(month_start: date) -> date:
    if month_start.month == 1:
        return date(month_start.year - 1, 12, 1)
    return date(month_start.year, month_start.month - 1, 1)


def prior_year_month(month_start: date) -> date:
    return date(month_start.year - 1, month_start.month, 1)


def comparison_mode_used(
    requested: str,
    *,
    latest_month_has_yoy: bool,
    ytd_has_yoy: bool,
    has_previous_month: bool,
) -> str:
    if requested == "yoy_only":
        if latest_month_has_yoy or ytd_has_yoy:
            return "yoy_only"
        return "descriptive"
    if requested == "mom_only":
        return "mom_only" if has_previous_month else "descriptive"
    if latest_month_has_yoy or ytd_has_yoy:
        return "yoy_preferred"
    if has_previous_month:
        return "mom_fallback"
    return "descriptive"


def index_report(report: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(report, dict):
        return {}
    indexed: dict[str, dict[str, Any]] = {}
    for row in report.get("line_items") or []:
        if not isinstance(row, dict):
            continue
        key = str(row.get("key") or "").strip()
        if key:
            indexed[key] = row
    return indexed


def dedupe_warnings(*warning_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    merged: list[dict[str, Any]] = []
    for warnings in warning_groups:
        for warning in warnings:
            if not isinstance(warning, dict):
                continue
            key = (
                warning.get("type"),
                tuple(str(month) for month in warning.get("months") or []),
                warning.get("message"),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(warning)
    return merged


class PNLComparisonService:
    def __init__(self, db: Client) -> None:
        self.db = db
        self.report_service = PNLReportService(db)

    async def build_month_comparison_async(
        self,
        profile_id: str,
        *,
        report_month_date: date,
        active_months: set[str],
        comparison_mode: str = "auto",
    ) -> dict[str, Any]:
        if comparison_mode not in {"auto", "yoy_only", "mom_only"}:
            raise PNLValidationError("comparison_mode must be one of auto, yoy_only, mom_only")

        report_month_iso = report_month_date.isoformat()
        current_ytd_start = date(report_month_date.year, 1, 1)
        previous_month_date = previous_month(report_month_date)
        prior_year_month_date = prior_year_month(report_month_date)

        current_ytd_months = _month_range(current_ytd_start, report_month_date)
        prior_ytd_start = date(prior_year_month_date.year, 1, 1)
        prior_ytd_months = _month_range(prior_ytd_start, prior_year_month_date)

        latest_month_has_yoy = prior_year_month_date.isoformat() in active_months
        has_previous_month = previous_month_date.isoformat() in active_months
        current_ytd_complete = all(month in active_months for month in current_ytd_months)
        ytd_has_yoy = current_ytd_complete and all(month in active_months for month in prior_ytd_months)

        latest_report = await self.report_service.build_report_async(
            profile_id,
            filter_mode="range",
            start_month=report_month_iso,
            end_month=report_month_iso,
        )
        ytd_report = await self.report_service.build_report_async(
            profile_id,
            filter_mode="range",
            start_month=current_ytd_start.isoformat(),
            end_month=report_month_iso,
        )

        previous_report = None
        if has_previous_month:
            previous_month_iso = previous_month_date.isoformat()
            previous_report = await self.report_service.build_report_async(
                profile_id,
                filter_mode="range",
                start_month=previous_month_iso,
                end_month=previous_month_iso,
            )

        latest_prior_year_report = None
        if latest_month_has_yoy:
            prior_year_month_iso = prior_year_month_date.isoformat()
            latest_prior_year_report = await self.report_service.build_report_async(
                profile_id,
                filter_mode="range",
                start_month=prior_year_month_iso,
                end_month=prior_year_month_iso,
            )

        ytd_prior_year_report = None
        if ytd_has_yoy:
            ytd_prior_year_report = await self.report_service.build_report_async(
                profile_id,
                filter_mode="range",
                start_month=prior_ytd_start.isoformat(),
                end_month=prior_year_month_date.isoformat(),
            )

        warnings = dedupe_warnings(
            list(latest_report.get("warnings") or []),
            list(ytd_report.get("warnings") or []),
        )

        return {
            "comparison_mode_requested": comparison_mode,
            "comparison_mode_used": comparison_mode_used(
                comparison_mode,
                latest_month_has_yoy=latest_month_has_yoy,
                ytd_has_yoy=ytd_has_yoy,
                has_previous_month=has_previous_month,
            ),
            "latest_month_has_yoy": latest_month_has_yoy,
            "ytd_has_yoy": ytd_has_yoy,
            "has_previous_month": has_previous_month,
            "current_ytd_complete": current_ytd_complete,
            "periods": {
                "latest_month": report_month_iso,
                "previous_month": previous_month_date.isoformat() if has_previous_month else None,
                "latest_month_prior_year": prior_year_month_date.isoformat() if latest_month_has_yoy else None,
                "ytd_start": current_ytd_start.isoformat(),
                "ytd_end": report_month_iso,
                "ytd_prior_year_start": prior_ytd_start.isoformat() if ytd_has_yoy else None,
                "ytd_prior_year_end": prior_year_month_date.isoformat() if ytd_has_yoy else None,
            },
            "reports": {
                "latest": latest_report,
                "ytd": ytd_report,
                "previous": previous_report,
                "latest_prior_year": latest_prior_year_report,
                "ytd_prior_year": ytd_prior_year_report,
            },
            "indexes": {
                "latest": index_report(latest_report),
                "ytd": index_report(ytd_report),
                "previous": index_report(previous_report),
                "latest_prior_year": index_report(latest_prior_year_report),
                "ytd_prior_year": index_report(ytd_prior_year_report),
            },
            "warnings": warnings,
        }

    async def build_year_comparison_async(
        self,
        profile_id: str,
        *,
        year: int,
    ) -> dict[str, Any]:
        active_months = await self._load_active_months_async(profile_id)
        year_months = sorted(month for month in active_months if month.startswith(f"{year:04d}-"))
        if not year_months:
            raise PNLNotFoundError(f"No active Monthly P&L data found for profile {profile_id} in {year}")

        current_end = date.fromisoformat(year_months[-1])
        current_start = date(year, 1, 1)
        prior_start = date(year - 1, 1, 1)
        prior_end = date(year - 1, current_end.month, 1)

        current_report = await self.report_service.build_report_async(
            profile_id,
            filter_mode="range",
            start_month=current_start.isoformat(),
            end_month=current_end.isoformat(),
        )
        prior_report = await self.report_service.build_report_async(
            profile_id,
            filter_mode="range",
            start_month=prior_start.isoformat(),
            end_month=prior_end.isoformat(),
        )

        return {
            "current_year": year,
            "prior_year": year - 1,
            "periods": {
                "current_start": current_start.isoformat(),
                "current_end": current_end.isoformat(),
                "prior_start": prior_start.isoformat(),
                "prior_end": prior_end.isoformat(),
            },
            "reports": {
                "current": current_report,
                "prior": prior_report,
            },
            "indexes": {
                "current": index_report(current_report),
                "prior": index_report(prior_report),
            },
            "warnings": dedupe_warnings(
                list(current_report.get("warnings") or []),
                list(prior_report.get("warnings") or []),
            ),
        }

    async def _load_active_months_async(self, profile_id: str) -> set[str]:
        return await asyncio.to_thread(self._load_active_months, profile_id)

    def _load_active_months(self, profile_id: str) -> set[str]:
        response = (
            self.db.table("monthly_pnl_import_months")
            .select("entry_month")
            .eq("profile_id", profile_id)
            .eq("is_active", True)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        months: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            entry_month = str(row.get("entry_month") or "").strip()
            if entry_month:
                months.add(entry_month)
        return months
