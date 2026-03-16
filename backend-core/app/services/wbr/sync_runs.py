from __future__ import annotations

from typing import Any

from supabase import Client

from .profiles import WBRProfileService, WBRValidationError

VALID_WBR_SYNC_SOURCE_TYPES = {
    "windsor_business",
    "windsor_inventory",
    "windsor_returns",
    "amazon_ads",
    "pacvue_import",
    "listing_import",
}


class WBRSyncRunService:
    def __init__(self, db: Client) -> None:
        self.db = db
        self._profiles = WBRProfileService(db)

    def list_sync_runs(self, profile_id: str, *, source_type: str) -> list[dict[str, Any]]:
        self._profiles.get_profile(profile_id)
        if source_type not in VALID_WBR_SYNC_SOURCE_TYPES:
            allowed = ", ".join(sorted(VALID_WBR_SYNC_SOURCE_TYPES))
            raise WBRValidationError(f"source_type must be one of: {allowed}")

        response = (
            self.db.table("wbr_sync_runs")
            .select("*")
            .eq("profile_id", profile_id)
            .eq("source_type", source_type)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        return response.data if isinstance(response.data, list) else []
