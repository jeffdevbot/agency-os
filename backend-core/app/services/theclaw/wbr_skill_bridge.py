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

    profile = resolve_wbr_profile(db, client_name, market_scope)
    if not profile:
        return {
            "status": "no_profile",
            "detail": f"No WBR profile found for {client_name} {market_scope}.",
        }

    svc = WBRSnapshotService(db)
    snapshot = svc.get_or_create_snapshot(str(profile["id"]))

    digest = snapshot.get("digest") if snapshot else None
    if not digest:
        _logger.warning("wbr_skill_bridge: snapshot returned but no digest")
        return {
            "status": "no_data",
            "detail": f"WBR data is not available for {client_name} {market_scope} yet.",
        }

    if snapshot.get("source_run_at") and "source_run_at" not in digest:
        digest["source_run_at"] = snapshot["source_run_at"]

    return digest
