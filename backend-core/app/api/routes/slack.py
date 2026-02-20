import asyncio
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse

from ...services.agencyclaw import orchestrate_dm_message
from ...services.agencyclaw.conversation_buffer import (
    append_exchange,
    compact_exchanges,
)
from ...services.agencyclaw.policy_gate import (
    evaluate_tool_policy,
    resolve_actor_context,
    resolve_surface_context,
)
from ...services.agencyclaw.brand_context_resolver import (
    BrandResolution,
    resolve_brand_context,
)
from ...services.agencyclaw.brand_mapping_remediation import (
    apply_brand_mapping_remediation_plan,
    build_brand_mapping_remediation_plan,
)
from ...services.agencyclaw.command_center_lookup import (
    audit_brand_mappings,
    format_brand_list,
    format_client_list,
    format_mapping_audit,
    list_brands,
    lookup_clients,
)
from ...services.agencyclaw.grounded_task_draft import build_grounded_task_draft
from ...services.agencyclaw.kb_retrieval import retrieve_kb_context
from ...services.agencyclaw.plan_executor import execute_plan
from ...services.agencyclaw.planner import generate_plan
from ...services.agencyclaw.pending_resolution import resolve_pending_action
from ...services.agencyclaw.tool_registry import get_tool_descriptions_for_prompt
from ...services.agencyclaw.clickup_reliability import (
    RetryExhaustedError,
    build_idempotency_key,
    check_duplicate,
    emit_orphan_event,
    retry_with_backoff,
)
from ...services.ai_token_usage_logger import log_ai_token_usage
from ...services.clickup import ClickUpError, ClickUpConfigurationError, get_clickup_service
from ...services.agencyclaw.preference_memory import PreferenceMemoryService
from ...services.playbook_session import get_playbook_session_service, get_supabase_admin_client
from ...services.sop_sync import SOPSyncService
from ...services.slack import (
    SlackAPIError,
    SlackReceiptService,
    get_slack_service,
    get_slack_signing_secret,
    verify_slack_signature,
)

_logger = logging.getLogger(__name__)

# C4C: In-memory concurrency guard for task mutations.
# Prevents two simultaneous creates for the same target from racing past
# the duplicate check.  Single-process only; see plan for multi-worker TODO.
_task_create_inflight: set[str] = set()
_task_create_inflight_lock = asyncio.Lock()

router = APIRouter(prefix="/slack", tags=["slack"])


def _is_llm_orchestrator_enabled() -> bool:
    """Check if the LLM DM orchestrator feature flag is enabled."""
    return os.environ.get("AGENCYCLAW_LLM_DM_ORCHESTRATOR", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _is_planner_enabled() -> bool:
    """Check if the C10D planner feature flag is enabled."""
    return os.environ.get("AGENCYCLAW_ENABLE_PLANNER", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _is_legacy_intent_fallback_enabled() -> bool:
    """Whether regex-based deterministic intent fallback is enabled.

    Defaults:
    - LLM orchestrator OFF -> enabled (backward compatibility / local dev).
    - LLM orchestrator ON  -> disabled (LLM-first conversational runtime).

    Override with ``AGENCYCLAW_ENABLE_LEGACY_INTENTS=1`` to force-enable.
    """
    if not _is_llm_orchestrator_enabled():
        return True
    return os.environ.get("AGENCYCLAW_ENABLE_LEGACY_INTENTS", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _get_receipt_service() -> SlackReceiptService:
    return SlackReceiptService(get_supabase_admin_client())



def _parse_json(body: bytes) -> dict[str, Any]:
    try:
        value = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    return value


def _verify_request_or_401(*, signing_secret: str, request: Request, body: bytes) -> None:
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    if not verify_slack_signature(signing_secret, timestamp, body, signature):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")


def _build_client_picker_blocks(clients: list[dict[str, Any]]) -> list[dict[str, Any]]:
    top = clients[:10]
    blocks: list[dict[str, Any]] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "Which client are you working on today?"},
        }
    ]

    # Slack actions block supports up to 5 elements; cap overall at 10.
    for i in range(0, len(top), 5):
        chunk = top[i : i + 5]
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": str(client.get("name", "Client"))},
                        "action_id": f"select_client_{client.get('id')}",
                        "value": str(client.get("id")),
                    }
                    for client in chunk
                ],
            }
        )

    return blocks


def _build_brand_picker_blocks(
    brands: list[dict[str, Any]], client_name: str,
) -> list[dict[str, Any]]:
    """Build Slack action blocks for brand selection (same pattern as client picker)."""
    top = brands[:10]
    blocks: list[dict[str, Any]] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"Which brand under *{client_name}*?"},
        }
    ]
    for i in range(0, len(top), 5):
        chunk = top[i : i + 5]
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": str(b.get("name", "Brand"))},
                        "action_id": f"select_brand_{b.get('id')}",
                        "value": str(b.get("id")),
                    }
                    for b in chunk
                ],
            }
        )
    return blocks


# Patterns that indicate a weekly task list query.
# Captures an optional trailing client name after "for <client>".
_WEEKLY_TASK_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"(?:what(?:'s| is) being worked on|what(?:'s| are) the tasks|"
        r"show (?:me )?tasks|list tasks|weekly tasks|this week(?:'s)? tasks)"
        r"(?:\s+(?:this week\s*)?(?:for\s+(.+))?)?$"
    ),
    re.compile(
        r"tasks?\s+(?:this week\s+)?for\s+(.+?)(?:\s+this week)?$"
    ),
]


def _sanitize_client_name_hint(value: str) -> str:
    """Normalize captured client hints (e.g., 'distex?' -> 'distex')."""
    collapsed = " ".join((value or "").strip().split())
    return re.sub(r"[?!.,:;]+$", "", collapsed).strip()


# Patterns for task creation intent.
# Supports: "create task for <client>: <title>", "add a task: <title>", "new task for <client>", etc.
_CREATE_TASK_PATTERN = re.compile(
    r"(?:create|add|new)\s+(?:a\s+)?tasks?"
    r"(?:\s+for\s+([^:]+?))?"  # optional "for <client>"
    r"(?:\s*:\s*(.+))?"        # optional ": <title>"
    r"$"
)

# Patterns for confirming a draft task creation.
_CONFIRM_DRAFT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^(?:create anyway|create as draft|just create it|yes,?\s*create(?:\s+it)?)$"),
]


def _classify_message(text: str) -> tuple[str, dict[str, Any]]:
    original = " ".join((text or "").strip().split())
    t = original.lower()
    if t.startswith("switch to "):
        return ("switch_client", {"client_name": t.removeprefix("switch to ").strip()})
    if t.startswith("work on "):
        return ("switch_client", {"client_name": t.removeprefix("work on ").strip()})

    # C10E: Set / clear default client preferences
    if t.startswith("set my default client to "):
        return ("set_default_client", {"client_name": t.removeprefix("set my default client to ").strip()})
    if t.startswith("set default client "):
        return ("set_default_client", {"client_name": t.removeprefix("set default client ").strip()})
    if t in ("clear my defaults", "clear defaults", "clear my default client"):
        return ("clear_defaults", {})

    # Task creation (check BEFORE weekly tasks — "create task for X" must not match "tasks for X")
    m = _CREATE_TASK_PATTERN.match(t)
    if m:
        client_hint = _sanitize_client_name_hint(m.group(1) or "")
        # Preserve original casing for the task title by extracting from original text
        title_start = m.start(2) if m.group(2) else -1
        task_title = original[title_start:].strip() if title_start >= 0 else ""
        return ("create_task", {"client_name": client_hint, "task_title": task_title})

    # Weekly task list queries
    for pattern in _WEEKLY_TASK_PATTERNS:
        m = pattern.search(t)
        if m:
            client_name = _sanitize_client_name_hint((m.group(1) or "")) if m.lastindex else ""
            return ("weekly_tasks", {"client_name": client_name})

    # Confirm draft creation (only meaningful when pending state exists in session)
    for pattern in _CONFIRM_DRAFT_PATTERNS:
        if pattern.match(t):
            return ("confirm_draft_task", {})

    # C11A: Command Center read-only skills
    if any(kw in t for kw in ("show me clients", "list clients", "my clients")):
        return ("cc_client_lookup", {"query": ""})
    if any(kw in t for kw in ("list all brands", "list brands", "show brands")):
        return ("cc_brand_list_all", {})
    if any(kw in t for kw in ("missing clickup mapping", "mapping audit", "brands missing")):
        return ("cc_brand_clickup_mapping_audit", {})

    # C11E: Brand mapping remediation
    def _extract_remediation_client_hint(trigger: str) -> str:
        idx = t.find(trigger)
        if idx < 0:
            return ""
        tail = t[idx + len(trigger):].strip()
        if not tail.startswith("for "):
            return ""
        return _sanitize_client_name_hint(tail.removeprefix("for ").strip())

    for kw in (
        "apply brand mapping remediation",
        "apply mapping remediation",
        "run mapping remediation now",
        "apply remediation",
    ):
        if kw in t:
            client_hint = _extract_remediation_client_hint(kw)
            return (
                "cc_brand_mapping_remediation_apply",
                {"client_name": client_hint} if client_hint else {},
            )

    for kw in (
        "preview brand mapping remediation",
        "preview mapping remediation",
        "show mapping remediation plan",
        "what can we auto-fix for mappings",
        "remediation preview",
        "mapping remediation",
    ):
        if kw in t:
            client_hint = _extract_remediation_client_hint(kw)
            return (
                "cc_brand_mapping_remediation_preview",
                {"client_name": client_hint} if client_hint else {},
            )

    return ("help", {})


def _help_text() -> str:
    return (
        "I can help with ClickUp tasks, weekly status, and SOP-based work.\n\n"
        "Ask naturally, for example:\n"
        "- What's being worked on this week for Distex?\n"
        "- Create a task for Distex: Set up 20% coupon for Thorinox\n"
        "- Start n-gram research for Distex\n"
        "- Switch to Revant\n"
        "- Show me clients / list brands / brands missing clickup mapping\n"
        "- Preview brand mapping remediation / apply brand mapping remediation"
    )


_WEEKLY_TASK_CAP = 200


def _current_week_range_ms() -> tuple[int, int]:
    """Return (start_ms, end_ms) for the current ISO week (Monday 00:00 UTC through Sunday 23:59)."""
    now = datetime.now(timezone.utc)
    monday = now - timedelta(days=now.weekday())
    start = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def _format_task_line(task: dict[str, Any]) -> str:
    name = str(task.get("name") or "Untitled")
    url = task.get("url") or ""
    status_obj = task.get("status")
    status = str(status_obj.get("status") or "") if isinstance(status_obj, dict) else ""

    assignees = task.get("assignees") or []
    assignee_names = []
    for a in (assignees if isinstance(assignees, list) else []):
        if isinstance(a, dict):
            assignee_names.append(str(a.get("username") or a.get("initials") or ""))

    parts = []
    if url:
        parts.append(f"<{url}|{name}>")
    else:
        parts.append(name)
    if status:
        parts.append(f"[{status}]")
    if assignee_names:
        parts.append(f"({', '.join(n for n in assignee_names if n)})")
    return "• " + " ".join(parts)


def _format_weekly_tasks_response(
    *,
    client_name: str,
    tasks: list[dict[str, Any]],
    total_fetched: int,
    brand_names: list[str],
) -> str:
    if not tasks:
        brands = ", ".join(brand_names) if brand_names else "no brands"
        return f"No tasks found this week for *{client_name}* (checked: {brands})."

    header = f"*Tasks this week for {client_name}* ({len(tasks)} task{'s' if len(tasks) != 1 else ''}):\n"
    lines = [_format_task_line(t) for t in tasks[:_WEEKLY_TASK_CAP]]
    body = "\n".join(lines)

    truncation = ""
    if total_fetched > _WEEKLY_TASK_CAP:
        truncation = f"\n\n_Showing {_WEEKLY_TASK_CAP} of {total_fetched} tasks. Check ClickUp for the full list._"

    return header + body + truncation


async def _handle_weekly_tasks(
    *,
    slack_user_id: str,
    channel: str,
    client_name_hint: str,
    session_service: Any,
    slack: Any,
) -> None:
    """Handle 'weekly tasks for <client>' intent."""
    session = await asyncio.to_thread(session_service.get_or_create_session, slack_user_id)

    # --- Resolve client ---
    client_id: str | None = None
    client_name: str = ""

    if client_name_hint:
        matches = await asyncio.to_thread(
            session_service.find_client_matches, session.profile_id, client_name_hint
        )
        if not matches:
            await slack.post_message(
                channel=channel,
                text=f"I couldn't find a client matching *{client_name_hint}*.",
            )
            return
        if len(matches) > 1:
            blocks = _build_client_picker_blocks(matches)
            await slack.post_message(
                channel=channel,
                text=f"Multiple clients match *{client_name_hint}*. Pick one and ask again:",
                blocks=blocks,
            )
            return
        client_id = str(matches[0].get("id") or "")
        client_name = str(matches[0].get("name") or client_name_hint)
    elif session.active_client_id:
        client_id = session.active_client_id
        client_name = await asyncio.to_thread(session_service.get_client_name, client_id) or "Client"
    else:
        clients = await asyncio.to_thread(session_service.list_clients_for_picker, session.profile_id)
        if clients:
            blocks = _build_client_picker_blocks(clients)
            await slack.post_message(
                channel=channel,
                text="Which client? Pick one and ask again:",
                blocks=blocks,
            )
        else:
            await slack.post_message(
                channel=channel,
                text="I couldn't find any clients. Ask an admin to assign you.",
            )
        return

    if not client_id:
        await slack.post_message(channel=channel, text="Could not resolve client.")
        return

    # --- Resolve brand destinations ---
    destinations = await asyncio.to_thread(
        session_service.get_all_brand_destinations_for_client, client_id
    )
    if not destinations:
        await slack.post_message(
            channel=channel,
            text=f"No brands with ClickUp mapping found for *{client_name}*. Ask an admin to configure brand destinations.",
        )
        return

    # --- Fetch tasks from ClickUp ---
    start_ms, end_ms = _current_week_range_ms()
    clickup = None
    all_tasks: list[dict[str, Any]] = []
    brand_names: list[str] = []

    try:
        clickup = get_clickup_service()

        for dest in destinations:
            list_id = dest.get("clickup_list_id")
            space_id = dest.get("clickup_space_id")
            brand_names.append(str(dest.get("name") or "Unknown"))

            if list_id:
                target_list_id = str(list_id)
            elif space_id:
                try:
                    target_list_id = await clickup.resolve_default_list_id(str(space_id))
                except (ClickUpConfigurationError, ClickUpError):
                    continue
            else:
                continue

            try:
                tasks = await clickup.get_tasks_in_list_all_pages(
                    target_list_id,
                    date_updated_gt=start_ms,
                    date_updated_lt=end_ms,
                    include_closed=False,
                    max_tasks=_WEEKLY_TASK_CAP + 1,
                )
                all_tasks.extend(tasks)
            except ClickUpError:
                # If one brand list fails, continue with others.
                continue

    except (ClickUpConfigurationError, ClickUpError) as exc:
        await slack.post_message(
            channel=channel,
            text=f"Failed to fetch tasks from ClickUp: {exc}",
        )
        return
    finally:
        if clickup:
            await clickup.aclose()

    # Deduplicate tasks by ClickUp task id
    seen_ids: set[str] = set()
    unique_tasks: list[dict[str, Any]] = []
    for t in all_tasks:
        tid = str(t.get("id") or "")
        if tid and tid not in seen_ids:
            seen_ids.add(tid)
            unique_tasks.append(t)

    total_fetched = len(unique_tasks)
    response_text = _format_weekly_tasks_response(
        client_name=client_name,
        tasks=unique_tasks,
        total_fetched=total_fetched,
        brand_names=brand_names,
    )
    await slack.post_message(channel=channel, text=response_text)


async def _resolve_client_for_task(
    *,
    client_name_hint: str,
    session: Any,
    session_service: Any,
    channel: str,
    slack: Any,
    pref_service: Any | None = None,
) -> tuple[str | None, str]:
    """Resolve client_id + client_name from hint or active session.

    Returns (client_id, client_name).  client_id is None on failure (message already sent).

    Precedence: explicit hint > actor preference > session active client > picker.
    """
    if client_name_hint:
        matches = await asyncio.to_thread(
            session_service.find_client_matches, session.profile_id, client_name_hint
        )
        if not matches:
            await slack.post_message(
                channel=channel,
                text=f"I couldn't find a client matching *{client_name_hint}*.",
            )
            return None, ""
        if len(matches) > 1:
            blocks = _build_client_picker_blocks(matches)
            await slack.post_message(
                channel=channel,
                text=f"Multiple clients match *{client_name_hint}*. Pick one and try again:",
                blocks=blocks,
            )
            return None, ""
        return str(matches[0].get("id") or ""), str(matches[0].get("name") or client_name_hint)

    # C10E: Check actor preference (durable default)
    if pref_service and session.profile_id:
        pref_client_id = await asyncio.to_thread(
            pref_service.get_default_client_id, session.profile_id
        )
        if pref_client_id:
            name = await asyncio.to_thread(session_service.get_client_name, pref_client_id)
            if name:
                return pref_client_id, name

    if session.active_client_id:
        name = await asyncio.to_thread(session_service.get_client_name, session.active_client_id)
        return session.active_client_id, name or "Client"

    clients = await asyncio.to_thread(session_service.list_clients_for_picker, session.profile_id)
    if clients:
        blocks = _build_client_picker_blocks(clients)
        await slack.post_message(
            channel=channel,
            text="Which client is this task for? Pick one and try again:",
            blocks=blocks,
        )
    else:
        await slack.post_message(
            channel=channel,
            text="I couldn't find any clients. Ask an admin to assign you.",
        )
    return None, ""


# ---------------------------------------------------------------------------
# C11D: Brand context resolution helper
# ---------------------------------------------------------------------------


async def _resolve_brand_for_task(
    *,
    client_id: str,
    client_name: str,
    task_text: str,
    brand_hint: str,
    session: Any,
    session_service: Any,
    channel: str,
    slack: Any,
) -> BrandResolution:
    """Resolve brand context for task creation.

    Fetches brands, calls the pure resolver, posts picker if ambiguous.
    """
    brands = await asyncio.to_thread(
        session_service.get_brands_with_context_for_client, client_id,
    )
    resolution = resolve_brand_context(brands, brand_hint=brand_hint, task_text=task_text)

    if resolution["mode"] in ("ambiguous_brand", "ambiguous_destination"):
        qualifier = (
            "different ClickUp destinations"
            if resolution["mode"] == "ambiguous_destination"
            else "multiple brands"
        )
        blocks = _build_brand_picker_blocks(resolution["candidates"], client_name)
        await slack.post_message(
            channel=channel,
            text=f"*{client_name}* has {qualifier}. Which brand is this for?",
            blocks=blocks,
        )

    return resolution


# ---------------------------------------------------------------------------
# C11A: Command Center read-only skill handler
# ---------------------------------------------------------------------------


async def _resolve_cc_client_hint(
    *,
    args: dict[str, Any],
    session_service: Any,
    session: Any,
    channel: str,
    slack: Any,
) -> str | None | bool:
    """Resolve optional client_name hint for CC skills.

    Returns:
    - ``None`` if no client_name hint was provided (scan all).
    - A client_id string on single match.
    - ``False`` if resolution failed (message already posted to Slack).
    """
    client_hint = str(args.get("client_name") or "").strip()
    if not client_hint:
        return None

    matches = await asyncio.to_thread(
        session_service.find_client_matches, session.profile_id, client_hint,
    )
    if not matches:
        await slack.post_message(
            channel=channel,
            text=f"I couldn't find a client matching *{client_hint}*.",
        )
        return False

    if len(matches) > 1:
        blocks = _build_client_picker_blocks(matches)
        await slack.post_message(
            channel=channel,
            text=f"Multiple clients match *{client_hint}*. Pick one and try again:",
            blocks=blocks,
        )
        return False

    return str(matches[0].get("id") or "")


def _format_remediation_preview(plan: list[dict[str, Any]]) -> str:
    """Format a remediation plan as a human-readable Slack message."""
    if not plan:
        return "All brands have ClickUp mappings. Nothing to remediate."

    safe = [item for item in plan if item.get("safe_to_apply")]
    blocked = [item for item in plan if not item.get("safe_to_apply")]

    lines: list[str] = [
        f"*Brand Mapping Remediation Preview*",
        f"Total items: {len(plan)} | Safe to apply: {len(safe)} | Blocked: {len(blocked)}",
        "",
    ]

    if safe:
        lines.append("*Safe to apply:*")
        for item in safe[:20]:
            lines.append(
                f"  - {item.get('brand_name', '?')} ({item.get('client_name', '?')}): "
                f"space={item.get('proposed_space_id', '—')}, list={item.get('proposed_list_id', '—')}"
            )
        if len(safe) > 20:
            lines.append(f"  … and {len(safe) - 20} more")

    if blocked:
        lines.append("")
        lines.append("*Blocked (needs manual fix):*")
        for item in blocked[:10]:
            lines.append(
                f"  - {item.get('brand_name', '?')} ({item.get('client_name', '?')}): {item.get('reason', '—')}"
            )
        if len(blocked) > 10:
            lines.append(f"  … and {len(blocked) - 10} more")

    lines.append("")
    lines.append("To apply the safe items, say: *apply brand mapping remediation*")
    return "\n".join(lines)


def _format_remediation_apply_result(result: dict[str, Any]) -> str:
    """Format the apply result as a human-readable Slack message."""
    lines: list[str] = [
        "*Brand Mapping Remediation — Applied*",
        f"Applied: {result.get('applied', 0)} | Skipped: {result.get('skipped', 0)} | Failures: {len(result.get('failures', []))}",
    ]

    failures = result.get("failures") or []
    if failures:
        lines.append("")
        lines.append("*Failures:*")
        for f in failures[:10]:
            lines.append(f"  - brand {f.get('brand_id', '?')}: {f.get('error', '?')}")
        if len(failures) > 10:
            lines.append(f"  … and {len(failures) - 10} more")

    if result.get("applied", 0) > 0:
        lines.append("")
        lines.append("Run *preview brand mapping remediation* to verify remaining gaps.")

    return "\n".join(lines)


async def _handle_cc_skill(
    *,
    skill_id: str,
    args: dict[str, Any],
    session: Any,
    session_service: Any,
    channel: str,
    slack: Any,
) -> str:
    """Dispatch a Command Center read-only skill and post results.

    Returns a tool summary string for conversation history.
    """
    db = session_service.db

    if skill_id == "cc_client_lookup":
        query = str(args.get("query") or "")
        clients = await asyncio.to_thread(
            lookup_clients, db, session.profile_id, query,
        )
        await slack.post_message(channel=channel, text=format_client_list(clients))
        return "[Listed clients]"

    if skill_id == "cc_brand_list_all":
        # Optionally resolve client_name hint to client_id
        client_id: str | None = None
        client_hint = str(args.get("client_name") or "").strip()
        if client_hint:
            matches = await asyncio.to_thread(
                session_service.find_client_matches, session.profile_id, client_hint,
            )
            if not matches:
                await slack.post_message(
                    channel=channel,
                    text=f"I couldn't find a client matching *{client_hint}*.",
                )
                return "[Brand list client not found]"

            if len(matches) > 1:
                blocks = _build_client_picker_blocks(matches)
                await slack.post_message(
                    channel=channel,
                    text=f"Multiple clients match *{client_hint}*. Pick one and try again:",
                    blocks=blocks,
                )
                return "[Brand list client ambiguous]"

            client_id = str(matches[0].get("id") or "")

        brands = await asyncio.to_thread(list_brands, db, client_id)
        await slack.post_message(channel=channel, text=format_brand_list(brands))
        return "[Listed brands]"

    if skill_id == "cc_brand_clickup_mapping_audit":
        missing = await asyncio.to_thread(audit_brand_mappings, db)
        await slack.post_message(channel=channel, text=format_mapping_audit(missing))
        return "[Ran ClickUp mapping audit]"

    # C11E: Brand mapping remediation preview
    if skill_id == "cc_brand_mapping_remediation_preview":
        client_id = await _resolve_cc_client_hint(
            args=args, session_service=session_service, session=session,
            channel=channel, slack=slack,
        )
        if client_id is False:
            return "[Remediation preview client error]"

        plan = await asyncio.to_thread(
            build_brand_mapping_remediation_plan, db, client_id=client_id,
        )
        await slack.post_message(
            channel=channel, text=_format_remediation_preview(plan),
        )
        return "[Remediation preview]"

    # C11E: Brand mapping remediation apply
    if skill_id == "cc_brand_mapping_remediation_apply":
        client_id = await _resolve_cc_client_hint(
            args=args, session_service=session_service, session=session,
            channel=channel, slack=slack,
        )
        if client_id is False:
            return "[Remediation apply client error]"

        plan = await asyncio.to_thread(
            build_brand_mapping_remediation_plan, db, client_id=client_id,
        )
        result = await asyncio.to_thread(
            apply_brand_mapping_remediation_plan, db, plan, dry_run=False,
        )
        await slack.post_message(
            channel=channel, text=_format_remediation_apply_result(result),
        )
        return "[Remediation applied]"

    return ""


async def _execute_task_create(
    *,
    channel: str,
    session: Any,
    session_service: Any,
    slack: Any,
    client_id: str,
    client_name: str,
    task_title: str,
    task_description: str,
    brand_id: str | None = None,
    brand_name: str | None = None,
) -> None:
    """Create a ClickUp task and report the result in Slack.

    Wires C4A reliability primitives: idempotency key, duplicate suppression,
    retry/backoff, and orphan detection.

    Always clears pending_task_create from session context, even on early failures.
    """
    clickup = None
    idempotency_key = ""
    acquired_inflight = False
    try:
        if not session.profile_id:
            await slack.post_message(
                channel=channel,
                text="I couldn't link your Slack user to a profile. Ask an admin to set `profiles.slack_user_id`.",
            )
            return

        # C11D: Use pre-resolved brand if available, else fall back to auto-pick
        if brand_id:
            try:
                brand_resp = await asyncio.to_thread(
                    lambda: session_service.db.table("brands")
                    .select("id,name,clickup_space_id,clickup_list_id")
                    .eq("id", brand_id)
                    .limit(1)
                    .execute()
                )
                rows = brand_resp.data if isinstance(brand_resp.data, list) else []
                destination = rows[0] if rows else None
            except Exception:  # noqa: BLE001
                destination = None
        else:
            destination = await asyncio.to_thread(
                session_service.get_brand_destination_for_client, client_id
            )
        list_id = destination.get("clickup_list_id") if destination else None
        space_id = destination.get("clickup_space_id") if destination else None

        if not destination or (not space_id and not list_id):
            await slack.post_message(
                channel=channel,
                text=(
                    f"No brand with ClickUp mapping found for *{client_name}*. "
                    "Ask an admin to configure a ClickUp destination in Command Center."
                ),
            )
            return

        brand_id = brand_id or str(destination.get("id") or "")
        brand_name_display = brand_name or destination.get("name") or ""

        # --- C4A: Idempotency + duplicate suppression ---
        idempotency_key = build_idempotency_key(brand_id, task_title)

        # --- C4C: Concurrency guard ---
        async with _task_create_inflight_lock:
            if idempotency_key in _task_create_inflight:
                await slack.post_message(
                    channel=channel,
                    text="Another operation for this target is in progress. Please wait and try again.",
                )
                return
            _task_create_inflight.add(idempotency_key)
            acquired_inflight = True

        try:
            db = get_supabase_admin_client()
            duplicate = await asyncio.to_thread(check_duplicate, db, idempotency_key)
        except Exception as dedupe_exc:  # noqa: BLE001
            _logger.warning("Dedupe check failed (fail-closed): %s", dedupe_exc)
            await slack.post_message(
                channel=channel,
                text="I couldn't safely validate duplicate protection right now. Please try again in a minute.",
            )
            return

        if duplicate:
            cu_id = duplicate.get("clickup_task_id") or ""
            if cu_id:
                await slack.post_message(
                    channel=channel,
                    text=f"A task with that title was already created today (ClickUp `{cu_id}`). Skipping duplicate.",
                )
            else:
                await slack.post_message(
                    channel=channel,
                    text="A task with that title was already created today. Skipping duplicate.",
                )
            return

        clickup_user_id = await asyncio.to_thread(
            session_service.get_profile_clickup_user_id, session.profile_id
        )

        clickup = get_clickup_service()

        # C11D: Prepend brand metadata to task description
        full_description = task_description or ""
        if brand_name_display:
            full_description = f"**Brand:** {brand_name_display}\n\n{full_description}".rstrip()

        # --- C4A: Retry/backoff wrapper ---
        if list_id:
            async def _create_fn():  # type: ignore[return]
                return await clickup.create_task_in_list(
                    list_id=str(list_id),
                    name=task_title,
                    description_md=full_description,
                    assignee_ids=[clickup_user_id] if clickup_user_id else None,
                )
        else:
            async def _create_fn():  # type: ignore[return]
                return await clickup.create_task_in_space(
                    space_id=str(space_id),
                    name=task_title,
                    description_md=full_description,
                    assignee_ids=[clickup_user_id] if clickup_user_id else None,
                )

        try:
            task = await retry_with_backoff(_create_fn)
        except RetryExhaustedError as exc:
            await slack.post_message(
                channel=channel,
                text=f"Failed to create ClickUp task: {exc.last_error}",
            )
            return

        # --- C4A: Persist to agent_tasks + orphan detection ---
        try:
            await asyncio.to_thread(
                lambda: db.table("agent_tasks").insert({
                    "clickup_task_id": task.id,
                    "client_id": client_id,
                    "assignee_id": session.profile_id,
                    "source": "slack_dm",
                    "source_reference": idempotency_key,
                    "skill_invoked": "clickup_task_create",
                    "status": "pending",
                }).execute()
            )
        except Exception as persist_exc:  # noqa: BLE001
            _logger.warning("agent_tasks insert failed (orphan): %s", persist_exc)
            try:
                await asyncio.to_thread(
                    emit_orphan_event,
                    db,
                    clickup_task=task,
                    idempotency_key=idempotency_key,
                    client_id=client_id,
                    employee_id=session.profile_id,
                    error=str(persist_exc),
                )
            except Exception:  # noqa: BLE001
                pass  # Never break user response path

        url = task.url or ""
        link = f"<{url}|{task_title}>" if url else task_title
        brand_note = f" (brand: {brand_name_display})" if brand_name_display else ""
        draft_note = ""
        if not task_description:
            draft_note = "\n_Created as draft — add details directly in ClickUp._"
        await slack.post_message(
            channel=channel,
            text=f"Task created: {link}{brand_note}{draft_note}",
        )
    except (ClickUpConfigurationError, ClickUpError) as exc:
        await slack.post_message(channel=channel, text=f"Failed to create ClickUp task: {exc}")
    finally:
        if acquired_inflight:
            async with _task_create_inflight_lock:
                _task_create_inflight.discard(idempotency_key)
        # Clear pending state regardless of outcome — prevents stuck loops.
        await asyncio.to_thread(
            session_service.update_context, session.id, {"pending_task_create": None}
        )
        if clickup:
            await clickup.aclose()


async def _handle_create_task(
    *,
    slack_user_id: str,
    channel: str,
    client_name_hint: str,
    task_title: str,
    session_service: Any,
    slack: Any,
    pref_service: Any | None = None,
) -> None:
    """Handle 'create task for <client>: <title>' intent."""
    session = await asyncio.to_thread(session_service.get_or_create_session, slack_user_id)

    # --- Resolve client ---
    client_id, client_name = await _resolve_client_for_task(
        client_name_hint=client_name_hint,
        session=session,
        session_service=session_service,
        channel=channel,
        slack=slack,
        pref_service=pref_service,
    )
    if not client_id:
        return

    # --- C11D: Resolve brand context ---
    resolution = await _resolve_brand_for_task(
        client_id=client_id,
        client_name=client_name,
        task_text=task_title,
        brand_hint="",
        session=session,
        session_service=session_service,
        channel=channel,
        slack=slack,
    )

    if resolution["mode"] == "no_destination":
        await slack.post_message(
            channel=channel,
            text=(
                f"No brand with ClickUp mapping found for *{client_name}*. "
                "Ask an admin to configure a ClickUp destination in Command Center."
            ),
        )
        return

    if resolution["mode"] in ("ambiguous_brand", "ambiguous_destination"):
        # Picker already posted by _resolve_brand_for_task
        pending = {
            "awaiting": "brand",
            "client_id": client_id,
            "client_name": client_name,
            "task_title": task_title,
            "brand_candidates": [
                {"id": str(b.get("id") or ""), "name": str(b.get("name") or "")}
                for b in resolution["candidates"]
            ],
        }
        await asyncio.to_thread(
            session_service.update_context, session.id, {"pending_task_create": pending}
        )
        return

    # Brand resolved
    brand_ctx = resolution["brand_context"]
    brand_id = str(brand_ctx["id"]) if brand_ctx else None
    brand_name = str(brand_ctx["name"]) if brand_ctx else None
    brand_note = f" (brand: {brand_name})" if brand_name else ""

    # --- Missing title: ask for it ---
    if not task_title:
        pending = {
            "awaiting": "title",
            "client_id": client_id,
            "client_name": client_name,
            "brand_id": brand_id,
            "brand_name": brand_name,
            "brand_resolution_mode": resolution["mode"],
        }
        await asyncio.to_thread(
            session_service.update_context, session.id, {"pending_task_create": pending}
        )
        await slack.post_message(
            channel=channel,
            text=f"What should the task be called for *{client_name}*{brand_note}? Send the title.",
        )
        return

    # --- Have title, no description: offer draft or details ---
    pending = {
        "awaiting": "confirm_or_details",
        "client_id": client_id,
        "client_name": client_name,
        "brand_id": brand_id,
        "brand_name": brand_name,
        "brand_resolution_mode": resolution["mode"],
        "task_title": task_title,
        "timestamp": datetime.now(timezone.utc).isoformat(), # C3: Add timestamp for expiry
    }
    await asyncio.to_thread(
        session_service.update_context, session.id, {"pending_task_create": pending}
    )

    # C3: Confirmation Block Protocol
    # Send interactive buttons for explicit confirmation
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"Ready to create task *{task_title}* for *{client_name}*{brand_note}.\n\n"
                    "Send a description to include, or click Create to proceed as draft."
                )
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Create Task (Draft)"},
                    "style": "primary",
                    "action_id": "confirm_create_task_draft",
                    "value": "confirmed"
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Cancel"},
                    "style": "danger",
                    "action_id": "cancel_create_task",
                    "value": "cancelled"
                }
            ]
        }
    ]

    await slack.post_message(
        channel=channel,
        text=f"Ready to create task '{task_title}'. Confirm?",
        blocks=blocks,
    )


async def _handle_ngram_research(
    *,
    slack_user_id: str,
    channel: str,
    client_name_hint: str,
    session_service: Any,
    slack: Any,
    pref_service: Any | None = None,
) -> None:
    """C10D: Handle ngram_research skill via SOP-grounded task creation.

    Fetches the N-gram SOP and routes through the standard create-task flow,
    gaining C4A reliability and C10C KB enrichment.
    """
    session = await asyncio.to_thread(session_service.get_or_create_session, slack_user_id)

    # Resolve client (reuse existing helper)
    client_id, client_name = await _resolve_client_for_task(
        client_name_hint=client_name_hint,
        session=session,
        session_service=session_service,
        channel=channel,
        slack=slack,
        pref_service=pref_service,
    )
    if not client_id:
        return

    # Verify SOP exists
    sop_service = SOPSyncService(clickup_token="", supabase_client=session_service.db)
    sop = await sop_service.get_sop_by_category("ngram")
    sop_md = str((sop or {}).get("content_md") or "")
    if not sop_md.strip():
        await slack.post_message(
            channel=channel,
            text="N-gram SOP not found (category='ngram'). Ask an admin to run the SOP sync.",
        )
        return

    # Route through standard create-task flow with pre-filled title
    task_title = f"N-gram Research: {client_name}"
    await _handle_create_task(
        slack_user_id=slack_user_id,
        channel=channel,
        client_name_hint=client_name,
        task_title=task_title,
        session_service=session_service,
        slack=slack,
    )


async def _try_planner(
    *,
    text: str,
    slack_user_id: str,
    channel: str,
    session: Any,
    session_service: Any,
    slack: Any,
) -> bool:
    """C10D: Attempt planner-driven execution.  Returns True if handled."""
    if not _is_planner_enabled():
        return False

    try:
        # Build context
        client_context_pack = ""
        if session.active_client_id:
            client_name = await asyncio.to_thread(
                session_service.get_client_name, session.active_client_id
            )
            client_context_pack = f"Active client: {client_name or 'Unknown'} (id={session.active_client_id})"

        # KB retrieval for planner context (non-fatal)
        kb_summary = ""
        try:
            db = get_supabase_admin_client()
            retrieval = await retrieve_kb_context(
                query=text, client_id=str(session.active_client_id or ""), db=db,
            )
            if retrieval["sources"]:
                kb_summary = "\n".join(
                    f"- [{s['tier']}] {s['title']}: {s['content'][:200]}"
                    for s in retrieval["sources"][:3]
                )
        except Exception:
            pass

        # Generate plan
        plan = await generate_plan(
            text=text,
            session_context=session.context,
            client_context_pack=client_context_pack,
            kb_context_summary=kb_summary,
        )

        if not plan or not plan["steps"]:
            return False

        # Build handler dispatch map
        handler_map = {
            "clickup_task_create": _handle_create_task,
            "clickup_task_list_weekly": _handle_weekly_tasks,
            "ngram_research": _handle_ngram_research,
        }

        # Execute plan
        result = await execute_plan(
            plan=plan,
            slack_user_id=slack_user_id,
            channel=channel,
            session=session,
            session_service=session_service,
            slack=slack,
            check_policy=_check_tool_policy,
            handler_map=handler_map,
        )

        # Persist conversation history
        summary = f"[Planned: {plan['intent']} — {result['steps_succeeded']}/{result['steps_attempted']} steps]"
        recent = session.context.get("recent_exchanges") or []
        updated = append_exchange(recent, text, summary)
        await asyncio.to_thread(
            session_service.update_context, session.id,
            {"recent_exchanges": compact_exchanges(updated)},
        )

        return True
    except Exception:
        _logger.warning("C10D: Planner failed, falling through", exc_info=True)
        return False


async def _enrich_task_draft(
    *,
    task_title: str,
    client_id: str,
    client_name: str,
) -> dict[str, Any] | None:
    """C10C: Attempt KB retrieval + grounded draft.  Returns None on any failure."""
    try:
        db = get_supabase_admin_client()
        retrieval = await retrieve_kb_context(
            query=task_title,
            client_id=client_id,
            skill_id="clickup_task_create",
            db=db,
        )
        if not retrieval["sources"]:
            return None

        draft = build_grounded_task_draft(
            request_text=task_title,
            client_name=client_name,
            retrieved_context=retrieval,
            task_title=task_title,
        )
        return draft
    except Exception:
        _logger.warning("C10C: KB retrieval/draft failed, continuing without enrichment", exc_info=True)
        return None


def _compose_asin_pending_description(stashed_draft: dict[str, Any] | None) -> str:
    """Build unresolved-task description when user proceeds without identifiers."""
    from app.services.agencyclaw.grounded_task_draft import _ASIN_OPEN_QUESTION

    draft = stashed_draft or {}
    open_qs = list(draft.get("open_questions") or [])
    if not open_qs:
        open_qs = [_ASIN_OPEN_QUESTION]

    parts: list[str] = []
    if draft.get("description"):
        parts.append(str(draft["description"]))

    checklist = draft.get("checklist") or []
    if isinstance(checklist, list) and checklist:
        parts.append("## Checklist\n" + "\n".join(f"- [ ] {s}" for s in checklist))

    citations = draft.get("citations") or []
    if isinstance(citations, list) and citations:
        titles = [str(c.get("title")) for c in citations if isinstance(c, dict) and c.get("title")]
        if titles:
            parts.append("---\nSources: " + ", ".join(titles))

    parts.append("## Unresolved\n- " + "\n- ".join(open_qs))
    parts.append("**First step:** Resolve ASIN(s)/SKU(s) before executing this task.")
    return "\n\n".join(parts)


async def _handle_pending_task_continuation(
    *,
    channel: str,
    text: str,
    session: Any,
    session_service: Any,
    slack: Any,
    pending: dict[str, Any],
) -> bool:
    """Handle follow-up messages when a task create is pending.

    Returns True if the message was consumed, False if it should fall through.
    """
    awaiting = pending.get("awaiting")

    # --- C11D: Brand disambiguation ---
    if awaiting == "brand":
        brand_hint = text.strip()
        if not brand_hint:
            return False

        # Guard: if text matches a known intent, clear pending and fall through.
        probe_intent, _ = _classify_message(text)
        if probe_intent != "help":
            await asyncio.to_thread(
                session_service.update_context, session.id, {"pending_task_create": None}
            )
            return False

        client_id = pending.get("client_id", "")
        client_name = pending.get("client_name", "")
        task_title = pending.get("task_title", "")

        resolution = await _resolve_brand_for_task(
            client_id=client_id,
            client_name=client_name,
            task_text=task_title,
            brand_hint=brand_hint,
            session=session,
            session_service=session_service,
            channel=channel,
            slack=slack,
        )

        if resolution["mode"] in ("ambiguous_brand", "ambiguous_destination"):
            # Picker re-posted, keep awaiting brand
            return True

        if resolution["mode"] == "no_destination":
            await slack.post_message(channel=channel, text="No matching brand with ClickUp mapping found.")
            return True

        # Brand resolved — advance to title or confirm
        brand_ctx = resolution["brand_context"]
        brand_id = str(brand_ctx["id"]) if brand_ctx else None
        brand_name = str(brand_ctx["name"]) if brand_ctx else None
        brand_note = f" (brand: {brand_name})" if brand_name else ""

        if not task_title:
            new_pending = {
                "awaiting": "title",
                "client_id": client_id,
                "client_name": client_name,
                "brand_id": brand_id,
                "brand_name": brand_name,
                "brand_resolution_mode": resolution["mode"],
            }
            await asyncio.to_thread(
                session_service.update_context, session.id, {"pending_task_create": new_pending}
            )
            await slack.post_message(
                channel=channel,
                text=f"Got it, brand: *{brand_name or 'selected'}*. What should the task be called?",
            )
            return True

        # Has title — go to confirm
        new_pending = {
            "awaiting": "confirm_or_details",
            "client_id": client_id,
            "client_name": client_name,
            "brand_id": brand_id,
            "brand_name": brand_name,
            "brand_resolution_mode": resolution["mode"],
            "task_title": task_title,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await asyncio.to_thread(
            session_service.update_context, session.id, {"pending_task_create": new_pending}
        )
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"Ready to create task *{task_title}* for *{client_name}*{brand_note}.\n\n"
                        "Send a description to include, or click Create to proceed as draft."
                    )
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Create Task (Draft)"},
                        "style": "primary",
                        "action_id": "confirm_create_task_draft",
                        "value": "confirmed"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Cancel"},
                        "style": "danger",
                        "action_id": "cancel_create_task",
                        "value": "cancelled"
                    }
                ]
            }
        ]
        await slack.post_message(
            channel=channel,
            text=f"Ready to create task '{task_title}'. Confirm?",
            blocks=blocks,
        )
        return True

    if awaiting == "title":
        title = text.strip()
        if not title:
            return False  # empty — fall through to normal routing

        # Guard: if the text matches a known intent, don't consume it as title.
        probe_intent, _ = _classify_message(text)
        if probe_intent != "help":
            await asyncio.to_thread(
                session_service.update_context, session.id, {"pending_task_create": None}
            )
            return False

        client_id = pending.get("client_id", "")
        client_name = pending.get("client_name", "")
        brand_id = pending.get("brand_id")
        brand_name = pending.get("brand_name")
        brand_resolution_mode = pending.get("brand_resolution_mode")

        # C11D: Re-resolve brand context now that we have title text.
        # This closes the gap where an initially generic request becomes
        # product-scoped only after the user provides the title.
        if not brand_id:
            resolution = await _resolve_brand_for_task(
                client_id=client_id,
                client_name=client_name,
                task_text=title,
                brand_hint="",
                session=session,
                session_service=session_service,
                channel=channel,
                slack=slack,
            )

            if resolution["mode"] == "no_destination":
                await asyncio.to_thread(
                    session_service.update_context, session.id, {"pending_task_create": None}
                )
                await slack.post_message(
                    channel=channel,
                    text=(
                        f"No brand with ClickUp mapping found for *{client_name}*. "
                        "Ask an admin to configure a ClickUp destination in Command Center."
                    ),
                )
                return True

            if resolution["mode"] in ("ambiguous_brand", "ambiguous_destination"):
                new_pending = {
                    "awaiting": "brand",
                    "client_id": client_id,
                    "client_name": client_name,
                    "task_title": title,
                    "brand_candidates": [
                        {"id": str(b.get("id") or ""), "name": str(b.get("name") or "")}
                        for b in resolution["candidates"]
                    ],
                }
                await asyncio.to_thread(
                    session_service.update_context, session.id, {"pending_task_create": new_pending}
                )
                return True

            brand_ctx = resolution["brand_context"]
            brand_id = str(brand_ctx["id"]) if brand_ctx else None
            brand_name = str(brand_ctx["name"]) if brand_ctx else None
            brand_resolution_mode = resolution["mode"]

        # Got title — now offer confirm-or-details
        new_pending = {
            "awaiting": "confirm_or_details",
            "client_id": client_id,
            "client_name": client_name,
            "brand_id": brand_id,
            "brand_name": brand_name,
            "brand_resolution_mode": brand_resolution_mode,
            "task_title": title,
            "timestamp": datetime.now(timezone.utc).isoformat(), # C3: Add timestamp for expiry
        }
        await asyncio.to_thread(
            session_service.update_context, session.id, {"pending_task_create": new_pending}
        )
        
        # C3: Confirmation Block Protocol
        _brand_name = brand_name
        _brand_note = f" (brand: {_brand_name})" if _brand_name else ""
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"Ready to create task *{title}* for *{client_name}*{_brand_note}.\n\n"
                        "Send a description to include, or click Create to proceed as draft."
                    )
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Create Task (Draft)"},
                        "style": "primary",
                        "action_id": "confirm_create_task_draft",
                        "value": "confirmed"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Cancel"},
                        "style": "danger",
                        "action_id": "cancel_create_task",
                        "value": "cancelled"
                    }
                ]
            }
        ]
        
        await slack.post_message(
            channel=channel,
            text=f"Ready to create task '{title}'. Confirm?",
            blocks=blocks,
        )
        return True

    if awaiting == "confirm_or_details":
        from app.services.agencyclaw.grounded_task_draft import (
            _ASIN_CLARIFICATION,
            _ASIN_OPEN_QUESTION,
            _has_product_identifier,
            _is_product_scoped,
        )
        probe_intent, _ = _classify_message(text)
        pending_action = resolve_pending_action(
            awaiting="confirm_or_details",
            text=text,
            known_intent=probe_intent,
            has_identifier=_has_product_identifier(text),
        )

        client_id = pending.get("client_id", "")
        client_name = pending.get("client_name", "")
        task_title = pending.get("task_title", "")
        stashed_draft = pending.get("draft") if isinstance(pending.get("draft"), dict) else None

        if pending_action["action"] == "interrupt":
            await asyncio.to_thread(
                session_service.update_context, session.id, {"pending_task_create": None}
            )
            return False

        if pending_action["action"] == "cancel":
            await asyncio.to_thread(
                session_service.update_context, session.id, {"pending_task_create": None}
            )
            await slack.post_message(channel=channel, text="Okay, canceled task creation.")
            return True

        if pending_action["action"] == "off_topic":
            return False

        if pending_action["action"] == "proceed_with_asin_pending":
            if not stashed_draft:
                draft = await _enrich_task_draft(
                    task_title=task_title,
                    client_id=client_id,
                    client_name=client_name,
                )
                stashed_draft = dict(draft) if draft else {}
            description = _compose_asin_pending_description(stashed_draft)
            await _execute_task_create(
                channel=channel,
                session=session,
                session_service=session_service,
                slack=slack,
                client_id=client_id,
                client_name=client_name,
                task_title=task_title,
                task_description=description,
                brand_id=pending.get("brand_id"),
                brand_name=pending.get("brand_name"),
            )
            return True

        if pending_action["action"] == "proceed_draft":
            # C10C: Enrich with KB context if available
            enriched_description = ""
            draft = await _enrich_task_draft(
                task_title=task_title,
                client_id=client_id,
                client_name=client_name,
            )

            # C10C.1: If draft has open_questions (e.g. missing ASIN), ask before creating
            if draft and draft.get("open_questions"):
                question = draft.get("clarification_question") or "Could you provide more details?"
                pending["awaiting"] = "asin_or_pending"
                pending["draft"] = dict(draft)  # stash for reuse
                await asyncio.to_thread(
                    session_service.update_context, session.id, {"pending_task_create": pending}
                )
                await slack.post_message(channel=channel, text=question)
                return True

            if draft and not draft["needs_clarification"]:
                parts: list[str] = []
                if draft["description"]:
                    parts.append(draft["description"])
                if draft["checklist"]:
                    parts.append("## Checklist\n" + "\n".join(f"- [ ] {s}" for s in draft["checklist"]))
                if draft["citations"]:
                    parts.append("---\nSources: " + ", ".join(c["title"] for c in draft["citations"]))
                if parts:
                    enriched_description = "\n\n".join(parts)

            await _execute_task_create(
                channel=channel,
                session=session,
                session_service=session_service,
                slack=slack,
                client_id=client_id,
                client_name=client_name,
                task_title=task_title,
                task_description=enriched_description,
                brand_id=pending.get("brand_id"),
                brand_name=pending.get("brand_name"),
            )
            return True

        # User sent descriptive details
        description = text.strip()

        combined_text = f"{task_title} {description}"
        if _is_product_scoped(combined_text) and not _has_product_identifier(combined_text):
            pending["awaiting"] = "asin_or_pending"
            pending["draft"] = {"description": description, "open_questions": [_ASIN_OPEN_QUESTION]}
            await asyncio.to_thread(
                session_service.update_context, session.id, {"pending_task_create": pending}
            )
            await slack.post_message(channel=channel, text=_ASIN_CLARIFICATION)
            return True

        await _execute_task_create(
            channel=channel,
            session=session,
            session_service=session_service,
            slack=slack,
            client_id=client_id,
            client_name=client_name,
            task_title=task_title,
            task_description=description,
            brand_id=pending.get("brand_id"),
            brand_name=pending.get("brand_name"),
        )
        return True

    if awaiting == "asin_or_pending":
        from app.services.agencyclaw.grounded_task_draft import _has_product_identifier

        probe_intent, _ = _classify_message(text)
        pending_action = resolve_pending_action(
            awaiting="asin_or_pending",
            text=text,
            known_intent=probe_intent,
            has_identifier=_has_product_identifier(text),
        )

        client_id = pending.get("client_id", "")
        client_name = pending.get("client_name", "")
        task_title = pending.get("task_title", "")
        stashed_draft = pending.get("draft") or {}

        if pending_action["action"] == "interrupt":
            await asyncio.to_thread(
                session_service.update_context, session.id, {"pending_task_create": None}
            )
            return False

        if pending_action["action"] == "cancel":
            await asyncio.to_thread(
                session_service.update_context, session.id, {"pending_task_create": None}
            )
            await slack.post_message(channel=channel, text="Okay, canceled task creation.")
            return True

        if pending_action["action"] == "proceed_with_asin_pending":
            description = _compose_asin_pending_description(stashed_draft)
            await _execute_task_create(
                channel=channel,
                session=session,
                session_service=session_service,
                slack=slack,
                client_id=client_id,
                client_name=client_name,
                task_title=task_title,
                task_description=description,
                brand_id=pending.get("brand_id"),
                brand_name=pending.get("brand_name"),
            )
            return True

        if pending_action["action"] == "provide_identifier":
            parts = []
            if stashed_draft.get("description"):
                parts.append(stashed_draft["description"])
            parts.append(f"Product identifiers: {text.strip()}")
            description = "\n\n".join(parts)

            await _execute_task_create(
                channel=channel,
                session=session,
                session_service=session_service,
                slack=slack,
                client_id=client_id,
                client_name=client_name,
                task_title=task_title,
                task_description=description,
                brand_id=pending.get("brand_id"),
                brand_name=pending.get("brand_name"),
            )
            return True

        if pending_action["action"] == "off_topic":
            return False

        # Unclear ASIN-related follow-up: re-ask without creating.
        from app.services.agencyclaw.grounded_task_draft import _ASIN_CLARIFICATION

        await slack.post_message(
            channel=channel,
            text=_ASIN_CLARIFICATION,
        )
        return True

    # Unknown awaiting state — clear it
    await asyncio.to_thread(
        session_service.update_context, session.id, {"pending_task_create": None}
    )
    return False


async def _try_llm_orchestrator(
    *,
    text: str,
    slack_user_id: str,
    channel: str,
    session: Any,
    session_service: Any,
    slack: Any,
) -> bool:
    """Attempt LLM-first orchestration.  Returns True if fully handled, False to fall back."""
    try:
        # Build lightweight client context pack for the orchestrator
        client_context_pack = ""
        if session.active_client_id:
            client_name = await asyncio.to_thread(
                session_service.get_client_name, session.active_client_id
            )
            client_context_pack = f"Active client: {client_name or 'Unknown'} (id={session.active_client_id})"

        # C10B.5: Read bounded conversation history from session context
        raw_exchanges = session.context.get("recent_exchanges") or []
        recent_exchanges = compact_exchanges(raw_exchanges)

        result = await orchestrate_dm_message(
            text=text,
            profile_id=session.profile_id,
            slack_user_id=slack_user_id,
            session_context=session.context,
            client_context_pack=client_context_pack,
            recent_exchanges=recent_exchanges,
        )

        mode = result["mode"]

        # --- Token telemetry (best-effort, fire-and-forget) ---
        if result.get("tokens_in") is not None:
            try:
                await log_ai_token_usage(
                    tool="agencyclaw",
                    stage="intent_parse",
                    user_id=session.profile_id,
                    model=result.get("model_used"),
                    prompt_tokens=result.get("tokens_in"),
                    completion_tokens=result.get("tokens_out"),
                    total_tokens=result.get("tokens_total"),
                    meta={
                        "run_type": "dm_orchestrate",
                        "skill_id": result.get("skill_id"),
                        "client_id": session.active_client_id,
                        "channel_id": channel,
                        "mode": mode,
                    },
                )
            except Exception:  # noqa: BLE001
                pass  # Never block response path

        if mode == "fallback":
            _logger.info("LLM orchestrator fallback: %s", result.get("reason", ""))
            return False  # fall through to deterministic classifier

        if mode == "reply":
            reply_text = result.get("text") or "I'm not sure how to help with that."
            await slack.post_message(channel=channel, text=reply_text)
            # C10B.5: Append exchange and persist
            updated = append_exchange(recent_exchanges, text, reply_text)
            await asyncio.to_thread(
                session_service.update_context, session.id,
                {"recent_exchanges": compact_exchanges(updated)},
            )
            return True

        if mode == "clarify":
            question = result.get("question") or "Could you provide more details?"
            clarify_skill_id = result.get("skill_id") or ""
            clarify_args = result.get("args") or {}

            # C10B: For mutation skills, persist pending state so the next
            # message routes through _handle_pending_task_continuation instead
            # of re-entering the LLM with no context.
            if clarify_skill_id == "clickup_task_create":
                client_name_hint = str(clarify_args.get("client_name") or "")
                task_title = str(clarify_args.get("task_title") or "")

                # Always resolve client (uses active-client fallback / picker
                # when hint is empty) — never write pending with empty client_id.
                pref_service = PreferenceMemoryService(session_service.db)
                client_id, client_name = await _resolve_client_for_task(
                    client_name_hint=client_name_hint,
                    session=session,
                    session_service=session_service,
                    channel=channel,
                    slack=slack,
                    pref_service=pref_service,
                )
                if not client_id:
                    return True  # picker/error already posted

                # C11D: Resolve brand context
                resolution = await _resolve_brand_for_task(
                    client_id=client_id,
                    client_name=client_name,
                    task_text=task_title,
                    brand_hint="",
                    session=session,
                    session_service=session_service,
                    channel=channel,
                    slack=slack,
                )

                if resolution["mode"] == "no_destination":
                    await slack.post_message(
                        channel=channel,
                        text=f"No ClickUp destination configured for *{client_name}*.",
                    )
                    return True

                if resolution["mode"] in ("ambiguous_brand", "ambiguous_destination"):
                    pending = {
                        "awaiting": "brand",
                        "client_id": client_id,
                        "client_name": client_name,
                        "task_title": task_title,
                        "brand_candidates": [
                            {"id": str(b.get("id") or ""), "name": str(b.get("name") or "")}
                            for b in resolution["candidates"]
                        ],
                    }
                    await asyncio.to_thread(
                        session_service.update_context, session.id,
                        {"pending_task_create": pending},
                    )
                    return True  # picker already posted

                brand_ctx = resolution["brand_context"]
                brand_id = str(brand_ctx["id"]) if brand_ctx else None
                brand_name = str(brand_ctx["name"]) if brand_ctx else None

                if not task_title:
                    pending = {
                        "awaiting": "title",
                        "client_id": client_id,
                        "client_name": client_name,
                        "brand_id": brand_id,
                        "brand_name": brand_name,
                        "brand_resolution_mode": resolution["mode"],
                    }
                else:
                    pending = {
                        "awaiting": "confirm_or_details",
                        "client_id": client_id,
                        "client_name": client_name,
                        "brand_id": brand_id,
                        "brand_name": brand_name,
                        "brand_resolution_mode": resolution["mode"],
                        "task_title": task_title,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }

                await asyncio.to_thread(
                    session_service.update_context, session.id,
                    {"pending_task_create": pending},
                )

            await slack.post_message(channel=channel, text=question)
            # C10B.5: Append exchange and persist
            updated = append_exchange(recent_exchanges, text, question)
            await asyncio.to_thread(
                session_service.update_context, session.id,
                {"recent_exchanges": compact_exchanges(updated)},
            )
            return True

        if mode == "tool_call":
            skill_id = result.get("skill_id") or ""
            args = result.get("args") or {}

            # C10A: Policy gate before execution
            policy = await _check_tool_policy(
                slack_user_id=slack_user_id,
                session=session,
                channel=channel,
                skill_id=skill_id,
                args=args,
            )
            if not policy["allowed"]:
                _logger.info(
                    "C10A policy denied: reason=%s skill=%s",
                    policy["reason_code"], skill_id,
                )
                await slack.post_message(channel=channel, text=policy["user_message"])
                return True

            tool_summary = ""

            if skill_id == "clickup_task_list_weekly":
                await _handle_weekly_tasks(
                    slack_user_id=slack_user_id,
                    channel=channel,
                    client_name_hint=str(args.get("client_name") or ""),
                    session_service=session_service,
                    slack=slack,
                )
                tool_summary = f"[Ran weekly task list for {args.get('client_name', 'client')}]"

            elif skill_id == "clickup_task_create":
                await _handle_create_task(
                    slack_user_id=slack_user_id,
                    channel=channel,
                    client_name_hint=str(args.get("client_name") or ""),
                    task_title=str(args.get("task_title") or ""),
                    session_service=session_service,
                    slack=slack,
                )
                tool_summary = f"[Started task creation for {args.get('client_name', 'client')}]"

            elif skill_id == "ngram_research":
                await _handle_ngram_research(
                    slack_user_id=slack_user_id,
                    channel=channel,
                    client_name_hint=str(args.get("client_name") or ""),
                    session_service=session_service,
                    slack=slack,
                )
                tool_summary = f"[Started n-gram research for {args.get('client_name', 'client')}]"

            elif skill_id in ("cc_client_lookup", "cc_brand_list_all", "cc_brand_clickup_mapping_audit", "cc_brand_mapping_remediation_preview", "cc_brand_mapping_remediation_apply"):
                tool_summary = await _handle_cc_skill(
                    skill_id=skill_id,
                    args=args,
                    session=session,
                    session_service=session_service,
                    channel=channel,
                    slack=slack,
                )

            else:
                # Unknown skill — fall through
                _logger.warning("LLM orchestrator returned unknown skill: %s", skill_id)
                return False

            # C10B.5: Persist conversation history after tool execution
            if tool_summary:
                updated = append_exchange(recent_exchanges, text, tool_summary)
                await asyncio.to_thread(
                    session_service.update_context, session.id,
                    {"recent_exchanges": compact_exchanges(updated)},
                )
            return True

        return False  # unknown mode — fall through

    except Exception as exc:  # noqa: BLE001
        _logger.warning("LLM orchestrator error: %s", exc)
        return False  # fall through to deterministic classifier


async def _check_tool_policy(
    *,
    slack_user_id: str,
    session: Any,
    channel: str,
    skill_id: str,
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """C10A: Resolve actor/surface and evaluate tool policy.

    Returns the PolicyDecision dict.  Caller should check ``allowed`` and
    post ``user_message`` on deny.
    """
    actor = await asyncio.to_thread(
        resolve_actor_context,
        get_supabase_admin_client(),
        slack_user_id,
        session.profile_id,
    )
    surface = resolve_surface_context(channel)
    return evaluate_tool_policy(actor, surface, skill_id, args, session.context)


async def _handle_dm_event(*, slack_user_id: str, channel: str, text: str) -> None:
    session_service = get_playbook_session_service()
    pref_service = PreferenceMemoryService(session_service.db)
    slack = get_slack_service()

    try:
        session = await asyncio.to_thread(session_service.get_or_create_session, slack_user_id)
        await asyncio.to_thread(session_service.touch_session, session.id)

        # --- Multi-turn continuation for pending task create ---
        pending = session.context.get("pending_task_create")
        if isinstance(pending, dict) and pending.get("awaiting"):
            consumed = await _handle_pending_task_continuation(
                channel=channel,
                text=text,
                session=session,
                session_service=session_service,
                slack=slack,
                pending=pending,
            )
            if consumed:
                return

        # --- C10D: Planner (feature-flagged) ---
        if await _try_planner(
            text=text,
            slack_user_id=slack_user_id,
            channel=channel,
            session=session,
            session_service=session_service,
            slack=slack,
        ):
            return

        # --- LLM orchestrator (feature-flagged) ---
        if _is_llm_orchestrator_enabled():
            handled = await _try_llm_orchestrator(
                text=text,
                slack_user_id=slack_user_id,
                channel=channel,
                session=session,
                session_service=session_service,
                slack=slack,
            )
            if handled:
                return
            # fallback mode → continue to deterministic classifier below

        intent, params = _classify_message(text)

        if intent == "create_task":
            # C10A: Policy gate for deterministic path
            policy = await _check_tool_policy(
                slack_user_id=slack_user_id,
                session=session,
                channel=channel,
                skill_id="clickup_task_create",
            )
            if not policy["allowed"]:
                await slack.post_message(channel=channel, text=policy["user_message"])
                return

            await _handle_create_task(
                slack_user_id=slack_user_id,
                channel=channel,
                client_name_hint=str(params.get("client_name") or ""),
                task_title=str(params.get("task_title") or ""),
                session_service=session_service,
                slack=slack,
                pref_service=pref_service,
            )
            return

        if intent == "confirm_draft_task":
            # No pending state (already checked above) — nothing to confirm.
            await slack.post_message(
                channel=channel,
                text="Nothing to confirm right now. Tell me what task you'd like to create.",
            )
            return

        if intent == "weekly_tasks":
            # C10A: Policy gate for deterministic path
            policy = await _check_tool_policy(
                slack_user_id=slack_user_id,
                session=session,
                channel=channel,
                skill_id="clickup_task_list_weekly",
            )
            if not policy["allowed"]:
                await slack.post_message(channel=channel, text=policy["user_message"])
                return

            await _handle_weekly_tasks(
                slack_user_id=slack_user_id,
                channel=channel,
                client_name_hint=str(params.get("client_name") or ""),
                session_service=session_service,
                slack=slack,
            )
            return

        if intent == "switch_client":
            client_name = str(params.get("client_name") or "").strip()
            if not client_name:
                await slack.post_message(channel=channel, text=_help_text())
                return

            matches = await asyncio.to_thread(
                session_service.find_client_matches, session.profile_id, client_name
            )

            if not matches:
                clients = await asyncio.to_thread(session_service.list_clients_for_picker, session.profile_id)
                blocks = _build_client_picker_blocks(clients) if clients else None
                await slack.post_message(
                    channel=channel,
                    text=f"I couldn't find a client matching: {client_name!r}",
                    blocks=blocks,
                )
                return

            if len(matches) > 1:
                blocks = _build_client_picker_blocks(matches)
                await slack.post_message(
                    channel=channel,
                    text=f"Multiple clients match {client_name!r}. Pick one:",
                    blocks=blocks,
                )
                return

            client_id = str(matches[0].get("id") or "")
            client_display = str(matches[0].get("name") or "that client")
            await asyncio.to_thread(session_service.set_active_client, session.id, client_id)
            await asyncio.to_thread(session_service.update_context, session.id, {"pending_task": None})
            await slack.post_message(
                channel=channel,
                text=f"Now working on *{client_display}*. What would you like to do for this client?",
            )
            return

        # C10E: Set default client preference
        if intent == "set_default_client":
            client_name = str(params.get("client_name") or "").strip()
            if not client_name:
                await slack.post_message(
                    channel=channel,
                    text="Usage: `set my default client to <client name>`",
                )
                return

            if not session.profile_id:
                await slack.post_message(
                    channel=channel,
                    text="I can't save preferences — your Slack account isn't linked to a profile yet.",
                )
                return

            matches = await asyncio.to_thread(
                session_service.find_client_matches, session.profile_id, client_name
            )
            if not matches:
                await slack.post_message(
                    channel=channel,
                    text=f"I couldn't find a client matching *{client_name}*.",
                )
                return
            if len(matches) > 1:
                blocks = _build_client_picker_blocks(matches)
                await slack.post_message(
                    channel=channel,
                    text=f"Multiple clients match *{client_name}*. Be more specific:",
                    blocks=blocks,
                )
                return

            client_id = str(matches[0].get("id") or "")
            client_display = str(matches[0].get("name") or client_name)
            await asyncio.to_thread(pref_service.set_default_client, session.profile_id, client_id)
            # Also set as active for this session
            await asyncio.to_thread(session_service.set_active_client, session.id, client_id)
            await slack.post_message(
                channel=channel,
                text=f"Default client set to *{client_display}*. This will persist across sessions.",
            )
            return

        # C10E: Clear default client preference
        if intent == "clear_defaults":
            if not session.profile_id:
                await slack.post_message(
                    channel=channel,
                    text="I can't manage preferences — your Slack account isn't linked to a profile yet.",
                )
                return

            await asyncio.to_thread(pref_service.clear_default_client, session.profile_id)
            await slack.post_message(
                channel=channel,
                text="Default client cleared. I'll ask you to pick a client each time.",
            )
            return

        # C11A: Command Center read-only skills
        if intent in ("cc_client_lookup", "cc_brand_list_all", "cc_brand_clickup_mapping_audit", "cc_brand_mapping_remediation_preview", "cc_brand_mapping_remediation_apply"):
            policy = await _check_tool_policy(
                slack_user_id=slack_user_id,
                session=session,
                channel=channel,
                skill_id=intent,
            )
            if not policy["allowed"]:
                await slack.post_message(channel=channel, text=policy["user_message"])
                return

            await _handle_cc_skill(
                skill_id=intent,
                args=params,
                session=session,
                session_service=session_service,
                channel=channel,
                slack=slack,
            )
            return

        # LLM-first mode: disable broad regex fallback after orchestrator attempt.
        # Keep only explicit control intents deterministic (switch/defaults).
        if _is_llm_orchestrator_enabled() and not _is_legacy_intent_fallback_enabled():
            # LLM already had a chance to reply conversationally. If it fell
            # back AND the classifier didn't match an actionable intent, send
            # a short natural nudge instead of a command-menu.
            await slack.post_message(
                channel=channel,
                text="I'm not sure what to do with that. "
                "Try asking about a client's tasks, or tell me what you need help with.",
            )
            return

        await slack.post_message(channel=channel, text=_help_text())
    except SlackAPIError:
        # Keep the endpoint non-fatal; Slack will retry delivery if needed.
        pass
    except Exception as exc:  # noqa: BLE001
        _logger.warning("Unhandled error in _handle_dm_event: %s", exc, exc_info=True)
        try:
            await slack.post_message(
                channel=channel,
                text="Something went wrong while processing that. Please try again.",
            )
        except Exception:  # noqa: BLE001
            pass  # Best-effort fallback — never re-raise
    finally:
        await slack.aclose()


def _parse_interaction_payload(raw_body: bytes) -> dict[str, Any]:
    try:
        form = parse_qs(raw_body.decode("utf-8"), keep_blank_values=True)
    except UnicodeDecodeError:
        return {}

    payload_str = (form.get("payload") or [""])[0]
    if not payload_str:
        return {}
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


async def _handle_interaction(payload: dict[str, Any]) -> None:
    if payload.get("type") != "block_actions":
        return

    actions = payload.get("actions")
    if not isinstance(actions, list) or not actions:
        return

    action = actions[0] if isinstance(actions[0], dict) else {}
    action_id = str(action.get("action_id") or "")
    
    user = payload.get("user") if isinstance(payload.get("user"), dict) else {}
    channel = payload.get("channel") if isinstance(payload.get("channel"), dict) else {}
    message = payload.get("message") if isinstance(payload.get("message"), dict) else {}

    slack_user_id = str(user.get("id") or "").strip()
    channel_id = str(channel.get("id") or "").strip()
    message_ts = str(message.get("ts") or "").strip()

    if not slack_user_id or not channel_id:
        return

    # C3: Interaction Dedupe
    receipt_service = _get_receipt_service()
    # Key: interaction:{user_id}:{action_id}:{message_ts}
    # This ensures a user clicking the same button on the same message is deduped.
    dedupe_key = f"interaction:{slack_user_id}:{action_id}:{message_ts}"[-255:] # Truncate if needed for DB key limit? Text column is usually fine.
    
    # Try atomic insert
    is_new = await asyncio.to_thread(
        receipt_service.attempt_insert_dedupe,
        event_key=dedupe_key,
        event_source="interactions",
        payload=payload
    )
    
    if not is_new:
        # Already processing/processed. Ignore.
        _logger.debug("Duplicate interaction ignored: %s", dedupe_key)
        return

    session_service = get_playbook_session_service()
    slack = get_slack_service()
    
    try:
        session = await asyncio.to_thread(session_service.get_or_create_session, slack_user_id)
        
        # --- Handle Client Selection ---
        if action_id.startswith("select_client_"):
            client_id = str(action.get("value") or "").strip()
            if not client_id:
                return

            await asyncio.to_thread(session_service.set_active_client, session.id, client_id)
            await asyncio.to_thread(session_service.update_context, session.id, {"pending_task": None})

            client_name = await asyncio.to_thread(session_service.get_client_name, client_id)
            client_name = client_name or "that client"

            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Now working on *{client_name}*. What would you like to do for this client?",
                    },
                }
            ]
            if message_ts:
                await slack.update_message(
                    channel=channel_id,
                    ts=message_ts,
                    text=f"Working on: {client_name}",
                    blocks=blocks,
                )
            else:
                await slack.post_message(channel=channel_id, text=f"Working on: {client_name}", blocks=blocks)
            
            receipt_service.update_status(dedupe_key, "processed")
            return

        # --- C11D: Handle Brand Selection ---
        if action_id.startswith("select_brand_"):
            brand_id = str(action.get("value") or "").strip()
            if not brand_id:
                return

            pending = session.context.get("pending_task_create")
            if not isinstance(pending, dict) or pending.get("awaiting") != "brand":
                await slack.post_message(channel=channel_id, text="No pending brand selection.")
                receipt_service.update_status(dedupe_key, "ignored")
                return

            # Look up brand name from stashed candidates
            candidates = pending.get("brand_candidates") or []
            valid_brand_ids = {
                str(c.get("id") or "")
                for c in candidates
                if isinstance(c, dict)
            }
            if brand_id not in valid_brand_ids:
                await slack.post_message(
                    channel=channel_id,
                    text="That brand option is no longer valid. Please choose from the current picker.",
                )
                receipt_service.update_status(dedupe_key, "ignored", {"reason": "invalid_brand_selection"})
                return

            brand_name = next(
                (str(c.get("name", "Brand")) for c in candidates if str(c.get("id")) == brand_id),
                "Brand",
            )

            client_id = pending.get("client_id", "")
            client_name = pending.get("client_name", "")
            task_title = pending.get("task_title", "")

            # Update picker message
            if message_ts:
                await slack.update_message(
                    channel=channel_id,
                    ts=message_ts,
                    text=f"Selected brand: {brand_name}",
                    blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": f"Selected: *{brand_name}*"}}],
                )

            brand_note = f" (brand: {brand_name})"

            if not task_title:
                new_pending = {
                    "awaiting": "title",
                    "client_id": client_id,
                    "client_name": client_name,
                    "brand_id": brand_id,
                    "brand_name": brand_name,
                    "brand_resolution_mode": "explicit_brand",
                }
                await asyncio.to_thread(
                    session_service.update_context, session.id, {"pending_task_create": new_pending}
                )
                await slack.post_message(
                    channel=channel_id,
                    text=f"Got it, brand: *{brand_name}*. What should the task be called for *{client_name}*?",
                )
            else:
                new_pending = {
                    "awaiting": "confirm_or_details",
                    "client_id": client_id,
                    "client_name": client_name,
                    "brand_id": brand_id,
                    "brand_name": brand_name,
                    "brand_resolution_mode": "explicit_brand",
                    "task_title": task_title,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                await asyncio.to_thread(
                    session_service.update_context, session.id, {"pending_task_create": new_pending}
                )
                blocks = [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"Ready to create task *{task_title}* for *{client_name}*{brand_note}.\n\n"
                                "Send a description to include, or click Create to proceed as draft."
                            )
                        }
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "Create Task (Draft)"},
                                "style": "primary",
                                "action_id": "confirm_create_task_draft",
                                "value": "confirmed"
                            },
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "Cancel"},
                                "style": "danger",
                                "action_id": "cancel_create_task",
                                "value": "cancelled"
                            }
                        ]
                    }
                ]
                await slack.post_message(
                    channel=channel_id,
                    text=f"Ready to create task '{task_title}'. Confirm?",
                    blocks=blocks,
                )

            receipt_service.update_status(dedupe_key, "processed")
            return

        # --- Handle Task Confirmation ---
        if action_id == "confirm_create_task_draft":
            pending = session.context.get("pending_task_create")
            
            # 1. Validate State
            if not isinstance(pending, dict) or pending.get("awaiting") != "confirm_or_details":
                await slack.post_message(channel=channel_id, text="No pending task to confirm.")
                receipt_service.update_status(dedupe_key, "ignored", {"reason": "no_state"})
                return

            # 2. Check Expiry (10 mins)
            ts_str = pending.get("timestamp")
            if ts_str:
                dt = datetime.fromisoformat(str(ts_str)).replace(tzinfo=timezone.utc) if "T" in str(ts_str) else None
                # Basic parsing safe guard
                try: 
                    dt = datetime.fromisoformat(str(ts_str)) 
                    # Ensure utc
                    if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
                    
                    if datetime.now(timezone.utc) - dt > timedelta(minutes=10):
                        # Expired
                        await asyncio.to_thread(session_service.update_context, session.id, {"pending_task_create": None})
                        await slack.update_message(
                            channel=channel_id,
                            ts=message_ts,
                            text="Task creation timed out.",
                            blocks=[]
                        )
                        receipt_service.update_status(dedupe_key, "ignored", {"reason": "expired"})
                        return
                except ValueError:
                    pass # Invalid timestamp, assume valid or ignore?

            # 3. Execute Mutation
            # Update UI first to prevent double-clicks conceptually (though dedupe handles it technically)
            await slack.update_message(
                channel=channel_id,
                ts=message_ts,
                text="Creating task...",
                blocks=[]
            )
            
            await _execute_task_create(
                channel=channel_id,
                session=session,
                session_service=session_service,
                slack=slack,
                client_id=pending.get("client_id", ""),
                client_name=pending.get("client_name", ""),
                task_title=pending.get("task_title", ""),
                task_description="", # Draft
                brand_id=pending.get("brand_id"),
                brand_name=pending.get("brand_name"),
            )
            receipt_service.update_status(dedupe_key, "processed")
            return

        # --- Handle Cancellation ---
        if action_id == "cancel_create_task":
            await asyncio.to_thread(session_service.update_context, session.id, {"pending_task_create": None})
            await slack.update_message(
                channel=channel_id,
                ts=message_ts,
                text="Task creation cancelled.",
                blocks=[]
            )
            receipt_service.update_status(dedupe_key, "processed")
            return

    except SlackAPIError:
        receipt_service.update_status(dedupe_key, "failed")
    except Exception as exc:  # noqa: BLE001
        _logger.warning("Error handling interaction: %s", exc)
        receipt_service.update_status(dedupe_key, "failed", {"error": str(exc)})
    finally:
        await slack.aclose()


@router.post("/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    signing_secret = get_slack_signing_secret().strip()
    if not signing_secret:
        raise HTTPException(status_code=500, detail="SLACK_SIGNING_SECRET not set")

    body = await request.body()
    _verify_request_or_401(signing_secret=signing_secret, request=request, body=body)

    # If Slack retries a delivery, avoid duplicating side effects.
    if request.headers.get("X-Slack-Retry-Num"):
        return JSONResponse({"ok": True})

    payload = _parse_json(body)

    if payload.get("type") == "url_verification":
        challenge = payload.get("challenge")
        if not isinstance(challenge, str) or not challenge:
            raise HTTPException(status_code=400, detail="Missing Slack challenge")
        return JSONResponse({"challenge": challenge})

    if payload.get("type") == "event_callback":
        event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
        if (
            event.get("type") == "message"
            and event.get("channel_type") == "im"
            and not event.get("bot_id")
            and not event.get("subtype")
        ):
            channel = str(event.get("channel") or "").strip()
            text = str(event.get("text") or "")
            slack_user_id = str(event.get("user") or "").strip()
            if channel and text and slack_user_id:
                background_tasks.add_task(
                    _handle_dm_event,
                    slack_user_id=slack_user_id,
                    channel=channel,
                    text=text,
                )

    return JSONResponse({"ok": True})


@router.post("/interactions")
async def slack_interactions(request: Request, background_tasks: BackgroundTasks):
    signing_secret = get_slack_signing_secret().strip()
    if not signing_secret:
        raise HTTPException(status_code=500, detail="SLACK_SIGNING_SECRET not set")

    body = await request.body()
    _verify_request_or_401(signing_secret=signing_secret, request=request, body=body)

    interaction = _parse_interaction_payload(body)
    if interaction:
        background_tasks.add_task(_handle_interaction, interaction)

    return JSONResponse({"ok": True})
