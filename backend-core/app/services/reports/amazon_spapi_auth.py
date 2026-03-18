"""Amazon Seller API OAuth helper – state signing, token exchange, and validation.

Follows the same patterns as wbr/amazon_ads_auth.py but for SP-API seller
authorization.  The LWA token endpoint is shared; the authorization URL and
callback parameters differ.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from typing import Any
from urllib.parse import urlencode

import httpx

from ..wbr.profiles import WBRValidationError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
SELLER_CENTRAL_AUTH_URL = "https://sellercentral.amazon.com/apps/authorize/consent"
SPAPI_NA_ENDPOINT = "https://sellingpartnerapi-na.amazon.com"
STATE_MAX_AGE_SECONDS = 600  # 10 minutes


def _spapi_client_id() -> str:
    value = os.getenv("AMAZON_SPAPI_LWA_CLIENT_ID", "").strip()
    if not value:
        raise WBRValidationError("AMAZON_SPAPI_LWA_CLIENT_ID is not configured")
    return value


def _spapi_client_secret() -> str:
    value = os.getenv("AMAZON_SPAPI_LWA_CLIENT_SECRET", "").strip()
    if not value:
        raise WBRValidationError("AMAZON_SPAPI_LWA_CLIENT_SECRET is not configured")
    return value


def _spapi_app_id() -> str:
    value = os.getenv("AMAZON_SPAPI_APP_ID", "").strip()
    if not value:
        raise WBRValidationError("AMAZON_SPAPI_APP_ID is not configured")
    return value


def _signing_key() -> bytes:
    """Use the Supabase JWT secret as the HMAC key for state tokens."""
    key = os.getenv("SUPABASE_JWT_SECRET", "").strip()
    if not key:
        raise WBRValidationError("SUPABASE_JWT_SECRET is not configured")
    return key.encode()


def _is_draft_app() -> bool:
    """Return True when the SP-API app is still in draft/beta on Seller Central."""
    return os.getenv("AMAZON_SPAPI_DRAFT_APP", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


# ---------------------------------------------------------------------------
# Signed OAuth state
# ---------------------------------------------------------------------------


def create_spapi_signed_state(
    *,
    client_id: str,
    initiated_by: str | None,
    return_path: str,
) -> str:
    """Create an HMAC-signed, base64url-encoded state parameter.

    Uses ``cid`` (client_id) instead of ``pid`` (profile_id) because SP-API
    connections are keyed at the client level.
    """
    payload = {
        "cid": client_id,
        "uid": initiated_by or "",
        "ret": return_path,
        "prv": "amazon_spapi",
        "nonce": secrets.token_hex(16),
        "iat": int(time.time()),
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    sig = hmac.new(_signing_key(), body, hashlib.sha256).hexdigest()
    token = urlsafe_b64encode(body).decode().rstrip("=") + "." + sig
    return token


def verify_spapi_signed_state(state: str) -> dict[str, Any]:
    """Verify and decode a signed state token.  Raises on invalid/expired."""
    parts = state.split(".", 1)
    if len(parts) != 2:
        raise WBRValidationError("Invalid OAuth state format")

    body_b64, received_sig = parts
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


def build_seller_auth_url(*, state: str) -> str:
    """Build the Seller Central authorization consent URL."""
    params: dict[str, str] = {
        "application_id": _spapi_app_id(),
        "state": state,
    }
    if _is_draft_app():
        params["version"] = "beta"
    return f"{SELLER_CENTRAL_AUTH_URL}?{urlencode(params)}"


# ---------------------------------------------------------------------------
# Token exchange and refresh
# ---------------------------------------------------------------------------


async def exchange_spapi_auth_code(code: str) -> dict[str, Any]:
    """Exchange an spapi_oauth_code for access + refresh tokens via LWA."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            LWA_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": _spapi_client_id(),
                "client_secret": _spapi_client_secret(),
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if response.status_code != 200:
        detail = response.text[:300]
        raise WBRValidationError(
            f"SP-API token exchange failed ({response.status_code}): {detail}"
        )

    data = response.json()
    if "refresh_token" not in data:
        raise WBRValidationError("SP-API token response missing refresh_token")

    return data


async def refresh_spapi_access_token(refresh_token: str) -> str:
    """Use a stored refresh token to get a fresh LWA access token."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            LWA_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": _spapi_client_id(),
                "client_secret": _spapi_client_secret(),
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if response.status_code != 200:
        detail = response.text[:300]
        raise WBRValidationError(
            f"SP-API token refresh failed ({response.status_code}): {detail}"
        )

    data = response.json()
    access_token = data.get("access_token", "")
    if not access_token:
        raise WBRValidationError(
            "SP-API token refresh response missing access_token"
        )

    return access_token


# ---------------------------------------------------------------------------
# Validation – getMarketplaceParticipations (Sellers API)
# ---------------------------------------------------------------------------


async def get_marketplace_participations(
    access_token: str,
) -> list[dict[str, Any]]:
    """Call Sellers API getMarketplaceParticipations to validate the connection.

    Uses the NA endpoint.  For apps registered after 2023-09-01 AWS Sig V4 is
    not required; the LWA access token alone is sufficient.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{SPAPI_NA_ENDPOINT}/sellers/v1/marketplaceParticipations",
            headers={
                "x-amz-access-token": access_token,
            },
        )

    if response.status_code != 200:
        detail = response.text[:300]
        raise WBRValidationError(
            f"SP-API getMarketplaceParticipations failed ({response.status_code}): {detail}"
        )

    data = response.json()
    payload = data.get("payload", [])
    if not isinstance(payload, list):
        raise WBRValidationError(
            "Unexpected getMarketplaceParticipations response shape"
        )

    return payload


# ---------------------------------------------------------------------------
# Finances API – smoke-test helpers
# ---------------------------------------------------------------------------

FINANCES_V0_BASE = f"{SPAPI_NA_ENDPOINT}/finances/v0"
FINANCES_V2024_BASE = f"{SPAPI_NA_ENDPOINT}/finances/2024-06-19"


async def list_financial_event_groups(
    access_token: str,
    *,
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """Call Finances API v0 listFinancialEventGroups.

    Returns the most recent financial event groups (payment/disbursement
    batches).  Kept deliberately low-volume per the rate-limit guidance.
    """
    params: dict[str, str] = {"MaxResultsPerPage": str(max_results)}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{FINANCES_V0_BASE}/financialEventGroups",
            params=params,
            headers={"x-amz-access-token": access_token},
        )

    if response.status_code != 200:
        detail = response.text[:500]
        raise WBRValidationError(
            f"listFinancialEventGroups failed ({response.status_code}): {detail}"
        )

    data = response.json()
    groups = data.get("payload", {}).get("FinancialEventGroupList", [])
    if not isinstance(groups, list):
        raise WBRValidationError(
            "Unexpected listFinancialEventGroups response shape"
        )
    return groups


async def list_transactions(
    access_token: str,
    *,
    financial_event_group_id: str,
    transaction_status: str = "RELEASED",
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Call Finances API v2024-06-19 listTransactions.

    Retrieves released transactions tied to a specific financial event group,
    which is the Amazon-documented path for determining which transactions
    make up a payment/disbursement.
    """
    params: dict[str, str] = {
        "relatedIdentifierName": "FINANCIAL_EVENT_GROUP_ID",
        "relatedIdentifierValue": financial_event_group_id,
        "transactionStatus": transaction_status,
        "maxResults": str(max_results),
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{FINANCES_V2024_BASE}/transactions",
            params=params,
            headers={"x-amz-access-token": access_token},
        )

    if response.status_code != 200:
        detail = response.text[:500]
        raise WBRValidationError(
            f"listTransactions failed ({response.status_code}): {detail}"
        )

    data = response.json()
    transactions = data.get("transactions", [])
    if not isinstance(transactions, list):
        raise WBRValidationError(
            "Unexpected listTransactions response shape"
        )
    return transactions
