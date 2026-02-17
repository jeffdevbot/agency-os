import os
from fastapi import APIRouter, Depends, HTTPException
from supabase import create_client, Client

from ..auth import require_admin_user
from ..config import settings
from ..services.sop_sync import SOPSyncService

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
