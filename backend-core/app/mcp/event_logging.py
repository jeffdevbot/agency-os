"""Structured logging helpers for MCP tool invocations."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from time import perf_counter
from typing import Any
from uuid import UUID

from supabase import Client, create_client

from ..config import settings
from .auth import MCPUser, get_current_mcp_user

logger = logging.getLogger(__name__)

MCP_SURFACE = "claude_mcp"
MCP_CONNECTOR_NAME = "Ecomlabs Tools"
_MUTATING_TOOLS = frozenset(
    {
        "draft_wbr_email",
        "draft_monthly_pnl_email",
        "create_clickup_task",
        "update_clickup_task",
    }
)


def _coerce_uuid(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _clean_meta(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        cleaned_items = []
        for item in value:
            cleaned = _clean_meta(item)
            if cleaned is not None:
                cleaned_items.append(cleaned)
        return cleaned_items
    if isinstance(value, dict):
        cleaned_dict: dict[str, Any] = {}
        for key, item in value.items():
            cleaned = _clean_meta(item)
            if cleaned is not None:
                cleaned_dict[str(key)] = cleaned
        return cleaned_dict
    return str(value)


def _clean_meta_dict(meta: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in meta.items():
        safe_value = _clean_meta(value)
        if safe_value is not None:
            cleaned[key] = safe_value
    return cleaned


def _is_mutation_tool(tool_name: str) -> bool:
    return tool_name in _MUTATING_TOOLS


class MCPEventLogger:
    """Thin wrapper around Supabase inserts for `mcp_tool_events`."""

    def __init__(self) -> None:
        self._client: Client | None = None

    def _get_client(self) -> Client | None:
        if not settings.usage_logging_enabled:
            return None
        if not settings.supabase_url or not settings.supabase_service_role:
            logger.warning("MCP event logging enabled but Supabase service role credentials missing.")
            return None
        if not self._client:
            self._client = create_client(settings.supabase_url, settings.supabase_service_role)
        return self._client

    def log(self, payload: dict[str, Any]) -> None:
        client = self._get_client()
        if not client:
            return

        allowed = {
            "occurred_at",
            "tool_name",
            "status",
            "duration_ms",
            "user_id",
            "user_email",
            "surface",
            "connector_name",
            "is_mutation",
            "meta",
        }
        base_row = {key: value for key, value in payload.items() if key in allowed and value is not None}
        extra = {key: value for key, value in payload.items() if key not in allowed and value is not None}
        if extra:
            meta = base_row.get("meta") if isinstance(base_row.get("meta"), dict) else {}
            base_row["meta"] = {**meta, **_clean_meta_dict(extra)}

        try:
            client.table("mcp_tool_events").insert(base_row).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to record MCP tool event: %s", exc)


mcp_event_logger = MCPEventLogger()


@dataclass
class MCPToolInvocation:
    tool_name: str
    is_mutation: bool | None = None
    user: MCPUser | None = field(default_factory=get_current_mcp_user)
    _started_at: float = field(default_factory=perf_counter)

    def success(self, **meta: Any) -> None:
        self._record("success", **meta)

    def error(self, *, error_type: str | None = None, **meta: Any) -> None:
        if error_type:
            meta.setdefault("error_type", error_type)
        self._record("error", **meta)

    def _record(self, status: str, **meta: Any) -> None:
        duration_ms = max(0, int((perf_counter() - self._started_at) * 1000))
        safe_meta = _clean_meta_dict(meta)
        user_id = self.user.user_id if self.user else None
        normalized_user_id = _coerce_uuid(user_id)
        if user_id and normalized_user_id is None:
            safe_meta.setdefault("raw_user_id", user_id)

        suffix = " ".join(f"{key}={value}" for key, value in safe_meta.items())
        if suffix:
            suffix = f" {suffix}"
        logger.info(
            "MCP tool event | tool=%s user_id=%s status=%s duration_ms=%s%s",
            self.tool_name,
            user_id,
            status,
            duration_ms,
            suffix,
        )

        mcp_event_logger.log(
            {
                "tool_name": self.tool_name,
                "status": status,
                "duration_ms": duration_ms,
                "user_id": normalized_user_id,
                "user_email": self.user.email if self.user else None,
                "surface": MCP_SURFACE,
                "connector_name": MCP_CONNECTOR_NAME,
                "is_mutation": (
                    self.is_mutation if self.is_mutation is not None else _is_mutation_tool(self.tool_name)
                ),
                "meta": safe_meta,
            }
        )


def start_mcp_tool_invocation(tool_name: str, *, is_mutation: bool | None = None) -> MCPToolInvocation:
    return MCPToolInvocation(tool_name=tool_name, is_mutation=is_mutation)
