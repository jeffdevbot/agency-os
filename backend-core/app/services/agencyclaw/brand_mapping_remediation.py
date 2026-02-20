"""C11E foundation: brand mapping remediation planner (dry-run first).

This module provides deterministic planning and optional apply helpers for
fixing missing brand ClickUp mappings where a safe client-level default exists.
It is intentionally runtime-agnostic: no Slack routing or orchestrator wiring.
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

logger = logging.getLogger(__name__)

_SCAN_LIMIT_DEFAULT = 500


class RemediationPlanItem(TypedDict):
    brand_id: str
    brand_name: str
    client_id: str
    client_name: str
    current_space_id: str | None
    current_list_id: str | None
    proposed_space_id: str | None
    proposed_list_id: str | None
    missing_fields: list[str]
    safe_to_apply: bool
    reason: str


class RemediationApplyResult(TypedDict):
    total_items: int
    safe_items: int
    would_apply: int
    applied: int
    skipped: int
    failures: list[dict[str, str]]


def build_brand_mapping_remediation_plan(
    db: Any,
    *,
    client_id: str | None = None,
    limit: int = _SCAN_LIMIT_DEFAULT,
) -> list[RemediationPlanItem]:
    """Build deterministic remediation plan for brands missing ClickUp mapping.

    Rules:
    - Only brands with at least one missing mapping field are included.
    - Missing field can be auto-proposed only when the client has exactly one
      known value for that field across mapped brands.
    - If client has multiple values or no value for a required field, plan item
      is marked ``safe_to_apply=False`` with explicit reason.
    """
    rows = _fetch_brand_rows(db, client_id=client_id, limit=limit)

    client_ids = {str(r.get("client_id") or "") for r in rows if isinstance(r, dict)}
    client_names = _fetch_client_name_map(db, client_ids)

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("client_id") or "")
        if not cid:
            continue
        grouped.setdefault(cid, []).append(row)

    plan: list[RemediationPlanItem] = []
    for cid, client_rows in grouped.items():
        space_values = sorted(
            {
                str(r.get("clickup_space_id"))
                for r in client_rows
                if r.get("clickup_space_id")
            }
        )
        list_values = sorted(
            {
                str(r.get("clickup_list_id"))
                for r in client_rows
                if r.get("clickup_list_id")
            }
        )
        default_space = space_values[0] if len(space_values) == 1 else None
        default_list = list_values[0] if len(list_values) == 1 else None

        for row in client_rows:
            brand_id = str(row.get("id") or "")
            if not brand_id:
                continue
            current_space = _normalize_optional_text(row.get("clickup_space_id"))
            current_list = _normalize_optional_text(row.get("clickup_list_id"))

            missing_fields: list[str] = []
            if not current_space:
                missing_fields.append("clickup_space_id")
            if not current_list:
                missing_fields.append("clickup_list_id")
            if not missing_fields:
                continue

            proposed_space = current_space or default_space
            proposed_list = current_list or default_list

            unresolved: list[str] = []
            reasons: list[str] = []

            if "clickup_space_id" in missing_fields:
                if len(space_values) > 1:
                    unresolved.append("clickup_space_id")
                    reasons.append("multiple defaults for clickup_space_id")
                elif not default_space:
                    unresolved.append("clickup_space_id")
                    reasons.append("no client default for clickup_space_id")

            if "clickup_list_id" in missing_fields:
                if len(list_values) > 1:
                    unresolved.append("clickup_list_id")
                    reasons.append("multiple defaults for clickup_list_id")
                elif not default_list:
                    unresolved.append("clickup_list_id")
                    reasons.append("no client default for clickup_list_id")

            safe_to_apply = len(unresolved) == 0 and (
                proposed_space != current_space or proposed_list != current_list
            )

            if safe_to_apply:
                reason = "single client default mapping"
            else:
                reason = "; ".join(reasons) if reasons else "no safe remediation candidate"

            plan.append(
                RemediationPlanItem(
                    brand_id=brand_id,
                    brand_name=str(row.get("name") or ""),
                    client_id=cid,
                    client_name=client_names.get(cid, ""),
                    current_space_id=current_space,
                    current_list_id=current_list,
                    proposed_space_id=proposed_space,
                    proposed_list_id=proposed_list,
                    missing_fields=missing_fields,
                    safe_to_apply=safe_to_apply,
                    reason=reason,
                )
            )

    plan.sort(key=lambda item: (item["client_name"].lower(), item["brand_name"].lower()))
    return plan


def apply_brand_mapping_remediation_plan(
    db: Any,
    plan: list[RemediationPlanItem],
    *,
    dry_run: bool = True,
) -> RemediationApplyResult:
    """Apply a remediation plan to ``brands`` table (or report dry-run impact)."""
    safe_items = [item for item in plan if item.get("safe_to_apply")]
    result: RemediationApplyResult = {
        "total_items": len(plan),
        "safe_items": len(safe_items),
        "would_apply": len(safe_items),
        "applied": 0,
        "skipped": len(plan) - len(safe_items),
        "failures": [],
    }

    if dry_run:
        return result

    for item in safe_items:
        payload: dict[str, str] = {}
        if not item.get("current_space_id") and item.get("proposed_space_id"):
            payload["clickup_space_id"] = str(item["proposed_space_id"])
        if not item.get("current_list_id") and item.get("proposed_list_id"):
            payload["clickup_list_id"] = str(item["proposed_list_id"])

        if not payload:
            result["skipped"] += 1
            continue

        brand_id = item.get("brand_id", "")
        try:
            db.table("brands").update(payload).eq("id", brand_id).execute()
            result["applied"] += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed applying mapping remediation for brand=%s", brand_id, exc_info=True)
            result["failures"].append({"brand_id": str(brand_id), "error": str(exc)})

    return result


def _fetch_brand_rows(
    db: Any,
    *,
    client_id: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    query = (
        db.table("brands")
        .select("id,name,client_id,clickup_space_id,clickup_list_id")
        .order("name", desc=False)
        .limit(limit)
    )
    if client_id:
        query = query.eq("client_id", client_id)

    response = query.execute()
    rows = response.data if isinstance(response.data, list) else []
    return [r for r in rows if isinstance(r, dict)]


def _fetch_client_name_map(
    db: Any,
    client_ids: set[str],
) -> dict[str, str]:
    ids = sorted(cid for cid in client_ids if cid)
    if not ids:
        return {}

    query = db.table("agency_clients").select("id,name")
    if hasattr(query, "in_"):
        query = query.in_("id", ids)

    try:
        response = query.execute()
    except Exception:  # noqa: BLE001
        logger.warning("Failed loading agency client names for remediation plan", exc_info=True)
        return {}

    rows = response.data if isinstance(response.data, list) else []
    out: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("id") or "")
        name = str(row.get("name") or "")
        if cid and name:
            out[cid] = name
    return out


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

