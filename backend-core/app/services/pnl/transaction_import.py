"""Amazon Monthly Unified Transaction Report import service.

Handles CSV parsing, raw-row storage, ledger expansion, mapping rule
application, and month-slice activation for the Monthly P&L system.
"""

from __future__ import annotations

import hashlib
import re
import time
from datetime import UTC, datetime, date, timedelta
from typing import Any

from supabase import Client

from .profiles import PNLDuplicateFileError, PNLNotFoundError, PNLValidationError
from .transaction_import_csv import parse_raw_rows, parse_transaction_csv
from .transaction_import_ledger import expand_raw_row_to_ledger, find_matching_rule
from .transaction_import_models import (
    LedgerEntry,
    MappingRule,
    MonthSlice,
    ParsedRawRow,
    PreparedImport,
)
from .transaction_import_store import TransactionImportStore

SOURCE_TYPE = "amazon_transaction_upload"
IMPORT_STORAGE_BUCKET = "monthly-pnl-imports"
ASYNC_IMPORT_META_FLAG = "async_import_v1"
ASYNC_IMPORT_PROGRESS_KEY = "async_import_progress_v1"
STALE_RUNNING_IMPORT_AGE = timedelta(minutes=15)


def _parse_db_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ── Import orchestration ─────────────────────────────────────────────


class TransactionImportService:
    def __init__(self, db: Client) -> None:
        self.db = db
        self.store = TransactionImportStore(db)

    def enqueue_file(
        self,
        *,
        profile_id: str,
        file_name: str,
        file_bytes: bytes,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Persist the file and queue import work for background processing."""
        profile = self.store.get_profile(profile_id)
        file_sha256 = hashlib.sha256(file_bytes).hexdigest()
        superseded_import = self._check_duplicate(profile_id, file_sha256)
        prepared = self._prepare_import(
            profile_id=profile_id,
            marketplace_code=str(profile.get("marketplace_code", "US")),
            file_bytes=file_bytes,
        )
        queued_at = _utc_now_iso()

        storage_path = self._build_storage_path(profile_id, file_name, file_sha256)
        self._upload_source_file(storage_path, file_bytes)

        try:
            import_record = self.store.create_import(
                profile_id=profile_id,
                source_type=SOURCE_TYPE,
                file_name=file_name,
                file_sha256=file_sha256,
                period_start=prepared.period_start.isoformat(),
                period_end=prepared.period_end.isoformat(),
                import_scope=prepared.import_scope,
                row_count=len(prepared.raw_rows),
                user_id=user_id,
                supersedes_import_id=(
                    str(superseded_import["id"])
                    if superseded_import and superseded_import.get("import_status") == "success"
                    else None
                ),
                storage_path=storage_path,
                raw_meta={
                    ASYNC_IMPORT_META_FLAG: True,
                    "queued_at": queued_at,
                    "file_size_bytes": len(file_bytes),
                    ASYNC_IMPORT_PROGRESS_KEY: self._build_progress_payload(
                        prepared=prepared,
                        stage="queued",
                        detail="Queued for worker-sync background processing",
                        heartbeat_at=queued_at,
                    ),
                },
            )
        except Exception:
            self._delete_source_file(storage_path)
            raise

        return {
            "import": import_record,
            "months": self._build_pending_month_summaries(prepared),
            "summary": self._build_import_summary(prepared),
        }

    def import_file(
        self,
        *,
        profile_id: str,
        file_name: str,
        file_bytes: bytes,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Full import pipeline: parse → store → expand → activate."""
        profile = self.store.get_profile(profile_id)
        file_sha256 = hashlib.sha256(file_bytes).hexdigest()
        superseded_import = self._check_duplicate(profile_id, file_sha256)
        prepared = self._prepare_import(
            profile_id=profile_id,
            marketplace_code=str(profile.get("marketplace_code", "US")),
            file_bytes=file_bytes,
        )
        import_record = self.store.create_import(
            profile_id=profile_id,
            source_type=SOURCE_TYPE,
            file_name=file_name,
            file_sha256=file_sha256,
            period_start=prepared.period_start.isoformat(),
            period_end=prepared.period_end.isoformat(),
            import_scope=prepared.import_scope,
            row_count=len(prepared.raw_rows),
            user_id=user_id,
            supersedes_import_id=(
                str(superseded_import["id"])
                if superseded_import and superseded_import.get("import_status") == "success"
                else None
            ),
        )
        return self._run_import(
            import_id=str(import_record["id"]),
            profile_id=profile_id,
            prepared=prepared,
            superseded_import_id=(
                str(superseded_import["id"])
                if superseded_import and superseded_import.get("import_status") == "success"
                else None
            ),
        )

    def process_import(self, import_id: str) -> dict[str, Any]:
        """Run a previously queued import from its staged source file."""
        import_record = self.store.get_import(import_id)
        profile_id = str(import_record.get("profile_id") or "").strip()
        if not profile_id:
            raise PNLValidationError(f"Import {import_id} is missing profile_id")

        storage_path = str(import_record.get("storage_path") or "").strip()
        if not storage_path:
            raise PNLValidationError(f"Import {import_id} has no staged source file")
        try:
            self._update_import_progress(
                import_id,
                stage="loading_source",
                detail="Worker claimed the import and is loading the staged file",
            )
            profile = self.store.get_profile(profile_id)
            file_bytes = self._download_source_file(storage_path)
            self._update_import_progress(
                import_id,
                stage="preparing",
                detail="Parsing the staged transaction export",
            )
            prepared = self._prepare_import(
                profile_id=profile_id,
                marketplace_code=str(profile.get("marketplace_code", "US")),
                file_bytes=file_bytes,
            )
        except Exception as exc:
            self.store.update_import_status(import_id, "error", error_message=str(exc))
            self._update_import_progress(
                import_id,
                stage="error",
                detail=str(exc),
                last_error=str(exc),
            )
            raise

        return self._run_import(
            import_id=import_id,
            profile_id=profile_id,
            prepared=prepared,
            superseded_import_id=(
                str(import_record["supersedes_import_id"])
                if import_record.get("supersedes_import_id")
                else None
            ),
            already_running=str(import_record.get("import_status") or "").strip() == "running",
        )

    def _prepare_import(
        self,
        *,
        profile_id: str,
        marketplace_code: str,
        file_bytes: bytes,
    ) -> PreparedImport:
        header_values, header_map, data_rows = parse_transaction_csv(file_bytes)
        raw_rows = parse_raw_rows(header_values, header_map, data_rows)
        rules = self.store.load_mapping_rules(
            marketplace_code=marketplace_code,
            profile_id=profile_id,
            source_type=SOURCE_TYPE,
        )

        month_slices: dict[date, MonthSlice] = {}
        for raw_row in raw_rows:
            if raw_row.entry_month is None:
                continue
            if raw_row.entry_month not in month_slices:
                month_slices[raw_row.entry_month] = MonthSlice(entry_month=raw_row.entry_month)
            month_slice = month_slices[raw_row.entry_month]
            month_slice.raw_rows.append(raw_row)

            for entry in expand_raw_row_to_ledger(raw_row, rules, profile_id):
                month_slice.ledger_entries.append(entry)
                if entry.is_mapped:
                    month_slice.mapped_amount += entry.amount
                else:
                    month_slice.unmapped_amount += entry.amount

        if not month_slices:
            raise PNLValidationError("No rows with valid dates found in transaction file")

        sorted_months = sorted(month_slices)
        period_start = sorted_months[0]
        period_end = sorted_months[-1]
        if len(sorted_months) == 1:
            import_scope = "single_month"
        elif len(sorted_months) >= 10:
            import_scope = "full_year"
        else:
            import_scope = "multi_month"

        return PreparedImport(
            raw_rows=raw_rows,
            month_slices=month_slices,
            sorted_months=sorted_months,
            period_start=period_start,
            period_end=period_end,
            import_scope=import_scope,
        )

    def _run_import(
        self,
        *,
        import_id: str,
        profile_id: str,
        prepared: PreparedImport,
        superseded_import_id: str | None,
        already_running: bool = False,
    ) -> dict[str, Any]:
        try:
            if not already_running:
                self.store.update_import_status(import_id, "running")

            month_summaries: list[dict[str, Any]] = []
            raw_rows_processed = 0
            ledger_rows_processed = 0
            total_months = len(prepared.sorted_months)

            for entry_month in prepared.sorted_months:
                month_slice = prepared.month_slices[entry_month]
                self._update_import_progress(
                    import_id,
                    prepared=prepared,
                    stage="processing_month",
                    detail=f"Processing {entry_month.isoformat()}",
                    months_completed=len(month_summaries),
                    current_month=entry_month.isoformat(),
                    current_month_raw_rows=len(month_slice.raw_rows),
                    current_month_ledger_rows=len(month_slice.ledger_entries),
                    raw_rows_processed=raw_rows_processed,
                    ledger_rows_processed=ledger_rows_processed,
                    months_total=total_months,
                )
                month_summaries.append(
                    self._process_month_slice(
                        import_id=import_id,
                        profile_id=profile_id,
                        month_slice=month_slice,
                    )
                )
                raw_rows_processed += len(month_slice.raw_rows)
                ledger_rows_processed += len(month_slice.ledger_entries)
                self._update_import_progress(
                    import_id,
                    prepared=prepared,
                    stage="processing_month",
                    detail=f"Completed {entry_month.isoformat()}",
                    months_completed=len(month_summaries),
                    last_completed_month=entry_month.isoformat(),
                    current_month=None,
                    current_month_raw_rows=None,
                    current_month_ledger_rows=None,
                    raw_rows_processed=raw_rows_processed,
                    ledger_rows_processed=ledger_rows_processed,
                    months_total=total_months,
                )

            if superseded_import_id:
                self.store.deactivate_superseded_months(
                    superseded_import_id=superseded_import_id,
                    retained_months=set(prepared.sorted_months),
                )

            self.store.update_import_status(import_id, "success")
            self.store.promote_profile_to_active_if_draft(profile_id)
            self._update_import_progress(
                import_id,
                prepared=prepared,
                stage="success",
                detail="Import finished successfully",
                months_completed=total_months,
                months_total=total_months,
                raw_rows_processed=len(prepared.raw_rows),
                ledger_rows_processed=sum(
                    len(prepared.month_slices[entry_month].ledger_entries)
                    for entry_month in prepared.sorted_months
                ),
                current_month=None,
                current_month_raw_rows=None,
                current_month_ledger_rows=None,
                completed_at=_utc_now_iso(),
            )
            final_import = self.store.get_import(import_id)

            return {
                "import": final_import,
                "months": month_summaries,
                "summary": self._build_import_summary(prepared),
            }
        except Exception as exc:
            self.store.update_import_status(import_id, "error", error_message=str(exc))
            self._update_import_progress(
                import_id,
                prepared=prepared,
                stage="error",
                detail=str(exc),
                months_completed=len(month_summaries),
                months_total=len(prepared.sorted_months),
                last_error=str(exc),
            )
            raise

    def _build_import_summary(self, prepared: PreparedImport) -> dict[str, Any]:
        return {
            "total_raw_rows": len(prepared.raw_rows),
            "total_months": len(prepared.sorted_months),
            "period_start": prepared.period_start.isoformat(),
            "period_end": prepared.period_end.isoformat(),
            "import_scope": prepared.import_scope,
        }

    def _build_pending_month_summaries(self, prepared: PreparedImport) -> list[dict[str, Any]]:
        pending_months: list[dict[str, Any]] = []
        for entry_month in prepared.sorted_months:
            month_slice = prepared.month_slices[entry_month]
            pending_months.append(
                {
                    "entry_month": entry_month.isoformat(),
                    "import_month_id": None,
                    "raw_row_count": len(month_slice.raw_rows),
                    "ledger_row_count": len(month_slice.ledger_entries),
                    "mapped_amount": str(month_slice.mapped_amount),
                    "unmapped_amount": str(month_slice.unmapped_amount),
                    "import_status": "pending",
                    "is_active": False,
                }
            )
        return pending_months

    def _check_duplicate(self, profile_id: str, file_sha256: str) -> dict[str, Any] | None:
        rows = self.store.list_duplicate_candidates(
            profile_id=profile_id,
            source_type=SOURCE_TYPE,
            file_sha256=file_sha256,
        )
        if rows:
            active_running_imports: list[dict[str, Any]] = []
            filtered_rows: list[dict[str, Any]] = []
            for row in rows:
                if row.get("import_status") != "running":
                    filtered_rows.append(row)
                    continue
                if self._is_stale_running_import(row):
                    self._mark_import_stale_error(str(row["id"]))
                    continue
                active_running_imports.append(row)
                filtered_rows.append(row)

            running_import = active_running_imports[0] if active_running_imports else None
            if running_import:
                raise PNLDuplicateFileError(
                    f"This file has already been imported (import {running_import['id']})"
                )

            successful_import = next(
                (row for row in filtered_rows if row.get("import_status") == "success"),
                None,
            )
            if successful_import:
                return successful_import

            if not filtered_rows:
                return None

            status = filtered_rows[0].get("import_status")
            if status == "running":
                raise PNLDuplicateFileError(
                    f"This file has already been imported (import {filtered_rows[0]['id']})"
                )
            return filtered_rows[0]
        return None

    def _process_month_slice(
        self,
        *,
        import_id: str,
        profile_id: str,
        month_slice: MonthSlice,
    ) -> dict[str, Any]:
        entry_month = month_slice.entry_month

        import_month = self.store.create_import_month(
            import_id=import_id,
            profile_id=profile_id,
            source_type=SOURCE_TYPE,
            entry_month=entry_month,
            raw_row_count=len(month_slice.raw_rows),
            ledger_row_count=len(month_slice.ledger_entries),
            mapped_amount=month_slice.mapped_amount,
            unmapped_amount=month_slice.unmapped_amount,
        )
        import_month_id = str(import_month["id"])

        try:
            # 2. Insert raw rows
            self._insert_raw_rows(
                import_id=import_id,
                import_month_id=import_month_id,
                profile_id=profile_id,
                raw_rows=month_slice.raw_rows,
            )

            # 3. Insert ledger entries
            self._insert_ledger_entries(
                import_id=import_id,
                import_month_id=import_month_id,
                profile_id=profile_id,
                entry_month=entry_month,
                entries=month_slice.ledger_entries,
            )

            self._insert_bucket_totals(
                import_id=import_id,
                import_month_id=import_month_id,
                profile_id=profile_id,
                entry_month=entry_month,
                entries=month_slice.ledger_entries,
            )

            self._insert_sku_unit_totals(
                import_id=import_id,
                import_month_id=import_month_id,
                profile_id=profile_id,
                entry_month=entry_month,
                raw_rows=month_slice.raw_rows,
            )

            self.store.activate_month_slice(
                profile_id=profile_id,
                source_type=SOURCE_TYPE,
                import_month_id=import_month_id,
                entry_month=entry_month,
            )

            self.store.update_import_month_status(import_month_id, "success")

        except Exception:
            self.store.update_import_month_status(import_month_id, "error")
            raise

        return {
            "entry_month": entry_month.isoformat(),
            "import_month_id": import_month_id,
            "raw_row_count": len(month_slice.raw_rows),
            "ledger_row_count": len(month_slice.ledger_entries),
            "mapped_amount": str(month_slice.mapped_amount),
            "unmapped_amount": str(month_slice.unmapped_amount),
            "is_active": True,
        }

    def _insert_raw_rows(
        self,
        *,
        import_id: str,
        import_month_id: str,
        profile_id: str,
        raw_rows: list[ParsedRawRow],
    ) -> None:
        self.store.insert_raw_rows(
            import_id=import_id,
            import_month_id=import_month_id,
            profile_id=profile_id,
            source_type=SOURCE_TYPE,
            raw_rows=raw_rows,
        )

    def _insert_ledger_entries(
        self,
        *,
        import_id: str,
        import_month_id: str,
        profile_id: str,
        entry_month: date,
        entries: list[LedgerEntry],
    ) -> None:
        self.store.insert_ledger_entries(
            import_id=import_id,
            import_month_id=import_month_id,
            profile_id=profile_id,
            entry_month=entry_month,
            source_type=SOURCE_TYPE,
            entries=entries,
        )

    def _insert_bucket_totals(
        self,
        *,
        import_id: str,
        import_month_id: str,
        profile_id: str,
        entry_month: date,
        entries: list[LedgerEntry],
    ) -> None:
        self.store.insert_bucket_totals(
            import_id=import_id,
            import_month_id=import_month_id,
            profile_id=profile_id,
            entry_month=entry_month,
            entries=entries,
        )

    def _insert_sku_unit_totals(
        self,
        *,
        import_id: str,
        import_month_id: str,
        profile_id: str,
        entry_month: date,
        raw_rows: list[ParsedRawRow],
    ) -> None:
        self.store.insert_sku_unit_totals(
            import_id=import_id,
            import_month_id=import_month_id,
            profile_id=profile_id,
            entry_month=entry_month,
            raw_rows=raw_rows,
        )

    def _is_stale_running_import(self, row: dict[str, Any]) -> bool:
        started_at = _parse_db_timestamp(row.get("started_at")) or _parse_db_timestamp(row.get("created_at"))
        if started_at is None:
            return False
        return (datetime.now(UTC) - started_at) >= STALE_RUNNING_IMPORT_AGE

    def _mark_import_stale_error(self, import_id: str) -> None:
        stale_message = (
            "Marked as error after a prior import attempt stopped progressing. Safe to retry."
        )
        self.store.update_import_status(import_id, "error", error_message=stale_message)
        self._update_import_progress(
            import_id,
            stage="stale_error",
            detail=stale_message,
            last_error=stale_message,
        )
        self.store.mark_pending_months_error(import_id)

    def _build_progress_payload(
        self,
        *,
        prepared: PreparedImport,
        stage: str,
        detail: str,
        heartbeat_at: str | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "stage": stage,
            "detail": detail,
            "heartbeat_at": heartbeat_at or _utc_now_iso(),
            "total_raw_rows": len(prepared.raw_rows),
            "total_months": len(prepared.sorted_months),
            "period_start": prepared.period_start.isoformat(),
            "period_end": prepared.period_end.isoformat(),
            "import_scope": prepared.import_scope,
            "months_total": len(prepared.sorted_months),
        }
        payload.update(extra)
        return payload

    def _update_import_progress(
        self,
        import_id: str,
        *,
        prepared: PreparedImport | None = None,
        stage: str,
        detail: str,
        **extra: Any,
    ) -> None:
        progress: dict[str, Any] = {
            "stage": stage,
            "detail": detail,
            "heartbeat_at": _utc_now_iso(),
        }
        if prepared is not None:
            progress = self._build_progress_payload(
                prepared=prepared,
                stage=stage,
                detail=detail,
                heartbeat_at=progress["heartbeat_at"],
                **extra,
            )
        else:
            progress.update(extra)
        self.store.merge_import_raw_meta(import_id, {ASYNC_IMPORT_PROGRESS_KEY: progress})

    def _build_storage_path(self, profile_id: str, file_name: str, file_sha256: str) -> str:
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", file_name.strip() or "upload.csv").strip("-")
        if not safe_name:
            safe_name = "upload.csv"
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        return f"{profile_id}/{timestamp}-{file_sha256[:12]}-{safe_name}"

    def _upload_source_file(self, storage_path: str, file_bytes: bytes) -> None:
        self.store.upload_source_file(
            IMPORT_STORAGE_BUCKET,
            storage_path,
            file_bytes,
        )

    def _download_source_file(self, storage_path: str) -> bytes:
        return self.store.download_source_file(IMPORT_STORAGE_BUCKET, storage_path)

    def _delete_source_file(self, storage_path: str) -> None:
        self.store.delete_source_file(IMPORT_STORAGE_BUCKET, storage_path)
