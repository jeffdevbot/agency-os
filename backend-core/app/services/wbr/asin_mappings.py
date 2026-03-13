"""ASIN mapping service for WBR v2."""

from __future__ import annotations

from typing import Any

from supabase import Client

from .profiles import WBRNotFoundError, WBRValidationError


class AsinMappingService:
    def __init__(self, db: Client) -> None:
        self.db = db

    def list_child_asins(self, profile_id: str) -> list[dict[str, Any]]:
        self._get_profile(profile_id)

        child_response = (
            self.db.table("wbr_profile_child_asins")
            .select("*")
            .eq("profile_id", profile_id)
            .eq("active", True)
            .execute()
        )
        child_rows = child_response.data if isinstance(child_response.data, list) else []

        mapping_response = (
            self.db.table("wbr_asin_row_map")
            .select("child_asin,row_id")
            .eq("profile_id", profile_id)
            .eq("active", True)
            .execute()
        )
        mappings = mapping_response.data if isinstance(mapping_response.data, list) else []
        mapping_by_asin = {
            str(row["child_asin"]): str(row["row_id"])
            for row in mappings
            if isinstance(row, dict) and row.get("child_asin") and row.get("row_id")
        }

        row_response = (
            self.db.table("wbr_rows")
            .select("id,row_label,active")
            .eq("profile_id", profile_id)
            .eq("row_kind", "leaf")
            .execute()
        )
        leaf_rows = row_response.data if isinstance(row_response.data, list) else []
        row_by_id = {
            str(row["id"]): row
            for row in leaf_rows
            if isinstance(row, dict) and row.get("id")
        }

        results: list[dict[str, Any]] = []
        for row in child_rows:
            if not isinstance(row, dict):
                continue
            child_asin = str(row.get("child_asin") or "").strip()
            if not child_asin:
                continue
            mapped_row_id = mapping_by_asin.get(child_asin)
            mapped_row = row_by_id.get(mapped_row_id) if mapped_row_id else None
            results.append(
                {
                    "id": row.get("id"),
                    "profile_id": row.get("profile_id"),
                    "listing_batch_id": row.get("listing_batch_id"),
                    "child_asin": child_asin,
                    "child_sku": row.get("child_sku"),
                    "child_product_name": row.get("child_product_name"),
                    "category": row.get("category"),
                    "fulfillment_method": row.get("fulfillment_method"),
                    "source_item_style": row.get("source_item_style"),
                    "active": bool(row.get("active")),
                    "mapped_row_id": mapped_row_id,
                    "mapped_row_label": mapped_row.get("row_label") if mapped_row else None,
                    "mapped_row_active": bool(mapped_row.get("active")) if mapped_row else None,
                    "created_at": row.get("created_at"),
                    "updated_at": row.get("updated_at"),
                }
            )

        results.sort(
            key=lambda item: (
                str(item.get("child_product_name") or "").lower(),
                str(item.get("child_asin") or "").lower(),
            )
        )
        return results

    def set_child_asin_mapping(
        self,
        *,
        profile_id: str,
        child_asin: str,
        row_id: str | None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        self._get_profile(profile_id)
        child = self._get_child_asin(profile_id, child_asin)
        existing = self._get_active_mapping(profile_id, child_asin)

        if row_id is None:
            if existing:
                updates: dict[str, Any] = {"active": False}
                if user_id:
                    updates["updated_by"] = user_id
                (
                    self.db.table("wbr_asin_row_map")
                    .update(updates)
                    .eq("id", existing["id"])
                    .execute()
                )
            return {
                "child_asin": child["child_asin"],
                "mapped_row_id": None,
                "mapped_row_label": None,
                "mapped_row_active": None,
            }

        row = self._get_leaf_row(profile_id, row_id)

        if existing and str(existing.get("row_id")) == row_id:
            return {
                "child_asin": child["child_asin"],
                "mapped_row_id": row_id,
                "mapped_row_label": row["row_label"],
                "mapped_row_active": bool(row.get("active")),
            }

        if existing:
            updates = {"active": False}
            if user_id:
                updates["updated_by"] = user_id
            (
                self.db.table("wbr_asin_row_map")
                .update(updates)
                .eq("id", existing["id"])
                .execute()
            )

        payload: dict[str, Any] = {
            "profile_id": profile_id,
            "child_asin": child_asin,
            "row_id": row_id,
            "mapping_source": "manual",
            "active": True,
        }
        if user_id:
            payload["created_by"] = user_id
            payload["updated_by"] = user_id

        response = self.db.table("wbr_asin_row_map").insert(payload).execute()
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise WBRValidationError("Failed to save ASIN mapping")

        return {
            "child_asin": child["child_asin"],
            "mapped_row_id": row_id,
            "mapped_row_label": row["row_label"],
            "mapped_row_active": bool(row.get("active")),
        }

    def _get_profile(self, profile_id: str) -> dict[str, Any]:
        response = (
            self.db.table("wbr_profiles")
            .select("id")
            .eq("id", profile_id)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise WBRNotFoundError(f"Profile {profile_id} not found")
        return rows[0]

    def _get_child_asin(self, profile_id: str, child_asin: str) -> dict[str, Any]:
        response = (
            self.db.table("wbr_profile_child_asins")
            .select("*")
            .eq("profile_id", profile_id)
            .eq("child_asin", child_asin)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise WBRNotFoundError(f"Child ASIN {child_asin} not found for profile {profile_id}")
        return rows[0]

    def _get_leaf_row(self, profile_id: str, row_id: str) -> dict[str, Any]:
        response = (
            self.db.table("wbr_rows")
            .select("*")
            .eq("id", row_id)
            .eq("profile_id", profile_id)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise WBRNotFoundError(f"Row {row_id} not found for profile {profile_id}")
        row = rows[0]
        if row.get("row_kind") != "leaf":
            raise WBRValidationError("ASIN mappings must target leaf rows")
        return row

    def _get_active_mapping(self, profile_id: str, child_asin: str) -> dict[str, Any] | None:
        response = (
            self.db.table("wbr_asin_row_map")
            .select("*")
            .eq("profile_id", profile_id)
            .eq("child_asin", child_asin)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        return rows[0] if rows else None
