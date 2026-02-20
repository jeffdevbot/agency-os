"""Command Center skill dispatch helpers for Slack runtime."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from .brand_mapping_remediation import (
    apply_brand_mapping_remediation_plan,
    build_brand_mapping_remediation_plan,
)
from .command_center_assignments import (
    format_person_ambiguous,
    format_remove_result,
    format_upsert_result,
    remove_assignment,
    resolve_brand_for_assignment,
    resolve_person,
    resolve_role,
    upsert_assignment,
)
from .command_center_brand_mutations import (
    create_brand,
    format_brand_ambiguous,
    format_brand_create_result,
    format_brand_update_result,
    resolve_brand_for_mutation,
    update_brand,
)
from .command_center_lookup import (
    audit_brand_mappings,
    format_brand_list,
    format_client_list,
    format_mapping_audit,
    list_brands,
    lookup_clients,
)


def format_remediation_preview(plan: list[dict[str, Any]]) -> str:
    """Format a remediation plan as a human-readable Slack message."""
    if not plan:
        return "All brands have ClickUp mappings. Nothing to remediate."

    safe = [item for item in plan if item.get("safe_to_apply")]
    blocked = [item for item in plan if not item.get("safe_to_apply")]

    lines: list[str] = [
        "*Brand Mapping Remediation Preview*",
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


def format_remediation_apply_result(result: dict[str, Any]) -> str:
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


async def resolve_cc_client_hint(
    *,
    args: dict[str, Any],
    session_service: Any,
    session: Any,
    channel: str,
    slack: Any,
    build_client_picker_blocks: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
) -> str | None | bool:
    """Resolve optional client_name hint for CC skills."""
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
        blocks = build_client_picker_blocks(matches)
        await slack.post_message(
            channel=channel,
            text=f"Multiple clients match *{client_hint}*. Pick one and try again:",
            blocks=blocks,
        )
        return False

    return str(matches[0].get("id") or "")


async def handle_cc_skill(
    *,
    skill_id: str,
    args: dict[str, Any],
    session: Any,
    session_service: Any,
    channel: str,
    slack: Any,
    build_client_picker_blocks: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    resolve_cc_client_hint_fn: Callable[..., Awaitable[str | None | bool]],
    resolve_assignment_client_fn: Callable[..., Awaitable[str | bool]],
    lookup_clients_fn: Callable[..., Any] = lookup_clients,
    format_client_list_fn: Callable[..., str] = format_client_list,
    list_brands_fn: Callable[..., Any] = list_brands,
    format_brand_list_fn: Callable[..., str] = format_brand_list,
    audit_brand_mappings_fn: Callable[..., Any] = audit_brand_mappings,
    format_mapping_audit_fn: Callable[..., str] = format_mapping_audit,
    build_brand_mapping_remediation_plan_fn: Callable[..., Any] = build_brand_mapping_remediation_plan,
    apply_brand_mapping_remediation_plan_fn: Callable[..., Any] = apply_brand_mapping_remediation_plan,
    format_remediation_preview_fn: Callable[[list[dict[str, Any]]], str] = format_remediation_preview,
    format_remediation_apply_result_fn: Callable[[dict[str, Any]], str] = format_remediation_apply_result,
    resolve_person_fn: Callable[..., Any] = resolve_person,
    resolve_role_fn: Callable[..., Any] = resolve_role,
    resolve_brand_for_assignment_fn: Callable[..., Any] = resolve_brand_for_assignment,
    upsert_assignment_fn: Callable[..., Any] = upsert_assignment,
    remove_assignment_fn: Callable[..., Any] = remove_assignment,
    format_person_ambiguous_fn: Callable[..., str] = format_person_ambiguous,
    format_upsert_result_fn: Callable[..., str] = format_upsert_result,
    format_remove_result_fn: Callable[..., str] = format_remove_result,
    create_brand_fn: Callable[..., Any] = create_brand,
    format_brand_create_result_fn: Callable[..., str] = format_brand_create_result,
    resolve_brand_for_mutation_fn: Callable[..., Any] = resolve_brand_for_mutation,
    format_brand_ambiguous_fn: Callable[..., str] = format_brand_ambiguous,
    update_brand_fn: Callable[..., Any] = update_brand,
    format_brand_update_result_fn: Callable[..., str] = format_brand_update_result,
) -> str:
    """Dispatch a Command Center skill and post results."""
    db = session_service.db

    if skill_id == "cc_client_lookup":
        query = str(args.get("query") or "")
        clients = await asyncio.to_thread(lookup_clients_fn, db, session.profile_id, query)
        await slack.post_message(channel=channel, text=format_client_list_fn(clients))
        return "[Listed clients]"

    if skill_id == "cc_brand_list_all":
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
                blocks = build_client_picker_blocks(matches)
                await slack.post_message(
                    channel=channel,
                    text=f"Multiple clients match *{client_hint}*. Pick one and try again:",
                    blocks=blocks,
                )
                return "[Brand list client ambiguous]"
            client_id = str(matches[0].get("id") or "")

        brands = await asyncio.to_thread(list_brands_fn, db, client_id)
        await slack.post_message(channel=channel, text=format_brand_list_fn(brands))
        return "[Listed brands]"

    if skill_id == "cc_brand_clickup_mapping_audit":
        missing = await asyncio.to_thread(audit_brand_mappings_fn, db)
        await slack.post_message(channel=channel, text=format_mapping_audit_fn(missing))
        return "[Ran ClickUp mapping audit]"

    if skill_id == "cc_brand_mapping_remediation_preview":
        client_id = await resolve_cc_client_hint_fn(
            args=args,
            session_service=session_service,
            session=session,
            channel=channel,
            slack=slack,
            build_client_picker_blocks=build_client_picker_blocks,
        )
        if client_id is False:
            return "[Remediation preview client error]"

        plan = await asyncio.to_thread(build_brand_mapping_remediation_plan_fn, db, client_id=client_id)
        await slack.post_message(channel=channel, text=format_remediation_preview_fn(plan))
        return "[Remediation preview]"

    if skill_id == "cc_brand_mapping_remediation_apply":
        client_id = await resolve_cc_client_hint_fn(
            args=args,
            session_service=session_service,
            session=session,
            channel=channel,
            slack=slack,
            build_client_picker_blocks=build_client_picker_blocks,
        )
        if client_id is False:
            return "[Remediation apply client error]"

        plan = await asyncio.to_thread(build_brand_mapping_remediation_plan_fn, db, client_id=client_id)
        result = await asyncio.to_thread(apply_brand_mapping_remediation_plan_fn, db, plan, dry_run=False)
        await slack.post_message(channel=channel, text=format_remediation_apply_result_fn(result))
        return "[Remediation applied]"

    if skill_id == "cc_assignment_upsert":
        person_name = str(args.get("person_name") or "").strip()
        role_slug = str(args.get("role_slug") or "").strip()
        brand_name_hint = str(args.get("brand_name") or "").strip()

        client_id = await resolve_assignment_client_fn(
            args=args, session_service=session_service, session=session, channel=channel, slack=slack,
        )
        if client_id is False:
            return "[Assignment upsert client error]"

        person_result = await asyncio.to_thread(resolve_person_fn, db, person_name)
        if person_result["status"] == "not_found":
            await slack.post_message(
                channel=channel,
                text=f"I couldn't find a team member matching *{person_name}*.",
            )
            return "[Assignment upsert person not found]"
        if person_result["status"] == "ambiguous":
            await slack.post_message(channel=channel, text=format_person_ambiguous_fn(person_result["candidates"]))
            return "[Assignment upsert person ambiguous]"

        role_result = await asyncio.to_thread(resolve_role_fn, db, role_slug)
        if role_result["status"] == "not_found":
            await slack.post_message(channel=channel, text=f"I couldn't find a role matching *{role_slug}*.")
            return "[Assignment upsert role not found]"

        brand_id: str | None = None
        brand_display: str | None = None
        if brand_name_hint:
            brand_result = await asyncio.to_thread(resolve_brand_for_assignment_fn, db, client_id, brand_name_hint)
            if brand_result["status"] == "not_found":
                await slack.post_message(channel=channel, text=f"I couldn't find a brand matching *{brand_name_hint}*.")
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

        assign_result = await asyncio.to_thread(
            upsert_assignment_fn,
            db,
            client_id=client_id,
            team_member_id=person_result["profile_id"],
            role_id=role_result["role_id"],
            brand_id=brand_id,
            assigned_by=session.profile_id,
        )
        client_display = await asyncio.to_thread(session_service.get_client_name, client_id)
        msg = format_upsert_result_fn(
            assign_result,
            person_name=person_result["display_name"] or person_name,
            role_name=role_result["role_name"] or role_slug,
            client_name=client_display or "client",
            brand_name=brand_display,
        )
        await slack.post_message(channel=channel, text=msg)
        return "[Assignment upsert]"

    if skill_id == "cc_assignment_remove":
        person_name = str(args.get("person_name") or "").strip()
        role_slug = str(args.get("role_slug") or "").strip()
        brand_name_hint = str(args.get("brand_name") or "").strip()

        client_id = await resolve_assignment_client_fn(
            args=args, session_service=session_service, session=session, channel=channel, slack=slack,
        )
        if client_id is False:
            return "[Assignment remove client error]"

        person_result = await asyncio.to_thread(resolve_person_fn, db, person_name)
        if person_result["status"] == "not_found":
            await slack.post_message(
                channel=channel,
                text=f"I couldn't find a team member matching *{person_name}*.",
            )
            return "[Assignment remove person not found]"
        if person_result["status"] == "ambiguous":
            await slack.post_message(channel=channel, text=format_person_ambiguous_fn(person_result["candidates"]))
            return "[Assignment remove person ambiguous]"

        role_result = await asyncio.to_thread(resolve_role_fn, db, role_slug)
        if role_result["status"] == "not_found":
            await slack.post_message(channel=channel, text=f"I couldn't find a role matching *{role_slug}*.")
            return "[Assignment remove role not found]"

        brand_id = None
        brand_display = None
        if brand_name_hint:
            brand_result = await asyncio.to_thread(resolve_brand_for_assignment_fn, db, client_id, brand_name_hint)
            if brand_result["status"] == "not_found":
                await slack.post_message(channel=channel, text=f"I couldn't find a brand matching *{brand_name_hint}*.")
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

        remove_result = await asyncio.to_thread(
            remove_assignment_fn,
            db,
            client_id=client_id,
            team_member_id=person_result["profile_id"],
            role_id=role_result["role_id"],
            brand_id=brand_id,
        )
        client_display = await asyncio.to_thread(session_service.get_client_name, client_id)
        msg = format_remove_result_fn(
            remove_result,
            person_name=person_result["display_name"] or person_name,
            role_name=role_result["role_name"] or role_slug,
            client_name=client_display or "client",
            brand_name=brand_display,
        )
        await slack.post_message(channel=channel, text=msg)
        return "[Assignment remove]"

    if skill_id == "cc_brand_create":
        brand_name = str(args.get("brand_name") or "").strip()
        if not brand_name:
            await slack.post_message(channel=channel, text="I need a brand name to create.")
            return "[Brand create missing name]"

        client_id = await resolve_assignment_client_fn(
            args=args, session_service=session_service, session=session, channel=channel, slack=slack,
        )
        if client_id is False:
            return "[Brand create client error]"

        result = await asyncio.to_thread(
            create_brand_fn,
            db,
            client_id=client_id,
            brand_name=brand_name,
            clickup_space_id=str(args.get("clickup_space_id") or "") or None,
            clickup_list_id=str(args.get("clickup_list_id") or "") or None,
            marketplaces=str(args.get("marketplaces") or "") or None,
        )
        client_display = await asyncio.to_thread(session_service.get_client_name, client_id)
        msg = format_brand_create_result_fn(result, brand_name, client_display or "client")
        await slack.post_message(channel=channel, text=msg)
        return "[Brand create]"

    if skill_id == "cc_brand_update":
        brand_name = str(args.get("brand_name") or "").strip()
        if not brand_name:
            await slack.post_message(channel=channel, text="I need a brand name to update.")
            return "[Brand update missing name]"

        client_hint = str(args.get("client_name") or "").strip()
        client_id: str | None = None
        if client_hint:
            resolved = await resolve_assignment_client_fn(
                args=args, session_service=session_service, session=session, channel=channel, slack=slack,
            )
            if resolved is False:
                return "[Brand update client error]"
            client_id = resolved
        elif session.active_client_id:
            client_id = str(session.active_client_id)

        brand_result = await asyncio.to_thread(resolve_brand_for_mutation_fn, db, client_id, brand_name)
        if brand_result["status"] == "not_found":
            await slack.post_message(channel=channel, text=f"I couldn't find a brand matching *{brand_name}*.")
            return "[Brand update brand not found]"
        if brand_result["status"] == "ambiguous":
            await slack.post_message(channel=channel, text=format_brand_ambiguous_fn(brand_result["candidates"]))
            return "[Brand update brand ambiguous]"

        update_result = await asyncio.to_thread(
            update_brand_fn,
            db,
            brand_id=brand_result["brand_id"],
            new_brand_name=str(args.get("new_brand_name") or "") or None,
            clickup_space_id=args.get("clickup_space_id"),
            clickup_list_id=args.get("clickup_list_id"),
            marketplaces=args.get("marketplaces"),
        )
        msg = format_brand_update_result_fn(update_result, brand_result["brand_name"] or brand_name)
        await slack.post_message(channel=channel, text=msg)
        return "[Brand update]"

    return ""
