"""Bridge helpers for Slack route Command Center wrapper shims."""

from __future__ import annotations

from dataclasses import dataclass
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
from .slack_cc_dispatch import (
    format_remediation_apply_result as _cc_format_remediation_apply_result,
    format_remediation_preview as _cc_format_remediation_preview,
    handle_cc_skill as _cc_handle_cc_skill,
    resolve_cc_client_hint as _cc_resolve_cc_client_hint,
)
from .slack_resolution_runtime import resolve_assignment_client_runtime


@dataclass(frozen=True)
class SlackCCBridgeRuntimeDeps:
    build_client_picker_blocks_fn: Callable[[list[dict[str, Any]]], list[dict[str, Any]]]

    lookup_clients_fn: Callable[..., Any] = lookup_clients
    format_client_list_fn: Callable[..., str] = format_client_list
    list_brands_fn: Callable[..., Any] = list_brands
    format_brand_list_fn: Callable[..., str] = format_brand_list
    audit_brand_mappings_fn: Callable[..., Any] = audit_brand_mappings
    format_mapping_audit_fn: Callable[..., str] = format_mapping_audit
    build_brand_mapping_remediation_plan_fn: Callable[..., Any] = build_brand_mapping_remediation_plan
    apply_brand_mapping_remediation_plan_fn: Callable[..., Any] = apply_brand_mapping_remediation_plan
    resolve_person_fn: Callable[..., Any] = resolve_person
    resolve_role_fn: Callable[..., Any] = resolve_role
    resolve_brand_for_assignment_fn: Callable[..., Any] = resolve_brand_for_assignment
    upsert_assignment_fn: Callable[..., Any] = upsert_assignment
    remove_assignment_fn: Callable[..., Any] = remove_assignment
    format_person_ambiguous_fn: Callable[..., str] = format_person_ambiguous
    format_upsert_result_fn: Callable[..., str] = format_upsert_result
    format_remove_result_fn: Callable[..., str] = format_remove_result
    create_brand_fn: Callable[..., Any] = create_brand
    format_brand_create_result_fn: Callable[..., str] = format_brand_create_result
    resolve_brand_for_mutation_fn: Callable[..., Any] = resolve_brand_for_mutation
    format_brand_ambiguous_fn: Callable[..., str] = format_brand_ambiguous
    update_brand_fn: Callable[..., Any] = update_brand
    format_brand_update_result_fn: Callable[..., str] = format_brand_update_result


def build_cc_bridge_runtime_deps(
    *,
    build_client_picker_blocks_fn: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    lookup_clients_fn: Callable[..., Any] = lookup_clients,
    format_client_list_fn: Callable[..., str] = format_client_list,
    list_brands_fn: Callable[..., Any] = list_brands,
    format_brand_list_fn: Callable[..., str] = format_brand_list,
    audit_brand_mappings_fn: Callable[..., Any] = audit_brand_mappings,
    format_mapping_audit_fn: Callable[..., str] = format_mapping_audit,
    build_brand_mapping_remediation_plan_fn: Callable[..., Any] = build_brand_mapping_remediation_plan,
    apply_brand_mapping_remediation_plan_fn: Callable[..., Any] = apply_brand_mapping_remediation_plan,
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
) -> SlackCCBridgeRuntimeDeps:
    return SlackCCBridgeRuntimeDeps(
        build_client_picker_blocks_fn=build_client_picker_blocks_fn,
        lookup_clients_fn=lookup_clients_fn,
        format_client_list_fn=format_client_list_fn,
        list_brands_fn=list_brands_fn,
        format_brand_list_fn=format_brand_list_fn,
        audit_brand_mappings_fn=audit_brand_mappings_fn,
        format_mapping_audit_fn=format_mapping_audit_fn,
        build_brand_mapping_remediation_plan_fn=build_brand_mapping_remediation_plan_fn,
        apply_brand_mapping_remediation_plan_fn=apply_brand_mapping_remediation_plan_fn,
        resolve_person_fn=resolve_person_fn,
        resolve_role_fn=resolve_role_fn,
        resolve_brand_for_assignment_fn=resolve_brand_for_assignment_fn,
        upsert_assignment_fn=upsert_assignment_fn,
        remove_assignment_fn=remove_assignment_fn,
        format_person_ambiguous_fn=format_person_ambiguous_fn,
        format_upsert_result_fn=format_upsert_result_fn,
        format_remove_result_fn=format_remove_result_fn,
        create_brand_fn=create_brand_fn,
        format_brand_create_result_fn=format_brand_create_result_fn,
        resolve_brand_for_mutation_fn=resolve_brand_for_mutation_fn,
        format_brand_ambiguous_fn=format_brand_ambiguous_fn,
        update_brand_fn=update_brand_fn,
        format_brand_update_result_fn=format_brand_update_result_fn,
    )


async def resolve_cc_client_hint_bridge_runtime(
    *,
    args: dict[str, Any],
    session_service: Any,
    session: Any,
    channel: str,
    slack: Any,
    deps: SlackCCBridgeRuntimeDeps,
    build_client_picker_blocks: Any | None = None,
) -> str | None | bool:
    return await _cc_resolve_cc_client_hint(
        args=args,
        session_service=session_service,
        session=session,
        channel=channel,
        slack=slack,
        build_client_picker_blocks=build_client_picker_blocks or deps.build_client_picker_blocks_fn,
    )


async def resolve_assignment_client_bridge_runtime(
    *,
    args: dict[str, Any],
    session_service: Any,
    session: Any,
    channel: str,
    slack: Any,
    deps: SlackCCBridgeRuntimeDeps,
) -> str | bool:
    return await resolve_assignment_client_runtime(
        args=args,
        session_service=session_service,
        session=session,
        channel=channel,
        slack=slack,
        build_client_picker_blocks_fn=deps.build_client_picker_blocks_fn,
    )


def format_remediation_preview_bridge_runtime(plan: list[dict[str, Any]]) -> str:
    return _cc_format_remediation_preview(plan)


def format_remediation_apply_result_bridge_runtime(result: dict[str, Any]) -> str:
    return _cc_format_remediation_apply_result(result)


async def handle_cc_skill_bridge_runtime(
    *,
    skill_id: str,
    args: dict[str, Any],
    session: Any,
    session_service: Any,
    channel: str,
    slack: Any,
    deps: SlackCCBridgeRuntimeDeps,
) -> str:
    async def _resolve_cc_client_hint(**kwargs: Any) -> str | None | bool:
        return await resolve_cc_client_hint_bridge_runtime(
            deps=deps,
            **kwargs,
        )

    async def _resolve_assignment_client(**kwargs: Any) -> str | bool:
        return await resolve_assignment_client_bridge_runtime(
            deps=deps,
            **kwargs,
        )

    return await _cc_handle_cc_skill(
        skill_id=skill_id,
        args=args,
        session=session,
        session_service=session_service,
        channel=channel,
        slack=slack,
        build_client_picker_blocks=deps.build_client_picker_blocks_fn,
        resolve_cc_client_hint_fn=_resolve_cc_client_hint,
        resolve_assignment_client_fn=_resolve_assignment_client,
        lookup_clients_fn=deps.lookup_clients_fn,
        format_client_list_fn=deps.format_client_list_fn,
        list_brands_fn=deps.list_brands_fn,
        format_brand_list_fn=deps.format_brand_list_fn,
        audit_brand_mappings_fn=deps.audit_brand_mappings_fn,
        format_mapping_audit_fn=deps.format_mapping_audit_fn,
        build_brand_mapping_remediation_plan_fn=deps.build_brand_mapping_remediation_plan_fn,
        apply_brand_mapping_remediation_plan_fn=deps.apply_brand_mapping_remediation_plan_fn,
        format_remediation_preview_fn=format_remediation_preview_bridge_runtime,
        format_remediation_apply_result_fn=format_remediation_apply_result_bridge_runtime,
        resolve_person_fn=deps.resolve_person_fn,
        resolve_role_fn=deps.resolve_role_fn,
        resolve_brand_for_assignment_fn=deps.resolve_brand_for_assignment_fn,
        upsert_assignment_fn=deps.upsert_assignment_fn,
        remove_assignment_fn=deps.remove_assignment_fn,
        format_person_ambiguous_fn=deps.format_person_ambiguous_fn,
        format_upsert_result_fn=deps.format_upsert_result_fn,
        format_remove_result_fn=deps.format_remove_result_fn,
        create_brand_fn=deps.create_brand_fn,
        format_brand_create_result_fn=deps.format_brand_create_result_fn,
        resolve_brand_for_mutation_fn=deps.resolve_brand_for_mutation_fn,
        format_brand_ambiguous_fn=deps.format_brand_ambiguous_fn,
        update_brand_fn=deps.update_brand_fn,
        format_brand_update_result_fn=deps.format_brand_update_result_fn,
    )
