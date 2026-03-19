"""Minimal OpenAI chat adapter for The Claw reboot path."""

from __future__ import annotations

import os
import time
from typing import Any, TypedDict

import httpx
import logging

_OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
_DEFAULT_MODEL = "gpt-4o-mini"
_logger = logging.getLogger(__name__)


class OpenAIError(Exception):
    pass


class OpenAIConfigurationError(OpenAIError):
    pass


class ChatMessage(TypedDict):
    role: str
    content: str


class ChatCompletionResult(TypedDict):
    content: str
    tokens_in: int
    tokens_out: int
    tokens_total: int
    model: str
    duration_ms: int
    tool_calls: list[dict[str, Any]] | None


def _get_api_key() -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise OpenAIConfigurationError("OPENAI_API_KEY environment variable is not set")
    return api_key


def _get_primary_model() -> str:
    return os.environ.get("OPENAI_MODEL_PRIMARY", "").strip() or _DEFAULT_MODEL


def _get_fallback_model() -> str | None:
    model = os.environ.get("OPENAI_MODEL_FALLBACK", "").strip()
    return model or None


async def _call_openai_http(
    *,
    messages: list[ChatMessage],
    model: str,
    temperature: float,
    max_tokens: int | None,
    tools: list[dict[str, Any]] | None = None,
    response_format: dict[str, Any] | None = None,
) -> ChatCompletionResult:
    api_key = _get_api_key()
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if tools:
        payload["tools"] = tools
    if response_format:
        payload["response_format"] = response_format

    started_ms = int(time.time() * 1000)
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        try:
            response = await client.post(
                _OPENAI_API_URL,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise OpenAIError(f"OpenAI request failed: {exc}") from exc

    duration_ms = int(time.time() * 1000) - started_ms
    if response.status_code != 200:
        raise OpenAIError(f"OpenAI API error ({response.status_code}): {response.text[:500]}")

    data = response.json()
    choices = data.get("choices") or []
    if not choices:
        raise OpenAIError("No choices in OpenAI response")

    message = choices[0].get("message") if isinstance(choices[0], dict) else {}
    content = message.get("content") if isinstance(message, dict) else None
    raw_tool_calls = message.get("tool_calls") if isinstance(message, dict) else None

    if not content and not raw_tool_calls:
        raise OpenAIError("No content or tool_calls in OpenAI response")

    usage = data.get("usage") or {}
    tokens_in = int(usage.get("prompt_tokens") or 0)
    tokens_out = int(usage.get("completion_tokens") or 0)
    tokens_total = int(usage.get("total_tokens") or (tokens_in + tokens_out))

    return ChatCompletionResult(
        content=str(content or ""),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        tokens_total=tokens_total,
        model=str(data.get("model") or model),
        duration_ms=duration_ms,
        tool_calls=raw_tool_calls,
    )


async def call_chat_completion(
    *,
    messages: list[ChatMessage],
    temperature: float = 0.2,
    max_tokens: int | None = None,
    model: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    response_format: dict[str, Any] | None = None,
) -> ChatCompletionResult:
    primary_model = model or _get_primary_model()
    try:
        return await _call_openai_http(
            messages=messages,
            model=primary_model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            response_format=response_format,
        )
    except OpenAIError as exc:
        if model:
            raise
        fallback_model = _get_fallback_model()
        if fallback_model and fallback_model != primary_model:
            _logger.warning(
                "The Claw OpenAI primary model failed; retrying fallback | primary_model=%s fallback_model=%s error=%s",
                primary_model,
                fallback_model,
                exc,
            )
            return await _call_openai_http(
                messages=messages,
                model=fallback_model,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                response_format=response_format,
            )
        raise
