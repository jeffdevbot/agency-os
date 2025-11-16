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
            client.table("usage_events").insert(payload).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to record usage event: %s", exc)


usage_logger = UsageLogger()
