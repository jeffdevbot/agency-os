"""Auth helpers for the Agency OS MCP pilot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier

from ..auth import verify_supabase_jwt
from ..config import settings


@dataclass(frozen=True)
class PilotUser:
    user_id: str
    email: str | None


class PilotAccessToken(AccessToken):
    """Access token enriched with Agency OS user identity."""

    user_id: str
    email: str | None = None


def get_current_pilot_user() -> PilotUser | None:
    """Return the current authenticated MCP pilot user, if any."""
    token = get_access_token()
    if not isinstance(token, PilotAccessToken):
        return None
    return PilotUser(user_id=token.user_id, email=token.email)


def _parse_scopes(payload: dict[str, Any]) -> list[str]:
    scope_claim = payload.get("scope")
    if isinstance(scope_claim, str):
        return [part for part in scope_claim.split() if part]
    if isinstance(scope_claim, list):
        return [str(part).strip() for part in scope_claim if str(part).strip()]
    return []


def _is_allowlisted(payload: dict[str, Any]) -> tuple[str, str | None] | None:
    user_id = str(payload.get("sub") or "").strip()
    email = str(payload.get("email") or "").strip() or None

    allowed_user_id = (settings.mcp_pilot_allowed_user_id or "").strip()
    allowed_email = (settings.mcp_pilot_allowed_email or "").strip().lower()

    if not allowed_user_id and not allowed_email:
        return None
    if allowed_user_id and user_id != allowed_user_id:
        return None
    if allowed_email and (email or "").lower() != allowed_email:
        return None
    if not user_id:
        return None

    return user_id, email


class SupabasePilotTokenVerifier(TokenVerifier):
    """Validate Supabase JWTs for the Jeff-only MCP pilot."""

    async def verify_token(self, token: str) -> PilotAccessToken | None:
        try:
            payload = verify_supabase_jwt(token)
        except Exception:  # noqa: BLE001
            return None

        allowlisted = _is_allowlisted(payload)
        if not allowlisted:
            return None

        user_id, email = allowlisted
        expires_at = payload.get("exp")
        try:
            expires = int(expires_at) if expires_at is not None else None
        except (TypeError, ValueError):
            expires = None

        return PilotAccessToken(
            token=token,
            client_id=user_id,
            user_id=user_id,
            email=email,
            scopes=_parse_scopes(payload),
            expires_at=expires,
            resource=settings.mcp_public_base_url,
        )
