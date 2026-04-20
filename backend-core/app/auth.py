from __future__ import annotations

import threading
import time
from typing import Any

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from supabase import Client, create_client

from .config import settings


auth_scheme = HTTPBearer(auto_error=True)
_supabase_admin_client: Client | None = None
_JWKS_CACHE_UNSET = object()
_supabase_jwks_cache: dict[str, Any] | object | None = _JWKS_CACHE_UNSET
_supabase_jwks_cache_expires_at = 0.0
_supabase_jwks_cache_lock = threading.Lock()
_ASYMMETRIC_JWT_ALGORITHMS = {"RS256", "ES256"}


def _reset_supabase_jwks_cache() -> None:
    global _supabase_jwks_cache, _supabase_jwks_cache_expires_at  # noqa: PLW0603
    with _supabase_jwks_cache_lock:
        _supabase_jwks_cache = _JWKS_CACHE_UNSET
        _supabase_jwks_cache_expires_at = 0.0


def _fetch_supabase_jwks() -> dict[str, Any] | None:
    jwks_url = (settings.supabase_jwks_url or "").strip()
    if not jwks_url:
        return None

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(jwks_url)
            response.raise_for_status()
            payload = response.json()
    except Exception:  # noqa: BLE001
        return None

    keys = payload.get("keys")
    if not isinstance(keys, list):
        return None

    normalized_keys = [key for key in keys if isinstance(key, dict)]
    return {"keys": normalized_keys}


def _get_cached_supabase_jwks() -> dict[str, Any] | None:
    global _supabase_jwks_cache, _supabase_jwks_cache_expires_at  # noqa: PLW0603

    now = time.time()
    with _supabase_jwks_cache_lock:
        if _supabase_jwks_cache is not _JWKS_CACHE_UNSET and now < _supabase_jwks_cache_expires_at:
            return _supabase_jwks_cache

    fresh_jwks = _fetch_supabase_jwks()
    ttl_seconds = max(settings.supabase_jwks_cache_ttl_seconds, 0)
    with _supabase_jwks_cache_lock:
        _supabase_jwks_cache = fresh_jwks
        _supabase_jwks_cache_expires_at = now + ttl_seconds
    return fresh_jwks


def _decode_with_supabase_jwks(token: str, algorithm: str) -> dict[str, Any]:
    jwks = _get_cached_supabase_jwks()
    keys = jwks.get("keys") if isinstance(jwks, dict) else None
    if not keys:
        raise JWTError("Supabase JWKS does not contain any signing keys")

    header = jwt.get_unverified_header(token)
    token_kid = str(header.get("kid") or "").strip()

    candidates = [
        key for key in keys
        if isinstance(key, dict) and (
            not token_kid or str(key.get("kid") or "").strip() == token_kid
        )
    ]
    if token_kid and not candidates:
        raise JWTError("No matching Supabase JWKS signing key was found")
    if not candidates:
        candidates = [key for key in keys if isinstance(key, dict)]

    last_error: JWTError | None = None
    for candidate in candidates:
        try:
            return jwt.decode(
                token,
                candidate,
                algorithms=[algorithm],
                audience=settings.supabase_jwt_audience,
                options={"verify_iss": True},
                issuer=settings.supabase_issuer,
            )
        except JWTError as exc:
            last_error = exc

    raise last_error or JWTError("Unable to validate token with Supabase JWKS")


def _decode_with_supabase_jwt_secret(token: str) -> dict[str, Any]:
    if not settings.supabase_jwt_secret:
        raise RuntimeError("SUPABASE_JWT_SECRET not configured.")
    return jwt.decode(
        token,
        settings.supabase_jwt_secret,
        algorithms=["HS256"],
        audience=settings.supabase_jwt_audience,
        options={"verify_iss": True},
        issuer=settings.supabase_issuer,
    )


def verify_supabase_jwt(token: str):
    try:
        header = jwt.get_unverified_header(token)
        algorithm = str(header.get("alg") or "").strip().upper()

        if algorithm in _ASYMMETRIC_JWT_ALGORITHMS:
            return _decode_with_supabase_jwks(token, algorithm)

        if algorithm in {"", "HS256"}:
            return _decode_with_supabase_jwt_secret(token)

        # Prefer the token-advertised algorithm, but keep HS256 as a migration
        # fallback in case older sessions are still circulating.
        try:
            return _decode_with_supabase_jwks(token, algorithm)
        except JWTError:
            return _decode_with_supabase_jwt_secret(token)
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc


def require_user(creds: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    token = creds.credentials
    return verify_supabase_jwt(token)


def _get_supabase_admin_client() -> Client:
    global _supabase_admin_client  # noqa: PLW0603
    if _supabase_admin_client:
        return _supabase_admin_client
    if not settings.supabase_url or not settings.supabase_service_role:
        raise RuntimeError("Supabase admin credentials are not configured.")
    _supabase_admin_client = create_client(settings.supabase_url, settings.supabase_service_role)
    return _supabase_admin_client


def _reset_supabase_admin_client() -> None:
    global _supabase_admin_client  # noqa: PLW0603
    _supabase_admin_client = None


def _fetch_profile_rows(user_id: str) -> list[dict]:
    last_error: Exception | None = None

    for attempt in range(2):
        try:
            db = _get_supabase_admin_client()
            response = db.table("profiles").select("*").eq("id", user_id).limit(1).execute()
            rows = response.data if isinstance(response.data, list) else []
            return [row for row in rows if isinstance(row, dict)]
        except Exception as exc:
            last_error = exc
            if attempt == 0:
                _reset_supabase_admin_client()
                continue
            break

    raise HTTPException(status_code=500, detail="Failed to validate admin access") from last_error


def _fetch_admin_profile_rows(user_id: str) -> list[dict]:
    return _fetch_profile_rows(user_id)


def _normalize_allowed_tools(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {
        str(item).strip().lower()
        for item in value
        if str(item).strip()
    }


def _is_admin_profile(profile: dict[str, Any]) -> bool:
    is_admin = bool(profile.get("is_admin"))
    role = str(profile.get("role") or "").strip().lower()
    team_role = str(profile.get("team_role") or "").strip().lower()
    return is_admin or role == "admin" or team_role == "admin"


def get_authenticated_profile(user: dict[str, Any]) -> dict[str, Any]:
    user_id = str(user.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token: missing subject")

    rows = _fetch_profile_rows(user_id)
    if not rows:
        raise HTTPException(status_code=403, detail="Profile not found")
    return rows[0]


def assert_tool_access(user: dict[str, Any], tool_slug: str) -> dict[str, Any]:
    profile = get_authenticated_profile(user)
    if _is_admin_profile(profile):
        return profile

    normalized_slug = str(tool_slug or "").strip().lower()
    if normalized_slug and normalized_slug in _normalize_allowed_tools(profile.get("allowed_tools")):
        return profile

    raise HTTPException(status_code=403, detail=f"{tool_slug} access required")


def _list_assigned_client_ids(profile_id: str) -> set[str]:
    try:
        db = _get_supabase_admin_client()
        response = (
            db.table("client_assignments")
            .select("client_id")
            .eq("team_member_id", profile_id)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        return {
            str(row.get("client_id") or "").strip()
            for row in rows
            if isinstance(row, dict) and str(row.get("client_id") or "").strip()
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to load client assignments") from exc


def assert_wbr_profile_tool_access(user: dict[str, Any], wbr_profile_id: str, tool_slug: str) -> dict[str, Any]:
    profile = assert_tool_access(user, tool_slug)
    if _is_admin_profile(profile):
        return profile

    try:
        db = _get_supabase_admin_client()
        response = (
            db.table("wbr_profiles")
            .select("id, client_id")
            .eq("id", wbr_profile_id)
            .limit(1)
            .execute()
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to validate marketplace access") from exc

    rows = response.data if isinstance(response.data, list) else []
    if not rows or not isinstance(rows[0], dict):
        raise HTTPException(status_code=404, detail="Profile not found")

    client_id = str(rows[0].get("client_id") or "").strip()
    if not client_id:
        raise HTTPException(status_code=403, detail="Client access required")

    allowed_client_ids = _list_assigned_client_ids(str(profile.get("id") or "").strip())
    if client_id not in allowed_client_ids:
        raise HTTPException(status_code=403, detail="Client access required")

    return profile


def require_admin_user(user=Depends(require_user)):
    profile = get_authenticated_profile(user)
    if _is_admin_profile(profile):
        return user

    raise HTTPException(status_code=403, detail="Admin access required")
