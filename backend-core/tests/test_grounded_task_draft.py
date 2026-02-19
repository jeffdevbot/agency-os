"""Tests for C10C: Grounded task draft builder.

Covers:
- SOP source → description with "Per SOP:", checklist extraction, citation
- Internal doc → description with doc name
- Similar tasks only → needs_clarification=True
- No evidence → needs_clarification=True, confidence=0.0
- Deterministic output
- Title passthrough
- Confidence reflects retrieval
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services.agencyclaw.grounded_task_draft import (
    DraftResult,
    _extract_checklist,
    build_grounded_task_draft,
)
from app.services.agencyclaw.kb_retrieval import RetrievalResult, RetrievedSource, SourceTier


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _retrieval(
    sources: list[RetrievedSource],
    overall_confidence: float | None = None,
) -> RetrievalResult:
    """Build a RetrievalResult from source list."""
    if overall_confidence is None:
        overall_confidence = max((s["confidence"] for s in sources), default=0.0)
    tiers_hit = list({s["tier"] for s in sources})
    return RetrievalResult(
        sources=sources,
        overall_confidence=overall_confidence,
        total_chars=sum(len(s["content"]) for s in sources),
        tiers_searched=[SourceTier.SOP, SourceTier.INTERNAL, SourceTier.SIMILAR_TASK, SourceTier.EXTERNAL],
        tiers_hit=tiers_hit,
    )


def _sop_source(
    content: str = "1. Open report\n2. Review data\n3. Export results",
    name: str = "N-gram Analysis",
    source_id: str = "ngram",
    confidence: float = 0.9,
) -> RetrievedSource:
    return RetrievedSource(
        tier=SourceTier.SOP,
        source_id=source_id,
        title=name,
        content=content,
        confidence=confidence,
        meta={"match_type": "category", "category": source_id},
    )


def _internal_source(
    content: str = "Guide for coupon workflows",
    name: str = "Coupon Setup Guide",
    source_id: str = "coupons",
) -> RetrievedSource:
    return RetrievedSource(
        tier=SourceTier.INTERNAL,
        source_id=source_id,
        title=name,
        content=content,
        confidence=0.5,
        meta={"category": source_id},
    )


def _similar_source(
    content: str = "- Task CU123 (clickup_task_create) created 2026-02-15",
    title: str = "Recent tasks (1)",
) -> RetrievedSource:
    return RetrievedSource(
        tier=SourceTier.SIMILAR_TASK,
        source_id="agent_tasks:c1",
        title=title,
        content=content,
        confidence=0.4,
        meta={"task_count": 1, "client_id": "c1"},
    )


def _empty_retrieval() -> RetrievalResult:
    return _retrieval([], overall_confidence=0.0)


# ---------------------------------------------------------------------------
# SOP source tests
# ---------------------------------------------------------------------------


class TestSopDraft:
    def test_sop_source_produces_description(self):
        ctx = _retrieval([_sop_source()])
        draft = build_grounded_task_draft(
            request_text="run ngram",
            client_name="Distex",
            retrieved_context=ctx,
            task_title="N-gram analysis for Distex",
        )

        assert draft["description"].startswith("Per SOP:")
        assert "N-gram Analysis" in draft["description"]
        assert draft["needs_clarification"] is False

    def test_sop_checklist_extraction(self):
        content = "1. Open report\n2. Review data\n3. Export results"
        ctx = _retrieval([_sop_source(content=content)])
        draft = build_grounded_task_draft(
            request_text="run ngram",
            client_name="Distex",
            retrieved_context=ctx,
        )

        assert len(draft["checklist"]) == 3
        assert "Open report" in draft["checklist"][0]
        assert "Export results" in draft["checklist"][2]

    def test_sop_checklist_empty_for_prose(self):
        content = "This is a prose description with no numbered steps or bullets."
        ctx = _retrieval([_sop_source(content=content)])
        draft = build_grounded_task_draft(
            request_text="run ngram",
            client_name="Distex",
            retrieved_context=ctx,
        )

        assert draft["checklist"] == []

    def test_citation_present_for_sop(self):
        ctx = _retrieval([_sop_source()])
        draft = build_grounded_task_draft(
            request_text="run ngram",
            client_name="Distex",
            retrieved_context=ctx,
        )

        assert len(draft["citations"]) == 1
        c = draft["citations"][0]
        assert c["source_id"] == "ngram"
        assert c["title"] == "N-gram Analysis"
        assert c["tier"] == SourceTier.SOP

    def test_sop_checklist_with_bullets(self):
        content = "- Check inventory levels\n- Review pricing\n* Update listings"
        ctx = _retrieval([_sop_source(content=content)])
        draft = build_grounded_task_draft(
            request_text="review",
            client_name="Distex",
            retrieved_context=ctx,
        )

        assert len(draft["checklist"]) == 3


# ---------------------------------------------------------------------------
# Internal doc tests
# ---------------------------------------------------------------------------


class TestInternalDocDraft:
    def test_internal_doc_source(self):
        ctx = _retrieval([_internal_source()])
        draft = build_grounded_task_draft(
            request_text="setup coupons",
            client_name="Distex",
            retrieved_context=ctx,
        )

        assert "Related doc:" in draft["description"]
        assert "Coupon Setup Guide" in draft["description"]
        assert draft["needs_clarification"] is False

    def test_internal_doc_citation(self):
        ctx = _retrieval([_internal_source()])
        draft = build_grounded_task_draft(
            request_text="setup coupons",
            client_name="Distex",
            retrieved_context=ctx,
        )

        assert len(draft["citations"]) == 1
        assert draft["citations"][0]["tier"] == SourceTier.INTERNAL


# ---------------------------------------------------------------------------
# Similar tasks tests
# ---------------------------------------------------------------------------


class TestSimilarTasksDraft:
    def test_similar_tasks_needs_clarification(self):
        ctx = _retrieval([_similar_source()])
        draft = build_grounded_task_draft(
            request_text="create task",
            client_name="Distex",
            retrieved_context=ctx,
        )

        assert draft["needs_clarification"] is True
        assert "similar tasks" in draft["clarification_question"].lower()

    def test_similar_tasks_description_includes_client(self):
        ctx = _retrieval([_similar_source()])
        draft = build_grounded_task_draft(
            request_text="create task",
            client_name="Distex",
            retrieved_context=ctx,
        )

        assert "Distex" in draft["description"]


# ---------------------------------------------------------------------------
# No evidence tests
# ---------------------------------------------------------------------------


class TestNoEvidenceDraft:
    def test_no_evidence_needs_clarification(self):
        ctx = _empty_retrieval()
        draft = build_grounded_task_draft(
            request_text="do something",
            client_name="Distex",
            retrieved_context=ctx,
        )

        assert draft["needs_clarification"] is True
        assert draft["confidence"] == 0.0

    def test_no_evidence_clarification_question(self):
        ctx = _empty_retrieval()
        draft = build_grounded_task_draft(
            request_text="do something",
            client_name="Distex",
            retrieved_context=ctx,
        )

        assert draft["clarification_question"] is not None
        assert len(draft["clarification_question"]) > 0

    def test_no_evidence_empty_citations(self):
        ctx = _empty_retrieval()
        draft = build_grounded_task_draft(
            request_text="do something",
            client_name="Distex",
            retrieved_context=ctx,
        )

        assert draft["citations"] == []
        assert draft["checklist"] == []


# ---------------------------------------------------------------------------
# General behavior tests
# ---------------------------------------------------------------------------


class TestDraftGeneral:
    def test_deterministic_output(self):
        ctx = _retrieval([_sop_source()])
        d1 = build_grounded_task_draft(
            request_text="run ngram",
            client_name="Distex",
            retrieved_context=ctx,
            task_title="Ngram task",
        )
        d2 = build_grounded_task_draft(
            request_text="run ngram",
            client_name="Distex",
            retrieved_context=ctx,
            task_title="Ngram task",
        )

        assert d1 == d2

    def test_title_passthrough(self):
        ctx = _retrieval([_sop_source()])
        draft = build_grounded_task_draft(
            request_text="run ngram",
            client_name="Distex",
            retrieved_context=ctx,
            task_title="Custom title here",
        )

        assert draft["title"] == "Custom title here"

    def test_title_defaults_to_request_text(self):
        ctx = _retrieval([_sop_source()])
        draft = build_grounded_task_draft(
            request_text="run ngram for Distex",
            client_name="Distex",
            retrieved_context=ctx,
        )

        assert draft["title"] == "run ngram for Distex"

    def test_confidence_reflects_retrieval(self):
        ctx = _retrieval([_sop_source(confidence=0.85)], overall_confidence=0.85)
        draft = build_grounded_task_draft(
            request_text="run ngram",
            client_name="Distex",
            retrieved_context=ctx,
        )

        assert draft["confidence"] == 0.85

    def test_source_tiers_used(self):
        ctx = _retrieval([_sop_source(), _similar_source()])
        draft = build_grounded_task_draft(
            request_text="run ngram",
            client_name="Distex",
            retrieved_context=ctx,
        )

        assert SourceTier.SOP in draft["source_tiers_used"]
        assert SourceTier.SIMILAR_TASK in draft["source_tiers_used"]


# ---------------------------------------------------------------------------
# Checklist extraction unit tests
# ---------------------------------------------------------------------------


class TestChecklistExtraction:
    def test_numbered_steps(self):
        content = "1. First step\n2. Second step\n3. Third step"
        assert _extract_checklist(content) == ["First step", "Second step", "Third step"]

    def test_bulleted_steps(self):
        content = "- First step\n- Second step"
        assert _extract_checklist(content) == ["First step", "Second step"]

    def test_mixed_steps(self):
        content = "1. Numbered\n- Bulleted\n* Star bullet"
        assert len(_extract_checklist(content)) == 3

    def test_no_steps_in_prose(self):
        content = "This is just plain text with no structure."
        assert _extract_checklist(content) == []

    def test_deduplication(self):
        content = "1. Same step\n2. Same step\n3. Different step"
        result = _extract_checklist(content)
        assert result == ["Same step", "Different step"]
