import asyncio
from datetime import datetime
from typing import Any

import httpx

from supabase import Client

class SOPSyncService:
    WORKSPACE_ID = "42600885"

    # Known SOP pages to sync
    SOP_PAGES = [
        {"doc_id": "18m2dn-4417", "page_id": "18m2dn-1997", "category": "ngram"},
    ]

    def __init__(self, clickup_token: str, supabase_client: Client):
        self.token = clickup_token
        self.db = supabase_client

    async def fetch_page(self, doc_id: str, page_id: str) -> dict[str, Any]:
        """Fetch a single page from ClickUp v3 API."""
        url = f"https://api.clickup.com/api/v3/workspaces/{self.WORKSPACE_ID}/docs/{doc_id}/pages/{page_id}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": self.token,
                    "Content-Type": "application/json"
                }
            )
            response.raise_for_status()
            return response.json()

    async def sync_all_sops(self) -> dict[str, str]:
        """Sync all known SOP pages to Supabase."""
        results = {}
        
        for sop in self.SOP_PAGES:
            try:
                page = await self.fetch_page(sop["doc_id"], sop["page_id"])
                
                # Extract content
                # v3 API returns page object with 'content' field (markdown/html? Guide says content_md)
                # fetch-clickup-doc.ts says field is 'content'
                
                content = page.get("content", "")
                name = page.get("name", "Untitled")

                # Upsert to Supabase
                data = {
                    "clickup_doc_id": sop["doc_id"],
                    "clickup_page_id": sop["page_id"],
                    "name": name,
                    "content_md": content,
                    "category": sop["category"],
                    "last_synced_at": datetime.utcnow().isoformat()
                }

                # Using supabase-py client
                # 'on_conflict' handled by primary key? Schema says UNIQUE(clickup_doc_id, clickup_page_id)
                # We should use on_conflict argument if supported or just upsert logic.
                # Supabase-py table(...).upsert(...) works.
                
                # Note: supabase-py upsert options might need 'on_conflict' columns specified if not PK.
                # Schema: id is PK. UNIQUE(clickup_doc_id, clickup_page_id). 
                # So we likely need to specify on_conflict='clickup_doc_id,clickup_page_id'.
                
                self.db.table("playbook_sops").upsert(
                    data, 
                    on_conflict="clickup_doc_id,clickup_page_id"
                ).execute()

                results[sop["category"]] = "synced"
                print(f"Synced SOP: {name} ({sop['category']})")
                
            except Exception as e:
                print(f"Failed to sync {sop['category']}: {e}")
                results[sop["category"]] = f"error: {str(e)}"
                
        return results

    def _get_sop_by_category_sync(self, category: str) -> dict[str, Any] | None:
        category = (category or "").strip()
        if not category:
            return None

        response = (
            self.db.table("playbook_sops")
            .select("*")
            .eq("category", category)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            return None
        return rows[0] if isinstance(rows[0], dict) else None

    async def get_sop_by_category(self, category: str) -> dict[str, Any] | None:
        """Get SOP content by category without blocking the event loop."""
        return await asyncio.to_thread(self._get_sop_by_category_sync, category)
