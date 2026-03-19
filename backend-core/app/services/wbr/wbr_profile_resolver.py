"""Resolve a WBR profile from client name + marketplace code.

Used by The Claw's wbr_summary skill bridge to map resolved session
context (client, market_scope) to a concrete wbr_profiles row.
"""

from __future__ import annotations

from typing import Any

from supabase import Client


def resolve_wbr_profile(
    db: Client,
    client_name: str,
    marketplace_code: str,
) -> dict[str, Any] | None:
    """Find the WBR profile matching a client name and marketplace.

    Returns the wbr_profiles row dict, or None if no match is found.
    """
    if not client_name or not marketplace_code:
        return None

    normalized_client_name = str(client_name).strip()
    normalized_marketplace_code = str(marketplace_code).strip().upper()

    # Step 1: find the agency client by name.
    # Prefer exact match first, then fall back to a case-insensitive scan over
    # the small client list so the runtime is tolerant of capitalization drift.
    client_resp = db.table("agency_clients").select("id, name").execute()
    clients = client_resp.data if isinstance(client_resp.data, list) else []
    if not clients:
        return None

    selected_client = next(
        (row for row in clients if isinstance(row, dict) and row.get("name") == normalized_client_name),
        None,
    )
    if selected_client is None:
        selected_client = next(
            (
                row
                for row in clients
                if isinstance(row, dict)
                and str(row.get("name") or "").strip().casefold() == normalized_client_name.casefold()
            ),
            None,
        )
    if selected_client is None:
        return None

    client_id = selected_client["id"]

    # Step 2: find the WBR profile for this client + marketplace.
    profile_resp = (
        db.table("wbr_profiles")
        .select("*")
        .eq("client_id", client_id)
        .eq("marketplace_code", normalized_marketplace_code)
        .limit(1)
        .execute()
    )
    profiles = profile_resp.data if isinstance(profile_resp.data, list) else []
    return profiles[0] if profiles else None
