"""Monthly P&L-related MCP tools."""

from __future__ import annotations

import logging
from typing import Any

from ...auth import _get_supabase_admin_client
from ...services.pnl.email_drafts import generate_email_draft
from ...services.pnl.email_prompt import PROMPT_VERSION
from ...services.pnl.email_brief import PNLEmailBriefService
from ...services.pnl.profiles import PNLNotFoundError, PNLProfileService, PNLValidationError
from ...services.pnl.report import PNLReportService
from .clients import resolve_client_name
from ..auth import get_current_pilot_user

_logger = logging.getLogger(__name__)


def _log_tool_outcome(tool_name: str, outcome: str, **extra: Any) -> None:
    user = get_current_pilot_user()
    suffix = " ".join(f"{key}={value}" for key, value in extra.items())
    if suffix:
        suffix = f" {suffix}"
    _logger.info(
        "MCP tool invocation | tool=%s user_id=%s outcome=%s%s",
        tool_name,
        user.user_id if user else None,
        outcome,
        suffix,
    )


def list_monthly_pnl_profiles_for_client(client_id: str) -> dict[str, list[dict[str, Any]]]:
    """List reportable Monthly P&L profiles for a canonical client."""
    normalized_client_id = str(client_id or "").strip()
    if not normalized_client_id:
        return {"profiles": []}

    db = _get_supabase_admin_client()
    profile_svc = PNLProfileService(db)
    client_name = resolve_client_name(db, normalized_client_id)
    profiles = profile_svc.list_profiles(normalized_client_id)

    active_months_resp = (
        db.table("monthly_pnl_import_months")
        .select("profile_id, entry_month")
        .eq("is_active", True)
        .execute()
    )
    active_month_rows = (
        active_months_resp.data if isinstance(active_months_resp.data, list) else []
    )

    month_ranges_by_profile: dict[str, dict[str, str]] = {}
    for row in active_month_rows:
        if not isinstance(row, dict):
            continue
        profile_id = str(row.get("profile_id") or "").strip()
        entry_month = str(row.get("entry_month") or "").strip()
        if not profile_id or not entry_month:
            continue
        month_range = month_ranges_by_profile.setdefault(
            profile_id,
            {
                "first_active_month": entry_month,
                "last_active_month": entry_month,
                "active_month_count": 0,
            },
        )
        month_range["first_active_month"] = min(month_range["first_active_month"], entry_month)
        month_range["last_active_month"] = max(month_range["last_active_month"], entry_month)
        month_range["active_month_count"] += 1

    result_profiles: list[dict[str, Any]] = []
    for row in profiles:
        if not isinstance(row, dict):
            continue
        profile_id = str(row.get("id") or "").strip()
        if not profile_id or profile_id not in month_ranges_by_profile:
            continue
        month_range = month_ranges_by_profile[profile_id]
        result_profiles.append(
            {
                "profile_id": profile_id,
                "client_id": normalized_client_id,
                "client_name": client_name,
                "marketplace_code": str(row.get("marketplace_code") or "").strip().upper(),
                "currency_code": str(row.get("currency_code") or "").strip().upper() or None,
                "status": str(row.get("status") or "").strip() or None,
                "first_active_month": month_range["first_active_month"],
                "last_active_month": month_range["last_active_month"],
                "active_month_count": month_range["active_month_count"],
            }
        )

    result_profiles.sort(
        key=lambda row: (
            str(row.get("marketplace_code") or ""),
            str(row.get("profile_id") or ""),
        )
    )
    return {"profiles": result_profiles}


async def get_monthly_pnl_report_for_profile(
    profile_id: str,
    *,
    filter_mode: str = "last_3",
    start_month: str | None = None,
    end_month: str | None = None,
) -> dict[str, Any]:
    """Return a Monthly P&L report envelope for one concrete profile."""
    normalized_profile_id = str(profile_id or "").strip()
    if not normalized_profile_id:
        raise ValueError("profile_id is required")

    db = _get_supabase_admin_client()
    profile_svc = PNLProfileService(db)
    report_svc = PNLReportService(db)

    try:
        profile = profile_svc.get_profile(normalized_profile_id)
        report = await report_svc.build_report_async(
            normalized_profile_id,
            filter_mode=filter_mode,
            start_month=start_month,
            end_month=end_month,
        )
    except (PNLNotFoundError, PNLValidationError) as exc:
        raise ValueError(str(exc)) from exc

    client_id = str(profile.get("client_id") or "").strip()
    client_name = resolve_client_name(db, client_id)

    report_profile = dict(report.get("profile") or {})
    report_profile.update(
        {
            "profile_id": normalized_profile_id,
            "client_id": client_id,
            "client_name": client_name,
            "marketplace_code": str(profile.get("marketplace_code") or "").strip().upper(),
            "currency_code": str(profile.get("currency_code") or "").strip().upper() or None,
            "status": str(profile.get("status") or "").strip() or None,
        }
    )

    return {
        "profile": report_profile,
        "months": list(report.get("months") or []),
        "line_items": list(report.get("line_items") or []),
        "warnings": list(report.get("warnings") or []),
    }


async def get_monthly_pnl_email_brief_for_client(
    client_id: str,
    *,
    report_month: str,
    marketplace_codes: list[str] | None = None,
    comparison_mode: str = "auto",
) -> dict[str, Any]:
    """Return a structured Monthly P&L email brief for one client/month."""
    normalized_client_id = str(client_id or "").strip()
    if not normalized_client_id:
        raise ValueError("client_id is required")

    db = _get_supabase_admin_client()
    brief_service = PNLEmailBriefService(db)

    try:
        return await brief_service.build_client_brief_async(
            normalized_client_id,
            report_month,
            marketplace_codes=marketplace_codes,
            comparison_mode=comparison_mode,
        )
    except (PNLNotFoundError, PNLValidationError) as exc:
        raise ValueError(str(exc)) from exc


async def draft_monthly_pnl_email_for_client(
    client_id: str,
    *,
    report_month: str,
    marketplace_codes: list[str] | None = None,
    comparison_mode: str = "auto",
    recipient_name: str | None = None,
    sender_name: str | None = None,
    sender_role: str | None = None,
    agency_name: str | None = None,
) -> dict[str, Any]:
    """Generate and persist a Monthly P&L email draft for one client/month."""
    normalized_client_id = str(client_id or "").strip()
    if not normalized_client_id:
        raise ValueError("client_id is required")

    db = _get_supabase_admin_client()
    result = await generate_email_draft(
        db,
        normalized_client_id,
        report_month=report_month,
        marketplace_codes=marketplace_codes,
        comparison_mode=comparison_mode,
        recipient_name=recipient_name,
        sender_name=sender_name,
        sender_role=sender_role,
        agency_name=agency_name,
        created_by=(get_current_pilot_user().user_id if get_current_pilot_user() else None),
    )
    return {
        "draft_id": str(result.get("id") or "").strip(),
        "client_id": normalized_client_id,
        "report_month": str(result.get("report_month") or report_month),
        "draft_kind": "monthly_pnl_highlights_email",
        "prompt_version": PROMPT_VERSION,
        "comparison_mode_requested": str(result.get("comparison_mode_requested") or comparison_mode),
        "comparison_mode_used": str(result.get("comparison_mode_used") or comparison_mode),
        "marketplace_scope": str(result.get("marketplace_scope") or "").strip(),
        "profile_ids": [str(item) for item in (result.get("profile_ids") or []) if item],
        "subject": str(result.get("subject") or "").strip(),
        "body": str(result.get("body") or "").strip(),
        "model": str(result.get("model") or "").strip() or None,
        "created_at": result.get("created_at"),
    }


def register_pnl_tools(mcp: Any) -> None:
    @mcp.tool(
        name="list_monthly_pnl_profiles",
        description=(
            "List reportable Monthly P&L profiles for a canonical Agency OS "
            "client ID. Returns only profiles that currently have active "
            "month coverage."
        ),
        structured_output=True,
    )
    def list_monthly_pnl_profiles(client_id: str) -> dict[str, list[dict[str, Any]]]:
        _log_tool_outcome("list_monthly_pnl_profiles", "started")
        result = list_monthly_pnl_profiles_for_client(client_id)
        _log_tool_outcome(
            "list_monthly_pnl_profiles",
            "success",
            profiles=len(result.get("profiles", [])),
        )
        return result

    @mcp.tool(
        name="get_monthly_pnl_report",
        description=(
            "Return the Monthly P&L report for one concrete profile ID over a "
            "requested month window. This is a read-only tool that reuses the "
            "current Agency OS report builder."
        ),
        structured_output=True,
    )
    async def get_monthly_pnl_report(
        profile_id: str,
        filter_mode: str = "last_3",
        start_month: str | None = None,
        end_month: str | None = None,
    ) -> dict[str, Any]:
        _log_tool_outcome("get_monthly_pnl_report", "started")
        result = await get_monthly_pnl_report_for_profile(
            profile_id,
            filter_mode=filter_mode,
            start_month=start_month,
            end_month=end_month,
        )
        _log_tool_outcome("get_monthly_pnl_report", "success", profile_id=profile_id)
        return result

    @mcp.tool(
        name="get_monthly_pnl_email_brief",
        description=(
            "Build a structured, read-only Monthly P&L email brief for one "
            "client and one report month. Use this when preparing a future "
            "client-facing P&L highlights draft from canonical Agency OS data."
        ),
        structured_output=True,
    )
    async def get_monthly_pnl_email_brief(
        client_id: str,
        report_month: str,
        marketplace_codes: list[str] | None = None,
        comparison_mode: str = "auto",
    ) -> dict[str, Any]:
        _log_tool_outcome("get_monthly_pnl_email_brief", "started")
        result = await get_monthly_pnl_email_brief_for_client(
            client_id,
            report_month=report_month,
            marketplace_codes=marketplace_codes,
            comparison_mode=comparison_mode,
        )
        _log_tool_outcome(
            "get_monthly_pnl_email_brief",
            "success",
            client_id=client_id,
            sections=len(result.get("sections", [])),
        )
        return result

    @mcp.tool(
        name="draft_monthly_pnl_email",
        description=(
            "Generate and persist a Monthly P&L highlights email draft for one "
            "client and one report month. This is a mutating tool built on top "
            "of the structured Monthly P&L brief layer."
        ),
        structured_output=True,
    )
    async def draft_monthly_pnl_email(
        client_id: str,
        report_month: str,
        marketplace_codes: list[str] | None = None,
        comparison_mode: str = "auto",
        recipient_name: str | None = None,
        sender_name: str | None = None,
        sender_role: str | None = None,
        agency_name: str | None = None,
    ) -> dict[str, Any]:
        _log_tool_outcome("draft_monthly_pnl_email", "started")
        result = await draft_monthly_pnl_email_for_client(
            client_id,
            report_month=report_month,
            marketplace_codes=marketplace_codes,
            comparison_mode=comparison_mode,
            recipient_name=recipient_name,
            sender_name=sender_name,
            sender_role=sender_role,
            agency_name=agency_name,
        )
        _log_tool_outcome(
            "draft_monthly_pnl_email",
            "success",
            draft_id=result.get("draft_id"),
        )
        return result
