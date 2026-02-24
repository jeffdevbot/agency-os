"""Deterministic pending-confirmation contract helpers for agent loop."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, TypedDict


class PendingConfirmation(TypedDict):
    action_type: str
    skill_id: str
    args: dict[str, Any]
    requested_by: str
    requested_at: str
    expires_at: str
    proposal_fingerprint: str


ValidationState = Literal["confirm", "cancel", "ignore", "expired", "wrong_actor", "invalid"]


class ValidationResult(TypedDict):
    state: ValidationState
    reason: str


_AFFIRMATIVE = {
    "yes",
    "y",
    "confirm",
    "confirmed",
    "approve",
    "approved",
    "do it",
    "go ahead",
    "create it",
}

_NEGATIVE = {
    "no",
    "n",
    "cancel",
    "stop",
    "never mind",
    "nevermind",
    "dont",
    "don't",
    "abort",
}


def build_pending_confirmation(
    *,
    action_type: str,
    skill_id: str,
    args: dict[str, Any],
    requested_by: str,
    lane_key: str,
    now: datetime | None = None,
    ttl_seconds: int = 600,
) -> PendingConfirmation:
    if not isinstance(args, dict):
        raise ValueError("args must be a dict")
    requested_by = (requested_by or "").strip()
    lane_key = (lane_key or "").strip()
    skill_id = (skill_id or "").strip()
    action_type = (action_type or "").strip()
    if not requested_by:
        raise ValueError("requested_by is required")
    if not lane_key:
        raise ValueError("lane_key is required")
    if not skill_id:
        raise ValueError("skill_id is required")
    if not action_type:
        raise ValueError("action_type is required")

    now_dt = now or datetime.now(timezone.utc)
    requested_at = now_dt.isoformat()
    expires_at = (now_dt + timedelta(seconds=ttl_seconds)).isoformat()
    canonical_args = json.dumps(args, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    fingerprint_base = f"{skill_id}|{canonical_args}|{requested_by}|{lane_key}"
    proposal_fingerprint = hashlib.sha256(fingerprint_base.encode("utf-8")).hexdigest()
    return PendingConfirmation(
        action_type=action_type,
        skill_id=skill_id,
        args=args,
        requested_by=requested_by,
        requested_at=requested_at,
        expires_at=expires_at,
        proposal_fingerprint=proposal_fingerprint,
    )


def is_expired(payload: dict[str, Any], now: datetime | None = None) -> bool:
    expires_at = payload.get("expires_at")
    if not isinstance(expires_at, str) or not expires_at.strip():
        return True
    try:
        parsed = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    now_dt = now or datetime.now(timezone.utc)
    return now_dt >= parsed.astimezone(timezone.utc)


def is_affirmative(text: str) -> bool:
    value = (text or "").strip().lower()
    return value in _AFFIRMATIVE


def is_negative(text: str) -> bool:
    value = (text or "").strip().lower()
    return value in _NEGATIVE


def validate_confirmation(
    payload: dict[str, Any] | None,
    *,
    slack_user_id: str,
    text: str,
    now: datetime | None = None,
) -> ValidationResult:
    if not isinstance(payload, dict):
        return ValidationResult(state="invalid", reason="missing_payload")
    if is_expired(payload, now=now):
        return ValidationResult(state="expired", reason="expired")

    requested_by = str(payload.get("requested_by") or "").strip()
    actor = (slack_user_id or "").strip()
    if requested_by and actor and requested_by != actor:
        return ValidationResult(state="wrong_actor", reason="wrong_actor")

    if is_negative(text):
        return ValidationResult(state="cancel", reason="user_cancelled")
    if is_affirmative(text):
        return ValidationResult(state="confirm", reason="user_confirmed")
    return ValidationResult(state="ignore", reason="no_confirmation_intent")
