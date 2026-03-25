from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from supabase import Client

from .amazon_ads_sync import OBSERVED_REPORT_RETENTION_DAYS
from .profiles import WBRProfileService, WBRValidationError

VALID_WBR_SYNC_SOURCE_TYPES = {
    "windsor_business",
    "windsor_inventory",
    "windsor_returns",
    "amazon_ads",
    "pacvue_import",
    "listing_import",
}

VALID_WBR_COVERAGE_SOURCE_TYPES = {
    "amazon_ads",
    "windsor_business",
}
WINDSOR_BUSINESS_COVERAGE_LOOKBACK_DAYS = 180


def _parse_iso_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _clip_range(
    start: date | None,
    end: date | None,
    *,
    window_start: date,
    window_end: date,
) -> tuple[date, date] | None:
    if start is None or end is None:
        return None
    clipped_start = max(start, window_start)
    clipped_end = min(end, window_end)
    if clipped_start > clipped_end:
        return None
    return clipped_start, clipped_end


def _merge_ranges(ranges: list[tuple[date, date]]) -> list[tuple[date, date]]:
    if not ranges:
        return []
    ordered = sorted(ranges, key=lambda item: (item[0], item[1]))
    merged: list[list[date]] = [[ordered[0][0], ordered[0][1]]]
    for start, end in ordered[1:]:
        last = merged[-1]
        if start <= last[1] + timedelta(days=1):
            if end > last[1]:
                last[1] = end
            continue
        merged.append([start, end])
    return [(start, end) for start, end in merged]


def _subtract_ranges(
    whole_start: date,
    whole_end: date,
    covered_ranges: list[tuple[date, date]],
) -> list[tuple[date, date]]:
    if whole_start > whole_end:
        return []
    if not covered_ranges:
        return [(whole_start, whole_end)]

    missing: list[tuple[date, date]] = []
    cursor = whole_start
    for covered_start, covered_end in covered_ranges:
        if covered_start > cursor:
            missing.append((cursor, covered_start - timedelta(days=1)))
        cursor = max(cursor, covered_end + timedelta(days=1))
        if cursor > whole_end:
            break
    if cursor <= whole_end:
        missing.append((cursor, whole_end))
    return missing


def _range_day_count(ranges: list[tuple[date, date]]) -> int:
    return sum((end - start).days + 1 for start, end in ranges)


class WBRSyncRunService:
    def __init__(self, db: Client) -> None:
        self.db = db
        self._profiles = WBRProfileService(db)

    def list_sync_runs(self, profile_id: str, *, source_type: str) -> list[dict[str, Any]]:
        self._profiles.get_profile(profile_id)
        if source_type not in VALID_WBR_SYNC_SOURCE_TYPES:
            allowed = ", ".join(sorted(VALID_WBR_SYNC_SOURCE_TYPES))
            raise WBRValidationError(f"source_type must be one of: {allowed}")

        response = (
            self.db.table("wbr_sync_runs")
            .select("*")
            .eq("profile_id", profile_id)
            .eq("source_type", source_type)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        return response.data if isinstance(response.data, list) else []

    def get_sync_coverage(self, profile_id: str, *, source_type: str) -> dict[str, Any]:
        profile = self._profiles.get_profile(profile_id)
        if source_type not in VALID_WBR_COVERAGE_SOURCE_TYPES:
            allowed = ", ".join(sorted(VALID_WBR_COVERAGE_SOURCE_TYPES))
            raise WBRValidationError(f"coverage source_type must be one of: {allowed}")

        today = datetime.now(UTC).date()
        window_start, window_label = self._coverage_window(profile=profile, source_type=source_type, today=today)
        window_end = today
        if window_start > window_end:
            window_start = window_end

        response = (
            self.db.table("wbr_sync_runs")
            .select("status,date_from,date_to")
            .eq("profile_id", profile_id)
            .eq("source_type", source_type)
            .in_("status", ["success", "running"])
            .order("date_from")
            .limit(1000)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []

        success_ranges: list[tuple[date, date]] = []
        inflight_ranges: list[tuple[date, date]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            clipped = _clip_range(
                _parse_iso_date(row.get("date_from")),
                _parse_iso_date(row.get("date_to")),
                window_start=window_start,
                window_end=window_end,
            )
            if clipped is None:
                continue
            status = str(row.get("status") or "").strip().lower()
            if status == "success":
                success_ranges.append(clipped)
            elif status == "running":
                inflight_ranges.append(clipped)

        merged_success = _merge_ranges(success_ranges)
        merged_inflight = _merge_ranges(inflight_ranges)
        unavailable_ranges = _merge_ranges([*merged_success, *merged_inflight])
        missing_ranges = _subtract_ranges(window_start, window_end, unavailable_ranges)

        return {
            "source_type": source_type,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "window_label": window_label,
            "covered_day_count": _range_day_count(merged_success),
            "in_flight_day_count": _range_day_count(merged_inflight),
            "missing_day_count": _range_day_count(missing_ranges),
            "covered_ranges": [
                {"date_from": start.isoformat(), "date_to": end.isoformat()} for start, end in merged_success
            ],
            "in_flight_ranges": [
                {"date_from": start.isoformat(), "date_to": end.isoformat()} for start, end in merged_inflight
            ],
            "missing_ranges": [
                {"date_from": start.isoformat(), "date_to": end.isoformat()} for start, end in missing_ranges
            ],
        }

    @staticmethod
    def _coverage_window(
        *,
        profile: dict[str, Any],
        source_type: str,
        today: date,
    ) -> tuple[date, str]:
        configured_start = _parse_iso_date(profile.get("backfill_start_date"))
        if source_type == "amazon_ads":
            base_start = today - timedelta(days=OBSERVED_REPORT_RETENTION_DAYS - 1)
            if configured_start is not None:
                return max(base_start, configured_start), "Current Amazon Ads retention window"
            return base_start, "Current Amazon Ads retention window"

        base_start = today - timedelta(days=WINDSOR_BUSINESS_COVERAGE_LOOKBACK_DAYS - 1)
        if configured_start is not None:
            return max(base_start, configured_start), "Recent SP-API coverage window"
        return base_start, "Recent SP-API coverage window"
