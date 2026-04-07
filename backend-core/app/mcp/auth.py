"""Auth helpers for the Ecomlabs Tools MCP connector."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier

from ..auth import _get_supabase_admin_client, verify_supabase_jwt
from ..config import settings


@dataclass(frozen=True)
class MCPUser:
    profile_id: str
    auth_user_id: str
    email: str | None
    employment_status: str | None

    @property
    def user_id(self) -> str:
        return self.profile_id


class MCPAccessToken(AccessToken):
    """Access token enriched with Ecomlabs Tools user identity."""

    profile_id: str
    auth_user_id: str
    email: str | None = None
    employment_status: str | None = None


def get_current_mcp_user() -> MCPUser | None:
    """Return the current authenticated MCP user, if any."""
    token = get_access_token()
    if not isinstance(token, MCPAccessToken):
        return None
    return MCPUser(
        profile_id=token.profile_id,
        auth_user_id=token.auth_user_id,
        email=token.email,
        employment_status=token.employment_status,
    )


def get_current_pilot_user() -> MCPUser | None:
    """Backward-compatible alias for existing MCP tool modules."""
    return get_current_mcp_user()


def _parse_scopes(payload: dict[str, Any]) -> list[str]:
    scope_claim = payload.get("scope")
    if isinstance(scope_claim, str):
        return [part for part in scope_claim.split() if part]
    if isinstance(scope_claim, list):
        return [str(part).strip() for part in scope_claim if str(part).strip()]
    return []


def _resolve_internal_profile(auth_user_id: str) -> tuple[str, str | None, str | None] | None:
    normalized_user_id = str(auth_user_id or "").strip()
    if not normalized_user_id:
        return None

    db = _get_supabase_admin_client()
    profile_columns = "id, auth_user_id, email, employment_status"
    queries = (
        db.table("profiles").select(profile_columns).eq("auth_user_id", normalized_user_id).limit(1),
        db.table("profiles").select(profile_columns).eq("id", normalized_user_id).limit(1),
    )

    for query in queries:
        response = query.execute()
        rows = response.data if isinstance(response.data, list) else []
        if not rows or not isinstance(rows[0], dict):
            continue

        row = rows[0]
        profile_id = str(row.get("id") or "").strip()
        if not profile_id:
            continue

        employment_status = str(row.get("employment_status") or "").strip().lower() or "active"
        if employment_status == "inactive":
            return None

        email = str(row.get("email") or "").strip() or None
        return profile_id, email, employment_status

    return None


class SupabaseInternalUserTokenVerifier(TokenVerifier):
    """Validate Supabase JWTs for internal Ecomlabs Tools users."""

    async def verify_token(self, token: str) -> MCPAccessToken | None:
        try:
            payload = verify_supabase_jwt(token)
        except Exception:  # noqa: BLE001
            return None

        auth_user_id = str(payload.get("sub") or "").strip()
        if not auth_user_id:
            return None

        profile_id = auth_user_id
        email = str(payload.get("email") or "").strip() or None
        employment_status: str | None = None

        if settings.mcp_require_internal_profile:
            try:
                resolved_profile = _resolve_internal_profile(auth_user_id)
            except Exception:  # noqa: BLE001
                return None
            if not resolved_profile:
                return None
            profile_id, profile_email, employment_status = resolved_profile
            email = profile_email or email

        expires_at = payload.get("exp")
        try:
            expires = int(expires_at) if expires_at is not None else None
        except (TypeError, ValueError):
            expires = None

        return MCPAccessToken(
            token=token,
            client_id=profile_id,
            profile_id=profile_id,
            auth_user_id=auth_user_id,
            email=email,
            employment_status=employment_status,
            scopes=_parse_scopes(payload),
            expires_at=expires,
            resource=settings.mcp_public_base_url,
        )
