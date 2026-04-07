"""WBR-related MCP tools."""

from __future__ import annotations

from collections.abc import Sequence
import logging
from typing import Any

from ...services.wbr.email_drafts import generate_email_draft
from ...services.wbr.email_prompt import PROMPT_VERSION
from ...services.wbr.profiles import WBRNotFoundError, WBRProfileService
from ...services.wbr.report_snapshots import WBRSnapshotService
from .clients import resolve_client_name
from ...auth import _get_supabase_admin_client
from ..auth import get_current_pilot_user

_logger = logging.getLogger(__name__)


def _log_tool_outcome(tool_name: str, outcome: str, **extra: Any) -> None:
    user = get_current_pilot_user()
    suffix = " ".join(f"{key}={value}" for key, value in extra.items())
    if suffix:
        suffix = f" {suffix}"
    _logger.info(
        "MCP tool invocation | tool=%s user_id=%s outcome=%s%s",
        tool_name,
        user.user_id if user else None,
        outcome,
        suffix,
    )


def _list_active_profiles(db: Any, client_id: str | None = None) -> list[dict[str, Any]]:
    svc = WBRProfileService(db)
    profiles: list[dict[str, Any]]
    if client_id:
        profiles = svc.list_profiles(client_id)
    else:
        resp = db.table("wbr_profiles").select("*").execute()
        profiles = resp.data if isinstance(resp.data, list) else []
    return [
        row for row in profiles
        if isinstance(row, dict) and str(row.get("status") or "").strip().lower() == "active"
    ]
def list_wbr_profiles_for_client(client_id: str) -> dict[str, list[dict[str, Any]]]:
    """List active WBR profiles for a canonical client."""
    normalized_client_id = str(client_id or "").strip()
    if not normalized_client_id:
        return {"profiles": []}

    db = _get_supabase_admin_client()
    client_name = resolve_client_name(db, normalized_client_id)
    profiles = _list_active_profiles(db, normalized_client_id)
    profiles.sort(
        key=lambda row: (
            str(row.get("display_name") or "").casefold(),
            str(row.get("marketplace_code") or "").upper(),
            str(row.get("id") or ""),
        )
    )

    return {
        "profiles": [
            {
                "profile_id": str(row.get("id") or ""),
                "client_id": normalized_client_id,
                "client_name": client_name or str(row.get("display_name") or "").strip(),
                "display_name": str(row.get("display_name") or "").strip(),
                "marketplace_code": str(row.get("marketplace_code") or "").strip().upper(),
                "status": "active",
            }
            for row in profiles
            if str(row.get("id") or "").strip()
        ]
    }


def get_wbr_summary_for_profile(profile_id: str) -> dict[str, Any]:
    """Return a canonical WBR snapshot envelope for one profile."""
    normalized_profile_id = str(profile_id or "").strip()
    if not normalized_profile_id:
        raise ValueError("profile_id is required")

    db = _get_supabase_admin_client()
    profile_svc = WBRProfileService(db)
    snapshot_svc = WBRSnapshotService(db)

    try:
        profile = profile_svc.get_profile(normalized_profile_id)
    except WBRNotFoundError as exc:
        raise ValueError(str(exc)) from exc

    client_id = str(profile.get("client_id") or "").strip()
    client_name = resolve_client_name(db, client_id) or str(profile.get("display_name") or "").strip()
    snapshot = snapshot_svc.get_or_create_snapshot(normalized_profile_id)
    digest = snapshot.get("digest")
    if not isinstance(digest, dict) or not digest:
        raise ValueError(f"No WBR digest is available for profile {normalized_profile_id}")

    return {
        "profile": {
            "profile_id": normalized_profile_id,
            "client_id": client_id,
            "client_name": client_name,
            "display_name": str(profile.get("display_name") or "").strip(),
            "marketplace_code": str(profile.get("marketplace_code") or "").strip().upper(),
        },
        "snapshot": {
            "snapshot_id": str(snapshot.get("id") or "").strip() or None,
            "snapshot_kind": str(snapshot.get("snapshot_kind") or "").strip() or None,
            "source_run_at": snapshot.get("source_run_at"),
            "created_at": snapshot.get("created_at"),
        },
        "digest": digest,
    }


async def draft_wbr_email_for_client(client_id: str) -> dict[str, Any]:
    """Generate and return a persisted WBR email draft."""
    normalized_client_id = str(client_id or "").strip()
    if not normalized_client_id:
        raise ValueError("client_id is required")

    db = _get_supabase_admin_client()
    result = await generate_email_draft(
        db,
        normalized_client_id,
        created_by=(get_current_pilot_user().user_id if get_current_pilot_user() else None),
    )
    snapshot_ids = result.get("snapshot_ids")
    if not isinstance(snapshot_ids, Sequence) or isinstance(snapshot_ids, (str, bytes)):
        snapshot_ids = []
    return {
        "draft_id": str(result.get("id") or "").strip(),
        "client_id": normalized_client_id,
        "snapshot_group_key": str(result.get("snapshot_group_key") or "").strip(),
        "draft_kind": "weekly_client_email",
        "prompt_version": PROMPT_VERSION,
        "marketplace_scope": str(result.get("marketplace_scope") or "").strip(),
        "snapshot_ids": [str(item) for item in snapshot_ids if item],
        "subject": str(result.get("subject") or "").strip(),
        "body": str(result.get("body") or "").strip(),
        "model": str(result.get("model") or "").strip() or None,
        "created_at": result.get("created_at"),
    }


def register_wbr_tools(mcp: Any) -> None:
    @mcp.tool(
        name="list_wbr_profiles",
        description=(
            "List active WBR profiles for a canonical Ecomlabs Tools client ID. "
            "Use this after resolve_client so later tools operate on concrete "
            "profile identifiers."
        ),
        structured_output=True,
    )
    def list_wbr_profiles(client_id: str) -> dict[str, list[dict[str, Any]]]:
        _log_tool_outcome("list_wbr_profiles", "started")
        result = list_wbr_profiles_for_client(client_id)
        _log_tool_outcome("list_wbr_profiles", "success", profiles=len(result.get("profiles", [])))
        return result

    @mcp.tool(
        name="get_wbr_summary",
        description=(
            "Return the current WBR snapshot envelope for one concrete profile "
            "ID, including profile metadata, snapshot metadata, and the full digest. "
            "This may read through to create a snapshot when none exists yet."
        ),
        structured_output=True,
    )
    def get_wbr_summary(profile_id: str) -> dict[str, Any]:
        _log_tool_outcome("get_wbr_summary", "started")
        result = get_wbr_summary_for_profile(profile_id)
        _log_tool_outcome("get_wbr_summary", "success", profile_id=profile_id)
        return result

    @mcp.tool(
        name="draft_wbr_email",
        description=(
            "Generate and persist a multi-marketplace weekly WBR client email draft "
            "for a canonical Ecomlabs Tools client ID. This is a mutating tool."
        ),
        structured_output=True,
    )
    async def draft_wbr_email(client_id: str) -> dict[str, Any]:
        _log_tool_outcome("draft_wbr_email", "started")
        result = await draft_wbr_email_for_client(client_id)
        _log_tool_outcome("draft_wbr_email", "success", draft_id=result.get("draft_id"))
        return result
