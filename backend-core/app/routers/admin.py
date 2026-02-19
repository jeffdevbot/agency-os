import asyncio
import os
from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import create_client, Client

from ..auth import require_admin_user
from ..config import settings
from ..services.sop_sync import SOPSyncService
from ..services.agencyclaw.identity_sync_runtime import run_identity_sync
from ..services.agencyclaw.clickup_space_registry import (
    classify_clickup_space,
    list_clickup_spaces,
    map_clickup_space_to_brand,
    sync_clickup_spaces,
)
from ..services.clickup import get_clickup_service
from pydantic import BaseModel
from typing import List, Optional

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


# Pydantic models for request validation
class SlackUserRequest(BaseModel):
    slack_user_id: str
    email: Optional[str] = None
    real_name: Optional[str] = None

class ClickUpUserRequest(BaseModel):
    clickup_user_id: str
    email: Optional[str] = None
    username: Optional[str] = None

class IdentitySyncRequest(BaseModel):
    dry_run: bool = True
    slack_users: List[SlackUserRequest]
    clickup_users: List[ClickUpUserRequest]

@router.post("/identity-sync/run")
async def run_identity_sync_endpoint(
    request: IdentitySyncRequest,
    user=Depends(require_admin_user)
):
    """
    Run identity reconciliation and sync.
    """
    if not settings.supabase_url or not settings.supabase_service_role:
        raise HTTPException(status_code=500, detail="Supabase credentials not configured")
        
    try:
        supabase: Client = create_client(settings.supabase_url, settings.supabase_service_role)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize Supabase client: {e}")

    # Convert Pydantic models to dicts for the service layer
    slack_dicts = [u.model_dump() for u in request.slack_users]
    clickup_dicts = [u.model_dump() for u in request.clickup_users]

    try:
        results = run_identity_sync(
            supabase,
            slack_users=slack_dicts,
            clickup_users=clickup_dicts,
            dry_run=request.dry_run
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Identity sync failed: {str(e)}")


# ---------------------------------------------------------------------------
# C6A: ClickUp Space Registry
# ---------------------------------------------------------------------------


class ClassifySpaceRequest(BaseModel):
    space_id: str
    classification: str


class MapBrandRequest(BaseModel):
    space_id: str
    brand_id: Optional[str] = None


def _get_supabase() -> Client:
    """Create a Supabase admin client or raise HTTPException."""
    if not settings.supabase_url or not settings.supabase_service_role:
        raise HTTPException(status_code=500, detail="Supabase credentials not configured")
    try:
        return create_client(settings.supabase_url, settings.supabase_service_role)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize Supabase client: {e}")


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
