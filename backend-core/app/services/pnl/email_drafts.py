"""Monthly P&L email draft generation and persistence."""

from __future__ import annotations

import json
import logging
from typing import Any

from supabase import Client

from .email_brief import PNLEmailBriefService
from .email_prompt import PROMPT_VERSION, build_monthly_pnl_email_prompt_messages

_logger = logging.getLogger(__name__)


async def generate_email_draft(
    db: Client,
    client_id: str,
    *,
    report_month: str,
    marketplace_codes: list[str] | None = None,
    comparison_mode: str = "auto",
    recipient_name: str | None = None,
    sender_name: str | None = None,
    sender_role: str | None = None,
    agency_name: str | None = None,
    created_by: str | None = None,
) -> dict[str, Any]:
    """Generate and persist a Monthly P&L highlights email draft."""
    from ..theclaw.openai_client import call_chat_completion

    brief_service = PNLEmailBriefService(db)
    brief = await brief_service.build_client_brief_async(
        client_id,
        report_month,
        marketplace_codes=marketplace_codes,
        comparison_mode=comparison_mode,
    )
    sections = list(brief.get("sections") or [])
    if not sections:
        raise ValueError(f"No Monthly P&L brief sections available for client {client_id}")

    messages = build_monthly_pnl_email_prompt_messages(
        brief=brief,
        recipient_name=recipient_name,
        sender_name=sender_name,
        sender_role=sender_role,
        agency_name=agency_name,
    )

    response = await call_chat_completion(
        messages=messages,
        temperature=0.4,
        max_tokens=3500,
        response_format={"type": "json_object"},
    )

    raw_content = response.get("content") or ""
    try:
        parsed = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        _logger.warning("Monthly P&L email draft LLM returned invalid JSON: %s", raw_content[:200])
        raise ValueError("LLM returned invalid JSON for Monthly P&L email draft")

    subject = str(parsed.get("subject") or "").strip()
    body = str(parsed.get("body") or "").strip()
    if not subject:
        raise ValueError("LLM returned empty email subject")
    if not body:
        raise ValueError("LLM returned empty email body")

    marketplace_scope = ",".join(
        str(section.get("marketplace_code") or "").strip().upper()
        for section in sections
        if str(section.get("marketplace_code") or "").strip()
    )
    profile_ids = [
        str(section.get("profile_id") or "").strip()
        for section in sections
        if str(section.get("profile_id") or "").strip()
    ]

    row: dict[str, Any] = {
        "client_id": client_id,
        "report_month": report_month,
        "draft_kind": "monthly_pnl_highlights_email",
        "prompt_version": PROMPT_VERSION,
        "comparison_mode_requested": str(brief.get("comparison_mode_requested") or comparison_mode),
        "comparison_mode_used": str(brief.get("comparison_mode_used") or comparison_mode),
        "marketplace_scope": marketplace_scope,
        "profile_ids": profile_ids,
        "brief_payload": brief,
        "subject": subject,
        "body": body,
        "model": str(response.get("model") or ""),
    }
    if created_by:
        row["created_by"] = created_by

    insert_resp = db.table("monthly_pnl_email_drafts").insert(row).execute()
    inserted = (insert_resp.data or [None])[0] if hasattr(insert_resp, "data") else None
    if not inserted:
        raise RuntimeError("Failed to persist Monthly P&L email draft")

    return {
        "id": inserted.get("id"),
        "client_id": client_id,
        "report_month": report_month,
        "draft_kind": row["draft_kind"],
        "prompt_version": PROMPT_VERSION,
        "comparison_mode_requested": row["comparison_mode_requested"],
        "comparison_mode_used": row["comparison_mode_used"],
        "marketplace_scope": marketplace_scope,
        "profile_ids": profile_ids,
        "subject": subject,
        "body": body,
        "model": row["model"],
        "created_at": inserted.get("created_at"),
        "brief": brief,
    }
