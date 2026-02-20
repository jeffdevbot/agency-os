"""C12A: Command Center assignment mutation skills for AgencyClaw.

Provides deterministic resolve + upsert/remove functions for
``client_assignments`` (role slot management via Slack chat).

All functions are **synchronous** (Supabase sync client).
Callers should wrap in ``asyncio.to_thread`` from async code.
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

logger = logging.getLogger(__name__)

_MAX_PERSON_RESULTS = 10


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class ResolvePersonResult(TypedDict):
    status: str  # "ok" | "not_found" | "ambiguous"
    profile_id: str | None
    display_name: str | None
    candidates: list[dict[str, Any]]


class ResolveRoleResult(TypedDict):
    status: str  # "ok" | "not_found"
    role_id: str | None
    role_slug: str | None
    role_name: str | None


class ResolveBrandResult(TypedDict):
    status: str  # "ok" | "not_found" | "ambiguous" | "skipped"
    brand_id: str | None
    brand_name: str | None
    candidates: list[dict[str, Any]]


class AssignmentResult(TypedDict):
    status: str  # "ok" | "replaced" | "not_found" | "error"
    message: str
    previous_assignee: str | None


# ---------------------------------------------------------------------------
# Resolve helpers
# ---------------------------------------------------------------------------


def resolve_person(db: Any, name_query: str) -> ResolvePersonResult:
    """Fuzzy-match a team member by display_name or full_name.

    Returns exactly one match, or an ambiguous/not_found result.
    """
    q = (name_query or "").strip().lower()
    if not q:
        return ResolvePersonResult(
            status="not_found", profile_id=None, display_name=None, candidates=[],
        )

    try:
        response = (
            db.table("profiles")
            .select("id,display_name,full_name,email,employment_status")
            .order("display_name", desc=False)
            .limit(200)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
    except Exception:  # noqa: BLE001
        logger.warning("Failed to fetch profiles for person resolution", exc_info=True)
        return ResolvePersonResult(
            status="not_found", profile_id=None, display_name=None, candidates=[],
        )

    # Score: exact > prefix > substring
    scored: list[tuple[int, dict[str, Any]]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        display = str(row.get("display_name") or "").strip()
        full = str(row.get("full_name") or "").strip()
        names = [n.lower() for n in (display, full) if n]
        if not names:
            continue

        best_score = 999
        for n in names:
            if n == q:
                best_score = min(best_score, 0)
            elif n.startswith(q):
                best_score = min(best_score, 1)
            elif q in n:
                best_score = min(best_score, 2)
        if best_score < 999:
            scored.append((best_score, row))

    scored.sort(key=lambda t: (t[0], str(t[1].get("display_name") or "")))

    if not scored:
        return ResolvePersonResult(
            status="not_found", profile_id=None, display_name=None, candidates=[],
        )

    if len(scored) == 1 or (scored[0][0] == 0 and (len(scored) == 1 or scored[1][0] > 0)):
        row = scored[0][1]
        return ResolvePersonResult(
            status="ok",
            profile_id=str(row["id"]),
            display_name=str(row.get("display_name") or row.get("full_name") or ""),
            candidates=[],
        )

    candidates = [
        {
            "id": str(r["id"]),
            "display_name": str(r.get("display_name") or r.get("full_name") or ""),
            "email": str(r.get("email") or ""),
        }
        for _, r in scored[:_MAX_PERSON_RESULTS]
    ]
    return ResolvePersonResult(
        status="ambiguous", profile_id=None, display_name=None, candidates=candidates,
    )


def resolve_role(db: Any, slug_query: str) -> ResolveRoleResult:
    """Resolve a role slug to an agency_roles row.

    Supports exact slug match and common aliases.
    """
    q = (slug_query or "").strip().lower().replace(" ", "_")
    if not q:
        return ResolveRoleResult(status="not_found", role_id=None, role_slug=None, role_name=None)

    # Alias mapping for natural language
    _ALIASES: dict[str, str] = {
        "csl": "customer_success_lead",
        "bm": "customer_success_lead",
        "brand_manager": "customer_success_lead",
        "ppc_strat": "ppc_strategist",
        "ppc_spec": "ppc_specialist",
        "cat_strat": "catalog_strategist",
        "cat_spec": "catalog_specialist",
        "report_spec": "report_specialist",
        "sd": "strategy_director",
    }
    slug = _ALIASES.get(q, q)

    try:
        response = (
            db.table("agency_roles")
            .select("id,slug,name")
            .eq("slug", slug)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if rows and isinstance(rows[0], dict):
            row = rows[0]
            return ResolveRoleResult(
                status="ok",
                role_id=str(row["id"]),
                role_slug=str(row.get("slug") or ""),
                role_name=str(row.get("name") or ""),
            )
    except Exception:  # noqa: BLE001
        logger.warning("Failed to resolve role slug=%s", slug, exc_info=True)

    return ResolveRoleResult(status="not_found", role_id=None, role_slug=None, role_name=None)


def resolve_brand_for_assignment(
    db: Any,
    client_id: str,
    brand_query: str,
) -> ResolveBrandResult:
    """Resolve a brand name within a client scope.

    Returns ok for single match, ambiguous for multiple, not_found for zero.
    """
    q = (brand_query or "").strip().lower()
    if not q:
        return ResolveBrandResult(
            status="skipped", brand_id=None, brand_name=None, candidates=[],
        )

    try:
        response = (
            db.table("brands")
            .select("id,name")
            .eq("client_id", client_id)
            .order("name", desc=False)
            .limit(50)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
    except Exception:  # noqa: BLE001
        logger.warning("Failed to fetch brands for assignment resolution", exc_info=True)
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


# ---------------------------------------------------------------------------
# Assignment mutations
# ---------------------------------------------------------------------------


def upsert_assignment(
    db: Any,
    *,
    client_id: str,
    team_member_id: str,
    role_id: str,
    brand_id: str | None = None,
    assigned_by: str | None = None,
) -> AssignmentResult:
    """Upsert assignment slot.

    The DB has unique constraints on (client_id, role_id) for client-scope
    and (client_id, brand_id, role_id) for brand-scope.

    When replacing an existing assignee, we UPDATE the row in-place rather
    than delete+insert, so a failed update never silently drops the prior
    assignment.  New slots use INSERT.
    """
    previous_assignee: str | None = None

    try:
        # Find existing assignment in this slot
        existing_query = (
            db.table("client_assignments")
            .select("id,team_member_id,profiles(display_name,full_name)")
            .eq("client_id", client_id)
            .eq("role_id", role_id)
        )
        if brand_id:
            existing_query = existing_query.eq("brand_id", brand_id)
        else:
            existing_query = existing_query.is_("brand_id", "null")

        existing_resp = existing_query.limit(1).execute()
        existing_rows = existing_resp.data if isinstance(existing_resp.data, list) else []

        if existing_rows and isinstance(existing_rows[0], dict):
            existing = existing_rows[0]
            existing_member_id = str(existing.get("team_member_id") or "")

            # Already assigned to the same person?
            if existing_member_id == team_member_id:
                profile_info = existing.get("profiles")
                name = ""
                if isinstance(profile_info, dict):
                    name = str(profile_info.get("display_name") or profile_info.get("full_name") or "")
                return AssignmentResult(
                    status="ok",
                    message=f"{name or 'This person'} is already assigned to this slot.",
                    previous_assignee=None,
                )

            # Extract previous assignee name
            profile_info = existing.get("profiles")
            if isinstance(profile_info, dict):
                previous_assignee = str(
                    profile_info.get("display_name") or profile_info.get("full_name") or ""
                )

            # Atomic update: swap team_member_id on the existing row
            update_payload: dict[str, Any] = {"team_member_id": team_member_id}
            if assigned_by:
                update_payload["assigned_by"] = assigned_by
            db.table("client_assignments").update(update_payload).eq("id", existing["id"]).execute()

            return AssignmentResult(
                status="replaced",
                message="Assignment updated.",
                previous_assignee=previous_assignee,
            )

        # No existing row — insert new assignment
        payload: dict[str, Any] = {
            "client_id": client_id,
            "team_member_id": team_member_id,
            "role_id": role_id,
        }
        if brand_id:
            payload["brand_id"] = brand_id
        if assigned_by:
            payload["assigned_by"] = assigned_by

        db.table("client_assignments").insert(payload).execute()

        return AssignmentResult(
            status="ok", message="Assignment created.", previous_assignee=None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to upsert assignment", exc_info=True)
        return AssignmentResult(
            status="error", message=f"Failed to update assignment: {exc}", previous_assignee=None,
        )


def remove_assignment(
    db: Any,
    *,
    client_id: str,
    team_member_id: str,
    role_id: str,
    brand_id: str | None = None,
) -> AssignmentResult:
    """Remove a specific assignment (person + role + scope)."""
    try:
        query = (
            db.table("client_assignments")
            .select("id,team_member_id")
            .eq("client_id", client_id)
            .eq("team_member_id", team_member_id)
            .eq("role_id", role_id)
        )
        if brand_id:
            query = query.eq("brand_id", brand_id)
        else:
            query = query.is_("brand_id", "null")

        resp = query.limit(1).execute()
        rows = resp.data if isinstance(resp.data, list) else []

        if not rows:
            return AssignmentResult(
                status="not_found",
                message="No matching assignment found to remove.",
                previous_assignee=None,
            )

        row = rows[0] if isinstance(rows[0], dict) else {}
        assignment_id = str(row.get("id") or "")
        if not assignment_id:
            return AssignmentResult(
                status="not_found",
                message="No matching assignment found to remove.",
                previous_assignee=None,
            )

        db.table("client_assignments").delete().eq("id", assignment_id).execute()
        return AssignmentResult(
            status="ok", message="Assignment removed.", previous_assignee=None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to remove assignment", exc_info=True)
        return AssignmentResult(
            status="error", message=f"Failed to remove assignment: {exc}", previous_assignee=None,
        )


# ---------------------------------------------------------------------------
# Slack formatters
# ---------------------------------------------------------------------------


def format_upsert_result(
    result: AssignmentResult,
    person_name: str,
    role_name: str,
    client_name: str,
    brand_name: str | None = None,
) -> str:
    scope = f"*{client_name}*"
    if brand_name:
        scope += f" / *{brand_name}*"

    if result["status"] == "ok":
        return f"Assigned *{person_name}* as *{role_name}* on {scope}."
    if result["status"] == "replaced":
        prev = result.get("previous_assignee") or "previous assignee"
        return (
            f"Replaced *{prev}* with *{person_name}* as *{role_name}* on {scope}."
        )
    if result["status"] == "error":
        return f"Failed to assign: {result['message']}"
    return result["message"]


def format_remove_result(
    result: AssignmentResult,
    person_name: str,
    role_name: str,
    client_name: str,
    brand_name: str | None = None,
) -> str:
    scope = f"*{client_name}*"
    if brand_name:
        scope += f" / *{brand_name}*"

    if result["status"] == "ok":
        return f"Removed *{person_name}* from *{role_name}* on {scope}."
    if result["status"] == "not_found":
        return f"No assignment found for *{person_name}* as *{role_name}* on {scope}."
    if result["status"] == "error":
        return f"Failed to remove: {result['message']}"
    return result["message"]


def format_person_ambiguous(candidates: list[dict[str, Any]]) -> str:
    lines = ["Multiple team members match. Please be more specific:"]
    for c in candidates[:10]:
        name = c.get("display_name") or "?"
        email = c.get("email") or ""
        suffix = f" ({email})" if email else ""
        lines.append(f"  - {name}{suffix}")
    return "\n".join(lines)
