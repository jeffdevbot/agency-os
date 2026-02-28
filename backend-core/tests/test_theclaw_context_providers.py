from __future__ import annotations

import asyncio

import pytest

import app.services.theclaw.context_providers as context_providers


def test_get_registered_context_keys_includes_defaults():
    keys = context_providers.get_registered_context_keys()
    assert "resolved_context" in keys
    assert "draft_tasks" in keys
    assert "pending_confirmation" in keys


@pytest.mark.asyncio
async def test_fetch_context_blobs_includes_always_resolved_context():
    blobs = await context_providers.fetch_context_blobs(
        required_context_keys=set(),
        session_context={
            "theclaw_resolved_context_v1": {
                "client": "Whoosh",
                "brand": "Whoosh",
                "clickup_space": "Whoosh",
                "market_scope": "CA",
            }
        },
    )
    assert "resolved_context" in blobs
    assert blobs["resolved_context"]["client"] == "Whoosh"


@pytest.mark.asyncio
async def test_fetch_context_blobs_includes_requested_draft_tasks():
    blobs = await context_providers.fetch_context_blobs(
        required_context_keys={"draft_tasks"},
        session_context={
            "theclaw_draft_tasks_v1": [
                {"id": "task-1", "title": "Launch campaign", "source": "meeting_notes", "status": "draft"}
            ]
        },
    )
    assert "draft_tasks" in blobs
    assert blobs["draft_tasks"][0]["id"] == "task-1"


@pytest.mark.asyncio
async def test_fetch_context_blobs_includes_requested_pending_confirmation():
    blobs = await context_providers.fetch_context_blobs(
        required_context_keys={"pending_confirmation"},
        session_context={
            "theclaw_pending_confirmation_v1": {
                "task_id": "task-1",
                "task_title": "Launch campaign",
                "status": "pending",
            }
        },
    )
    assert "pending_confirmation" in blobs
    assert blobs["pending_confirmation"]["task_id"] == "task-1"


@pytest.mark.asyncio
async def test_fetch_context_blobs_unknown_context_key_logs_warning(caplog):
    caplog.set_level("WARNING")
    blobs = await context_providers.fetch_context_blobs(
        required_context_keys={"not_real"},
        session_context={},
    )
    assert blobs == {}
    assert "unknown context key 'not_real'" in caplog.text


@pytest.mark.asyncio
async def test_fetch_context_blobs_timeout_is_fail_open(monkeypatch, caplog):
    async def _slow_fetcher(**kwargs):  # noqa: ARG001
        await asyncio.sleep(0.05)
        return {"too": "slow"}

    slow_provider = context_providers.TheClawContextProvider(
        context_key="slow_test",
        fetcher=_slow_fetcher,
        prompt_renderer=lambda _: "",
        always_include=False,
    )
    monkeypatch.setitem(context_providers._CONTEXT_PROVIDERS, "slow_test", slow_provider)
    monkeypatch.setenv("THECLAW_CONTEXT_FETCH_TIMEOUT_SECONDS", "0.001")
    caplog.set_level("WARNING")

    blobs = await context_providers.fetch_context_blobs(
        required_context_keys={"slow_test"},
        session_context={},
    )
    assert blobs == {}
    assert "context fetch timed out for context 'slow_test'" in caplog.text


def test_render_context_blobs_for_prompt_respects_required_keys():
    prompt = context_providers.render_context_blobs_for_prompt(
        context_blobs={
            "resolved_context": {"client": "Whoosh", "market_scope": "CA"},
            "draft_tasks": [{"id": "task-1", "title": "Launch campaign", "source": "meeting_notes"}],
        },
        required_context_keys=set(),
    )
    assert "Active context:" in prompt
    assert "Existing draft tasks context for ID preservation" not in prompt

    prompt_with_drafts = context_providers.render_context_blobs_for_prompt(
        context_blobs={
            "resolved_context": {"client": "Whoosh", "market_scope": "CA"},
            "draft_tasks": [{"id": "task-1", "title": "Launch campaign", "source": "meeting_notes"}],
        },
        required_context_keys={"draft_tasks"},
    )
    assert "Existing draft tasks context for ID preservation" in prompt_with_drafts
    assert '"index":1' in prompt_with_drafts
