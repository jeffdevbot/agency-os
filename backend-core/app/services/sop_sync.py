import asyncio
from datetime import datetime
from typing import Any

import httpx

from supabase import Client


class SOPSyncService:
    """
    Service for syncing SOP content from ClickUp Docs to Supabase.

    SOP registry is stored in playbook_sops table:
    - clickup_doc_id, clickup_page_id: Source location in ClickUp
    - category: Canonical identifier (e.g., 'ngram', 'hv_kw')
    - aliases: Alternative names for natural language lookup
    - content_md: Synced content (updated by sync_all_sops)
    """

    WORKSPACE_ID = "42600885"

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
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            return response.json()

    def _get_all_sop_configs_sync(self) -> list[dict[str, Any]]:
        """Get all SOP configurations from database (sync version)."""
        response = (
            self.db.table("playbook_sops")
            .select("clickup_doc_id, clickup_page_id, category")
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        return [r for r in rows if isinstance(r, dict) and r.get("clickup_doc_id")]

    async def sync_all_sops(self) -> dict[str, str]:
        """
        Sync all SOPs registered in the database.

        Reads SOP configurations from playbook_sops table, fetches content
        from ClickUp, and updates the content_md field.
        """
        results = {}

        # Get SOP configs from database (not hardcoded)
        sop_configs = await asyncio.to_thread(self._get_all_sop_configs_sync)

        if not sop_configs:
            print("No SOPs registered in playbook_sops table. Run seed migration first.")
            return {"error": "no_sops_registered"}

        for sop in sop_configs:
            doc_id = sop.get("clickup_doc_id", "")
            page_id = sop.get("clickup_page_id", "")
            category = sop.get("category", "unknown")

            if not doc_id or not page_id:
                results[category] = "error: missing doc_id or page_id"
                continue

            try:
                page = await self.fetch_page(doc_id, page_id)

                content = page.get("content", "")
                name = page.get("name", "Untitled")

                # Update content and name (preserve category and aliases from seed)
                update_response = (
                    self.db.table("playbook_sops")
                    .update(
                        {
                            "name": name,
                            "content_md": content,
                            "last_synced_at": datetime.utcnow().isoformat(),
                        }
                    )
                    .eq("clickup_doc_id", doc_id)
                    .eq("clickup_page_id", page_id)
                    .select("id")
                    .execute()
                )
                updated_rows = (
                    update_response.data if isinstance(update_response.data, list) else []
                )
                if not updated_rows:
                    raise RuntimeError(
                        f"no playbook_sops row found for doc_id={doc_id}, page_id={page_id}"
                    )

                results[category] = "synced"
                print(f"Synced SOP: {name} ({category})")

            except Exception as e:
                print(f"Failed to sync {category}: {e}")
                results[category] = f"error: {str(e)}"

        return results

    def _get_sop_by_category_sync(self, category: str) -> dict[str, Any] | None:
        """Get SOP by exact category match (sync version)."""
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

    def _get_sop_by_alias_sync(self, alias: str) -> dict[str, Any] | None:
        """Get SOP by alias (sync version) using safe exact-match in Python."""
        alias_norm = " ".join((alias or "").strip().lower().split())
        if not alias_norm:
            return None

        response = self.db.table("playbook_sops").select("*").execute()
        rows = response.data if isinstance(response.data, list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            aliases = row.get("aliases")
            if not isinstance(aliases, list):
                continue
            for candidate in aliases:
                if not isinstance(candidate, str):
                    continue
                candidate_norm = " ".join(candidate.strip().lower().split())
                if candidate_norm == alias_norm:
                    return row
        return None

    def _list_categories_sync(self) -> list[str]:
        """List all available SOP categories (sync version)."""
        response = self.db.table("playbook_sops").select("category").execute()
        rows = response.data if isinstance(response.data, list) else []
        categories = []
        for row in rows:
            if isinstance(row, dict) and row.get("category"):
                categories.append(str(row["category"]))
        return sorted(set(categories))

    async def get_sop_by_category(self, category: str) -> dict[str, Any] | None:
        """Get SOP content by exact category match."""
        return await asyncio.to_thread(self._get_sop_by_category_sync, category)

    async def get_sop_by_alias(self, alias: str) -> dict[str, Any] | None:
        """Get SOP content by alias (natural language lookup)."""
        return await asyncio.to_thread(self._get_sop_by_alias_sync, alias)

    async def get_sop_by_category_or_alias(self, query: str) -> dict[str, Any] | None:
        """
        Get SOP by category or alias.

        First tries exact category match, then falls back to alias lookup.
        This is the primary method for AI tool lookups.
        """
        # Try exact category first
        sop = await self.get_sop_by_category(query)
        if sop:
            return sop

        # Fall back to alias lookup
        return await self.get_sop_by_alias(query)

    async def list_categories(self) -> list[str]:
        """List all available SOP categories."""
        return await asyncio.to_thread(self._list_categories_sync)
