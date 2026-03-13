"""Amazon Ads OAuth callback router.

The callback endpoint is public (no Bearer token) because Amazon redirects
the browser here after the user authorizes.  State validation provides CSRF
protection via HMAC signature + expiry.

The connect-initiation endpoint lives on the WBR admin router so it stays
behind require_admin_user.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from supabase import Client, create_client

from ..config import settings
from ..services.wbr.amazon_ads_auth import (
    exchange_authorization_code,
    verify_signed_state,
)
from ..services.wbr.profiles import WBRValidationError

router = APIRouter(tags=["amazon-ads-oauth"])

def _frontend_url() -> str:
    return os.getenv("FRONTEND_URL", "https://tools.ecomlabs.ca").rstrip("/")


def _get_supabase() -> Client:
    if not settings.supabase_url or not settings.supabase_service_role:
        raise HTTPException(status_code=500, detail="Supabase credentials not configured")
    try:
        return create_client(settings.supabase_url, settings.supabase_service_role)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to initialize Supabase client")


@router.get("/amazon-ads/callback")
@router.get("/api/amazon-ads/callback")
async def amazon_ads_callback(
    code: str = Query(...),
    state: str = Query(...),
):
    """Handle the LWA redirect after user authorizes."""
    # 1. Validate signed state
    try:
        state_payload = verify_signed_state(state)
    except WBRValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    profile_id = state_payload.get("pid", "")
    return_path = state_payload.get("ret", "")

    if not profile_id:
        raise HTTPException(status_code=400, detail="OAuth state missing profile_id")

    # 2. Exchange authorization code for tokens
    try:
        token_data = await exchange_authorization_code(code)
    except WBRValidationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    refresh_token = token_data["refresh_token"]

    # 3. Store the refresh token in wbr_amazon_ads_connections
    db = _get_supabase()
    now = datetime.now(UTC).isoformat()

    try:
        existing = (
            db.table("wbr_amazon_ads_connections")
            .select("id")
            .eq("profile_id", profile_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            db.table("wbr_amazon_ads_connections").update(
                {
                    "amazon_ads_refresh_token": refresh_token,
                    "connected_at": now,
                    "updated_at": now,
                }
            ).eq("profile_id", profile_id).execute()
        else:
            db.table("wbr_amazon_ads_connections").insert(
                {
                    "profile_id": profile_id,
                    "amazon_ads_refresh_token": refresh_token,
                    "connected_at": now,
                    "updated_at": now,
                }
            ).execute()
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail="Failed to store Amazon Ads connection"
        ) from exc

    # 4. Redirect back to the frontend
    base = _frontend_url()
    redirect_url = f"{base}{return_path}" if return_path else base
    return RedirectResponse(url=redirect_url, status_code=302)
