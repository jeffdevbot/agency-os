"""Unit tests for AgentLoopTurnLogger (C17D).

Validates the lifecycle facade delegates correctly to AgentLoopStore
and produces the expected payload shapes.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.services.agencyclaw.agent_loop_store import AgentLoopStore
from app.services.agencyclaw.agent_loop_turn_logger import AgentLoopTurnLogger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_db(*, execute_data: Any = None) -> MagicMock:
    """Build a mock Supabase client matching AgentLoopStore usage."""
    db = MagicMock()
    table = MagicMock()
    response = MagicMock()
    response.data = execute_data if execute_data is not None else []

    db.table.return_value = table
    table.insert.return_value = table
    table.update.return_value = table
    table.select.return_value = table
    table.eq.return_value = table
    table.order.return_value = table
    table.limit.return_value = table
    table.execute.return_value = response

    return db


def _make_logger(execute_data: Any = None) -> tuple[AgentLoopTurnLogger, MagicMock]:
    db = _mock_db(execute_data=execute_data)
    store = AgentLoopStore(db)
    return AgentLoopTurnLogger(store), db


# ===================================================================
# Run lifecycle
# ===================================================================


class TestStartMainRun:
    def test_creates_run_with_main_type(self) -> None:
        logger, db = _make_logger([{"id": "r1", "status": "running"}])

        row = logger.start_main_run("sess-1")

        assert row["id"] == "r1"
        assert row["status"] == "running"
        db.table.assert_called_with("agent_runs")
        insert_payload = db.table.return_value.insert.call_args.args[0]
        assert insert_payload["session_id"] == "sess-1"
        assert insert_payload["run_type"] == "main"
        assert insert_payload["status"] == "running"

    def test_passes_trace_id_when_provided(self) -> None:
        logger, db = _make_logger([{"id": "r2", "status": "running"}])

        logger.start_main_run("sess-1", trace_id="trace-abc")

        insert_payload = db.table.return_value.insert.call_args.args[0]
        assert insert_payload["trace_id"] == "trace-abc"

    def test_omits_trace_id_when_none(self) -> None:
        logger, db = _make_logger([{"id": "r3", "status": "running"}])

        logger.start_main_run("sess-1")

        insert_payload = db.table.return_value.insert.call_args.args[0]
        assert "trace_id" not in insert_payload

    def test_rejects_empty_session_id(self) -> None:
        logger, _ = _make_logger()

        with pytest.raises(ValueError, match="session_id is required"):
            logger.start_main_run("")


class TestCompleteRun:
    def test_completed_sets_completed_at(self) -> None:
        logger, db = _make_logger()

        logger.complete_run("r1", "completed")

        db.table.assert_called_with("agent_runs")
        update_payload = db.table.return_value.update.call_args.args[0]
        assert update_payload["status"] == "completed"
        assert "completed_at" in update_payload

    def test_failed_sets_completed_at(self) -> None:
        logger, db = _make_logger()

        logger.complete_run("r1", "failed")

        update_payload = db.table.return_value.update.call_args.args[0]
        assert update_payload["status"] == "failed"
        assert "completed_at" in update_payload

    def test_blocked_sets_completed_at(self) -> None:
        logger, db = _make_logger()

        logger.complete_run("r1", "blocked")

        update_payload = db.table.return_value.update.call_args.args[0]
        assert update_payload["status"] == "blocked"
        assert "completed_at" in update_payload

    def test_rejects_invalid_status(self) -> None:
        logger, _ = _make_logger()

        with pytest.raises(ValueError, match="status must be one of"):
            logger.complete_run("r1", "cancelled")


# ===================================================================
# Message logging
# ===================================================================


class TestLogUserMessage:
    def test_inserts_user_role_with_text_payload(self) -> None:
        logger, db = _make_logger([{"id": "m1", "role": "user"}])

        row = logger.log_user_message("r1", "Show me tasks")

        assert row["id"] == "m1"
        db.table.assert_called_with("agent_messages")
        insert_payload = db.table.return_value.insert.call_args.args[0]
        assert insert_payload["run_id"] == "r1"
        assert insert_payload["role"] == "user"
        assert insert_payload["content"] == {"text": "Show me tasks"}

    def test_includes_summary_when_provided(self) -> None:
        logger, db = _make_logger([{"id": "m2"}])

        logger.log_user_message("r1", "A long message...", summary="short")

        insert_payload = db.table.return_value.insert.call_args.args[0]
        assert insert_payload["summary"] == "short"

    def test_omits_summary_when_none(self) -> None:
        logger, db = _make_logger([{"id": "m3"}])

        logger.log_user_message("r1", "hello")

        insert_payload = db.table.return_value.insert.call_args.args[0]
        assert "summary" not in insert_payload


class TestLogAssistantMessage:
    def test_inserts_assistant_role_with_text_payload(self) -> None:
        logger, db = _make_logger([{"id": "m4", "role": "assistant"}])

        row = logger.log_assistant_message("r1", "Here are your tasks")

        assert row["id"] == "m4"
        insert_payload = db.table.return_value.insert.call_args.args[0]
        assert insert_payload["role"] == "assistant"
        assert insert_payload["content"] == {"text": "Here are your tasks"}

    def test_includes_summary_when_provided(self) -> None:
        logger, db = _make_logger([{"id": "m5"}])

        logger.log_assistant_message("r1", "long reply", summary="short")

        insert_payload = db.table.return_value.insert.call_args.args[0]
        assert insert_payload["summary"] == "short"


# ===================================================================
# Skill event logging
# ===================================================================


class TestLogSkillCall:
    def test_inserts_skill_call_event(self) -> None:
        logger, db = _make_logger([{"id": "e1", "event_type": "skill_call"}])

        row = logger.log_skill_call(
            "r1", "clickup_task_list", {"client_name": "Acme"},
        )

        assert row["id"] == "e1"
        db.table.assert_called_with("agent_skill_events")
        insert_payload = db.table.return_value.insert.call_args.args[0]
        assert insert_payload["run_id"] == "r1"
        assert insert_payload["event_type"] == "skill_call"
        assert insert_payload["skill_id"] == "clickup_task_list"
        assert insert_payload["payload"] == {"client_name": "Acme"}

    def test_auto_generates_payload_summary(self) -> None:
        logger, db = _make_logger([{"id": "e2"}])

        logger.log_skill_call("r1", "clickup_task_list", {"client_name": "Acme"})

        insert_payload = db.table.return_value.insert.call_args.args[0]
        assert insert_payload["payload_summary"] == '{"client_name":"Acme"}'

    def test_uses_explicit_payload_summary(self) -> None:
        logger, db = _make_logger([{"id": "e3"}])

        logger.log_skill_call(
            "r1", "clickup_task_list", {"client_name": "Acme"},
            payload_summary="Acme tasks",
        )

        insert_payload = db.table.return_value.insert.call_args.args[0]
        assert insert_payload["payload_summary"] == "Acme tasks"

    def test_rejects_empty_skill_id(self) -> None:
        logger, _ = _make_logger()

        with pytest.raises(ValueError, match="skill_id is required"):
            logger.log_skill_call("r1", "", {"x": 1})


class TestLogSkillResult:
    def test_inserts_skill_result_event(self) -> None:
        logger, db = _make_logger([{"id": "e4", "event_type": "skill_result"}])

        row = logger.log_skill_result(
            "r1", "clickup_task_list", {"tasks": [{"id": "t1"}]},
        )

        assert row["id"] == "e4"
        insert_payload = db.table.return_value.insert.call_args.args[0]
        assert insert_payload["event_type"] == "skill_result"
        assert insert_payload["skill_id"] == "clickup_task_list"
        assert insert_payload["payload"] == {"tasks": [{"id": "t1"}]}

    def test_auto_generates_payload_summary(self) -> None:
        logger, db = _make_logger([{"id": "e5"}])

        logger.log_skill_result("r1", "clickup_task_list", {"count": 3})

        insert_payload = db.table.return_value.insert.call_args.args[0]
        assert insert_payload["payload_summary"] == '{"count":3}'

    def test_truncates_large_payloads_in_auto_summary(self) -> None:
        logger, db = _make_logger([{"id": "e6"}])
        big_payload = {"data": "x" * 500}

        logger.log_skill_result("r1", "clickup_task_list", big_payload)

        insert_payload = db.table.return_value.insert.call_args.args[0]
        summary = insert_payload["payload_summary"]
        assert len(summary) <= 280
        assert summary.endswith("...")


# ===================================================================
# Full lifecycle integration
# ===================================================================


class TestFullTurnLifecycle:
    """Validates a realistic turn sequence produces correct call order."""

    def test_full_turn_calls_store_in_order(self) -> None:
        db = _mock_db(execute_data=[{"id": "generated"}])
        store = AgentLoopStore(db)
        logger = AgentLoopTurnLogger(store)

        # Simulate a full turn
        logger.start_main_run("sess-1")
        logger.log_user_message("r1", "Show tasks for Acme")
        logger.log_skill_call("r1", "clickup_task_list", {"client_name": "Acme"})
        logger.log_skill_result("r1", "clickup_task_list", {"tasks": []})
        logger.log_assistant_message("r1", "No tasks found for Acme.")
        logger.complete_run("r1", "completed")

        # Verify table call sequence
        table_calls = [c.args[0] for c in db.table.call_args_list]
        assert table_calls == [
            "agent_runs",         # start_main_run
            "agent_messages",     # log_user_message
            "agent_skill_events", # log_skill_call
            "agent_skill_events", # log_skill_result
            "agent_messages",     # log_assistant_message
            "agent_runs",         # complete_run
        ]

    def test_multi_skill_turn(self) -> None:
        """A turn that calls two skills before replying."""
        db = _mock_db(execute_data=[{"id": "generated"}])
        store = AgentLoopStore(db)
        logger = AgentLoopTurnLogger(store)

        logger.start_main_run("sess-1")
        logger.log_user_message("r1", "tasks and brands for Acme")
        logger.log_skill_call("r1", "clickup_task_list", {"client_name": "Acme"})
        logger.log_skill_result("r1", "clickup_task_list", {"tasks": []})
        logger.log_skill_call("r1", "cc_brand_list_all", {"client_name": "Acme"})
        logger.log_skill_result("r1", "cc_brand_list_all", {"brands": []})
        logger.log_assistant_message("r1", "No tasks or brands found.")
        logger.complete_run("r1", "completed")

        table_calls = [c.args[0] for c in db.table.call_args_list]
        assert table_calls == [
            "agent_runs",
            "agent_messages",
            "agent_skill_events",
            "agent_skill_events",
            "agent_skill_events",
            "agent_skill_events",
            "agent_messages",
            "agent_runs",
        ]
