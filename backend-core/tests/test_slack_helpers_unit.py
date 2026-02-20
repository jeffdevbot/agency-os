"""C14X: Unit tests for slack_helpers.py extracted module.

Covers:
- Strict mode gating (_is_llm_orchestrator_enabled, _is_legacy_intent_fallback_enabled,
  _is_llm_strict_mode, _should_block_deterministic_intent)
- Deterministic control-intent allowlist
- Product identifier extraction (_extract_product_identifiers)
- Classifier coverage (_classify_message) for all intent families
- Formatting helpers (_help_text, _format_task_line, _format_weekly_tasks_response)
- Utility helpers (_sanitize_client_name_hint, _current_week_range_ms)
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from app.services.agencyclaw.slack_helpers import (
    _DETERMINISTIC_CONTROL_INTENTS,
    _classify_message,
    _current_week_range_ms,
    _extract_product_identifiers,
    _format_task_line,
    _format_weekly_tasks_response,
    _help_text,
    _is_deterministic_control_intent,
    _is_legacy_intent_fallback_enabled,
    _is_llm_orchestrator_enabled,
    _is_llm_strict_mode,
    _sanitize_client_name_hint,
    _should_block_deterministic_intent,
)


# ---------------------------------------------------------------------------
# Strict mode gating
# ---------------------------------------------------------------------------


class TestLLMOrchestratorEnabled:
    @pytest.mark.parametrize("val", ["1", "true", "yes", "on", "True", " YES "])
    def test_enabled_truthy(self, val: str) -> None:
        with patch.dict(os.environ, {"AGENCYCLAW_LLM_DM_ORCHESTRATOR": val}):
            assert _is_llm_orchestrator_enabled() is True

    @pytest.mark.parametrize("val", ["0", "false", "no", "off", ""])
    def test_disabled_falsy(self, val: str) -> None:
        with patch.dict(os.environ, {"AGENCYCLAW_LLM_DM_ORCHESTRATOR": val}):
            assert _is_llm_orchestrator_enabled() is False

    def test_missing_env_var(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            assert _is_llm_orchestrator_enabled() is False


class TestLegacyIntentFallback:
    def test_enabled_when_orchestrator_off(self) -> None:
        with patch.dict(os.environ, {"AGENCYCLAW_LLM_DM_ORCHESTRATOR": "0"}):
            assert _is_legacy_intent_fallback_enabled() is True

    def test_enabled_via_flag(self) -> None:
        with patch.dict(os.environ, {
            "AGENCYCLAW_LLM_DM_ORCHESTRATOR": "1",
            "AGENCYCLAW_ENABLE_LEGACY_INTENTS": "1",
        }):
            assert _is_legacy_intent_fallback_enabled() is True

    def test_disabled_when_orchestrator_on_and_no_legacy(self) -> None:
        with patch.dict(os.environ, {
            "AGENCYCLAW_LLM_DM_ORCHESTRATOR": "1",
            "AGENCYCLAW_ENABLE_LEGACY_INTENTS": "0",
        }):
            assert _is_legacy_intent_fallback_enabled() is False


class TestStrictMode:
    def test_strict_when_orchestrator_on_and_legacy_off(self) -> None:
        with patch.dict(os.environ, {
            "AGENCYCLAW_LLM_DM_ORCHESTRATOR": "1",
            "AGENCYCLAW_ENABLE_LEGACY_INTENTS": "0",
        }):
            assert _is_llm_strict_mode() is True

    def test_not_strict_when_orchestrator_off(self) -> None:
        with patch.dict(os.environ, {"AGENCYCLAW_LLM_DM_ORCHESTRATOR": "0"}):
            assert _is_llm_strict_mode() is False

    def test_not_strict_when_legacy_on(self) -> None:
        with patch.dict(os.environ, {
            "AGENCYCLAW_LLM_DM_ORCHESTRATOR": "1",
            "AGENCYCLAW_ENABLE_LEGACY_INTENTS": "1",
        }):
            assert _is_llm_strict_mode() is False


# ---------------------------------------------------------------------------
# Deterministic control-intent allowlist
# ---------------------------------------------------------------------------


class TestDeterministicControlIntent:
    @pytest.mark.parametrize("intent", sorted(_DETERMINISTIC_CONTROL_INTENTS))
    def test_allowed_intents(self, intent: str) -> None:
        assert _is_deterministic_control_intent(intent) is True

    @pytest.mark.parametrize("intent", [
        "weekly_tasks", "create_task", "help", "cc_client_lookup",
        "cc_brand_list_all", "cc_assignment_upsert",
    ])
    def test_non_control_intents_rejected(self, intent: str) -> None:
        assert _is_deterministic_control_intent(intent) is False


class TestShouldBlockDeterministicIntent:
    def test_blocks_non_control_in_strict_mode(self) -> None:
        with patch.dict(os.environ, {
            "AGENCYCLAW_LLM_DM_ORCHESTRATOR": "1",
            "AGENCYCLAW_ENABLE_LEGACY_INTENTS": "0",
        }):
            assert _should_block_deterministic_intent("weekly_tasks") is True

    def test_allows_control_in_strict_mode(self) -> None:
        with patch.dict(os.environ, {
            "AGENCYCLAW_LLM_DM_ORCHESTRATOR": "1",
            "AGENCYCLAW_ENABLE_LEGACY_INTENTS": "0",
        }):
            assert _should_block_deterministic_intent("switch_client") is False

    def test_allows_all_when_not_strict(self) -> None:
        with patch.dict(os.environ, {"AGENCYCLAW_LLM_DM_ORCHESTRATOR": "0"}):
            assert _should_block_deterministic_intent("weekly_tasks") is False
            assert _should_block_deterministic_intent("create_task") is False


# ---------------------------------------------------------------------------
# Product identifier extraction
# ---------------------------------------------------------------------------


class TestExtractProductIdentifiers:
    def test_extract_asin(self) -> None:
        result = _extract_product_identifiers("Check ASIN B08N5WRWNW please")
        assert "B08N5WRWNW" in result

    def test_extract_multiple_asins(self) -> None:
        result = _extract_product_identifiers("B08N5WRWNW and B09XYZ1234")
        assert result == ["B08N5WRWNW", "B09XYZ1234"]

    def test_extract_sku_with_dash(self) -> None:
        result = _extract_product_identifiers("SKU TH-200-BLK for coupon")
        assert "TH-200-BLK" in result

    def test_no_duplicates(self) -> None:
        result = _extract_product_identifiers("B08N5WRWNW and B08N5WRWNW again")
        assert result.count("B08N5WRWNW") == 1

    def test_empty_input(self) -> None:
        assert _extract_product_identifiers("") == []
        assert _extract_product_identifiers("hello world") == []

    def test_sku_requires_alpha_and_digit(self) -> None:
        # Pure alpha or pure digit tokens that are 4-24 chars shouldn't match as SKUs
        result = _extract_product_identifiers("ABCDE 12345")
        # "ABCDE" has no digits, "12345" has no alpha — filter both
        sku_only = [t for t in result if len(t) < 10]  # exclude 10-char ASIN matches
        assert not any(t == "ABCDE" for t in sku_only)

    def test_multiple_text_args(self) -> None:
        result = _extract_product_identifiers("B08N5WRWNW", "B09XYZ1234")
        assert "B08N5WRWNW" in result
        assert "B09XYZ1234" in result


# ---------------------------------------------------------------------------
# _sanitize_client_name_hint
# ---------------------------------------------------------------------------


class TestSanitizeClientNameHint:
    def test_strips_trailing_punctuation(self) -> None:
        assert _sanitize_client_name_hint("distex?") == "distex"
        assert _sanitize_client_name_hint("revant!") == "revant"
        assert _sanitize_client_name_hint("acme.") == "acme"

    def test_collapses_whitespace(self) -> None:
        assert _sanitize_client_name_hint("  some   client  ") == "some client"

    def test_empty_input(self) -> None:
        assert _sanitize_client_name_hint("") == ""
        assert _sanitize_client_name_hint("   ") == ""


# ---------------------------------------------------------------------------
# _classify_message
# ---------------------------------------------------------------------------


class TestClassifyMessage:
    # Switch client
    def test_switch_to(self) -> None:
        intent, params = _classify_message("switch to Revant")
        assert intent == "switch_client"
        assert params["client_name"] == "revant"

    def test_work_on(self) -> None:
        intent, params = _classify_message("work on Distex")
        assert intent == "switch_client"
        assert params["client_name"] == "distex"

    # Set/clear defaults
    def test_set_default_client(self) -> None:
        intent, params = _classify_message("set my default client to Revant")
        assert intent == "set_default_client"
        assert params["client_name"] == "revant"

    def test_clear_defaults(self) -> None:
        intent, _ = _classify_message("clear my defaults")
        assert intent == "clear_defaults"

    # Task creation
    def test_create_task_with_client_and_title(self) -> None:
        intent, params = _classify_message("create task for Distex: Set up coupon")
        assert intent == "create_task"
        assert params["client_name"] == "distex"
        assert params["task_title"] == "Set up coupon"

    def test_create_task_no_client(self) -> None:
        intent, params = _classify_message("create task: Do something")
        assert intent == "create_task"
        assert params["client_name"] == ""

    def test_add_task(self) -> None:
        intent, _ = _classify_message("add a task for Acme: Review listing")
        assert intent == "create_task"

    # Weekly tasks
    def test_weekly_tasks(self) -> None:
        intent, params = _classify_message("what's being worked on this week for Distex")
        assert intent == "weekly_tasks"
        assert "distex" in params["client_name"].lower()

    def test_show_tasks(self) -> None:
        intent, _ = _classify_message("show me tasks")
        assert intent == "weekly_tasks"

    def test_list_tasks(self) -> None:
        intent, _ = _classify_message("list tasks")
        assert intent == "weekly_tasks"

    # Confirm draft
    def test_confirm_draft(self) -> None:
        intent, _ = _classify_message("create anyway")
        assert intent == "confirm_draft_task"

    def test_create_as_draft(self) -> None:
        intent, _ = _classify_message("create as draft")
        assert intent == "confirm_draft_task"

    # CC read-only skills
    def test_cc_client_lookup(self) -> None:
        intent, _ = _classify_message("show me clients")
        assert intent == "cc_client_lookup"

    def test_cc_brand_list(self) -> None:
        intent, _ = _classify_message("list brands")
        assert intent == "cc_brand_list_all"

    def test_cc_mapping_audit(self) -> None:
        intent, _ = _classify_message("brands missing clickup mapping")
        assert intent == "cc_brand_clickup_mapping_audit"

    # Remediation
    def test_remediation_preview(self) -> None:
        intent, _ = _classify_message("preview brand mapping remediation")
        assert intent == "cc_brand_mapping_remediation_preview"

    def test_remediation_apply(self) -> None:
        intent, _ = _classify_message("apply brand mapping remediation")
        assert intent == "cc_brand_mapping_remediation_apply"

    def test_remediation_preview_with_client(self) -> None:
        intent, params = _classify_message("preview brand mapping remediation for Distex")
        assert intent == "cc_brand_mapping_remediation_preview"
        assert params["client_name"] == "distex"

    # Assignment skills (C12A)
    def test_assign_person(self) -> None:
        intent, params = _classify_message("assign Sarah as csl")
        assert intent == "cc_assignment_upsert"
        assert params["person_name"] == "Sarah"
        assert params["role_slug"] == "csl"

    def test_remove_person(self) -> None:
        intent, params = _classify_message("remove Sarah from csl")
        assert intent == "cc_assignment_remove"
        assert params["person_name"] == "Sarah"

    def test_assign_with_brand(self) -> None:
        intent, params = _classify_message("assign Sarah as csl on Alpha")
        assert intent == "cc_assignment_upsert"
        assert params["person_name"] == "Sarah"
        assert params["client_name"] == "Alpha"

    # Brand mutations (C12B)
    def test_create_brand(self) -> None:
        intent, params = _classify_message("create brand NewBrand for Acme")
        assert intent == "cc_brand_create"
        assert params["brand_name"] == "NewBrand"
        assert params["client_name"] == "Acme"

    def test_update_brand(self) -> None:
        intent, params = _classify_message("update brand OldBrand")
        assert intent == "cc_brand_update"
        assert params["brand_name"] == "OldBrand"

    # Help fallback
    def test_unknown_returns_help(self) -> None:
        intent, _ = _classify_message("what is the meaning of life")
        assert intent == "help"

    def test_empty_returns_help(self) -> None:
        intent, _ = _classify_message("")
        assert intent == "help"


# ---------------------------------------------------------------------------
# _help_text
# ---------------------------------------------------------------------------


class TestHelpText:
    def test_returns_non_empty_string(self) -> None:
        text = _help_text()
        assert isinstance(text, str)
        assert len(text) > 20

    def test_mentions_key_capabilities(self) -> None:
        text = _help_text()
        assert "task" in text.lower()
        assert "client" in text.lower()


# ---------------------------------------------------------------------------
# _format_task_line
# ---------------------------------------------------------------------------


class TestFormatTaskLine:
    def test_basic_task(self) -> None:
        task = {"name": "Test Task", "url": "https://app.clickup.com/t/abc"}
        line = _format_task_line(task)
        assert "Test Task" in line
        assert "https://app.clickup.com/t/abc" in line
        assert line.startswith("• ")

    def test_task_with_status(self) -> None:
        task = {"name": "Task", "url": "", "status": {"status": "in progress"}}
        line = _format_task_line(task)
        assert "[in progress]" in line

    def test_task_with_assignees(self) -> None:
        task = {
            "name": "Task",
            "url": "",
            "assignees": [{"username": "alice"}, {"username": "bob"}],
        }
        line = _format_task_line(task)
        assert "alice" in line
        assert "bob" in line

    def test_untitled_task(self) -> None:
        task = {}
        line = _format_task_line(task)
        assert "Untitled" in line

    def test_no_url_no_link(self) -> None:
        task = {"name": "Plain", "url": ""}
        line = _format_task_line(task)
        assert "<" not in line
        assert "Plain" in line


# ---------------------------------------------------------------------------
# _format_weekly_tasks_response
# ---------------------------------------------------------------------------


class TestFormatWeeklyTasksResponse:
    def test_no_tasks(self) -> None:
        result = _format_weekly_tasks_response(
            client_name="Acme",
            tasks=[],
            total_fetched=0,
            brand_names=["Brand1"],
        )
        assert "No tasks found" in result
        assert "Acme" in result

    def test_with_tasks(self) -> None:
        tasks = [{"name": "T1", "url": ""}, {"name": "T2", "url": ""}]
        result = _format_weekly_tasks_response(
            client_name="Acme",
            tasks=tasks,
            total_fetched=2,
            brand_names=["B1"],
        )
        assert "Acme" in result
        assert "2 tasks" in result
        assert "T1" in result

    def test_single_task_singular(self) -> None:
        tasks = [{"name": "T1", "url": ""}]
        result = _format_weekly_tasks_response(
            client_name="Acme",
            tasks=tasks,
            total_fetched=1,
            brand_names=[],
        )
        assert "1 task)" in result  # singular, no trailing 's'

    def test_truncation_message(self) -> None:
        tasks = [{"name": f"T{i}", "url": ""} for i in range(200)]
        result = _format_weekly_tasks_response(
            client_name="Acme",
            tasks=tasks,
            total_fetched=250,
            brand_names=[],
        )
        assert "Showing 200" in result
        assert "250" in result


# ---------------------------------------------------------------------------
# _current_week_range_ms
# ---------------------------------------------------------------------------


class TestCurrentWeekRangeMs:
    def test_returns_pair_of_ints(self) -> None:
        start, end = _current_week_range_ms()
        assert isinstance(start, int)
        assert isinstance(end, int)

    def test_end_after_start(self) -> None:
        start, end = _current_week_range_ms()
        assert end > start

    def test_span_is_one_week(self) -> None:
        start, end = _current_week_range_ms()
        week_ms = 7 * 24 * 60 * 60 * 1000
        assert end - start == week_ms
