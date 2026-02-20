"""Tests for C11E: Brand mapping remediation runtime wiring.

Covers:
- Classifier recognizes remediation preview/apply phrases
- Policy gate: admin can preview/apply, non-admin denied
- Tool registry includes both remediation skills
- Handler coverage for preview/apply happy paths
- Formatting helpers produce readable output
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.routes.slack import (
    _classify_message,
    _format_remediation_apply_result,
    _format_remediation_preview,
    _handle_cc_skill,
)
from app.services.agencyclaw.policy_gate import (
    ActorContext,
    SurfaceContext,
    evaluate_skill_policy,
)
from app.services.agencyclaw.skill_registry import (
    SKILL_SCHEMAS,
    get_skill_descriptions_for_prompt,
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


# ---------------------------------------------------------------------------
# Classifier tests
# ---------------------------------------------------------------------------


class TestClassifierRemediationSkills:
    def test_preview_brand_mapping_remediation(self):
        intent, _ = _classify_message("preview brand mapping remediation")
        assert intent == "cc_brand_mapping_remediation_preview"

    def test_show_mapping_remediation_plan(self):
        intent, _ = _classify_message("show mapping remediation plan")
        assert intent == "cc_brand_mapping_remediation_preview"

    def test_what_can_we_auto_fix(self):
        intent, _ = _classify_message("what can we auto-fix for mappings")
        assert intent == "cc_brand_mapping_remediation_preview"

    def test_preview_mapping_remediation(self):
        intent, _ = _classify_message("preview mapping remediation")
        assert intent == "cc_brand_mapping_remediation_preview"

    def test_remediation_preview(self):
        intent, _ = _classify_message("remediation preview")
        assert intent == "cc_brand_mapping_remediation_preview"

    def test_mapping_remediation(self):
        intent, _ = _classify_message("mapping remediation")
        assert intent == "cc_brand_mapping_remediation_preview"

    def test_apply_brand_mapping_remediation(self):
        intent, _ = _classify_message("apply brand mapping remediation")
        assert intent == "cc_brand_mapping_remediation_apply"

    def test_apply_mapping_remediation(self):
        intent, _ = _classify_message("apply mapping remediation")
        assert intent == "cc_brand_mapping_remediation_apply"

    def test_run_mapping_remediation_now(self):
        intent, _ = _classify_message("run mapping remediation now")
        assert intent == "cc_brand_mapping_remediation_apply"

    def test_apply_remediation(self):
        intent, _ = _classify_message("apply remediation")
        assert intent == "cc_brand_mapping_remediation_apply"

    def test_apply_with_client_hint(self):
        intent, params = _classify_message("apply brand mapping remediation for Distex")
        assert intent == "cc_brand_mapping_remediation_apply"
        assert params.get("client_name") == "distex"

    def test_preview_with_client_hint(self):
        intent, params = _classify_message("preview mapping remediation for Revant")
        assert intent == "cc_brand_mapping_remediation_preview"
        assert params.get("client_name") == "revant"

    def test_generic_mapping_remediation_with_client_hint(self):
        intent, params = _classify_message("mapping remediation for Whoosh")
        assert intent == "cc_brand_mapping_remediation_preview"
        assert params.get("client_name") == "whoosh"

    def test_run_now_with_client_hint(self):
        intent, params = _classify_message("run mapping remediation now for Indigo")
        assert intent == "cc_brand_mapping_remediation_apply"
        assert params.get("client_name") == "indigo"

    def test_unrelated_not_matched(self):
        intent, _ = _classify_message("hello there")
        assert intent == "help"

    def test_mapping_audit_still_works(self):
        """Regression: existing mapping audit classifier unchanged."""
        intent, _ = _classify_message("run a mapping audit")
        assert intent == "cc_brand_clickup_mapping_audit"


# ---------------------------------------------------------------------------
# Policy gate tests
# ---------------------------------------------------------------------------


class TestPolicyRemediationSkills:
    def test_admin_can_preview(self):
        policy = evaluate_skill_policy(
            _actor(role="admin", is_admin=True),
            _dm_surface(),
            "cc_brand_mapping_remediation_preview",
        )
        assert policy["allowed"] is True

    def test_admin_can_apply(self):
        policy = evaluate_skill_policy(
            _actor(role="admin", is_admin=True),
            _dm_surface(),
            "cc_brand_mapping_remediation_apply",
        )
        assert policy["allowed"] is True

    def test_non_admin_denied_preview(self):
        policy = evaluate_skill_policy(
            _actor(),
            _dm_surface(),
            "cc_brand_mapping_remediation_preview",
        )
        assert policy["allowed"] is False
        assert policy["reason_code"] == "admin_skill_denied"

    def test_non_admin_denied_apply(self):
        policy = evaluate_skill_policy(
            _actor(),
            _dm_surface(),
            "cc_brand_mapping_remediation_apply",
        )
        assert policy["allowed"] is False
        assert policy["reason_code"] == "admin_skill_denied"

    def test_viewer_denied_preview(self):
        policy = evaluate_skill_policy(
            _actor(role="viewer"),
            _dm_surface(),
            "cc_brand_mapping_remediation_preview",
        )
        assert policy["allowed"] is False

    def test_viewer_denied_apply(self):
        policy = evaluate_skill_policy(
            _actor(role="viewer"),
            _dm_surface(),
            "cc_brand_mapping_remediation_apply",
        )
        assert policy["allowed"] is False

    def test_non_dm_denied(self):
        surface = SurfaceContext(channel_id="C1", surface_type="channel")
        policy = evaluate_skill_policy(
            _actor(role="admin", is_admin=True),
            surface,
            "cc_brand_mapping_remediation_preview",
        )
        assert policy["allowed"] is False

    def test_existing_audit_still_works(self):
        """Regression: existing mapping audit policy unchanged."""
        policy = evaluate_skill_policy(
            _actor(role="admin", is_admin=True),
            _dm_surface(),
            "cc_brand_clickup_mapping_audit",
        )
        assert policy["allowed"] is True


# ---------------------------------------------------------------------------
# Tool registry tests
# ---------------------------------------------------------------------------


class TestToolRegistryRemediationSkills:
    def test_preview_registered(self):
        assert "cc_brand_mapping_remediation_preview" in SKILL_SCHEMAS

    def test_apply_registered(self):
        assert "cc_brand_mapping_remediation_apply" in SKILL_SCHEMAS

    def test_preview_client_name_optional(self):
        schema = SKILL_SCHEMAS["cc_brand_mapping_remediation_preview"]
        assert schema["args"]["client_name"]["required"] is False

    def test_apply_client_name_optional(self):
        schema = SKILL_SCHEMAS["cc_brand_mapping_remediation_apply"]
        assert schema["args"]["client_name"]["required"] is False

    def test_validate_preview_no_args(self):
        errors = validate_skill_call("cc_brand_mapping_remediation_preview", {})
        assert errors == []

    def test_validate_apply_with_client(self):
        errors = validate_skill_call(
            "cc_brand_mapping_remediation_apply", {"client_name": "Distex"}
        )
        assert errors == []

    def test_tool_descriptions_include_remediation(self):
        desc = get_skill_descriptions_for_prompt()
        assert "cc_brand_mapping_remediation_preview" in desc
        assert "cc_brand_mapping_remediation_apply" in desc

    def test_existing_skills_still_present(self):
        """Regression."""
        assert "clickup_task_create" in SKILL_SCHEMAS
        assert "cc_brand_clickup_mapping_audit" in SKILL_SCHEMAS


# ---------------------------------------------------------------------------
# Formatting tests
# ---------------------------------------------------------------------------


class TestFormatRemediationPreview:
    def test_empty_plan(self):
        text = _format_remediation_preview([])
        assert "nothing to remediate" in text.lower()

    def test_safe_items_shown(self):
        plan = [
            {
                "brand_name": "Thorinox",
                "client_name": "Distex",
                "proposed_space_id": "sp1",
                "proposed_list_id": "l1",
                "safe_to_apply": True,
                "reason": "single client default mapping",
            }
        ]
        text = _format_remediation_preview(plan)
        assert "Thorinox" in text
        assert "Safe to apply: 1" in text
        assert "Blocked: 0" in text
        assert "apply brand mapping remediation" in text.lower()

    def test_blocked_items_shown(self):
        plan = [
            {
                "brand_name": "BadBrand",
                "client_name": "Distex",
                "safe_to_apply": False,
                "reason": "multiple defaults for clickup_list_id",
            }
        ]
        text = _format_remediation_preview(plan)
        assert "BadBrand" in text
        assert "Blocked: 1" in text
        assert "multiple defaults" in text

    def test_mixed_safe_and_blocked(self):
        plan = [
            {"brand_name": "A", "client_name": "C1", "proposed_space_id": "s", "proposed_list_id": "l", "safe_to_apply": True, "reason": "ok"},
            {"brand_name": "B", "client_name": "C1", "safe_to_apply": False, "reason": "no defaults"},
        ]
        text = _format_remediation_preview(plan)
        assert "Safe to apply: 1" in text
        assert "Blocked: 1" in text


class TestFormatRemediationApplyResult:
    def test_success(self):
        result = {"applied": 3, "skipped": 1, "failures": []}
        text = _format_remediation_apply_result(result)
        assert "Applied: 3" in text
        assert "Skipped: 1" in text
        assert "Failures: 0" in text

    def test_with_failures(self):
        result = {
            "applied": 1,
            "skipped": 0,
            "failures": [{"brand_id": "b1", "error": "timeout"}],
        }
        text = _format_remediation_apply_result(result)
        assert "Failures: 1" in text
        assert "timeout" in text

    def test_zero_applied_no_verify_prompt(self):
        result = {"applied": 0, "skipped": 2, "failures": []}
        text = _format_remediation_apply_result(result)
        assert "preview brand mapping remediation" not in text.lower()


# ---------------------------------------------------------------------------
# Handler behavior tests
# ---------------------------------------------------------------------------


class TestHandleRemediationPreview:
    @pytest.mark.asyncio
    async def test_preview_all_brands(self):
        session = MagicMock(profile_id="p1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        slack = AsyncMock()

        fake_plan = [
            {
                "brand_name": "Brand A",
                "client_name": "Client X",
                "proposed_space_id": "sp1",
                "proposed_list_id": "l1",
                "safe_to_apply": True,
                "reason": "single client default mapping",
            }
        ]

        with patch(
            "app.api.routes.slack.build_brand_mapping_remediation_plan",
            return_value=fake_plan,
        ) as mock_build:
            summary = await _handle_cc_skill(
                skill_id="cc_brand_mapping_remediation_preview",
                args={},
                session=session,
                session_service=session_service,
                channel="D1",
                slack=slack,
            )

        assert summary == "[Remediation preview]"
        mock_build.assert_called_once()
        posted = slack.post_message.call_args.kwargs.get("text", "")
        assert "Brand A" in posted

    @pytest.mark.asyncio
    async def test_preview_with_client_hint_not_found(self):
        session = MagicMock(profile_id="p1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        session_service.find_client_matches.return_value = []
        slack = AsyncMock()

        with patch(
            "app.api.routes.slack.build_brand_mapping_remediation_plan",
        ) as mock_build:
            summary = await _handle_cc_skill(
                skill_id="cc_brand_mapping_remediation_preview",
                args={"client_name": "NoSuch"},
                session=session,
                session_service=session_service,
                channel="D1",
                slack=slack,
            )

        assert summary == "[Remediation preview client error]"
        mock_build.assert_not_called()
        msg = slack.post_message.call_args.kwargs.get("text", "")
        assert "couldn't find" in msg.lower()


class TestHandleRemediationApply:
    @pytest.mark.asyncio
    async def test_apply_all_brands(self):
        session = MagicMock(profile_id="p1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        slack = AsyncMock()

        fake_plan = [
            {
                "brand_name": "Brand A",
                "client_name": "Client X",
                "current_space_id": None,
                "current_list_id": None,
                "proposed_space_id": "sp1",
                "proposed_list_id": "l1",
                "safe_to_apply": True,
                "reason": "single client default mapping",
            }
        ]
        fake_result = {"applied": 1, "skipped": 0, "failures": []}

        with (
            patch(
                "app.api.routes.slack.build_brand_mapping_remediation_plan",
                return_value=fake_plan,
            ),
            patch(
                "app.api.routes.slack.apply_brand_mapping_remediation_plan",
                return_value=fake_result,
            ) as mock_apply,
        ):
            summary = await _handle_cc_skill(
                skill_id="cc_brand_mapping_remediation_apply",
                args={},
                session=session,
                session_service=session_service,
                channel="D1",
                slack=slack,
            )

        assert summary == "[Remediation applied]"
        mock_apply.assert_called_once()
        # Verify dry_run=False was passed
        call_kwargs = mock_apply.call_args
        assert call_kwargs.kwargs.get("dry_run") is False or (len(call_kwargs.args) >= 3 and call_kwargs.args[2] is False) or call_kwargs.kwargs.get("dry_run") is False
        posted = slack.post_message.call_args.kwargs.get("text", "")
        assert "Applied: 1" in posted

    @pytest.mark.asyncio
    async def test_apply_with_client_hint_ambiguous(self):
        session = MagicMock(profile_id="p1")
        session_service = MagicMock()
        session_service.db = MagicMock()
        session_service.find_client_matches.return_value = [
            {"id": "c1", "name": "Distex US"},
            {"id": "c2", "name": "Distex CA"},
        ]
        slack = AsyncMock()

        with patch(
            "app.api.routes.slack.apply_brand_mapping_remediation_plan",
        ) as mock_apply:
            summary = await _handle_cc_skill(
                skill_id="cc_brand_mapping_remediation_apply",
                args={"client_name": "Distex"},
                session=session,
                session_service=session_service,
                channel="D1",
                slack=slack,
            )

        assert summary == "[Remediation apply client error]"
        mock_apply.assert_not_called()
        msg = slack.post_message.call_args.kwargs.get("text", "")
        assert "multiple clients" in msg.lower()
