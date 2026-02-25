from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services.agencyclaw.slack_debug_route_runtime import (
    handle_debug_chat_route_runtime,
)


class _FakeRequest:
    def __init__(self, *, headers: dict[str, str] | None = None, body: dict | None = None) -> None:
        self.headers = headers or {}
        self._body = body or {}

    async def json(self) -> dict:
        return self._body


@pytest.mark.asyncio
async def test_debug_route_runtime_disabled_flag_returns_404(monkeypatch):
    monkeypatch.setenv("AGENCYCLAW_DEBUG_CHAT_ENABLED", "false")
    request = _FakeRequest(headers={"X-Debug-Token": "token"}, body={"text": "hello"})

    with pytest.raises(HTTPException) as exc:
        await handle_debug_chat_route_runtime(request=request, deps=MagicMock())

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_debug_route_runtime_bad_token_returns_401(monkeypatch):
    monkeypatch.setenv("AGENCYCLAW_DEBUG_CHAT_ENABLED", "true")
    monkeypatch.setenv("AGENCYCLAW_DEBUG_CHAT_TOKEN", "expected")
    request = _FakeRequest(headers={"X-Debug-Token": "wrong"}, body={"text": "hello"})

    with pytest.raises(HTTPException) as exc:
        await handle_debug_chat_route_runtime(request=request, deps=MagicMock())

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_debug_route_runtime_empty_text_returns_400(monkeypatch):
    monkeypatch.setenv("AGENCYCLAW_DEBUG_CHAT_ENABLED", "true")
    monkeypatch.setenv("AGENCYCLAW_DEBUG_CHAT_TOKEN", "expected")
    request = _FakeRequest(headers={"X-Debug-Token": "expected"}, body={"text": "   "})

    with pytest.raises(HTTPException) as exc:
        await handle_debug_chat_route_runtime(request=request, deps=MagicMock())

    assert exc.value.status_code == 400
    assert exc.value.detail == "text is required"


@pytest.mark.asyncio
async def test_debug_route_runtime_happy_path_calls_debug_chat(monkeypatch):
    monkeypatch.setenv("AGENCYCLAW_DEBUG_CHAT_ENABLED", "true")
    monkeypatch.setenv("AGENCYCLAW_DEBUG_CHAT_TOKEN", "expected")
    monkeypatch.setenv("AGENCYCLAW_DEBUG_CHAT_USER_ID", "U_SERVER")
    monkeypatch.setenv("AGENCYCLAW_DEBUG_CHAT_ALLOW_MUTATIONS", "true")

    called: dict = {}

    async def _fake_handle_debug_chat(**kwargs):
        called.update(kwargs)
        return {"messages": [{"text": "ok"}], "user_id": kwargs.get("user_id")}

    monkeypatch.setattr(
        "app.services.agencyclaw.slack_debug_route_runtime.handle_debug_chat",
        _fake_handle_debug_chat,
    )

    deps = SimpleNamespace()
    request = _FakeRequest(
        headers={"X-Debug-Token": "expected"},
        body={"text": "hello world", "user_id": "U_CLIENT"},
    )
    result = await handle_debug_chat_route_runtime(request=request, deps=deps)

    assert called["text"] == "hello world"
    assert called["deps"] is deps
    assert called["user_id"] == "U_SERVER"
    assert called["allow_mutations"] is True
    assert result == {"messages": [{"text": "ok"}], "user_id": "U_SERVER"}


@pytest.mark.asyncio
async def test_debug_route_runtime_reset_session_calls_session_service(monkeypatch):
    monkeypatch.setenv("AGENCYCLAW_DEBUG_CHAT_ENABLED", "true")
    monkeypatch.setenv("AGENCYCLAW_DEBUG_CHAT_TOKEN", "expected")

    called: dict = {}

    async def _fake_handle_debug_chat(**kwargs):
        called.update(kwargs)
        return {"messages": [{"text": "ok"}], "user_id": kwargs.get("user_id")}

    monkeypatch.setattr(
        "app.services.agencyclaw.slack_debug_route_runtime.handle_debug_chat",
        _fake_handle_debug_chat,
    )

    class _FakeSessionService:
        def __init__(self) -> None:
            self.cleared: list[str] = []

        def clear_active_session(self, slack_user_id: str) -> None:
            self.cleared.append(slack_user_id)

    session_service = _FakeSessionService()
    deps = SimpleNamespace(get_session_service_fn=lambda: session_service)
    request = _FakeRequest(
        headers={"X-Debug-Token": "expected"},
        body={"text": "hello world", "user_id": "U_CLIENT", "reset_session": True},
    )

    result = await handle_debug_chat_route_runtime(request=request, deps=deps)

    assert session_service.cleared == ["U_CLIENT"]
    assert called["user_id"] == "U_CLIENT"
    assert result == {"messages": [{"text": "ok"}], "user_id": "U_CLIENT"}
