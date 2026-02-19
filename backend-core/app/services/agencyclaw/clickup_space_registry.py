"""ClickUp Space Registry service for AgencyClaw (C6A).

Provides CRUD + sync operations for the ``clickup_space_registry`` table.
All functions are **synchronous** (Supabase Python client is sync);
callers should wrap in ``asyncio.to_thread`` when calling from async code.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_VALID_CLASSIFICATIONS = ("brand_scoped", "shared_service", "unknown")


def sync_clickup_spaces(
    db: Any,
    spaces: list[dict[str, str]],
) -> dict[str, Any]:
    """Upsert spaces from ClickUp API into the registry.

    Only updates ``name``, ``team_id``, ``last_seen_at``, ``last_synced_at``.
    Preserves manual ``classification``, ``brand_id``, and ``active`` fields.
    """
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for s in spaces:
        rows.append({
            "space_id": str(s["id"]),
            "team_id": str(s.get("team_id", "")),
            "name": str(s.get("name", "")),
            "last_seen_at": now,
            "last_synced_at": now,
        })

    if not rows:
        return {"synced": 0, "spaces": []}

    response = (
        db.table("clickup_space_registry")
        .upsert(rows, on_conflict="space_id")
        .execute()
    )
    upserted = response.data if isinstance(response.data, list) else []
    return {"synced": len(upserted), "spaces": upserted}


def list_clickup_spaces(
    db: Any,
    *,
    classification: str | None = None,
    include_inactive: bool = False,
) -> list[dict[str, Any]]:
    """List spaces from the registry with optional filters."""
    query = db.table("clickup_space_registry").select("*")
    if classification:
        query = query.eq("classification", classification)
    if not include_inactive:
        query = query.eq("active", True)
    query = query.order("name")
    response = query.execute()
    return response.data if isinstance(response.data, list) else []


def classify_clickup_space(
    db: Any,
    space_id: str,
    classification: str,
) -> dict[str, Any]:
    """Update the classification of a registered space."""
    if classification not in _VALID_CLASSIFICATIONS:
        raise ValueError(
            f"Invalid classification {classification!r}. "
            f"Must be one of: {', '.join(_VALID_CLASSIFICATIONS)}"
        )
    response = (
        db.table("clickup_space_registry")
        .update({"classification": classification})
        .eq("space_id", space_id)
        .execute()
    )
    rows = response.data if isinstance(response.data, list) else []
    if not rows:
        raise ValueError(f"Space {space_id!r} not found in registry")
    return rows[0]


def map_clickup_space_to_brand(
    db: Any,
    space_id: str,
    brand_id: str | None,
) -> dict[str, Any]:
    """Map (or unmap) a space to a brand. Pass ``None`` to unmap."""
    response = (
        db.table("clickup_space_registry")
        .update({"brand_id": brand_id})
        .eq("space_id", space_id)
        .execute()
    )
    rows = response.data if isinstance(response.data, list) else []
    if not rows:
        raise ValueError(f"Space {space_id!r} not found in registry")
    return rows[0]
