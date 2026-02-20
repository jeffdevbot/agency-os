"""Tests for C11A: Command Center integration (classifier, policy, registry).

Covers:
- Classifier recognizes CC skill phrases
- Policy gate: member can use lookup/brands, admin can audit, non-admin denied
- Tool registry includes all 3 CC skills
- Tool descriptions include CC skills in prompt
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.routes.slack import _classify_message, _handle_cc_skill
from app.services.agencyclaw.policy_gate import (
    ActorContext,
    SurfaceContext,
    evaluate_tool_policy,
)
from app.services.agencyclaw.tool_registry import (
    TOOL_SCHEMAS,
    get_tool_descriptions_for_prompt,
    validate_tool_call,
)


# ---------------------------------------------------------------------------
# Classifier tests
# ---------------------------------------------------------------------------


class TestClassifierCCSkills:
    def test_show_me_clients(self):
        intent, params = _classify_message("show me clients")
        assert intent == "cc_client_lookup"

    def test_list_clients(self):
        intent, params = _classify_message("list clients")
        assert intent == "cc_client_lookup"

    def test_my_clients(self):
        intent, params = _classify_message("my clients")
        assert intent == "cc_client_lookup"

    def test_list_all_brands(self):
        intent, params = _classify_message("list all brands")
        assert intent == "cc_brand_list_all"

    def test_list_brands(self):
        intent, params = _classify_message("list brands")
        assert intent == "cc_brand_list_all"

    def test_show_brands(self):
        intent, params = _classify_message("show brands")
        assert intent == "cc_brand_list_all"

    def test_missing_clickup_mapping(self):
        intent, params = _classify_message("which brands are missing clickup mapping?")
        assert intent == "cc_brand_clickup_mapping_audit"

    def test_mapping_audit(self):
        intent, params = _classify_message("run a mapping audit")
        assert intent == "cc_brand_clickup_mapping_audit"

    def test_brands_missing(self):
        intent, params = _classify_message("brands missing clickup config")
        assert intent == "cc_brand_clickup_mapping_audit"

    def test_unrelated_not_matched(self):
        """Unrelated message should not match CC skills."""
        intent, params = _classify_message("hello there")
        assert intent == "help"

    def test_create_task_not_intercepted(self):
        """Task creation should not be hijacked by CC classifier."""
        intent, params = _classify_message("create task for Distex: Fix listing")
        assert intent == "create_task"


# ---------------------------------------------------------------------------
# Policy gate tests
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


class TestPolicyCCSkills:
    def test_member_can_lookup_clients(self):
        policy = evaluate_tool_policy(_actor(), _dm_surface(), "cc_client_lookup")
        assert policy["allowed"] is True

    def test_member_can_list_brands(self):
        policy = evaluate_tool_policy(_actor(), _dm_surface(), "cc_brand_list_all")
        assert policy["allowed"] is True

    def test_admin_can_audit(self):
        policy = evaluate_tool_policy(
            _actor(role="admin", is_admin=True), _dm_surface(), "cc_brand_clickup_mapping_audit"
        )
        assert policy["allowed"] is True

    def test_non_admin_denied_audit(self):
        policy = evaluate_tool_policy(_actor(), _dm_surface(), "cc_brand_clickup_mapping_audit")
        assert policy["allowed"] is False
        assert policy["reason_code"] == "admin_skill_denied"
        assert "admin" in policy["user_message"].lower()

    def test_viewer_can_read_clients(self):
        policy = evaluate_tool_policy(
            _actor(role="viewer"), _dm_surface(), "cc_client_lookup"
        )
        assert policy["allowed"] is True

    def test_viewer_can_read_brands(self):
        policy = evaluate_tool_policy(
            _actor(role="viewer"), _dm_surface(), "cc_brand_list_all"
        )
        assert policy["allowed"] is True

    def test_viewer_denied_audit(self):
        policy = evaluate_tool_policy(
            _actor(role="viewer"), _dm_surface(), "cc_brand_clickup_mapping_audit"
        )
        assert policy["allowed"] is False
        assert policy["reason_code"] == "admin_skill_denied"

    def test_unknown_actor_denied(self):
        policy = evaluate_tool_policy(
            _actor(role="unknown"), _dm_surface(), "cc_client_lookup"
        )
        assert policy["allowed"] is False
        assert policy["reason_code"] == "unknown_actor"

    def test_non_dm_surface_denied(self):
        surface = SurfaceContext(channel_id="C1", surface_type="channel")
        policy = evaluate_tool_policy(_actor(), surface, "cc_client_lookup")
        assert policy["allowed"] is False

    def test_existing_mutation_still_blocked_for_viewer(self):
        """Regression: viewer still can't create tasks."""
        policy = evaluate_tool_policy(
            _actor(role="viewer"), _dm_surface(), "clickup_task_create"
        )
        assert policy["allowed"] is False
        assert policy["reason_code"] == "viewer_mutation_denied"

    def test_existing_read_still_works(self):
        """Regression: existing weekly tasks skill still works."""
        policy = evaluate_tool_policy(_actor(), _dm_surface(), "clickup_task_list_weekly")
        assert policy["allowed"] is True


# ---------------------------------------------------------------------------
# Tool registry tests
# ---------------------------------------------------------------------------


class TestToolRegistryCCSkills:
    def test_cc_client_lookup_registered(self):
        assert "cc_client_lookup" in TOOL_SCHEMAS

    def test_cc_brand_list_all_registered(self):
        assert "cc_brand_list_all" in TOOL_SCHEMAS

    def test_cc_brand_clickup_mapping_audit_registered(self):
        assert "cc_brand_clickup_mapping_audit" in TOOL_SCHEMAS

    def test_audit_has_no_required_args(self):
        schema = TOOL_SCHEMAS["cc_brand_clickup_mapping_audit"]
        assert schema["args"] == {}

    def test_client_lookup_query_optional(self):
        schema = TOOL_SCHEMAS["cc_client_lookup"]
        assert schema["args"]["query"]["required"] is False

    def test_brand_list_client_name_optional(self):
        schema = TOOL_SCHEMAS["cc_brand_list_all"]
        assert schema["args"]["client_name"]["required"] is False

    def test_validate_client_lookup_valid(self):
        errors = validate_tool_call("cc_client_lookup", {"query": "dist"})
        assert errors == []

    def test_validate_client_lookup_no_args(self):
        errors = validate_tool_call("cc_client_lookup", {})
        assert errors == []

    def test_validate_audit_no_args(self):
        errors = validate_tool_call("cc_brand_clickup_mapping_audit", {})
        assert errors == []

    def test_tool_descriptions_include_cc(self):
        desc = get_tool_descriptions_for_prompt()
        assert "cc_client_lookup" in desc
        assert "cc_brand_list_all" in desc
        assert "cc_brand_clickup_mapping_audit" in desc

    def test_existing_skills_still_present(self):
        """Regression: existing skills not removed."""
        assert "clickup_task_create" in TOOL_SCHEMAS
        assert "clickup_task_list_weekly" in TOOL_SCHEMAS
        assert "ngram_research" in TOOL_SCHEMAS


# ---------------------------------------------------------------------------
# Slack CC handler behavior
# ---------------------------------------------------------------------------


class TestHandleCCSkillBrandListDisambiguation:
    @pytest.mark.asyncio
    async def test_client_hint_not_found_does_not_fallback_to_all_brands(self):
        session = MagicMock(profile_id="p1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        session_service.find_client_matches.return_value = []
        slack = AsyncMock()

        with patch("app.api.routes.slack.list_brands") as mock_list_brands:
            summary = await _handle_cc_skill(
                skill_id="cc_brand_list_all",
                args={"client_name": "NoSuchClient"},
                session=session,
                session_service=session_service,
                channel="D1",
                slack=slack,
            )

        assert summary == "[Brand list client not found]"
        mock_list_brands.assert_not_called()
        msg = slack.post_message.call_args.kwargs.get("text", "")
        assert "couldn't find a client" in msg.lower()

    @pytest.mark.asyncio
    async def test_client_hint_ambiguous_prompts_picker(self):
        session = MagicMock(profile_id="p1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        session_service.find_client_matches.return_value = [
            {"id": "c1", "name": "Distex US"},
            {"id": "c2", "name": "Distex CA"},
        ]
        slack = AsyncMock()

        with patch("app.api.routes.slack.list_brands") as mock_list_brands:
            summary = await _handle_cc_skill(
                skill_id="cc_brand_list_all",
                args={"client_name": "Distex"},
                session=session,
                session_service=session_service,
                channel="D1",
                slack=slack,
            )

        assert summary == "[Brand list client ambiguous]"
        mock_list_brands.assert_not_called()
        kwargs = slack.post_message.call_args.kwargs
        assert "multiple clients match" in kwargs.get("text", "").lower()
        assert kwargs.get("blocks") is not None

    @pytest.mark.asyncio
    async def test_client_hint_single_match_filters_brands(self):
        session = MagicMock(profile_id="p1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        session_service.find_client_matches.return_value = [
            {"id": "c1", "name": "Distex"},
        ]
        slack = AsyncMock()

        with (
            patch("app.api.routes.slack.list_brands", return_value=[{"name": "Brand A"}]) as mock_list_brands,
            patch("app.api.routes.slack.format_brand_list", return_value="formatted brand list"),
        ):
            summary = await _handle_cc_skill(
                skill_id="cc_brand_list_all",
                args={"client_name": "Distex"},
                session=session,
                session_service=session_service,
                channel="D1",
                slack=slack,
            )

        assert summary == "[Listed brands]"
        mock_list_brands.assert_called_once_with(session_service.db, "c1")
        assert slack.post_message.call_args.kwargs.get("text") == "formatted brand list"
