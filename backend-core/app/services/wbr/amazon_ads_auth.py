"""Amazon Ads OAuth helper – state signing, token exchange, and token refresh."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from typing import Any

import httpx

from .profiles import WBRValidationError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AMAZON_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
AMAZON_AUTH_URL = "https://www.amazon.com/ap/oa"
AMAZON_ADS_API_URL = "https://advertising-api.amazon.com"
OAUTH_SCOPE = "advertising::campaign_management"
STATE_MAX_AGE_SECONDS = 600  # 10 minutes


def _client_id() -> str:
    value = os.getenv("AMAZON_ADS_CLIENT_ID", "").strip()
    if not value:
        raise WBRValidationError("AMAZON_ADS_CLIENT_ID is not configured")
    return value


def _client_secret() -> str:
    value = os.getenv("AMAZON_ADS_CLIENT_SECRET", "").strip()
    if not value:
        raise WBRValidationError("AMAZON_ADS_CLIENT_SECRET is not configured")
    return value


def _redirect_uri() -> str:
    value = os.getenv("AMAZON_ADS_REDIRECT_URI", "").strip()
    if not value:
        raise WBRValidationError("AMAZON_ADS_REDIRECT_URI is not configured")
    return value


def _signing_key() -> bytes:
    """Use the Supabase JWT secret as the HMAC key for state tokens."""
    key = os.getenv("SUPABASE_JWT_SECRET", "").strip()
    if not key:
        raise WBRValidationError("SUPABASE_JWT_SECRET is not configured")
    return key.encode()


# ---------------------------------------------------------------------------
# Signed OAuth state
# ---------------------------------------------------------------------------


def create_signed_state(
    *,
    profile_id: str,
    initiated_by: str | None,
    return_path: str,
) -> str:
    """Create an HMAC-signed, base64url-encoded state parameter."""
    payload = {
        "pid": profile_id,
        "uid": initiated_by or "",
        "ret": return_path,
        "nonce": secrets.token_hex(16),
        "iat": int(time.time()),
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    sig = hmac.new(_signing_key(), body, hashlib.sha256).hexdigest()
    token = urlsafe_b64encode(body).decode().rstrip("=") + "." + sig
    return token


def verify_signed_state(state: str) -> dict[str, Any]:
    """Verify and decode a signed state token. Raises on invalid/expired."""
    parts = state.split(".", 1)
    if len(parts) != 2:
        raise WBRValidationError("Invalid OAuth state format")

    body_b64, received_sig = parts
    # Re-pad base64
    padding = 4 - len(body_b64) % 4
    if padding != 4:
        body_b64 += "=" * padding

    try:
        body = urlsafe_b64decode(body_b64)
    except Exception as exc:
        raise WBRValidationError("Invalid OAuth state encoding") from exc

    expected_sig = hmac.new(_signing_key(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, received_sig):
        raise WBRValidationError("Invalid OAuth state signature")

    try:
        payload = json.loads(body)
    except Exception as exc:
        raise WBRValidationError("Invalid OAuth state payload") from exc

    issued_at = payload.get("iat", 0)
    if time.time() - issued_at > STATE_MAX_AGE_SECONDS:
        raise WBRValidationError("OAuth state has expired")

    return payload


# ---------------------------------------------------------------------------
# Authorization URL
# ---------------------------------------------------------------------------


def build_authorization_url(*, state: str) -> str:
    """Build the LWA authorization URL for the browser redirect."""
    from urllib.parse import urlencode

    params = {
        "client_id": _client_id(),
        "scope": OAUTH_SCOPE,
        "response_type": "code",
        "redirect_uri": _redirect_uri(),
        "state": state,
    }
    return f"{AMAZON_AUTH_URL}?{urlencode(params)}"


# ---------------------------------------------------------------------------
# Token exchange and refresh
# ---------------------------------------------------------------------------


async def exchange_authorization_code(code: str) -> dict[str, Any]:
    """Exchange an authorization code for access + refresh tokens."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            AMAZON_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": _redirect_uri(),
                "client_id": _client_id(),
                "client_secret": _client_secret(),
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if response.status_code != 200:
        detail = response.text[:300]
        raise WBRValidationError(
            f"Amazon token exchange failed ({response.status_code}): {detail}"
        )

    data = response.json()
    if "refresh_token" not in data:
        raise WBRValidationError("Amazon token response missing refresh_token")

    return data


async def refresh_access_token(refresh_token: str) -> str:
    """Use a stored refresh token to get a fresh access token."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            AMAZON_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": _client_id(),
                "client_secret": _client_secret(),
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if response.status_code != 200:
        detail = response.text[:300]
        raise WBRValidationError(
            f"Amazon token refresh failed ({response.status_code}): {detail}"
        )

    data = response.json()
    access_token = data.get("access_token", "")
    if not access_token:
        raise WBRValidationError("Amazon token refresh response missing access_token")

    return access_token


# ---------------------------------------------------------------------------
# Amazon Ads API helpers
# ---------------------------------------------------------------------------


async def list_advertising_profiles(access_token: str) -> list[dict[str, Any]]:
    """Fetch all advertising profiles accessible via the given access token."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{AMAZON_ADS_API_URL}/v2/profiles",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Amazon-Advertising-API-ClientId": _client_id(),
            },
        )

    if response.status_code != 200:
        detail = response.text[:300]
        raise WBRValidationError(
            f"Amazon Ads profiles request failed ({response.status_code}): {detail}"
        )

    data = response.json()
    if not isinstance(data, list):
        raise WBRValidationError("Unexpected Amazon Ads profiles response shape")

    return data
