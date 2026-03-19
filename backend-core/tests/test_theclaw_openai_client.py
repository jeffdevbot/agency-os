from __future__ import annotations

import logging

import pytest

from app.services.theclaw.openai_client import OpenAIError, _call_openai_http, call_chat_completion


@pytest.mark.asyncio
async def test_call_chat_completion_logs_when_falling_back(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger="app.services.theclaw.openai_client")

    responses = [
        OpenAIError("model_not_found"),
        {
            "content": "ok",
            "tokens_in": 10,
            "tokens_out": 5,
            "tokens_total": 15,
            "model": "gpt-4o-2024-08-06",
            "duration_ms": 5,
            "tool_calls": None,
        },
    ]
    call_models: list[str] = []

    async def _fake_call_openai_http(**kwargs):
        call_models.append(kwargs["model"])
        next_item = responses.pop(0)
        if isinstance(next_item, Exception):
            raise next_item
        return next_item

    monkeypatch.setattr(
        "app.services.theclaw.openai_client._call_openai_http",
        _fake_call_openai_http,
    )
    monkeypatch.setattr(
        "app.services.theclaw.openai_client._get_primary_model",
        lambda: "gpt-5-mini",
    )
    monkeypatch.setattr(
        "app.services.theclaw.openai_client._get_fallback_model",
        lambda: "gpt-4o",
    )

    result = await call_chat_completion(
        messages=[{"role": "user", "content": "hello"}],
    )

    assert result["model"] == "gpt-4o-2024-08-06"
    assert call_models == ["gpt-5-mini", "gpt-4o"]
    assert (
        "The Claw OpenAI primary model failed; retrying fallback | primary_model=gpt-5-mini fallback_model=gpt-4o error=model_not_found"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_call_openai_http_uses_max_completion_tokens_for_gpt5(monkeypatch):
    captured_payload: dict[str, object] = {}

    class _FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "model": "gpt-5-mini",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            }

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            _ = (args, kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json, headers):
            _ = (url, headers)
            captured_payload.update(json)
            return _FakeResponse()

    monkeypatch.setattr("app.services.theclaw.openai_client._get_api_key", lambda: "test-key")
    monkeypatch.setattr("app.services.theclaw.openai_client.httpx.AsyncClient", _FakeAsyncClient)

    result = await _call_openai_http(
        messages=[{"role": "user", "content": "hello"}],
        model="gpt-5-mini",
        temperature=0.2,
        max_tokens=321,
    )

    assert result["model"] == "gpt-5-mini"
    assert captured_payload["max_completion_tokens"] == 321
    assert "max_tokens" not in captured_payload
    assert "temperature" not in captured_payload


@pytest.mark.asyncio
async def test_call_openai_http_uses_max_tokens_for_non_gpt5(monkeypatch):
    captured_payload: dict[str, object] = {}

    class _FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "model": "gpt-4o",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            }

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            _ = (args, kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json, headers):
            _ = (url, headers)
            captured_payload.update(json)
            return _FakeResponse()

    monkeypatch.setattr("app.services.theclaw.openai_client._get_api_key", lambda: "test-key")
    monkeypatch.setattr("app.services.theclaw.openai_client.httpx.AsyncClient", _FakeAsyncClient)

    result = await _call_openai_http(
        messages=[{"role": "user", "content": "hello"}],
        model="gpt-4o",
        temperature=0.2,
        max_tokens=123,
    )

    assert result["model"] == "gpt-4o"
    assert captured_payload["max_tokens"] == 123
    assert "max_completion_tokens" not in captured_payload
    assert captured_payload["temperature"] == 0.2


@pytest.mark.asyncio
async def test_call_openai_http_extracts_text_from_content_parts(monkeypatch):
    class _FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "model": "gpt-5-mini",
                "choices": [{
                    "message": {
                        "content": [
                            {"type": "text", "text": "Hello "},
                            {"type": "text", "text": {"value": "world"}},
                        ]
                    },
                    "finish_reason": "stop",
                }],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            }

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            _ = (args, kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json, headers):
            _ = (url, json, headers)
            return _FakeResponse()

    monkeypatch.setattr("app.services.theclaw.openai_client._get_api_key", lambda: "test-key")
    monkeypatch.setattr("app.services.theclaw.openai_client.httpx.AsyncClient", _FakeAsyncClient)

    result = await _call_openai_http(
        messages=[{"role": "user", "content": "hello"}],
        model="gpt-5-mini",
        temperature=0.2,
        max_tokens=321,
    )

    assert result["content"] == "Hello world"


@pytest.mark.asyncio
async def test_call_openai_http_error_includes_finish_reason_and_message_keys(monkeypatch):
    class _FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "model": "gpt-5-mini",
                "choices": [{
                    "message": {"role": "assistant"},
                    "finish_reason": "stop",
                }],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            }

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            _ = (args, kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json, headers):
            _ = (url, json, headers)
            return _FakeResponse()

    monkeypatch.setattr("app.services.theclaw.openai_client._get_api_key", lambda: "test-key")
    monkeypatch.setattr("app.services.theclaw.openai_client.httpx.AsyncClient", _FakeAsyncClient)

    with pytest.raises(OpenAIError, match="finish_reason=stop"):
        await _call_openai_http(
            messages=[{"role": "user", "content": "hello"}],
            model="gpt-5-mini",
            temperature=0.2,
            max_tokens=321,
        )
