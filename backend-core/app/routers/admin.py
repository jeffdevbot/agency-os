import asyncio
import os
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import create_client, Client

from ..auth import require_admin_user
from ..config import settings
from ..services.sop_sync import SOPSyncService
from ..services.clickup_space_registry import (
    classify_clickup_space,
    list_clickup_spaces,
    map_clickup_space_to_brand,
    sync_clickup_spaces,
)
from ..services.clickup import get_clickup_service
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/sync-sops")
async def sync_sops(user=Depends(require_admin_user)):
    """
    Manually trigger sync of SOPs from ClickUp to Supabase.
    """
    if not settings.supabase_url or not settings.supabase_service_role:
        raise HTTPException(status_code=500, detail="Supabase credentials not configured")
        
    try:
        supabase: Client = create_client(settings.supabase_url, settings.supabase_service_role)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize Supabase client: {e}")

    clickup_token = os.environ.get("CLICKUP_API_TOKEN")
    if not clickup_token:
        raise HTTPException(status_code=500, detail="CLICKUP_API_TOKEN not set")

    service = SOPSyncService(clickup_token, supabase)
    
    try:
        results = await service.sync_all_sops()
        return {"status": "completed", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


# ---------------------------------------------------------------------------
# C6A: ClickUp Space Registry
# ---------------------------------------------------------------------------


class ClassifySpaceRequest(BaseModel):
    space_id: str
    classification: str


class MapBrandRequest(BaseModel):
    space_id: str
    brand_id: Optional[str] = None


class WBRSection1IngestRangeRequest(BaseModel):
    client_id: str = Field(..., min_length=1)
    account_id: str = Field(..., min_length=1)
    date_from: date
    date_to: date


class WBRSection1BackfillRequest(BaseModel):
    client_id: str = Field(..., min_length=1)
    account_id: str = Field(..., min_length=1)
    weeks: int = Field(4, ge=1, le=52)


def _get_supabase() -> Client:
    """Create a Supabase admin client or raise HTTPException."""
    if not settings.supabase_url or not settings.supabase_service_role:
        raise HTTPException(status_code=500, detail="Supabase credentials not configured")
    try:
        return create_client(settings.supabase_url, settings.supabase_service_role)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize Supabase client: {e}")


def _get_wbr_ingest_runtime() -> tuple[type, type]:
    """Lazy-load WBR ingest runtime to avoid startup failure when module is absent."""
    try:
        from ..services.wbr.windsor_section1_ingest import (
            WindsorSection1IngestError as _WindsorSection1IngestError,
            WindsorSection1IngestService as _WindsorSection1IngestService,
        )
        return _WindsorSection1IngestError, _WindsorSection1IngestService
    except ModuleNotFoundError as exc:
        raise HTTPException(status_code=503, detail="WBR ingest runtime not available") from exc


@router.post("/clickup-spaces/sync")
async def sync_spaces_endpoint(user=Depends(require_admin_user)):
    """Sync ClickUp spaces from the workspace into the registry."""
    db = _get_supabase()
    try:
        clickup = get_clickup_service()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ClickUp not configured: {e}")
    try:
        spaces = await clickup.list_spaces()
        result = await asyncio.to_thread(sync_clickup_spaces, db, spaces)
        return {"ok": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Space sync failed: {e}")
    finally:
        await clickup.aclose()


@router.get("/clickup-spaces")
async def list_spaces_endpoint(
    classification: Optional[str] = Query(None),
    include_inactive: bool = Query(False),
    user=Depends(require_admin_user),
):
    """List registered ClickUp spaces with optional filters."""
    db = _get_supabase()
    try:
        spaces = await asyncio.to_thread(
            list_clickup_spaces, db,
            classification=classification,
            include_inactive=include_inactive,
        )
        return {"spaces": spaces}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list spaces: {e}")


@router.post("/clickup-spaces/classify")
async def classify_space_endpoint(
    request: ClassifySpaceRequest,
    user=Depends(require_admin_user),
):
    """Update the classification of a registered ClickUp space."""
    db = _get_supabase()
    try:
        space = await asyncio.to_thread(
            classify_clickup_space, db, request.space_id, request.classification
        )
        return {"ok": True, "space": space}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Classification failed: {e}")


@router.post("/clickup-spaces/map-brand")
async def map_brand_endpoint(
    request: MapBrandRequest,
    user=Depends(require_admin_user),
):
    """Map (or unmap) a registered ClickUp space to a brand."""
    db = _get_supabase()
    try:
        space = await asyncio.to_thread(
            map_clickup_space_to_brand, db, request.space_id, request.brand_id
        )
        return {"ok": True, "space": space}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Brand mapping failed: {e}")


@router.post("/wbr/section1/ingest-range")
async def wbr_section1_ingest_range(
    request: WBRSection1IngestRangeRequest,
    user=Depends(require_admin_user),
):
    """Ingest Windsor Section 1 data for an explicit date range."""
    wbr_error_cls, wbr_service_cls = _get_wbr_ingest_runtime()
    db = _get_supabase()
    service = wbr_service_cls(db)
    try:
        result = await service.ingest_range(
            client_id=request.client_id,
            account_id=request.account_id,
            date_from=request.date_from,
            date_to=request.date_to,
            initiated_by=str(user.get("sub")) if isinstance(user, dict) else None,
        )
        return result
    except wbr_error_cls as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"WBR Section 1 ingest failed: {e}")


@router.post("/wbr/section1/backfill-last-full-weeks")
async def wbr_section1_backfill_last_full_weeks(
    request: WBRSection1BackfillRequest,
    user=Depends(require_admin_user),
):
    """Ingest previous full Sunday-Saturday weeks, most-recent first."""
    if request.weeks <= 0:
        raise HTTPException(status_code=400, detail="weeks must be > 0")

    wbr_error_cls, wbr_service_cls = _get_wbr_ingest_runtime()
    db = _get_supabase()
    service = wbr_service_cls(db)
    try:
        result = await service.ingest_previous_full_weeks(
            client_id=request.client_id,
            account_id=request.account_id,
            weeks=request.weeks,
            initiated_by=str(user.get("sub")) if isinstance(user, dict) else None,
        )
        return result
    except wbr_error_cls as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"WBR Section 1 backfill failed: {e}")
