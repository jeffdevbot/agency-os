from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from supabase import Client, create_client

from .config import settings

logger = logging.getLogger(__name__)


class UsageLogger:
    """Thin wrapper around Supabase inserts for `usage_events`."""

    def __init__(self) -> None:
        self._client: Optional[Client] = None
        self._supports_tool: Optional[bool] = None
        self._supports_meta: Optional[bool] = None

    def _get_client(self) -> Optional[Client]:
        if not settings.usage_logging_enabled:
            return None
        if not settings.supabase_url or not settings.supabase_service_role:
            logger.warning("Usage logging enabled but Supabase service role credentials missing.")
            return None
        if not self._client:
            self._client = create_client(settings.supabase_url, settings.supabase_service_role)
        return self._client

    def log(self, payload: Dict[str, Any]) -> None:
        client = self._get_client()
        if not client:
            return
        try:
            allowed = {
                "occurred_at",
                "user_id",
                "user_email",
                "ip",
                "file_name",
                "file_size_bytes",
                "rows_processed",
                "campaigns",
                "status",
                "duration_ms",
                "app_version",
                "tool",
                "meta",
            }

            base_row = {k: v for k, v in payload.items() if k in allowed and v is not None}
            extra = {k: v for k, v in payload.items() if k not in allowed and v is not None}

            # Prefer capturing tool-specific metrics into JSONB meta (if supported).
            if extra:
                base_row.setdefault("meta", {})
                if isinstance(base_row["meta"], dict):
                    base_row["meta"] = {**base_row["meta"], **extra}
                else:
                    base_row["meta"] = extra

            # Handle deployments where schema hasn't been migrated yet.
            if self._supports_tool is False:
                base_row.pop("tool", None)
            if self._supports_meta is False:
                base_row.pop("meta", None)

            try:
                client.table("usage_events").insert(base_row).execute()
            except Exception as exc:  # noqa: BLE001
                msg = str(exc).lower()
                if self._supports_tool is None and ("tool" in msg and "column" in msg):
                    self._supports_tool = False
                    base_row.pop("tool", None)
                if self._supports_meta is None and ("meta" in msg and "column" in msg):
                    self._supports_meta = False
                    base_row.pop("meta", None)

                # One retry with reduced columns to avoid dropping logs entirely.
                client.table("usage_events").insert(base_row).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to record usage event: %s", exc)


usage_logger = UsageLogger()
