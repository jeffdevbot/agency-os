from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.services.wbr.nightly_sync import WBRNightlySyncService


def test_run_pending_is_idle_before_scheduled_time():
    svc = WBRNightlySyncService(
        MagicMock(),
        timezone_name="America/Toronto",
        run_hour=2,
        run_minute=0,
        now_provider=lambda: datetime(2026, 3, 14, 5, 30, tzinfo=UTC),
    )

    result = asyncio.run(svc.run_pending())

    assert result["status"] == "idle"
    assert result["reason"] == "before_schedule"


def test_run_pending_executes_enabled_sources(monkeypatch):
    svc = WBRNightlySyncService(
        MagicMock(),
        timezone_name="America/Toronto",
        run_hour=2,
        run_minute=0,
        worker_user_id="worker-user",
        now_provider=lambda: datetime(2026, 3, 14, 8, 0, tzinfo=UTC),
    )
    windsor_run = AsyncMock(return_value={"ok": True})
    ads_run = AsyncMock(return_value={"ok": True})
    svc._windsor = SimpleNamespace(run_daily_refresh=windsor_run)
    svc._amazon_ads = SimpleNamespace(run_daily_refresh=ads_run)
    monkeypatch.setattr(
        svc,
        "_list_profiles_for_nightly_sync",
        lambda: [
            {
                "id": "profile-1",
                "sp_api_auto_sync_enabled": True,
                "ads_api_auto_sync_enabled": True,
            }
        ],
    )
    monkeypatch.setattr(svc, "_already_started_today", lambda **_: False)

    result = asyncio.run(svc.run_pending())

    windsor_run.assert_awaited_once_with(profile_id="profile-1", user_id="worker-user")
    ads_run.assert_awaited_once_with(profile_id="profile-1", user_id="worker-user")
    assert result["status"] == "ok"
    assert result["runs_attempted"] == 2
    assert all(item["status"] == "success" for item in result["results"])


def test_run_pending_skips_sources_already_started_today(monkeypatch):
    svc = WBRNightlySyncService(
        MagicMock(),
        timezone_name="America/Toronto",
        run_hour=2,
        run_minute=0,
        now_provider=lambda: datetime(2026, 3, 14, 8, 0, tzinfo=UTC),
    )
    windsor_run = AsyncMock(return_value={"ok": True})
    ads_run = AsyncMock(return_value={"ok": True})
    svc._windsor = SimpleNamespace(run_daily_refresh=windsor_run)
    svc._amazon_ads = SimpleNamespace(run_daily_refresh=ads_run)
    monkeypatch.setattr(
        svc,
        "_list_profiles_for_nightly_sync",
        lambda: [
            {
                "id": "profile-1",
                "sp_api_auto_sync_enabled": True,
                "ads_api_auto_sync_enabled": True,
            }
        ],
    )
    monkeypatch.setattr(
        svc,
        "_already_started_today",
        lambda *, source_type, **_: source_type == "windsor_business",
    )

    result = asyncio.run(svc.run_pending())

    windsor_run.assert_not_awaited()
    ads_run.assert_awaited_once()
    assert result["runs_attempted"] == 1
    assert result["results"][0]["source_type"] == "amazon_ads"
