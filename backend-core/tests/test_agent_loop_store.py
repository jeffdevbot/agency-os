from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.services.agencyclaw.agent_loop_store import AgentLoopStore, summarize_json


def _mock_db(*, execute_data: Any) -> MagicMock:
    db = MagicMock()
    table = MagicMock()
    response = MagicMock()
    response.data = execute_data

    db.table.return_value = table
    table.insert.return_value = table
    table.update.return_value = table
    table.select.return_value = table
    table.eq.return_value = table
    table.order.return_value = table
    table.limit.return_value = table
    table.execute.return_value = response

    return db


def test_create_run_happy_path():
    db = _mock_db(execute_data=[{"id": "r1", "status": "running"}])
    svc = AgentLoopStore(db)

    row = svc.create_run("s1", run_type="main")

    assert row == {"id": "r1", "status": "running"}
    db.table.assert_called_with("agent_runs")
    insert_payload = db.table.return_value.insert.call_args.args[0]
    assert insert_payload["session_id"] == "s1"
    assert insert_payload["run_type"] == "main"
    assert insert_payload["status"] == "running"


def test_append_message_happy_path():
    db = _mock_db(execute_data=[{"id": "m1", "role": "assistant"}])
    svc = AgentLoopStore(db)

    row = svc.append_message("r1", "assistant", {"text": "hello"}, summary="short")

    assert row == {"id": "m1", "role": "assistant"}
    db.table.assert_called_with("agent_messages")
    insert_payload = db.table.return_value.insert.call_args.args[0]
    assert insert_payload == {
        "run_id": "r1",
        "role": "assistant",
        "content": {"text": "hello"},
        "summary": "short",
    }


def test_append_skill_event_happy_path():
    db = _mock_db(execute_data=[{"id": "e1", "event_type": "skill_call"}])
    svc = AgentLoopStore(db)

    row = svc.append_skill_event(
        run_id="r1",
        event_type="skill_call",
        skill_id="list_tasks",
        payload={"client_id": "c1"},
        payload_summary="c1",
    )

    assert row == {"id": "e1", "event_type": "skill_call"}
    db.table.assert_called_with("agent_skill_events")
    insert_payload = db.table.return_value.insert.call_args.args[0]
    assert insert_payload == {
        "run_id": "r1",
        "event_type": "skill_call",
        "skill_id": "list_tasks",
        "payload": {"client_id": "c1"},
        "payload_summary": "c1",
    }


def test_update_run_status_completed_sets_completed_at():
    db = _mock_db(execute_data=[])
    svc = AgentLoopStore(db)

    svc.update_run_status("r1", "completed", completed=True)

    db.table.assert_called_with("agent_runs")
    update_payload = db.table.return_value.update.call_args.args[0]
    assert update_payload["status"] == "completed"
    assert isinstance(update_payload.get("completed_at"), str)
    db.table.return_value.eq.assert_called_with("id", "r1")


def test_list_recent_run_messages_returns_empty_on_non_list_data():
    db = _mock_db(execute_data={"not": "a list"})
    svc = AgentLoopStore(db)

    rows = svc.list_recent_run_messages("r1", limit=10)

    assert rows == []


def test_list_recent_run_messages_filters_non_dict_rows():
    db = _mock_db(execute_data=[{"id": "m1"}, "bad", 123, {"id": "m2"}])
    svc = AgentLoopStore(db)

    rows = svc.list_recent_run_messages("r1", limit=10)

    assert rows == [{"id": "m1"}, {"id": "m2"}]


def test_summarize_json_stable_and_truncates():
    payload = {"b": 2, "a": 1}

    full = summarize_json(payload, max_chars=100)
    short = summarize_json(payload, max_chars=8)

    assert full == '{"a":1,"b":2}'
    assert short.endswith("...")
    assert len(short) == 8
    assert summarize_json(payload, max_chars=100) == full


def test_invalid_create_run_empty_session_id_raises():
    db = _mock_db(execute_data=[])
    svc = AgentLoopStore(db)

    with pytest.raises(ValueError, match="session_id is required"):
        svc.create_run("")


def test_invalid_append_message_role_raises():
    db = _mock_db(execute_data=[])
    svc = AgentLoopStore(db)

    with pytest.raises(ValueError, match="role must be one of"):
        svc.append_message("r1", "bot", {"text": "x"})


def test_invalid_append_skill_event_type_raises():
    db = _mock_db(execute_data=[])
    svc = AgentLoopStore(db)

    with pytest.raises(ValueError, match="event_type must be one of"):
        svc.append_skill_event("r1", "call", "x", {})


def test_invalid_list_limit_raises():
    db = _mock_db(execute_data=[])
    svc = AgentLoopStore(db)

    with pytest.raises(ValueError, match="limit must be > 0"):
        svc.list_recent_run_messages("r1", limit=0)


def test_invalid_summarize_json_payload_raises():
    with pytest.raises(ValueError, match="payload must be a dict"):
        summarize_json("nope")  # type: ignore[arg-type]


# ===================================================================
# C17D hardening: additional edge cases
# ===================================================================


def test_summarize_json_extremely_long_payload():
    """Extremely long payload truncates to exactly max_chars with '...' suffix."""
    payload = {"data": "x" * 1000}
    result = summarize_json(payload, max_chars=50)
    assert len(result) == 50
    assert result.endswith("...")


def test_summarize_json_max_chars_at_boundary():
    """Payload that fits exactly at max_chars boundary is not truncated."""
    payload = {"a": 1}
    rendered = '{"a":1}'
    result = summarize_json(payload, max_chars=len(rendered))
    assert result == rendered
    assert not result.endswith("...")


def test_summarize_json_max_chars_3_or_less():
    """When max_chars <= 3, truncation omits the '...' suffix."""
    payload = {"a": 1}
    result = summarize_json(payload, max_chars=3)
    assert len(result) == 3
    assert result == '{"a'


def test_summarize_json_negative_max_chars_raises():
    with pytest.raises(ValueError, match="max_chars must be > 0"):
        summarize_json({"a": 1}, max_chars=0)


def test_create_run_planner_type():
    db = _mock_db(execute_data=[{"id": "r1", "run_type": "planner"}])
    svc = AgentLoopStore(db)

    row = svc.create_run("s1", run_type="planner", parent_run_id="parent-1")

    insert_payload = db.table.return_value.insert.call_args.args[0]
    assert insert_payload["run_type"] == "planner"
    assert insert_payload["parent_run_id"] == "parent-1"


def test_create_run_invalid_run_type_raises():
    db = _mock_db(execute_data=[])
    svc = AgentLoopStore(db)

    with pytest.raises(ValueError, match="run_type must be one of"):
        svc.create_run("s1", run_type="background")


def test_create_run_whitespace_only_parent_run_id_raises():
    db = _mock_db(execute_data=[])
    svc = AgentLoopStore(db)

    with pytest.raises(ValueError, match="parent_run_id must be non-empty"):
        svc.create_run("s1", parent_run_id="   ")


def test_update_run_status_without_completed_flag():
    """When completed=False, completed_at is not set regardless of status."""
    db = _mock_db(execute_data=[])
    svc = AgentLoopStore(db)

    svc.update_run_status("r1", "running", completed=False)

    update_payload = db.table.return_value.update.call_args.args[0]
    assert update_payload["status"] == "running"
    assert "completed_at" not in update_payload


def test_update_run_status_blocked():
    db = _mock_db(execute_data=[])
    svc = AgentLoopStore(db)

    svc.update_run_status("r1", "blocked", completed=True)

    update_payload = db.table.return_value.update.call_args.args[0]
    assert update_payload["status"] == "blocked"
    assert "completed_at" in update_payload


def test_update_run_status_failed():
    db = _mock_db(execute_data=[])
    svc = AgentLoopStore(db)

    svc.update_run_status("r1", "failed", completed=True)

    update_payload = db.table.return_value.update.call_args.args[0]
    assert update_payload["status"] == "failed"
    assert isinstance(update_payload["completed_at"], str)


def test_update_run_status_invalid_raises():
    db = _mock_db(execute_data=[])
    svc = AgentLoopStore(db)

    with pytest.raises(ValueError, match="status must be one of"):
        svc.update_run_status("r1", "cancelled")


def test_append_message_all_valid_roles():
    """All four valid roles are accepted without error."""
    for role in ("user", "assistant", "system", "planner_report"):
        db = _mock_db(execute_data=[{"id": "m1", "role": role}])
        svc = AgentLoopStore(db)
        row = svc.append_message("r1", role, {"text": "x"})
        assert row["role"] == role


def test_append_message_non_dict_content_raises():
    db = _mock_db(execute_data=[])
    svc = AgentLoopStore(db)

    with pytest.raises(ValueError, match="content must be a dict"):
        svc.append_message("r1", "user", "plain string")  # type: ignore[arg-type]


def test_append_message_omits_summary_when_none():
    db = _mock_db(execute_data=[{"id": "m1"}])
    svc = AgentLoopStore(db)

    svc.append_message("r1", "user", {"text": "hi"})

    insert_payload = db.table.return_value.insert.call_args.args[0]
    assert "summary" not in insert_payload


def test_append_skill_event_omits_payload_summary_when_none():
    db = _mock_db(execute_data=[{"id": "e1"}])
    svc = AgentLoopStore(db)

    svc.append_skill_event("r1", "skill_call", "test", {"x": 1})

    insert_payload = db.table.return_value.insert.call_args.args[0]
    assert "payload_summary" not in insert_payload


def test_append_skill_event_non_dict_payload_raises():
    db = _mock_db(execute_data=[])
    svc = AgentLoopStore(db)

    with pytest.raises(ValueError, match="payload must be a dict"):
        svc.append_skill_event("r1", "skill_call", "test", "bad")  # type: ignore[arg-type]


def test_first_row_returns_empty_on_none_data():
    """_first_row handles response.data being None gracefully."""
    db = _mock_db(execute_data=[{"id": "r1"}])
    svc = AgentLoopStore(db)

    # Override response.data to None
    db.table.return_value.execute.return_value.data = None
    row = svc.create_run("s1")
    assert row == {}
