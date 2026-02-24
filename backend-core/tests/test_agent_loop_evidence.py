"""Unit tests for agent_loop_evidence (C17G).

Validates payload summarization, evidence-note formatting, and
rehydration key generation/parsing.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.services.agencyclaw.agent_loop_evidence import (
    build_evidence_note,
    build_payload_summary,
    parse_rehydration_key,
    rehydration_key,
)
from app.services.agencyclaw.agent_loop_store import AgentLoopStore


# ===================================================================
# build_payload_summary
# ===================================================================


class TestBuildPayloadSummary:
    def test_basic_payload(self) -> None:
        result = build_payload_summary("clickup_task_list", {"client_name": "Acme"})
        assert result == '{"client_name":"Acme"}'

    def test_sorted_keys(self) -> None:
        result = build_payload_summary("test", {"z": 1, "a": 2})
        assert result == '{"a":2,"z":1}'

    def test_truncation(self) -> None:
        result = build_payload_summary("test", {"data": "x" * 500}, max_chars=50)
        assert len(result) == 50
        assert result.endswith("...")

    def test_exact_boundary_no_truncation(self) -> None:
        payload = {"a": 1}
        rendered = '{"a":1}'
        result = build_payload_summary("test", payload, max_chars=len(rendered))
        assert result == rendered
        assert not result.endswith("...")

    def test_empty_payload(self) -> None:
        result = build_payload_summary("test", {})
        assert result == "{}"

    def test_non_dict_payload_raises(self) -> None:
        with pytest.raises(ValueError, match="payload must be a dict"):
            build_payload_summary("test", "not a dict")  # type: ignore[arg-type]

    def test_empty_skill_id_raises(self) -> None:
        with pytest.raises(ValueError, match="skill_id is required"):
            build_payload_summary("", {"x": 1})

    def test_whitespace_only_skill_id_raises(self) -> None:
        with pytest.raises(ValueError, match="skill_id is required"):
            build_payload_summary("   ", {"x": 1})

    def test_zero_max_chars_raises(self) -> None:
        with pytest.raises(ValueError, match="max_chars must be > 0"):
            build_payload_summary("test", {"x": 1}, max_chars=0)

    def test_negative_max_chars_raises(self) -> None:
        with pytest.raises(ValueError, match="max_chars must be > 0"):
            build_payload_summary("test", {"x": 1}, max_chars=-1)

    def test_max_chars_3_or_less(self) -> None:
        result = build_payload_summary("test", {"a": 1}, max_chars=3)
        assert len(result) == 3
        assert result == '{"a'

    def test_default_max_chars_280(self) -> None:
        big_payload = {"data": "x" * 500}
        result = build_payload_summary("test", big_payload)
        assert len(result) <= 280

    def test_deterministic(self) -> None:
        payload = {"b": 2, "a": 1, "c": 3}
        r1 = build_payload_summary("test", payload)
        r2 = build_payload_summary("test", payload)
        assert r1 == r2


# ===================================================================
# build_evidence_note
# ===================================================================


class TestBuildEvidenceNote:
    def test_basic_format(self) -> None:
        result = build_evidence_note("skill_call", "clickup_task_list", '{"client":"Acme"}')
        assert result == '[skill_call] clickup_task_list: {"client":"Acme"}'

    def test_skill_result(self) -> None:
        result = build_evidence_note("skill_result", "clickup_task_list", '{"count":3}')
        assert result == '[skill_result] clickup_task_list: {"count":3}'

    def test_strips_whitespace(self) -> None:
        result = build_evidence_note("  skill_call  ", "  my_skill  ", "  summary  ")
        assert result == "[skill_call] my_skill: summary"

    def test_empty_event_type_raises(self) -> None:
        with pytest.raises(ValueError, match="event_type is required"):
            build_evidence_note("", "test", "summary")

    def test_empty_skill_id_raises(self) -> None:
        with pytest.raises(ValueError, match="skill_id is required"):
            build_evidence_note("skill_call", "", "summary")

    def test_non_string_payload_summary_raises(self) -> None:
        with pytest.raises(ValueError, match="payload_summary must be a string"):
            build_evidence_note("skill_call", "test", 123)  # type: ignore[arg-type]

    def test_empty_payload_summary_allowed(self) -> None:
        result = build_evidence_note("skill_call", "test", "")
        assert result == "[skill_call] test: "

    def test_whitespace_only_event_type_raises(self) -> None:
        with pytest.raises(ValueError, match="event_type is required"):
            build_evidence_note("   ", "test", "summary")


# ===================================================================
# rehydration_key
# ===================================================================


class TestRehydrationKey:
    def test_run_only(self) -> None:
        key = rehydration_key("run-abc-123")
        assert key == "ev:run-abc-123"

    def test_run_and_event(self) -> None:
        key = rehydration_key("run-1", event_id="evt-2")
        assert key == "ev:run-1/evt-2"

    def test_strips_whitespace(self) -> None:
        key = rehydration_key("  run-1  ", event_id="  evt-2  ")
        assert key == "ev:run-1/evt-2"

    def test_empty_run_id_raises(self) -> None:
        with pytest.raises(ValueError, match="run_id is required"):
            rehydration_key("")

    def test_whitespace_only_run_id_raises(self) -> None:
        with pytest.raises(ValueError, match="run_id is required"):
            rehydration_key("   ")

    def test_empty_event_id_raises(self) -> None:
        with pytest.raises(ValueError, match="event_id must be non-empty"):
            rehydration_key("run-1", event_id="")

    def test_whitespace_only_event_id_raises(self) -> None:
        with pytest.raises(ValueError, match="event_id must be non-empty"):
            rehydration_key("run-1", event_id="   ")

    def test_none_event_id_omitted(self) -> None:
        key = rehydration_key("run-1", event_id=None)
        assert key == "ev:run-1"
        assert "/" not in key

    def test_uuid_style_ids(self) -> None:
        key = rehydration_key("a1b2c3d4-e5f6-7890-abcd-ef1234567890", event_id="aaaa-bbbb")
        assert key == "ev:a1b2c3d4-e5f6-7890-abcd-ef1234567890/aaaa-bbbb"


# ===================================================================
# parse_rehydration_key
# ===================================================================


class TestParseRehydrationKey:
    def test_run_only(self) -> None:
        result = parse_rehydration_key("ev:run-abc-123")
        assert result == {"run_id": "run-abc-123", "event_id": None}

    def test_run_and_event(self) -> None:
        result = parse_rehydration_key("ev:run-1/evt-2")
        assert result == {"run_id": "run-1", "event_id": "evt-2"}

    def test_strips_whitespace(self) -> None:
        result = parse_rehydration_key("  ev:run-1/evt-2  ")
        assert result == {"run_id": "run-1", "event_id": "evt-2"}

    def test_invalid_prefix_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid rehydration key"):
            parse_rehydration_key("bad:run-1")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid rehydration key"):
            parse_rehydration_key("")

    def test_non_string_raises(self) -> None:
        with pytest.raises(ValueError, match="key must be a string"):
            parse_rehydration_key(123)  # type: ignore[arg-type]

    def test_no_prefix_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid rehydration key"):
            parse_rehydration_key("run-1/evt-2")

    def test_double_slash_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid rehydration key"):
            parse_rehydration_key("ev:run-1/evt-2/extra")

    def test_round_trip_run_only(self) -> None:
        key = rehydration_key("run-abc")
        parsed = parse_rehydration_key(key)
        assert parsed["run_id"] == "run-abc"
        assert parsed["event_id"] is None

    def test_round_trip_with_event(self) -> None:
        key = rehydration_key("run-abc", event_id="evt-xyz")
        parsed = parse_rehydration_key(key)
        assert parsed["run_id"] == "run-abc"
        assert parsed["event_id"] == "evt-xyz"

    def test_special_chars_in_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="invalid rehydration key"):
            parse_rehydration_key("ev:run id with spaces")

    def test_ev_prefix_only_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid rehydration key"):
            parse_rehydration_key("ev:")


# ===================================================================
# get_skill_event_by_id (store integration)
# ===================================================================


def _mock_db(*, execute_data: Any = None) -> MagicMock:
    db = MagicMock()
    table = MagicMock()
    response = MagicMock()
    response.data = execute_data if execute_data is not None else []

    db.table.return_value = table
    table.select.return_value = table
    table.eq.return_value = table
    table.limit.return_value = table
    table.execute.return_value = response

    return db


class TestGetSkillEventById:
    def test_returns_row_when_found(self) -> None:
        row = {"id": "evt-1", "skill_id": "test_skill", "payload": {"x": 1}}
        db = _mock_db(execute_data=[row])
        store = AgentLoopStore(db)

        result = store.get_skill_event_by_id("run-1", "evt-1")

        assert result == row
        db.table.assert_called_with("agent_skill_events")

    def test_returns_empty_when_not_found(self) -> None:
        db = _mock_db(execute_data=[])
        store = AgentLoopStore(db)

        result = store.get_skill_event_by_id("run-1", "evt-missing")

        assert result == {}

    def test_empty_run_id_raises(self) -> None:
        db = _mock_db()
        store = AgentLoopStore(db)

        with pytest.raises(ValueError, match="run_id is required"):
            store.get_skill_event_by_id("", "evt-1")

    def test_empty_event_id_raises(self) -> None:
        db = _mock_db()
        store = AgentLoopStore(db)

        with pytest.raises(ValueError, match="event_id is required"):
            store.get_skill_event_by_id("run-1", "")

    def test_queries_with_both_filters(self) -> None:
        db = _mock_db(execute_data=[{"id": "evt-1"}])
        store = AgentLoopStore(db)

        store.get_skill_event_by_id("run-1", "evt-1")

        eq_calls = db.table.return_value.eq.call_args_list
        eq_args = [(c.args[0], c.args[1]) for c in eq_calls]
        assert ("run_id", "run-1") in eq_args
        assert ("id", "evt-1") in eq_args


# ===================================================================
# End-to-end: summarize → note → rehydration round-trip
# ===================================================================


class TestEndToEnd:
    def test_summarize_then_note_then_rehydration(self) -> None:
        payload = {"client_name": "Acme", "limit": 10}

        summary = build_payload_summary("clickup_task_list", payload)
        note = build_evidence_note("skill_call", "clickup_task_list", summary)
        key = rehydration_key("run-abc", event_id="evt-123")
        parsed = parse_rehydration_key(key)

        assert summary == '{"client_name":"Acme","limit":10}'
        assert note == '[skill_call] clickup_task_list: {"client_name":"Acme","limit":10}'
        assert parsed == {"run_id": "run-abc", "event_id": "evt-123"}

    def test_large_payload_pipeline(self) -> None:
        payload = {"results": [{"id": i, "name": f"item-{i}"} for i in range(100)]}

        summary = build_payload_summary("big_skill", payload, max_chars=100)
        note = build_evidence_note("skill_result", "big_skill", summary)

        assert len(summary) <= 100
        assert summary.endswith("...")
        assert note.startswith("[skill_result] big_skill: ")
        assert note.endswith("...")
