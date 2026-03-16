from __future__ import annotations

from unittest.mock import MagicMock

from app.services.pnl.worker import PNLImportWorkerService


def _chain_table(response_data: list[dict] | None = None) -> MagicMock:
    table = MagicMock()
    table.select.return_value = table
    table.eq.return_value = table
    table.order.return_value = table
    table.limit.return_value = table
    response = MagicMock()
    response.data = response_data if response_data is not None else []
    table.execute.return_value = response
    return table


def test_worker_processes_pending_async_imports_and_marks_stale_running():
    running_table = _chain_table(
        [
            {
                "id": "running-async",
                "import_status": "running",
                "raw_meta": {"async_import_v1": True},
                "started_at": "2026-03-16T12:00:00+00:00",
            },
        ]
    )
    claimed_rpc = MagicMock()
    claimed_rpc.execute.return_value = MagicMock(
        data=[
            {
                "id": "pending-async",
                "import_status": "running",
                "raw_meta": {"async_import_v1": True},
            }
        ]
    )

    db = MagicMock()
    db.table.return_value = running_table
    db.rpc.return_value = claimed_rpc

    svc = PNLImportWorkerService(db)
    svc.imports.process_import = MagicMock()
    svc.imports._is_stale_running_import = MagicMock(side_effect=lambda row: row["id"] == "running-async")
    svc.imports._mark_import_stale_error = MagicMock()

    result = svc.run_pending(limit=2)

    svc.imports.process_import.assert_called_once_with("pending-async")
    svc.imports._mark_import_stale_error.assert_called_once_with("running-async")
    db.rpc.assert_called_once_with("pnl_claim_pending_imports", {"p_limit": 2})
    assert result["imports_considered"] == 2
    assert result["imports_processed"] == 1
