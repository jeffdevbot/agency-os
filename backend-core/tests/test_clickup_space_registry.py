"""Tests for C6A: ClickUp Space Registry service + admin endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth import require_admin_user
from app.services.agencyclaw.clickup_space_registry import (
    classify_clickup_space,
    list_clickup_spaces,
    map_clickup_space_to_brand,
    sync_clickup_spaces,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def override_admin_auth():
    app.dependency_overrides[require_admin_user] = lambda: {"id": "admin_user", "is_admin": True}
    yield
    app.dependency_overrides = {}


@pytest.fixture(autouse=True)
def mock_supabase():
    with patch("app.routers.admin.create_client") as mock:
        mock.return_value = MagicMock()
        yield mock


@pytest.fixture(autouse=True)
def mock_settings():
    with patch("app.routers.admin.settings") as mock:
        mock.supabase_url = "http://localhost:54321"
        mock.supabase_service_role = "service_role_token"
        yield mock


def _make_db(*, upsert_data=None, select_data=None, update_data=None):
    """Build a mock Supabase client with configurable responses."""
    db = MagicMock()

    # Upsert chain
    upsert_resp = MagicMock()
    upsert_resp.data = upsert_data or []
    db.table.return_value.upsert.return_value.execute.return_value = upsert_resp

    # Select chain (for list queries)
    select_resp = MagicMock()
    select_resp.data = select_data or []
    chain = db.table.return_value.select.return_value
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.execute.return_value = select_resp

    # Update chain
    update_resp = MagicMock()
    update_resp.data = update_data or []
    db.table.return_value.update.return_value.eq.return_value.execute.return_value = update_resp

    return db


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------


class TestSyncClickupSpaces:
    def test_upserts_spaces(self):
        db = _make_db(upsert_data=[
            {"space_id": "sp1", "name": "Brand A"},
            {"space_id": "sp2", "name": "Brand B"},
        ])
        spaces = [
            {"id": "sp1", "name": "Brand A", "team_id": "t1"},
            {"id": "sp2", "name": "Brand B", "team_id": "t1"},
        ]
        result = sync_clickup_spaces(db, spaces)
        assert result["synced"] == 2
        assert len(result["spaces"]) == 2

        db.table.assert_called_with("clickup_space_registry")
        upsert_call = db.table.return_value.upsert.call_args
        rows = upsert_call[0][0]
        assert len(rows) == 2
        assert rows[0]["space_id"] == "sp1"
        assert rows[0]["team_id"] == "t1"
        # on_conflict kwarg
        assert upsert_call[1].get("on_conflict") == "space_id"

    def test_preserves_classification(self):
        """Upsert payload must NOT include classification, brand_id, or active."""
        db = _make_db(upsert_data=[{"space_id": "sp1"}])
        spaces = [{"id": "sp1", "name": "Test", "team_id": "t1"}]
        sync_clickup_spaces(db, spaces)

        rows = db.table.return_value.upsert.call_args[0][0]
        for row in rows:
            assert "classification" not in row
            assert "brand_id" not in row
            assert "active" not in row

    def test_empty_spaces_returns_zero(self):
        db = _make_db()
        result = sync_clickup_spaces(db, [])
        assert result["synced"] == 0
        assert result["spaces"] == []
        db.table.return_value.upsert.assert_not_called()


class TestListClickupSpaces:
    def test_filters_by_classification(self):
        db = _make_db(select_data=[{"space_id": "sp1"}])
        result = list_clickup_spaces(db, classification="brand_scoped")
        assert result == [{"space_id": "sp1"}]

        chain = db.table.return_value.select.return_value
        # eq should have been called (at least once for classification, once for active)
        eq_calls = chain.eq.call_args_list
        class_call = [c for c in eq_calls if c[0][0] == "classification"]
        assert len(class_call) == 1
        assert class_call[0][0][1] == "brand_scoped"

    def test_excludes_inactive_by_default(self):
        db = _make_db(select_data=[])
        list_clickup_spaces(db)

        chain = db.table.return_value.select.return_value
        eq_calls = chain.eq.call_args_list
        active_call = [c for c in eq_calls if c[0][0] == "active"]
        assert len(active_call) == 1
        assert active_call[0][0][1] is True

    def test_includes_inactive_when_requested(self):
        db = _make_db(select_data=[])
        list_clickup_spaces(db, include_inactive=True)

        chain = db.table.return_value.select.return_value
        eq_calls = chain.eq.call_args_list
        active_call = [c for c in eq_calls if c[0][0] == "active"]
        assert len(active_call) == 0


class TestClassifyClickupSpace:
    def test_classify_valid(self):
        row = {"space_id": "sp1", "classification": "brand_scoped"}
        db = _make_db(update_data=[row])
        result = classify_clickup_space(db, "sp1", "brand_scoped")
        assert result == row

        update_call = db.table.return_value.update.call_args[0][0]
        assert update_call == {"classification": "brand_scoped"}

    def test_classify_invalid_value(self):
        db = _make_db()
        with pytest.raises(ValueError, match="Invalid classification"):
            classify_clickup_space(db, "sp1", "nonsense")

    def test_classify_not_found(self):
        db = _make_db(update_data=[])
        with pytest.raises(ValueError, match="not found"):
            classify_clickup_space(db, "sp-missing", "unknown")


class TestMapClickupSpaceToBrand:
    def test_map_brand(self):
        row = {"space_id": "sp1", "brand_id": "b-1"}
        db = _make_db(update_data=[row])
        result = map_clickup_space_to_brand(db, "sp1", "b-1")
        assert result == row

        update_call = db.table.return_value.update.call_args[0][0]
        assert update_call == {"brand_id": "b-1"}

    def test_unmap_brand(self):
        row = {"space_id": "sp1", "brand_id": None}
        db = _make_db(update_data=[row])
        result = map_clickup_space_to_brand(db, "sp1", None)
        assert result == row

        update_call = db.table.return_value.update.call_args[0][0]
        assert update_call == {"brand_id": None}

    def test_not_found(self):
        db = _make_db(update_data=[])
        with pytest.raises(ValueError, match="not found"):
            map_clickup_space_to_brand(db, "sp-missing", "b-1")


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


class TestSyncEndpoint:
    def test_success(self):
        mock_cu = AsyncMock()
        mock_cu.list_spaces.return_value = [
            {"id": "sp1", "name": "Space 1", "team_id": "t1"},
        ]

        with (
            patch("app.routers.admin.get_clickup_service", return_value=mock_cu),
            patch("app.routers.admin.sync_clickup_spaces", return_value={"synced": 1, "spaces": [{"space_id": "sp1"}]}),
        ):
            response = client.post("/admin/clickup-spaces/sync")

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["synced"] == 1

    def test_clickup_failure(self):
        with patch("app.routers.admin.get_clickup_service", side_effect=Exception("No token")):
            response = client.post("/admin/clickup-spaces/sync")

        assert response.status_code == 500
        assert "ClickUp not configured" in response.json()["detail"]


class TestListEndpoint:
    def test_list_all(self):
        with patch("app.routers.admin.list_clickup_spaces", return_value=[{"space_id": "sp1"}]):
            response = client.get("/admin/clickup-spaces")

        assert response.status_code == 200
        assert len(response.json()["spaces"]) == 1

    def test_list_with_classification_filter(self):
        with patch("app.routers.admin.list_clickup_spaces", return_value=[]) as mock_list:
            response = client.get("/admin/clickup-spaces?classification=brand_scoped")

        assert response.status_code == 200
        call_kwargs = mock_list.call_args
        assert call_kwargs[1]["classification"] == "brand_scoped"


class TestClassifyEndpoint:
    def test_success(self):
        row = {"space_id": "sp1", "classification": "brand_scoped"}
        with patch("app.routers.admin.classify_clickup_space", return_value=row):
            response = client.post(
                "/admin/clickup-spaces/classify",
                json={"space_id": "sp1", "classification": "brand_scoped"},
            )

        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert response.json()["space"]["classification"] == "brand_scoped"

    def test_invalid_classification(self):
        with patch("app.routers.admin.classify_clickup_space", side_effect=ValueError("Invalid classification")):
            response = client.post(
                "/admin/clickup-spaces/classify",
                json={"space_id": "sp1", "classification": "bad"},
            )

        assert response.status_code == 400


class TestMapBrandEndpoint:
    def test_map(self):
        row = {"space_id": "sp1", "brand_id": "b-1"}
        with patch("app.routers.admin.map_clickup_space_to_brand", return_value=row):
            response = client.post(
                "/admin/clickup-spaces/map-brand",
                json={"space_id": "sp1", "brand_id": "b-1"},
            )

        assert response.status_code == 200
        assert response.json()["ok"] is True

    def test_unmap(self):
        row = {"space_id": "sp1", "brand_id": None}
        with patch("app.routers.admin.map_clickup_space_to_brand", return_value=row):
            response = client.post(
                "/admin/clickup-spaces/map-brand",
                json={"space_id": "sp1", "brand_id": None},
            )

        assert response.status_code == 200
        assert response.json()["space"]["brand_id"] is None
