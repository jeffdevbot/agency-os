import asyncio
import json
import logging
import os
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
    evaluate_skill_policy,
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
from ...services.agencyclaw.command_center_assignments import (
    format_person_ambiguous,
    format_remove_result,
    format_upsert_result,
    remove_assignment,
    resolve_brand_for_assignment,
    resolve_person,
    resolve_role,
    upsert_assignment,
)
from ...services.agencyclaw.command_center_brand_mutations import (
    create_brand,
    format_brand_ambiguous,
    format_brand_create_result,
    format_brand_update_result,
    resolve_brand_for_mutation,
    update_brand,
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
from ...services.agencyclaw.slack_pending_flow import (
    compose_asin_pending_description as _pending_flow_compose_asin_pending_description,
    handle_pending_task_continuation as _pending_flow_handle_pending_task_continuation,
)
from ...services.agencyclaw.skill_registry import get_skill_descriptions_for_prompt
from ...services.agencyclaw.slack_helpers import (
    _WEEKLY_TASK_CAP,
    _classify_message,
    _current_week_range_ms,
    _extract_product_identifiers,
    _format_task_line,
    _format_weekly_tasks_response,
    _help_text,
    _is_deterministic_control_intent as _helpers_is_deterministic_control_intent,
    _is_legacy_intent_fallback_enabled as _helpers_is_legacy_intent_fallback_enabled,
    _is_llm_orchestrator_enabled as _helpers_is_llm_orchestrator_enabled,
    _sanitize_client_name_hint,
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
from ...services.agencyclaw.preference_memory import PreferenceMemoryService
from ...services.playbook_session import get_playbook_session_service, get_supabase_admin_client
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
    return _helpers_is_llm_orchestrator_enabled()


def _is_planner_enabled() -> bool:
    """Check if the C10D planner feature flag is enabled."""
    return os.environ.get("AGENCYCLAW_ENABLE_PLANNER", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _is_legacy_intent_fallback_enabled() -> bool:
    return _helpers_is_legacy_intent_fallback_enabled()


def _is_llm_strict_mode() -> bool:
    return _is_llm_orchestrator_enabled() and not _is_legacy_intent_fallback_enabled()


def _is_deterministic_control_intent(intent: str) -> bool:
    return _helpers_is_deterministic_control_intent(intent)


def _should_block_deterministic_intent(intent: str) -> bool:
    return _is_llm_strict_mode() and not _is_deterministic_control_intent(intent)


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


async def _resolve_assignment_client(
    *,
    args: dict[str, Any],
    session_service: Any,
    session: Any,
    channel: str,
    slack: Any,
) -> str | bool:
    """Resolve client for assignment skills (always requires a concrete client).

    Unlike ``_resolve_cc_client_hint`` (which returns None for "scan all"),
    assignment skills always need a client_id.

    Returns:
    - A client_id string on success.
    - ``False`` if resolution failed (message already posted to Slack).
    """
    client_hint = str(args.get("client_name") or "").strip()

    # Explicit client_name hint — resolve via fuzzy match
    if client_hint:
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

    # No hint — fall back to active client on session
    if session.active_client_id:
        return str(session.active_client_id)

    # No active client — ask user to pick or switch
    clients = await asyncio.to_thread(
        session_service.list_clients_for_picker, session.profile_id,
    )
    if clients:
        blocks = _build_client_picker_blocks(clients)
        await slack.post_message(
            channel=channel,
            text="Which client is this assignment for? Pick one or say *switch to <client>* first:",
            blocks=blocks,
        )
    else:
        await slack.post_message(
            channel=channel,
            text="I need a client for this assignment. Say *switch to <client>* first.",
        )
    return False


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

    Returns a skill summary string for conversation history.
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

    # C12A: Assignment upsert
    if skill_id == "cc_assignment_upsert":
        person_name = str(args.get("person_name") or "").strip()
        role_slug = str(args.get("role_slug") or "").strip()
        brand_name_hint = str(args.get("brand_name") or "").strip()

        # Resolve client (requires concrete client, falls back to active)
        client_id = await _resolve_assignment_client(
            args=args, session_service=session_service, session=session,
            channel=channel, slack=slack,
        )
        if client_id is False:
            return "[Assignment upsert client error]"

        # Resolve person
        person_result = await asyncio.to_thread(resolve_person, db, person_name)
        if person_result["status"] == "not_found":
            await slack.post_message(
                channel=channel,
                text=f"I couldn't find a team member matching *{person_name}*.",
            )
            return "[Assignment upsert person not found]"
        if person_result["status"] == "ambiguous":
            await slack.post_message(
                channel=channel,
                text=format_person_ambiguous(person_result["candidates"]),
            )
            return "[Assignment upsert person ambiguous]"

        # Resolve role
        role_result = await asyncio.to_thread(resolve_role, db, role_slug)
        if role_result["status"] == "not_found":
            await slack.post_message(
                channel=channel,
                text=f"I couldn't find a role matching *{role_slug}*.",
            )
            return "[Assignment upsert role not found]"

        # Optionally resolve brand
        brand_id: str | None = None
        brand_display: str | None = None
        if brand_name_hint:
            brand_result = await asyncio.to_thread(
                resolve_brand_for_assignment, db, client_id, brand_name_hint,
            )
            if brand_result["status"] == "not_found":
                await slack.post_message(
                    channel=channel,
                    text=f"I couldn't find a brand matching *{brand_name_hint}*.",
                )
                return "[Assignment upsert brand not found]"
            if brand_result["status"] == "ambiguous":
                names = ", ".join(c.get("name", "?") for c in brand_result["candidates"][:5])
                await slack.post_message(
                    channel=channel,
                    text=f"Multiple brands match *{brand_name_hint}*: {names}. Please be more specific.",
                )
                return "[Assignment upsert brand ambiguous]"
            if brand_result["status"] == "ok":
                brand_id = brand_result["brand_id"]
                brand_display = brand_result["brand_name"]

        # Execute upsert
        assign_result = await asyncio.to_thread(
            upsert_assignment, db,
            client_id=client_id,
            team_member_id=person_result["profile_id"],
            role_id=role_result["role_id"],
            brand_id=brand_id,
            assigned_by=session.profile_id,
        )
        client_display = await asyncio.to_thread(
            session_service.get_client_name, client_id,
        )
        msg = format_upsert_result(
            assign_result,
            person_name=person_result["display_name"] or person_name,
            role_name=role_result["role_name"] or role_slug,
            client_name=client_display or "client",
            brand_name=brand_display,
        )
        await slack.post_message(channel=channel, text=msg)
        return "[Assignment upsert]"

    # C12A: Assignment remove
    if skill_id == "cc_assignment_remove":
        person_name = str(args.get("person_name") or "").strip()
        role_slug = str(args.get("role_slug") or "").strip()
        brand_name_hint = str(args.get("brand_name") or "").strip()

        # Resolve client (requires concrete client, falls back to active)
        client_id = await _resolve_assignment_client(
            args=args, session_service=session_service, session=session,
            channel=channel, slack=slack,
        )
        if client_id is False:
            return "[Assignment remove client error]"

        # Resolve person
        person_result = await asyncio.to_thread(resolve_person, db, person_name)
        if person_result["status"] == "not_found":
            await slack.post_message(
                channel=channel,
                text=f"I couldn't find a team member matching *{person_name}*.",
            )
            return "[Assignment remove person not found]"
        if person_result["status"] == "ambiguous":
            await slack.post_message(
                channel=channel,
                text=format_person_ambiguous(person_result["candidates"]),
            )
            return "[Assignment remove person ambiguous]"

        # Resolve role
        role_result = await asyncio.to_thread(resolve_role, db, role_slug)
        if role_result["status"] == "not_found":
            await slack.post_message(
                channel=channel,
                text=f"I couldn't find a role matching *{role_slug}*.",
            )
            return "[Assignment remove role not found]"

        # Optionally resolve brand
        brand_id = None
        brand_display = None
        if brand_name_hint:
            brand_result = await asyncio.to_thread(
                resolve_brand_for_assignment, db, client_id, brand_name_hint,
            )
            if brand_result["status"] == "not_found":
                await slack.post_message(
                    channel=channel,
                    text=f"I couldn't find a brand matching *{brand_name_hint}*.",
                )
                return "[Assignment remove brand not found]"
            if brand_result["status"] == "ambiguous":
                names = ", ".join(c.get("name", "?") for c in brand_result["candidates"][:5])
                await slack.post_message(
                    channel=channel,
                    text=f"Multiple brands match *{brand_name_hint}*: {names}. Please be more specific.",
                )
                return "[Assignment remove brand ambiguous]"
            if brand_result["status"] == "ok":
                brand_id = brand_result["brand_id"]
                brand_display = brand_result["brand_name"]

        # Execute remove
        remove_result = await asyncio.to_thread(
            remove_assignment, db,
            client_id=client_id,
            team_member_id=person_result["profile_id"],
            role_id=role_result["role_id"],
            brand_id=brand_id,
        )
        client_display = await asyncio.to_thread(
            session_service.get_client_name, client_id,
        )
        msg = format_remove_result(
            remove_result,
            person_name=person_result["display_name"] or person_name,
            role_name=role_result["role_name"] or role_slug,
            client_name=client_display or "client",
            brand_name=brand_display,
        )
        await slack.post_message(channel=channel, text=msg)
        return "[Assignment remove]"

    # C12B: Brand create
    if skill_id == "cc_brand_create":
        brand_name = str(args.get("brand_name") or "").strip()
        if not brand_name:
            await slack.post_message(channel=channel, text="I need a brand name to create.")
            return "[Brand create missing name]"

        # Resolve client (required for brand create)
        client_id = await _resolve_assignment_client(
            args=args, session_service=session_service, session=session,
            channel=channel, slack=slack,
        )
        if client_id is False:
            return "[Brand create client error]"

        result = await asyncio.to_thread(
            create_brand, db,
            client_id=client_id,
            brand_name=brand_name,
            clickup_space_id=str(args.get("clickup_space_id") or "") or None,
            clickup_list_id=str(args.get("clickup_list_id") or "") or None,
            marketplaces=str(args.get("marketplaces") or "") or None,
        )
        client_display = await asyncio.to_thread(
            session_service.get_client_name, client_id,
        )
        msg = format_brand_create_result(result, brand_name, client_display or "client")
        await slack.post_message(channel=channel, text=msg)
        return "[Brand create]"

    # C12B: Brand update
    if skill_id == "cc_brand_update":
        brand_name = str(args.get("brand_name") or "").strip()
        if not brand_name:
            await slack.post_message(channel=channel, text="I need a brand name to update.")
            return "[Brand update missing name]"

        # Resolve client scope (optional but recommended)
        client_hint = str(args.get("client_name") or "").strip()
        client_id: str | None = None
        if client_hint:
            resolved = await _resolve_assignment_client(
                args=args, session_service=session_service, session=session,
                channel=channel, slack=slack,
            )
            if resolved is False:
                return "[Brand update client error]"
            client_id = resolved
        elif session.active_client_id:
            client_id = str(session.active_client_id)

        # Resolve brand
        brand_result = await asyncio.to_thread(
            resolve_brand_for_mutation, db, client_id, brand_name,
        )
        if brand_result["status"] == "not_found":
            await slack.post_message(
                channel=channel,
                text=f"I couldn't find a brand matching *{brand_name}*.",
            )
            return "[Brand update brand not found]"
        if brand_result["status"] == "ambiguous":
            await slack.post_message(
                channel=channel,
                text=format_brand_ambiguous(brand_result["candidates"]),
            )
            return "[Brand update brand ambiguous]"

        # Apply update
        update_result = await asyncio.to_thread(
            update_brand, db,
            brand_id=brand_result["brand_id"],
            new_brand_name=str(args.get("new_brand_name") or "") or None,
            clickup_space_id=args.get("clickup_space_id"),
            clickup_list_id=args.get("clickup_list_id"),
            marketplaces=args.get("marketplaces"),
        )
        msg = format_brand_update_result(update_result, brand_result["brand_name"] or brand_name)
        await slack.post_message(channel=channel, text=msg)
        return "[Brand update]"

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

        # C12C Path-1: preserve explicitly provided identifiers in task body metadata.
        full_description = task_description or ""
        explicit_identifiers = _extract_product_identifiers(task_title, task_description)
        has_identifier_block = "product identifiers:" in full_description.lower()
        if explicit_identifiers and not has_identifier_block:
            full_description = (
                f"**Product identifiers:** {', '.join(explicit_identifiers)}\n\n{full_description}"
            ).rstrip()
        # C11D: Prepend brand metadata to task description
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
        }

        # Execute plan
        result = await execute_plan(
            plan=plan,
            slack_user_id=slack_user_id,
            channel=channel,
            session=session,
            session_service=session_service,
            slack=slack,
            check_policy=_check_skill_policy,
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
    return _pending_flow_compose_asin_pending_description(stashed_draft)


async def _handle_pending_task_continuation(
    *,
    channel: str,
    text: str,
    session: Any,
    session_service: Any,
    slack: Any,
    pending: dict[str, Any],
) -> bool:
    return await _pending_flow_handle_pending_task_continuation(
        channel=channel,
        text=text,
        session=session,
        session_service=session_service,
        slack=slack,
        pending=pending,
        classify_message=_classify_message,
        resolve_brand_for_task=_resolve_brand_for_task,
        enrich_task_draft=_enrich_task_draft,
        execute_task_create=_execute_task_create,
        extract_product_identifiers=_extract_product_identifiers,
    )


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
            policy = await _check_skill_policy(
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

            skill_summary = ""

            if skill_id == "clickup_task_list_weekly":
                await _handle_weekly_tasks(
                    slack_user_id=slack_user_id,
                    channel=channel,
                    client_name_hint=str(args.get("client_name") or ""),
                    session_service=session_service,
                    slack=slack,
                )
                skill_summary = f"[Ran weekly task list for {args.get('client_name', 'client')}]"

            elif skill_id == "clickup_task_create":
                await _handle_create_task(
                    slack_user_id=slack_user_id,
                    channel=channel,
                    client_name_hint=str(args.get("client_name") or ""),
                    task_title=str(args.get("task_title") or ""),
                    session_service=session_service,
                    slack=slack,
                )
                skill_summary = f"[Started task creation for {args.get('client_name', 'client')}]"

            elif skill_id in ("cc_client_lookup", "cc_brand_list_all", "cc_brand_clickup_mapping_audit", "cc_brand_mapping_remediation_preview", "cc_brand_mapping_remediation_apply", "cc_assignment_upsert", "cc_assignment_remove", "cc_brand_create", "cc_brand_update"):
                skill_summary = await _handle_cc_skill(
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

            # C10B.5: Persist conversation history after skill execution
            if skill_summary:
                updated = append_exchange(recent_exchanges, text, skill_summary)
                await asyncio.to_thread(
                    session_service.update_context, session.id,
                    {"recent_exchanges": compact_exchanges(updated)},
                )
            return True

        return False  # unknown mode — fall through

    except Exception as exc:  # noqa: BLE001
        _logger.warning("LLM orchestrator error: %s", exc)
        return False  # fall through to deterministic classifier


async def _check_skill_policy(
    *,
    slack_user_id: str,
    session: Any,
    channel: str,
    skill_id: str,
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """C10A: Resolve actor/surface and evaluate skill policy.

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
    return evaluate_skill_policy(actor, surface, skill_id, args, session.context)

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
        # C13A: In strict LLM-first mode, deterministic classifier is limited to
        # explicit control intents only. All operational intents must come from
        # orchestrator/planner tool-call paths.
        if _should_block_deterministic_intent(intent):
            await slack.post_message(
                channel=channel,
                text="I'm not sure what to do with that. "
                "Try asking about a client's tasks, or tell me what you need help with.",
            )
            return

        if intent == "create_task":
            # C10A: Policy gate for deterministic path
            policy = await _check_skill_policy(
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
            policy = await _check_skill_policy(
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
        if intent in ("cc_client_lookup", "cc_brand_list_all", "cc_brand_clickup_mapping_audit", "cc_brand_mapping_remediation_preview", "cc_brand_mapping_remediation_apply", "cc_assignment_upsert", "cc_assignment_remove", "cc_brand_create", "cc_brand_update"):
            policy = await _check_skill_policy(
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
