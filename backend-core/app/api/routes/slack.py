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
from ...services.agencyclaw.clickup_reliability import (
    RetryExhaustedError,
    build_idempotency_key,
    check_duplicate,
    emit_orphan_event,
    retry_with_backoff,
)
from ...services.ai_token_usage_logger import log_ai_token_usage
from ...services.clickup import ClickUpError, ClickUpConfigurationError, get_clickup_service
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
    if any(kw in t for kw in ("ngram", "n-gram", "keyword research")):
        return ("create_ngram_task", {})
    if t.startswith("switch to "):
        return ("switch_client", {"client_name": t.removeprefix("switch to ").strip()})
    if t.startswith("work on "):
        return ("switch_client", {"client_name": t.removeprefix("work on ").strip()})

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

    return ("help", {})


def _help_text() -> str:
    return (
        "I can help you with ClickUp tasks and SOPs.\n\n"
        "Try:\n"
        "- `create task for <client>: <title>`\n"
        "- `what's being worked on this week for <client>`\n"
        "- `show tasks for <client>`\n"
        "- `start ngram research`\n"
        "- `switch to <client name>`"
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
) -> tuple[str | None, str]:
    """Resolve client_id + client_name from hint or active session.

    Returns (client_id, client_name).  client_id is None on failure (message already sent).
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

        brand_id = str(destination.get("id") or "")

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

        # --- C4A: Retry/backoff wrapper ---
        if list_id:
            async def _create_fn():  # type: ignore[return]
                return await clickup.create_task_in_list(
                    list_id=str(list_id),
                    name=task_title,
                    description_md=task_description or "",
                    assignee_ids=[clickup_user_id] if clickup_user_id else None,
                )
        else:
            async def _create_fn():  # type: ignore[return]
                return await clickup.create_task_in_space(
                    space_id=str(space_id),
                    name=task_title,
                    description_md=task_description or "",
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
        brand_name = destination.get("name") or ""
        brand_note = f" (brand: {brand_name})" if brand_name else ""
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
    )
    if not client_id:
        return

    # --- Missing title: ask for it ---
    if not task_title:
        pending = {
            "awaiting": "title",
            "client_id": client_id,
            "client_name": client_name,
        }
        await asyncio.to_thread(
            session_service.update_context, session.id, {"pending_task_create": pending}
        )
        await slack.post_message(
            channel=channel,
            text=f"What should the task be called for *{client_name}*? Send the title.",
        )
        return

    # --- Have title, no description: offer draft or details ---
    pending = {
        "awaiting": "confirm_or_details",
        "client_id": client_id,
        "client_name": client_name,
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
                    f"Ready to create task *{task_title}* for *{client_name}*.\n\n"
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

        # Got title — now offer confirm-or-details
        new_pending = {
            "awaiting": "confirm_or_details",
            "client_id": client_id,
            "client_name": client_name,
            "task_title": title,
            "timestamp": datetime.now(timezone.utc).isoformat(), # C3: Add timestamp for expiry
        }
        await asyncio.to_thread(
            session_service.update_context, session.id, {"pending_task_create": new_pending}
        )
        
        # C3: Confirmation Block Protocol
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"Ready to create task *{title}* for *{client_name}*.\n\n"
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
        t_lower = " ".join(text.strip().lower().split())

        # Check if user wants to create as draft
        is_confirm = any(p.match(t_lower) for p in _CONFIRM_DRAFT_PATTERNS)

        client_id = pending.get("client_id", "")
        client_name = pending.get("client_name", "")
        task_title = pending.get("task_title", "")

        if is_confirm:
            # Create as draft (no description)
            await _execute_task_create(
                channel=channel,
                session=session,
                session_service=session_service,
                slack=slack,
                client_id=client_id,
                client_name=client_name,
                task_title=task_title,
                task_description="",
            )
            return True

        # Guard: if the text matches a known intent, don't consume it as description.
        # Clear pending state and fall through to normal routing.
        probe_intent, _ = _classify_message(text)
        if probe_intent != "help":
            await asyncio.to_thread(
                session_service.update_context, session.id, {"pending_task_create": None}
            )
            return False

        # User sent description text — create with it
        description = text.strip()
        await _execute_task_create(
            channel=channel,
            session=session,
            session_service=session_service,
            slack=slack,
            client_id=client_id,
            client_name=client_name,
            task_title=task_title,
            task_description=description,
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
                client_id, client_name = await _resolve_client_for_task(
                    client_name_hint=client_name_hint,
                    session=session,
                    session_service=session_service,
                    channel=channel,
                    slack=slack,
                )
                if not client_id:
                    return True  # picker/error already posted

                if not task_title:
                    pending = {
                        "awaiting": "title",
                        "client_id": client_id,
                        "client_name": client_name,
                    }
                else:
                    pending = {
                        "awaiting": "confirm_or_details",
                        "client_id": client_id,
                        "client_name": client_name,
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
            )
            return

        if intent == "confirm_draft_task":
            # No pending state (already checked above) — nothing to confirm.
            await slack.post_message(
                channel=channel,
                text="Nothing to confirm. Start with `create task for <client>: <title>`.",
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
                text=f"Now working on *{client_display}*.\n\nTry: `start ngram research`",
            )
            return

        if not session.active_client_id:
            clients = await asyncio.to_thread(session_service.list_clients_for_picker, session.profile_id)
            if not clients:
                await slack.post_message(
                    channel=channel,
                    text="I couldn’t find any clients to pick from. Ask an admin to assign you.",
                )
                return

            blocks = _build_client_picker_blocks(clients)
            await slack.post_message(channel=channel, text=_help_text())
            await slack.post_message(channel=channel, text="Select a client", blocks=blocks)
            return

        if intent == "create_ngram_task":
            client_id = str(session.active_client_id or "")
            client_name = await asyncio.to_thread(session_service.get_client_name, client_id)
            client_name = client_name or "Client"

            if not session.profile_id:
                await slack.post_message(
                    channel=channel,
                    text="I couldn't link your Slack user to a profile. Ask an admin to set `profiles.slack_user_id`.",
                )
                return

            clickup_user_id = await asyncio.to_thread(
                session_service.get_profile_clickup_user_id, session.profile_id
            )

            destination = await asyncio.to_thread(session_service.get_brand_destination_for_client, client_id)
            if not destination or not destination.get("clickup_space_id"):
                await slack.post_message(
                    channel=channel,
                    text=f"No brand configured for *{client_name}* with `clickup_space_id`. Ask an admin to set it in Command Center.",
                )
                return

            sop_service = SOPSyncService(clickup_token="", supabase_client=session_service.db)
            sop = await sop_service.get_sop_by_category("ngram")
            sop_md = str((sop or {}).get("content_md") or "")
            if not sop_md.strip():
                await slack.post_message(
                    channel=channel,
                    text="N-gram SOP not found (category='ngram'). Ask an admin to run the SOP sync.",
                )
                return

            pending = {
                "intent": "create_ngram_task",
                "client_id": client_id,
                "client_name": client_name,
                "brand_id": destination.get("id"),
                "brand_name": destination.get("name"),
            }
            await asyncio.to_thread(session_service.update_context, session.id, {"pending_task": pending})

            clickup = None
            try:
                clickup = get_clickup_service()
                task = await clickup.create_task_in_space(
                    space_id=str(destination.get("clickup_space_id")),
                    name=f"N-gram Research: {client_name}",
                    description_md=sop_md,
                    assignee_ids=[clickup_user_id] if clickup_user_id else None,
                    override_list_id=str(destination.get("clickup_list_id"))
                    if destination.get("clickup_list_id")
                    else None,
                )
            except (ClickUpConfigurationError, ClickUpError) as exc:
                await slack.post_message(channel=channel, text=f"Failed to create ClickUp task: {exc}")
                return
            finally:
                await asyncio.to_thread(session_service.update_context, session.id, {"pending_task": None})
                if clickup:
                    await clickup.aclose()

            url = task.url or ""
            link = f"<{url}|N-gram Research: {client_name}>" if url else f"N-gram Research: {client_name}"
            await slack.post_message(
                channel=channel,
                text=f"Task created: {link}",
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
                        "text": f"Now working on *{client_name}*.\n\nTry: `start ngram research`",
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
