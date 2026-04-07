"""Shared client-discovery MCP tools."""

from __future__ import annotations

from typing import Any

from ...auth import _get_supabase_admin_client
from ..event_logging import start_mcp_tool_invocation


def resolve_client_name(db: Any, client_id: str) -> str | None:
    resp = (
        db.table("agency_clients")
        .select("name")
        .eq("id", client_id)
        .limit(1)
        .execute()
    )
    rows = resp.data if isinstance(resp.data, list) else []
    if not rows:
        return None
    row = rows[0]
    if not isinstance(row, dict):
        return None
    name = str(row.get("name") or "").strip()
    return name or None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def resolve_client_matches(query: str) -> dict[str, list[dict[str, Any]]]:
    """Resolve canonical clients from Command Center data with reporting metadata."""
    needle = (query or "").strip().casefold()
    if not needle:
        return {"matches": []}

    db = _get_supabase_admin_client()

    clients_resp = db.table("agency_clients").select(
        "id, name, company_name, email, phone, status, notes, context_summary, target_audience, positioning_notes"
    ).execute()
    clients = clients_resp.data if isinstance(clients_resp.data, list) else []

    brands_resp = db.table("brands").select(
        "id, client_id, name, product_keywords, amazon_marketplaces, clickup_space_id, clickup_list_id"
    ).execute()
    brand_rows = brands_resp.data if isinstance(brands_resp.data, list) else []

    wbr_profiles_resp = (
        db.table("wbr_profiles")
        .select("client_id, marketplace_code, status")
        .eq("status", "active")
        .execute()
    )
    wbr_profiles = wbr_profiles_resp.data if isinstance(wbr_profiles_resp.data, list) else []

    pnl_profiles_resp = db.table("monthly_pnl_profiles").select(
        "id, client_id, marketplace_code"
    ).execute()
    pnl_profile_rows = pnl_profiles_resp.data if isinstance(pnl_profiles_resp.data, list) else []

    pnl_active_months_resp = (
        db.table("monthly_pnl_import_months")
        .select("profile_id")
        .eq("is_active", True)
        .execute()
    )
    pnl_active_month_rows = (
        pnl_active_months_resp.data if isinstance(pnl_active_months_resp.data, list) else []
    )

    assignments_resp = db.table("client_assignments").select(
        "id, client_id, brand_id, team_member_id, role_id"
    ).execute()
    assignment_rows = assignments_resp.data if isinstance(assignments_resp.data, list) else []

    roles_resp = db.table("agency_roles").select("id, slug, name").execute()
    role_rows = roles_resp.data if isinstance(roles_resp.data, list) else []

    team_members_resp = db.table("profiles").select(
        "id, email, display_name, full_name, employment_status, bench_status, clickup_user_id, slack_user_id"
    ).execute()
    team_member_rows = team_members_resp.data if isinstance(team_members_resp.data, list) else []

    wbr_market_by_client: dict[str, set[str]] = {}
    for row in wbr_profiles:
        if not isinstance(row, dict):
            continue
        client_id = str(row.get("client_id") or "").strip()
        market = str(row.get("marketplace_code") or "").strip().upper()
        if not client_id or not market:
            continue
        wbr_market_by_client.setdefault(client_id, set()).add(market)

    active_pnl_profile_ids = {
        str(row.get("profile_id") or "").strip()
        for row in pnl_active_month_rows
        if isinstance(row, dict) and str(row.get("profile_id") or "").strip()
    }

    pnl_market_by_client: dict[str, set[str]] = {}
    for row in pnl_profile_rows:
        if not isinstance(row, dict):
            continue
        profile_id = str(row.get("id") or "").strip()
        client_id = str(row.get("client_id") or "").strip()
        market = str(row.get("marketplace_code") or "").strip().upper()
        if not profile_id or profile_id not in active_pnl_profile_ids or not client_id or not market:
            continue
        pnl_market_by_client.setdefault(client_id, set()).add(market)

    brands_by_client: dict[str, list[dict[str, Any]]] = {}
    brand_name_by_id: dict[str, str] = {}
    for row in brand_rows:
        if not isinstance(row, dict):
            continue
        brand_id = str(row.get("id") or "").strip()
        client_id = str(row.get("client_id") or "").strip()
        brand_name = str(row.get("name") or "").strip()
        if not brand_id or not client_id or not brand_name:
            continue
        brand_name_by_id[brand_id] = brand_name
        brands_by_client.setdefault(client_id, []).append(
            {
                "brand_id": brand_id,
                "brand_name": brand_name,
                "product_keywords": _string_list(row.get("product_keywords")),
                "amazon_marketplaces": _string_list(row.get("amazon_marketplaces")),
                "clickup_space_id": str(row.get("clickup_space_id") or "").strip() or None,
                "clickup_list_id": str(row.get("clickup_list_id") or "").strip() or None,
                "has_clickup_space": bool(str(row.get("clickup_space_id") or "").strip()),
                "has_clickup_list": bool(str(row.get("clickup_list_id") or "").strip()),
            }
        )

    roles_by_id = {
        str(row.get("id") or "").strip(): {
            "role_slug": str(row.get("slug") or "").strip() or None,
            "role_name": str(row.get("name") or "").strip() or None,
        }
        for row in role_rows
        if isinstance(row, dict) and str(row.get("id") or "").strip()
    }

    team_members_by_id = {
        str(row.get("id") or "").strip(): {
            "team_member_name": str(row.get("display_name") or row.get("full_name") or "").strip()
            or None,
            "team_member_email": str(row.get("email") or "").strip() or None,
            "employment_status": str(row.get("employment_status") or "").strip() or None,
            "bench_status": str(row.get("bench_status") or "").strip() or None,
            "clickup_user_id": str(row.get("clickup_user_id") or "").strip() or None,
            "slack_user_id": str(row.get("slack_user_id") or "").strip() or None,
        }
        for row in team_member_rows
        if isinstance(row, dict) and str(row.get("id") or "").strip()
    }

    assignments_by_client: dict[str, list[dict[str, Any]]] = {}
    for row in assignment_rows:
        if not isinstance(row, dict):
            continue
        client_id = str(row.get("client_id") or "").strip()
        assignment_id = str(row.get("id") or "").strip()
        team_member_id = str(row.get("team_member_id") or "").strip()
        role_id = str(row.get("role_id") or "").strip()
        brand_id = str(row.get("brand_id") or "").strip() or None
        if not client_id or not assignment_id or not team_member_id:
            continue
        team_member = team_members_by_id.get(team_member_id, {})
        role = roles_by_id.get(role_id, {})
        assignments_by_client.setdefault(client_id, []).append(
            {
                "assignment_id": assignment_id,
                "team_member_id": team_member_id,
                "team_member_name": team_member.get("team_member_name"),
                "team_member_email": team_member.get("team_member_email"),
                "employment_status": team_member.get("employment_status"),
                "bench_status": team_member.get("bench_status"),
                "clickup_user_id": team_member.get("clickup_user_id"),
                "slack_user_id": team_member.get("slack_user_id"),
                "role_slug": role.get("role_slug"),
                "role_name": role.get("role_name"),
                "scope": "brand" if brand_id else "client",
                "brand_id": brand_id,
                "brand_name": brand_name_by_id.get(brand_id) if brand_id else None,
            }
        )

    matches: list[dict[str, Any]] = []
    for row in clients:
        if not isinstance(row, dict):
            continue
        client_id = str(row.get("id") or "").strip()
        client_name = str(row.get("name") or "").strip()
        if not client_id or not client_name:
            continue
        if needle not in client_name.casefold():
            continue
        wbr_markets = sorted(wbr_market_by_client.get(client_id, set()))
        pnl_markets = sorted(pnl_market_by_client.get(client_id, set()))
        client_brands = sorted(
            brands_by_client.get(client_id, []),
            key=lambda item: (
                str(item.get("brand_name") or "").casefold(),
                str(item.get("brand_id") or ""),
            ),
        )
        client_assignments = sorted(
            assignments_by_client.get(client_id, []),
            key=lambda item: (
                str(item.get("scope") or ""),
                str(item.get("brand_name") or "").casefold(),
                str(item.get("role_name") or "").casefold(),
                str(item.get("team_member_name") or "").casefold(),
                str(item.get("assignment_id") or ""),
            ),
        )
        matches.append(
            {
                "client_id": client_id,
                "client_name": client_name,
                "client_status": str(row.get("status") or "").strip() or None,
                "company_name": str(row.get("company_name") or "").strip() or None,
                "primary_email": str(row.get("email") or "").strip() or None,
                "phone": str(row.get("phone") or "").strip() or None,
                "active_wbr_marketplaces": wbr_markets,
                "active_monthly_pnl_marketplaces": pnl_markets,
                "brands": client_brands,
                "team_assignments": client_assignments,
                "context": {
                    "notes": str(row.get("notes") or "").strip() or None,
                    "context_summary": str(row.get("context_summary") or "").strip() or None,
                    "target_audience": str(row.get("target_audience") or "").strip() or None,
                    "positioning_notes": str(row.get("positioning_notes") or "").strip() or None,
                },
                "capabilities": {
                    "has_wbr": bool(wbr_markets),
                    "has_monthly_pnl": bool(pnl_markets),
                    "has_brands": bool(client_brands),
                    "has_clickup_destinations": any(
                        bool(brand.get("has_clickup_space") or brand.get("has_clickup_list"))
                        for brand in client_brands
                    ),
                    "has_team_assignments": bool(client_assignments),
                },
            }
        )

    matches.sort(key=lambda item: (item["client_name"].casefold(), item["client_id"]))
    return {"matches": matches}


def register_client_tools(mcp: Any) -> None:
    @mcp.tool(
        name="resolve_client",
        description=(
            "Resolve a free-text client query to canonical Ecomlabs Tools clients "
            "from Command Center data. Returns candidate matches with shared "
            "Ecomlabs Tools metadata including WBR coverage, Monthly P&L coverage, "
            "brand setup, ClickUp destination hints, team assignments, and "
            "client context fields. Does not silently choose a winner."
        ),
        structured_output=True,
    )
    def resolve_client(query: str) -> dict[str, list[dict[str, Any]]]:
        invocation = start_mcp_tool_invocation("resolve_client", is_mutation=False)
        try:
            result = resolve_client_matches(query)
        except Exception as exc:  # noqa: BLE001
            invocation.error(error_type=type(exc).__name__, query_length=len(str(query or "").strip()))
            raise
        invocation.success(
            query_length=len(str(query or "").strip()),
            match_count=len(result.get("matches", [])),
        )
        return result
