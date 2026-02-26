"""Context provider registry for skill-scoped prompt context assembly."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Iterable

from .runtime_state import (
    draft_tasks_from_session_context,
    resolved_context_from_session_context,
    sanitize_context_field,
)

_logger = logging.getLogger(__name__)

_DEFAULT_CONTEXT_FETCH_TIMEOUT_SECONDS = 0.75


@dataclass(frozen=True)
class TheClawContextProvider:
    context_key: str
    fetcher: Callable[..., Awaitable[Any]]
    prompt_renderer: Callable[[Any], str]
    always_include: bool = False


def _normalize_context_keys(values: Iterable[str]) -> set[str]:
    return {str(value or "").strip().lower() for value in values if str(value or "").strip()}


def _get_context_fetch_timeout_seconds() -> float:
    raw = os.environ.get("THECLAW_CONTEXT_FETCH_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return _DEFAULT_CONTEXT_FETCH_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return _DEFAULT_CONTEXT_FETCH_TIMEOUT_SECONDS
    if value <= 0:
        return _DEFAULT_CONTEXT_FETCH_TIMEOUT_SECONDS
    return value


def _has_usable_blob(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return True


async def _fetch_resolved_context(*, session_context: dict[str, Any], **_: Any) -> dict[str, Any] | None:
    return resolved_context_from_session_context(session_context)


def _render_resolved_context(blob: Any) -> str:
    if not isinstance(blob, dict):
        return ""
    parts: list[str] = []
    if blob.get("client"):
        parts.append(f"Client: {sanitize_context_field(blob['client'])}")
    if blob.get("brand"):
        parts.append(f"Brand: {sanitize_context_field(blob['brand'])}")
    if blob.get("clickup_space"):
        parts.append(f"ClickUp Space: {sanitize_context_field(blob['clickup_space'])}")
    if blob.get("market_scope"):
        parts.append(f"Market: {sanitize_context_field(blob['market_scope'])}")
    if not parts:
        return ""
    return f"Active context: {', '.join(parts)}."


async def _fetch_draft_tasks(*, session_context: dict[str, Any], **_: Any) -> list[dict[str, Any]]:
    return draft_tasks_from_session_context(session_context)


def _render_draft_tasks(blob: Any) -> str:
    if not isinstance(blob, list) or not blob:
        return ""
    compact_tasks = []
    for task in blob[:25]:
        if not isinstance(task, dict):
            continue
        compact_tasks.append(
            {
                "id": sanitize_context_field(task.get("id")),
                "title": sanitize_context_field(task.get("title")),
                "source": sanitize_context_field(task.get("source")),
                "action": sanitize_context_field(task.get("action")),
                "asin_list": [
                    sanitize_context_field(value)
                    for value in (task.get("asin_list") or [])[:10]
                    if sanitize_context_field(value)
                ],
                "status": sanitize_context_field(task.get("status")),
            }
        )
    if not compact_tasks:
        return ""
    draft_tasks_json = json.dumps(compact_tasks, separators=(",", ":"), ensure_ascii=True)
    return (
        "Existing draft tasks context for ID preservation: "
        f"{draft_tasks_json}. Preserve existing IDs for matching tasks when updating drafts."
    )


_CONTEXT_PROVIDERS: dict[str, TheClawContextProvider] = {
    "resolved_context": TheClawContextProvider(
        context_key="resolved_context",
        fetcher=_fetch_resolved_context,
        prompt_renderer=_render_resolved_context,
        always_include=True,
    ),
    "draft_tasks": TheClawContextProvider(
        context_key="draft_tasks",
        fetcher=_fetch_draft_tasks,
        prompt_renderer=_render_draft_tasks,
        always_include=False,
    ),
}


def get_registered_context_keys() -> frozenset[str]:
    return frozenset(_CONTEXT_PROVIDERS.keys())


def get_always_context_keys() -> frozenset[str]:
    return frozenset(
        context_key
        for context_key, provider in _CONTEXT_PROVIDERS.items()
        if provider.always_include
    )


async def _fetch_with_timeout(
    *,
    provider: TheClawContextProvider,
    session_context: dict[str, Any],
    timeout_seconds: float,
) -> Any:
    try:
        return await asyncio.wait_for(
            provider.fetcher(session_context=session_context),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        _logger.warning("The Claw context fetch timed out for context '%s'", provider.context_key)
    except Exception as exc:  # noqa: BLE001
        _logger.warning("The Claw context fetch failed for context '%s': %s", provider.context_key, exc)
    return None


async def fetch_context_blobs(
    *,
    required_context_keys: Iterable[str],
    session_context: dict[str, Any],
) -> dict[str, Any]:
    normalized_required = _normalize_context_keys(required_context_keys)
    unknown = normalized_required.difference(_CONTEXT_PROVIDERS.keys())
    for context_key in sorted(unknown):
        _logger.warning("The Claw requested unknown context key '%s'", context_key)

    requested = {
        context_key
        for context_key, provider in _CONTEXT_PROVIDERS.items()
        if provider.always_include
    }
    requested.update(normalized_required.intersection(_CONTEXT_PROVIDERS.keys()))
    if not requested:
        return {}

    timeout_seconds = _get_context_fetch_timeout_seconds()
    tasks = [
        _fetch_with_timeout(
            provider=_CONTEXT_PROVIDERS[context_key],
            session_context=session_context,
            timeout_seconds=timeout_seconds,
        )
        for context_key in requested
    ]
    results = await asyncio.gather(*tasks)

    context_blobs: dict[str, Any] = {}
    for context_key, result in zip(requested, results, strict=True):
        if _has_usable_blob(result):
            context_blobs[context_key] = result
    return context_blobs


def render_context_blobs_for_prompt(
    *,
    context_blobs: dict[str, Any],
    required_context_keys: Iterable[str],
) -> str:
    normalized_required = _normalize_context_keys(required_context_keys)
    allowed = {
        context_key
        for context_key, provider in _CONTEXT_PROVIDERS.items()
        if provider.always_include
    }
    allowed.update(normalized_required)

    snippets: list[str] = []
    for context_key, provider in _CONTEXT_PROVIDERS.items():
        if context_key not in allowed:
            continue
        value = context_blobs.get(context_key)
        if not _has_usable_blob(value):
            continue
        snippet = provider.prompt_renderer(value)
        if snippet:
            snippets.append(snippet)
    return " ".join(snippets).strip()
