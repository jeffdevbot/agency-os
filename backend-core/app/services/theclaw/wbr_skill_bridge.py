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


def list_wbr_profiles() -> dict[str, Any]:
    """Return the configured WBR profiles for LLM-side disambiguation."""
    from supabase import create_client
    from ...config import settings

    db = create_client(settings.supabase_url, settings.supabase_service_role_key)

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

    db = create_client(settings.supabase_url, settings.supabase_service_role_key)

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
