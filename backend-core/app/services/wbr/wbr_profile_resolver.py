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

    # Step 1: find the agency client by name.
    # The entity resolver outputs the canonical client name, so exact match
    # (case-insensitive via Supabase/Postgres) is preferred.
    client_resp = (
        db.table("agency_clients")
        .select("id, name")
        .eq("name", client_name)
        .limit(1)
        .execute()
    )
    clients = client_resp.data if isinstance(client_resp.data, list) else []
    if not clients:
        return None

    client_id = clients[0]["id"]

    # Step 2: find the WBR profile for this client + marketplace.
    profile_resp = (
        db.table("wbr_profiles")
        .select("*")
        .eq("client_id", client_id)
        .eq("marketplace_code", marketplace_code)
        .limit(1)
        .execute()
    )
    profiles = profile_resp.data if isinstance(profile_resp.data, list) else []
    return profiles[0] if profiles else None
