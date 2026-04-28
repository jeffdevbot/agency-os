"""WBR v2 admin router – profile and row management."""

from __future__ import annotations

import os

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from supabase import Client, create_client

from ..auth import require_admin_user
from ..services.wbr.amazon_ads_auth import (
    build_authorization_url,
    create_signed_state,
    list_advertising_profiles,
    normalize_ads_region_code,
    refresh_access_token,
)
from ..services.wbr.amazon_ads_sync import AmazonAdsSyncService
from ..services.wbr.amazon_ads_search_terms import AmazonAdsSearchTermSyncService
from ..services.wbr.asin_mappings import AsinMappingService
from ..services.wbr.campaign_exclusions import CampaignExclusionService
from ..config import settings
from ..services.wbr.listing_imports import ListingImportService
from ..services.wbr.pacvue_imports import PacvueImportService
from ..services.wbr.pacvue_mappings import PacvueMappingService
from ..services.wbr.sales_mix import SalesMixService
from ..services.wbr.sales_mix_workbook import build_sales_mix_workbook
from ..services.wbr.profiles import WBRNotFoundError, WBRValidationError, WBRProfileService
from ..services.wbr.email_drafts import generate_email_draft, list_email_drafts, get_email_draft
from ..services.wbr.report_snapshots import WBRSnapshotService
from ..services.wbr.section1_report import Section1ReportService
from ..services.wbr.section2_report import Section2ReportService
from ..services.wbr.section3_report import Section3ReportService
from ..services.wbr.search_term_facts import SearchTermFactsService
from ..services.wbr.sync_runs import WBRSyncRunService
from ..services.wbr.workbook import WbrWorkbookExportService
from ..services.wbr.windsor_business_sync import WindsorBusinessSyncService

router = APIRouter(prefix="/admin/wbr", tags=["wbr-admin"])
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "40"))


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _get_supabase() -> Client:
    if not settings.supabase_url or not settings.supabase_service_role:
        raise HTTPException(status_code=500, detail="Supabase credentials not configured")
    try:
        return create_client(settings.supabase_url, settings.supabase_service_role)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to initialize Supabase client")


def _get_service() -> WBRProfileService:
    return WBRProfileService(_get_supabase())


def _get_pacvue_service() -> PacvueImportService:
    return PacvueImportService(_get_supabase())


def _get_pacvue_mapping_service() -> PacvueMappingService:
    return PacvueMappingService(_get_supabase())


def _get_sales_mix_service() -> SalesMixService:
    return SalesMixService(_get_supabase())


def _get_listing_service() -> ListingImportService:
    return ListingImportService(_get_supabase())


def _get_asin_mapping_service() -> AsinMappingService:
    return AsinMappingService(_get_supabase())


def _get_campaign_exclusion_service() -> CampaignExclusionService:
    return CampaignExclusionService(_get_supabase())


def _get_windsor_business_sync_service() -> WindsorBusinessSyncService:
    return WindsorBusinessSyncService(_get_supabase())


def _get_sync_run_service() -> WBRSyncRunService:
    return WBRSyncRunService(_get_supabase())


def _get_section1_report_service() -> Section1ReportService:
    return Section1ReportService(_get_supabase())


def _get_section2_report_service() -> Section2ReportService:
    return Section2ReportService(_get_supabase())


def _get_section3_report_service() -> Section3ReportService:
    return Section3ReportService(_get_supabase())


def _get_amazon_ads_sync_service() -> AmazonAdsSyncService:
    return AmazonAdsSyncService(_get_supabase())


def _get_amazon_ads_search_term_sync_service() -> AmazonAdsSearchTermSyncService:
    return AmazonAdsSearchTermSyncService(_get_supabase())


def _get_search_term_facts_service() -> SearchTermFactsService:
    return SearchTermFactsService(_get_supabase())


def _get_wbr_workbook_export_service() -> WbrWorkbookExportService:
    return WbrWorkbookExportService(_get_supabase())


def _get_snapshot_service() -> WBRSnapshotService:
    return WBRSnapshotService(_get_supabase())


def _user_id(user: dict) -> str | None:
    return str(user.get("sub")) if isinstance(user, dict) else None


# ------------------------------------------------------------------
# Request models
# ------------------------------------------------------------------


class CreateProfileRequest(BaseModel):
    client_id: str = Field(..., min_length=1)
    marketplace_code: str = Field(..., min_length=1)
    display_name: str = Field(..., min_length=1)
    week_start_day: str = Field("sunday")
    status: str = Field("draft")
    windsor_account_id: Optional[str] = None
    amazon_ads_profile_id: Optional[str] = None
    amazon_ads_account_id: Optional[str] = None
    amazon_ads_country_code: Optional[str] = None
    amazon_ads_currency_code: Optional[str] = None
    amazon_ads_marketplace_string_id: Optional[str] = None
    backfill_start_date: Optional[str] = None
    daily_rewrite_days: int = Field(14, ge=1, le=60)
    sp_api_auto_sync_enabled: bool = False
    ads_api_auto_sync_enabled: bool = False
    search_term_auto_sync_enabled: bool = False
    search_term_sb_auto_sync_enabled: bool = False
    search_term_sd_auto_sync_enabled: bool = False


class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = None
    week_start_day: Optional[str] = None
    status: Optional[str] = None
    windsor_account_id: Optional[str] = None
    amazon_ads_profile_id: Optional[str] = None
    amazon_ads_account_id: Optional[str] = None
    amazon_ads_country_code: Optional[str] = None
    amazon_ads_currency_code: Optional[str] = None
    amazon_ads_marketplace_string_id: Optional[str] = None
    backfill_start_date: Optional[str] = None
    daily_rewrite_days: Optional[int] = Field(None, ge=1, le=60)
    sp_api_auto_sync_enabled: Optional[bool] = None
    ads_api_auto_sync_enabled: Optional[bool] = None
    search_term_auto_sync_enabled: Optional[bool] = None
    search_term_sb_auto_sync_enabled: Optional[bool] = None
    search_term_sd_auto_sync_enabled: Optional[bool] = None


class CreateRowRequest(BaseModel):
    row_label: str = Field(..., min_length=1)
    row_kind: str = Field(..., pattern=r"^(parent|leaf)$")
    parent_row_id: Optional[str] = None
    sort_order: int = 0


class UpdateRowRequest(BaseModel):
    row_label: Optional[str] = None
    row_kind: Optional[str] = Field(None, pattern=r"^(parent|leaf)$")
    parent_row_id: Optional[str] = None
    sort_order: Optional[int] = None
    active: Optional[bool] = None


class SetAsinMappingRequest(BaseModel):
    row_id: Optional[str] = None


class RunWindsorBusinessBackfillRequest(BaseModel):
    date_from: str
    date_to: str
    chunk_days: int = Field(7, ge=1, le=31)


class RunAmazonAdsBackfillRequest(BaseModel):
    date_from: str
    date_to: str
    chunk_days: int = Field(14, ge=1, le=31)
    ad_product: Optional[str] = None


# ------------------------------------------------------------------
# Profile endpoints
# ------------------------------------------------------------------


@router.get("/profiles")
async def list_profiles(
    client_id: str = Query(..., min_length=1),
    user=Depends(require_admin_user),
):
    svc = _get_service()
    try:
        profiles = svc.list_profiles(client_id)
        return {"ok": True, "profiles": profiles}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list profiles")


@router.post("/profiles")
async def create_profile(
    request: CreateProfileRequest,
    user=Depends(require_admin_user),
):
    svc = _get_service()
    payload = request.model_dump(exclude_none=True)
    try:
        profile = svc.create_profile(payload, user_id=_user_id(user))
        return {"ok": True, "profile": profile}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to create profile")


@router.get("/profiles/{profile_id}")
async def get_profile(
    profile_id: str,
    user=Depends(require_admin_user),
):
    svc = _get_service()
    try:
        profile = svc.get_profile(profile_id)
        return {"ok": True, "profile": profile}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to get profile")


@router.patch("/profiles/{profile_id}")
async def update_profile(
    profile_id: str,
    request: UpdateProfileRequest,
    user=Depends(require_admin_user),
):
    svc = _get_service()
    updates = request.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        profile = svc.update_profile(profile_id, updates, user_id=_user_id(user))
        return {"ok": True, "profile": profile}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to update profile")


# ------------------------------------------------------------------
# Row endpoints
# ------------------------------------------------------------------


@router.get("/profiles/{profile_id}/rows")
async def list_rows(
    profile_id: str,
    include_inactive: bool = Query(False),
    user=Depends(require_admin_user),
):
    svc = _get_service()
    try:
        rows = svc.list_rows(profile_id, include_inactive=include_inactive)
        return {"ok": True, "rows": rows}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list rows")


@router.post("/profiles/{profile_id}/rows")
async def create_row(
    profile_id: str,
    request: CreateRowRequest,
    user=Depends(require_admin_user),
):
    svc = _get_service()
    payload = request.model_dump(exclude_none=True)
    try:
        row = svc.create_row(profile_id, payload, user_id=_user_id(user))
        return {"ok": True, "row": row}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to create row")


@router.patch("/rows/{row_id}")
async def update_row(
    row_id: str,
    request: UpdateRowRequest,
    user=Depends(require_admin_user),
):
    svc = _get_service()
    updates = request.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        row = svc.update_row(row_id, updates, user_id=_user_id(user))
        return {"ok": True, "row": row}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to update row")


@router.delete("/rows/{row_id}")
async def delete_row(
    row_id: str,
    permanent: bool = Query(False),
    user=Depends(require_admin_user),
):
    svc = _get_service()
    try:
        if permanent:
            row = svc.hard_delete_row(row_id)
        else:
            row = svc.soft_delete_row(row_id, user_id=_user_id(user))
        return {"ok": True, "row": row}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to delete row")


# ------------------------------------------------------------------
# Pacvue import endpoints
# ------------------------------------------------------------------


@router.get("/profiles/{profile_id}/pacvue/import-batches")
async def list_pacvue_import_batches(
    profile_id: str,
    user=Depends(require_admin_user),
):
    svc = _get_pacvue_service()
    try:
        batches = svc.list_import_batches(profile_id)
        return {"ok": True, "batches": batches}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list Pacvue import batches")


@router.post("/profiles/{profile_id}/pacvue/import")
async def import_pacvue_workbook(
    profile_id: str,
    file: UploadFile = File(...),
    user=Depends(require_admin_user),
):
    svc = _get_pacvue_service()
    total = 0
    chunk_size = 2 * 1024 * 1024
    file_bytes = bytearray()

    try:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_MB * 1024 * 1024:
                raise HTTPException(status_code=413, detail="File too large")
            file_bytes.extend(chunk)
    finally:
        await file.close()

    try:
        result = svc.import_workbook(
            profile_id=profile_id,
            file_name=file.filename or "pacvue_import.xlsx",
            file_bytes=bytes(file_bytes),
            user_id=_user_id(user),
        )
        return {"ok": True, **result}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to import Pacvue workbook")


# ------------------------------------------------------------------
# Pacvue mapping management (admin sync UI)
# ------------------------------------------------------------------


class PacvueManualMapPayload(BaseModel):
    campaign_name: str
    row_id: str
    goal_code: str


class PacvueDeactivateMapPayload(BaseModel):
    campaign_name: str


class PacvueExclusionPayload(BaseModel):
    campaign_name: str
    excluded: bool = True
    reason: Optional[str] = None


@router.get("/profiles/{profile_id}/pacvue/unmapped")
async def list_pacvue_unmapped(
    profile_id: str,
    weeks: int = Query(4, ge=1, le=26),
    user=Depends(require_admin_user),
):
    svc = _get_pacvue_mapping_service()
    try:
        return {"ok": True, **svc.list_unmapped(profile_id, weeks=weeks)}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list unmapped campaigns")


@router.get("/profiles/{profile_id}/pacvue/mappings")
async def list_pacvue_mappings(
    profile_id: str,
    weeks: int = Query(4, ge=1, le=26),
    user=Depends(require_admin_user),
):
    svc = _get_pacvue_mapping_service()
    try:
        return {"ok": True, **svc.list_mappings(profile_id, weeks=weeks)}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list Pacvue mappings")


@router.get("/profiles/{profile_id}/pacvue/leaf-rows")
async def list_pacvue_leaf_rows(
    profile_id: str,
    user=Depends(require_admin_user),
):
    svc = _get_pacvue_mapping_service()
    try:
        return {"ok": True, "items": svc.list_leaf_rows(profile_id)}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list leaf rows")


@router.post("/profiles/{profile_id}/pacvue/manual-map")
async def upsert_pacvue_manual_map(
    profile_id: str,
    payload: PacvueManualMapPayload,
    user=Depends(require_admin_user),
):
    svc = _get_pacvue_mapping_service()
    try:
        item = svc.upsert_manual_mapping(
            profile_id=profile_id,
            campaign_name=payload.campaign_name,
            row_id=payload.row_id,
            goal_code=payload.goal_code,
            user_id=_user_id(user),
        )
        return {"ok": True, "item": item}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save manual mapping: {exc}",
        )


@router.post("/profiles/{profile_id}/pacvue/deactivate-mapping")
async def deactivate_pacvue_mapping(
    profile_id: str,
    payload: PacvueDeactivateMapPayload,
    user=Depends(require_admin_user),
):
    svc = _get_pacvue_mapping_service()
    try:
        deactivated = svc.deactivate_mapping(
            profile_id=profile_id,
            campaign_name=payload.campaign_name,
        )
        return {"ok": True, "deactivated": deactivated}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to deactivate mapping")


@router.post("/profiles/{profile_id}/pacvue/exclusion")
async def set_pacvue_campaign_exclusion(
    profile_id: str,
    payload: PacvueExclusionPayload,
    user=Depends(require_admin_user),
):
    svc = _get_pacvue_mapping_service()
    try:
        result = svc.set_exclusion(
            profile_id=profile_id,
            campaign_name=payload.campaign_name,
            excluded=payload.excluded,
            reason=payload.reason,
            user_id=_user_id(user),
        )
        return {"ok": True, **result}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to update campaign exclusion")


# ------------------------------------------------------------------
# Listings import endpoints
# ------------------------------------------------------------------


@router.get("/profiles/{profile_id}/listings/import-batches")
async def list_listing_import_batches(
    profile_id: str,
    user=Depends(require_admin_user),
):
    svc = _get_listing_service()
    try:
        batches = svc.list_import_batches(profile_id)
        return {"ok": True, "batches": batches}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list listings import batches")


@router.post("/profiles/{profile_id}/listings/import")
async def import_listing_file(
    profile_id: str,
    file: UploadFile = File(...),
    user=Depends(require_admin_user),
):
    svc = _get_listing_service()
    total = 0
    chunk_size = 2 * 1024 * 1024
    file_bytes = bytearray()

    try:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_MB * 1024 * 1024:
                raise HTTPException(status_code=413, detail="File too large")
            file_bytes.extend(chunk)
    finally:
        await file.close()

    try:
        result = svc.import_file(
            profile_id=profile_id,
            file_name=file.filename or "all_listings_report.txt",
            file_bytes=bytes(file_bytes),
            user_id=_user_id(user),
        )
        return {"ok": True, **result}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to import listings file")


@router.post("/profiles/{profile_id}/listings/import-windsor")
async def import_listing_file_from_windsor(
    profile_id: str,
    user=Depends(require_admin_user),
):
    svc = _get_listing_service()
    try:
        result = await svc.import_from_windsor(
            profile_id=profile_id,
            user_id=_user_id(user),
        )
        return {"ok": True, **result}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to import Windsor listings")


# ------------------------------------------------------------------
# ASIN mapping endpoints
# ------------------------------------------------------------------


@router.get("/profiles/{profile_id}/child-asins")
async def list_child_asins(
    profile_id: str,
    user=Depends(require_admin_user),
):
    svc = _get_asin_mapping_service()
    try:
        items = svc.list_child_asins(profile_id)
        return {"ok": True, "items": items}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list child ASINs")


@router.get("/profiles/{profile_id}/child-asins/mapping-export")
async def export_child_asin_mapping_csv(
    profile_id: str,
    user=Depends(require_admin_user),
):
    svc = _get_asin_mapping_service()
    try:
        csv_text = svc.export_child_asin_mapping_csv(profile_id)
        return Response(
            content=csv_text,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="wbr-asin-mapping-{profile_id}.csv"'
            },
        )
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to export ASIN mapping CSV")


@router.post("/profiles/{profile_id}/child-asins/mapping-import")
async def import_child_asin_mapping_csv(
    profile_id: str,
    file: UploadFile = File(...),
    user=Depends(require_admin_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="File name is required")

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {MAX_UPLOAD_MB} MB upload limit",
        )

    svc = _get_asin_mapping_service()
    try:
        summary = svc.import_child_asin_mapping_csv(
            profile_id=profile_id,
            file_name=file.filename,
            file_bytes=contents,
            user_id=_user_id(user),
        )
        return {"ok": True, "summary": summary}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to import ASIN mapping CSV")


@router.get("/profiles/{profile_id}/campaign-exclusions")
async def list_campaign_exclusions(
    profile_id: str,
    user=Depends(require_admin_user),
):
    svc = _get_campaign_exclusion_service()
    try:
        items = svc.list_exclusions(profile_id)
        return {"ok": True, "items": items}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list campaign exclusions")


@router.get("/profiles/{profile_id}/campaign-exclusions/export")
async def export_campaign_exclusions_csv(
    profile_id: str,
    user=Depends(require_admin_user),
):
    svc = _get_campaign_exclusion_service()
    try:
        csv_text = svc.export_exclusions_csv(profile_id)
        return Response(
            content=csv_text,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="wbr-campaign-exclusions-{profile_id}.csv"'
            },
        )
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to export campaign exclusions CSV")


@router.post("/profiles/{profile_id}/campaign-exclusions/import")
async def import_campaign_exclusions_csv(
    profile_id: str,
    file: UploadFile = File(...),
    user=Depends(require_admin_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="File name is required")

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {MAX_UPLOAD_MB} MB upload limit",
        )

    svc = _get_campaign_exclusion_service()
    try:
        summary = svc.import_exclusions_csv(
            profile_id=profile_id,
            file_name=file.filename,
            file_bytes=contents,
            user_id=_user_id(user),
        )
        return {"ok": True, "summary": summary}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to import campaign exclusions CSV")


@router.get("/profiles/{profile_id}/sync-runs")
async def list_sync_runs(
    profile_id: str,
    source_type: str = Query("windsor_business"),
    ad_product: str | None = Query(None),
    user=Depends(require_admin_user),
):
    svc = _get_sync_run_service()
    try:
        runs = svc.list_sync_runs(profile_id, source_type=source_type, ad_product=ad_product)
        return {"ok": True, "runs": runs}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list WBR sync runs")


@router.get("/profiles/{profile_id}/sync-coverage")
async def get_sync_coverage(
    profile_id: str,
    source_type: str = Query("windsor_business"),
    ad_product: str | None = Query(None),
    user=Depends(require_admin_user),
):
    svc = _get_sync_run_service()
    try:
        coverage = svc.get_sync_coverage(profile_id, source_type=source_type, ad_product=ad_product)
        return {"ok": True, **coverage}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to load WBR sync coverage")


@router.get("/profiles/{profile_id}/search-term-facts")
async def list_search_term_facts(
    profile_id: str,
    ad_product: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    campaign_type: str | None = Query(None),
    campaign_name_contains: str | None = Query(None),
    search_term_contains: str | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    user=Depends(require_admin_user),
):
    svc = _get_search_term_facts_service()
    try:
        result = svc.list_facts(
            profile_id,
            ad_product=ad_product,
            date_from=date_from,
            date_to=date_to,
            campaign_type=campaign_type,
            campaign_name_contains=campaign_name_contains,
            search_term_contains=search_term_contains,
            limit=limit,
            offset=offset,
        )
        return {"ok": True, **result}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list search term facts")


@router.get("/profiles/{profile_id}/search-term-facts/export")
async def export_search_term_facts_csv(
    profile_id: str,
    ad_product: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    campaign_type: str | None = Query(None),
    campaign_name_contains: str | None = Query(None),
    search_term_contains: str | None = Query(None),
    user=Depends(require_admin_user),
):
    svc = _get_search_term_facts_service()
    try:
        csv_text = svc.export_facts_csv(
            profile_id,
            ad_product=ad_product,
            date_from=date_from,
            date_to=date_to,
            campaign_type=campaign_type,
            campaign_name_contains=campaign_name_contains,
            search_term_contains=search_term_contains,
        )
        filename = f"search-term-data-{profile_id}.csv"
        return Response(
            content=csv_text,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to export search term facts")


@router.post("/profiles/{profile_id}/sync-runs/windsor-business/backfill")
async def run_windsor_business_backfill(
    profile_id: str,
    request: RunWindsorBusinessBackfillRequest,
    user=Depends(require_admin_user),
):
    svc = _get_windsor_business_sync_service()
    try:
        result = await svc.run_backfill(
            profile_id=profile_id,
            date_from=date.fromisoformat(request.date_from),
            date_to=date.fromisoformat(request.date_to),
            chunk_days=request.chunk_days,
            user_id=_user_id(user),
        )
        return {"ok": True, **result}
    except ValueError:
        raise HTTPException(status_code=400, detail="date_from and date_to must be YYYY-MM-DD")
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to run Windsor business backfill")


@router.post("/profiles/{profile_id}/sync-runs/windsor-business/daily-refresh")
async def run_windsor_business_daily_refresh(
    profile_id: str,
    user=Depends(require_admin_user),
):
    svc = _get_windsor_business_sync_service()
    try:
        result = await svc.run_daily_refresh(profile_id=profile_id, user_id=_user_id(user))
        return {"ok": True, **result}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to run Windsor business daily refresh")


@router.post("/profiles/{profile_id}/sync-runs/amazon-ads/backfill")
async def run_amazon_ads_backfill(
    profile_id: str,
    request: RunAmazonAdsBackfillRequest,
    user=Depends(require_admin_user),
):
    svc = _get_amazon_ads_sync_service()
    try:
        result = await svc.run_backfill(
            profile_id=profile_id,
            date_from=date.fromisoformat(request.date_from),
            date_to=date.fromisoformat(request.date_to),
            chunk_days=request.chunk_days,
            user_id=_user_id(user),
        )
        return {"ok": True, **result}
    except ValueError:
        raise HTTPException(status_code=400, detail="date_from and date_to must be YYYY-MM-DD")
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to run Amazon Ads backfill")


@router.post("/profiles/{profile_id}/sync-runs/amazon-ads/daily-refresh")
async def run_amazon_ads_daily_refresh(
    profile_id: str,
    user=Depends(require_admin_user),
):
    svc = _get_amazon_ads_sync_service()
    try:
        result = await svc.run_daily_refresh(profile_id=profile_id, user_id=_user_id(user))
        return {"ok": True, **result}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to run Amazon Ads daily refresh")


@router.post("/profiles/{profile_id}/sync-runs/search-terms/backfill")
async def run_search_term_backfill(
    profile_id: str,
    request: RunAmazonAdsBackfillRequest,
    user=Depends(require_admin_user),
):
    svc = _get_amazon_ads_search_term_sync_service()
    try:
        result = await svc.run_backfill(
            profile_id=profile_id,
            date_from=date.fromisoformat(request.date_from),
            date_to=date.fromisoformat(request.date_to),
            ad_product=request.ad_product,
            chunk_days=request.chunk_days,
            user_id=_user_id(user),
        )
        return {"ok": True, **result}
    except ValueError:
        raise HTTPException(status_code=400, detail="date_from and date_to must be YYYY-MM-DD")
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to run search-term backfill")


@router.post("/profiles/{profile_id}/sync-runs/search-terms/daily-refresh")
async def run_search_term_daily_refresh(
    profile_id: str,
    ad_product: str | None = Query(None),
    user=Depends(require_admin_user),
):
    svc = _get_amazon_ads_search_term_sync_service()
    try:
        result = await svc.run_daily_refresh(
            profile_id=profile_id,
            ad_product=ad_product,
            user_id=_user_id(user),
        )
        return {"ok": True, **result}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to run search-term daily refresh")


@router.get("/profiles/{profile_id}/section1-report")
async def get_section1_report(
    profile_id: str,
    weeks: int = Query(4, ge=1, le=12),
    user=Depends(require_admin_user),
):
    svc = _get_section1_report_service()
    try:
        report = svc.build_report(profile_id, weeks=weeks)
        return {"ok": True, **report}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to build Section 1 report")


@router.get("/profiles/{profile_id}/section2-report")
async def get_section2_report(
    profile_id: str,
    weeks: int = Query(4, ge=1, le=12),
    user=Depends(require_admin_user),
):
    svc = _get_section2_report_service()
    try:
        report = svc.build_report(profile_id, weeks=weeks)
        return {"ok": True, **report}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to build Section 2 report")


@router.get("/profiles/{profile_id}/section3-report")
async def get_section3_report(
    profile_id: str,
    weeks: int = Query(4, ge=1, le=12),
    user=Depends(require_admin_user),
):
    svc = _get_section3_report_service()
    try:
        report = svc.build_report(profile_id, weeks=weeks)
        return {"ok": True, **report}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to build Section 3 report")


@router.get("/profiles/{profile_id}/export.xlsx")
async def export_wbr_workbook(
    profile_id: str,
    weeks: int = Query(4, ge=1, le=12),
    hide_empty_rows: bool = Query(False),
    newest_first: bool = Query(True),
    user=Depends(require_admin_user),
):
    svc = _get_wbr_workbook_export_service()
    try:
        workbook_path, filename = svc.build_export(
            profile_id,
            weeks=weeks,
            hide_empty_rows=hide_empty_rows,
            newest_first=newest_first,
        )
        return FileResponse(
            workbook_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=filename,
        )
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to export WBR workbook")


# ------------------------------------------------------------------
# Sales Mix report
# ------------------------------------------------------------------


def _parse_csv_query(value: str | None) -> list[str]:
    if not value:
        return []
    return [chunk.strip() for chunk in value.split(",") if chunk.strip()]


def _parse_iso_date(field_name: str, value: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name} (expected YYYY-MM-DD)",
        ) from exc


@router.get("/profiles/{profile_id}/sales-mix")
async def get_sales_mix_report(
    profile_id: str,
    date_from: str = Query(..., description="ISO date (YYYY-MM-DD), inclusive"),
    date_to: str = Query(..., description="ISO date (YYYY-MM-DD), inclusive"),
    parent_row_ids: str | None = Query(None, description="Comma-separated row IDs"),
    ad_types: str | None = Query(
        None,
        description="Comma-separated subset of sponsored_products,sponsored_brands,sponsored_display",
    ),
    user=Depends(require_admin_user),
):
    parsed_from = _parse_iso_date("date_from", date_from)
    parsed_to = _parse_iso_date("date_to", date_to)
    svc = _get_sales_mix_service()
    try:
        return {
            "ok": True,
            **svc.build_report(
                profile_id,
                date_from=parsed_from,
                date_to=parsed_to,
                parent_row_ids=_parse_csv_query(parent_row_ids),
                ad_types=_parse_csv_query(ad_types),
            ),
        }
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to build Sales Mix report: {exc}",
        )


@router.get("/profiles/{profile_id}/sales-mix/export.xlsx")
async def export_sales_mix_workbook(
    profile_id: str,
    date_from: str = Query(..., description="ISO date (YYYY-MM-DD), inclusive"),
    date_to: str = Query(..., description="ISO date (YYYY-MM-DD), inclusive"),
    parent_row_ids: str | None = Query(None),
    ad_types: str | None = Query(None),
    user=Depends(require_admin_user),
):
    parsed_from = _parse_iso_date("date_from", date_from)
    parsed_to = _parse_iso_date("date_to", date_to)
    svc = _get_sales_mix_service()
    try:
        report = svc.build_report(
            profile_id,
            date_from=parsed_from,
            date_to=parsed_to,
            parent_row_ids=_parse_csv_query(parent_row_ids),
            ad_types=_parse_csv_query(ad_types),
        )
        profile = report.get("profile") or {}
        workbook_path, filename = build_sales_mix_workbook(
            report,
            profile_display_name=str(profile.get("display_name") or "wbr"),
            marketplace_code=str(profile.get("marketplace_code") or ""),
        )
        return FileResponse(
            workbook_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=filename,
        )
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export Sales Mix workbook: {exc}",
        )


@router.put("/profiles/{profile_id}/child-asins/{child_asin}/mapping")
async def set_child_asin_mapping(
    profile_id: str,
    child_asin: str,
    request: SetAsinMappingRequest,
    user=Depends(require_admin_user),
):
    svc = _get_asin_mapping_service()
    try:
        result = svc.set_child_asin_mapping(
            profile_id=profile_id,
            child_asin=child_asin,
            row_id=request.row_id,
            user_id=_user_id(user),
        )
        return {"ok": True, "mapping": result}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to save ASIN mapping")


# ------------------------------------------------------------------
# Amazon Ads OAuth + profile discovery
# ------------------------------------------------------------------


class AmazonAdsConnectRequest(BaseModel):
    region: str | None = Field(default=None, min_length=2, max_length=3)
    return_path: str = Field("", description="Frontend path to redirect to after OAuth")


class SelectAmazonAdsProfileRequest(BaseModel):
    amazon_ads_profile_id: str = Field(..., min_length=1)
    amazon_ads_account_id: Optional[str] = None
    amazon_ads_country_code: Optional[str] = None
    amazon_ads_currency_code: Optional[str] = None
    amazon_ads_marketplace_string_id: Optional[str] = None


@router.post("/profiles/{profile_id}/amazon-ads/connect")
async def amazon_ads_connect(
    profile_id: str,
    request: AmazonAdsConnectRequest,
    user=Depends(require_admin_user),
):
    """Generate the LWA authorization URL for connecting Amazon Ads."""
    svc = _get_service()
    try:
        svc.get_profile(profile_id)
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        region_code = normalize_ads_region_code(request.region)
        state = create_signed_state(
            profile_id=profile_id,
            initiated_by=_user_id(user),
            return_path=request.return_path,
            region_code=region_code,
        )
        url = build_authorization_url(state=state)
        return {"ok": True, "authorization_url": url, "region_code": region_code}
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to generate Amazon Ads authorization URL")


@router.get("/profiles/{profile_id}/amazon-ads/connection")
async def get_amazon_ads_connection(
    profile_id: str,
    user=Depends(require_admin_user),
):
    """Check whether this profile has a stored Amazon Ads connection."""
    svc = _get_service()
    try:
        profile = svc.get_profile(profile_id)
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    db = _get_supabase()

    # Prefer shared report_api_connections (keyed by client_id)
    client_id = str(profile.get("client_id") or "").strip()
    if client_id:
        shared_response = (
            db.table("report_api_connections")
            .select(
                "client_id, connection_status, connected_at, last_validated_at, "
                "last_error, updated_at, access_meta, region_code"
            )
            .eq("client_id", client_id)
            .eq("provider", "amazon_ads")
            .limit(1)
            .execute()
        )
        shared_rows = shared_response.data if isinstance(shared_response.data, list) else []
        if shared_rows:
            row = shared_rows[0]
            meta = row.get("access_meta") if isinstance(row.get("access_meta"), dict) else {}
            status = str(row.get("connection_status") or "").strip().lower()
            return {
                "ok": True,
                "connected": status == "connected",
                "source": "shared",
                "connection": {
                    "profile_id": profile_id,
                    "connection_status": status or "error",
                    "connected_at": row.get("connected_at"),
                    "region_code": row.get("region_code"),
                    "lwa_account_hint": meta.get("lwa_account_hint"),
                    "created_at": row.get("connected_at"),
                    "updated_at": row.get("updated_at"),
                },
            }

    # Fallback to legacy wbr_amazon_ads_connections
    response = (
        db.table("wbr_amazon_ads_connections")
        .select("profile_id, connected_at, lwa_account_hint, created_at, updated_at")
        .eq("profile_id", profile_id)
        .limit(1)
        .execute()
    )
    rows = response.data if isinstance(response.data, list) else []
    if not rows:
        return {"ok": True, "connected": False, "connection": None}

    return {
        "ok": True,
        "connected": True,
        "source": "legacy",
        "connection": {
            **rows[0],
            "connection_status": "connected",
        },
    }


@router.get("/profiles/{profile_id}/amazon-ads/profiles")
async def list_amazon_ads_profiles(
    profile_id: str,
    user=Depends(require_admin_user),
):
    """Discover available Amazon Ads advertiser profiles for this connection."""
    svc = _get_service()
    try:
        profile = svc.get_profile(profile_id)
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    db = _get_supabase()
    refresh_token = ""
    region_code = "NA"

    # Prefer shared report_api_connections (keyed by client_id)
    client_id = str(profile.get("client_id") or "").strip()
    if client_id:
        shared_response = (
            db.table("report_api_connections")
            .select("refresh_token, connection_status, region_code")
            .eq("client_id", client_id)
            .eq("provider", "amazon_ads")
            .limit(1)
            .execute()
        )
        shared_rows = shared_response.data if isinstance(shared_response.data, list) else []
        if shared_rows:
            shared_status = str(shared_rows[0].get("connection_status") or "").strip().lower()
            if shared_status == "connected":
                refresh_token = str(shared_rows[0].get("refresh_token") or "").strip()
                region_code = normalize_ads_region_code(shared_rows[0].get("region_code"))

    # Fallback to legacy wbr_amazon_ads_connections
    if not refresh_token:
        conn_response = (
            db.table("wbr_amazon_ads_connections")
            .select("amazon_ads_refresh_token")
            .eq("profile_id", profile_id)
            .limit(1)
            .execute()
        )
        conn_rows = conn_response.data if isinstance(conn_response.data, list) else []
        refresh_token = str(conn_rows[0].get("amazon_ads_refresh_token") or "").strip() if conn_rows else ""

    if not refresh_token:
        raise HTTPException(status_code=400, detail="No Amazon Ads connection found. Connect first.")

    try:
        access_token = await refresh_access_token(refresh_token)
        profiles = await list_advertising_profiles(access_token, region_code=region_code)
        return {"ok": True, "profiles": profiles}
    except WBRValidationError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch Amazon Ads profiles")


@router.post("/profiles/{profile_id}/amazon-ads/select-profile")
async def select_amazon_ads_profile(
    profile_id: str,
    request: SelectAmazonAdsProfileRequest,
    user=Depends(require_admin_user),
):
    """Save the chosen Amazon Ads profile/account IDs to the WBR profile."""
    svc = _get_service()
    try:
        updates = {
            "amazon_ads_profile_id": request.amazon_ads_profile_id,
            "amazon_ads_account_id": request.amazon_ads_account_id or None,
            "amazon_ads_country_code": request.amazon_ads_country_code or None,
            "amazon_ads_currency_code": request.amazon_ads_currency_code or None,
            "amazon_ads_marketplace_string_id": request.amazon_ads_marketplace_string_id or None,
        }
        profile = svc.update_profile(profile_id, updates, user_id=_user_id(user))
        return {"ok": True, "profile": profile}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to save Amazon Ads profile selection")


# ------------------------------------------------------------------
# WBR Snapshots
# ------------------------------------------------------------------


class CreateSnapshotRequest(BaseModel):
    weeks: int = Field(4, ge=1, le=12)
    snapshot_kind: str = Field("manual")
    include_raw: bool = Field(False)


@router.post("/profiles/{profile_id}/snapshots")
async def create_wbr_snapshot(
    profile_id: str,
    request: CreateSnapshotRequest,
    user=Depends(require_admin_user),
):
    """Build and persist a WBR digest snapshot."""
    svc = _get_snapshot_service()
    try:
        result = svc.create_snapshot(
            profile_id,
            weeks=request.weeks,
            snapshot_kind=request.snapshot_kind,
            include_raw=request.include_raw,
            created_by=_user_id(user),
        )
        return {"ok": True, "snapshot": result}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WBRValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to create WBR snapshot")


@router.get("/profiles/{profile_id}/snapshots")
async def list_wbr_snapshots(
    profile_id: str,
    limit: int = Query(10, ge=1, le=50),
    user=Depends(require_admin_user),
):
    """List recent snapshots for a profile."""
    svc = _get_snapshot_service()
    try:
        snapshots = svc.list_snapshots(profile_id, limit=limit)
        return {"ok": True, "snapshots": snapshots}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list WBR snapshots")


@router.get("/profiles/{profile_id}/snapshots/{snapshot_id}")
async def get_wbr_snapshot(
    profile_id: str,
    snapshot_id: str,
    user=Depends(require_admin_user),
):
    """Return a single snapshot with its full digest."""
    svc = _get_snapshot_service()
    try:
        snapshot = svc.get_snapshot(profile_id, snapshot_id)
        return {"ok": True, "snapshot": snapshot}
    except WBRNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to load WBR snapshot")


# ------------------------------------------------------------------
# WBR Email Drafts
# ------------------------------------------------------------------


@router.post("/clients/{client_id}/email-drafts")
async def create_email_draft(
    client_id: str,
    user=Depends(require_admin_user),
):
    """Generate a multi-marketplace WBR email draft for a client."""
    db = _get_supabase()
    try:
        draft = await generate_email_draft(db, client_id, created_by=_user_id(user))
        return {"ok": True, "draft": draft}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to generate email draft")


@router.get("/clients/{client_id}/email-drafts")
async def list_client_email_drafts(
    client_id: str,
    limit: int = Query(10, ge=1, le=50),
    user=Depends(require_admin_user),
):
    """List recent email drafts for a client (without full body)."""
    db = _get_supabase()
    try:
        drafts = list_email_drafts(db, client_id, limit=limit)
        return {"ok": True, "drafts": drafts}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list email drafts")


@router.get("/email-drafts/{draft_id}")
async def get_single_email_draft(
    draft_id: str,
    user=Depends(require_admin_user),
):
    """Return a single email draft with full body."""
    db = _get_supabase()
    try:
        draft = get_email_draft(db, draft_id)
        if not draft:
            raise HTTPException(status_code=404, detail="Email draft not found")
        return {"ok": True, "draft": draft}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to load email draft")
