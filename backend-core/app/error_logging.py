from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from supabase import Client, create_client

from .config import settings

logger = logging.getLogger(__name__)


class AppErrorLogger:
    """Thin wrapper around Supabase inserts for `app_error_events`."""

    def __init__(self) -> None:
        self._client: Optional[Client] = None

    def _get_client(self) -> Optional[Client]:
        if not settings.usage_logging_enabled:
            return None
        if not settings.supabase_url or not settings.supabase_service_role:
            logger.warning("Error logging enabled but Supabase service role credentials missing.")
            return None
        if not self._client:
            self._client = create_client(settings.supabase_url, settings.supabase_service_role)
        return self._client

    def log(self, payload: Dict[str, Any]) -> None:
        client = self._get_client()
        if not client:
            return

        allowed = {
            "occurred_at",
            "tool",
            "severity",
            "message",
            "route",
            "method",
            "status_code",
            "request_id",
            "user_id",
            "user_email",
            "meta",
        }

        base_row = {k: v for k, v in payload.items() if k in allowed and v is not None}
        extra = {k: v for k, v in payload.items() if k not in allowed and v is not None}
        if extra:
            meta = base_row.get("meta") if isinstance(base_row.get("meta"), dict) else {}
            base_row["meta"] = {**meta, **extra}

        try:
            client.table("app_error_events").insert(base_row).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to record app error event: %s", exc)


error_logger = AppErrorLogger()

