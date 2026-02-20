"""Tests for C12B: Brand CRUD mutation skills.

Covers:
- Classifier recognizes create/update brand phrases
- Policy gate: admin allowed, non-admin denied
- Tool registry includes both brand mutation skills
- Service layer: resolve_brand_for_mutation, create_brand, update_brand
- Handler coverage for create/update happy paths + error paths
- Formatting helpers
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.routes.slack import _classify_message, _handle_cc_skill
from app.services.agencyclaw.command_center_brand_mutations import (
    create_brand,
    format_brand_ambiguous,
    format_brand_create_result,
    format_brand_update_result,
    resolve_brand_for_mutation,
    update_brand,
)
from app.services.agencyclaw.policy_gate import (
    ActorContext,
    SurfaceContext,
    evaluate_tool_policy,
)
from app.services.agencyclaw.tool_registry import (
    TOOL_SCHEMAS,
    validate_tool_call,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _actor(role: str = "operator", is_admin: bool = False) -> ActorContext:
    return ActorContext(
        profile_id="p1",
        slack_user_id="U1",
        role=role,
        is_admin=is_admin,
    )


def _dm_surface() -> SurfaceContext:
    return SurfaceContext(channel_id="D1", surface_type="dm")


def _fake_db_response(data):
    resp = MagicMock()
    resp.data = data
    return resp


# ---------------------------------------------------------------------------
# Classifier tests
# ---------------------------------------------------------------------------


class TestClassifierBrandMutations:
    def test_create_brand_for_client(self):
        intent, params = _classify_message("create brand Alpha for Distex")
        assert intent == "cc_brand_create"
        assert params["brand_name"] == "Alpha"
        assert params["client_name"] == "Distex"

    def test_add_brand_under_client(self):
        intent, params = _classify_message("add brand Beta under Acme")
        assert intent == "cc_brand_create"
        assert params["brand_name"] == "Beta"
        assert params["client_name"] == "Acme"

    def test_new_brand_on_client(self):
        intent, params = _classify_message("new brand Gamma on Distex")
        assert intent == "cc_brand_create"
        assert params["brand_name"] == "Gamma"
        assert params["client_name"] == "Distex"

    def test_update_brand(self):
        intent, params = _classify_message("update brand Alpha")
        assert intent == "cc_brand_update"
        assert params["brand_name"] == "Alpha"

    def test_update_brand_for_client(self):
        intent, params = _classify_message("update brand Alpha for Distex")
        assert intent == "cc_brand_update"
        assert params["brand_name"] == "Alpha"
        assert params["client_name"] == "Distex"

    def test_rename_brand(self):
        intent, params = _classify_message("rename brand Alpha")
        assert intent == "cc_brand_update"
        assert params["brand_name"] == "Alpha"

    def test_edit_brand_under_client(self):
        intent, params = _classify_message("edit brand Alpha under Distex")
        assert intent == "cc_brand_update"
        assert params["brand_name"] == "Alpha"
        assert params["client_name"] == "Distex"


# ---------------------------------------------------------------------------
# Policy gate tests
# ---------------------------------------------------------------------------


class TestPolicyBrandMutations:
    def test_admin_can_create(self):
        policy = evaluate_tool_policy(
            _actor(role="admin", is_admin=True),
            _dm_surface(),
            "cc_brand_create",
        )
        assert policy["allowed"] is True

    def test_admin_can_update(self):
        policy = evaluate_tool_policy(
            _actor(role="admin", is_admin=True),
            _dm_surface(),
            "cc_brand_update",
        )
        assert policy["allowed"] is True

    def test_non_admin_denied_create(self):
        policy = evaluate_tool_policy(
            _actor(),
            _dm_surface(),
            "cc_brand_create",
        )
        assert policy["allowed"] is False
        assert policy["reason_code"] == "admin_skill_denied"

    def test_non_admin_denied_update(self):
        policy = evaluate_tool_policy(
            _actor(),
            _dm_surface(),
            "cc_brand_update",
        )
        assert policy["allowed"] is False
        assert policy["reason_code"] == "admin_skill_denied"

    def test_viewer_denied_create(self):
        policy = evaluate_tool_policy(
            _actor(role="viewer"),
            _dm_surface(),
            "cc_brand_create",
        )
        assert policy["allowed"] is False

    def test_non_dm_denied(self):
        surface = SurfaceContext(channel_id="C1", surface_type="channel")
        policy = evaluate_tool_policy(
            _actor(role="admin", is_admin=True),
            surface,
            "cc_brand_create",
        )
        assert policy["allowed"] is False


# ---------------------------------------------------------------------------
# Tool registry tests
# ---------------------------------------------------------------------------


class TestToolRegistryBrandMutations:
    def test_create_registered(self):
        assert "cc_brand_create" in TOOL_SCHEMAS

    def test_update_registered(self):
        assert "cc_brand_update" in TOOL_SCHEMAS

    def test_create_client_name_required(self):
        schema = TOOL_SCHEMAS["cc_brand_create"]
        assert schema["args"]["client_name"]["required"] is True

    def test_create_brand_name_required(self):
        schema = TOOL_SCHEMAS["cc_brand_create"]
        assert schema["args"]["brand_name"]["required"] is True

    def test_update_brand_name_required(self):
        schema = TOOL_SCHEMAS["cc_brand_update"]
        assert schema["args"]["brand_name"]["required"] is True

    def test_update_client_name_optional(self):
        schema = TOOL_SCHEMAS["cc_brand_update"]
        assert schema["args"]["client_name"]["required"] is False

    def test_validate_create_valid(self):
        errors = validate_tool_call(
            "cc_brand_create",
            {"client_name": "Distex", "brand_name": "Alpha"},
        )
        assert errors == []

    def test_validate_create_missing_brand(self):
        errors = validate_tool_call("cc_brand_create", {"client_name": "Distex"})
        assert any("brand_name" in e for e in errors)

    def test_validate_update_valid(self):
        errors = validate_tool_call(
            "cc_brand_update",
            {"brand_name": "Alpha", "new_brand_name": "Beta"},
        )
        assert errors == []


# ---------------------------------------------------------------------------
# Service layer: resolve_brand_for_mutation
# ---------------------------------------------------------------------------


class TestResolveBrandForMutation:
    def test_single_match(self):
        db = MagicMock()
        db.table.return_value.select.return_value.order.return_value.limit.return_value.eq.return_value.execute.return_value = (
            _fake_db_response([{"id": "b1", "name": "Alpha", "client_id": "c1"}])
        )
        result = resolve_brand_for_mutation(db, "c1", "Alpha")
        assert result["status"] == "ok"
        assert result["brand_id"] == "b1"

    def test_not_found(self):
        db = MagicMock()
        db.table.return_value.select.return_value.order.return_value.limit.return_value.eq.return_value.execute.return_value = (
            _fake_db_response([{"id": "b1", "name": "Alpha", "client_id": "c1"}])
        )
        result = resolve_brand_for_mutation(db, "c1", "Nonexistent")
        assert result["status"] == "not_found"

    def test_ambiguous(self):
        db = MagicMock()
        db.table.return_value.select.return_value.order.return_value.limit.return_value.eq.return_value.execute.return_value = (
            _fake_db_response([
                {"id": "b1", "name": "Alpha One", "client_id": "c1"},
                {"id": "b2", "name": "Alpha Two", "client_id": "c1"},
            ])
        )
        result = resolve_brand_for_mutation(db, "c1", "alpha")
        assert result["status"] == "ambiguous"
        assert len(result["candidates"]) == 2

    def test_no_client_scope(self):
        """Resolves across all clients when client_id is None."""
        db = MagicMock()
        db.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value = (
            _fake_db_response([{"id": "b1", "name": "Alpha", "client_id": "c1"}])
        )
        result = resolve_brand_for_mutation(db, None, "Alpha")
        assert result["status"] == "ok"
        assert result["brand_id"] == "b1"

    def test_empty_query(self):
        result = resolve_brand_for_mutation(MagicMock(), "c1", "")
        assert result["status"] == "not_found"


# ---------------------------------------------------------------------------
# Service layer: create_brand
# ---------------------------------------------------------------------------


class TestCreateBrand:
    def test_create_success(self):
        db = MagicMock()
        # Duplicate check returns no existing brands
        db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
            _fake_db_response([])
        )
        # Insert returns new row
        db.table.return_value.insert.return_value.execute.return_value = (
            _fake_db_response([{"id": "new-brand-id"}])
        )
        result = create_brand(db, client_id="c1", brand_name="Alpha")
        assert result["status"] == "ok"
        assert result["brand_id"] == "new-brand-id"

    def test_create_duplicate(self):
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
            _fake_db_response([{"id": "existing-id", "name": "Alpha"}])
        )
        result = create_brand(db, client_id="c1", brand_name="alpha")
        assert result["status"] == "duplicate"
        assert "already exists" in result["message"]

    def test_create_empty_name(self):
        result = create_brand(MagicMock(), client_id="c1", brand_name="")
        assert result["status"] == "error"
        assert "empty" in result["message"].lower()

    def test_create_with_marketplaces(self):
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
            _fake_db_response([])
        )
        insert_mock = MagicMock()
        insert_mock.execute.return_value = _fake_db_response([{"id": "b1"}])
        db.table.return_value.insert.return_value = insert_mock

        result = create_brand(
            db, client_id="c1", brand_name="Alpha", marketplaces="US,CA,UK",
        )
        assert result["status"] == "ok"
        # Verify the insert payload included amazon_marketplaces
        insert_call = db.table.return_value.insert.call_args
        payload = insert_call[0][0] if insert_call[0] else insert_call[1].get("payload", {})
        assert "amazon_marketplaces" in payload
        assert payload["amazon_marketplaces"] == ["US", "CA", "UK"]


# ---------------------------------------------------------------------------
# Service layer: update_brand
# ---------------------------------------------------------------------------


class TestUpdateBrand:
    def test_update_name(self):
        db = MagicMock()
        db.table.return_value.update.return_value.eq.return_value.execute.return_value = (
            _fake_db_response([])
        )
        result = update_brand(db, brand_id="b1", new_brand_name="Beta")
        assert result["status"] == "ok"
        assert "name" in result["fields_updated"]

    def test_update_clickup_fields(self):
        db = MagicMock()
        db.table.return_value.update.return_value.eq.return_value.execute.return_value = (
            _fake_db_response([])
        )
        result = update_brand(
            db, brand_id="b1",
            clickup_space_id="sp-1", clickup_list_id="list-1",
        )
        assert result["status"] == "ok"
        assert "clickup_space_id" in result["fields_updated"]
        assert "clickup_list_id" in result["fields_updated"]

    def test_update_no_changes(self):
        result = update_brand(MagicMock(), brand_id="b1")
        assert result["status"] == "no_changes"

    def test_update_marketplaces(self):
        db = MagicMock()
        db.table.return_value.update.return_value.eq.return_value.execute.return_value = (
            _fake_db_response([])
        )
        result = update_brand(db, brand_id="b1", marketplaces="US,UK")
        assert result["status"] == "ok"
        assert "amazon_marketplaces" in result["fields_updated"]

    def test_update_failure(self):
        db = MagicMock()
        db.table.return_value.update.return_value.eq.return_value.execute.side_effect = Exception("DB error")
        result = update_brand(db, brand_id="b1", new_brand_name="Beta")
        assert result["status"] == "error"
        assert "DB error" in result["message"]


# ---------------------------------------------------------------------------
# Formatting tests
# ---------------------------------------------------------------------------


class TestBrandMutationFormatters:
    def test_format_create_ok(self):
        result = {"status": "ok", "brand_id": "b1", "message": "Brand *Alpha* created."}
        text = format_brand_create_result(result, "Alpha", "Distex")
        assert "Alpha" in text
        assert "Distex" in text

    def test_format_create_duplicate(self):
        result = {"status": "duplicate", "brand_id": "b1", "message": "A brand named *Alpha* already exists for this client."}
        text = format_brand_create_result(result, "Alpha", "Distex")
        assert "already exists" in text

    def test_format_update_ok(self):
        result = {"status": "ok", "message": "Updated name.", "fields_updated": ["name"]}
        text = format_brand_update_result(result, "Alpha")
        assert "Alpha" in text
        assert "Updated" in text

    def test_format_update_no_changes(self):
        result = {"status": "no_changes", "message": "No fields to update.", "fields_updated": []}
        text = format_brand_update_result(result, "Alpha")
        assert "No changes" in text

    def test_format_brand_ambiguous(self):
        candidates = [{"name": "Alpha One"}, {"name": "Alpha Two"}]
        text = format_brand_ambiguous(candidates)
        assert "Alpha One" in text
        assert "Alpha Two" in text
        assert "specific" in text.lower()


# ---------------------------------------------------------------------------
# Handler tests: Brand create
# ---------------------------------------------------------------------------


class TestHandleBrandCreate:
    @pytest.mark.asyncio
    async def test_create_happy_path(self):
        session = MagicMock(profile_id="p1", active_client_id="client-1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        session_service.get_client_name.return_value = "Distex"
        slack = AsyncMock()

        create_result = {"status": "ok", "brand_id": "b1", "message": "Brand *Alpha* created."}

        with patch("app.api.routes.slack.create_brand", return_value=create_result):
            summary = await _handle_cc_skill(
                skill_id="cc_brand_create",
                args={"brand_name": "Alpha", "client_name": "Distex"},
                session=session,
                session_service=session_service,
                channel="D1",
                slack=slack,
            )

        assert summary == "[Brand create]"
        posted = slack.post_message.call_args.kwargs.get("text", "")
        assert "Alpha" in posted
        assert "Distex" in posted

    @pytest.mark.asyncio
    async def test_create_duplicate(self):
        session = MagicMock(profile_id="p1", active_client_id="client-1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        session_service.get_client_name.return_value = "Distex"
        slack = AsyncMock()

        create_result = {"status": "duplicate", "brand_id": "b1", "message": "A brand named *Alpha* already exists for this client."}

        with patch("app.api.routes.slack.create_brand", return_value=create_result):
            summary = await _handle_cc_skill(
                skill_id="cc_brand_create",
                args={"brand_name": "Alpha", "client_name": "Distex"},
                session=session,
                session_service=session_service,
                channel="D1",
                slack=slack,
            )

        assert summary == "[Brand create]"
        posted = slack.post_message.call_args.kwargs.get("text", "")
        assert "already exists" in posted

    @pytest.mark.asyncio
    async def test_create_missing_brand_name(self):
        session = MagicMock(profile_id="p1", active_client_id="client-1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        slack = AsyncMock()

        summary = await _handle_cc_skill(
            skill_id="cc_brand_create",
            args={"brand_name": "", "client_name": "Distex"},
            session=session,
            session_service=session_service,
            channel="D1",
            slack=slack,
        )

        assert "missing name" in summary.lower()

    @pytest.mark.asyncio
    async def test_create_client_not_found(self):
        session = MagicMock(profile_id="p1", active_client_id=None)
        session_service = MagicMock()
        session_service.db = MagicMock()
        session_service.find_client_matches.return_value = []
        slack = AsyncMock()

        summary = await _handle_cc_skill(
            skill_id="cc_brand_create",
            args={"brand_name": "Alpha", "client_name": "NoSuch"},
            session=session,
            session_service=session_service,
            channel="D1",
            slack=slack,
        )

        assert "client error" in summary.lower()

    @pytest.mark.asyncio
    async def test_create_uses_active_client(self):
        """When client_name omitted, uses active client."""
        session = MagicMock(profile_id="p1", active_client_id="client-1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        session_service.get_client_name.return_value = "Distex"
        slack = AsyncMock()

        create_result = {"status": "ok", "brand_id": "b1", "message": "Brand *Alpha* created."}

        with patch("app.api.routes.slack.create_brand", return_value=create_result) as mock_create:
            summary = await _handle_cc_skill(
                skill_id="cc_brand_create",
                args={"brand_name": "Alpha"},
                session=session,
                session_service=session_service,
                channel="D1",
                slack=slack,
            )

        assert summary == "[Brand create]"
        mock_create.assert_called_once()


# ---------------------------------------------------------------------------
# Handler tests: Brand update
# ---------------------------------------------------------------------------


class TestHandleBrandUpdate:
    @pytest.mark.asyncio
    async def test_update_happy_path(self):
        session = MagicMock(profile_id="p1", active_client_id="client-1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        slack = AsyncMock()

        brand_result = {"status": "ok", "brand_id": "b1", "brand_name": "Alpha", "candidates": []}
        update_result = {"status": "ok", "message": "Updated name.", "fields_updated": ["name"]}

        with (
            patch("app.api.routes.slack.resolve_brand_for_mutation", return_value=brand_result),
            patch("app.api.routes.slack.update_brand", return_value=update_result),
        ):
            summary = await _handle_cc_skill(
                skill_id="cc_brand_update",
                args={"brand_name": "Alpha", "new_brand_name": "Beta"},
                session=session,
                session_service=session_service,
                channel="D1",
                slack=slack,
            )

        assert summary == "[Brand update]"
        posted = slack.post_message.call_args.kwargs.get("text", "")
        assert "Alpha" in posted

    @pytest.mark.asyncio
    async def test_update_brand_not_found(self):
        session = MagicMock(profile_id="p1", active_client_id="client-1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        slack = AsyncMock()

        brand_result = {"status": "not_found", "brand_id": None, "brand_name": None, "candidates": []}

        with patch("app.api.routes.slack.resolve_brand_for_mutation", return_value=brand_result):
            summary = await _handle_cc_skill(
                skill_id="cc_brand_update",
                args={"brand_name": "Nonexistent"},
                session=session,
                session_service=session_service,
                channel="D1",
                slack=slack,
            )

        assert "brand not found" in summary.lower()

    @pytest.mark.asyncio
    async def test_update_brand_ambiguous(self):
        session = MagicMock(profile_id="p1", active_client_id="client-1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        slack = AsyncMock()

        brand_result = {
            "status": "ambiguous",
            "brand_id": None,
            "brand_name": None,
            "candidates": [{"name": "Alpha One"}, {"name": "Alpha Two"}],
        }

        with patch("app.api.routes.slack.resolve_brand_for_mutation", return_value=brand_result):
            summary = await _handle_cc_skill(
                skill_id="cc_brand_update",
                args={"brand_name": "Alpha"},
                session=session,
                session_service=session_service,
                channel="D1",
                slack=slack,
            )

        assert "brand ambiguous" in summary.lower()
        posted = slack.post_message.call_args.kwargs.get("text", "")
        assert "Alpha One" in posted

    @pytest.mark.asyncio
    async def test_update_missing_brand_name(self):
        session = MagicMock(profile_id="p1", active_client_id="client-1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        slack = AsyncMock()

        summary = await _handle_cc_skill(
            skill_id="cc_brand_update",
            args={"brand_name": ""},
            session=session,
            session_service=session_service,
            channel="D1",
            slack=slack,
        )

        assert "missing name" in summary.lower()

    @pytest.mark.asyncio
    async def test_update_with_client_hint(self):
        session = MagicMock(profile_id="p1", active_client_id="client-1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        session_service.find_client_matches.return_value = [{"id": "client-1", "name": "Distex"}]
        slack = AsyncMock()

        brand_result = {"status": "ok", "brand_id": "b1", "brand_name": "Alpha", "candidates": []}
        update_result = {"status": "ok", "message": "Updated name.", "fields_updated": ["name"]}

        with (
            patch("app.api.routes.slack.resolve_brand_for_mutation", return_value=brand_result),
            patch("app.api.routes.slack.update_brand", return_value=update_result),
        ):
            summary = await _handle_cc_skill(
                skill_id="cc_brand_update",
                args={"brand_name": "Alpha", "client_name": "Distex", "new_brand_name": "Beta"},
                session=session,
                session_service=session_service,
                channel="D1",
                slack=slack,
            )

        assert summary == "[Brand update]"

    @pytest.mark.asyncio
    async def test_update_no_changes(self):
        session = MagicMock(profile_id="p1", active_client_id="client-1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        slack = AsyncMock()

        brand_result = {"status": "ok", "brand_id": "b1", "brand_name": "Alpha", "candidates": []}
        update_result = {"status": "no_changes", "message": "No fields to update.", "fields_updated": []}

        with (
            patch("app.api.routes.slack.resolve_brand_for_mutation", return_value=brand_result),
            patch("app.api.routes.slack.update_brand", return_value=update_result),
        ):
            summary = await _handle_cc_skill(
                skill_id="cc_brand_update",
                args={"brand_name": "Alpha"},
                session=session,
                session_service=session_service,
                channel="D1",
                slack=slack,
            )

        assert summary == "[Brand update]"
        posted = slack.post_message.call_args.kwargs.get("text", "")
        assert "No changes" in posted
