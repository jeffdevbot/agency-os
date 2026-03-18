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
    list_financial_event_groups,
    list_transactions,
    normalize_spapi_region_code,
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
    region_code: str = Field(..., min_length=2, max_length=3)
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
        region_code = normalize_spapi_region_code(request.region_code)
        state = create_spapi_signed_state(
            client_id=request.client_id,
            region_code=region_code,
            initiated_by=_user_id(user),
            return_path=request.return_path,
        )
        return {
            "ok": True,
            "authorization_url": build_seller_auth_url(
                state=state,
                region_code=region_code,
            ),
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
    region_code = str(connection.get("region_code") or "").strip()
    existing_meta = connection.get("access_meta") if isinstance(connection.get("access_meta"), dict) else {}
    if not refresh_token:
        raise HTTPException(
            status_code=400,
            detail="Stored SP-API connection has no refresh token",
        )
    if not region_code:
        raise HTTPException(
            status_code=400,
            detail="Stored SP-API connection has no region_code",
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
            "region_code": region_code,
            "error": str(exc),
        }

    try:
        participations = await get_marketplace_participations(
            access_token,
            region_code=region_code,
        )
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
            "region_code": region_code,
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
        access_meta={**existing_meta, "marketplace_ids": marketplace_ids},
    )

    return {
        "ok": True,
        "region_code": region_code,
        "marketplace_count": len(participations),
        "marketplace_ids": marketplace_ids,
    }


# ---------------------------------------------------------------------------
# P&L-first direct-SP-API smoke test (Pass 4)
# ---------------------------------------------------------------------------


class SpApiFinanceSmokeRequest(BaseModel):
    client_id: str = Field(..., min_length=1)
    max_groups: int = Field(5, ge=1, le=20)
    max_transactions: int = Field(20, ge=1, le=100)


@router.post("/amazon-spapi/finance-smoke-test")
async def spapi_finance_smoke_test(
    request: SpApiFinanceSmokeRequest,
    user=Depends(require_admin_user),
):
    """Run the Finances API smoke test against a stored SP-API connection.

    Sequence:
    1. Refresh access token from stored refresh token
    2. Call Finances API v0 listFinancialEventGroups
    3. Pick the first group with a FinancialEventGroupId
    4. Call Finances API v2024-06-19 listTransactions for that group
    5. Return raw results for inspection
    """
    del user
    db = _get_supabase()
    connection = get_spapi_connection(db, request.client_id)
    if not connection:
        raise HTTPException(
            status_code=404,
            detail="No Amazon Seller API connection found for this client",
        )

    refresh_token = str(connection.get("refresh_token") or "").strip()
    region_code = str(connection.get("region_code") or "").strip()
    if not refresh_token:
        raise HTTPException(
            status_code=400,
            detail="Stored SP-API connection has no refresh token",
        )
    if not region_code:
        raise HTTPException(
            status_code=400,
            detail="Stored SP-API connection has no region_code",
        )

    # Step 1: refresh access token
    try:
        access_token = await refresh_spapi_access_token(refresh_token)
    except WBRValidationError as exc:
        return {
            "ok": False,
            "step": "token_refresh",
            "region_code": region_code,
            "error": str(exc),
        }

    # Step 2: listFinancialEventGroups
    try:
        groups = await list_financial_event_groups(
            access_token,
            region_code=region_code,
            max_results=request.max_groups,
        )
    except WBRValidationError as exc:
        return {
            "ok": False,
            "step": "list_financial_event_groups",
            "region_code": region_code,
            "error": str(exc),
        }

    if not groups:
        return {
            "ok": True,
            "step": "list_financial_event_groups",
            "region_code": region_code,
            "note": "No financial event groups returned",
            "groups": [],
            "transactions": [],
        }

    # Summarize groups for the response
    group_summaries = []
    for g in groups:
        group_summaries.append(
            {
                "FinancialEventGroupId": g.get("FinancialEventGroupId"),
                "ProcessingStatus": g.get("ProcessingStatus"),
                "FundTransferStatus": g.get("FundTransferStatus"),
                "OriginalTotal": g.get("OriginalTotal"),
                "ConvertedTotal": g.get("ConvertedTotal"),
                "FundTransferDate": g.get("FundTransferDate"),
                "TraceId": g.get("TraceId"),
                "AccountTail": g.get("AccountTail"),
                "BeginningBalance": g.get("BeginningBalance"),
                "FinancialEventGroupStart": g.get("FinancialEventGroupStart"),
                "FinancialEventGroupEnd": g.get("FinancialEventGroupEnd"),
            }
        )

    # Step 3: pick the first group that has an ID
    target_group_id = None
    for g in groups:
        gid = g.get("FinancialEventGroupId")
        if gid:
            target_group_id = str(gid)
            break

    if not target_group_id:
        return {
            "ok": True,
            "step": "list_financial_event_groups",
            "region_code": region_code,
            "note": "Groups returned but none have a FinancialEventGroupId",
            "groups": group_summaries,
            "transactions": [],
        }

    # Step 4: listTransactions for the selected group
    try:
        transactions = await list_transactions(
            access_token,
            region_code=region_code,
            financial_event_group_id=target_group_id,
            max_results=request.max_transactions,
        )
    except WBRValidationError as exc:
        return {
            "ok": False,
            "step": "list_transactions",
            "region_code": region_code,
            "target_group_id": target_group_id,
            "error": str(exc),
            "groups": group_summaries,
        }

    # Summarize transactions
    transaction_summaries = []
    for t in transactions:
        transaction_summaries.append(
            {
                "transactionId": t.get("transactionId"),
                "transactionType": t.get("transactionType"),
                "transactionStatus": t.get("transactionStatus"),
                "totalAmount": t.get("totalAmount"),
                "description": t.get("description"),
                "relatedIdentifiers": t.get("relatedIdentifiers"),
                "postingDate": t.get("postingDate"),
                "marketplaceDetails": t.get("marketplaceDetails"),
            }
        )

    return {
        "ok": True,
        "region_code": region_code,
        "target_group_id": target_group_id,
        "group_count": len(groups),
        "groups": group_summaries,
        "transaction_count": len(transactions),
        "transactions": transaction_summaries,
    }
