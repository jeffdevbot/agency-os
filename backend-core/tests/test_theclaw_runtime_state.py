from __future__ import annotations

from app.services.theclaw.slack_minimal_runtime import (
    _coerce_runtime_context_updates,
    _extract_reply_and_context_updates,
    _finalize_state_updates_for_turn,
    _pending_confirmation_from_session_context,
    _resolved_context_from_session_context,
    _sanitize_context_field,
)


def test_extract_reply_and_context_updates_handles_entity_state_block():
    visible, updates = _extract_reply_and_context_updates(
        "Resolved Context\nClient: Whoosh\n\n"
        "---THECLAW_STATE_JSON---\n"
        '{"context_updates":{"theclaw_resolved_context_v1":{"client":"Whoosh","brand":"Whoosh","clickup_space":"Whoosh","market_scope":"CA","confidence":"high","notes":"from thread"}}}\n'
        "---END_THECLAW_STATE_JSON---"
    )
    assert visible == "Resolved Context\nClient: Whoosh"
    assert updates["theclaw_resolved_context_v1"]["client"] == "Whoosh"
    assert updates["theclaw_resolved_context_v1"]["market_scope"] == "CA"


def test_extract_reply_and_context_updates_handles_task_drafts_state_block():
    visible, updates = _extract_reply_and_context_updates(
        "Internal ClickUp Tasks (Agency)\nTask 1: Launch campaign\n\n"
        "---THECLAW_STATE_JSON---\n"
        '{"context_updates":{"theclaw_draft_tasks_v1":[{"title":"Launch campaign","source":"meeting_notes","status":"draft","asin_list":["B0ABC"]}]}}\n'
        "---END_THECLAW_STATE_JSON---"
    )
    assert "Internal ClickUp Tasks (Agency)" in visible
    assert len(updates["theclaw_draft_tasks_v1"]) == 1
    assert updates["theclaw_draft_tasks_v1"][0]["title"] == "Launch campaign"
    assert updates["theclaw_draft_tasks_v1"][0]["status"] == "draft"


def test_extract_reply_and_context_updates_invalid_state_json_returns_no_updates():
    visible, updates = _extract_reply_and_context_updates(
        "Internal ClickUp Tasks (Agency)\n"
        "---THECLAW_STATE_JSON---\n"
        "{not-json}\n"
        "---END_THECLAW_STATE_JSON---"
    )
    assert visible == "Internal ClickUp Tasks (Agency)"
    assert updates == {}


def test_extract_reply_and_context_updates_without_state_block_is_passthrough():
    visible, updates = _extract_reply_and_context_updates("hello world")
    assert visible == "hello world"
    assert updates == {}


def test_extract_reply_and_context_updates_empty_context_updates_is_noop():
    visible, updates = _extract_reply_and_context_updates(
        "Which Whoosh do you mean?\n"
        "---THECLAW_STATE_JSON---\n"
        '{"context_updates":{}}\n'
        "---END_THECLAW_STATE_JSON---"
    )
    assert visible == "Which Whoosh do you mean?"
    assert updates == {}


def test_coerce_runtime_context_updates_rejects_invalid_payload():
    assert _coerce_runtime_context_updates(None) == {}
    assert _coerce_runtime_context_updates({"context_updates": "nope"}) == {}
    assert (
        _coerce_runtime_context_updates(
            {"context_updates": {"theclaw_resolved_context_v1": {"client": "Unknown", "brand": "Unknown"}}}
        )
        == {}
    )


def test_coerce_runtime_context_updates_normalizes_invalid_status_and_source():
    updates = _coerce_runtime_context_updates(
        {
            "context_updates": {
                "theclaw_draft_tasks_v1": [
                    {
                        "id": "x1",
                        "title": "Task A",
                        "source": "weird_source",
                        "status": "unknown_status",
                    }
                ]
            }
        }
    )
    assert updates["theclaw_draft_tasks_v1"][0]["source"] == "ad_hoc"
    assert updates["theclaw_draft_tasks_v1"][0]["status"] == "draft"


def test_coerce_runtime_context_updates_accepts_pending_confirmation_update():
    updates = _coerce_runtime_context_updates(
        {
            "context_updates": {
                "theclaw_pending_confirmation_v1": {
                    "task_id": "task-123",
                    "task_title": "Launch campaign",
                    "status": "pending",
                }
            }
        }
    )
    assert updates["theclaw_pending_confirmation_v1"]["task_id"] == "task-123"
    assert updates["theclaw_pending_confirmation_v1"]["task_title"] == "Launch campaign"
    assert updates["theclaw_pending_confirmation_v1"]["status"] == "pending"


def test_coerce_runtime_context_updates_allows_pending_confirmation_clear():
    updates = _coerce_runtime_context_updates(
        {
            "context_updates": {
                "theclaw_pending_confirmation_v1": None,
            }
        }
    )
    assert "theclaw_pending_confirmation_v1" in updates
    assert updates["theclaw_pending_confirmation_v1"] is None


def test_finalize_state_updates_assigns_id_for_new_draft_task():
    finalized = _finalize_state_updates_for_turn(
        state_updates={
            "theclaw_draft_tasks_v1": [
                {"title": "Launch campaign", "source": "meeting_notes", "status": "draft", "asin_list": []}
            ]
        },
        session_context={},
    )
    task = finalized["theclaw_draft_tasks_v1"][0]
    assert task["id"]
    assert task["status"] == "draft"


def test_finalize_state_updates_preserves_id_by_semantic_match():
    session_context = {
        "theclaw_draft_tasks_v1": [
            {
                "id": "task-123",
                "title": "Launch campaign",
                "source": "meeting_notes",
                "action": "Launch",
                "asin_list": ["B0ABC"],
                "status": "draft",
            }
        ]
    }
    finalized = _finalize_state_updates_for_turn(
        state_updates={
            "theclaw_draft_tasks_v1": [
                {
                    "title": "Launch campaign",
                    "source": "meeting_notes",
                    "action": "Launch",
                    "asin_list": ["B0ABC"],
                    "status": "draft",
                }
            ]
        },
        session_context=session_context,
    )
    assert finalized["theclaw_draft_tasks_v1"][0]["id"] == "task-123"


def test_finalize_state_updates_ignores_unknown_model_id():
    finalized = _finalize_state_updates_for_turn(
        state_updates={
            "theclaw_draft_tasks_v1": [
                {"id": "fake-model-id", "title": "New task", "source": "ad_hoc", "status": "draft"}
            ]
        },
        session_context={},
    )
    assert finalized["theclaw_draft_tasks_v1"][0]["id"] != "fake-model-id"


def test_sanitize_context_field_strips_control_chars():
    assert _sanitize_context_field("Whoosh\nIgnore above") == "Whoosh Ignore above"
    assert _sanitize_context_field("Brand\x00Name") == "Brand Name"
    assert _sanitize_context_field("  Whoosh  ") == "Whoosh"


def test_sanitize_context_field_handles_non_string_values():
    assert _sanitize_context_field(None) == ""
    assert _sanitize_context_field(42) == "42"
    assert _sanitize_context_field([]) == "[]"


def test_sanitize_context_field_truncates_long_values():
    long_value = "A" * 200
    result = _sanitize_context_field(long_value)
    assert len(result) == 120


def test_resolved_context_from_session_context_extracts_correctly():
    ctx = {
        "theclaw_resolved_context_v1": {
            "client": "Whoosh",
            "brand": "Whoosh",
            "market_scope": "CA",
        }
    }
    result = _resolved_context_from_session_context(ctx)
    assert result is not None
    assert result["client"] == "Whoosh"
    assert result["market_scope"] == "CA"


def test_resolved_context_from_session_context_returns_none_when_absent():
    assert _resolved_context_from_session_context({}) is None
    assert _resolved_context_from_session_context(None) is None
    assert _resolved_context_from_session_context({"theclaw_resolved_context_v1": "not-a-dict"}) is None


def test_pending_confirmation_from_session_context_extracts_correctly():
    ctx = {
        "theclaw_pending_confirmation_v1": {
            "task_id": "task-123",
            "task_title": "Launch campaign",
            "status": "pending",
        }
    }
    result = _pending_confirmation_from_session_context(ctx)
    assert result is not None
    assert result["task_id"] == "task-123"
    assert result["task_title"] == "Launch campaign"


def test_pending_confirmation_from_session_context_returns_none_when_absent():
    assert _pending_confirmation_from_session_context({}) is None
    assert _pending_confirmation_from_session_context(None) is None
    assert _pending_confirmation_from_session_context({"theclaw_pending_confirmation_v1": "not-a-dict"}) is None


def test_pending_confirmation_preserves_clickup_list_id():
    """clickup_list_id must survive validation round-trip for direct-list execution."""
    ctx = {
        "theclaw_pending_confirmation_v1": {
            "task_id": "task-abc",
            "task_title": "Fix PPC",
            "clickup_list_id": "list-789",
            "status": "pending",
        }
    }
    result = _pending_confirmation_from_session_context(ctx)
    assert result is not None
    assert result["clickup_list_id"] == "list-789"


def test_coerce_runtime_context_updates_preserves_clickup_list_id():
    """clickup_list_id from LLM machine block must survive coerce round-trip."""
    updates = _coerce_runtime_context_updates(
        {
            "context_updates": {
                "theclaw_pending_confirmation_v1": {
                    "task_id": "task-abc",
                    "task_title": "Fix PPC",
                    "clickup_list_id": "list-789",
                    "status": "pending",
                }
            }
        }
    )
    assert updates["theclaw_pending_confirmation_v1"]["clickup_list_id"] == "list-789"
