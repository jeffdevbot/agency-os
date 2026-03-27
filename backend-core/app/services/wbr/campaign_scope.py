"""Campaign-product scope service for search-term automation.

Builds and persists a snapshot of each campaign's resolved child-ASIN scope
by walking the WBR row tree from the Pacvue campaign map entries to their
active leaf descendants, then resolving child ASINs mapped to those leaves.

This is the foundation for Phase 2 relevance classification.  The table is
populated by rebuild_campaign_scope_for_profile() and is read-only from the
perspective of all other services.

Safe rebuild ordering
---------------------
To avoid leaving a profile with zero active scope rows on failure, the rebuild
follows an insert-first, atomic-swap-second pattern:

  1. If there are no payloads (empty source data), skip deactivation entirely
     and return rebuilt=0.  Existing active rows are preserved.
  2. If there are payloads, insert ALL new rows as inactive first.
  3. Only after all inserts succeed, call one Postgres function that swaps
     old active rows off and new staged rows on in a single transaction.

If an insert fails partway through, the WBRValidationError is raised before the
atomic swap, so the old active rows remain intact.
"""

from __future__ import annotations

from typing import Any

from supabase import Client

from .profiles import WBRNotFoundError, WBRValidationError

_BATCH_SIZE = 500
_PAGE_SIZE = 1000


def rebuild_campaign_scope_for_profile(
    db: Client,
    profile_id: str,
) -> dict[str, Any]:
    """Rebuild the campaign-product scope snapshot for a WBR profile.

    See module docstring for the safe ordering strategy.
    Returns a summary dict: {profile_id, rebuilt, campaigns_skipped_no_asin}.
    """
    _require_profile(db, profile_id)

    campaign_map_rows = _load_active_campaign_map(db, profile_id)
    all_rows = _load_all_rows(db, profile_id)
    asin_row_map = _load_active_asin_row_map(db, profile_id)

    # Build in-memory row tree: parent_id -> [child_ids]
    children_by_parent: dict[str, list[str]] = {}
    rows_by_id: dict[str, dict[str, Any]] = {}
    for row in all_rows:
        row_id = str(row.get("id") or "")
        if not row_id:
            continue
        rows_by_id[row_id] = row
        parent_id = str(row.get("parent_row_id") or "")
        if parent_id:
            children_by_parent.setdefault(parent_id, []).append(row_id)

    # Build ASIN lookup: row_id -> list of child ASINs
    asins_by_row: dict[str, list[str]] = {}
    for entry in asin_row_map:
        row_id = str(entry.get("row_id") or "")
        child_asin = str(entry.get("child_asin") or "").strip().upper()
        if row_id and child_asin:
            asins_by_row.setdefault(row_id, []).append(child_asin)

    payloads: list[dict[str, Any]] = []
    campaigns_skipped_no_asin = 0

    for campaign_row in campaign_map_rows:
        campaign_name = str(campaign_row.get("campaign_name") or "").strip()
        source_row_id = str(campaign_row.get("row_id") or "").strip()
        if not campaign_name or not source_row_id:
            continue

        leaf_ids = _resolve_active_leaves(source_row_id, rows_by_id, children_by_parent)

        asin_set: set[str] = set()
        for leaf_id in leaf_ids:
            asin_set.update(asins_by_row.get(leaf_id, []))

        if not asin_set:
            campaigns_skipped_no_asin += 1
            continue

        payloads.append(
            {
                "profile_id": profile_id,
                "campaign_name": campaign_name,
                "campaign_id": None,
                "source_type": "pacvue_row_mapping",
                "source_row_id": source_row_id,
                "resolved_row_ids": sorted(leaf_ids),
                "resolved_child_asins": sorted(asin_set),
                # Insert inactive; activated only after old rows are deactivated
                "active": False,
            }
        )

    # If nothing to insert, preserve the existing active scope.
    if not payloads:
        return {
            "profile_id": profile_id,
            "rebuilt": 0,
            "campaigns_skipped_no_asin": campaigns_skipped_no_asin,
        }

    # Step 1: Insert all new rows as inactive.  Raises on failure before
    # we touch existing active rows.
    inserted_ids: list[str] = []
    for start in range(0, len(payloads), _BATCH_SIZE):
        chunk = payloads[start : start + _BATCH_SIZE]
        response = db.table("search_term_campaign_scope").insert(chunk).execute()
        rows = response.data if isinstance(response.data, list) else []
        if len(rows) != len(chunk):
            raise WBRValidationError(
                "Failed to stage campaign scope rows — row count mismatch after insert"
            )
        for row in rows:
            row_id = str(row.get("id") or "")
            if row_id:
                inserted_ids.append(row_id)

    # Step 2: Atomically swap old active rows off and new rows on.
    activated = _swap_active_scope_ids(db, profile_id, inserted_ids)

    return {
        "profile_id": profile_id,
        "rebuilt": activated,
        "campaigns_skipped_no_asin": campaigns_skipped_no_asin,
    }


def get_scope_for_campaign(
    db: Client,
    profile_id: str,
    campaign_name: str,
) -> dict[str, Any] | None:
    """Return the active scope row for a campaign, or None if not found.

    Raises WBRNotFoundError if the profile does not exist.
    """
    _require_profile(db, profile_id)
    response = (
        db.table("search_term_campaign_scope")
        .select("*")
        .eq("profile_id", profile_id)
        .eq("campaign_name", campaign_name)
        .eq("active", True)
        .limit(1)
        .execute()
    )
    rows = response.data if isinstance(response.data, list) else []
    return rows[0] if rows else None


def list_scope_for_profile(
    db: Client,
    profile_id: str,
) -> list[dict[str, Any]]:
    """Return all active scope rows for a profile, sorted by campaign name.

    Raises WBRNotFoundError if the profile does not exist.
    """
    _require_profile(db, profile_id)
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        response = (
            db.table("search_term_campaign_scope")
            .select("*")
            .eq("profile_id", profile_id)
            .eq("active", True)
            .order("campaign_name")
            .range(offset, offset + _PAGE_SIZE - 1)
            .execute()
        )
        batch = response.data if isinstance(response.data, list) else []
        rows.extend(batch)
        if len(batch) < _PAGE_SIZE:
            break
        offset += _PAGE_SIZE
    return rows


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require_profile(db: Client, profile_id: str) -> dict[str, Any]:
    response = (
        db.table("wbr_profiles")
        .select("id")
        .eq("id", profile_id)
        .limit(1)
        .execute()
    )
    rows = response.data if isinstance(response.data, list) else []
    if not rows:
        raise WBRNotFoundError(f"Profile {profile_id} not found")
    return rows[0]


def _load_active_campaign_map(
    db: Client, profile_id: str
) -> list[dict[str, Any]]:
    return _select_all(
        db,
        "wbr_pacvue_campaign_map",
        "campaign_name,row_id",
        [("eq", "profile_id", profile_id), ("eq", "active", True)],
    )


def _load_all_rows(db: Client, profile_id: str) -> list[dict[str, Any]]:
    return _select_all(
        db,
        "wbr_rows",
        "id,row_kind,parent_row_id,active",
        [("eq", "profile_id", profile_id)],
    )


def _load_active_asin_row_map(
    db: Client, profile_id: str
) -> list[dict[str, Any]]:
    return _select_all(
        db,
        "wbr_asin_row_map",
        "child_asin,row_id",
        [("eq", "profile_id", profile_id), ("eq", "active", True)],
    )


def _resolve_active_leaves(
    root_row_id: str,
    rows_by_id: dict[str, dict[str, Any]],
    children_by_parent: dict[str, list[str]],
) -> set[str]:
    """Return the set of active leaf row ids reachable from root_row_id.

    If root_row_id is itself an active leaf, returns {root_row_id}.
    If it is a parent, returns all active leaf descendants recursively.
    Inactive rows are excluded from the result.
    """
    result: set[str] = set()
    stack = [root_row_id]
    while stack:
        current_id = stack.pop()
        row = rows_by_id.get(current_id)
        if not row or not row.get("active"):
            continue
        if row.get("row_kind") == "leaf":
            result.add(current_id)
        else:
            for child_id in children_by_parent.get(current_id, []):
                stack.append(child_id)
    return result


def _swap_active_scope_ids(db: Client, profile_id: str, scope_ids: list[str]) -> int:
    """Atomically deactivate old scope rows and activate newly staged ids."""
    if not scope_ids:
        return 0
    response = db.rpc(
        "activate_search_term_campaign_scope",
        {
            "p_profile_id": profile_id,
            "p_scope_ids": scope_ids,
        },
    ).execute()
    activated = response.data
    if isinstance(activated, str) and activated.isdigit():
        activated = int(activated)
    if not isinstance(activated, int):
        raise WBRValidationError("Campaign scope activation RPC returned an unexpected result")
    if activated != len(scope_ids):
        raise WBRValidationError(
            f"Failed to activate campaign scope rows — expected {len(scope_ids)}, activated {activated}"
        )
    return activated


def _select_all(
    db: Client,
    table_name: str,
    columns: str,
    filters: list[tuple[str, str, Any]],
    *,
    page_size: int = _PAGE_SIZE,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = db.table(table_name).select(columns)
        for op, field, value in filters:
            query = getattr(query, op)(field, value)
        response = query.range(offset, offset + page_size - 1).execute()
        batch = response.data if isinstance(response.data, list) else []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows
