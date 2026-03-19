"""WBR weekly email draft generation and persistence.

Orchestrates: gather multi-marketplace snapshots → build prompt →
call LLM → persist draft → return.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from supabase import Client

from .email_prompt import PROMPT_VERSION, build_email_prompt_messages
from .report_snapshots import WBRSnapshotService

_logger = logging.getLogger(__name__)

# Preferred marketplace display order.
_MARKETPLACE_ORDER = ["US", "CA", "UK", "MX", "DE", "FR", "ES", "IT", "JP", "AU"]


def _marketplace_sort_key(code: str) -> tuple[int, str]:
    """Sort marketplaces by preferred order, unknowns at the end alphabetically."""
    code_upper = (code or "").upper()
    try:
        idx = _MARKETPLACE_ORDER.index(code_upper)
    except ValueError:
        idx = len(_MARKETPLACE_ORDER)
    return (idx, code_upper)


def gather_client_snapshots(
    db: Client,
    client_id: str,
) -> list[dict[str, Any]]:
    """Find active WBR profiles for a client and get/create snapshots for each.

    Returns a list of ``(snapshot, profile_row)`` style dicts with both
    snapshot metadata and the digest, ordered by marketplace preference.
    """
    profile_resp = (
        db.table("wbr_profiles")
        .select("id, client_id, marketplace_code, display_name, status")
        .eq("client_id", client_id)
        .eq("status", "active")
        .execute()
    )
    profiles = profile_resp.data if isinstance(profile_resp.data, list) else []
    if not profiles:
        return []

    profiles.sort(key=lambda p: _marketplace_sort_key(p.get("marketplace_code", "")))

    svc = WBRSnapshotService(db)
    results: list[dict[str, Any]] = []
    for profile in profiles:
        profile_id = str(profile["id"])
        try:
            snapshot = svc.get_or_create_snapshot(profile_id)
        except Exception as exc:  # noqa: BLE001
            _logger.warning(
                "Failed to get/create snapshot for profile %s: %s",
                profile_id, exc,
            )
            continue

        digest = snapshot.get("digest")
        if not digest:
            continue

        if snapshot.get("source_run_at") and "source_run_at" not in digest:
            digest["source_run_at"] = snapshot["source_run_at"]

        results.append({
            "snapshot_id": snapshot.get("id"),
            "profile_id": profile_id,
            "marketplace_code": profile.get("marketplace_code"),
            "display_name": profile.get("display_name"),
            "digest": digest,
        })

    return results


def _resolve_client_name(db: Client, client_id: str) -> str:
    """Look up the agency client name."""
    resp = (
        db.table("agency_clients")
        .select("name")
        .eq("id", client_id)
        .limit(1)
        .execute()
    )
    rows = resp.data if isinstance(resp.data, list) else []
    return rows[0]["name"] if rows else "Client"


async def generate_email_draft(
    db: Client,
    client_id: str,
    *,
    created_by: str | None = None,
) -> dict[str, Any]:
    """Generate and persist a multi-marketplace WBR email draft.

    Returns the saved draft record including id, subject, body, and metadata.
    Raises ValueError if no snapshots are available for the client.
    """
    from ..theclaw.openai_client import call_chat_completion

    snapshot_entries = gather_client_snapshots(db, client_id)
    if not snapshot_entries:
        raise ValueError(f"No active WBR profiles with data found for client {client_id}")

    # Validate all digests share the same week_ending before calling the LLM.
    week_endings = set()
    for entry in snapshot_entries:
        w = (entry["digest"].get("window") or {}).get("week_ending")
        if w:
            week_endings.add(w)
    if len(week_endings) > 1:
        by_market = ", ".join(
            f"{e['marketplace_code']}={(e['digest'].get('window') or {}).get('week_ending', '?')}"
            for e in snapshot_entries
        )
        raise ValueError(
            f"Cannot combine snapshots with different week_ending values ({by_market}). "
            "All marketplaces must share the same reporting week."
        )
    week_ending = week_endings.pop() if week_endings else "unknown"
    snapshot_group_key = f"week_ending:{week_ending}"

    digests = [entry["digest"] for entry in snapshot_entries]
    messages = build_email_prompt_messages(digests=digests)

    response = await call_chat_completion(
        messages=messages,
        temperature=0.4,
        max_tokens=3000,
        response_format={"type": "json_object"},
    )

    raw_content = response.get("content") or ""
    try:
        parsed = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        _logger.warning("WBR email draft LLM returned invalid JSON: %s", raw_content[:200])
        raise ValueError("LLM returned invalid JSON for email draft")

    subject = str(parsed.get("subject") or "Weekly WBR Update").strip()
    body = str(parsed.get("body") or "").strip()
    if not body:
        raise ValueError("LLM returned empty email body")

    snapshot_ids = [entry["snapshot_id"] for entry in snapshot_entries if entry.get("snapshot_id")]
    marketplace_codes = [entry["marketplace_code"] for entry in snapshot_entries]
    marketplace_scope = ",".join(marketplace_codes)

    row: dict[str, Any] = {
        "client_id": client_id,
        "snapshot_group_key": snapshot_group_key,
        "draft_kind": "weekly_client_email",
        "prompt_version": PROMPT_VERSION,
        "marketplace_scope": marketplace_scope,
        "snapshot_ids": snapshot_ids,
        "subject": subject,
        "body": body,
        "model": str(response.get("model") or ""),
    }
    if created_by:
        row["created_by"] = created_by

    insert_resp = db.table("wbr_email_drafts").insert(row).execute()
    inserted = (insert_resp.data or [None])[0] if hasattr(insert_resp, "data") else None
    if not inserted:
        raise RuntimeError("Failed to persist WBR email draft")

    return {
        "id": inserted.get("id"),
        "client_id": client_id,
        "snapshot_group_key": snapshot_group_key,
        "marketplace_scope": marketplace_scope,
        "subject": subject,
        "body": body,
        "model": row["model"],
        "week_ending": week_ending,
        "snapshot_ids": snapshot_ids,
        "created_at": inserted.get("created_at"),
    }


def list_email_drafts(
    db: Client,
    client_id: str,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return recent email drafts for a client (without full body)."""
    response = (
        db.table("wbr_email_drafts")
        .select(
            "id, client_id, snapshot_group_key, draft_kind, prompt_version, "
            "marketplace_scope, snapshot_ids, subject, model, created_by, created_at"
        )
        .eq("client_id", client_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data if isinstance(response.data, list) else []


def get_email_draft(db: Client, draft_id: str) -> dict[str, Any] | None:
    """Return a single email draft with full body."""
    response = (
        db.table("wbr_email_drafts")
        .select("*")
        .eq("id", draft_id)
        .limit(1)
        .execute()
    )
    rows = response.data if isinstance(response.data, list) else []
    return rows[0] if rows else None
