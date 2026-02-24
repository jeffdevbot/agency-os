"""Unit tests for agent_loop_evidence_reader (C17G).

Validates the read_evidence service function against all success and
failure paths, including key parsing, event lookup, payload validation,
and deterministic note formatting.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.services.agencyclaw.agent_loop_evidence_reader import read_evidence
from app.services.agencyclaw.agent_loop_store import AgentLoopStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _store(execute_data: Any = None) -> AgentLoopStore:
    return AgentLoopStore(_mock_db(execute_data=execute_data))


def _valid_row(
    *,
    event_id: str = "evt-1",
    skill_id: str = "clickup_task_list",
    event_type: str = "skill_call",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": event_id,
        "skill_id": skill_id,
        "event_type": event_type,
        "payload": payload if payload is not None else {"client_name": "Acme"},
    }


# ===================================================================
# Success path
# ===================================================================


class TestValidEventKey:
    def test_returns_ok_with_note_and_summary(self) -> None:
        row = _valid_row()
        store = _store(execute_data=[row])

        result = read_evidence(store, "ev:run-1/evt-1")

        assert result["ok"] is True
        assert result["run_id"] == "run-1"
        assert result["event_id"] == "evt-1"
        assert result["error"] is None
        assert result["payload_summary"] == '{"client_name":"Acme"}'
        assert result["note"] == '[skill_call] clickup_task_list: {"client_name":"Acme"}'

    def test_skill_result_event(self) -> None:
        row = _valid_row(event_type="skill_result", payload={"count": 3})
        store = _store(execute_data=[row])

        result = read_evidence(store, "ev:run-1/evt-1")

        assert result["ok"] is True
        assert result["note"] == '[skill_result] clickup_task_list: {"count":3}'
        assert result["payload_summary"] == '{"count":3}'

    def test_large_payload_truncated(self) -> None:
        row = _valid_row(payload={"data": "x" * 500})
        store = _store(execute_data=[row])

        result = read_evidence(store, "ev:run-1/evt-1")

        assert result["ok"] is True
        assert len(result["payload_summary"]) <= 280
        assert result["payload_summary"].endswith("...")

    def test_empty_payload(self) -> None:
        row = _valid_row(payload={})
        store = _store(execute_data=[row])

        result = read_evidence(store, "ev:run-1/evt-1")

        assert result["ok"] is True
        assert result["payload_summary"] == "{}"
        assert result["note"] == "[skill_call] clickup_task_list: {}"


# ===================================================================
# Deterministic formatting
# ===================================================================


class TestDeterministicFormatting:
    def test_sorted_keys_in_summary(self) -> None:
        row = _valid_row(payload={"z": 1, "a": 2, "m": 3})
        store = _store(execute_data=[row])

        result = read_evidence(store, "ev:run-1/evt-1")

        assert result["payload_summary"] == '{"a":2,"m":3,"z":1}'

    def test_same_input_same_output(self) -> None:
        row = _valid_row(payload={"b": 2, "a": 1})
        store = _store(execute_data=[row])

        r1 = read_evidence(store, "ev:run-1/evt-1")
        r2 = read_evidence(store, "ev:run-1/evt-1")

        assert r1 == r2

    def test_note_format_matches_convention(self) -> None:
        row = _valid_row(
            event_type="skill_call",
            skill_id="cc_brand_list_all",
            payload={"client": "Acme"},
        )
        store = _store(execute_data=[row])

        result = read_evidence(store, "ev:run-1/evt-1")

        assert result["note"] == '[skill_call] cc_brand_list_all: {"client":"Acme"}'


# ===================================================================
# Invalid key
# ===================================================================


class TestInvalidKey:
    def test_bad_prefix(self) -> None:
        result = read_evidence(_store(), "bad:run-1/evt-1")

        assert result["ok"] is False
        assert result["error"] == "invalid_key"
        assert result["run_id"] is None
        assert result["event_id"] is None

    def test_empty_string(self) -> None:
        result = read_evidence(_store(), "")

        assert result["ok"] is False
        assert result["error"] == "invalid_key"

    def test_no_prefix(self) -> None:
        result = read_evidence(_store(), "run-1/evt-1")

        assert result["ok"] is False
        assert result["error"] == "invalid_key"

    def test_non_string_key(self) -> None:
        result = read_evidence(_store(), 123)  # type: ignore[arg-type]

        assert result["ok"] is False
        assert result["error"] == "invalid_key"

    def test_spaces_in_key(self) -> None:
        result = read_evidence(_store(), "ev:run id/evt id")

        assert result["ok"] is False
        assert result["error"] == "invalid_key"


# ===================================================================
# Run-only key (not implemented)
# ===================================================================


class TestRunOnlyKey:
    def test_returns_not_implemented(self) -> None:
        result = read_evidence(_store(), "ev:run-abc")

        assert result["ok"] is False
        assert result["error"] == "not_implemented_run_scope"
        assert result["run_id"] == "run-abc"
        assert result["event_id"] is None
        assert result["note"] is None
        assert result["payload_summary"] is None

    def test_preserves_run_id(self) -> None:
        result = read_evidence(_store(), "ev:my-special-run-123")

        assert result["run_id"] == "my-special-run-123"
        assert result["error"] == "not_implemented_run_scope"


# ===================================================================
# Missing event
# ===================================================================


class TestMissingEvent:
    def test_returns_not_found(self) -> None:
        store = _store(execute_data=[])

        result = read_evidence(store, "ev:run-1/evt-missing")

        assert result["ok"] is False
        assert result["error"] == "not_found"
        assert result["run_id"] == "run-1"
        assert result["event_id"] == "evt-missing"
        assert result["note"] is None

    def test_none_data_returns_not_found(self) -> None:
        db = _mock_db()
        db.table.return_value.execute.return_value.data = None
        store = AgentLoopStore(db)

        result = read_evidence(store, "ev:run-1/evt-1")

        assert result["ok"] is False
        assert result["error"] == "not_found"


# ===================================================================
# Malformed event payload
# ===================================================================


class TestMalformedPayload:
    def test_missing_skill_id(self) -> None:
        row = {"id": "evt-1", "event_type": "skill_call", "payload": {"x": 1}}
        store = _store(execute_data=[row])

        result = read_evidence(store, "ev:run-1/evt-1")

        assert result["ok"] is False
        assert result["error"] == "invalid_event_payload"
        assert result["run_id"] == "run-1"
        assert result["event_id"] == "evt-1"

    def test_missing_event_type(self) -> None:
        row = {"id": "evt-1", "skill_id": "test", "payload": {"x": 1}}
        store = _store(execute_data=[row])

        result = read_evidence(store, "ev:run-1/evt-1")

        assert result["ok"] is False
        assert result["error"] == "invalid_event_payload"

    def test_non_dict_payload(self) -> None:
        row = {"id": "evt-1", "skill_id": "test", "event_type": "skill_call", "payload": "bad"}
        store = _store(execute_data=[row])

        result = read_evidence(store, "ev:run-1/evt-1")

        assert result["ok"] is False
        assert result["error"] == "invalid_event_payload"

    def test_null_payload(self) -> None:
        row = {"id": "evt-1", "skill_id": "test", "event_type": "skill_call", "payload": None}
        store = _store(execute_data=[row])

        result = read_evidence(store, "ev:run-1/evt-1")

        assert result["ok"] is False
        assert result["error"] == "invalid_event_payload"

    def test_empty_skill_id(self) -> None:
        row = {"id": "evt-1", "skill_id": "", "event_type": "skill_call", "payload": {"x": 1}}
        store = _store(execute_data=[row])

        result = read_evidence(store, "ev:run-1/evt-1")

        assert result["ok"] is False
        assert result["error"] == "invalid_event_payload"

    def test_whitespace_skill_id(self) -> None:
        row = {"id": "evt-1", "skill_id": "   ", "event_type": "skill_call", "payload": {"x": 1}}
        store = _store(execute_data=[row])

        result = read_evidence(store, "ev:run-1/evt-1")

        assert result["ok"] is False
        assert result["error"] == "invalid_event_payload"


# ===================================================================
# Output shape consistency
# ===================================================================


class TestOutputShape:
    """Every result has exactly the six expected keys."""

    _EXPECTED_KEYS = {"ok", "run_id", "event_id", "note", "payload_summary", "error"}

    def test_success_shape(self) -> None:
        row = _valid_row()
        store = _store(execute_data=[row])

        result = read_evidence(store, "ev:run-1/evt-1")

        assert set(result.keys()) == self._EXPECTED_KEYS

    def test_invalid_key_shape(self) -> None:
        result = read_evidence(_store(), "garbage")

        assert set(result.keys()) == self._EXPECTED_KEYS

    def test_not_found_shape(self) -> None:
        result = read_evidence(_store(), "ev:run-1/evt-1")

        assert set(result.keys()) == self._EXPECTED_KEYS

    def test_run_only_shape(self) -> None:
        result = read_evidence(_store(), "ev:run-1")

        assert set(result.keys()) == self._EXPECTED_KEYS

    def test_malformed_payload_shape(self) -> None:
        row = {"id": "evt-1", "skill_id": "test", "event_type": "skill_call", "payload": "bad"}
        result = read_evidence(_store(execute_data=[row]), "ev:run-1/evt-1")

        assert set(result.keys()) == self._EXPECTED_KEYS


# ===================================================================
# Integration seam: reader → store query path
# ===================================================================


class TestIntegrationSeam:
    """Verify read_evidence drives the store's query interface correctly.

    These tests validate the seam contract between reader and store so
    that wiring to a real Supabase client later requires no reader changes.
    """

    def test_store_receives_correct_table_and_filters(self) -> None:
        row = _valid_row(event_id="evt-42", skill_id="my_skill")
        db = _mock_db(execute_data=[row])
        store = AgentLoopStore(db)

        read_evidence(store, "ev:run-99/evt-42")

        db.table.assert_called_with("agent_skill_events")
        eq_calls = db.table.return_value.eq.call_args_list
        eq_args = [(c.args[0], c.args[1]) for c in eq_calls]
        assert ("run_id", "run-99") in eq_args
        assert ("id", "evt-42") in eq_args

    def test_store_limit_1_applied(self) -> None:
        db = _mock_db(execute_data=[_valid_row()])
        store = AgentLoopStore(db)

        read_evidence(store, "ev:run-1/evt-1")

        db.table.return_value.limit.assert_called_with(1)

    def test_round_trip_key_to_result(self) -> None:
        """Full pipeline: generate key → read_evidence → verify deterministic output."""
        from app.services.agencyclaw.agent_loop_evidence import rehydration_key

        key = rehydration_key("run-abc", event_id="evt-xyz")
        row = _valid_row(
            event_id="evt-xyz",
            skill_id="clickup_task_list",
            event_type="skill_result",
            payload={"tasks": [{"id": "t1", "name": "Fix bug"}]},
        )
        store = _store(execute_data=[row])

        result = read_evidence(store, key)

        assert result["ok"] is True
        assert result["run_id"] == "run-abc"
        assert result["event_id"] == "evt-xyz"
        assert result["note"].startswith("[skill_result] clickup_task_list:")
        assert "t1" in result["payload_summary"]

    def test_missing_event_propagates_through_store(self) -> None:
        """Store returns {} for missing row; reader maps to not_found."""
        db = _mock_db(execute_data=[])
        store = AgentLoopStore(db)

        result = read_evidence(store, "ev:run-1/evt-ghost")

        assert result["ok"] is False
        assert result["error"] == "not_found"
        db.table.assert_called_with("agent_skill_events")
