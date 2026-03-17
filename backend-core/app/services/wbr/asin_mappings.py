"""ASIN mapping service for WBR v2."""

from __future__ import annotations

import csv
import io
from typing import Any

from supabase import Client

from .profiles import WBRNotFoundError, WBRValidationError

CSV_IMPORT_ALLOWED_EXTENSIONS = (".csv",)
CSV_IMPORT_COLUMN_ALIASES = {
    "child_asin": {"child_asin", "child asin", "asin"},
    "mapped_row_id": {
        "mapped_row_id",
        "mapped row id",
        "current_row_id",
        "current row id",
        "row_id",
        "row id",
    },
    "mapped_row_label": {
        "mapped_row_label",
        "mapped row label",
        "current_row_label",
        "current row label",
        "row_label",
        "row label",
    },
}

_BATCH_SIZE = 500


def _decode_csv_text(file_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise WBRValidationError("Unable to decode ASIN mapping CSV")


def _canonicalize_column_name(value: str) -> str:
    return value.strip().lower().replace("_", " ")


def _resolve_column(fieldnames: list[str], aliases: set[str]) -> str | None:
    canonical_to_original = {_canonicalize_column_name(name): name for name in fieldnames if name}
    for alias in aliases:
        original = canonical_to_original.get(_canonicalize_column_name(alias))
        if original:
            return original
    return None


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

    def export_child_asin_mapping_csv(self, profile_id: str) -> str:
        items = self.list_child_asins(profile_id)
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "child_asin",
                "child_sku",
                "child_product_name",
                "row_label",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        for item in items:
            writer.writerow(
                {
                    "child_asin": item.get("child_asin") or "",
                    "child_sku": item.get("child_sku") or "",
                    "child_product_name": item.get("child_product_name") or "",
                    "row_label": item.get("mapped_row_label") or "",
                }
            )
        return output.getvalue()

    def import_child_asin_mapping_csv(
        self,
        *,
        profile_id: str,
        file_name: str,
        file_bytes: bytes,
        user_id: str | None = None,
    ) -> dict[str, int]:
        self._validate_csv_file_name(file_name)
        self._get_profile(profile_id)

        text = _decode_csv_text(file_bytes)
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise WBRValidationError("ASIN mapping CSV must include a header row")

        fieldnames = [name for name in reader.fieldnames if name]
        child_asin_column = _resolve_column(fieldnames, CSV_IMPORT_COLUMN_ALIASES["child_asin"])
        row_id_column = _resolve_column(fieldnames, CSV_IMPORT_COLUMN_ALIASES["mapped_row_id"])
        row_label_column = _resolve_column(fieldnames, CSV_IMPORT_COLUMN_ALIASES["mapped_row_label"])

        if not child_asin_column:
            raise WBRValidationError("ASIN mapping CSV must include a child_asin column")
        if not row_id_column and not row_label_column:
            raise WBRValidationError(
                "ASIN mapping CSV must include mapped_row_id or mapped_row_label"
            )

        active_child_asins = self._list_active_child_asins(profile_id)
        leaf_rows = self._list_leaf_rows(profile_id)
        active_rows_by_id = {
            str(row["id"]): row
            for row in leaf_rows
            if isinstance(row, dict) and row.get("id") and row.get("active") is True
        }
        active_rows_by_label = {
            str(row["row_label"]).strip(): row
            for row in active_rows_by_id.values()
            if str(row.get("row_label") or "").strip()
        }

        seen_child_asins: set[str] = set()
        operations: list[tuple[str, str | None]] = []

        for index, row in enumerate(reader, start=2):
            child_asin = str(row.get(child_asin_column) or "").strip().upper()
            if not child_asin:
                raise WBRValidationError(f"ASIN mapping CSV row {index} is missing child_asin")
            if child_asin in seen_child_asins:
                raise WBRValidationError(f"ASIN mapping CSV contains duplicate child_asin {child_asin}")
            seen_child_asins.add(child_asin)

            if child_asin not in active_child_asins:
                raise WBRValidationError(
                    f"ASIN mapping CSV row {index} references unknown active child_asin {child_asin}"
                )

            mapped_row_id = str(row.get(row_id_column) or "").strip() if row_id_column else ""
            mapped_row_label = str(row.get(row_label_column) or "").strip() if row_label_column else ""

            if mapped_row_id:
                target_row = active_rows_by_id.get(mapped_row_id)
                if not target_row:
                    raise WBRValidationError(
                        f"ASIN mapping CSV row {index} references unknown active mapped_row_id {mapped_row_id}"
                    )
                operations.append((child_asin, str(target_row["id"])))
                continue

            if mapped_row_label:
                target_row = active_rows_by_label.get(mapped_row_label)
                if not target_row:
                    raise WBRValidationError(
                        f'ASIN mapping CSV row {index} references unknown active mapped_row_label "{mapped_row_label}"'
                    )
                operations.append((child_asin, str(target_row["id"])))
                continue

            operations.append((child_asin, None))

        rows_updated = 0
        rows_cleared = 0
        rows_unchanged = 0
        active_mapping_by_asin = self._list_active_mapping_by_asin(profile_id)
        mapping_ids_to_deactivate: list[str] = []
        mapping_payloads_to_insert: list[dict[str, Any]] = []

        for child_asin, target_row_id in operations:
            current = active_mapping_by_asin.get(child_asin)
            current_row_id = str(current.get("row_id")) if current and current.get("row_id") else None
            if current_row_id == target_row_id:
                rows_unchanged += 1
                continue
            if current and current.get("id"):
                mapping_ids_to_deactivate.append(str(current["id"]))
            if target_row_id is None:
                rows_cleared += 1
            else:
                rows_updated += 1
                payload: dict[str, Any] = {
                    "profile_id": profile_id,
                    "child_asin": child_asin,
                    "row_id": target_row_id,
                    "mapping_source": "manual",
                    "active": True,
                }
                if user_id:
                    payload["created_by"] = user_id
                    payload["updated_by"] = user_id
                mapping_payloads_to_insert.append(payload)

        self._deactivate_mapping_ids(mapping_ids_to_deactivate, user_id=user_id)
        self._insert_mapping_payloads(mapping_payloads_to_insert)

        return {
            "rows_read": len(operations),
            "rows_updated": rows_updated,
            "rows_cleared": rows_cleared,
            "rows_unchanged": rows_unchanged,
        }

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

    def _validate_csv_file_name(self, file_name: str) -> None:
        lower_name = (file_name or "").lower()
        if not lower_name.endswith(CSV_IMPORT_ALLOWED_EXTENSIONS):
            raise WBRValidationError("ASIN mapping import supports .csv files only")

    def _list_leaf_rows(self, profile_id: str) -> list[dict[str, Any]]:
        response = (
            self.db.table("wbr_rows")
            .select("*")
            .eq("profile_id", profile_id)
            .eq("row_kind", "leaf")
            .execute()
        )
        return response.data if isinstance(response.data, list) else []

    def _list_active_child_asins(self, profile_id: str) -> set[str]:
        response = (
            self.db.table("wbr_profile_child_asins")
            .select("child_asin")
            .eq("profile_id", profile_id)
            .eq("active", True)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        return {
            str(row["child_asin"]).strip().upper()
            for row in rows
            if isinstance(row, dict) and row.get("child_asin")
        }

    def _list_active_mapping_by_asin(self, profile_id: str) -> dict[str, dict[str, Any]]:
        response = (
            self.db.table("wbr_asin_row_map")
            .select("id,child_asin,row_id")
            .eq("profile_id", profile_id)
            .eq("active", True)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        return {
            str(row["child_asin"]).strip().upper(): row
            for row in rows
            if isinstance(row, dict) and row.get("child_asin")
        }

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

    def _deactivate_mapping_ids(self, mapping_ids: list[str], *, user_id: str | None = None) -> None:
        if not mapping_ids:
            return

        updates: dict[str, Any] = {"active": False}
        if user_id:
            updates["updated_by"] = user_id

        for start in range(0, len(mapping_ids), _BATCH_SIZE):
            chunk = mapping_ids[start:start + _BATCH_SIZE]
            (
                self.db.table("wbr_asin_row_map")
                .update(updates)
                .in_("id", chunk)
                .execute()
            )

    def _insert_mapping_payloads(self, payloads: list[dict[str, Any]]) -> None:
        if not payloads:
            return

        for start in range(0, len(payloads), _BATCH_SIZE):
            chunk = payloads[start:start + _BATCH_SIZE]
            response = self.db.table("wbr_asin_row_map").insert(chunk).execute()
            rows = response.data if isinstance(response.data, list) else []
            if len(rows) != len(chunk):
                raise WBRValidationError("Failed to save ASIN mapping")
