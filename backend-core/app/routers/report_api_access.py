from __future__ import annotations

import logging
from datetime import UTC, date, datetime

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
from ..services.reports.sp_api_reports_client import SpApiReportsClient
from ..services.wbr.amazon_ads_auth import build_authorization_url, create_signed_state
from ..services.wbr.profiles import WBRNotFoundError, WBRValidationError
from ..services.wbr.spapi_business_sync import SpApiBusinessCompareService
from ..services.wbr.spapi_listings_fetch import SpApiListingsFetchService

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


class SpApiBusinessCompareRequest(BaseModel):
    profile_id: str = Field(..., min_length=1)
    date_from: date
    date_to: date


class SpApiBusinessDebugRequest(BaseModel):
    profile_id: str = Field(..., min_length=1)
    report_date: date
    asin_granularity: str | None = Field(default="CHILD")
    date_granularity: str | None = Field(default="DAY")
    end_inclusive: bool = Field(default=False)
    omit_report_options: bool = Field(default=False)


class SpApiGenericDebugRequest(BaseModel):
    profile_id: str = Field(..., min_length=1)
    report_type: str = Field(..., min_length=1)
    data_start_time: datetime | None = None
    data_end_time: datetime | None = None
    report_options: dict[str, str] | None = None
    format: str = Field(default="tsv")
    max_sample_rows: int = Field(default=3, ge=0, le=20)


class SpApiListingsPreviewRequest(BaseModel):
    profile_id: str = Field(..., min_length=1)


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


@router.post("/amazon-spapi/compare-business")
async def compare_report_api_access_spapi_business(
    request: SpApiBusinessCompareRequest,
    user=Depends(require_admin_user),
):
    """Run direct SP-API Sales & Traffic compare sync into the compare table."""
    del user
    if request.date_from > request.date_to:
        raise HTTPException(status_code=400, detail="date_from must be <= date_to")
    range_days = (request.date_to - request.date_from).days + 1
    if range_days > 120:
        raise HTTPException(status_code=400, detail="Date range must be <= 120 days")

    db = _get_supabase()
    try:
        summary = await SpApiBusinessCompareService(db).run_compare(
            profile_id=request.profile_id,
            date_from=request.date_from,
            date_to=request.date_to,
        )
    except WBRNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WBRValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        logger.exception("Direct SP-API business compare failed")
        raise HTTPException(
            status_code=500,
            detail="Failed to run direct SP-API business compare",
        )

    return {
        "ok": True,
        "summary": summary,
        "next_step": (
            "Compare rows by running SQL FULL OUTER JOIN on (profile_id, report_date, child_asin) "
            "between wbr_business_asin_daily and wbr_business_asin_daily__compare."
        ),
    }


@router.post("/amazon-spapi/debug-sales-traffic")
async def debug_report_api_access_spapi_business(
    request: SpApiBusinessDebugRequest,
    user=Depends(require_admin_user),
):
    """Diagnostic: fetch ONE Sales & Traffic report for a single day and return
    the raw parsed rows + top-level shape summary. Read-only, writes nothing.
    Use to verify what SP-API actually sends when rows_fetched=0 on the
    compare endpoint."""
    del user
    from datetime import UTC, datetime, time as datetime_time, timedelta
    from ..services.wbr.spapi_business_sync import MARKETPLACE_IDS_BY_CODE

    db = _get_supabase()

    profile_resp = (
        db.table("wbr_profiles").select("*").eq("id", request.profile_id).limit(1).execute()
    )
    profile_rows = profile_resp.data if isinstance(profile_resp.data, list) else []
    if not profile_rows:
        raise HTTPException(status_code=404, detail=f"Profile {request.profile_id} not found")
    profile = profile_rows[0]

    client_id = str(profile.get("client_id") or "").strip()
    marketplace_code = str(profile.get("marketplace_code") or "").strip().upper()
    marketplace_id = MARKETPLACE_IDS_BY_CODE.get(marketplace_code)
    if not marketplace_id:
        raise HTTPException(
            status_code=400,
            detail=f"Marketplace {marketplace_code or '<blank>'} not mapped",
        )

    conn_resp = (
        db.table("report_api_connections")
        .select("*")
        .eq("client_id", client_id)
        .eq("provider", "amazon_spapi")
        .limit(1)
        .execute()
    )
    conn_rows = conn_resp.data if isinstance(conn_resp.data, list) else []
    if not conn_rows:
        raise HTTPException(status_code=400, detail="No SP-API connection for this client")
    connection = conn_rows[0]

    refresh_token = str(connection.get("refresh_token") or "").strip()
    region_code = str(connection.get("region_code") or "").strip()
    if not refresh_token or not region_code:
        raise HTTPException(status_code=400, detail="Connection missing refresh_token or region_code")

    day_start = datetime.combine(request.report_date, datetime_time.min, tzinfo=UTC)
    if request.end_inclusive:
        # same-day 23:59:59Z instead of next-day 00:00:00Z
        day_end = datetime.combine(request.report_date, datetime_time.max, tzinfo=UTC)
    else:
        day_end = day_start + timedelta(days=1)

    report_options: dict[str, str] | None
    if request.omit_report_options:
        report_options = None
    else:
        report_options = {}
        if request.asin_granularity:
            report_options["asinGranularity"] = request.asin_granularity
        if request.date_granularity:
            report_options["dateGranularity"] = request.date_granularity
        if not report_options:
            report_options = None

    client = SpApiReportsClient(refresh_token, region_code)
    rows = await client.fetch_report_rows(
        "GET_SALES_AND_TRAFFIC_REPORT",
        marketplace_ids=[marketplace_id],
        data_start_time=day_start,
        data_end_time=day_end,
        report_options=report_options,
        format="json",
    )

    shape_summary: list[dict[str, object]] = []
    for index, row in enumerate(rows if isinstance(rows, list) else []):
        if not isinstance(row, dict):
            shape_summary.append({"index": index, "type": type(row).__name__})
            continue
        shape_summary.append(
            {
                "index": index,
                "top_level_keys": sorted(row.keys()),
                "salesAndTrafficByDate_len": (
                    len(row["salesAndTrafficByDate"])
                    if isinstance(row.get("salesAndTrafficByDate"), list)
                    else None
                ),
                "salesAndTrafficByAsin_len": (
                    len(row["salesAndTrafficByAsin"])
                    if isinstance(row.get("salesAndTrafficByAsin"), list)
                    else None
                ),
                "reportSpecification": row.get("reportSpecification"),
            }
        )

    return {
        "ok": True,
        "request": {
            "profile_id": request.profile_id,
            "marketplace_code": marketplace_code,
            "marketplace_id": marketplace_id,
            "report_date": request.report_date.isoformat(),
            "data_start_time": day_start.isoformat(),
            "data_end_time": day_end.isoformat(),
            "report_options": report_options,
        },
        "rows_received": len(rows) if isinstance(rows, list) else 0,
        "shape_summary": shape_summary,
        "raw_rows": rows,
    }


@router.post("/amazon-spapi/debug-generic-report")
async def debug_report_api_access_spapi_generic(
    request: SpApiGenericDebugRequest,
    user=Depends(require_admin_user),
):
    """Diagnostic: fetch ANY SP-API report by type for a profile's marketplace.
    Returns a sampled preview + shape summary + row count. Useful for isolating
    whether empty-response issues are Brand-Analytics-specific or broader."""
    del user
    from ..services.wbr.spapi_business_sync import MARKETPLACE_IDS_BY_CODE

    db = _get_supabase()

    profile_resp = (
        db.table("wbr_profiles").select("*").eq("id", request.profile_id).limit(1).execute()
    )
    profile_rows = profile_resp.data if isinstance(profile_resp.data, list) else []
    if not profile_rows:
        raise HTTPException(status_code=404, detail=f"Profile {request.profile_id} not found")
    profile = profile_rows[0]

    client_id = str(profile.get("client_id") or "").strip()
    marketplace_code = str(profile.get("marketplace_code") or "").strip().upper()
    marketplace_id = MARKETPLACE_IDS_BY_CODE.get(marketplace_code)
    if not marketplace_id:
        raise HTTPException(
            status_code=400,
            detail=f"Marketplace {marketplace_code or '<blank>'} not mapped",
        )

    conn_resp = (
        db.table("report_api_connections")
        .select("*")
        .eq("client_id", client_id)
        .eq("provider", "amazon_spapi")
        .limit(1)
        .execute()
    )
    conn_rows = conn_resp.data if isinstance(conn_resp.data, list) else []
    if not conn_rows:
        raise HTTPException(status_code=400, detail="No SP-API connection for this client")
    connection = conn_rows[0]

    refresh_token = str(connection.get("refresh_token") or "").strip()
    region_code = str(connection.get("region_code") or "").strip()
    if not refresh_token or not region_code:
        raise HTTPException(status_code=400, detail="Connection missing refresh_token or region_code")

    fmt = request.format.strip().lower()
    if fmt not in {"tsv", "json"}:
        raise HTTPException(status_code=400, detail="format must be 'tsv' or 'json'")

    client = SpApiReportsClient(refresh_token, region_code)
    call_kwargs: dict = {
        "marketplace_ids": [marketplace_id],
    }
    if request.data_start_time is not None:
        call_kwargs["data_start_time"] = request.data_start_time
    if request.data_end_time is not None:
        call_kwargs["data_end_time"] = request.data_end_time
    if request.report_options is not None:
        call_kwargs["report_options"] = request.report_options

    try:
        rows = await client.fetch_report_rows(
            request.report_type,
            format=fmt,
            **call_kwargs,
        )
    except Exception as exc:
        logger.exception("Generic SP-API debug report failed")
        raise HTTPException(
            status_code=500,
            detail=f"SP-API debug report failed: {exc}",
        )

    row_list = rows if isinstance(rows, list) else []
    first_keys: list[str] = []
    if row_list and isinstance(row_list[0], dict):
        first_keys = sorted(row_list[0].keys())
    sample = row_list[: request.max_sample_rows]

    return {
        "ok": True,
        "request": {
            "profile_id": request.profile_id,
            "marketplace_code": marketplace_code,
            "marketplace_id": marketplace_id,
            "report_type": request.report_type,
            "format": fmt,
            "data_start_time": request.data_start_time.isoformat() if request.data_start_time else None,
            "data_end_time": request.data_end_time.isoformat() if request.data_end_time else None,
            "report_options": request.report_options,
        },
        "rows_received": len(row_list),
        "first_row_columns": first_keys,
        "sample_rows": sample,
    }


@router.post("/amazon-spapi/preview-listings")
async def preview_report_api_access_spapi_listings(
    request: SpApiListingsPreviewRequest,
    user=Depends(require_admin_user),
):
    del user
    db = _get_supabase()
    service = SpApiListingsFetchService(db)
    try:
        return {"ok": True, **await service.fetch_listings(profile_id=request.profile_id)}
    except WBRNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WBRValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("SP-API listings preview failed")
        raise HTTPException(
            status_code=500,
            detail=f"SP-API listings preview failed: {exc}",
        ) from exc


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

    # Step 3: prefer a closed/succeeded group so transaction lookup is more
    # likely to hit a released payout batch, then fall back to the first ID.
    target_group_id = None
    for g in groups:
        gid = g.get("FinancialEventGroupId")
        processing_status = str(g.get("ProcessingStatus") or "").strip().lower()
        fund_transfer_status = str(g.get("FundTransferStatus") or "").strip().lower()
        if gid and processing_status == "closed" and fund_transfer_status == "succeeded":
            target_group_id = str(gid)
            break

    if not target_group_id:
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

    # Step 4: listTransactions for the selected group. Try a few status
    # variants before falling back to no status filter so the smoke test is
    # resilient to account-specific transaction lifecycles.
    transactions: list[dict] = []
    attempted_statuses: list[str] = []
    transaction_lookup_mode = "filtered"
    transaction_status_candidates = [
        "RELEASED",
        "DEFERRED_RELEASED",
        "DEFERRED",
        None,
    ]
    last_transactions_error: str | None = None
    for status in transaction_status_candidates:
        attempted_statuses.append(status or "ALL")
        try:
            candidate_transactions = await list_transactions(
                access_token,
                region_code=region_code,
                financial_event_group_id=target_group_id,
                transaction_status=status,
                max_results=request.max_transactions,
            )
        except WBRValidationError as exc:
            last_transactions_error = str(exc)
            if status is None:
                return {
                    "ok": False,
                    "step": "list_transactions",
                    "region_code": region_code,
                    "target_group_id": target_group_id,
                    "error": str(exc),
                    "groups": group_summaries,
                    "attempted_transaction_statuses": attempted_statuses,
                }
            continue

        if candidate_transactions:
            transactions = candidate_transactions
            transaction_lookup_mode = "unfiltered" if status is None else "filtered"
            break

    if not transactions and last_transactions_error and attempted_statuses[-1] != "ALL":
        return {
            "ok": False,
            "step": "list_transactions",
            "region_code": region_code,
            "target_group_id": target_group_id,
            "error": last_transactions_error,
            "groups": group_summaries,
            "attempted_transaction_statuses": attempted_statuses,
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
        "attempted_transaction_statuses": attempted_statuses,
        "transaction_lookup_mode": transaction_lookup_mode,
    }
