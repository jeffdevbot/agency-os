from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.routers import wbr


class _FakeWbrService:
    def __init__(self) -> None:
        self.profile_updates = None
        self.row_updates = None

    def update_profile(self, profile_id: str, updates: dict, user_id: str | None = None):
        self.profile_updates = {
            "profile_id": profile_id,
            "updates": updates,
            "user_id": user_id,
        }
        return {"id": profile_id, **updates}

    def update_row(self, row_id: str, updates: dict, user_id: str | None = None):
        self.row_updates = {
            "row_id": row_id,
            "updates": updates,
            "user_id": user_id,
        }
        return {"id": row_id, **updates}


class _FakeSyncRunService:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def list_sync_runs(self, profile_id: str, *, source_type: str):
        self.calls.append({"profile_id": profile_id, "source_type": source_type})
        return [{"id": "run-1", "source_type": source_type}]

    def get_sync_coverage(self, profile_id: str, *, source_type: str):
        self.calls.append({"profile_id": profile_id, "source_type": source_type, "kind": "coverage"})
        return {
            "source_type": source_type,
            "window_start": "2026-01-01",
            "window_end": "2026-03-25",
            "window_label": "Recent SP-API coverage window",
            "covered_day_count": 70,
            "in_flight_day_count": 5,
            "missing_day_count": 9,
            "covered_ranges": [{"date_from": "2026-01-01", "date_to": "2026-03-10"}],
            "in_flight_ranges": [{"date_from": "2026-03-11", "date_to": "2026-03-15"}],
            "missing_ranges": [{"date_from": "2026-03-16", "date_to": "2026-03-24"}],
        }


def _override_admin():
    return {"sub": "user-123"}


def test_update_row_preserves_explicit_null_parent(monkeypatch):
    fake_service = _FakeWbrService()
    monkeypatch.setattr(wbr, "_get_service", lambda: fake_service)
    app.dependency_overrides[wbr.require_admin_user] = _override_admin

    try:
      with TestClient(app) as client:
          response = client.patch("/admin/wbr/rows/row-1", json={"parent_row_id": None})
    finally:
      app.dependency_overrides.pop(wbr.require_admin_user, None)

    assert response.status_code == 200
    assert fake_service.row_updates is not None
    assert "parent_row_id" in fake_service.row_updates["updates"]
    assert fake_service.row_updates["updates"]["parent_row_id"] is None


def test_update_profile_preserves_explicit_null_field(monkeypatch):
    fake_service = _FakeWbrService()
    monkeypatch.setattr(wbr, "_get_service", lambda: fake_service)
    app.dependency_overrides[wbr.require_admin_user] = _override_admin

    try:
      with TestClient(app) as client:
          response = client.patch("/admin/wbr/profiles/profile-1", json={"windsor_account_id": None})
    finally:
      app.dependency_overrides.pop(wbr.require_admin_user, None)

    assert response.status_code == 200
    assert fake_service.profile_updates is not None
    assert "windsor_account_id" in fake_service.profile_updates["updates"]
    assert fake_service.profile_updates["updates"]["windsor_account_id"] is None


def test_update_profile_preserves_explicit_false_boolean(monkeypatch):
    fake_service = _FakeWbrService()
    monkeypatch.setattr(wbr, "_get_service", lambda: fake_service)
    app.dependency_overrides[wbr.require_admin_user] = _override_admin

    try:
      with TestClient(app) as client:
          response = client.patch("/admin/wbr/profiles/profile-1", json={"sp_api_auto_sync_enabled": False})
    finally:
      app.dependency_overrides.pop(wbr.require_admin_user, None)

    assert response.status_code == 200
    assert fake_service.profile_updates is not None
    assert "sp_api_auto_sync_enabled" in fake_service.profile_updates["updates"]
    assert fake_service.profile_updates["updates"]["sp_api_auto_sync_enabled"] is False


def test_update_profile_preserves_explicit_false_search_term_boolean(monkeypatch):
    fake_service = _FakeWbrService()
    monkeypatch.setattr(wbr, "_get_service", lambda: fake_service)
    app.dependency_overrides[wbr.require_admin_user] = _override_admin

    try:
      with TestClient(app) as client:
          response = client.patch("/admin/wbr/profiles/profile-1", json={"search_term_auto_sync_enabled": False})
    finally:
      app.dependency_overrides.pop(wbr.require_admin_user, None)

    assert response.status_code == 200
    assert fake_service.profile_updates is not None
    assert "search_term_auto_sync_enabled" in fake_service.profile_updates["updates"]
    assert fake_service.profile_updates["updates"]["search_term_auto_sync_enabled"] is False


def test_list_sync_runs_uses_generic_sync_run_service(monkeypatch):
    fake_sync_service = _FakeSyncRunService()
    monkeypatch.setattr(wbr, "_get_sync_run_service", lambda: fake_sync_service)

    def _fail_if_called():
        raise AssertionError("Windsor business sync service should not be used for generic sync-run listing")

    monkeypatch.setattr(wbr, "_get_windsor_business_sync_service", _fail_if_called)
    app.dependency_overrides[wbr.require_admin_user] = _override_admin

    try:
        with TestClient(app) as client:
            response = client.get(
                "/admin/wbr/profiles/profile-1/sync-runs",
                params={"source_type": "windsor_returns"},
            )
    finally:
        app.dependency_overrides.pop(wbr.require_admin_user, None)

    assert response.status_code == 200
    assert response.json()["runs"] == [{"id": "run-1", "source_type": "windsor_returns"}]
    assert fake_sync_service.calls == [{"profile_id": "profile-1", "source_type": "windsor_returns"}]


def test_get_sync_coverage_uses_generic_sync_run_service(monkeypatch):
    fake_sync_service = _FakeSyncRunService()
    monkeypatch.setattr(wbr, "_get_sync_run_service", lambda: fake_sync_service)
    app.dependency_overrides[wbr.require_admin_user] = _override_admin

    try:
        with TestClient(app) as client:
            response = client.get(
                "/admin/wbr/profiles/profile-1/sync-coverage",
                params={"source_type": "amazon_ads"},
            )
    finally:
        app.dependency_overrides.pop(wbr.require_admin_user, None)

    assert response.status_code == 200
    assert response.json()["missing_ranges"] == [{"date_from": "2026-03-16", "date_to": "2026-03-24"}]
    assert fake_sync_service.calls == [
        {"profile_id": "profile-1", "source_type": "amazon_ads", "kind": "coverage"}
    ]
