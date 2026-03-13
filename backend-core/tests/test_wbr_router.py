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
