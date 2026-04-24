from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from supabase import Client

from .amazon_spapi_auth import normalize_spapi_region_code
from ..wbr.amazon_ads_auth import normalize_ads_region_code
from ..wbr.profiles import WBRNotFoundError, WBRValidationError

AMAZON_ADS_PROVIDER = "amazon_ads"
AMAZON_SPAPI_PROVIDER = "amazon_spapi"
VALID_CONNECTION_STATUSES = {"connected", "error", "revoked"}


def _as_rows(response: Any) -> list[dict[str, Any]]:
    rows = response.data if hasattr(response, "data") else []
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _ts_value(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _pick_latest(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    return max(
        rows,
        key=lambda row: _ts_value(
            row,
            "last_validated_at",
            "updated_at",
            "connected_at",
            "created_at",
        ),
    )


def _profile_sort_key(profile: dict[str, Any]) -> tuple[int, str]:
    status = str(profile.get("status") or "").strip().lower()
    rank = 0 if status == "active" else 1 if status == "draft" else 2
    created_at = str(profile.get("created_at") or "")
    return (rank, created_at)


def _serialize_connect_profile(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile_id": profile.get("id"),
        "display_name": profile.get("display_name"),
        "marketplace_code": profile.get("marketplace_code"),
        "status": profile.get("status"),
        "amazon_ads_profile_id": profile.get("amazon_ads_profile_id"),
        "amazon_ads_account_id": profile.get("amazon_ads_account_id"),
    }


def _serialize_shared_connection(row: dict[str, Any]) -> dict[str, Any]:
    access_meta = row.get("access_meta")
    meta = access_meta if isinstance(access_meta, dict) else {}
    return {
        "id": row.get("id"),
        "provider": row.get("provider"),
        "connection_status": row.get("connection_status"),
        "external_account_id": row.get("external_account_id"),
        "region_code": row.get("region_code"),
        "connected_at": row.get("connected_at"),
        "last_validated_at": row.get("last_validated_at"),
        "last_error": row.get("last_error"),
        "updated_at": row.get("updated_at"),
        "lwa_account_hint": meta.get("lwa_account_hint"),
        "access_meta": meta,
    }


def _serialize_legacy_connection(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile_id": row.get("profile_id"),
        "connection_status": "connected",
        "connected_at": row.get("connected_at"),
        "updated_at": row.get("updated_at"),
        "lwa_account_hint": row.get("lwa_account_hint"),
    }


def _normalized_connection_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    return status if status in VALID_CONNECTION_STATUSES else "error"


def _is_shared_connection_healthy(row: dict[str, Any] | None) -> bool:
    return isinstance(row, dict) and _normalized_connection_status(row.get("connection_status")) == "connected"


def get_wbr_profile(db: Client, profile_id: str) -> dict[str, Any]:
    response = (
        db.table("wbr_profiles")
        .select(
            "id, client_id, marketplace_code, display_name, status, "
            "amazon_ads_profile_id, amazon_ads_account_id, created_at"
        )
        .eq("id", profile_id)
        .limit(1)
        .execute()
    )
    rows = _as_rows(response)
    if not rows:
        raise WBRNotFoundError(f"Profile {profile_id} not found")
    return rows[0]


def list_amazon_ads_connections(db: Client) -> list[dict[str, Any]]:
    client_rows = _as_rows(
        db.table("agency_clients")
        .select("id, name, status")
        .neq("status", "archived")
        .order("name")
        .execute()
    )
    profile_rows = _as_rows(
        db.table("wbr_profiles")
        .select(
            "id, client_id, marketplace_code, display_name, status, "
            "amazon_ads_profile_id, amazon_ads_account_id, created_at"
        )
        .order("created_at")
        .execute()
    )
    shared_rows = _as_rows(
        db.table("report_api_connections")
        .select(
            "id, client_id, provider, connection_status, external_account_id, region_code, "
            "access_meta, connected_at, last_validated_at, last_error, updated_at"
        )
        .eq("provider", AMAZON_ADS_PROVIDER)
        .order("created_at")
        .execute()
    )
    legacy_rows = _as_rows(
        db.table("wbr_amazon_ads_connections")
        .select("profile_id, connected_at, updated_at, lwa_account_hint, created_at")
        .order("created_at")
        .execute()
    )

    profiles_by_client: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for profile in profile_rows:
        client_id = str(profile.get("client_id") or "").strip()
        if client_id:
            profiles_by_client[client_id].append(profile)

    shared_by_client: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in shared_rows:
        client_id = str(row.get("client_id") or "").strip()
        if client_id:
            shared_by_client[client_id].append(row)
    legacy_by_profile = {
        str(row.get("profile_id") or "").strip(): row
        for row in legacy_rows
        if str(row.get("profile_id") or "").strip()
    }

    summaries: list[dict[str, Any]] = []
    for client in client_rows:
        client_id = str(client.get("id") or "").strip()
        client_profiles = sorted(profiles_by_client.get(client_id, []), key=_profile_sort_key)
        latest_legacy = _pick_latest(
            [legacy_by_profile[profile_id] for profile_id in [str(p.get("id") or "") for p in client_profiles] if profile_id in legacy_by_profile]
        )
        shared_connections = shared_by_client.get(client_id, [])
        shared_connection = _pick_latest(shared_connections)
        source = "shared" if shared_connection else "legacy" if latest_legacy else "none"

        summaries.append(
            {
                "client_id": client_id,
                "client_name": client.get("name"),
                "client_status": client.get("status"),
                "connected": _is_shared_connection_healthy(shared_connection) if shared_connection else bool(latest_legacy),
                "source": source,
                "shared_connection": _serialize_shared_connection(shared_connection) if shared_connection else None,
                "shared_connections": [
                    _serialize_shared_connection(row)
                    for row in sorted(shared_connections, key=lambda row: _ts_value(row, "region_code", "external_account_id"))
                ],
                "legacy_connection": _serialize_legacy_connection(latest_legacy) if latest_legacy else None,
                "connect_profiles": [_serialize_connect_profile(profile) for profile in client_profiles],
            }
        )

    return summaries


def upsert_amazon_ads_connection(
    db: Client,
    *,
    client_id: str,
    refresh_token: str,
    region_code: str | None = None,
    external_account_id: str | None = None,
    connected_at: str | None = None,
    updated_by: str | None = None,
    access_meta: dict[str, Any] | None = None,
) -> None:
    client_id = str(client_id or "").strip()
    refresh_token = str(refresh_token or "").strip()
    normalized_region = normalize_ads_region_code(region_code)
    normalized_external_account_id = str(external_account_id or "").strip()
    if not client_id:
        raise WBRValidationError("client_id is required")
    if not refresh_token:
        raise WBRValidationError("refresh_token is required")

    now = connected_at or datetime.now(UTC).isoformat()
    payload: dict[str, Any] = {
        "client_id": client_id,
        "provider": AMAZON_ADS_PROVIDER,
        "connection_status": "connected",
        "refresh_token": refresh_token,
        "external_account_id": normalized_external_account_id or None,
        "region_code": normalized_region,
        "connected_at": now,
        "last_error": None,
        "access_meta": access_meta or {},
    }
    if updated_by:
        payload["updated_by"] = updated_by

    query = (
        db.table("report_api_connections")
        .select("id")
        .eq("client_id", client_id)
        .eq("provider", AMAZON_ADS_PROVIDER)
    )
    if normalized_external_account_id:
        query = query.eq("external_account_id", normalized_external_account_id)
    else:
        query = query.eq("region_code", normalized_region)
    existing_rows = _as_rows(query.limit(1).execute())
    if existing_rows:
        db.table("report_api_connections").update(payload).eq("id", existing_rows[0]["id"]).execute()
        return

    if updated_by:
        payload["created_by"] = updated_by
    db.table("report_api_connections").insert(payload).execute()


# ---------------------------------------------------------------------------
# Amazon Seller API (SP-API) connections
# ---------------------------------------------------------------------------


def upsert_spapi_connection(
    db: Client,
    *,
    client_id: str,
    refresh_token: str,
    selling_partner_id: str,
    region_code: str,
    connected_at: str | None = None,
    updated_by: str | None = None,
) -> None:
    client_id = str(client_id or "").strip()
    refresh_token = str(refresh_token or "").strip()
    selling_partner_id = str(selling_partner_id or "").strip()
    normalized_region = normalize_spapi_region_code(region_code)
    if not client_id:
        raise WBRValidationError("client_id is required")
    if not refresh_token:
        raise WBRValidationError("refresh_token is required")

    now = connected_at or datetime.now(UTC).isoformat()
    payload: dict[str, Any] = {
        "client_id": client_id,
        "provider": AMAZON_SPAPI_PROVIDER,
        "connection_status": "connected",
        "refresh_token": refresh_token,
        "external_account_id": selling_partner_id or None,
        "region_code": normalized_region,
        "connected_at": now,
        "last_error": None,
        "access_meta": {},
    }
    if updated_by:
        payload["updated_by"] = updated_by

    query = (
        db.table("report_api_connections")
        .select("id")
        .eq("client_id", client_id)
        .eq("provider", AMAZON_SPAPI_PROVIDER)
    )
    if selling_partner_id:
        query = query.eq("external_account_id", selling_partner_id)
    else:
        query = query.eq("region_code", normalized_region)

    existing_rows = _as_rows(query.limit(1).execute())
    if existing_rows:
        db.table("report_api_connections").update(payload).eq(
            "id", existing_rows[0]["id"]
        ).execute()
        return

    if updated_by:
        payload["created_by"] = updated_by
    db.table("report_api_connections").insert(payload).execute()


def list_spapi_connections(db: Client) -> list[dict[str, Any]]:
    client_rows = _as_rows(
        db.table("agency_clients")
        .select("id, name, status")
        .neq("status", "archived")
        .order("name")
        .execute()
    )
    shared_rows = _as_rows(
        db.table("report_api_connections")
        .select(
            "id, client_id, provider, connection_status, external_account_id, region_code, "
            "access_meta, connected_at, last_validated_at, last_error, updated_at"
        )
        .eq("provider", AMAZON_SPAPI_PROVIDER)
        .order("created_at")
        .execute()
    )

    shared_by_client: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in shared_rows:
        client_id = str(row.get("client_id") or "").strip()
        if client_id:
            shared_by_client[client_id].append(row)

    summaries: list[dict[str, Any]] = []
    for client in client_rows:
        client_id = str(client.get("id") or "").strip()
        connections = shared_by_client.get(client_id, [])
        connection = _pick_latest(connections)
        summaries.append(
            {
                "client_id": client_id,
                "client_name": client.get("name"),
                "client_status": client.get("status"),
                "connected": _is_shared_connection_healthy(connection),
                "connection": _serialize_shared_connection(connection)
                if connection
                else None,
                "connections": [
                    _serialize_shared_connection(row)
                    for row in sorted(connections, key=lambda row: _ts_value(row, "region_code", "external_account_id"))
                ],
            }
        )

    return summaries


def get_spapi_connection(
    db: Client,
    client_id: str,
    *,
    region_code: str | None = None,
) -> dict[str, Any] | None:
    """Return the SP-API shared connection for a client, or None."""
    query = (
        db.table("report_api_connections")
        .select(
            "id, client_id, provider, connection_status, external_account_id, "
            "region_code, refresh_token, access_meta, connected_at, "
            "last_validated_at, last_error, updated_at"
        )
        .eq("client_id", client_id)
        .eq("provider", AMAZON_SPAPI_PROVIDER)
    )
    if region_code:
        query = query.eq("region_code", normalize_spapi_region_code(region_code))

    rows = _as_rows(query.limit(1).execute())
    return rows[0] if rows else None


def update_connection_validation(
    db: Client,
    *,
    connection_id: str,
    last_validated_at: str,
    last_error: str | None,
    connection_status: str = "connected",
    access_meta: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "last_validated_at": last_validated_at,
        "last_error": last_error,
        "connection_status": connection_status,
    }
    if access_meta is not None:
        payload["access_meta"] = access_meta
    db.table("report_api_connections").update(payload).eq(
        "id", connection_id
    ).execute()
