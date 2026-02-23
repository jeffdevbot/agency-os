"""Per-session lane queue primitives for Slack DM runtime serialization."""

from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager
from typing import AsyncIterator

_SESSION_LOCKS: dict[str, asyncio.Lock] = {}
_REGISTRY_LOCK = threading.Lock()


def _get_or_create_session_lock(session_id: str) -> asyncio.Lock:
    key = (session_id or "").strip()
    if not key:
        raise ValueError("session_id is required")

    with _REGISTRY_LOCK:
        lock = _SESSION_LOCKS.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _SESSION_LOCKS[key] = lock
        return lock


@asynccontextmanager
async def acquire_session_lane(session_id: str) -> AsyncIterator[None]:
    """Acquire the per-session lane lock for serialized same-session handling."""
    lock = _get_or_create_session_lock(session_id)
    async with lock:
        yield
