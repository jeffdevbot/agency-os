"""Lane queue primitives for Slack DM runtime serialization.

The lane key is any stable per-actor identifier for a dispatch path
(for example ``slack_user_id`` in DM runtime).
"""

from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager
from typing import AsyncIterator

_SESSION_LOCKS: dict[tuple[int, str], asyncio.Lock] = {}
_REGISTRY_LOCK = threading.Lock()


def _get_or_create_session_lock(key: str) -> asyncio.Lock:
    key = (key or "").strip()
    if not key:
        raise ValueError("lane key is required")
    loop_id = id(asyncio.get_running_loop())
    registry_key = (loop_id, key)

    with _REGISTRY_LOCK:
        lock = _SESSION_LOCKS.get(registry_key)
        if lock is None:
            lock = asyncio.Lock()
            _SESSION_LOCKS[registry_key] = lock
        return lock


@asynccontextmanager
async def acquire_session_lane(key: str) -> AsyncIterator[None]:
    """Acquire the per-key lane lock for serialized same-actor handling."""
    lock = _get_or_create_session_lock(key)
    async with lock:
        yield
