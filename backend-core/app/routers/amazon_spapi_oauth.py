"""Amazon Seller API OAuth callback router.

The callback endpoint is public (no Bearer token) because Amazon redirects
the browser here after the seller authorizes.  State validation provides CSRF
protection via HMAC signature + expiry.

Follows the same structure as amazon_ads_oauth.py.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from supabase import Client, create_client

from ..config import settings
from ..services.reports.amazon_spapi_auth import (
    exchange_spapi_auth_code,
    verify_spapi_signed_state,
)
from ..services.reports.api_access import upsert_spapi_connection
from ..services.wbr.profiles import WBRValidationError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["amazon-spapi-oauth"])


def _frontend_url() -> str:
    return os.getenv("FRONTEND_URL", "https://tools.ecomlabs.ca").rstrip("/")


def _get_supabase() -> Client:
    if not settings.supabase_url or not settings.supabase_service_role:
        raise HTTPException(
            status_code=500, detail="Supabase credentials not configured"
        )
    try:
        return create_client(settings.supabase_url, settings.supabase_service_role)
    except Exception:
        raise HTTPException(
            status_code=500, detail="Failed to initialize Supabase client"
        )


@router.get("/amazon-spapi/callback")
@router.get("/api/amazon-spapi/callback")
async def amazon_spapi_callback(
    state: str = Query(...),
    selling_partner_id: str = Query(""),
    spapi_oauth_code: str = Query(""),
    error: str = Query(""),
    error_description: str = Query(""),
):
    """Handle the Seller Central redirect after seller authorizes."""
    # Handle error response from Amazon (user denied, etc.)
    if error:
        logger.warning(
            "SP-API OAuth error from Amazon: error=%s description=%s",
            error,
            error_description,
        )
        frontend = _frontend_url()
        return RedirectResponse(
            url=f"{frontend}/reports/api-access?spapi_error={error}",
            status_code=302,
        )

    # 1. Validate signed state
    try:
        state_payload = verify_spapi_signed_state(state)
    except WBRValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    client_id = state_payload.get("cid", "")
    return_path = state_payload.get("ret", "")

    if not client_id:
        raise HTTPException(status_code=400, detail="OAuth state missing client_id")

    if not spapi_oauth_code:
        raise HTTPException(status_code=400, detail="Missing spapi_oauth_code")

    if not selling_partner_id:
        raise HTTPException(status_code=400, detail="Missing selling_partner_id")

    # 2. Exchange authorization code for tokens
    try:
        token_data = await exchange_spapi_auth_code(spapi_oauth_code)
    except WBRValidationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    refresh_token = token_data["refresh_token"]

    # 3. Store in report_api_connections
    db = _get_supabase()
    now = datetime.now(UTC).isoformat()

    try:
        upsert_spapi_connection(
            db,
            client_id=client_id,
            refresh_token=refresh_token,
            selling_partner_id=selling_partner_id,
            connected_at=now,
        )
    except Exception as exc:
        logger.error(
            "Failed to store SP-API connection for client_id=%s selling_partner_id=%s",
            client_id,
            selling_partner_id,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="Failed to store Seller API connection"
        ) from exc

    # 4. Redirect back to frontend
    base = _frontend_url()
    redirect_url = f"{base}{return_path}" if return_path else base
    return RedirectResponse(url=redirect_url, status_code=302)
