"""Async OpenAI chat completion adapter using httpx.

Port of lib/composer/ai/openai.ts — same env vars, same fallback logic.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, TypedDict

import httpx

_OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
_DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIError(Exception):
    pass


class OpenAIConfigurationError(OpenAIError):
    pass


class ChatMessage(TypedDict):
    role: str  # "system" | "user" | "assistant"
    content: str


class ChatCompletionResult(TypedDict):
    content: str
    tokens_in: int
    tokens_out: int
    tokens_total: int
    model: str
    duration_ms: int


def _get_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise OpenAIConfigurationError("OPENAI_API_KEY environment variable is not set")
    return key


def _get_default_model() -> str:
    return os.environ.get("OPENAI_MODEL_PRIMARY", "").strip() or _DEFAULT_MODEL


def _get_fallback_model() -> str | None:
    val = os.environ.get("OPENAI_MODEL_FALLBACK", "").strip()
    return val or None


async def _call_openai_http(
    messages: list[ChatMessage],
    *,
    model: str,
    temperature: float,
    max_tokens: int | None = None,
) -> ChatCompletionResult:
    api_key = _get_api_key()
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    start_ms = int(time.time() * 1000)

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

    duration_ms = int(time.time() * 1000) - start_ms

    if response.status_code != 200:
        body = response.text[:500]
        raise OpenAIError(f"OpenAI API error ({response.status_code}): {body}")

    data = response.json()
    choices = data.get("choices") or []
    if not choices:
        raise OpenAIError("No choices in OpenAI response")
    content = (choices[0].get("message") or {}).get("content")
    if not content:
        raise OpenAIError("No content in OpenAI response")

    usage = data.get("usage") or {}
    tokens_in = usage.get("prompt_tokens", 0)
    tokens_out = usage.get("completion_tokens", 0)

    return ChatCompletionResult(
        content=content,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        tokens_total=usage.get("total_tokens", tokens_in + tokens_out),
        model=data.get("model", model),
        duration_ms=duration_ms,
    )


async def call_chat_completion(
    messages: list[ChatMessage],
    *,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    model: str | None = None,
) -> ChatCompletionResult:
    """Call OpenAI chat completion with automatic primary→fallback model retry."""
    resolved_model = model or _get_default_model()
    try:
        return await _call_openai_http(
            messages, model=resolved_model, temperature=temperature, max_tokens=max_tokens
        )
    except OpenAIError:
        # If caller specified an explicit model, don't retry with fallback.
        if model and model != _get_default_model():
            raise
        fallback = _get_fallback_model()
        if fallback and fallback != resolved_model:
            return await _call_openai_http(
                messages, model=fallback, temperature=temperature, max_tokens=max_tokens
            )
        raise


_JSON_FENCE_RE = re.compile(r"```json\s*([\s\S]*?)\s*```")


def parse_json_response(content: str) -> dict[str, Any]:
    """Extract JSON from LLM output, stripping markdown fences if present."""
    m = _JSON_FENCE_RE.search(content)
    raw = m.group(1) if m else content.strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OpenAIError(f"Failed to parse JSON from OpenAI response: {exc}") from exc
    if not isinstance(result, dict):
        raise OpenAIError("OpenAI response JSON is not an object")
    return result
