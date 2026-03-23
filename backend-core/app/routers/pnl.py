"""Monthly P&L admin API router."""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..auth import require_admin_user, _get_supabase_admin_client
from ..services.pnl.profiles import (
    PNLDuplicateFileError,
    PNLNotFoundError,
    PNLProfileService,
    PNLValidationError,
)
from ..services.pnl.report import PNLReportService
from ..services.pnl.transaction_import import TransactionImportService
from ..services.pnl.workbook import PNLWorkbookExportService
from ..services.pnl.windsor_compare import WindsorSettlementCompareService
from ..services.pnl.yoy_report import PNLYoYReportService

router = APIRouter(prefix="/admin/pnl", tags=["pnl-admin"])
logger = logging.getLogger(__name__)

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "40"))


def _get_profile_service() -> PNLProfileService:
    return PNLProfileService(_get_supabase_admin_client())


def _get_import_service() -> TransactionImportService:
    return TransactionImportService(_get_supabase_admin_client())


def _get_report_service() -> PNLReportService:
    return PNLReportService(_get_supabase_admin_client())


def _get_workbook_export_service() -> PNLWorkbookExportService:
    return PNLWorkbookExportService(_get_supabase_admin_client())


def _get_windsor_compare_service() -> WindsorSettlementCompareService:
    return WindsorSettlementCompareService(_get_supabase_admin_client())


def _get_yoy_report_service() -> PNLYoYReportService:
    return PNLYoYReportService(_get_supabase_admin_client())


# ── Request / response models ────────────────────────────────────────


class CreateProfileRequest(BaseModel):
    client_id: str = Field(..., min_length=1)
    marketplace_code: str = Field(..., min_length=1)
    currency_code: str = Field(default="USD")
    notes: str | None = None


class SaveSkuCogsEntry(BaseModel):
    sku: str = Field(..., min_length=1)
    unit_cost: str | float | int | None = None


class SaveSkuCogsRequest(BaseModel):
    entries: list[SaveSkuCogsEntry] = Field(default_factory=list)


class SaveOtherExpenseTypeRequest(BaseModel):
    key: str = Field(..., min_length=1)
    enabled: bool = False


class SaveOtherExpenseMonthRequest(BaseModel):
    entry_month: str = Field(..., pattern=r"^\d{4}-\d{2}-01$")
    values: dict[str, str | float | int | None] = Field(default_factory=dict)


class SaveOtherExpensesRequest(BaseModel):
    start_month: str = Field(..., pattern=r"^\d{4}-\d{2}-01$")
    end_month: str = Field(..., pattern=r"^\d{4}-\d{2}-01$")
    expense_types: list[SaveOtherExpenseTypeRequest] = Field(default_factory=list)
    months: list[SaveOtherExpenseMonthRequest] = Field(default_factory=list)


# ── Profile endpoints ────────────────────────────────────────────────


@router.get("/profiles")
def list_profiles(
    client_id: str = Query(..., min_length=1),
    user=Depends(require_admin_user),
):
    svc = _get_profile_service()
    try:
        profiles = svc.list_profiles(client_id)
        return {"ok": True, "profiles": profiles}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list P&L profiles")


@router.post("/profiles")
def create_profile(
    body: CreateProfileRequest,
    user=Depends(require_admin_user),
):
    svc = _get_profile_service()
    user_id = str(user.get("sub") or "").strip() or None
    try:
        profile = svc.create_profile(
            client_id=body.client_id,
            marketplace_code=body.marketplace_code,
            currency_code=body.currency_code,
            notes=body.notes,
            user_id=user_id,
        )
        return {"ok": True, "profile": profile}
    except PNLValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to create P&L profile")


@router.get("/profiles/{profile_id}")
def get_profile(
    profile_id: str,
    user=Depends(require_admin_user),
):
    svc = _get_profile_service()
    try:
        profile = svc.get_profile(profile_id)
        return {"ok": True, "profile": profile}
    except PNLNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to get P&L profile")


# ── Import endpoints ─────────────────────────────────────────────────


@router.get("/profiles/{profile_id}/imports")
def list_imports(
    profile_id: str,
    user=Depends(require_admin_user),
):
    svc = _get_profile_service()
    try:
        imports = svc.list_imports(profile_id)
        return {"ok": True, "imports": imports}
    except PNLNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list imports")


@router.get("/profiles/{profile_id}/imports/{import_id}")
def get_import_summary(
    profile_id: str,
    import_id: str,
    user=Depends(require_admin_user),
):
    svc = _get_profile_service()
    try:
        summary = svc.get_import_summary(profile_id, import_id)
        return {"ok": True, **summary}
    except PNLNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to get import summary")


@router.get("/profiles/{profile_id}/import-months")
def list_import_months(
    profile_id: str,
    user=Depends(require_admin_user),
):
    svc = _get_profile_service()
    try:
        months = svc.list_import_months(profile_id)
        return {"ok": True, "months": months}
    except PNLNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list import months")


@router.get("/profiles/{profile_id}/cogs-skus")
def list_cogs_skus(
    profile_id: str,
    user=Depends(require_admin_user),
):
    svc = _get_profile_service()
    try:
        skus = svc.list_sku_cogs(profile_id)
        return {"ok": True, "skus": skus}
    except PNLNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PNLValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list COGS SKUs")


@router.put("/profiles/{profile_id}/cogs-skus")
def save_cogs_skus(
    profile_id: str,
    body: SaveSkuCogsRequest,
    user=Depends(require_admin_user),
):
    svc = _get_profile_service()
    try:
        svc.save_sku_cogs(profile_id, [entry.model_dump() for entry in body.entries])
        return {"ok": True}
    except PNLNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PNLValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to save COGS SKUs")


@router.get("/profiles/{profile_id}/other-expenses")
def list_other_expenses(
    profile_id: str,
    start_month: str = Query(..., pattern=r"^\d{4}-\d{2}-01$"),
    end_month: str = Query(..., pattern=r"^\d{4}-\d{2}-01$"),
    user=Depends(require_admin_user),
):
    svc = _get_profile_service()
    try:
        payload = svc.list_other_expenses(profile_id, start_month, end_month)
        return {"ok": True, **payload}
    except PNLNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PNLValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to list other expenses")


@router.put("/profiles/{profile_id}/other-expenses")
def save_other_expenses(
    profile_id: str,
    body: SaveOtherExpensesRequest,
    user=Depends(require_admin_user),
):
    svc = _get_profile_service()
    try:
        svc.save_other_expenses(
            profile_id,
            body.start_month,
            body.end_month,
            [entry.model_dump() for entry in body.expense_types],
            [entry.model_dump() for entry in body.months],
        )
        return {"ok": True}
    except PNLNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PNLValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to save other expenses")


# ── Transaction upload endpoint ──────────────────────────────────────


@router.post("/profiles/{profile_id}/transaction-upload")
async def upload_transaction_report(
    profile_id: str,
    file: UploadFile = File(...),
    user=Depends(require_admin_user),
):
    """Upload and queue an Amazon Monthly Unified Transaction Report CSV."""
    file_name = file.filename or "unknown.csv"
    lower_name = file_name.lower()
    if not lower_name.endswith((".csv", ".txt", ".tsv")):
        raise HTTPException(status_code=400, detail="Transaction upload supports .csv, .txt, and .tsv files")

    # Read file with size check
    chunks: list[bytes] = []
    total = 0
    chunk_size = 2 * 1024 * 1024
    try:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_MB * 1024 * 1024:
                raise HTTPException(
                    status_code=413,
                    detail=f"File exceeds {MAX_UPLOAD_MB}MB limit",
                )
            chunks.append(chunk)
    finally:
        await file.close()

    file_bytes = b"".join(chunks)
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    user_id = str(user.get("sub") or "").strip() or None
    svc = _get_import_service()
    try:
        result = svc.enqueue_file(
            profile_id=profile_id,
            file_name=file_name,
            file_bytes=file_bytes,
            user_id=user_id,
        )
        return {"ok": True, **result}
    except PNLNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PNLDuplicateFileError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except PNLValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Transaction import failed")


# ── Report endpoint ─────────────────────────────────────────────────


@router.get("/profiles/{profile_id}/report")
async def get_pnl_report(
    profile_id: str,
    filter_mode: str = Query("ytd", pattern="^(ytd|last_3|last_6|last_12|last_year|range)$"),
    start_month: str | None = Query(None),
    end_month: str | None = Query(None),
    user=Depends(require_admin_user),
):
    """Build and return the Monthly P&L report."""
    svc = _get_report_service()
    try:
        report = await svc.build_report_async(
            profile_id,
            filter_mode=filter_mode,
            start_month=start_month,
            end_month=end_month,
        )
        return {"ok": True, **report}
    except PNLNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PNLValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to build P&L report")


@router.get("/profiles/{profile_id}/yoy-report")
async def get_pnl_yoy_report(
    profile_id: str,
    year: int = Query(..., ge=2020),
    user=Depends(require_admin_user),
):
    svc = _get_yoy_report_service()
    try:
        report = await svc.build_yoy_report_async(profile_id, year=year)
        return {"ok": True, **report}
    except PNLNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PNLValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("Failed to build P&L YoY report for profile %s year %s", profile_id, year)
        raise HTTPException(status_code=500, detail="Failed to build P&L YoY report")


@router.get("/profiles/{profile_id}/windsor-compare")
async def get_windsor_month_compare(
    profile_id: str,
    entry_month: str = Query(..., pattern=r"^\d{4}-\d{2}-01$"),
    marketplace_scope: str = Query("all"),
    user=Depends(require_admin_user),
):
    svc = _get_windsor_compare_service()
    try:
        comparison = await svc.compare_month(profile_id, entry_month, marketplace_scope)
        return {"ok": True, **comparison}
    except PNLNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PNLValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to compare Windsor settlement data")


@router.get("/profiles/{profile_id}/export.xlsx")
async def export_pnl_workbook(
    profile_id: str,
    view_mode: str = Query("standard", pattern="^(standard|yoy)$"),
    filter_mode: str = Query("ytd", pattern="^(ytd|last_3|last_6|last_12|last_year|range)$"),
    start_month: str | None = Query(None),
    end_month: str | None = Query(None),
    year: int | None = Query(None, ge=2020),
    show_totals: bool = Query(True),
    user=Depends(require_admin_user),
):
    svc = _get_workbook_export_service()
    try:
        workbook_path, filename = await svc.build_export_async(
            profile_id,
            view_mode=view_mode,
            filter_mode=filter_mode,
            start_month=start_month,
            end_month=end_month,
            year=year,
            show_totals=show_totals,
        )
        return FileResponse(
            workbook_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=filename,
        )
    except PNLNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PNLValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to export P&L workbook")
