"""C10C: Evidence-grounded task draft builder for AgencyClaw.

Produces structured task drafts (title, description, checklist, citations)
from retrieval results.  Pure function — no LLM call, no DB access.
Deterministic: same inputs always produce the same output.

Rules:
- If evidence is weak or absent, ``needs_clarification=True``
- Citations always reflect which source tier produced the draft
- Checklist extraction is regex-based (numbered/bulleted lines)
"""

from __future__ import annotations

import re
from typing import Any, TypedDict

from .kb_retrieval import RetrievalResult, SourceTier

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class DraftCitation(TypedDict):
    source_id: str
    title: str
    tier: str


class DraftResult(TypedDict):
    title: str
    description: str
    checklist: list[str]
    citations: list[DraftCitation]
    confidence: float
    needs_clarification: bool
    clarification_question: str | None
    open_questions: list[str]
    source_tiers_used: list[str]


# ---------------------------------------------------------------------------
# Checklist extraction
# ---------------------------------------------------------------------------

# Matches lines like "1. Do something" or "- Do something" or "* Do something"
_STEP_PATTERN = re.compile(r"^\s*(?:\d+\.\s+|[-*]\s+)(.+)$", re.MULTILINE)


def _extract_checklist(content: str) -> list[str]:
    """Extract step items from markdown-ish content."""
    matches = _STEP_PATTERN.findall(content)
    # Deduplicate while preserving order
    seen: set[str] = set()
    steps: list[str] = []
    for m in matches:
        stripped = m.strip()
        if stripped and stripped not in seen:
            seen.add(stripped)
            steps.append(stripped)
    return steps


# ---------------------------------------------------------------------------
# C10C.1: Product-scope detection
# ---------------------------------------------------------------------------

_PRODUCT_SCOPE_KEYWORDS = frozenset({
    "coupon", "coupons", "discount", "discounts",
    "listing", "listings", "catalog",
    "product", "products", "sku", "asin",
})

_ASIN_RE = re.compile(r"\b[A-Z0-9]{10}\b")
_SKU_RE = re.compile(r"\b[A-Z0-9][-A-Z0-9]{3,18}[A-Z0-9]\b")


_WORD_RE = re.compile(r"\w+")


def _is_product_scoped(text: str) -> bool:
    """Return True if request text involves product-level operations."""
    words = set(w.lower() for w in _WORD_RE.findall(text))
    return bool(words & _PRODUCT_SCOPE_KEYWORDS)


def _has_product_identifier(text: str) -> bool:
    """Return True if text contains at least one ASIN or SKU-like identifier."""
    return bool(_ASIN_RE.search(text)) or bool(_SKU_RE.search(text))


_ASIN_OPEN_QUESTION = "ASIN(s) or SKU(s) required for this product-scoped task."
_ASIN_CLARIFICATION = (
    "This looks like a product-level task but no ASIN/SKU was provided. "
    "Please reply with the ASIN(s) or SKU(s), or say \"create with ASIN pending\"."
)


def _apply_asin_guardrail(
    draft: DraftResult,
    product_scoped: bool,
    has_identifier: bool,
) -> DraftResult:
    """C10C.1: If product-scoped without identifiers, force clarification."""
    if not product_scoped or has_identifier:
        return draft

    draft["needs_clarification"] = True
    draft["open_questions"].append(_ASIN_OPEN_QUESTION)
    draft["clarification_question"] = _ASIN_CLARIFICATION
    return draft


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------


def build_grounded_task_draft(
    *,
    request_text: str,
    client_name: str,
    retrieved_context: RetrievalResult,
    task_title: str | None = None,
    preferences: dict[str, Any] | None = None,
) -> DraftResult:
    """Build a grounded task draft from retrieval results.

    Cases (by highest-confidence source tier):
    1. SOP hit → structured description + checklist + citation
    2. Internal doc → description with excerpt + citation
    3. Similar tasks only → reference list + needs_clarification
    4. No evidence → empty draft + needs_clarification
    """
    title = task_title or request_text
    sources = retrieved_context["sources"]
    overall_confidence = retrieved_context["overall_confidence"]

    # --- C10C.1: detect product-scope for post-processing ---
    product_scoped = _is_product_scoped(request_text)
    has_identifier = _has_product_identifier(request_text) if product_scoped else False

    if not sources:
        draft = DraftResult(
            title=title,
            description="",
            checklist=[],
            citations=[],
            confidence=0.0,
            needs_clarification=True,
            clarification_question=(
                "I don't have an SOP or reference for this task. "
                "Could you provide more details about what needs to be done?"
            ),
            open_questions=[],
            source_tiers_used=[],
        )
        return _apply_asin_guardrail(draft, product_scoped, has_identifier)

    # Find the best source by tier priority
    best_sop = next((s for s in sources if s["tier"] == SourceTier.SOP), None)
    best_internal = next((s for s in sources if s["tier"] == SourceTier.INTERNAL), None)
    best_similar = next((s for s in sources if s["tier"] == SourceTier.SIMILAR_TASK), None)

    tiers_used = list({s["tier"] for s in sources})

    # Case 1: SOP source
    if best_sop:
        sop_name = best_sop["title"]
        content = best_sop["content"]
        checklist = _extract_checklist(content)

        draft = DraftResult(
            title=title,
            description=f"Per SOP: {sop_name}\n\n{content}",
            checklist=checklist,
            citations=[DraftCitation(
                source_id=best_sop["source_id"],
                title=sop_name,
                tier=SourceTier.SOP,
            )],
            confidence=overall_confidence,
            needs_clarification=False,
            clarification_question=None,
            open_questions=[],
            source_tiers_used=tiers_used,
        )
        return _apply_asin_guardrail(draft, product_scoped, has_identifier)

    # Case 2: Internal doc
    if best_internal:
        doc_name = best_internal["title"]
        content = best_internal["content"]

        draft = DraftResult(
            title=title,
            description=f"Related doc: {doc_name}\n\n{content}",
            checklist=[],
            citations=[DraftCitation(
                source_id=best_internal["source_id"],
                title=doc_name,
                tier=SourceTier.INTERNAL,
            )],
            confidence=overall_confidence,
            needs_clarification=False,
            clarification_question=None,
            open_questions=[],
            source_tiers_used=tiers_used,
        )
        return _apply_asin_guardrail(draft, product_scoped, has_identifier)

    # Case 3: Similar tasks only
    if best_similar:
        content = best_similar["content"]
        citations = [DraftCitation(
            source_id=best_similar["source_id"],
            title=best_similar["title"],
            tier=SourceTier.SIMILAR_TASK,
        )]

        draft = DraftResult(
            title=title,
            description=f"Similar recent tasks found for {client_name}:\n{content}",
            checklist=[],
            citations=citations,
            confidence=overall_confidence,
            needs_clarification=True,
            clarification_question=(
                "I found similar tasks but no SOP for this. "
                "Could you describe what steps should be included?"
            ),
            open_questions=[],
            source_tiers_used=tiers_used,
        )
        return _apply_asin_guardrail(draft, product_scoped, has_identifier)

    # Should not reach here (sources is non-empty), but fail safe
    draft = DraftResult(
        title=title,
        description="",
        checklist=[],
        citations=[],
        confidence=0.0,
        needs_clarification=True,
        clarification_question="Could you provide more details about what needs to be done?",
        open_questions=[],
        source_tiers_used=tiers_used,
    )
    return _apply_asin_guardrail(draft, product_scoped, has_identifier)
