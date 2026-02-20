"""C12B: Brand CRUD mutation service for AgencyClaw.

Provides deterministic create + update functions for the ``brands`` table
via Slack chat.

All functions are **synchronous** (Supabase sync client).
Callers should wrap in ``asyncio.to_thread`` from async code.
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class BrandCreateResult(TypedDict):
    status: str  # "ok" | "duplicate" | "error"
    brand_id: str | None
    message: str


class BrandUpdateResult(TypedDict):
    status: str  # "ok" | "not_found" | "ambiguous" | "no_changes" | "error"
    message: str
    fields_updated: list[str]


class ResolveBrandResult(TypedDict):
    status: str  # "ok" | "not_found" | "ambiguous"
    brand_id: str | None
    brand_name: str | None
    candidates: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Resolve helpers
# ---------------------------------------------------------------------------


def resolve_brand_for_mutation(
    db: Any,
    client_id: str | None,
    brand_query: str,
) -> ResolveBrandResult:
    """Resolve a brand name, optionally scoped to a client.

    Returns ok for single match, ambiguous for multiple, not_found for zero.
    """
    q = (brand_query or "").strip().lower()
    if not q:
        return ResolveBrandResult(
            status="not_found", brand_id=None, brand_name=None, candidates=[],
        )

    try:
        query = (
            db.table("brands")
            .select("id,name,client_id")
            .order("name", desc=False)
            .limit(50)
        )
        if client_id:
            query = query.eq("client_id", client_id)
        response = query.execute()
        rows = response.data if isinstance(response.data, list) else []
    except Exception:  # noqa: BLE001
        logger.warning("Failed to fetch brands for mutation resolution", exc_info=True)
        return ResolveBrandResult(
            status="not_found", brand_id=None, brand_name=None, candidates=[],
        )

    matches: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").lower()
        if name == q or q in name:
            matches.append({"id": str(row["id"]), "name": str(row.get("name") or "")})

    if not matches:
        return ResolveBrandResult(
            status="not_found", brand_id=None, brand_name=None, candidates=[],
        )
    if len(matches) == 1:
        return ResolveBrandResult(
            status="ok",
            brand_id=matches[0]["id"],
            brand_name=matches[0]["name"],
            candidates=[],
        )

    # Check for exact match among multiple substring matches
    exact = [m for m in matches if m["name"].lower() == q]
    if len(exact) == 1:
        return ResolveBrandResult(
            status="ok",
            brand_id=exact[0]["id"],
            brand_name=exact[0]["name"],
            candidates=[],
        )

    return ResolveBrandResult(
        status="ambiguous", brand_id=None, brand_name=None, candidates=matches[:10],
    )


def _parse_marketplaces(raw: str) -> list[str]:
    """Parse comma-separated marketplace codes into a clean list."""
    if not raw:
        return []
    return [m.strip().upper() for m in raw.split(",") if m.strip()]


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def create_brand(
    db: Any,
    *,
    client_id: str,
    brand_name: str,
    clickup_space_id: str | None = None,
    clickup_list_id: str | None = None,
    marketplaces: str | None = None,
) -> BrandCreateResult:
    """Create a new brand under a client.

    Checks for duplicate brand name (case-insensitive) within the same client
    before inserting.
    """
    name = (brand_name or "").strip()
    if not name:
        return BrandCreateResult(
            status="error", brand_id=None, message="Brand name cannot be empty.",
        )

    try:
        # Check for existing brand with same name under this client
        existing = (
            db.table("brands")
            .select("id,name")
            .eq("client_id", client_id)
            .limit(200)
            .execute()
        )
        existing_rows = existing.data if isinstance(existing.data, list) else []
        for row in existing_rows:
            if isinstance(row, dict) and str(row.get("name") or "").lower() == name.lower():
                return BrandCreateResult(
                    status="duplicate",
                    brand_id=str(row["id"]),
                    message=f"A brand named *{row.get('name')}* already exists for this client.",
                )

        payload: dict[str, Any] = {
            "client_id": client_id,
            "name": name,
        }
        if clickup_space_id:
            payload["clickup_space_id"] = clickup_space_id
        if clickup_list_id:
            payload["clickup_list_id"] = clickup_list_id
        if marketplaces:
            payload["amazon_marketplaces"] = _parse_marketplaces(marketplaces)

        resp = db.table("brands").insert(payload).execute()
        inserted = resp.data if isinstance(resp.data, list) else []
        new_id = str(inserted[0]["id"]) if inserted and isinstance(inserted[0], dict) else None

        return BrandCreateResult(
            status="ok",
            brand_id=new_id,
            message=f"Brand *{name}* created.",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to create brand", exc_info=True)
        return BrandCreateResult(
            status="error", brand_id=None, message=f"Failed to create brand: {exc}",
        )


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def update_brand(
    db: Any,
    *,
    brand_id: str,
    new_brand_name: str | None = None,
    clickup_space_id: str | None = None,
    clickup_list_id: str | None = None,
    marketplaces: str | None = None,
) -> BrandUpdateResult:
    """Partial-update a brand's fields.

    Only provided (non-None) fields are patched. Returns the list of updated fields.
    """
    patch: dict[str, Any] = {}
    fields: list[str] = []

    if new_brand_name and new_brand_name.strip():
        patch["name"] = new_brand_name.strip()
        fields.append("name")
    if clickup_space_id is not None:
        patch["clickup_space_id"] = clickup_space_id or None
        fields.append("clickup_space_id")
    if clickup_list_id is not None:
        patch["clickup_list_id"] = clickup_list_id or None
        fields.append("clickup_list_id")
    if marketplaces is not None:
        patch["amazon_marketplaces"] = _parse_marketplaces(marketplaces)
        fields.append("amazon_marketplaces")

    if not patch:
        return BrandUpdateResult(
            status="no_changes", message="No fields to update.", fields_updated=[],
        )

    try:
        db.table("brands").update(patch).eq("id", brand_id).execute()
        return BrandUpdateResult(
            status="ok",
            message=f"Updated {', '.join(fields)}.",
            fields_updated=fields,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to update brand id=%s", brand_id, exc_info=True)
        return BrandUpdateResult(
            status="error",
            message=f"Failed to update brand: {exc}",
            fields_updated=[],
        )


# ---------------------------------------------------------------------------
# Slack formatters
# ---------------------------------------------------------------------------


def format_brand_create_result(
    result: BrandCreateResult,
    brand_name: str,
    client_name: str,
) -> str:
    if result["status"] == "ok":
        return f"Created brand *{brand_name}* under *{client_name}*."
    if result["status"] == "duplicate":
        return result["message"]
    if result["status"] == "error":
        return f"Failed to create brand: {result['message']}"
    return result["message"]


def format_brand_update_result(
    result: BrandUpdateResult,
    brand_name: str,
) -> str:
    if result["status"] == "ok":
        return f"Updated *{brand_name}*: {result['message']}"
    if result["status"] == "no_changes":
        return f"No changes to apply for *{brand_name}*."
    if result["status"] == "error":
        return f"Failed to update brand: {result['message']}"
    return result["message"]


def format_brand_ambiguous(candidates: list[dict[str, Any]]) -> str:
    lines = ["Multiple brands match. Please be more specific:"]
    for c in candidates[:10]:
        name = c.get("name") or "?"
        lines.append(f"  - {name}")
    return "\n".join(lines)
