from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.routers import admin
from app.services.clickup import ClickUpConfigurationError


def _override_admin():
    return {"sub": "user-123"}


class _FakeClickUp:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


class _FakeTeamHoursService:
    def __init__(self, db, clickup) -> None:
        self.db = db
        self.clickup = clickup

    async def build_report_async(self, *, start_date_ms: int, end_date_ms: int):
        return {
            "date_range": {
                "start_date_ms": start_date_ms,
                "end_date_ms": end_date_ms,
            },
            "summary": {
                "total_hours": 1.5,
                "mapped_hours": 1.0,
                "unmapped_hours": 0.5,
                "unattributed_hours": 0.5,
                "unique_users": 1,
                "entry_count": 2,
                "running_entries": 0,
            },
            "by_team_member": [],
            "unmapped_users": [],
            "unmapped_spaces": [],
        }


def test_team_hours_endpoint_returns_report(monkeypatch):
    fake_clickup = _FakeClickUp()
    monkeypatch.setattr(admin, "_get_supabase", lambda: object())
    monkeypatch.setattr(admin, "get_clickup_service", lambda: fake_clickup)
    monkeypatch.setattr(admin, "ClickUpTeamHoursService", _FakeTeamHoursService)
    app.dependency_overrides[admin.require_admin_user] = _override_admin

    try:
        with TestClient(app) as client:
            response = client.get(
                "/admin/team-hours",
                params={
                    "start_date_ms": 1700000000000,
                    "end_date_ms": 1700086400000,
                },
            )
    finally:
        app.dependency_overrides.pop(admin.require_admin_user, None)

    assert response.status_code == 200
    assert response.json()["summary"]["total_hours"] == 1.5
    assert fake_clickup.closed is True


def test_team_hours_endpoint_returns_500_when_clickup_is_not_configured(monkeypatch):
    monkeypatch.setattr(admin, "_get_supabase", lambda: object())
    monkeypatch.setattr(
        admin,
        "get_clickup_service",
        lambda: (_ for _ in ()).throw(ClickUpConfigurationError("CLICKUP_TEAM_ID not set")),
    )
    app.dependency_overrides[admin.require_admin_user] = _override_admin

    try:
        with TestClient(app) as client:
            response = client.get(
                "/admin/team-hours",
                params={
                    "start_date_ms": 1700000000000,
                    "end_date_ms": 1700086400000,
                },
            )
    finally:
        app.dependency_overrides.pop(admin.require_admin_user, None)

    assert response.status_code == 500
    assert "ClickUp not configured" in response.json()["detail"]
