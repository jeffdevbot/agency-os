"""Structured Monthly P&L email brief builder.

Builds a deterministic, read-only briefing envelope that can later be rendered
into a client-facing monthly P&L highlights email.
"""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from typing import Any

from supabase import Client

from .profiles import PNLNotFoundError, PNLProfileService, PNLValidationError
from .report import EXPENSE_BUCKETS, REFUND_BUCKETS, REVENUE_BUCKETS, PNLReportService, _month_range

ZERO = Decimal("0")
HUNDRED = Decimal("100")
_MARKETPLACE_ORDER = ["US", "CA", "UK", "MX", "DE", "FR", "ES", "IT", "JP", "AU"]
_SNAPSHOT_KEYS = [
    ("total_gross_revenue", "Total Gross Revenue", "amount"),
    ("total_refunds", "Total Refunds", "amount"),
    ("total_net_revenue", "Total Net Revenue", "amount"),
    ("advertising", "Advertising", "amount"),
    ("advertising_pct_of_net_revenue", "Advertising % of Net Revenue", "percentage"),
    ("net_earnings", "Net Earnings", "amount"),
    ("net_earnings_pct_of_net_revenue", "Net Earnings % of Net Revenue", "percentage"),
]
_REFUND_KEYS = {key for key, *_rest in REFUND_BUCKETS} | {"total_refunds"}
_EXPENSE_KEYS = {key for key, *_rest in EXPENSE_BUCKETS} | {"total_expenses", "payout"}
_POSITIVE_SHARE_LOWER_IS_BETTER = {
    "advertising",
    "total_refunds",
    "fba_monthly_storage_fees",
    "fba_long_term_storage_fees",
    "fba_removal_order_fees",
    "inbound_shipping_and_duties",
    "inbound_placement_and_defect_fees",
    "referral_fees",
    "fba_fees",
    "promotions_fees",
}
_POSITIVE_ABSOLUTE_HIGHER_IS_BETTER = {
    "total_net_revenue",
    "total_gross_revenue",
    "gross_profit",
    "net_earnings",
}
_SHARE_PRIORITY_MULTIPLIER = 5


def _q_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.quantize(Decimal("0.01")), "f")


def _month_label(month_iso: str | None) -> str | None:
    if not month_iso:
        return None
    parsed = date.fromisoformat(month_iso)
    return parsed.strftime("%b %Y")


def _previous_month(month_start: date) -> date:
    if month_start.month == 1:
        return date(month_start.year - 1, 12, 1)
    return date(month_start.year, month_start.month - 1, 1)


def _prior_year_month(month_start: date) -> date:
    return date(month_start.year - 1, month_start.month, 1)


def _marketplace_sort_key(code: str) -> tuple[int, str]:
    code_upper = str(code or "").upper()
    try:
        idx = _MARKETPLACE_ORDER.index(code_upper)
    except ValueError:
        idx = len(_MARKETPLACE_ORDER)
    return (idx, code_upper)


def _to_decimal(value: Any) -> Decimal:
    if value in (None, ""):
        return ZERO
    return Decimal(str(value))


def _sum_months(row: dict[str, Any] | None, months: list[str]) -> Decimal:
    if not row:
        return ZERO
    month_values = row.get("months") or {}
    total = ZERO
    for month in months:
        total += _to_decimal(month_values.get(month))
    return total


def _amount_for_growth(key: str, category: str | None, amount: Decimal) -> Decimal:
    if category in {"refunds", "expenses"} or key in _REFUND_KEYS or key in _EXPENSE_KEYS:
        return abs(amount)
    return amount


def _share_of_net_revenue(key: str, category: str | None, amount: Decimal, net_revenue: Decimal) -> Decimal | None:
    if net_revenue == ZERO:
        return None
    if category in {"refunds", "expenses"} or key in _REFUND_KEYS or key in _EXPENSE_KEYS:
        return (abs(amount) / net_revenue) * HUNDRED
    return (amount / net_revenue) * HUNDRED


def _percent_change(current: Decimal, prior: Decimal) -> Decimal | None:
    if prior == ZERO:
        return None
    return ((current - prior) / prior) * HUNDRED


def _pp_change(current: Decimal | None, prior: Decimal | None) -> Decimal | None:
    if current is None or prior is None:
        return None
    return current - prior


def _comparison_mode_used(
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


def _dedupe_warnings(*warning_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


class PNLEmailBriefService:
    def __init__(self, db: Client) -> None:
        self.db = db
        self.profile_service = PNLProfileService(db)
        self.report_service = PNLReportService(db)

    async def build_client_brief_async(
        self,
        client_id: str,
        report_month: str,
        *,
        marketplace_codes: list[str] | None = None,
        comparison_mode: str = "auto",
    ) -> dict[str, Any]:
        normalized_client_id = str(client_id or "").strip()
        if not normalized_client_id:
            raise PNLValidationError("client_id is required")

        if comparison_mode not in {"auto", "yoy_only", "mom_only"}:
            raise PNLValidationError("comparison_mode must be one of auto, yoy_only, mom_only")

        try:
            report_month_date = date.fromisoformat(report_month)
        except ValueError as exc:
            raise PNLValidationError("report_month must be YYYY-MM-01") from exc
        if report_month_date.day != 1:
            raise PNLValidationError("report_month must be the first day of the month")

        client = await asyncio.to_thread(self._get_client, normalized_client_id)
        profiles = await asyncio.to_thread(self.profile_service.list_profiles, normalized_client_id)
        requested_marketplaces = {
            str(code or "").strip().upper()
            for code in (marketplace_codes or [])
            if str(code or "").strip()
        }
        if requested_marketplaces:
            profiles = [
                row for row in profiles
                if str(row.get("marketplace_code") or "").strip().upper() in requested_marketplaces
            ]
        active_months_by_profile = await asyncio.to_thread(self._load_active_months_by_profile)

        selected_profiles: list[dict[str, Any]] = []
        unavailable_marketplaces: list[str] = []
        report_month_iso = report_month_date.isoformat()
        for profile in profiles:
            if not isinstance(profile, dict):
                continue
            profile_id = str(profile.get("id") or "").strip()
            marketplace_code = str(profile.get("marketplace_code") or "").strip().upper()
            if not profile_id:
                continue
            active_months = active_months_by_profile.get(profile_id, set())
            if report_month_iso in active_months:
                selected_profiles.append(profile)
            elif marketplace_code:
                unavailable_marketplaces.append(marketplace_code)

        if not selected_profiles:
            raise PNLNotFoundError(
                f"No Monthly P&L profiles with active data found for client {normalized_client_id} in {report_month_iso}"
            )

        selected_profiles.sort(
            key=lambda row: _marketplace_sort_key(str(row.get("marketplace_code") or ""))
        )

        sections: list[dict[str, Any]] = []
        for profile in selected_profiles:
            sections.append(
                await self._build_profile_section_async(
                    profile,
                    report_month_date=report_month_date,
                    active_months=active_months_by_profile.get(str(profile.get("id") or "").strip(), set()),
                    comparison_mode=comparison_mode,
                )
            )

        overall_summary_points = self._build_overall_summary_points(sections)
        top_level_notes = list(overall_summary_points)
        if unavailable_marketplaces:
            top_level_notes.append(
                "No active data for the selected report month in: "
                + ", ".join(sorted(set(unavailable_marketplaces), key=_marketplace_sort_key))
            )

        return {
            "client": {
                "client_id": normalized_client_id,
                "client_name": str(client.get("name") or "").strip() or "Client",
            },
            "report_month": report_month_iso,
            "report_month_label": _month_label(report_month_iso),
            "comparison_mode_requested": comparison_mode,
            "comparison_mode_used": self._overall_comparison_mode(sections),
            "marketplace_scope": [section["marketplace_code"] for section in sections],
            "sections": sections,
            "overall_summary_points": overall_summary_points,
            "data_quality_notes": top_level_notes,
            "unavailable_marketplaces": sorted(
                set(unavailable_marketplaces),
                key=_marketplace_sort_key,
            ),
        }

    def _get_client(self, client_id: str) -> dict[str, Any]:
        response = (
            self.db.table("agency_clients")
            .select("id, name")
            .eq("id", client_id)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise PNLNotFoundError(f"Client {client_id} not found")
        return rows[0]

    def _load_active_months_by_profile(self) -> dict[str, set[str]]:
        response = (
            self.db.table("monthly_pnl_import_months")
            .select("profile_id, entry_month")
            .eq("is_active", True)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        by_profile: dict[str, set[str]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            profile_id = str(row.get("profile_id") or "").strip()
            entry_month = str(row.get("entry_month") or "").strip()
            if not profile_id or not entry_month:
                continue
            by_profile.setdefault(profile_id, set()).add(entry_month)
        return by_profile

    async def _build_profile_section_async(
        self,
        profile: dict[str, Any],
        *,
        report_month_date: date,
        active_months: set[str],
        comparison_mode: str,
    ) -> dict[str, Any]:
        profile_id = str(profile.get("id") or "").strip()
        report_month_iso = report_month_date.isoformat()
        current_ytd_start = date(report_month_date.year, 1, 1)
        previous_month_date = _previous_month(report_month_date)
        prior_year_month_date = _prior_year_month(report_month_date)

        current_ytd_months = _month_range(current_ytd_start, report_month_date)
        prior_ytd_start = date(prior_year_month_date.year, 1, 1)
        prior_ytd_months = _month_range(prior_ytd_start, prior_year_month_date)

        latest_month_has_yoy = prior_year_month_date.isoformat() in active_months
        has_previous_month = previous_month_date.isoformat() in active_months
        current_ytd_complete = all(month in active_months for month in current_ytd_months)
        ytd_has_yoy = current_ytd_complete and all(month in active_months for month in prior_ytd_months)

        report_tasks: dict[str, Any] = {
            "latest": self.report_service.build_report_async(
                profile_id,
                filter_mode="range",
                start_month=report_month_iso,
                end_month=report_month_iso,
            ),
            "ytd": self.report_service.build_report_async(
                profile_id,
                filter_mode="range",
                start_month=current_ytd_start.isoformat(),
                end_month=report_month_iso,
            ),
        }
        if has_previous_month:
            previous_month_iso = previous_month_date.isoformat()
            report_tasks["previous"] = self.report_service.build_report_async(
                profile_id,
                filter_mode="range",
                start_month=previous_month_iso,
                end_month=previous_month_iso,
            )
        if latest_month_has_yoy:
            prior_year_month_iso = prior_year_month_date.isoformat()
            report_tasks["latest_prior_year"] = self.report_service.build_report_async(
                profile_id,
                filter_mode="range",
                start_month=prior_year_month_iso,
                end_month=prior_year_month_iso,
            )
        if ytd_has_yoy:
            report_tasks["ytd_prior_year"] = self.report_service.build_report_async(
                profile_id,
                filter_mode="range",
                start_month=prior_ytd_start.isoformat(),
                end_month=prior_year_month_date.isoformat(),
            )

        reports: dict[str, Any] = {}
        for name, task in report_tasks.items():
            reports[name] = await task

        latest_report = reports["latest"]
        ytd_report = reports["ytd"]
        previous_report = reports.get("previous")
        latest_prior_year_report = reports.get("latest_prior_year")
        ytd_prior_year_report = reports.get("ytd_prior_year")

        latest_index = self._index_report(latest_report)
        ytd_index = self._index_report(ytd_report)
        previous_index = self._index_report(previous_report)
        latest_prior_year_index = self._index_report(latest_prior_year_report)
        ytd_prior_year_index = self._index_report(ytd_prior_year_report)

        comparison_mode_used = _comparison_mode_used(
            comparison_mode,
            latest_month_has_yoy=latest_month_has_yoy,
            ytd_has_yoy=ytd_has_yoy,
            has_previous_month=has_previous_month,
        )

        warnings = _dedupe_warnings(
            list(latest_report.get("warnings") or []),
            list(ytd_report.get("warnings") or []),
        )
        data_quality_notes = self._build_data_quality_notes(
            report_month_iso=report_month_iso,
            latest_month_has_yoy=latest_month_has_yoy,
            ytd_has_yoy=ytd_has_yoy,
            has_previous_month=has_previous_month,
            current_ytd_complete=current_ytd_complete,
            warnings=warnings,
        )

        component_metrics = self._build_component_metrics(
            latest_index=latest_index,
            latest_month=report_month_iso,
            latest_prior_year_index=latest_prior_year_index,
            latest_prior_year_month=prior_year_month_date.isoformat() if latest_month_has_yoy else None,
            previous_index=previous_index,
            previous_month=previous_month_date.isoformat() if has_previous_month else None,
            ytd_index=ytd_index,
            ytd_months=list(ytd_report.get("months") or []),
            ytd_prior_year_index=ytd_prior_year_index,
            ytd_prior_year_months=list(ytd_prior_year_report.get("months") or []) if ytd_prior_year_report else [],
        )
        snapshot_metrics = [
            metric for metric in component_metrics
            if metric["key"] in {key for key, *_rest in _SNAPSHOT_KEYS}
        ]

        positive_drivers, negative_drivers = self._rank_driver_candidates(
            component_metrics=component_metrics,
            comparison_mode_used=comparison_mode_used,
            report_month_label=_month_label(report_month_iso) or report_month_iso,
            prior_year_month_label=_month_label(prior_year_month_date.isoformat()),
            previous_month_label=_month_label(previous_month_date.isoformat()) if has_previous_month else None,
        )
        financial_health = self._build_financial_health(component_metrics, warnings)

        return {
            "profile_id": profile_id,
            "client_id": str(profile.get("client_id") or "").strip() or None,
            "marketplace_code": str(profile.get("marketplace_code") or "").strip().upper(),
            "currency_code": str(profile.get("currency_code") or "").strip().upper() or None,
            "status": str(profile.get("status") or "").strip() or None,
            "comparison_mode_used": comparison_mode_used,
            "latest_month_has_yoy": latest_month_has_yoy,
            "ytd_has_yoy": ytd_has_yoy,
            "has_previous_month": has_previous_month,
            "periods": {
                "latest_month": report_month_iso,
                "latest_month_label": _month_label(report_month_iso),
                "previous_month": previous_month_date.isoformat() if has_previous_month else None,
                "previous_month_label": _month_label(previous_month_date.isoformat()) if has_previous_month else None,
                "latest_month_prior_year": prior_year_month_date.isoformat() if latest_month_has_yoy else None,
                "latest_month_prior_year_label": (
                    _month_label(prior_year_month_date.isoformat()) if latest_month_has_yoy else None
                ),
                "ytd_start": current_ytd_start.isoformat(),
                "ytd_end": report_month_iso,
                "ytd_prior_year_start": prior_ytd_start.isoformat() if ytd_has_yoy else None,
                "ytd_prior_year_end": prior_year_month_date.isoformat() if ytd_has_yoy else None,
            },
            "snapshot_metrics": snapshot_metrics,
            "component_metrics": component_metrics,
            "positive_drivers": positive_drivers,
            "negative_drivers": negative_drivers,
            "financial_health": financial_health,
            "warnings": warnings,
            "data_quality_notes": data_quality_notes,
            "report_refs": [
                {
                    "profile_id": profile_id,
                    "report_kind": "latest_month",
                    "months_used": list(latest_report.get("months") or []),
                },
                {
                    "profile_id": profile_id,
                    "report_kind": "ytd",
                    "months_used": list(ytd_report.get("months") or []),
                },
            ],
        }

    def _index_report(self, report: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
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

    def _build_component_metrics(
        self,
        *,
        latest_index: dict[str, dict[str, Any]],
        latest_month: str,
        latest_prior_year_index: dict[str, dict[str, Any]],
        latest_prior_year_month: str | None,
        previous_index: dict[str, dict[str, Any]],
        previous_month: str | None,
        ytd_index: dict[str, dict[str, Any]],
        ytd_months: list[str],
        ytd_prior_year_index: dict[str, dict[str, Any]],
        ytd_prior_year_months: list[str],
    ) -> list[dict[str, Any]]:
        latest_net_revenue = _to_decimal(
            (latest_index.get("total_net_revenue") or {}).get("months", {}).get(latest_month)
        )
        latest_prior_net_revenue = _to_decimal(
            (latest_prior_year_index.get("total_net_revenue") or {}).get("months", {}).get(latest_prior_year_month)
        )
        previous_net_revenue = _to_decimal(
            (previous_index.get("total_net_revenue") or {}).get("months", {}).get(previous_month)
        )
        ytd_net_revenue = _sum_months(ytd_index.get("total_net_revenue"), ytd_months)
        ytd_prior_net_revenue = _sum_months(ytd_prior_year_index.get("total_net_revenue"), ytd_prior_year_months)

        all_keys = {
            *latest_index.keys(),
            *ytd_index.keys(),
            *latest_prior_year_index.keys(),
            *ytd_prior_year_index.keys(),
            *previous_index.keys(),
            "advertising_pct_of_net_revenue",
            "net_earnings_pct_of_net_revenue",
        }
        metrics: list[dict[str, Any]] = []
        for key in sorted(all_keys):
            metric = self._build_metric_row(
                key=key,
                latest_index=latest_index,
                latest_month=latest_month,
                latest_net_revenue=latest_net_revenue,
                latest_prior_year_index=latest_prior_year_index,
                latest_prior_year_month=latest_prior_year_month,
                latest_prior_net_revenue=latest_prior_net_revenue,
                previous_index=previous_index,
                previous_month=previous_month,
                previous_net_revenue=previous_net_revenue,
                ytd_index=ytd_index,
                ytd_months=ytd_months,
                ytd_net_revenue=ytd_net_revenue,
                ytd_prior_year_index=ytd_prior_year_index,
                ytd_prior_year_months=ytd_prior_year_months,
                ytd_prior_net_revenue=ytd_prior_net_revenue,
            )
            if metric is not None:
                metrics.append(metric)
        metrics.sort(key=lambda row: row.get("label") or row.get("key") or "")
        return metrics

    def _build_metric_row(
        self,
        *,
        key: str,
        latest_index: dict[str, dict[str, Any]],
        latest_month: str,
        latest_net_revenue: Decimal,
        latest_prior_year_index: dict[str, dict[str, Any]],
        latest_prior_year_month: str | None,
        latest_prior_net_revenue: Decimal,
        previous_index: dict[str, dict[str, Any]],
        previous_month: str | None,
        previous_net_revenue: Decimal,
        ytd_index: dict[str, dict[str, Any]],
        ytd_months: list[str],
        ytd_net_revenue: Decimal,
        ytd_prior_year_index: dict[str, dict[str, Any]],
        ytd_prior_year_months: list[str],
        ytd_prior_net_revenue: Decimal,
    ) -> dict[str, Any] | None:
        if key == "advertising_pct_of_net_revenue":
            source_key = "advertising"
            label = "Advertising % of Net Revenue"
            category = "percentage"
            latest_value = _share_of_net_revenue(
                source_key,
                (latest_index.get(source_key) or {}).get("category"),
                _to_decimal((latest_index.get(source_key) or {}).get("months", {}).get(latest_month)),
                latest_net_revenue,
            )
            latest_prior_value = _share_of_net_revenue(
                source_key,
                (latest_prior_year_index.get(source_key) or {}).get("category"),
                _to_decimal((latest_prior_year_index.get(source_key) or {}).get("months", {}).get(latest_prior_year_month)),
                latest_prior_net_revenue,
            ) if latest_prior_year_month else None
            previous_value = _share_of_net_revenue(
                source_key,
                (previous_index.get(source_key) or {}).get("category"),
                _to_decimal((previous_index.get(source_key) or {}).get("months", {}).get(previous_month)),
                previous_net_revenue,
            ) if previous_month else None
            ytd_value = _share_of_net_revenue(
                source_key,
                (ytd_index.get(source_key) or {}).get("category"),
                _sum_months(ytd_index.get(source_key), ytd_months),
                ytd_net_revenue,
            )
            ytd_prior_value = _share_of_net_revenue(
                source_key,
                (ytd_prior_year_index.get(source_key) or {}).get("category"),
                _sum_months(ytd_prior_year_index.get(source_key), ytd_prior_year_months),
                ytd_prior_net_revenue,
            ) if ytd_prior_year_months else None
            return {
                "key": key,
                "source_key": source_key,
                "label": label,
                "category": category,
                "value_kind": "percentage",
                "latest_month_value": _q_decimal(latest_value),
                "latest_month_yoy_percent_change": None,
                "latest_month_yoy_pp_change": _q_decimal(_pp_change(latest_value, latest_prior_value)),
                "latest_month_mom_percent_change": None,
                "latest_month_mom_pp_change": _q_decimal(_pp_change(latest_value, previous_value)),
                "ytd_value": _q_decimal(ytd_value),
                "ytd_yoy_percent_change": None,
                "ytd_yoy_pp_change": _q_decimal(_pp_change(ytd_value, ytd_prior_value)),
            }
        if key == "net_earnings_pct_of_net_revenue":
            source_key = "net_earnings"
            label = "Net Earnings % of Net Revenue"
            category = "percentage"
            latest_value = _share_of_net_revenue(
                source_key,
                (latest_index.get(source_key) or {}).get("category"),
                _to_decimal((latest_index.get(source_key) or {}).get("months", {}).get(latest_month)),
                latest_net_revenue,
            )
            latest_prior_value = _share_of_net_revenue(
                source_key,
                (latest_prior_year_index.get(source_key) or {}).get("category"),
                _to_decimal((latest_prior_year_index.get(source_key) or {}).get("months", {}).get(latest_prior_year_month)),
                latest_prior_net_revenue,
            ) if latest_prior_year_month else None
            previous_value = _share_of_net_revenue(
                source_key,
                (previous_index.get(source_key) or {}).get("category"),
                _to_decimal((previous_index.get(source_key) or {}).get("months", {}).get(previous_month)),
                previous_net_revenue,
            ) if previous_month else None
            ytd_value = _share_of_net_revenue(
                source_key,
                (ytd_index.get(source_key) or {}).get("category"),
                _sum_months(ytd_index.get(source_key), ytd_months),
                ytd_net_revenue,
            )
            ytd_prior_value = _share_of_net_revenue(
                source_key,
                (ytd_prior_year_index.get(source_key) or {}).get("category"),
                _sum_months(ytd_prior_year_index.get(source_key), ytd_prior_year_months),
                ytd_prior_net_revenue,
            ) if ytd_prior_year_months else None
            return {
                "key": key,
                "source_key": source_key,
                "label": label,
                "category": category,
                "value_kind": "percentage",
                "latest_month_value": _q_decimal(latest_value),
                "latest_month_yoy_percent_change": None,
                "latest_month_yoy_pp_change": _q_decimal(_pp_change(latest_value, latest_prior_value)),
                "latest_month_mom_percent_change": None,
                "latest_month_mom_pp_change": _q_decimal(_pp_change(latest_value, previous_value)),
                "ytd_value": _q_decimal(ytd_value),
                "ytd_yoy_percent_change": None,
                "ytd_yoy_pp_change": _q_decimal(_pp_change(ytd_value, ytd_prior_value)),
            }

        latest_row = latest_index.get(key)
        ytd_row = ytd_index.get(key)
        latest_prior_row = latest_prior_year_index.get(key)
        previous_row = previous_index.get(key)
        ytd_prior_row = ytd_prior_year_index.get(key)

        row = latest_row or ytd_row or latest_prior_row or previous_row or ytd_prior_row
        if not row:
            return None

        category = str(row.get("category") or "").strip() or None
        label = str(row.get("label") or key).strip()

        latest_amount = _to_decimal((latest_row or {}).get("months", {}).get(latest_month))
        latest_prior_amount = _to_decimal((latest_prior_row or {}).get("months", {}).get(latest_prior_year_month))
        previous_amount = _to_decimal((previous_row or {}).get("months", {}).get(previous_month))
        ytd_amount = _sum_months(ytd_row, ytd_months)
        ytd_prior_amount = _sum_months(ytd_prior_row, ytd_prior_year_months)

        latest_display_amount = _amount_for_growth(key, category, latest_amount)
        latest_prior_display_amount = _amount_for_growth(key, category, latest_prior_amount)
        previous_display_amount = _amount_for_growth(key, category, previous_amount)
        ytd_display_amount = _amount_for_growth(key, category, ytd_amount)
        ytd_prior_display_amount = _amount_for_growth(key, category, ytd_prior_amount)

        latest_share = _share_of_net_revenue(key, category, latest_amount, latest_net_revenue)
        latest_prior_share = _share_of_net_revenue(
            key, category, latest_prior_amount, latest_prior_net_revenue
        ) if latest_prior_year_month else None
        previous_share = _share_of_net_revenue(
            key, category, previous_amount, previous_net_revenue
        ) if previous_month else None
        ytd_share = _share_of_net_revenue(key, category, ytd_amount, ytd_net_revenue)
        ytd_prior_share = _share_of_net_revenue(
            key, category, ytd_prior_amount, ytd_prior_net_revenue
        ) if ytd_prior_year_months else None

        return {
            "key": key,
            "source_key": key,
            "label": label,
            "category": category,
            "value_kind": "amount",
            "latest_month_value": _q_decimal(latest_amount),
            "latest_month_share_of_net_revenue": _q_decimal(latest_share),
            "latest_month_yoy_percent_change": _q_decimal(
                _percent_change(latest_display_amount, latest_prior_display_amount)
            ),
            "latest_month_yoy_pp_change": _q_decimal(_pp_change(latest_share, latest_prior_share)),
            "latest_month_mom_percent_change": _q_decimal(
                _percent_change(latest_display_amount, previous_display_amount)
            ),
            "latest_month_mom_pp_change": _q_decimal(_pp_change(latest_share, previous_share)),
            "ytd_value": _q_decimal(ytd_amount),
            "ytd_share_of_net_revenue": _q_decimal(ytd_share),
            "ytd_yoy_percent_change": _q_decimal(_percent_change(ytd_display_amount, ytd_prior_display_amount)),
            "ytd_yoy_pp_change": _q_decimal(_pp_change(ytd_share, ytd_prior_share)),
        }

    def _build_data_quality_notes(
        self,
        *,
        report_month_iso: str,
        latest_month_has_yoy: bool,
        ytd_has_yoy: bool,
        has_previous_month: bool,
        current_ytd_complete: bool,
        warnings: list[dict[str, Any]],
    ) -> list[str]:
        notes: list[str] = []
        if not latest_month_has_yoy:
            notes.append(f"Latest-month YoY is unavailable for {_month_label(report_month_iso)}.")
        if not ytd_has_yoy:
            notes.append(f"YTD YoY is unavailable for {_month_label(report_month_iso)}.")
        if not has_previous_month:
            notes.append(f"Previous-month comparison is unavailable for {_month_label(report_month_iso)}.")
        if not current_ytd_complete:
            notes.append("Current-year YTD coverage is incomplete, so YTD comparisons should be treated cautiously.")
        for warning in warnings:
            message = str(warning.get("message") or "").strip()
            months = [str(month) for month in warning.get("months") or [] if str(month)]
            if message and months:
                notes.append(f"{message}: {', '.join(_month_label(month) or month for month in months)}.")
            elif message:
                notes.append(message)
        return notes

    def _rank_driver_candidates(
        self,
        *,
        component_metrics: list[dict[str, Any]],
        comparison_mode_used: str,
        report_month_label: str,
        prior_year_month_label: str | None,
        previous_month_label: str | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        by_key = {str(metric.get("key") or ""): metric for metric in component_metrics}

        if comparison_mode_used.startswith("yoy"):
            basis = "yoy"
            basis_label = prior_year_month_label or "prior year"
        elif comparison_mode_used.startswith("mom"):
            basis = "mom"
            basis_label = previous_month_label or "previous month"
        else:
            basis = "descriptive"
            basis_label = report_month_label

        positives: list[dict[str, Any]] = []
        negatives: list[dict[str, Any]] = []

        def add_share_candidate(metric_key: str, title: str, *, lower_is_better: bool) -> None:
            metric = by_key.get(metric_key)
            if not metric:
                return
            latest_value = _to_decimal(metric.get("latest_month_value"))
            latest_pp_field = (
                metric.get("latest_month_yoy_pp_change") if basis == "yoy"
                else metric.get("latest_month_mom_pp_change")
            )
            latest_pct_field = (
                metric.get("latest_month_yoy_percent_change") if basis == "yoy"
                else metric.get("latest_month_mom_percent_change")
            )
            if basis == "descriptive":
                if metric_key == "net_earnings_pct_of_net_revenue" and latest_value >= Decimal("20"):
                    positives.append({
                        "title": title,
                        "evidence": f"{title} is strong at {latest_value.quantize(Decimal('0.1'))}% in {report_month_label}.",
                        "_score": float(latest_value),
                    })
                elif metric_key == "advertising_pct_of_net_revenue" and latest_value >= Decimal("25"):
                    negatives.append({
                        "title": title,
                        "evidence": f"{title} is elevated at {latest_value.quantize(Decimal('0.1'))}% of Net Revenue in {report_month_label}.",
                        "_score": float(latest_value),
                    })
                return
            pp_change = _to_decimal(latest_pp_field)
            if latest_pp_field is None:
                return
            improved = pp_change < ZERO if lower_is_better else pp_change > ZERO
            evidence = (
                f"{title} changed {abs(pp_change).quantize(Decimal('0.1'))} p.p. "
                f"to {latest_value.quantize(Decimal('0.1'))}% versus {basis_label}."
            )
            candidate = {
                "title": title,
                "evidence": evidence,
                "_score": float(abs(pp_change) * _SHARE_PRIORITY_MULTIPLIER),
            }
            (positives if improved else negatives).append(candidate)

            if latest_pct_field is not None and metric_key == "total_net_revenue":
                pass

        def add_amount_candidate(metric_key: str, title: str, *, higher_is_better: bool) -> None:
            metric = by_key.get(metric_key)
            if not metric:
                return
            latest_value = _to_decimal(metric.get("latest_month_value"))
            pct_field = (
                metric.get("latest_month_yoy_percent_change") if basis == "yoy"
                else metric.get("latest_month_mom_percent_change")
            )
            if basis == "descriptive":
                if metric_key == "net_earnings" and latest_value < ZERO:
                    negatives.append({
                        "title": title,
                        "evidence": f"{title} was negative in {report_month_label} at {latest_value.quantize(Decimal('0.01'))}.",
                        "_score": float(abs(latest_value)),
                    })
                return
            if pct_field is None:
                return
            pct_change = _to_decimal(pct_field)
            improved = pct_change > ZERO if higher_is_better else pct_change < ZERO
            evidence = f"{title} changed {abs(pct_change).quantize(Decimal('0.1'))}% versus {basis_label}."
            candidate = {
                "title": title,
                "evidence": evidence,
                "_score": float(abs(pct_change)),
            }
            (positives if improved else negatives).append(candidate)

        add_amount_candidate("total_net_revenue", "Total Net Revenue", higher_is_better=True)
        add_amount_candidate("gross_profit", "Gross Profit", higher_is_better=True)
        add_amount_candidate("net_earnings", "Net Earnings", higher_is_better=True)
        add_share_candidate("net_earnings_pct_of_net_revenue", "Net Earnings margin", lower_is_better=False)
        add_share_candidate("advertising_pct_of_net_revenue", "Advertising share", lower_is_better=True)
        add_share_candidate("total_refunds", "Refund rate", lower_is_better=True)
        add_share_candidate("fba_monthly_storage_fees", "Monthly storage burden", lower_is_better=True)
        add_share_candidate("fba_long_term_storage_fees", "Long-term storage burden", lower_is_better=True)
        add_share_candidate("fba_removal_order_fees", "Removal-fee burden", lower_is_better=True)
        add_share_candidate("inbound_shipping_and_duties", "Inbound logistics burden", lower_is_better=True)
        add_share_candidate("inbound_placement_and_defect_fees", "Inbound placement burden", lower_is_better=True)

        positives.sort(key=lambda row: row["_score"], reverse=True)
        negatives.sort(key=lambda row: row["_score"], reverse=True)
        return (
            [{k: v for k, v in row.items() if not k.startswith("_")} for row in positives[:3]],
            [{k: v for k, v in row.items() if not k.startswith("_")} for row in negatives[:3]],
        )

    def _build_financial_health(
        self,
        component_metrics: list[dict[str, Any]],
        warnings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        by_key = {str(metric.get("key") or ""): metric for metric in component_metrics}
        margin = _to_decimal((by_key.get("net_earnings_pct_of_net_revenue") or {}).get("latest_month_value"))
        has_missing_cogs = any(str(warning.get("type") or "") == "missing_cogs" for warning in warnings)

        if has_missing_cogs:
            verdict = "Caution"
            reason = "COGS is missing for sold SKUs, so profitability is overstated."
        elif margin >= Decimal("20"):
            verdict = "Excellent"
            reason = f"Net Earnings margin is strong at {margin.quantize(Decimal('0.1'))}%."
        elif margin >= Decimal("10"):
            verdict = "Good"
            reason = f"Net Earnings margin remains healthy at {margin.quantize(Decimal('0.1'))}%."
        elif margin >= ZERO:
            verdict = "Mixed"
            reason = f"Net Earnings margin is positive but limited at {margin.quantize(Decimal('0.1'))}%."
        else:
            verdict = "Warning"
            reason = f"The latest month is loss-making at {margin.quantize(Decimal('0.1'))}% Net Earnings margin."

        return {
            "verdict": verdict,
            "reason": reason,
        }

    def _build_overall_summary_points(self, sections: list[dict[str, Any]]) -> list[str]:
        if not sections:
            return []

        def _margin(section: dict[str, Any]) -> Decimal:
            snapshot = {
                str(metric.get("key") or ""): metric
                for metric in section.get("snapshot_metrics") or []
            }
            return _to_decimal(
                (snapshot.get("net_earnings_pct_of_net_revenue") or {}).get("latest_month_value")
            )

        def _revenue_growth(section: dict[str, Any]) -> Decimal | None:
            snapshot = {
                str(metric.get("key") or ""): metric
                for metric in section.get("snapshot_metrics") or []
            }
            value = (snapshot.get("total_net_revenue") or {}).get("latest_month_yoy_percent_change")
            return None if value is None else _to_decimal(value)

        best_margin = max(sections, key=_margin)
        worst_margin = min(sections, key=_margin)
        points = [
            f"Best latest-month Net Earnings margin: {best_margin['marketplace_code']} at {_margin(best_margin).quantize(Decimal('0.1'))}%.",
        ]
        if len(sections) > 1:
            points.append(
                f"Weakest latest-month Net Earnings margin: {worst_margin['marketplace_code']} at {_margin(worst_margin).quantize(Decimal('0.1'))}%."
            )

        yoy_sections = [section for section in sections if _revenue_growth(section) is not None]
        if yoy_sections:
            fastest = max(yoy_sections, key=lambda section: _revenue_growth(section) or ZERO)
            points.append(
                f"Fastest latest-month Net Revenue growth: {fastest['marketplace_code']} at {(_revenue_growth(fastest) or ZERO).quantize(Decimal('0.1'))}% YoY."
            )
        return points

    def _overall_comparison_mode(self, sections: list[dict[str, Any]]) -> str:
        modes = {str(section.get("comparison_mode_used") or "") for section in sections}
        if len(modes) == 1:
            return next(iter(modes))
        return "mixed"
