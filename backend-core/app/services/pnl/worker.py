from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from supabase import Client

from .transaction_import import (
    ASYNC_IMPORT_META_FLAG,
    SOURCE_TYPE,
    TransactionImportService,
)


@dataclass(frozen=True)
class PNLImportWorkerResult:
    import_id: str
    status: str
    detail: str | None = None


class PNLImportWorkerService:
    def __init__(self, db: Client) -> None:
        self.db = db
        self.imports = TransactionImportService(db)

    def run_pending(self, *, limit: int = 2) -> dict[str, Any]:
        results: list[PNLImportWorkerResult] = []
        stale_running = self._list_running_async_imports(limit=max(limit * 5, 10))
        claimed_imports = self._claim_pending_imports(limit=limit)

        for import_record in stale_running:
            import_id = str(import_record.get("id") or "").strip()
            if not import_id:
                continue

            if self.imports._is_stale_running_import(import_record):
                self.imports._mark_import_stale_error(import_id)
                results.append(
                    PNLImportWorkerResult(
                        import_id=import_id,
                        status="stale_error",
                        detail="Marked stale running import as error",
                    )
                )

        processed = 0
        for import_record in claimed_imports:
            import_id = str(import_record.get("id") or "").strip()
            if not import_id:
                continue
            try:
                self.imports.process_import(import_id)
                results.append(PNLImportWorkerResult(import_id=import_id, status="success"))
            except Exception as exc:  # noqa: BLE001
                results.append(
                    PNLImportWorkerResult(
                        import_id=import_id,
                        status="error",
                        detail=str(exc),
                    )
                )

            processed += 1
            if processed >= limit:
                break

        return {
            "imports_considered": len(stale_running) + len(claimed_imports),
            "imports_processed": processed,
            "results": [result.__dict__ for result in results],
        }

    def _claim_pending_imports(self, *, limit: int) -> list[dict[str, Any]]:
        response = self.db.rpc("pnl_claim_pending_imports", {"p_limit": limit}).execute()
        rows = response.data if isinstance(response.data, list) else []
        return [row for row in rows if isinstance(row, dict)]

    def _list_running_async_imports(self, *, limit: int) -> list[dict[str, Any]]:
        response = (
            self.db.table("monthly_pnl_imports")
            .select("id, profile_id, import_status, created_at, started_at, raw_meta")
            .eq("source_type", SOURCE_TYPE)
            .eq("import_status", "running")
            .order("created_at")
            .limit(limit)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        return [
            row
            for row in rows
            if isinstance(row, dict) and self._is_async_import(row)
        ]

    @staticmethod
    def _is_async_import(import_record: dict[str, Any]) -> bool:
        raw_meta = import_record.get("raw_meta")
        return isinstance(raw_meta, dict) and bool(raw_meta.get(ASYNC_IMPORT_META_FLAG))
