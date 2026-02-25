from __future__ import annotations

import pytest

from app.api.routes.slack import _handle_dm_event, _handle_interaction


@pytest.mark.asyncio
async def test_handle_dm_event_dispatches_to_theclaw_runtime(monkeypatch):
    called: dict[str, object] = {}

    async def _fake_minimal(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr("app.api.routes.slack.run_theclaw_minimal_dm_turn", _fake_minimal)

    await _handle_dm_event(slack_user_id="U123", channel="D123", text="hello")

    assert called == {"slack_user_id": "U123", "channel": "D123", "text": "hello"}


@pytest.mark.asyncio
async def test_handle_interaction_dispatches_to_theclaw_runtime(monkeypatch):
    called: dict[str, object] = {}

    async def _fake_interaction(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr("app.api.routes.slack.handle_theclaw_minimal_interaction", _fake_interaction)

    payload = {"type": "block_actions"}
    await _handle_interaction(payload)

    assert called == {"payload": payload}
