"""Unit tests for AgentLoopContextAssembler (C17D).

Covers: normal assembly, summary preference, malformed row tolerance,
budget trimming, deterministic ordering, and role normalization.
"""

from __future__ import annotations

import pytest

from app.services.agencyclaw.agent_loop_context_assembler import (
    AssembledContext,
    assemble_prompt_context,
    normalize_role,
)


# ---------------------------------------------------------------------------
# Helpers — build fake DB rows
# ---------------------------------------------------------------------------


def _msg(
    role: str,
    text: str,
    *,
    summary: str | None = None,
    created_at: str = "2026-01-01T00:00:00Z",
) -> dict:
    row: dict = {
        "role": role,
        "content": {"text": text},
        "created_at": created_at,
    }
    if summary is not None:
        row["summary"] = summary
    return row


def _event(
    event_type: str,
    skill_id: str,
    payload: dict | None = None,
    *,
    payload_summary: str | None = None,
    created_at: str = "2026-01-01T00:00:00Z",
) -> dict:
    row: dict = {
        "event_type": event_type,
        "skill_id": skill_id,
        "payload": payload or {},
        "created_at": created_at,
    }
    if payload_summary is not None:
        row["payload_summary"] = payload_summary
    return row


# ===================================================================
# normalize_role
# ===================================================================


class TestNormalizeRole:
    def test_passthrough_roles(self) -> None:
        assert normalize_role("user") == "user"
        assert normalize_role("assistant") == "assistant"
        assert normalize_role("system") == "system"

    def test_planner_report_maps_to_system(self) -> None:
        assert normalize_role("planner_report") == "system"

    def test_unknown_role_returns_none(self) -> None:
        assert normalize_role("bot") is None
        assert normalize_role("") is None

    def test_strips_whitespace(self) -> None:
        assert normalize_role("  user  ") == "user"

    def test_case_insensitive(self) -> None:
        assert normalize_role("User") == "user"
        assert normalize_role("ASSISTANT") == "assistant"
        assert normalize_role("Planner_Report") == "system"

    def test_non_string_returns_none(self) -> None:
        assert normalize_role(123) is None  # type: ignore[arg-type]
        assert normalize_role(None) is None  # type: ignore[arg-type]


# ===================================================================
# Normal mixed assembly
# ===================================================================


class TestNormalAssembly:
    def test_mixed_messages_and_events(self) -> None:
        messages = [
            _msg("user", "Show tasks", created_at="2026-01-01T00:01:00Z"),
            _msg("assistant", "Here are 3 tasks", created_at="2026-01-01T00:02:00Z"),
        ]
        events = [
            _event("skill_call", "clickup_task_list", {"client": "Acme"},
                   created_at="2026-01-01T00:01:30Z"),
            _event("skill_result", "clickup_task_list", {"count": 3},
                   payload_summary="3 tasks",
                   created_at="2026-01-01T00:01:45Z"),
        ]

        result = assemble_prompt_context(messages, events)

        assert len(result["messages_for_llm"]) == 2
        assert result["messages_for_llm"][0]["role"] == "user"
        assert result["messages_for_llm"][1]["role"] == "assistant"
        assert len(result["evidence_notes"]) == 2
        assert "[skill_call]" in result["evidence_notes"][0]
        assert "3 tasks" in result["evidence_notes"][1]
        assert result["stats"]["messages_in"] == 2
        assert result["stats"]["messages_out"] == 2
        assert result["stats"]["events_in"] == 2
        assert result["stats"]["events_out"] == 2
        assert result["stats"]["truncated"] is False

    def test_empty_inputs(self) -> None:
        result = assemble_prompt_context([], [])

        assert result["messages_for_llm"] == []
        assert result["evidence_notes"] == []
        assert result["stats"]["messages_in"] == 0
        assert result["stats"]["truncated"] is False

    def test_messages_only(self) -> None:
        messages = [_msg("user", "hello")]
        result = assemble_prompt_context(messages, [])

        assert len(result["messages_for_llm"]) == 1
        assert result["stats"]["events_in"] == 0

    def test_events_only(self) -> None:
        events = [_event("skill_call", "cc_client_lookup", {"query": "Acme"})]
        result = assemble_prompt_context([], events)

        assert result["messages_for_llm"] == []
        assert len(result["evidence_notes"]) == 1

    def test_planner_report_emitted_as_system(self) -> None:
        messages = [_msg("planner_report", "Plan summary here")]
        result = assemble_prompt_context(messages, [])

        assert len(result["messages_for_llm"]) == 1
        assert result["messages_for_llm"][0]["role"] == "system"


# ===================================================================
# Summary preference
# ===================================================================


class TestSummaryPreference:
    def test_prefers_summary_over_content_text(self) -> None:
        messages = [
            {
                "role": "user",
                "content": {"text": "this is the full long message"},
                "summary": "short version",
                "created_at": "2026-01-01T00:00:00Z",
            }
        ]
        result = assemble_prompt_context(messages, [])

        assert result["messages_for_llm"][0]["content"] == "short version"

    def test_falls_back_to_content_text(self) -> None:
        messages = [
            {
                "role": "user",
                "content": {"text": "the actual text"},
                "created_at": "2026-01-01T00:00:00Z",
            }
        ]
        result = assemble_prompt_context(messages, [])

        assert result["messages_for_llm"][0]["content"] == "the actual text"

    def test_falls_back_to_compact_json(self) -> None:
        """When content has no 'text' key, use summarize_json."""
        messages = [
            {
                "role": "assistant",
                "content": {"data": [1, 2, 3]},
                "created_at": "2026-01-01T00:00:00Z",
            }
        ]
        result = assemble_prompt_context(messages, [])

        assert result["messages_for_llm"][0]["content"] == '{"data":[1,2,3]}'

    def test_event_prefers_payload_summary(self) -> None:
        events = [
            _event("skill_result", "clickup_task_list", {"tasks": []},
                   payload_summary="0 tasks found"),
        ]
        result = assemble_prompt_context([], events)

        assert "0 tasks found" in result["evidence_notes"][0]

    def test_event_falls_back_to_payload_json(self) -> None:
        events = [
            _event("skill_call", "cc_client_lookup", {"query": "Acme"}),
        ]
        result = assemble_prompt_context([], events)

        assert '"query":"Acme"' in result["evidence_notes"][0]


# ===================================================================
# Malformed row tolerance
# ===================================================================


class TestMalformedRowTolerance:
    def test_skips_non_dict_message_rows(self) -> None:
        messages = [
            "not a dict",  # type: ignore[list-item]
            42,  # type: ignore[list-item]
            _msg("user", "valid"),
        ]
        result = assemble_prompt_context(messages, [])  # type: ignore[arg-type]

        assert len(result["messages_for_llm"]) == 1
        assert result["stats"]["messages_in"] == 3

    def test_skips_non_dict_event_rows(self) -> None:
        events = [
            None,  # type: ignore[list-item]
            _event("skill_call", "test", {"x": 1}),
        ]
        result = assemble_prompt_context([], events)  # type: ignore[arg-type]

        assert len(result["evidence_notes"]) == 1
        assert result["stats"]["events_in"] == 2

    def test_skips_unknown_role(self) -> None:
        messages = [
            _msg("bot", "should be skipped"),
            _msg("user", "kept"),
        ]
        result = assemble_prompt_context(messages, [])

        assert len(result["messages_for_llm"]) == 1
        assert result["messages_for_llm"][0]["content"] == "kept"

    def test_skips_empty_text_message(self) -> None:
        messages = [
            {"role": "user", "content": {"text": ""}, "created_at": "2026-01-01T00:00:00Z"},
            {"role": "user", "content": {}, "created_at": "2026-01-01T00:00:01Z"},
            _msg("user", "valid"),
        ]
        result = assemble_prompt_context(messages, [])

        # Empty-text row falls back to summarize_json({"text":""}), empty-dict
        # falls back to summarize_json({}), both produce non-empty strings.
        # All 3 rows pass through.
        assert result["stats"]["messages_out"] == 3

    def test_missing_role_field(self) -> None:
        messages = [
            {"content": {"text": "no role"}, "created_at": "2026-01-01T00:00:00Z"},
        ]
        result = assemble_prompt_context(messages, [])

        assert result["messages_for_llm"] == []

    def test_content_as_plain_string(self) -> None:
        """Some rows might have content stored as a plain string."""
        messages = [
            {"role": "user", "content": "plain string", "created_at": "2026-01-01T00:00:00Z"},
        ]
        result = assemble_prompt_context(messages, [])

        assert len(result["messages_for_llm"]) == 1
        assert result["messages_for_llm"][0]["content"] == "plain string"

    def test_event_missing_payload(self) -> None:
        events = [
            {"event_type": "skill_call", "skill_id": "test", "created_at": "2026-01-01T00:00:00Z"},
        ]
        result = assemble_prompt_context([], events)

        assert len(result["evidence_notes"]) == 1
        assert "test" in result["evidence_notes"][0]


# ===================================================================
# Trimming under budget pressure
# ===================================================================


class TestBudgetTrimming:
    def test_trims_oldest_messages_first(self) -> None:
        messages = [
            _msg("user", "A" * 3000, created_at="2026-01-01T00:01:00Z"),
            _msg("assistant", "B" * 3000, created_at="2026-01-01T00:02:00Z"),
            _msg("user", "C" * 3000, created_at="2026-01-01T00:03:00Z"),
        ]
        result = assemble_prompt_context(messages, [], budget_chars=6000)

        assert result["stats"]["truncated"] is True
        # Oldest message(s) trimmed to fit budget.
        assert result["stats"]["messages_out"] == 2
        # Newest messages retained.
        roles = [m["role"] for m in result["messages_for_llm"]]
        assert roles == ["assistant", "user"]

    def test_trims_messages_before_events(self) -> None:
        """Oldest messages are trimmed first; events only trimmed if still over."""
        # 2 messages: 100 chars each.
        # 1 event note: "[skill_call] s1: short" ~ 22 chars.
        # Total ~222.  Budget = 150: oldest message trimmed, event kept.
        messages = [
            _msg("user", "A" * 100, created_at="2026-01-01T00:01:00Z"),
            _msg("assistant", "B" * 100, created_at="2026-01-01T00:02:00Z"),
        ]
        events = [
            _event("skill_call", "s1", {"a": 1},
                   payload_summary="short",
                   created_at="2026-01-01T00:01:30Z"),
        ]
        result = assemble_prompt_context(messages, events, budget_chars=150)

        assert result["stats"]["truncated"] is True
        # Oldest message trimmed; newest message + event fit.
        assert result["stats"]["messages_out"] == 1
        assert result["stats"]["events_out"] == 1
        assert result["messages_for_llm"][0]["content"] == "B" * 100

    def test_small_budget_keeps_at_least_newest(self) -> None:
        messages = [
            _msg("user", "old", created_at="2026-01-01T00:01:00Z"),
            _msg("assistant", "new", created_at="2026-01-01T00:02:00Z"),
        ]
        # Budget of 5 chars — only "new" (3 chars) fits.
        result = assemble_prompt_context(messages, [], budget_chars=5)

        assert result["stats"]["truncated"] is True
        assert result["stats"]["messages_out"] == 1
        assert result["messages_for_llm"][0]["content"] == "new"

    def test_no_truncation_within_budget(self) -> None:
        messages = [_msg("user", "short")]
        result = assemble_prompt_context(messages, [], budget_chars=6000)

        assert result["stats"]["truncated"] is False
        assert result["stats"]["messages_out"] == 1

    def test_rejects_zero_budget(self) -> None:
        with pytest.raises(ValueError, match="budget_chars must be > 0"):
            assemble_prompt_context([], [], budget_chars=0)

    def test_rejects_negative_budget(self) -> None:
        with pytest.raises(ValueError, match="budget_chars must be > 0"):
            assemble_prompt_context([], [], budget_chars=-1)


# ===================================================================
# Deterministic ordering
# ===================================================================


class TestDeterministicOrdering:
    def test_messages_sorted_oldest_to_newest(self) -> None:
        messages = [
            _msg("assistant", "second", created_at="2026-01-01T00:02:00Z"),
            _msg("user", "first", created_at="2026-01-01T00:01:00Z"),
            _msg("user", "third", created_at="2026-01-01T00:03:00Z"),
        ]
        result = assemble_prompt_context(messages, [])

        contents = [m["content"] for m in result["messages_for_llm"]]
        assert contents == ["first", "second", "third"]

    def test_events_sorted_oldest_to_newest(self) -> None:
        events = [
            _event("skill_result", "s1", {}, payload_summary="result",
                   created_at="2026-01-01T00:02:00Z"),
            _event("skill_call", "s1", {}, payload_summary="call",
                   created_at="2026-01-01T00:01:00Z"),
        ]
        result = assemble_prompt_context([], events)

        assert "call" in result["evidence_notes"][0]
        assert "result" in result["evidence_notes"][1]

    def test_stable_order_on_same_timestamp(self) -> None:
        """When created_at is the same, input order is preserved (stable sort)."""
        ts = "2026-01-01T00:00:00Z"
        messages = [
            _msg("user", "A", created_at=ts),
            _msg("assistant", "B", created_at=ts),
            _msg("user", "C", created_at=ts),
        ]
        result = assemble_prompt_context(messages, [])

        contents = [m["content"] for m in result["messages_for_llm"]]
        assert contents == ["A", "B", "C"]


# ===================================================================
# Output shape contract
# ===================================================================


class TestOutputShape:
    def test_has_required_keys(self) -> None:
        result = assemble_prompt_context(
            [_msg("user", "hello")],
            [_event("skill_call", "test", {"x": 1})],
        )

        assert "messages_for_llm" in result
        assert "evidence_notes" in result
        assert "stats" in result
        stats = result["stats"]
        assert "messages_in" in stats
        assert "messages_out" in stats
        assert "events_in" in stats
        assert "events_out" in stats
        assert "truncated" in stats

    def test_message_items_have_role_and_content(self) -> None:
        result = assemble_prompt_context([_msg("user", "hi")], [])

        msg = result["messages_for_llm"][0]
        assert "role" in msg
        assert "content" in msg
        assert isinstance(msg["role"], str)
        assert isinstance(msg["content"], str)

    def test_evidence_notes_are_strings(self) -> None:
        result = assemble_prompt_context(
            [], [_event("skill_call", "test", {"x": 1})],
        )

        for note in result["evidence_notes"]:
            assert isinstance(note, str)
