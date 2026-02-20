"""C11A: Command Center read-only lookup skills for AgencyClaw.

Provides query functions and Slack formatters for:
- cc_client_lookup — search/list clients
- cc_brand_list_all — list brands with ClickUp mapping fields
- cc_brand_clickup_mapping_audit — find brands missing ClickUp mappings

All functions are **synchronous** (Supabase sync client).
Callers should wrap in ``asyncio.to_thread`` from async code.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_MAX_RESULTS = 50


# ---------------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------------


def lookup_clients(
    db: Any,
    profile_id: str | None = None,
    query: str = "",
) -> list[dict[str, Any]]:
    """Search/list clients.

    If *query* is provided, fuzzy-match against name.
    Otherwise return assigned clients (or all active if none assigned).
    """
    query = (query or "").strip()

    if query:
        return _search_clients(db, profile_id, query)
    return _list_accessible_clients(db, profile_id)


def list_brands(
    db: Any,
    client_id: str | None = None,
) -> list[dict[str, Any]]:
    """List brands with client name and ClickUp mapping fields.

    If *client_id* is provided, filter to that client.
    Uses Supabase foreign-key join to fetch client name.
    """
    rows = _fetch_brand_rows(
        db,
        client_id=client_id,
        limit=_MAX_RESULTS,
        include_client_join=True,
    )

    # Join shape can vary by DB metadata; backfill client names by ID when needed.
    missing_client_name_ids = {
        str(row.get("client_id") or "")
        for row in rows
        if isinstance(row, dict)
        and row.get("client_id")
        and not _extract_client_name(row)
    }
    client_name_map = _fetch_client_name_map(db, missing_client_name_ids)

    results: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        client_id_value = str(row.get("client_id") or "")
        client_name = _extract_client_name(row) or client_name_map.get(client_id_value, "")
        results.append({
            "id": str(row.get("id") or ""),
            "name": str(row.get("name") or ""),
            "client_name": str(client_name),
            "client_id": client_id_value,
            "clickup_space_id": row.get("clickup_space_id"),
            "clickup_list_id": row.get("clickup_list_id"),
        })
    return results


def audit_brand_mappings(db: Any) -> list[dict[str, Any]]:
    """Find brands missing clickup_space_id and/or clickup_list_id.

    Returns brands where at least one mapping field is NULL.
    """
    rows = _fetch_brand_rows(
        db,
        client_id=None,
        limit=200,
        include_client_join=True,
    )

    missing_client_name_ids = {
        str(row.get("client_id") or "")
        for row in rows
        if isinstance(row, dict)
        and row.get("client_id")
        and not _extract_client_name(row)
    }
    client_name_map = _fetch_client_name_map(db, missing_client_name_ids)

    missing: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        space = row.get("clickup_space_id")
        list_id = row.get("clickup_list_id")
        if space and list_id:
            continue  # fully mapped

        client_id_value = str(row.get("client_id") or "")
        client_name = _extract_client_name(row) or client_name_map.get(client_id_value, "")

        missing_fields: list[str] = []
        if not space:
            missing_fields.append("clickup_space_id")
        if not list_id:
            missing_fields.append("clickup_list_id")

        missing.append({
            "id": str(row.get("id") or ""),
            "name": str(row.get("name") or ""),
            "client_name": str(client_name),
            "client_id": client_id_value,
            "missing_fields": missing_fields,
        })
    return missing


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _search_clients(
    db: Any,
    profile_id: str | None,
    query: str,
) -> list[dict[str, Any]]:
    """Fuzzy search clients by name (case-insensitive substring match).

    If profile_id is provided, constrain search to accessible clients to keep
    behavior consistent with non-query listing.
    """
    if profile_id:
        accessible = _list_accessible_clients(db, profile_id)
        q = query.lower()
        return [c for c in accessible if q in str(c.get("name") or "").lower()][: _MAX_RESULTS]

    response = (
        db.table("agency_clients")
        .select("id,name,status")
        .eq("status", "active")
        .ilike("name", f"%{query}%")
        .order("name", desc=False)
        .limit(_MAX_RESULTS)
        .execute()
    )
    rows = response.data if isinstance(response.data, list) else []
    return [
        {"id": str(r.get("id") or ""), "name": str(r.get("name") or ""), "status": r.get("status")}
        for r in rows
        if isinstance(r, dict) and r.get("id") and r.get("name")
    ]


def _fetch_brand_rows(
    db: Any,
    *,
    client_id: str | None,
    limit: int,
    include_client_join: bool,
) -> list[dict[str, Any]]:
    """Fetch brand rows, with safe fallback if FK join metadata is unavailable."""
    select_clause = "id,name,client_id,clickup_space_id,clickup_list_id"
    if include_client_join:
        select_clause = f"{select_clause},agency_clients(name)"

    try:
        query = (
            db.table("brands")
            .select(select_clause)
            .order("name", desc=False)
            .limit(limit)
        )
        if client_id:
            query = query.eq("client_id", client_id)
        response = query.execute()
        return response.data if isinstance(response.data, list) else []
    except Exception:  # noqa: BLE001
        if include_client_join:
            logger.warning(
                "Brands query join lookup failed; retrying without FK join metadata",
                exc_info=True,
            )
            return _fetch_brand_rows(
                db,
                client_id=client_id,
                limit=limit,
                include_client_join=False,
            )
        raise


def _fetch_client_name_map(
    db: Any,
    client_ids: set[str],
) -> dict[str, str]:
    """Hydrate client names by ID for rows missing join metadata."""
    if not client_ids:
        return {}

    ids = sorted(cid for cid in client_ids if cid)
    if not ids:
        return {}

    query = db.table("agency_clients").select("id,name")
    if hasattr(query, "in_"):
        query = query.in_("id", ids)

    try:
        response = query.execute()
    except Exception:  # noqa: BLE001
        logger.warning("Failed to hydrate client names for brand rows", exc_info=True)
        return {}

    rows = response.data if isinstance(response.data, list) else []
    mapping: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("id") or "")
        name = str(row.get("name") or "")
        if cid and name:
            mapping[cid] = name
    return mapping


def _extract_client_name(row: dict[str, Any]) -> str:
    """Extract client name from joined brand row, handling Supabase shape variance."""
    client_info = row.get("agency_clients")
    if isinstance(client_info, dict):
        return str(client_info.get("name") or "")
    if isinstance(client_info, list) and client_info:
        first = client_info[0]
        if isinstance(first, dict):
            return str(first.get("name") or "")
    return ""


def _list_accessible_clients(
    db: Any,
    profile_id: str | None,
) -> list[dict[str, Any]]:
    """List clients accessible to a user — assigned first, fallback to active."""
    if profile_id:
        for column in ("team_member_id", "profile_id"):
            try:
                assignments = (
                    db.table("client_assignments")
                    .select("agency_clients(id,name,status)")
                    .eq(column, profile_id)
                    .execute()
                )
                rows = assignments.data if isinstance(assignments.data, list) else []
                clients = []
                for row in rows:
                    client = row.get("agency_clients")
                    if isinstance(client, dict) and client.get("id") and client.get("name"):
                        if client.get("status") in (None, "active"):
                            clients.append({
                                "id": str(client["id"]),
                                "name": str(client["name"]),
                                "status": client.get("status"),
                            })
                if clients:
                    return sorted(clients, key=lambda c: c["name"].lower())
            except Exception:  # noqa: BLE001
                continue

    # Fallback: all active clients
    response = (
        db.table("agency_clients")
        .select("id,name,status")
        .eq("status", "active")
        .order("name", desc=False)
        .limit(_MAX_RESULTS)
        .execute()
    )
    rows = response.data if isinstance(response.data, list) else []
    return [
        {"id": str(r.get("id") or ""), "name": str(r.get("name") or ""), "status": r.get("status")}
        for r in rows
        if isinstance(r, dict) and r.get("id") and r.get("name")
    ]


# ---------------------------------------------------------------------------
# Slack formatters (pure functions)
# ---------------------------------------------------------------------------


def format_client_list(clients: list[dict[str, Any]]) -> str:
    """Format client list for Slack — bullet list with name and status."""
    if not clients:
        return "No clients found."

    lines = [f"*Clients* ({len(clients)} found):"]
    for c in clients:
        name = c.get("name", "Unknown")
        status = c.get("status", "")
        tag = f" _({status})_" if status and status != "active" else ""
        lines.append(f"  - {name}{tag}")

    if len(clients) >= _MAX_RESULTS:
        lines.append(f"\n_Showing first {_MAX_RESULTS}. Use a search query to narrow results._")

    lines.append(
        "\n_Note: results reflect clients you currently have access to "
        "(assignment-scoped for most users)._"
    )
    return "\n".join(lines)


def format_brand_list(brands: list[dict[str, Any]]) -> str:
    """Format brand list for Slack — shows client, mapping status."""
    if not brands:
        return "No brands found."

    lines = [f"*Brands* ({len(brands)} found):"]
    for b in brands:
        name = b.get("name", "Unknown")
        client = b.get("client_name", "")
        space = b.get("clickup_space_id")
        list_id = b.get("clickup_list_id")

        if space and list_id:
            mapping = "space + list"
        elif space:
            mapping = "space only"
        elif list_id:
            mapping = "list only"
        else:
            mapping = "no mapping"

        client_prefix = f"[{client}] " if client else ""
        lines.append(f"  - {client_prefix}*{name}* — {mapping}")

    if len(brands) >= _MAX_RESULTS:
        lines.append(f"\n_Showing first {_MAX_RESULTS}. Filter by client to narrow results._")
    return "\n".join(lines)


def format_mapping_audit(missing: list[dict[str, Any]]) -> str:
    """Format audit results for Slack — groups by client, shows missing fields."""
    if not missing:
        return "All brands have ClickUp mappings. Nothing to fix."

    # Group by client
    by_client: dict[str, list[dict[str, Any]]] = {}
    for b in missing:
        client = b.get("client_name") or "Unknown Client"
        by_client.setdefault(client, []).append(b)

    lines = [f"*ClickUp Mapping Audit* — {len(missing)} brand(s) need attention:"]
    for client_name in sorted(by_client.keys()):
        lines.append(f"\n*{client_name}:*")
        for b in by_client[client_name]:
            name = b.get("name", "Unknown")
            fields = b.get("missing_fields", [])
            fields_str = ", ".join(fields)
            lines.append(f"  - {name} — missing: {fields_str}")

    return "\n".join(lines)
