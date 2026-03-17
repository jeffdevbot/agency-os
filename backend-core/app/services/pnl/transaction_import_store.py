"""Persistence helpers for Monthly P&L transaction imports."""

from __future__ import annotations

import json
import time
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from postgrest.exceptions import APIError as PostgrestAPIError
from supabase import Client

from .profiles import PNLNotFoundError, PNLValidationError
from .sku_units import SkuUnitSourceRow, summarize_sku_units
from .transaction_import_models import LedgerEntry, MappingRule, ParsedRawRow

IMPORT_INSERT_CHUNK_SIZE = 500
IMPORT_INSERT_MIN_CHUNK_SIZE = 100
IMPORT_INSERT_RETRY_ATTEMPTS = 2
_TRANSIENT_INSERT_ERROR_MARKERS = (
    "JSON could not be generated",
    "Bad gateway",
    "bad gateway",
    "'code': 502",
    '"code": 502',
)


def _merge_json_object(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_json_object(merged[key], value)
        else:
            merged[key] = value
    return merged


def _is_transient_insert_error(exc: PostgrestAPIError) -> bool:
    text = str(exc)
    return any(marker in text for marker in _TRANSIENT_INSERT_ERROR_MARKERS)


class TransactionImportStore:
    def __init__(self, db: Client) -> None:
        self.db = db

    def get_profile(self, profile_id: str) -> dict[str, Any]:
        response = (
            self.db.table("monthly_pnl_profiles")
            .select("*")
            .eq("id", profile_id)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise PNLNotFoundError(f"P&L profile {profile_id} not found")
        return rows[0]

    def get_import(self, import_id: str) -> dict[str, Any]:
        response = (
            self.db.table("monthly_pnl_imports")
            .select("*")
            .eq("id", import_id)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise PNLNotFoundError(f"Import {import_id} not found")
        return rows[0]

    def list_duplicate_candidates(
        self,
        *,
        profile_id: str,
        source_type: str,
        file_sha256: str,
    ) -> list[dict[str, Any]]:
        response = (
            self.db.table("monthly_pnl_imports")
            .select("id, import_status, created_at, started_at")
            .eq("profile_id", profile_id)
            .eq("source_type", source_type)
            .eq("source_file_sha256", file_sha256)
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        return [row for row in rows if isinstance(row, dict)]

    def load_mapping_rules(
        self,
        *,
        marketplace_code: str,
        profile_id: str,
        source_type: str,
    ) -> list[MappingRule]:
        response = (
            self.db.table("monthly_pnl_mapping_rules")
            .select("*")
            .eq("source_type", source_type)
            .eq("marketplace_code", marketplace_code)
            .eq("active", True)
            .order("priority")
            .execute()
        )
        rows_data = response.data if isinstance(response.data, list) else []
        rules: list[MappingRule] = []
        for row in rows_data:
            spec = row.get("match_spec") or {}
            if isinstance(spec, str):
                spec = json.loads(spec)
            rules.append(
                MappingRule(
                    id=str(row["id"]),
                    profile_id=row.get("profile_id"),
                    source_type=row.get("source_type", source_type),
                    match_spec=spec,
                    match_operator=row.get("match_operator", "exact_fields"),
                    target_bucket=row["target_bucket"],
                    priority=row.get("priority", 100),
                )
            )
        return rules

    def create_import(
        self,
        *,
        profile_id: str,
        source_type: str,
        file_name: str,
        file_sha256: str,
        period_start: str,
        period_end: str,
        import_scope: str,
        row_count: int,
        user_id: str | None,
        supersedes_import_id: str | None,
        storage_path: str | None = None,
        raw_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "profile_id": profile_id,
            "source_type": source_type,
            "source_filename": file_name,
            "source_file_sha256": file_sha256,
            "period_start": period_start,
            "period_end": period_end,
            "import_scope": import_scope,
            "import_status": "pending",
            "row_count": row_count,
        }
        if supersedes_import_id:
            payload["supersedes_import_id"] = supersedes_import_id
        if user_id:
            payload["initiated_by"] = user_id
        if storage_path:
            payload["storage_path"] = storage_path
        if raw_meta:
            payload["raw_meta"] = raw_meta

        try:
            response = self.db.table("monthly_pnl_imports").insert(payload).execute()
        except PostgrestAPIError as exc:
            if supersedes_import_id and "uq_monthly_pnl_imports_profile_source_sha256" in str(exc):
                self.clear_import_hash(supersedes_import_id)
                response = self.db.table("monthly_pnl_imports").insert(payload).execute()
            else:
                raise

        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise PNLValidationError("Failed to create import record")
        return rows[0]

    def clear_import_hash(self, import_id: str) -> None:
        (
            self.db.table("monthly_pnl_imports")
            .update({"source_file_sha256": None})
            .eq("id", import_id)
            .execute()
        )

    def merge_import_raw_meta(self, import_id: str, patch: dict[str, Any]) -> None:
        import_record = self.get_import(import_id)
        raw_meta = import_record.get("raw_meta")
        merged = _merge_json_object(raw_meta if isinstance(raw_meta, dict) else {}, patch)
        (
            self.db.table("monthly_pnl_imports")
            .update({"raw_meta": merged})
            .eq("id", import_id)
            .execute()
        )

    def update_import_status(
        self,
        import_id: str,
        status: str,
        *,
        error_message: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {"import_status": status}
        if status == "running":
            payload["started_at"] = datetime.now(UTC).isoformat()
            payload["error_message"] = None
        if status in ("success", "error"):
            payload["finished_at"] = datetime.now(UTC).isoformat()
            if status == "success":
                payload["error_message"] = None
        if error_message is not None:
            payload["error_message"] = error_message
        self.db.table("monthly_pnl_imports").update(payload).eq("id", import_id).execute()

    def create_import_month(
        self,
        *,
        import_id: str,
        profile_id: str,
        source_type: str,
        entry_month: date,
        raw_row_count: int,
        ledger_row_count: int,
        mapped_amount: Decimal,
        unmapped_amount: Decimal,
    ) -> dict[str, Any]:
        payload = {
            "import_id": import_id,
            "profile_id": profile_id,
            "source_type": source_type,
            "entry_month": entry_month.isoformat(),
            "import_status": "pending",
            "raw_row_count": raw_row_count,
            "ledger_row_count": ledger_row_count,
            "mapped_amount": str(mapped_amount),
            "unmapped_amount": str(unmapped_amount),
        }
        response = self.db.table("monthly_pnl_import_months").insert(payload).execute()
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise PNLValidationError("Failed to create import month record")
        return rows[0]

    def insert_raw_rows(
        self,
        *,
        import_id: str,
        import_month_id: str,
        profile_id: str,
        source_type: str,
        raw_rows: list[ParsedRawRow],
    ) -> None:
        payloads = [
            {
                "import_id": import_id,
                "import_month_id": import_month_id,
                "profile_id": profile_id,
                "source_type": source_type,
                "row_index": rr.row_index,
                "posted_at": rr.posted_at.isoformat() if rr.posted_at else None,
                "release_at": rr.release_at.isoformat() if rr.release_at else None,
                "order_id": rr.order_id,
                "sku": rr.sku,
                "raw_type": rr.raw_type,
                "raw_description": rr.raw_description,
                "raw_payload": rr.raw_payload,
            }
            for rr in raw_rows
        ]
        self._insert_payloads("monthly_pnl_raw_rows", payloads)

    def insert_ledger_entries(
        self,
        *,
        import_id: str,
        import_month_id: str,
        profile_id: str,
        entry_month: date,
        source_type: str,
        entries: list[LedgerEntry],
    ) -> None:
        payloads = [
            {
                "import_id": import_id,
                "import_month_id": import_month_id,
                "profile_id": profile_id,
                "entry_month": entry_month.isoformat(),
                "posted_at": e.posted_at.isoformat() if e.posted_at else None,
                "order_id": e.order_id,
                "sku": e.sku,
                "source_type": source_type,
                "raw_type": e.raw_type,
                "raw_description": e.raw_description,
                "ledger_bucket": e.ledger_bucket,
                "amount": str(e.amount),
                "is_mapped": e.is_mapped,
                "mapping_rule_id": e.mapping_rule_id,
                "source_row_index": e.source_row_index,
            }
            for e in entries
        ]
        self._insert_payloads("monthly_pnl_ledger_entries", payloads)

    def insert_bucket_totals(
        self,
        *,
        import_id: str,
        import_month_id: str,
        profile_id: str,
        entry_month: date,
        entries: list[LedgerEntry],
    ) -> None:
        totals: dict[str, Decimal] = {}
        for entry in entries:
            totals[entry.ledger_bucket] = totals.get(entry.ledger_bucket, Decimal("0")) + entry.amount

        payloads = [
            {
                "import_id": import_id,
                "import_month_id": import_month_id,
                "profile_id": profile_id,
                "entry_month": entry_month.isoformat(),
                "ledger_bucket": bucket,
                "amount": str(amount),
            }
            for bucket, amount in totals.items()
            if amount != 0
        ]
        if payloads:
            self._insert_payloads("monthly_pnl_import_month_bucket_totals", payloads)

    def insert_sku_unit_totals(
        self,
        *,
        import_id: str,
        import_month_id: str,
        profile_id: str,
        entry_month: date,
        raw_rows: list[ParsedRawRow],
    ) -> None:
        totals = summarize_sku_units(
            SkuUnitSourceRow(
                sku=raw_row.sku,
                quantity=raw_row.quantity,
                raw_type=raw_row.raw_type,
                product_sales=raw_row.amounts.get("product_sales", Decimal("0")),
            )
            for raw_row in raw_rows
        )
        payloads = [
            {
                "import_id": import_id,
                "import_month_id": import_month_id,
                "profile_id": profile_id,
                "entry_month": entry_month.isoformat(),
                "sku": sku,
                "net_units": summary["net_units"],
                "order_row_count": summary["order_row_count"],
                "refund_row_count": summary["refund_row_count"],
            }
            for sku, summary in totals.items()
            if summary["net_units"] != 0
        ]
        if payloads:
            self._insert_payloads("monthly_pnl_import_month_sku_units", payloads)

    def update_import_month_status(self, import_month_id: str, status: str) -> None:
        (
            self.db.table("monthly_pnl_import_months")
            .update({"import_status": status})
            .eq("id", import_month_id)
            .execute()
        )

    def activate_month_slice(
        self,
        *,
        profile_id: str,
        source_type: str,
        import_month_id: str,
        entry_month: date,
    ) -> None:
        self.db.rpc(
            "pnl_activate_month_slice",
            {
                "p_profile_id": profile_id,
                "p_source_type": source_type,
                "p_entry_month": entry_month.isoformat(),
                "p_import_month_id": import_month_id,
            },
        ).execute()

    def deactivate_superseded_months(
        self,
        *,
        superseded_import_id: str,
        retained_months: set[date],
    ) -> None:
        response = (
            self.db.table("monthly_pnl_import_months")
            .select("id, entry_month")
            .eq("import_id", superseded_import_id)
            .eq("is_active", True)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        for row in rows:
            raw_entry_month = row.get("entry_month")
            if not raw_entry_month:
                continue
            entry_month = date.fromisoformat(str(raw_entry_month))
            if entry_month in retained_months:
                continue
            (
                self.db.table("monthly_pnl_import_months")
                .update({"is_active": False})
                .eq("id", row["id"])
                .execute()
            )

    def mark_pending_months_error(self, import_id: str) -> None:
        (
            self.db.table("monthly_pnl_import_months")
            .update({"import_status": "error"})
            .eq("import_id", import_id)
            .eq("import_status", "pending")
            .execute()
        )

    def upload_source_file(self, bucket: str, storage_path: str, file_bytes: bytes) -> None:
        self.db.storage.from_(bucket).upload(
            storage_path,
            file_bytes,
            {"content-type": "text/csv"},
        )

    def download_source_file(self, bucket: str, storage_path: str) -> bytes:
        return self.db.storage.from_(bucket).download(storage_path)

    def delete_source_file(self, bucket: str, storage_path: str) -> None:
        try:
            self.db.storage.from_(bucket).remove([storage_path])
        except Exception:
            return

    def _insert_payloads(self, table_name: str, payloads: list[dict[str, Any]]) -> None:
        for start in range(0, len(payloads), IMPORT_INSERT_CHUNK_SIZE):
            self._insert_chunk(table_name, payloads[start : start + IMPORT_INSERT_CHUNK_SIZE])

    def _insert_chunk(self, table_name: str, chunk: list[dict[str, Any]]) -> None:
        for attempt in range(1, IMPORT_INSERT_RETRY_ATTEMPTS + 1):
            try:
                self.db.table(table_name).insert(chunk).execute()
                return
            except PostgrestAPIError as exc:
                if not _is_transient_insert_error(exc):
                    raise
                if attempt < IMPORT_INSERT_RETRY_ATTEMPTS:
                    time.sleep(0.25 * attempt)
                    continue
                break

        if len(chunk) <= IMPORT_INSERT_MIN_CHUNK_SIZE:
            self.db.table(table_name).insert(chunk).execute()
            return

        midpoint = len(chunk) // 2
        self._insert_chunk(table_name, chunk[:midpoint])
        self._insert_chunk(table_name, chunk[midpoint:])
