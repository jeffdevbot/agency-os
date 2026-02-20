"""Tests for C12A: Command Center assignment mutation skills.

Covers:
- Classifier recognizes assign/remove phrases
- Policy gate: admin allowed, non-admin denied
- Tool registry includes both assignment skills
- Service layer: resolve_person, resolve_role, resolve_brand_for_assignment
- Service layer: upsert_assignment, remove_assignment
- Handler coverage for upsert/remove happy paths + error paths
- Formatting helpers
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.routes.slack import _classify_message, _handle_cc_skill
from app.services.agencyclaw.command_center_assignments import (
    format_person_ambiguous,
    format_remove_result,
    format_upsert_result,
    resolve_brand_for_assignment,
    resolve_person,
    resolve_role,
    upsert_assignment,
)
from app.services.agencyclaw.policy_gate import (
    ActorContext,
    SurfaceContext,
    evaluate_skill_policy,
)
from app.services.agencyclaw.skill_registry import (
    SKILL_SCHEMAS,
    validate_skill_call,
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
    """Create a mock Supabase response."""
    resp = MagicMock()
    resp.data = data
    return resp


def _mock_db_with_profiles(profiles):
    """Create a mock DB that returns given profiles from profiles table."""
    db = MagicMock()

    def _table(name):
        t = MagicMock()
        if name == "profiles":
            t.select.return_value = t
            t.order.return_value = t
            t.limit.return_value = t
            t.execute.return_value = _fake_db_response(profiles)
        return t

    db.table.side_effect = _table
    return db


# ---------------------------------------------------------------------------
# Classifier tests
# ---------------------------------------------------------------------------


class TestClassifierAssignmentSkills:
    def test_assign_person_as_role(self):
        intent, params = _classify_message("assign Sarah as ppc_strategist")
        assert intent == "cc_assignment_upsert"
        assert params["person_name"] == "Sarah"
        assert params["role_slug"] == "ppc_strategist"

    def test_make_person_to_role(self):
        intent, params = _classify_message("make John to brand_manager")
        assert intent == "cc_assignment_upsert"
        assert params["person_name"] == "John"
        assert params["role_slug"] == "brand_manager"

    def test_set_person_as_role_for_client(self):
        intent, params = _classify_message("set Sarah as csl for Distex")
        assert intent == "cc_assignment_upsert"
        assert params["person_name"] == "Sarah"
        assert params["role_slug"] == "csl"
        assert params["client_name"] == "Distex"

    def test_remove_person_from_role(self):
        intent, params = _classify_message("remove Sarah from ppc_strategist")
        assert intent == "cc_assignment_remove"
        assert params["person_name"] == "Sarah"
        assert params["role_slug"] == "ppc_strategist"

    def test_unassign_person_from_role(self):
        intent, params = _classify_message("unassign John from brand_manager")
        assert intent == "cc_assignment_remove"
        assert params["person_name"] == "John"
        assert params["role_slug"] == "brand_manager"

    def test_remove_with_client_hint(self):
        intent, params = _classify_message("remove Sarah from csl for Distex")
        assert intent == "cc_assignment_remove"
        assert params["person_name"] == "Sarah"
        assert params["role_slug"] == "csl"
        assert params["client_name"] == "Distex"

    def test_assign_with_on_client(self):
        intent, params = _classify_message("assign Sarah as ppc_strategist on Distex")
        assert intent == "cc_assignment_upsert"
        assert params["person_name"] == "Sarah"
        assert params["role_slug"] == "ppc_strategist"
        assert params["client_name"] == "Distex"


# ---------------------------------------------------------------------------
# Policy gate tests
# ---------------------------------------------------------------------------


class TestPolicyAssignmentSkills:
    def test_admin_can_upsert(self):
        policy = evaluate_skill_policy(
            _actor(role="admin", is_admin=True),
            _dm_surface(),
            "cc_assignment_upsert",
        )
        assert policy["allowed"] is True

    def test_admin_can_remove(self):
        policy = evaluate_skill_policy(
            _actor(role="admin", is_admin=True),
            _dm_surface(),
            "cc_assignment_remove",
        )
        assert policy["allowed"] is True

    def test_non_admin_denied_upsert(self):
        policy = evaluate_skill_policy(
            _actor(),
            _dm_surface(),
            "cc_assignment_upsert",
        )
        assert policy["allowed"] is False
        assert policy["reason_code"] == "admin_skill_denied"

    def test_non_admin_denied_remove(self):
        policy = evaluate_skill_policy(
            _actor(),
            _dm_surface(),
            "cc_assignment_remove",
        )
        assert policy["allowed"] is False
        assert policy["reason_code"] == "admin_skill_denied"

    def test_viewer_denied_upsert(self):
        policy = evaluate_skill_policy(
            _actor(role="viewer"),
            _dm_surface(),
            "cc_assignment_upsert",
        )
        assert policy["allowed"] is False

    def test_non_dm_denied(self):
        surface = SurfaceContext(channel_id="C1", surface_type="channel")
        policy = evaluate_skill_policy(
            _actor(role="admin", is_admin=True),
            surface,
            "cc_assignment_upsert",
        )
        assert policy["allowed"] is False


# ---------------------------------------------------------------------------
# Tool registry tests
# ---------------------------------------------------------------------------


class TestToolRegistryAssignmentSkills:
    def test_upsert_registered(self):
        assert "cc_assignment_upsert" in SKILL_SCHEMAS

    def test_remove_registered(self):
        assert "cc_assignment_remove" in SKILL_SCHEMAS

    def test_upsert_person_name_required(self):
        schema = SKILL_SCHEMAS["cc_assignment_upsert"]
        assert schema["args"]["person_name"]["required"] is True

    def test_upsert_role_slug_required(self):
        schema = SKILL_SCHEMAS["cc_assignment_upsert"]
        assert schema["args"]["role_slug"]["required"] is True

    def test_upsert_client_name_optional(self):
        schema = SKILL_SCHEMAS["cc_assignment_upsert"]
        assert schema["args"]["client_name"]["required"] is False

    def test_upsert_brand_name_optional(self):
        schema = SKILL_SCHEMAS["cc_assignment_upsert"]
        assert schema["args"]["brand_name"]["required"] is False

    def test_validate_upsert_valid(self):
        errors = validate_skill_call(
            "cc_assignment_upsert",
            {"person_name": "Sarah", "role_slug": "ppc_strategist"},
        )
        assert errors == []

    def test_validate_upsert_missing_person(self):
        errors = validate_skill_call("cc_assignment_upsert", {"role_slug": "csl"})
        assert any("person_name" in e for e in errors)

    def test_validate_upsert_missing_role(self):
        errors = validate_skill_call("cc_assignment_upsert", {"person_name": "Sarah"})
        assert any("role_slug" in e for e in errors)

    def test_validate_remove_valid(self):
        errors = validate_skill_call(
            "cc_assignment_remove",
            {"person_name": "Sarah", "role_slug": "ppc_strategist"},
        )
        assert errors == []


# ---------------------------------------------------------------------------
# Service layer: resolve_person
# ---------------------------------------------------------------------------


class TestResolvePerson:
    def test_exact_match(self):
        db = _mock_db_with_profiles([
            {"id": "p1", "display_name": "Sarah", "full_name": "Sarah Smith", "email": "s@x.com", "employment_status": "active"},
        ])
        result = resolve_person(db, "Sarah")
        assert result["status"] == "ok"
        assert result["profile_id"] == "p1"
        assert result["display_name"] == "Sarah"

    def test_prefix_match(self):
        db = _mock_db_with_profiles([
            {"id": "p1", "display_name": "Sarah Smith", "full_name": "Sarah Smith", "email": "s@x.com", "employment_status": "active"},
        ])
        result = resolve_person(db, "Sarah")
        assert result["status"] == "ok"
        assert result["profile_id"] == "p1"

    def test_not_found(self):
        db = _mock_db_with_profiles([
            {"id": "p1", "display_name": "John", "full_name": "John Doe", "email": "j@x.com", "employment_status": "active"},
        ])
        result = resolve_person(db, "Sarah")
        assert result["status"] == "not_found"

    def test_ambiguous(self):
        db = _mock_db_with_profiles([
            {"id": "p1", "display_name": "Sarah Smith", "full_name": "Sarah Smith", "email": "s1@x.com", "employment_status": "active"},
            {"id": "p2", "display_name": "Sarah Jones", "full_name": "Sarah Jones", "email": "s2@x.com", "employment_status": "active"},
        ])
        result = resolve_person(db, "Sarah")
        assert result["status"] == "ambiguous"
        assert len(result["candidates"]) == 2

    def test_empty_query(self):
        db = _mock_db_with_profiles([])
        result = resolve_person(db, "")
        assert result["status"] == "not_found"

    def test_exact_beats_prefix(self):
        db = _mock_db_with_profiles([
            {"id": "p1", "display_name": "Sarah", "full_name": "Sarah", "email": "s@x.com", "employment_status": "active"},
            {"id": "p2", "display_name": "Sarah Smith", "full_name": "Sarah Smith", "email": "s2@x.com", "employment_status": "active"},
        ])
        result = resolve_person(db, "sarah")
        assert result["status"] == "ok"
        assert result["profile_id"] == "p1"


# ---------------------------------------------------------------------------
# Service layer: resolve_role
# ---------------------------------------------------------------------------


class TestResolveRole:
    def test_exact_slug(self):
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
            _fake_db_response([{"id": "r1", "slug": "ppc_strategist", "name": "PPC Strategist"}])
        )
        result = resolve_role(db, "ppc_strategist")
        assert result["status"] == "ok"
        assert result["role_id"] == "r1"
        assert result["role_slug"] == "ppc_strategist"

    def test_alias_csl(self):
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
            _fake_db_response([{"id": "r2", "slug": "customer_success_lead", "name": "Customer Success Lead"}])
        )
        result = resolve_role(db, "csl")
        assert result["status"] == "ok"
        assert result["role_slug"] == "customer_success_lead"

    def test_not_found(self):
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
            _fake_db_response([])
        )
        result = resolve_role(db, "nonexistent_role")
        assert result["status"] == "not_found"

    def test_empty_query(self):
        result = resolve_role(MagicMock(), "")
        assert result["status"] == "not_found"


# ---------------------------------------------------------------------------
# Service layer: resolve_brand_for_assignment
# ---------------------------------------------------------------------------


class TestResolveBrandForAssignment:
    def test_single_match(self):
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = (
            _fake_db_response([{"id": "b1", "name": "Brand Alpha"}])
        )
        result = resolve_brand_for_assignment(db, "client-1", "Brand Alpha")
        assert result["status"] == "ok"
        assert result["brand_id"] == "b1"

    def test_not_found(self):
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = (
            _fake_db_response([{"id": "b1", "name": "Brand Alpha"}])
        )
        result = resolve_brand_for_assignment(db, "client-1", "NoSuch")
        assert result["status"] == "not_found"

    def test_ambiguous(self):
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = (
            _fake_db_response([
                {"id": "b1", "name": "Brand Alpha One"},
                {"id": "b2", "name": "Brand Alpha Two"},
            ])
        )
        # "brand alpha" is a substring of both but exact match of neither
        result = resolve_brand_for_assignment(db, "client-1", "brand alpha")
        assert result["status"] == "ambiguous"
        assert len(result["candidates"]) == 2

    def test_skipped_when_empty(self):
        result = resolve_brand_for_assignment(MagicMock(), "client-1", "")
        assert result["status"] == "skipped"


# ---------------------------------------------------------------------------
# Formatting tests
# ---------------------------------------------------------------------------


class TestAssignmentFormatters:
    def test_format_upsert_ok(self):
        result = {"status": "ok", "message": "Assignment created.", "previous_assignee": None}
        text = format_upsert_result(result, "Sarah", "PPC Strategist", "Distex")
        assert "Sarah" in text
        assert "PPC Strategist" in text
        assert "Distex" in text

    def test_format_upsert_replaced(self):
        result = {"status": "replaced", "message": "Assignment updated.", "previous_assignee": "John"}
        text = format_upsert_result(result, "Sarah", "PPC Strategist", "Distex")
        assert "John" in text
        assert "Sarah" in text

    def test_format_upsert_with_brand(self):
        result = {"status": "ok", "message": "Assignment created.", "previous_assignee": None}
        text = format_upsert_result(result, "Sarah", "PPC Strategist", "Distex", brand_name="Brand A")
        assert "Brand A" in text
        assert "Distex" in text

    def test_format_remove_ok(self):
        result = {"status": "ok", "message": "Assignment removed.", "previous_assignee": None}
        text = format_remove_result(result, "Sarah", "PPC Strategist", "Distex")
        assert "Sarah" in text
        assert "Removed" in text

    def test_format_remove_not_found(self):
        result = {"status": "not_found", "message": "No matching assignment found.", "previous_assignee": None}
        text = format_remove_result(result, "Sarah", "PPC Strategist", "Distex")
        assert "No assignment found" in text

    def test_format_person_ambiguous(self):
        candidates = [
            {"display_name": "Sarah Smith", "email": "s1@x.com"},
            {"display_name": "Sarah Jones", "email": "s2@x.com"},
        ]
        text = format_person_ambiguous(candidates)
        assert "Sarah Smith" in text
        assert "Sarah Jones" in text
        assert "s1@x.com" in text


# ---------------------------------------------------------------------------
# Handler tests
# ---------------------------------------------------------------------------


class TestHandleAssignmentUpsert:
    @pytest.mark.asyncio
    async def test_upsert_happy_path(self):
        session = MagicMock(profile_id="p1", active_client_id="client-1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        session_service.get_client_name.return_value = "Distex"
        slack = AsyncMock()

        person_result = {"status": "ok", "profile_id": "p2", "display_name": "Sarah", "candidates": []}
        role_result = {"status": "ok", "role_id": "r1", "role_slug": "ppc_strategist", "role_name": "PPC Strategist"}
        assign_result = {"status": "ok", "message": "Assignment created.", "previous_assignee": None}

        with (
            patch("app.api.routes.slack.resolve_person", return_value=person_result),
            patch("app.api.routes.slack.resolve_role", return_value=role_result),
            patch("app.api.routes.slack.upsert_assignment", return_value=assign_result),
        ):
            summary = await _handle_cc_skill(
                skill_id="cc_assignment_upsert",
                args={"person_name": "Sarah", "role_slug": "ppc_strategist"},
                session=session,
                session_service=session_service,
                channel="D1",
                slack=slack,
            )

        assert summary == "[Assignment upsert]"
        posted = slack.post_message.call_args.kwargs.get("text", "")
        assert "Sarah" in posted
        assert "PPC Strategist" in posted

    @pytest.mark.asyncio
    async def test_upsert_person_not_found(self):
        session = MagicMock(profile_id="p1", active_client_id="client-1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        slack = AsyncMock()

        person_result = {"status": "not_found", "profile_id": None, "display_name": None, "candidates": []}

        with patch("app.api.routes.slack.resolve_person", return_value=person_result):
            summary = await _handle_cc_skill(
                skill_id="cc_assignment_upsert",
                args={"person_name": "Nobody", "role_slug": "csl"},
                session=session,
                session_service=session_service,
                channel="D1",
                slack=slack,
            )

        assert "person not found" in summary.lower()
        posted = slack.post_message.call_args.kwargs.get("text", "")
        assert "couldn't find" in posted.lower()

    @pytest.mark.asyncio
    async def test_upsert_person_ambiguous(self):
        session = MagicMock(profile_id="p1", active_client_id="client-1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        slack = AsyncMock()

        person_result = {
            "status": "ambiguous",
            "profile_id": None,
            "display_name": None,
            "candidates": [
                {"display_name": "Sarah Smith", "email": "s1@x.com"},
                {"display_name": "Sarah Jones", "email": "s2@x.com"},
            ],
        }

        with patch("app.api.routes.slack.resolve_person", return_value=person_result):
            summary = await _handle_cc_skill(
                skill_id="cc_assignment_upsert",
                args={"person_name": "Sarah", "role_slug": "csl"},
                session=session,
                session_service=session_service,
                channel="D1",
                slack=slack,
            )

        assert "ambiguous" in summary.lower()
        posted = slack.post_message.call_args.kwargs.get("text", "")
        assert "Sarah Smith" in posted

    @pytest.mark.asyncio
    async def test_upsert_role_not_found(self):
        session = MagicMock(profile_id="p1", active_client_id="client-1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        slack = AsyncMock()

        person_result = {"status": "ok", "profile_id": "p2", "display_name": "Sarah", "candidates": []}
        role_result = {"status": "not_found", "role_id": None, "role_slug": None, "role_name": None}

        with (
            patch("app.api.routes.slack.resolve_person", return_value=person_result),
            patch("app.api.routes.slack.resolve_role", return_value=role_result),
        ):
            summary = await _handle_cc_skill(
                skill_id="cc_assignment_upsert",
                args={"person_name": "Sarah", "role_slug": "fake_role"},
                session=session,
                session_service=session_service,
                channel="D1",
                slack=slack,
            )

        assert "role not found" in summary.lower()

    @pytest.mark.asyncio
    async def test_upsert_with_brand(self):
        session = MagicMock(profile_id="p1", active_client_id="client-1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        session_service.get_client_name.return_value = "Distex"
        slack = AsyncMock()

        person_result = {"status": "ok", "profile_id": "p2", "display_name": "Sarah", "candidates": []}
        role_result = {"status": "ok", "role_id": "r1", "role_slug": "ppc_strategist", "role_name": "PPC Strategist"}
        brand_result = {"status": "ok", "brand_id": "b1", "brand_name": "Brand Alpha", "candidates": []}
        assign_result = {"status": "ok", "message": "Assignment created.", "previous_assignee": None}

        with (
            patch("app.api.routes.slack.resolve_person", return_value=person_result),
            patch("app.api.routes.slack.resolve_role", return_value=role_result),
            patch("app.api.routes.slack.resolve_brand_for_assignment", return_value=brand_result),
            patch("app.api.routes.slack.upsert_assignment", return_value=assign_result),
        ):
            summary = await _handle_cc_skill(
                skill_id="cc_assignment_upsert",
                args={"person_name": "Sarah", "role_slug": "ppc_strategist", "brand_name": "Brand Alpha"},
                session=session,
                session_service=session_service,
                channel="D1",
                slack=slack,
            )

        assert summary == "[Assignment upsert]"
        posted = slack.post_message.call_args.kwargs.get("text", "")
        assert "Brand Alpha" in posted

    @pytest.mark.asyncio
    async def test_upsert_replaced(self):
        session = MagicMock(profile_id="p1", active_client_id="client-1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        session_service.get_client_name.return_value = "Distex"
        slack = AsyncMock()

        person_result = {"status": "ok", "profile_id": "p2", "display_name": "Sarah", "candidates": []}
        role_result = {"status": "ok", "role_id": "r1", "role_slug": "csl", "role_name": "Customer Success Lead"}
        assign_result = {"status": "replaced", "message": "Assignment updated.", "previous_assignee": "John"}

        with (
            patch("app.api.routes.slack.resolve_person", return_value=person_result),
            patch("app.api.routes.slack.resolve_role", return_value=role_result),
            patch("app.api.routes.slack.upsert_assignment", return_value=assign_result),
        ):
            summary = await _handle_cc_skill(
                skill_id="cc_assignment_upsert",
                args={"person_name": "Sarah", "role_slug": "csl"},
                session=session,
                session_service=session_service,
                channel="D1",
                slack=slack,
            )

        assert summary == "[Assignment upsert]"
        posted = slack.post_message.call_args.kwargs.get("text", "")
        assert "John" in posted
        assert "Sarah" in posted


class TestHandleAssignmentRemove:
    @pytest.mark.asyncio
    async def test_remove_happy_path(self):
        session = MagicMock(profile_id="p1", active_client_id="client-1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        session_service.get_client_name.return_value = "Distex"
        slack = AsyncMock()

        person_result = {"status": "ok", "profile_id": "p2", "display_name": "Sarah", "candidates": []}
        role_result = {"status": "ok", "role_id": "r1", "role_slug": "ppc_strategist", "role_name": "PPC Strategist"}
        remove_result = {"status": "ok", "message": "Assignment removed.", "previous_assignee": None}

        with (
            patch("app.api.routes.slack.resolve_person", return_value=person_result),
            patch("app.api.routes.slack.resolve_role", return_value=role_result),
            patch("app.api.routes.slack.remove_assignment", return_value=remove_result),
        ):
            summary = await _handle_cc_skill(
                skill_id="cc_assignment_remove",
                args={"person_name": "Sarah", "role_slug": "ppc_strategist"},
                session=session,
                session_service=session_service,
                channel="D1",
                slack=slack,
            )

        assert summary == "[Assignment remove]"
        posted = slack.post_message.call_args.kwargs.get("text", "")
        assert "Removed" in posted
        assert "Sarah" in posted

    @pytest.mark.asyncio
    async def test_remove_not_found(self):
        session = MagicMock(profile_id="p1", active_client_id="client-1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        session_service.get_client_name.return_value = "Distex"
        slack = AsyncMock()

        person_result = {"status": "ok", "profile_id": "p2", "display_name": "Sarah", "candidates": []}
        role_result = {"status": "ok", "role_id": "r1", "role_slug": "csl", "role_name": "CSL"}
        remove_result = {"status": "not_found", "message": "No matching assignment found to remove.", "previous_assignee": None}

        with (
            patch("app.api.routes.slack.resolve_person", return_value=person_result),
            patch("app.api.routes.slack.resolve_role", return_value=role_result),
            patch("app.api.routes.slack.remove_assignment", return_value=remove_result),
        ):
            summary = await _handle_cc_skill(
                skill_id="cc_assignment_remove",
                args={"person_name": "Sarah", "role_slug": "csl"},
                session=session,
                session_service=session_service,
                channel="D1",
                slack=slack,
            )

        assert summary == "[Assignment remove]"
        posted = slack.post_message.call_args.kwargs.get("text", "")
        assert "No assignment found" in posted

    @pytest.mark.asyncio
    async def test_remove_person_not_found(self):
        session = MagicMock(profile_id="p1", active_client_id="client-1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        slack = AsyncMock()

        person_result = {"status": "not_found", "profile_id": None, "display_name": None, "candidates": []}

        with patch("app.api.routes.slack.resolve_person", return_value=person_result):
            summary = await _handle_cc_skill(
                skill_id="cc_assignment_remove",
                args={"person_name": "Nobody", "role_slug": "csl"},
                session=session,
                session_service=session_service,
                channel="D1",
                slack=slack,
            )

        assert "person not found" in summary.lower()

    @pytest.mark.asyncio
    async def test_remove_client_not_found(self):
        session = MagicMock(profile_id="p1", active_client_id=None)
        session_service = MagicMock()
        session_service.db = MagicMock()
        session_service.find_client_matches.return_value = []
        slack = AsyncMock()

        summary = await _handle_cc_skill(
            skill_id="cc_assignment_remove",
            args={"person_name": "Sarah", "role_slug": "csl", "client_name": "NoSuch"},
            session=session,
            session_service=session_service,
            channel="D1",
            slack=slack,
        )

        assert "client error" in summary.lower()


# ---------------------------------------------------------------------------
# Fix 1: Active client fallback tests
# ---------------------------------------------------------------------------


class TestAssignmentClientFallback:
    @pytest.mark.asyncio
    async def test_upsert_no_client_name_uses_active_client(self):
        """When client_name is omitted, use session.active_client_id."""
        session = MagicMock(profile_id="p1", active_client_id="client-1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        session_service.get_client_name.return_value = "Distex"
        slack = AsyncMock()

        person_result = {"status": "ok", "profile_id": "p2", "display_name": "Sarah", "candidates": []}
        role_result = {"status": "ok", "role_id": "r1", "role_slug": "csl", "role_name": "CSL"}
        assign_result = {"status": "ok", "message": "Assignment created.", "previous_assignee": None}

        with (
            patch("app.api.routes.slack.resolve_person", return_value=person_result),
            patch("app.api.routes.slack.resolve_role", return_value=role_result),
            patch("app.api.routes.slack.upsert_assignment", return_value=assign_result) as mock_upsert,
        ):
            summary = await _handle_cc_skill(
                skill_id="cc_assignment_upsert",
                args={"person_name": "Sarah", "role_slug": "csl"},
                session=session,
                session_service=session_service,
                channel="D1",
                slack=slack,
            )

        assert summary == "[Assignment upsert]"
        # Verify the active client_id was used
        mock_upsert.assert_called_once()
        call_kwargs = mock_upsert.call_args
        assert call_kwargs[1]["client_id"] == "client-1" or call_kwargs[0][1] == "client-1"

    @pytest.mark.asyncio
    async def test_remove_no_client_name_uses_active_client(self):
        """When client_name is omitted, use session.active_client_id for remove."""
        session = MagicMock(profile_id="p1", active_client_id="client-1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        session_service.get_client_name.return_value = "Distex"
        slack = AsyncMock()

        person_result = {"status": "ok", "profile_id": "p2", "display_name": "Sarah", "candidates": []}
        role_result = {"status": "ok", "role_id": "r1", "role_slug": "csl", "role_name": "CSL"}
        remove_result = {"status": "ok", "message": "Assignment removed.", "previous_assignee": None}

        with (
            patch("app.api.routes.slack.resolve_person", return_value=person_result),
            patch("app.api.routes.slack.resolve_role", return_value=role_result),
            patch("app.api.routes.slack.remove_assignment", return_value=remove_result) as mock_remove,
        ):
            summary = await _handle_cc_skill(
                skill_id="cc_assignment_remove",
                args={"person_name": "Sarah", "role_slug": "csl"},
                session=session,
                session_service=session_service,
                channel="D1",
                slack=slack,
            )

        assert summary == "[Assignment remove]"
        mock_remove.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_client_name_no_active_client_shows_picker(self):
        """No client_name + no active client -> shows picker."""
        session = MagicMock(profile_id="p1", active_client_id=None)
        session_service = MagicMock()
        session_service.db = MagicMock()
        session_service.list_clients_for_picker.return_value = [
            {"id": "c1", "name": "Acme"},
            {"id": "c2", "name": "Distex"},
        ]
        slack = AsyncMock()

        summary = await _handle_cc_skill(
            skill_id="cc_assignment_upsert",
            args={"person_name": "Sarah", "role_slug": "csl"},
            session=session,
            session_service=session_service,
            channel="D1",
            slack=slack,
        )

        assert "client error" in summary.lower()
        posted = slack.post_message.call_args.kwargs.get("text", "")
        assert "which client" in posted.lower() or "switch to" in posted.lower()

    @pytest.mark.asyncio
    async def test_no_client_name_no_active_no_clients_shows_message(self):
        """No client_name + no active + no accessible clients -> shows fallback message."""
        session = MagicMock(profile_id="p1", active_client_id=None)
        session_service = MagicMock()
        session_service.db = MagicMock()
        session_service.list_clients_for_picker.return_value = []
        slack = AsyncMock()

        summary = await _handle_cc_skill(
            skill_id="cc_assignment_upsert",
            args={"person_name": "Sarah", "role_slug": "csl"},
            session=session,
            session_service=session_service,
            channel="D1",
            slack=slack,
        )

        assert "client error" in summary.lower()
        posted = slack.post_message.call_args.kwargs.get("text", "")
        assert "switch to" in posted.lower()


# ---------------------------------------------------------------------------
# Fix 2: Role alias tests (bm, brand_manager -> CSL)
# ---------------------------------------------------------------------------


class TestRoleAliasFixups:
    def test_bm_resolves_to_csl(self):
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
            _fake_db_response([{"id": "r2", "slug": "customer_success_lead", "name": "Customer Success Lead"}])
        )
        result = resolve_role(db, "bm")
        assert result["status"] == "ok"
        assert result["role_slug"] == "customer_success_lead"

    def test_brand_manager_resolves_to_csl(self):
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
            _fake_db_response([{"id": "r2", "slug": "customer_success_lead", "name": "Customer Success Lead"}])
        )
        result = resolve_role(db, "brand_manager")
        assert result["status"] == "ok"
        assert result["role_slug"] == "customer_success_lead"

    def test_csl_still_resolves_to_csl(self):
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
            _fake_db_response([{"id": "r2", "slug": "customer_success_lead", "name": "Customer Success Lead"}])
        )
        result = resolve_role(db, "csl")
        assert result["status"] == "ok"
        assert result["role_slug"] == "customer_success_lead"


# ---------------------------------------------------------------------------
# Fix 3: Atomic upsert replacement tests
# ---------------------------------------------------------------------------


class TestAtomicUpsertReplacement:
    def test_replace_uses_update_not_delete(self):
        """When replacing an existing assignee, should UPDATE the row, not DELETE+INSERT."""
        db = MagicMock()

        # Mock: existing assignment found
        existing_row = {
            "id": "assign-1",
            "team_member_id": "old-person",
            "profiles": {"display_name": "Old Person", "full_name": "Old Person"},
        }
        select_chain = MagicMock()
        select_chain.eq.return_value = select_chain
        select_chain.is_.return_value = select_chain
        select_chain.limit.return_value = select_chain
        select_chain.execute.return_value = _fake_db_response([existing_row])

        update_chain = MagicMock()
        update_chain.eq.return_value = update_chain
        update_chain.execute.return_value = _fake_db_response([])

        delete_chain = MagicMock()
        delete_chain.eq.return_value = delete_chain

        def _table(name):
            t = MagicMock()
            t.select.return_value = select_chain
            t.update.return_value = update_chain
            t.delete.return_value = delete_chain
            t.insert.return_value = MagicMock()
            return t

        db.table.side_effect = _table

        result = upsert_assignment(
            db,
            client_id="c1",
            team_member_id="new-person",
            role_id="r1",
            assigned_by="admin-1",
        )

        assert result["status"] == "replaced"
        assert result["previous_assignee"] == "Old Person"
        # Verify UPDATE was called (not DELETE+INSERT)
        update_chain.eq.assert_called_with("id", "assign-1")
        # DELETE should NOT have been called on the existing row
        delete_chain.eq.assert_not_called()

    def test_insert_failure_does_not_lose_prior_assignment(self):
        """If insert fails for a new slot, no prior assignment is affected."""
        db = MagicMock()

        # Mock: no existing assignment
        select_chain = MagicMock()
        select_chain.eq.return_value = select_chain
        select_chain.is_.return_value = select_chain
        select_chain.limit.return_value = select_chain
        select_chain.execute.return_value = _fake_db_response([])

        insert_chain = MagicMock()
        insert_chain.execute.side_effect = Exception("DB insert failed")

        def _table(name):
            t = MagicMock()
            t.select.return_value = select_chain
            t.insert.return_value = insert_chain
            return t

        db.table.side_effect = _table

        result = upsert_assignment(
            db,
            client_id="c1",
            team_member_id="new-person",
            role_id="r1",
        )

        assert result["status"] == "error"
        assert "DB insert failed" in result["message"]

    def test_update_failure_preserves_prior_assignment(self):
        """If update fails during replacement, existing row is preserved (error returned)."""
        db = MagicMock()

        # Mock: existing assignment found
        existing_row = {
            "id": "assign-1",
            "team_member_id": "old-person",
            "profiles": {"display_name": "Old Person", "full_name": "Old Person"},
        }
        select_chain = MagicMock()
        select_chain.eq.return_value = select_chain
        select_chain.is_.return_value = select_chain
        select_chain.limit.return_value = select_chain
        select_chain.execute.return_value = _fake_db_response([existing_row])

        update_chain = MagicMock()
        update_chain.eq.return_value = update_chain
        update_chain.execute.side_effect = Exception("DB update failed")

        def _table(name):
            t = MagicMock()
            t.select.return_value = select_chain
            t.update.return_value = update_chain
            return t

        db.table.side_effect = _table

        result = upsert_assignment(
            db,
            client_id="c1",
            team_member_id="new-person",
            role_id="r1",
        )

        # Should return error — existing assignment was NOT deleted
        assert result["status"] == "error"
        assert "DB update failed" in result["message"]
