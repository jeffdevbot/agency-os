from __future__ import annotations

from starlette.background import BackgroundTasks

import pytest
from fastapi import HTTPException

from app.services.agencyclaw.slack_http_route_runtime import (
    handle_slack_events_http_runtime,
    handle_slack_interactions_http_runtime,
)


class _FakeRequest:
    def __init__(self, *, headers: dict[str, str] | None = None, body: bytes = b"{}") -> None:
        self.headers = headers or {}
        self._body = body

    async def body(self) -> bytes:
        return self._body


@pytest.mark.asyncio
async def test_slack_events_runtime_requires_signing_secret(monkeypatch):
    monkeypatch.setattr(
        "app.services.agencyclaw.slack_http_route_runtime.get_slack_signing_secret",
        lambda: "",
    )
    request = _FakeRequest()
    background = BackgroundTasks()

    with pytest.raises(HTTPException) as exc:
        await handle_slack_events_http_runtime(
            request=request,
            background_tasks=background,
            handle_dm_event_fn=lambda **kwargs: None,  # pragma: no cover
        )

    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_slack_events_runtime_retry_is_noop(monkeypatch):
    monkeypatch.setattr(
        "app.services.agencyclaw.slack_http_route_runtime.get_slack_signing_secret",
        lambda: "secret",
    )
    monkeypatch.setattr(
        "app.services.agencyclaw.slack_http_route_runtime.verify_request_or_401",
        lambda **kwargs: None,
    )
    request = _FakeRequest(headers={"X-Slack-Retry-Num": "1"})
    background = BackgroundTasks()

    result = await handle_slack_events_http_runtime(
        request=request,
        background_tasks=background,
        handle_dm_event_fn=lambda **kwargs: None,  # pragma: no cover
    )

    assert result == {"ok": True}
    assert len(background.tasks) == 0


@pytest.mark.asyncio
async def test_slack_events_runtime_url_verification(monkeypatch):
    monkeypatch.setattr(
        "app.services.agencyclaw.slack_http_route_runtime.get_slack_signing_secret",
        lambda: "secret",
    )
    monkeypatch.setattr(
        "app.services.agencyclaw.slack_http_route_runtime.verify_request_or_401",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.agencyclaw.slack_http_route_runtime.parse_json_payload",
        lambda _body: {"type": "url_verification", "challenge": "abc123"},
    )
    request = _FakeRequest()

    result = await handle_slack_events_http_runtime(
        request=request,
        background_tasks=BackgroundTasks(),
        handle_dm_event_fn=lambda **kwargs: None,  # pragma: no cover
    )

    assert result == {"challenge": "abc123"}


@pytest.mark.asyncio
async def test_slack_events_runtime_schedules_valid_dm(monkeypatch):
    monkeypatch.setattr(
        "app.services.agencyclaw.slack_http_route_runtime.get_slack_signing_secret",
        lambda: "secret",
    )
    monkeypatch.setattr(
        "app.services.agencyclaw.slack_http_route_runtime.verify_request_or_401",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.agencyclaw.slack_http_route_runtime.parse_json_payload",
        lambda _body: {
            "type": "event_callback",
            "event": {
                "type": "message",
                "channel_type": "im",
                "channel": "D123",
                "text": "hello",
                "user": "U123",
            },
        },
    )
    background = BackgroundTasks()

    async def _fake_dm_handler(**kwargs):
        return None

    result = await handle_slack_events_http_runtime(
        request=_FakeRequest(),
        background_tasks=background,
        handle_dm_event_fn=_fake_dm_handler,
    )

    assert result == {"ok": True}
    assert len(background.tasks) == 1
    task = background.tasks[0]
    assert task.func is _fake_dm_handler
    assert task.kwargs == {"slack_user_id": "U123", "channel": "D123", "text": "hello"}


@pytest.mark.asyncio
async def test_slack_interactions_runtime_schedules_interaction(monkeypatch):
    monkeypatch.setattr(
        "app.services.agencyclaw.slack_http_route_runtime.get_slack_signing_secret",
        lambda: "secret",
    )
    monkeypatch.setattr(
        "app.services.agencyclaw.slack_http_route_runtime.verify_request_or_401",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.agencyclaw.slack_http_route_runtime.parse_interaction_payload",
        lambda _body: {"type": "block_actions", "user": {"id": "U123"}},
    )
    background = BackgroundTasks()

    async def _fake_interaction_handler(payload):
        _ = payload
        return None

    result = await handle_slack_interactions_http_runtime(
        request=_FakeRequest(),
        background_tasks=background,
        handle_interaction_fn=_fake_interaction_handler,
    )

    assert result == {"ok": True}
    assert len(background.tasks) == 1
    task = background.tasks[0]
    assert task.func is _fake_interaction_handler
    assert task.args == ({"type": "block_actions", "user": {"id": "U123"}},)
