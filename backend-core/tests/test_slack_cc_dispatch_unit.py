"""C14X: Unit tests for slack_cc_dispatch.py extracted module.

Covers:
- resolve_cc_client_hint: no hint, single match, multiple matches, zero matches
- format_remediation_preview: empty plan, safe items, blocked items, mixed
- format_remediation_apply_result: zero applied, applied with failures
- handle_cc_skill: all skill branches via injected mock callables
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.agencyclaw.slack_cc_dispatch import (
    format_remediation_apply_result,
    format_remediation_preview,
    handle_cc_skill,
    resolve_cc_client_hint,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(profile_id: str = "prof1", active_client_id: str | None = None) -> MagicMock:
    s = MagicMock()
    s.id = "sess1"
    s.profile_id = profile_id
    s.active_client_id = active_client_id
    return s


def _make_session_service(
    find_matches: list[dict] | None = None,
    client_name: str = "Acme",
) -> MagicMock:
    ss = MagicMock()
    ss.find_client_matches = MagicMock(return_value=find_matches or [])
    ss.get_client_name = MagicMock(return_value=client_name)
    ss.db = MagicMock()
    return ss


def _make_slack() -> AsyncMock:
    return AsyncMock()


def _picker_blocks(matches: list[dict]) -> list[dict]:
    return [{"type": "actions", "matches": matches}]


# ---------------------------------------------------------------------------
# resolve_cc_client_hint
# ---------------------------------------------------------------------------


class TestResolveCcClientHint:
    @pytest.mark.asyncio
    async def test_no_hint_returns_none(self) -> None:
        result = await resolve_cc_client_hint(
            args={},
            session_service=_make_session_service(),
            session=_make_session(),
            channel="C01",
            slack=_make_slack(),
            build_client_picker_blocks=_picker_blocks,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_hint_returns_none(self) -> None:
        result = await resolve_cc_client_hint(
            args={"client_name": "   "},
            session_service=_make_session_service(),
            session=_make_session(),
            channel="C01",
            slack=_make_slack(),
            build_client_picker_blocks=_picker_blocks,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_single_match_returns_id(self) -> None:
        ss = _make_session_service(find_matches=[{"id": "c1", "name": "Acme"}])
        result = await resolve_cc_client_hint(
            args={"client_name": "acme"},
            session_service=ss,
            session=_make_session(),
            channel="C01",
            slack=_make_slack(),
            build_client_picker_blocks=_picker_blocks,
        )
        assert result == "c1"

    @pytest.mark.asyncio
    async def test_multiple_matches_returns_false(self) -> None:
        ss = _make_session_service(
            find_matches=[{"id": "c1", "name": "Acme"}, {"id": "c2", "name": "Acme Corp"}],
        )
        slack = _make_slack()
        result = await resolve_cc_client_hint(
            args={"client_name": "acme"},
            session_service=ss,
            session=_make_session(),
            channel="C01",
            slack=slack,
            build_client_picker_blocks=_picker_blocks,
        )
        assert result is False
        slack.post_message.assert_called_once()
        assert "Multiple" in slack.post_message.call_args[1]["text"]

    @pytest.mark.asyncio
    async def test_zero_matches_returns_false(self) -> None:
        ss = _make_session_service(find_matches=[])
        slack = _make_slack()
        result = await resolve_cc_client_hint(
            args={"client_name": "nonexistent"},
            session_service=ss,
            session=_make_session(),
            channel="C01",
            slack=slack,
            build_client_picker_blocks=_picker_blocks,
        )
        assert result is False
        slack.post_message.assert_called_once()
        assert "couldn't find" in slack.post_message.call_args[1]["text"]


# ---------------------------------------------------------------------------
# format_remediation_preview
# ---------------------------------------------------------------------------


class TestFormatRemediationPreview:
    def test_empty_plan(self) -> None:
        result = format_remediation_preview([])
        assert "Nothing to remediate" in result

    def test_safe_items(self) -> None:
        plan = [
            {"safe_to_apply": True, "brand_name": "Alpha", "client_name": "Acme",
             "proposed_space_id": "s1", "proposed_list_id": "l1"},
        ]
        result = format_remediation_preview(plan)
        assert "Safe to apply" in result
        assert "Alpha" in result
        assert "Acme" in result

    def test_blocked_items(self) -> None:
        plan = [
            {"safe_to_apply": False, "brand_name": "Beta", "client_name": "Corp",
             "reason": "Missing space"},
        ]
        result = format_remediation_preview(plan)
        assert "Blocked" in result
        assert "Beta" in result
        assert "Missing space" in result

    def test_mixed_plan(self) -> None:
        plan = [
            {"safe_to_apply": True, "brand_name": "A", "client_name": "X",
             "proposed_space_id": "s", "proposed_list_id": "l"},
            {"safe_to_apply": False, "brand_name": "B", "client_name": "Y",
             "reason": "No space"},
        ]
        result = format_remediation_preview(plan)
        assert "Safe to apply: 1" in result
        assert "Blocked: 1" in result

    def test_truncation_safe(self) -> None:
        plan = [
            {"safe_to_apply": True, "brand_name": f"B{i}", "client_name": "X",
             "proposed_space_id": "s", "proposed_list_id": "l"}
            for i in range(25)
        ]
        result = format_remediation_preview(plan)
        assert "and 5 more" in result


# ---------------------------------------------------------------------------
# format_remediation_apply_result
# ---------------------------------------------------------------------------


class TestFormatRemediationApplyResult:
    def test_all_applied(self) -> None:
        result = format_remediation_apply_result({"applied": 5, "skipped": 0, "failures": []})
        assert "Applied: 5" in result

    def test_with_failures(self) -> None:
        result = format_remediation_apply_result({
            "applied": 3,
            "skipped": 1,
            "failures": [{"brand_id": "b1", "error": "timeout"}],
        })
        assert "Failures: 1" in result
        assert "timeout" in result

    def test_zero_applied_no_verify_msg(self) -> None:
        result = format_remediation_apply_result({"applied": 0, "skipped": 0, "failures": []})
        assert "preview" not in result.lower() or "Applied: 0" in result


# ---------------------------------------------------------------------------
# handle_cc_skill — all skill branches
# ---------------------------------------------------------------------------


class TestHandleCcSkillClientLookup:
    @pytest.mark.asyncio
    async def test_cc_client_lookup(self) -> None:
        slack = _make_slack()
        ss = _make_session_service()
        lookup_fn = MagicMock(return_value=[{"id": "c1", "name": "Acme"}])
        format_fn = MagicMock(return_value="Clients: Acme")

        result = await handle_cc_skill(
            skill_id="cc_client_lookup",
            args={"query": ""},
            session=_make_session(),
            session_service=ss,
            channel="C01",
            slack=slack,
            build_client_picker_blocks=_picker_blocks,
            resolve_cc_client_hint_fn=AsyncMock(return_value=None),
            resolve_assignment_client_fn=AsyncMock(return_value="c1"),
            lookup_clients_fn=lookup_fn,
            format_client_list_fn=format_fn,
        )

        assert "Listed clients" in result
        slack.post_message.assert_called_once()
        lookup_fn.assert_called_once()


class TestHandleCcSkillBrandList:
    @pytest.mark.asyncio
    async def test_brand_list_no_client(self) -> None:
        slack = _make_slack()
        ss = _make_session_service()
        list_fn = MagicMock(return_value=[])
        format_fn = MagicMock(return_value="No brands")

        result = await handle_cc_skill(
            skill_id="cc_brand_list_all",
            args={},
            session=_make_session(),
            session_service=ss,
            channel="C01",
            slack=slack,
            build_client_picker_blocks=_picker_blocks,
            resolve_cc_client_hint_fn=AsyncMock(return_value=None),
            resolve_assignment_client_fn=AsyncMock(return_value="c1"),
            list_brands_fn=list_fn,
            format_brand_list_fn=format_fn,
        )

        assert "Listed brands" in result
        list_fn.assert_called_once()


class TestHandleCcSkillMappingAudit:
    @pytest.mark.asyncio
    async def test_mapping_audit(self) -> None:
        slack = _make_slack()
        ss = _make_session_service()
        audit_fn = MagicMock(return_value=[])
        format_fn = MagicMock(return_value="All mapped")

        result = await handle_cc_skill(
            skill_id="cc_brand_clickup_mapping_audit",
            args={},
            session=_make_session(),
            session_service=ss,
            channel="C01",
            slack=slack,
            build_client_picker_blocks=_picker_blocks,
            resolve_cc_client_hint_fn=AsyncMock(return_value=None),
            resolve_assignment_client_fn=AsyncMock(return_value="c1"),
            audit_brand_mappings_fn=audit_fn,
            format_mapping_audit_fn=format_fn,
        )

        assert "mapping audit" in result
        audit_fn.assert_called_once()


class TestHandleCcSkillRemediationPreview:
    @pytest.mark.asyncio
    async def test_remediation_preview(self) -> None:
        slack = _make_slack()
        ss = _make_session_service()
        build_fn = MagicMock(return_value=[])

        result = await handle_cc_skill(
            skill_id="cc_brand_mapping_remediation_preview",
            args={},
            session=_make_session(),
            session_service=ss,
            channel="C01",
            slack=slack,
            build_client_picker_blocks=_picker_blocks,
            resolve_cc_client_hint_fn=AsyncMock(return_value=None),
            resolve_assignment_client_fn=AsyncMock(return_value="c1"),
            build_brand_mapping_remediation_plan_fn=build_fn,
            format_remediation_preview_fn=MagicMock(return_value="Preview text"),
        )

        assert "Remediation preview" in result

    @pytest.mark.asyncio
    async def test_remediation_preview_client_error(self) -> None:
        slack = _make_slack()
        ss = _make_session_service()

        result = await handle_cc_skill(
            skill_id="cc_brand_mapping_remediation_preview",
            args={"client_name": "bad"},
            session=_make_session(),
            session_service=ss,
            channel="C01",
            slack=slack,
            build_client_picker_blocks=_picker_blocks,
            resolve_cc_client_hint_fn=AsyncMock(return_value=False),
            resolve_assignment_client_fn=AsyncMock(return_value="c1"),
        )

        assert "client error" in result


class TestHandleCcSkillRemediationApply:
    @pytest.mark.asyncio
    async def test_remediation_apply(self) -> None:
        slack = _make_slack()
        ss = _make_session_service()
        build_fn = MagicMock(return_value=[{"safe_to_apply": True}])
        apply_fn = MagicMock(return_value={"applied": 1, "skipped": 0, "failures": []})

        result = await handle_cc_skill(
            skill_id="cc_brand_mapping_remediation_apply",
            args={},
            session=_make_session(),
            session_service=ss,
            channel="C01",
            slack=slack,
            build_client_picker_blocks=_picker_blocks,
            resolve_cc_client_hint_fn=AsyncMock(return_value=None),
            resolve_assignment_client_fn=AsyncMock(return_value="c1"),
            build_brand_mapping_remediation_plan_fn=build_fn,
            apply_brand_mapping_remediation_plan_fn=apply_fn,
            format_remediation_apply_result_fn=MagicMock(return_value="Applied"),
        )

        assert "Remediation applied" in result


class TestHandleCcSkillAssignmentUpsert:
    @pytest.mark.asyncio
    async def test_happy_path(self) -> None:
        slack = _make_slack()
        ss = _make_session_service()

        result = await handle_cc_skill(
            skill_id="cc_assignment_upsert",
            args={"person_name": "Sarah", "role_slug": "csl", "brand_name": ""},
            session=_make_session(),
            session_service=ss,
            channel="C01",
            slack=slack,
            build_client_picker_blocks=_picker_blocks,
            resolve_cc_client_hint_fn=AsyncMock(return_value=None),
            resolve_assignment_client_fn=AsyncMock(return_value="c1"),
            resolve_person_fn=MagicMock(return_value={
                "status": "ok", "profile_id": "p1", "display_name": "Sarah",
            }),
            resolve_role_fn=MagicMock(return_value={
                "status": "ok", "role_id": "r1", "role_name": "CSL",
            }),
            upsert_assignment_fn=MagicMock(return_value={
                "status": "ok", "message": "Assigned",
            }),
            format_upsert_result_fn=MagicMock(return_value="Assigned Sarah as CSL"),
        )

        assert "Assignment upsert" in result
        slack.post_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_person_not_found(self) -> None:
        slack = _make_slack()
        ss = _make_session_service()

        result = await handle_cc_skill(
            skill_id="cc_assignment_upsert",
            args={"person_name": "Nobody", "role_slug": "csl"},
            session=_make_session(),
            session_service=ss,
            channel="C01",
            slack=slack,
            build_client_picker_blocks=_picker_blocks,
            resolve_cc_client_hint_fn=AsyncMock(return_value=None),
            resolve_assignment_client_fn=AsyncMock(return_value="c1"),
            resolve_person_fn=MagicMock(return_value={
                "status": "not_found", "profile_id": None, "display_name": None, "candidates": [],
            }),
        )

        assert "person not found" in result

    @pytest.mark.asyncio
    async def test_client_error(self) -> None:
        slack = _make_slack()
        ss = _make_session_service()

        result = await handle_cc_skill(
            skill_id="cc_assignment_upsert",
            args={"person_name": "Sarah", "role_slug": "csl"},
            session=_make_session(),
            session_service=ss,
            channel="C01",
            slack=slack,
            build_client_picker_blocks=_picker_blocks,
            resolve_cc_client_hint_fn=AsyncMock(return_value=None),
            resolve_assignment_client_fn=AsyncMock(return_value=False),
        )

        assert "client error" in result


class TestHandleCcSkillAssignmentRemove:
    @pytest.mark.asyncio
    async def test_happy_path(self) -> None:
        slack = _make_slack()
        ss = _make_session_service()

        result = await handle_cc_skill(
            skill_id="cc_assignment_remove",
            args={"person_name": "Sarah", "role_slug": "csl", "brand_name": ""},
            session=_make_session(),
            session_service=ss,
            channel="C01",
            slack=slack,
            build_client_picker_blocks=_picker_blocks,
            resolve_cc_client_hint_fn=AsyncMock(return_value=None),
            resolve_assignment_client_fn=AsyncMock(return_value="c1"),
            resolve_person_fn=MagicMock(return_value={
                "status": "ok", "profile_id": "p1", "display_name": "Sarah",
            }),
            resolve_role_fn=MagicMock(return_value={
                "status": "ok", "role_id": "r1", "role_name": "CSL",
            }),
            remove_assignment_fn=MagicMock(return_value={
                "status": "ok", "message": "Removed",
            }),
            format_remove_result_fn=MagicMock(return_value="Removed Sarah from CSL"),
        )

        assert "Assignment remove" in result
        slack.post_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_role_not_found(self) -> None:
        slack = _make_slack()
        ss = _make_session_service()

        result = await handle_cc_skill(
            skill_id="cc_assignment_remove",
            args={"person_name": "Sarah", "role_slug": "nonexistent"},
            session=_make_session(),
            session_service=ss,
            channel="C01",
            slack=slack,
            build_client_picker_blocks=_picker_blocks,
            resolve_cc_client_hint_fn=AsyncMock(return_value=None),
            resolve_assignment_client_fn=AsyncMock(return_value="c1"),
            resolve_person_fn=MagicMock(return_value={
                "status": "ok", "profile_id": "p1", "display_name": "Sarah",
            }),
            resolve_role_fn=MagicMock(return_value={
                "status": "not_found", "role_id": None, "role_name": None,
            }),
        )

        assert "role not found" in result


class TestHandleCcSkillBrandCreate:
    @pytest.mark.asyncio
    async def test_happy_path(self) -> None:
        slack = _make_slack()
        ss = _make_session_service()

        result = await handle_cc_skill(
            skill_id="cc_brand_create",
            args={"brand_name": "NewBrand", "client_name": "Acme"},
            session=_make_session(),
            session_service=ss,
            channel="C01",
            slack=slack,
            build_client_picker_blocks=_picker_blocks,
            resolve_cc_client_hint_fn=AsyncMock(return_value=None),
            resolve_assignment_client_fn=AsyncMock(return_value="c1"),
            create_brand_fn=MagicMock(return_value={
                "status": "ok", "brand_id": "b1", "message": "Created",
            }),
            format_brand_create_result_fn=MagicMock(return_value="Created brand NewBrand"),
        )

        assert "Brand create" in result
        slack.post_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_name(self) -> None:
        slack = _make_slack()
        ss = _make_session_service()

        result = await handle_cc_skill(
            skill_id="cc_brand_create",
            args={"brand_name": "", "client_name": "Acme"},
            session=_make_session(),
            session_service=ss,
            channel="C01",
            slack=slack,
            build_client_picker_blocks=_picker_blocks,
            resolve_cc_client_hint_fn=AsyncMock(return_value=None),
            resolve_assignment_client_fn=AsyncMock(return_value="c1"),
        )

        assert "missing name" in result


class TestHandleCcSkillBrandUpdate:
    @pytest.mark.asyncio
    async def test_happy_path(self) -> None:
        slack = _make_slack()
        ss = _make_session_service()

        result = await handle_cc_skill(
            skill_id="cc_brand_update",
            args={"brand_name": "Alpha", "client_name": "Acme"},
            session=_make_session(),
            session_service=ss,
            channel="C01",
            slack=slack,
            build_client_picker_blocks=_picker_blocks,
            resolve_cc_client_hint_fn=AsyncMock(return_value=None),
            resolve_assignment_client_fn=AsyncMock(return_value="c1"),
            resolve_brand_for_mutation_fn=MagicMock(return_value={
                "status": "ok", "brand_id": "b1", "brand_name": "Alpha", "candidates": [],
            }),
            update_brand_fn=MagicMock(return_value={
                "status": "ok", "message": "Updated name", "fields_updated": ["name"],
            }),
            format_brand_update_result_fn=MagicMock(return_value="Updated Alpha"),
        )

        assert "Brand update" in result
        slack.post_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_brand_not_found(self) -> None:
        slack = _make_slack()
        ss = _make_session_service()

        result = await handle_cc_skill(
            skill_id="cc_brand_update",
            args={"brand_name": "Nonexistent"},
            session=_make_session(),
            session_service=ss,
            channel="C01",
            slack=slack,
            build_client_picker_blocks=_picker_blocks,
            resolve_cc_client_hint_fn=AsyncMock(return_value=None),
            resolve_assignment_client_fn=AsyncMock(return_value="c1"),
            resolve_brand_for_mutation_fn=MagicMock(return_value={
                "status": "not_found", "brand_id": None, "brand_name": None, "candidates": [],
            }),
        )

        assert "brand not found" in result

    @pytest.mark.asyncio
    async def test_brand_ambiguous(self) -> None:
        slack = _make_slack()
        ss = _make_session_service()

        result = await handle_cc_skill(
            skill_id="cc_brand_update",
            args={"brand_name": "Alpha"},
            session=_make_session(),
            session_service=ss,
            channel="C01",
            slack=slack,
            build_client_picker_blocks=_picker_blocks,
            resolve_cc_client_hint_fn=AsyncMock(return_value=None),
            resolve_assignment_client_fn=AsyncMock(return_value="c1"),
            resolve_brand_for_mutation_fn=MagicMock(return_value={
                "status": "ambiguous", "brand_id": None, "brand_name": None,
                "candidates": [{"name": "Alpha One"}, {"name": "Alpha Two"}],
            }),
            format_brand_ambiguous_fn=MagicMock(return_value="Multiple brands match"),
        )

        assert "brand ambiguous" in result

    @pytest.mark.asyncio
    async def test_missing_name(self) -> None:
        slack = _make_slack()
        ss = _make_session_service()

        result = await handle_cc_skill(
            skill_id="cc_brand_update",
            args={"brand_name": ""},
            session=_make_session(),
            session_service=ss,
            channel="C01",
            slack=slack,
            build_client_picker_blocks=_picker_blocks,
            resolve_cc_client_hint_fn=AsyncMock(return_value=None),
            resolve_assignment_client_fn=AsyncMock(return_value="c1"),
        )

        assert "missing name" in result


class TestHandleCcSkillUnknown:
    @pytest.mark.asyncio
    async def test_unknown_skill_returns_empty(self) -> None:
        result = await handle_cc_skill(
            skill_id="cc_unknown_skill",
            args={},
            session=_make_session(),
            session_service=_make_session_service(),
            channel="C01",
            slack=_make_slack(),
            build_client_picker_blocks=_picker_blocks,
            resolve_cc_client_hint_fn=AsyncMock(return_value=None),
            resolve_assignment_client_fn=AsyncMock(return_value="c1"),
        )

        assert result == ""
