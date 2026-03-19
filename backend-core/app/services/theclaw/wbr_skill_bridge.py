"""WBR data lookup for The Claw skills.

Provides the DB lookup that resolves a client + marketplace into a WBR
digest.  Called by the skill_tools registry when the LLM invokes the
``lookup_wbr`` tool — the LLM decides *when* to call it and with what
arguments, not deterministic bridge code.
"""

from __future__ import annotations

import logging
from typing import Any

_logger = logging.getLogger(__name__)


def _get_supabase_service_role(settings_obj: Any) -> str | None:
    return (
        getattr(settings_obj, "supabase_service_role", None)
        or getattr(settings_obj, "supabase_service_role_key", None)
    )


def list_wbr_profiles() -> dict[str, Any]:
    """Return the configured WBR profiles for LLM-side disambiguation."""
    from supabase import create_client
    from ...config import settings

    db = create_client(settings.supabase_url, _get_supabase_service_role(settings))

    client_resp = db.table("agency_clients").select("id, name").execute()
    clients = client_resp.data if isinstance(client_resp.data, list) else []
    client_names = {str(row["id"]): row.get("name") for row in clients if isinstance(row, dict) and row.get("id")}

    profile_resp = (
        db.table("wbr_profiles")
        .select("id, client_id, display_name, marketplace_code")
        .order("display_name")
        .execute()
    )
    profiles = profile_resp.data if isinstance(profile_resp.data, list) else []

    return {
        "profiles": [
            {
                "profile_id": str(row["id"]),
                "client_name": client_names.get(str(row.get("client_id"))) or row.get("display_name"),
                "display_name": row.get("display_name"),
                "marketplace_code": row.get("marketplace_code"),
            }
            for row in profiles
            if isinstance(row, dict)
        ]
    }


def resolve_client_id(client_name: str) -> str | None:
    """Resolve a client name to a client ID for email-draft generation.

    Only considers clients that have at least one active WBR profile,
    and requires an unambiguous match for partial/substring lookups.
    """
    from supabase import create_client
    from ...config import settings

    db = create_client(settings.supabase_url, _get_supabase_service_role(settings))

    # Load clients that have active WBR profiles.
    profile_resp = (
        db.table("wbr_profiles")
        .select("client_id, status")
        .eq("status", "active")
        .execute()
    )
    profiles = profile_resp.data if isinstance(profile_resp.data, list) else []
    wbr_client_ids = {str(row["client_id"]) for row in profiles if isinstance(row, dict) and row.get("client_id")}

    if not wbr_client_ids:
        return None

    client_resp = db.table("agency_clients").select("id, name").execute()
    clients = client_resp.data if isinstance(client_resp.data, list) else []

    # Filter to WBR-enabled clients only.
    wbr_clients = [
        row for row in clients
        if isinstance(row, dict) and str(row.get("id")) in wbr_client_ids
    ]

    name_lower = (client_name or "").strip().lower()
    if not name_lower:
        return None

    # Exact match (case-insensitive) — wins immediately.
    for row in wbr_clients:
        if (row.get("name") or "").strip().lower() == name_lower:
            return str(row["id"])

    # Substring fallback — only if exactly one client matches.
    partial_matches = [
        row for row in wbr_clients
        if name_lower in (row.get("name") or "").strip().lower()
    ]
    if len(partial_matches) == 1:
        return str(partial_matches[0]["id"])

    return None


async def generate_wbr_email_draft(client_name: str) -> dict[str, Any]:
    """Generate a multi-marketplace WBR email draft for a client.

    Returns the draft dict on success, or a status dict on failure.
    """
    from ..wbr.email_drafts import generate_email_draft
    from supabase import create_client
    from ...config import settings

    client_id = resolve_client_id(client_name)
    if not client_id:
        return {
            "status": "no_client",
            "detail": f"No client found matching '{client_name}'.",
        }

    db = create_client(settings.supabase_url, _get_supabase_service_role(settings))

    try:
        draft = await generate_email_draft(db, client_id)
    except ValueError as exc:
        return {
            "status": "no_data",
            "detail": str(exc),
        }

    return draft


def lookup_wbr_digest(client_name: str, market_scope: str) -> dict[str, Any]:
    """Resolve profile -> get/create snapshot -> return digest or error dict.

    Returns either:
    - The full digest dict (has ``digest_version``) on success.
    - A status dict (``{"status": ..., "detail": ...}``) when the profile
      or data doesn't exist yet.
    """
    from ..wbr.wbr_profile_resolver import resolve_wbr_profile
    from ..wbr.report_snapshots import WBRSnapshotService
    from supabase import create_client
    from ...config import settings

    db = create_client(settings.supabase_url, _get_supabase_service_role(settings))

    normalized_market = str(market_scope or "").strip().upper()
    profile = resolve_wbr_profile(db, client_name, normalized_market)
    if not profile:
        return {
            "status": "no_profile",
            "detail": f"No WBR profile found for {client_name} {normalized_market}.",
        }

    svc = WBRSnapshotService(db)
    snapshot = svc.get_or_create_snapshot(str(profile["id"]))

    digest = snapshot.get("digest") if snapshot else None
    if not digest:
        _logger.warning("wbr_skill_bridge: snapshot returned but no digest")
        return {
            "status": "no_data",
            "detail": f"WBR data is not available for {client_name} {normalized_market} yet.",
        }

    if snapshot.get("source_run_at") and "source_run_at" not in digest:
        digest["source_run_at"] = snapshot["source_run_at"]

    return digest
