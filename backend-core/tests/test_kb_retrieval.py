"""Tests for C10C: KB retrieval cascade.

Covers:
- Tier 1 (SOP): exact category match, alias match, empty content skip
- Tier 2 (internal): keyword overlap search
- Tier 3 (similar tasks): client+skill query, skipped when no client
- Context cap enforcement
- Deterministic output
- Tier metadata (tiers_searched, tiers_hit)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.services.agencyclaw.kb_retrieval import (
    DEFAULT_MAX_CHARS,
    RetrievalResult,
    SourceTier,
    _enforce_char_cap,
    _extract_keywords,
    retrieve_kb_context,
)


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _make_sop_row(
    *,
    category: str = "ngram",
    name: str = "N-gram Analysis",
    content_md: str = "Step 1: open report\nStep 2: review",
    aliases: list[str] | None = None,
    row_id: str = "sop-1",
) -> dict[str, Any]:
    return {
        "id": row_id,
        "name": name,
        "category": category,
        "content_md": content_md,
        "aliases": aliases or [],
    }


def _make_task_row(
    *,
    task_id: str = "task-1",
    clickup_task_id: str = "CU123",
    skill_invoked: str = "clickup_task_create",
    status: str = "success",
    created_at: str = "2026-02-15T12:00:00Z",
) -> dict[str, Any]:
    return {
        "id": task_id,
        "clickup_task_id": clickup_task_id,
        "skill_invoked": skill_invoked,
        "source_reference": f"ref-{task_id}",
        "status": status,
        "created_at": created_at,
    }


def _mock_db(
    *,
    sop_rows: list[dict] | None = None,
    task_rows: list[dict] | None = None,
    sop_category_row: dict | None = None,
) -> MagicMock:
    """Build a mock Supabase client with configurable table responses.

    - playbook_sops: returns sop_rows for full-table queries, sop_category_row for eq(category) queries
    - agent_tasks: returns task_rows
    """
    db = MagicMock()

    # --- playbook_sops mock ---
    sop_table = MagicMock()

    def _sop_select(*args, **kwargs):
        chain = MagicMock()

        # eq("category", ...) → category-filtered response
        def _eq(col, val):
            eq_chain = MagicMock()
            limit_chain = MagicMock()
            resp = MagicMock()
            if sop_category_row and sop_category_row.get("category") == val:
                resp.data = [sop_category_row]
            else:
                resp.data = []
            limit_chain.execute.return_value = resp
            eq_chain.limit.return_value = limit_chain
            return eq_chain

        chain.eq = _eq

        # Full table scan (no eq) → all sop_rows
        resp_all = MagicMock()
        resp_all.data = sop_rows or []
        chain.execute.return_value = resp_all

        return chain

    sop_table.select = _sop_select

    # --- agent_tasks mock ---
    task_table = MagicMock()

    def _task_select(*args, **kwargs):
        chain = MagicMock()
        # Chain eq calls
        chain.eq.return_value = chain
        # order + limit
        order_chain = MagicMock()
        limit_chain = MagicMock()
        resp = MagicMock()
        resp.data = task_rows or []
        limit_chain.execute.return_value = resp
        order_chain.limit.return_value = limit_chain
        chain.order.return_value = order_chain
        return chain

    task_table.select = _task_select

    def _table_dispatch(name):
        if name == "playbook_sops":
            return sop_table
        if name == "agent_tasks":
            return task_table
        return MagicMock()

    db.table = _table_dispatch
    return db


# ---------------------------------------------------------------------------
# Tier 1: SOP
# ---------------------------------------------------------------------------


class TestSopRetrieval:
    @pytest.mark.asyncio
    async def test_sop_exact_category_match(self):
        row = _make_sop_row(category="ngram")
        db = _mock_db(sop_category_row=row, sop_rows=[row])
        result = await retrieve_kb_context(query="ngram", db=db)

        assert len(result["sources"]) >= 1
        sop = result["sources"][0]
        assert sop["tier"] == SourceTier.SOP
        assert sop["confidence"] == 0.9
        assert "ngram" in sop["source_id"].lower() or "ngram" in sop["meta"].get("category", "")

    @pytest.mark.asyncio
    async def test_sop_alias_match(self):
        row = _make_sop_row(category="ngram", aliases=["n-gram analysis", "ngram report"])
        db = _mock_db(sop_rows=[row])  # No category match, alias match
        result = await retrieve_kb_context(query="n-gram analysis", db=db)

        assert len(result["sources"]) >= 1
        sop = result["sources"][0]
        assert sop["tier"] == SourceTier.SOP
        assert sop["confidence"] == 0.7
        assert sop["meta"]["match_type"] == "alias"

    @pytest.mark.asyncio
    async def test_sop_dominates_ranking(self):
        """SOP source should sort first even when other tiers present."""
        sop_row = _make_sop_row(category="ngram")
        task_row = _make_task_row()
        db = _mock_db(sop_category_row=sop_row, sop_rows=[sop_row], task_rows=[task_row])
        result = await retrieve_kb_context(query="ngram", client_id="c1", db=db)

        assert result["sources"][0]["tier"] == SourceTier.SOP

    @pytest.mark.asyncio
    async def test_sop_empty_content_skipped(self):
        """SOP with empty content_md should not produce a source."""
        row = _make_sop_row(category="ngram", content_md="")
        db = _mock_db(sop_category_row=row, sop_rows=[row])
        result = await retrieve_kb_context(query="ngram", db=db)

        sop_sources = [s for s in result["sources"] if s["tier"] == SourceTier.SOP]
        assert len(sop_sources) == 0


# ---------------------------------------------------------------------------
# Tier 2: Internal docs
# ---------------------------------------------------------------------------


class TestInternalDocsRetrieval:
    @pytest.mark.asyncio
    async def test_internal_docs_keyword_match(self):
        """When no SOP exact match, keyword overlap finds related docs."""
        row = _make_sop_row(category="coupons", name="Coupon Setup Guide", content_md="Guide for coupon setup flow")
        db = _mock_db(sop_rows=[row])  # No category match for "setup coupons"
        result = await retrieve_kb_context(query="setup coupons", db=db)

        internal = [s for s in result["sources"] if s["tier"] == SourceTier.INTERNAL]
        assert len(internal) >= 1
        assert "coupons" in internal[0]["source_id"].lower() or "coupon" in internal[0]["title"].lower()

    @pytest.mark.asyncio
    async def test_internal_docs_not_searched_when_sop_hit(self):
        """Tier 2 should not add internal sources when Tier 1 SOP matched."""
        row = _make_sop_row(category="ngram", content_md="SOP content here")
        db = _mock_db(sop_category_row=row, sop_rows=[row])
        result = await retrieve_kb_context(query="ngram", db=db)

        internal = [s for s in result["sources"] if s["tier"] == SourceTier.INTERNAL]
        assert len(internal) == 0


# ---------------------------------------------------------------------------
# Tier 3: Similar tasks
# ---------------------------------------------------------------------------


class TestSimilarTasksRetrieval:
    @pytest.mark.asyncio
    async def test_similar_tasks_fallback(self):
        """When no SOP/docs, agent_tasks matches produce similar_task source."""
        task_rows = [_make_task_row(task_id=f"t{i}") for i in range(3)]
        db = _mock_db(task_rows=task_rows)
        result = await retrieve_kb_context(query="something unknown", client_id="c1", db=db)

        similar = [s for s in result["sources"] if s["tier"] == SourceTier.SIMILAR_TASK]
        assert len(similar) == 1
        assert similar[0]["confidence"] == 0.4
        assert similar[0]["meta"]["task_count"] == 3

    @pytest.mark.asyncio
    async def test_client_id_none_skips_similar_tasks(self):
        """No client_id → tier 3 not queried."""
        task_rows = [_make_task_row()]
        db = _mock_db(task_rows=task_rows)
        result = await retrieve_kb_context(query="something", client_id=None, db=db)

        similar = [s for s in result["sources"] if s["tier"] == SourceTier.SIMILAR_TASK]
        assert len(similar) == 0


# ---------------------------------------------------------------------------
# No evidence
# ---------------------------------------------------------------------------


class TestNoEvidence:
    @pytest.mark.asyncio
    async def test_no_evidence_returns_empty(self):
        db = _mock_db()
        result = await retrieve_kb_context(query="completely unknown thing", db=db)

        assert result["sources"] == []
        assert result["overall_confidence"] == 0.0


# ---------------------------------------------------------------------------
# Context cap
# ---------------------------------------------------------------------------


class TestContextCap:
    @pytest.mark.asyncio
    async def test_context_cap_enforced(self):
        """Total content chars should not exceed max_chars."""
        long_content = "x" * 10000
        row = _make_sop_row(category="ngram", content_md=long_content)
        db = _mock_db(sop_category_row=row, sop_rows=[row])
        result = await retrieve_kb_context(query="ngram", db=db, max_chars=500)

        assert result["total_chars"] <= 500

    @pytest.mark.asyncio
    async def test_context_cap_truncates_last_source(self):
        """Last source should be truncated (not dropped) when partially fits."""
        content = "a" * 1000
        row = _make_sop_row(category="ngram", content_md=content)
        db = _mock_db(sop_category_row=row, sop_rows=[row])
        result = await retrieve_kb_context(query="ngram", db=db, max_chars=500)

        assert len(result["sources"]) == 1
        assert len(result["sources"][0]["content"]) == 500

    def test_enforce_char_cap_unit(self):
        """Unit test for _enforce_char_cap directly."""
        sources = [
            {"tier": "sop", "source_id": "a", "title": "A", "content": "x" * 300, "confidence": 0.9, "meta": {}},
            {"tier": "internal", "source_id": "b", "title": "B", "content": "y" * 300, "confidence": 0.5, "meta": {}},
        ]
        result = _enforce_char_cap(sources, 500)
        total = sum(len(s["content"]) for s in result)
        assert total <= 500
        assert len(result) == 2
        assert len(result[1]["content"]) == 200  # truncated


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


class TestMetadata:
    @pytest.mark.asyncio
    async def test_tiers_searched_and_hit(self):
        row = _make_sop_row(category="ngram")
        db = _mock_db(sop_category_row=row, sop_rows=[row])
        result = await retrieve_kb_context(query="ngram", db=db)

        assert SourceTier.SOP in result["tiers_searched"]
        assert SourceTier.INTERNAL in result["tiers_searched"]
        assert SourceTier.SIMILAR_TASK in result["tiers_searched"]
        assert SourceTier.EXTERNAL in result["tiers_searched"]
        assert SourceTier.SOP in result["tiers_hit"]

    @pytest.mark.asyncio
    async def test_deterministic_output(self):
        """Same inputs → same output."""
        row = _make_sop_row(category="ngram")
        db = _mock_db(sop_category_row=row, sop_rows=[row])

        r1 = await retrieve_kb_context(query="ngram", db=db)
        r2 = await retrieve_kb_context(query="ngram", db=db)

        assert r1["sources"] == r2["sources"]
        assert r1["overall_confidence"] == r2["overall_confidence"]
        assert r1["total_chars"] == r2["total_chars"]


# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------


class TestKeywordExtraction:
    def test_extracts_meaningful_words(self):
        assert _extract_keywords("setup coupons for store") == ["setup", "coupons", "for", "store"]

    def test_filters_short_words(self):
        result = _extract_keywords("do it")
        assert "do" not in result
        assert "it" not in result
