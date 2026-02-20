"""C10A: Actor/Surface context resolver + policy gate for AgencyClaw.

Provides a fail-closed authorization layer that resolves WHO is asking
(actor context) and WHERE they are asking (surface context), then evaluates
whether a specific skill execution is permitted.

All functions are **synchronous** for the DB-backed resolve_actor_context;
callers should wrap in ``asyncio.to_thread`` when calling from async code.
resolve_surface_context and evaluate_skill_policy are pure functions.
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from .skill_registry import SKILL_SCHEMAS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

_KNOWN_ROLES = ("admin", "operator", "viewer")
_KNOWN_SURFACES = ("dm", "channel", "group")

# Skills classified by mutation vs read
_MUTATION_SKILLS = frozenset({
    "clickup_task_create",
    "cc_brand_mapping_remediation_apply",
    "cc_assignment_upsert",
    "cc_assignment_remove",
    "cc_brand_create",
    "cc_brand_update",
})
_READ_SKILLS = frozenset({
    "clickup_task_list",
    "clickup_task_list_weekly",
    "cc_client_lookup",
    "cc_brand_list_all",
    "cc_brand_clickup_mapping_audit",
    "cc_brand_mapping_remediation_preview",
})
_ADMIN_SKILLS = frozenset({
    "cc_brand_clickup_mapping_audit",
    "cc_brand_mapping_remediation_preview",
    "cc_brand_mapping_remediation_apply",
    "cc_assignment_upsert",
    "cc_assignment_remove",
    "cc_brand_create",
    "cc_brand_update",
})


class ActorContext(TypedDict):
    profile_id: str | None
    slack_user_id: str
    role: str  # "admin" | "operator" | "viewer" | "unknown"
    is_admin: bool


class SurfaceContext(TypedDict):
    channel_id: str
    surface_type: str  # "dm" | "channel" | "group" | "unknown"


class PolicyDecision(TypedDict):
    allowed: bool
    reason_code: str
    user_message: str
    meta: dict[str, Any]


# ---------------------------------------------------------------------------
# Resolvers
# ---------------------------------------------------------------------------


def resolve_actor_context(
    db: Any,
    slack_user_id: str,
    profile_id: str | None,
) -> ActorContext:
    """Resolve actor identity from profile table.

    Queries ``profiles`` for ``is_admin`` to determine role.
    Returns ``role="unknown"`` if profile is missing or lookup fails.
    This is a sync function (Supabase client is sync).
    """
    if not profile_id:
        return ActorContext(
            profile_id=None,
            slack_user_id=slack_user_id,
            role="unknown",
            is_admin=False,
        )

    try:
        response = (
            db.table("profiles")
            .select("id, is_admin")
            .eq("id", profile_id)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            return ActorContext(
                profile_id=profile_id,
                slack_user_id=slack_user_id,
                role="unknown",
                is_admin=False,
            )

        is_admin = bool(rows[0].get("is_admin", False))
        role = "admin" if is_admin else "operator"

        return ActorContext(
            profile_id=profile_id,
            slack_user_id=slack_user_id,
            role=role,
            is_admin=is_admin,
        )
    except Exception:
        logger.warning(
            "Failed to resolve actor context for profile=%s, slack=%s",
            profile_id, slack_user_id, exc_info=True,
        )
        # Fail closed: unknown role on error
        return ActorContext(
            profile_id=profile_id,
            slack_user_id=slack_user_id,
            role="unknown",
            is_admin=False,
        )


def resolve_surface_context(
    channel_id: str,
    event_payload: dict[str, Any] | None = None,
) -> SurfaceContext:
    """Resolve the surface (DM, channel, group) from channel metadata.

    Uses ``channel_type`` from the Slack event payload when available.
    Falls back to channel ID prefix heuristic (D=DM, C=channel, G=group).
    """
    surface_type = "unknown"

    # Prefer explicit channel_type from event payload
    if event_payload:
        ct = str(event_payload.get("channel_type") or "").lower()
        if ct == "im":
            surface_type = "dm"
        elif ct == "channel":
            surface_type = "channel"
        elif ct == "group":
            surface_type = "group"
        elif ct == "mpim":
            surface_type = "group"

    # Fallback: channel ID prefix heuristic
    if surface_type == "unknown" and channel_id:
        prefix = channel_id[0].upper()
        if prefix == "D":
            surface_type = "dm"
        elif prefix == "C":
            surface_type = "channel"
        elif prefix == "G":
            surface_type = "group"

    return SurfaceContext(channel_id=channel_id, surface_type=surface_type)


# ---------------------------------------------------------------------------
# Policy evaluator
# ---------------------------------------------------------------------------


def evaluate_skill_policy(
    actor: ActorContext,
    surface: SurfaceContext,
    skill_id: str,
    args: dict[str, Any] | None = None,
    session_context: dict[str, Any] | None = None,
) -> PolicyDecision:
    """Evaluate whether a skill execution is permitted.

    Fail-closed: any unrecognized actor, surface, or skill is denied.

    V1 rules:
    - Unknown actor role → deny
    - Unknown surface → deny
    - Unknown skill_id → deny
    - Mutation skills (clickup_task_create): DM only
    - Read skills (clickup_task_list/clickup_task_list_weekly): DM only (v1)
    - Viewer role → deny mutations, allow reads
    """
    meta: dict[str, Any] = {
        "actor_role": actor["role"],
        "surface_type": surface["surface_type"],
        "skill_id": skill_id,
    }

    # --- Unknown actor ---
    if actor["role"] not in _KNOWN_ROLES:
        return PolicyDecision(
            allowed=False,
            reason_code="unknown_actor",
            user_message="I couldn't verify your identity. Please ask an admin to link your Slack account.",
            meta=meta,
        )

    # --- Unknown surface ---
    if surface["surface_type"] not in _KNOWN_SURFACES:
        return PolicyDecision(
            allowed=False,
            reason_code="unknown_surface",
            user_message="I can only run tools in a direct message for now.",
            meta=meta,
        )

    # --- Unknown skill ---
    if skill_id not in SKILL_SCHEMAS:
        return PolicyDecision(
            allowed=False,
            reason_code="unknown_skill",
            user_message="That action isn't available.",
            meta=meta,
        )

    # --- Surface restrictions (v1: DM only for all skills) ---
    if surface["surface_type"] != "dm":
        reason = "non_dm_mutation" if skill_id in _MUTATION_SKILLS else "non_dm_read"
        return PolicyDecision(
            allowed=False,
            reason_code=reason,
            user_message="I can only run tools in a direct message for now.",
            meta=meta,
        )

    # --- Role restrictions ---
    if actor["role"] == "viewer" and skill_id in _MUTATION_SKILLS:
        return PolicyDecision(
            allowed=False,
            reason_code="viewer_mutation_denied",
            user_message="You don't have permission to create tasks. Ask an admin to upgrade your access.",
            meta=meta,
        )

    # --- Admin-only skills (C11A) ---
    if skill_id in _ADMIN_SKILLS and not actor["is_admin"]:
        return PolicyDecision(
            allowed=False,
            reason_code="admin_skill_denied",
            user_message="That action requires admin access.",
            meta=meta,
        )

    # --- Allowed ---
    return PolicyDecision(
        allowed=True,
        reason_code="allowed",
        user_message="",
        meta=meta,
    )
