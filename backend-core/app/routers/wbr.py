"""WBR v2 admin router – profile and row management."""

from __future__ import annotations

import os

from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from supabase import Client, create_client

from ..auth import require_admin_user
from ..config import settings
from ..services.wbr.listing_imports import ListingImportService
from ..services.wbr.pacvue_imports import PacvueImportService
from ..services.wbr.profiles import WBRNotFoundError, WBRValidationError, WBRProfileService

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


def _get_listing_service() -> ListingImportService:
    return ListingImportService(_get_supabase())


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
    backfill_start_date: Optional[str] = None
    daily_rewrite_days: int = Field(14, ge=1, le=60)


class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = None
    week_start_day: Optional[str] = None
    status: Optional[str] = None
    windsor_account_id: Optional[str] = None
    amazon_ads_profile_id: Optional[str] = None
    amazon_ads_account_id: Optional[str] = None
    backfill_start_date: Optional[str] = None
    daily_rewrite_days: Optional[int] = Field(None, ge=1, le=60)


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
