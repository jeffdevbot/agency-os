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
