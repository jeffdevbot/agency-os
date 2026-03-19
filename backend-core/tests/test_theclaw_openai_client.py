from __future__ import annotations

import logging

import pytest

from app.services.theclaw.openai_client import OpenAIError, call_chat_completion


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
