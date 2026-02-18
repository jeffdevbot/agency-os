import os
from fastapi import APIRouter, Depends, HTTPException
from supabase import create_client, Client

from ..auth import require_admin_user
from ..config import settings
from ..services.sop_sync import SOPSyncService
from ..services.agencyclaw.identity_sync_runtime import run_identity_sync
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
