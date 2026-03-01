from __future__ import annotations

import pytest

from app.services.theclaw.slack_minimal_runtime import run_theclaw_minimal_dm_turn

from .theclaw_runtime_test_fakes import FakeSession, FakeSessionService, FakeSlackService


@pytest.mark.asyncio
async def test_run_theclaw_minimal_dm_turn_enriches_pending_confirmation_space_id(monkeypatch):
    """When LLM stages a pending confirmation with clickup_space, enrichment resolves clickup_space_id."""
    fake_slack = FakeSlackService()
    fake_session = FakeSession(
        context={
            "theclaw_draft_tasks_v1": [
                {"id": "task-50", "title": "Launch campaign", "status": "draft"},
            ],
        }
    )
    fake_session_service = FakeSessionService(session=fake_session)
    call_count = 0

    async def _fake_call_chat_completion(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {
                "content": '{"skill_id":"task_confirmation_to_create","confidence":0.95,"reason":"user wants to create"}',
                "tokens_in": 10,
                "tokens_out": 10,
                "tokens_total": 20,
                "model": "gpt-4o-mini",
                "duration_ms": 5,
            }
        return {
            "content": (
                "Ready to create 'Launch campaign'. Reply with exactly `yes` to proceed or `no` to cancel.\n\n"
                "---THECLAW_STATE_JSON---\n"
                '{"context_updates":{"theclaw_pending_confirmation_v1":{"task_id":"task-50","task_title":"Launch campaign","clickup_space":"Whoosh","status":"pending"}}}\n'
                "---END_THECLAW_STATE_JSON---"
            ),
            "tokens_in": 10,
            "tokens_out": 10,
            "tokens_total": 20,
            "model": "gpt-4o-mini",
            "duration_ms": 5,
        }

    class FakeEnrichClickUp:
        async def list_spaces(self, *, team_id=None):
            return [{"id": "sp-enriched-42", "name": "Whoosh"}]

        async def aclose(self):
            return None

    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)
    monkeypatch.setattr(
        "app.services.theclaw.clickup_execution.get_clickup_service",
        lambda: FakeEnrichClickUp(),
    )

    await run_theclaw_minimal_dm_turn(slack_user_id="U30", channel="D30", text="create task launch campaign for whoosh")

    assert len(fake_session_service.updated) == 1
    _, updates = fake_session_service.updated[0]
    pending = updates["theclaw_pending_confirmation_v1"]
    assert pending["clickup_space_id"] == "sp-enriched-42"
    assert pending["clickup_space"] == "Whoosh"
    assert pending["task_id"] == "task-50"
