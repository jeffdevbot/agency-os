from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time
from typing import Any, Callable
from zoneinfo import ZoneInfo

from supabase import Client

from .amazon_ads_sync import AmazonAdsSyncService
from .windsor_business_sync import WindsorBusinessSyncService


@dataclass(frozen=True)
class NightlySyncResult:
    profile_id: str
    source_type: str
    status: str
    detail: str | None = None


class WBRNightlySyncService:
    def __init__(
        self,
        db: Client,
        *,
        timezone_name: str = "America/Toronto",
        run_hour: int = 2,
        run_minute: int = 0,
        worker_user_id: str | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.db = db
        self.timezone = ZoneInfo(timezone_name)
        self.run_at = time(hour=max(min(run_hour, 23), 0), minute=max(min(run_minute, 59), 0))
        self.worker_user_id = worker_user_id
        self._now_provider = now_provider or (lambda: datetime.now(UTC))
        self._windsor = WindsorBusinessSyncService(db)
        self._amazon_ads = AmazonAdsSyncService(db)

    async def run_pending(self) -> dict[str, Any]:
        now_utc = self._normalize_now(self._now_provider())
        local_now = now_utc.astimezone(self.timezone)
        pending_ads = await self._amazon_ads.process_pending_runs()
        if local_now.timetz().replace(tzinfo=None) < self.run_at:
            if pending_ads.get("runs_processed", 0) > 0:
                return {
                    "status": "ok",
                    "reason": "before_schedule",
                    "scheduled_time": self.run_at.strftime("%H:%M"),
                    "timezone": self.timezone.key,
                    "pending_amazon_ads": pending_ads,
                    "profiles_considered": 0,
                    "runs_attempted": 0,
                    "results": [],
                }
            return {
                "status": "idle",
                "reason": "before_schedule",
                "scheduled_time": self.run_at.strftime("%H:%M"),
                "timezone": self.timezone.key,
            }

        profiles = self._list_profiles_for_nightly_sync()
        results: list[NightlySyncResult] = []

        for profile in profiles:
            profile_id = str(profile.get("id") or "")
            if not profile_id:
                continue

            if profile.get("sp_api_auto_sync_enabled") and not self._already_started_today(
                profile_id=profile_id,
                source_type="windsor_business",
                local_now=local_now,
            ):
                results.append(
                    await self._run_source(
                        profile_id=profile_id,
                        source_type="windsor_business",
                    )
                )

            if profile.get("ads_api_auto_sync_enabled") and not self._already_started_today(
                profile_id=profile_id,
                source_type="amazon_ads",
                local_now=local_now,
            ):
                results.append(
                    await self._run_source(
                        profile_id=profile_id,
                        source_type="amazon_ads",
                    )
                )

        return {
            "status": "ok",
            "timezone": self.timezone.key,
            "scheduled_time": self.run_at.strftime("%H:%M"),
            "profiles_considered": len(profiles),
            "runs_attempted": len(results),
            "pending_amazon_ads": pending_ads,
            "results": [result.__dict__ for result in results],
        }

    async def _run_source(self, *, profile_id: str, source_type: str) -> NightlySyncResult:
        try:
            if source_type == "windsor_business":
                await self._windsor.run_daily_refresh(
                    profile_id=profile_id,
                    user_id=self.worker_user_id,
                )
            else:
                await self._amazon_ads.run_daily_refresh(
                    profile_id=profile_id,
                    user_id=self.worker_user_id,
                )
            return NightlySyncResult(profile_id=profile_id, source_type=source_type, status="success")
        except Exception as exc:  # noqa: BLE001
            return NightlySyncResult(
                profile_id=profile_id,
                source_type=source_type,
                status="error",
                detail=str(exc),
            )

    def _list_profiles_for_nightly_sync(self) -> list[dict[str, Any]]:
        response = (
            self.db.table("wbr_profiles")
            .select(
                "id, status, windsor_account_id, amazon_ads_profile_id, "
                "sp_api_auto_sync_enabled, ads_api_auto_sync_enabled"
            )
            .eq("status", "active")
            .order("created_at")
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        return [row for row in rows if isinstance(row, dict)]

    def _already_started_today(
        self,
        *,
        profile_id: str,
        source_type: str,
        local_now: datetime,
    ) -> bool:
        local_day_start = datetime.combine(local_now.date(), time.min, tzinfo=self.timezone)
        local_day_end = datetime.combine(local_now.date(), time.max, tzinfo=self.timezone)
        started_after = local_day_start.astimezone(UTC).isoformat()
        started_before = local_day_end.astimezone(UTC).isoformat()
        response = (
            self.db.table("wbr_sync_runs")
            .select("id")
            .eq("profile_id", profile_id)
            .eq("source_type", source_type)
            .eq("job_type", "daily_refresh")
            .gte("started_at", started_after)
            .lte("started_at", started_before)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        return len(rows) > 0

    @staticmethod
    def _normalize_now(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
