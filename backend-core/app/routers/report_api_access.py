from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from supabase import Client, create_client

from ..auth import require_admin_user
from ..config import settings
from ..services.reports.amazon_spapi_auth import (
    build_seller_auth_url,
    create_spapi_signed_state,
    get_marketplace_participations,
    refresh_spapi_access_token,
)
from ..services.reports.api_access import (
    get_spapi_connection,
    get_wbr_profile,
    list_amazon_ads_connections,
    list_spapi_connections,
    update_connection_validation,
)
from ..services.wbr.amazon_ads_auth import build_authorization_url, create_signed_state
from ..services.wbr.profiles import WBRNotFoundError, WBRValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/reports/api-access", tags=["report-api-access"])


def _get_supabase() -> Client:
    if not settings.supabase_url or not settings.supabase_service_role:
        raise HTTPException(status_code=500, detail="Supabase credentials not configured")
    try:
        return create_client(settings.supabase_url, settings.supabase_service_role)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to initialize Supabase client")


def _user_id(user: dict) -> str | None:
    return str(user.get("sub")) if isinstance(user, dict) else None


class ReportApiAccessConnectRequest(BaseModel):
    profile_id: str = Field(..., min_length=1)
    return_path: str = Field("/reports/api-access")


@router.get("/amazon-ads/connections")
async def list_report_api_access_amazon_ads_connections(user=Depends(require_admin_user)):
    del user
    db = _get_supabase()
    try:
        return {"ok": True, "connections": list_amazon_ads_connections(db)}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to load Amazon Ads API access")


@router.post("/amazon-ads/connect")
async def connect_report_api_access_amazon_ads(
    request: ReportApiAccessConnectRequest,
    user=Depends(require_admin_user),
):
    db = _get_supabase()
    try:
        profile = get_wbr_profile(db, request.profile_id)
        state = create_signed_state(
            profile_id=request.profile_id,
            initiated_by=_user_id(user),
            return_path=request.return_path,
        )
        return {
            "ok": True,
            "authorization_url": build_authorization_url(state=state),
            "profile": {
                "profile_id": profile.get("id"),
                "client_id": profile.get("client_id"),
                "display_name": profile.get("display_name"),
                "marketplace_code": profile.get("marketplace_code"),
            },
        }
    except WBRNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WBRValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to generate Amazon Ads authorization URL")


# ---------------------------------------------------------------------------
# Amazon Seller API (SP-API) endpoints
# ---------------------------------------------------------------------------


class SpApiConnectRequest(BaseModel):
    client_id: str = Field(..., min_length=1)
    return_path: str = Field("/reports/api-access")


class SpApiValidateRequest(BaseModel):
    client_id: str = Field(..., min_length=1)


@router.get("/amazon-spapi/connections")
async def list_report_api_access_spapi_connections(user=Depends(require_admin_user)):
    del user
    db = _get_supabase()
    try:
        return {"ok": True, "connections": list_spapi_connections(db)}
    except Exception:
        raise HTTPException(
            status_code=500, detail="Failed to load Amazon Seller API access"
        )


@router.post("/amazon-spapi/connect")
async def connect_report_api_access_spapi(
    request: SpApiConnectRequest,
    user=Depends(require_admin_user),
):
    try:
        state = create_spapi_signed_state(
            client_id=request.client_id,
            initiated_by=_user_id(user),
            return_path=request.return_path,
        )
        return {
            "ok": True,
            "authorization_url": build_seller_auth_url(state=state),
        }
    except WBRValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to generate Seller API authorization URL",
        )


@router.post("/amazon-spapi/validate")
async def validate_report_api_access_spapi(
    request: SpApiValidateRequest,
    user=Depends(require_admin_user),
):
    """Validate a stored SP-API connection by refreshing the token and calling
    getMarketplaceParticipations."""
    del user
    db = _get_supabase()
    connection = get_spapi_connection(db, request.client_id)
    if not connection:
        raise HTTPException(
            status_code=404,
            detail="No Amazon Seller API connection found for this client",
        )

    connection_id = str(connection.get("id") or "")
    refresh_token = str(connection.get("refresh_token") or "").strip()
    if not refresh_token:
        raise HTTPException(
            status_code=400,
            detail="Stored SP-API connection has no refresh token",
        )

    now = datetime.now(UTC).isoformat()
    try:
        access_token = await refresh_spapi_access_token(refresh_token)
    except WBRValidationError as exc:
        update_connection_validation(
            db,
            connection_id=connection_id,
            last_validated_at=now,
            last_error=f"Token refresh failed: {exc}",
            connection_status="error",
        )
        return {
            "ok": False,
            "step": "token_refresh",
            "error": str(exc),
        }

    try:
        participations = await get_marketplace_participations(access_token)
    except WBRValidationError as exc:
        update_connection_validation(
            db,
            connection_id=connection_id,
            last_validated_at=now,
            last_error=f"getMarketplaceParticipations failed: {exc}",
            connection_status="error",
        )
        return {
            "ok": False,
            "step": "marketplace_participations",
            "error": str(exc),
        }

    marketplace_ids = [
        p.get("marketplace", {}).get("id")
        for p in participations
        if isinstance(p, dict) and isinstance(p.get("marketplace"), dict)
    ]

    update_connection_validation(
        db,
        connection_id=connection_id,
        last_validated_at=now,
        last_error=None,
        connection_status="connected",
        access_meta={"marketplace_ids": marketplace_ids},
    )

    return {
        "ok": True,
        "marketplace_count": len(participations),
        "marketplace_ids": marketplace_ids,
    }
