"""C10F: Semantic pending-state resolver for AgencyClaw task creation.

This module converts free-form user text into typed pending-state actions.
It is intentionally deterministic and side-effect free:
- no DB calls
- no network calls
- no Slack/ClickUp dependencies

Runtime code can then execute actions safely with existing guardrails.
"""

from __future__ import annotations

import re
from typing import Literal, TypedDict


PendingAction = Literal[
    "interrupt",
    "cancel",
    "proceed_draft",
    "proceed_with_asin_pending",
    "provide_identifier",
    "provide_details",
    "off_topic",
    "reask",
]


class PendingResolution(TypedDict):
    action: PendingAction
    reason: str


_CANCEL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^(?:cancel|cancel task|abort|stop|never mind|nevermind|forget it)$"),
)

_PROCEED_DRAFT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^(?:yes(?:,?\s*please)?|okay|ok|sure)[.!]?$"),
    re.compile(r"^(?:create|proceed|do|ship)\s+(?:it|this)(?:\s+now)?$"),
    re.compile(r"^(?:go ahead(?:\s+and)?\s+create(?:\s+it)?)$"),
    re.compile(r"^(?:just create it|create anyway|create as draft)$"),
)

_DEFER_ASIN_CUES: tuple[str, ...] = (
    "asin pending",
    "sku pending",
    "identifier pending",
    "create with asin pending",
    "create with sku pending",
    "create with identifier pending",
    "without asin",
    "without sku",
    "no asin",
    "no sku",
    "asin later",
    "sku later",
    "identifiers later",
    "without identifiers",
    "no identifiers",
    "skip asin",
    "skip sku",
)

_SMALLTALK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^(?:hi|hello|hey|yo)\b.*$"),
    re.compile(r"^(?:you there|are you there)\??$"),
    re.compile(r"^(?:how are you|what's up|whats up)\??$"),
    re.compile(r"^(?:thanks|thank you|thx)[.!]?$"),
)

_WORKFLOW_HINTS: tuple[str, ...] = (
    "task",
    "create",
    "coupon",
    "asin",
    "sku",
    "listing",
    "product",
    "promo",
    "campaign",
    "client",
    "brand",
    "distex",
    "thorinox",
)

_ASIN_FOLLOWUP_HINTS: tuple[str, ...] = (
    "asin",
    "sku",
    "identifier",
    "coupon",
    "promo",
    "listing",
    "product",
    "for ",
    "thorinox",
)


def _normalize(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _matches_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(p.match(text) for p in patterns)


def _contains_any(text: str, values: tuple[str, ...]) -> bool:
    return any(v in text for v in values)


def _has_create_intent(text: str) -> bool:
    return _contains_any(text, ("create", "proceed", "go ahead", "do it", "ship it"))


def _is_proceed_with_asin_pending(text: str) -> bool:
    if _contains_any(text, _DEFER_ASIN_CUES):
        return True
    if _has_create_intent(text) and _contains_any(text, ("asin", "sku", "identifier")):
        return _contains_any(text, ("pending", "later", "without", "no ", "skip"))
    return False


def _is_smalltalk_or_general(text: str) -> bool:
    if _matches_any(text, _SMALLTALK_PATTERNS):
        return True
    if text.endswith("?") and not _contains_any(text, _WORKFLOW_HINTS):
        return True
    return False


def _is_asin_followup_like(text: str) -> bool:
    return _contains_any(text, _ASIN_FOLLOWUP_HINTS)


def resolve_pending_action(
    *,
    awaiting: str,
    text: str,
    known_intent: str,
    has_identifier: bool,
) -> PendingResolution:
    """Resolve a pending-state message into a typed action.

    ``known_intent`` should be the output intent from the top-level classifier.
    Non-help intents interrupt pending state, except ``confirm_draft_task``
    which is considered a valid continuation inside confirm/ASIN states.
    """
    t = _normalize(text)

    if _matches_any(t, _CANCEL_PATTERNS):
        return PendingResolution(action="cancel", reason="explicit_cancel")

    if awaiting == "confirm_or_details":
        if known_intent not in {"help", "confirm_draft_task"}:
            return PendingResolution(action="interrupt", reason="known_intent")
        if _is_proceed_with_asin_pending(t):
            return PendingResolution(action="proceed_with_asin_pending", reason="explicit_asin_deferral")
        if _matches_any(t, _PROCEED_DRAFT_PATTERNS):
            return PendingResolution(action="proceed_draft", reason="explicit_proceed")
        if _is_smalltalk_or_general(t):
            return PendingResolution(action="off_topic", reason="smalltalk_or_general")
        return PendingResolution(action="provide_details", reason="default_details")

    if awaiting == "asin_or_pending":
        if known_intent not in {"help", "confirm_draft_task"}:
            return PendingResolution(action="interrupt", reason="known_intent")
        if has_identifier:
            return PendingResolution(action="provide_identifier", reason="identifier_present")
        if _is_proceed_with_asin_pending(t):
            return PendingResolution(action="proceed_with_asin_pending", reason="explicit_asin_deferral")
        if _is_smalltalk_or_general(t):
            return PendingResolution(action="off_topic", reason="smalltalk_or_general")
        if _is_asin_followup_like(t):
            return PendingResolution(action="reask", reason="asin_followup_without_identifier")
        return PendingResolution(action="off_topic", reason="non_asin_offtopic")

    return PendingResolution(action="reask", reason="unknown_state")
