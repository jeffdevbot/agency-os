"""C10C: Tiered KB retrieval cascade for AgencyClaw.

Gathers evidence from multiple source tiers (SOP, internal docs, similar
historical tasks) and returns a structured, confidence-scored result within
a hard character budget.

All DB queries use the sync Supabase client wrapped in ``asyncio.to_thread``.
"""

from __future__ import annotations

import asyncio
import logging
import re
from enum import Enum
from typing import Any, TypedDict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class SourceTier(str, Enum):
    SOP = "sop"
    INTERNAL = "internal"
    SIMILAR_TASK = "similar_task"
    EXTERNAL = "external"


class RetrievedSource(TypedDict):
    tier: str
    source_id: str
    title: str
    content: str
    confidence: float
    meta: dict[str, Any]


class RetrievalResult(TypedDict):
    sources: list[RetrievedSource]
    overall_confidence: float
    total_chars: int
    tiers_searched: list[str]
    tiers_hit: list[str]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MAX_CHARS = 6000
_KEYWORD_PREVIEW_CHARS = 500  # chars of content_md to scan for keyword match
_MIN_KEYWORD_LEN = 3  # ignore very short keywords
_MAX_INTERNAL_RESULTS = 2
_MAX_SIMILAR_TASKS = 5


# ---------------------------------------------------------------------------
# Tier 1: SOP exact match (category / alias)
# ---------------------------------------------------------------------------


def _search_sop_category_sync(db: Any, query: str) -> dict[str, Any] | None:
    """Exact category match on playbook_sops."""
    normalized = query.strip().lower().replace(" ", "_")
    if not normalized:
        return None
    resp = (
        db.table("playbook_sops")
        .select("id, name, category, content_md, aliases")
        .eq("category", normalized)
        .limit(1)
        .execute()
    )
    rows = resp.data if isinstance(resp.data, list) else []
    return rows[0] if rows and isinstance(rows[0], dict) else None


def _search_sop_alias_sync(db: Any, query: str) -> dict[str, Any] | None:
    """Alias match on playbook_sops (Python scan, same as SOPSyncService)."""
    alias_norm = " ".join(query.strip().lower().split())
    if not alias_norm:
        return None
    resp = db.table("playbook_sops").select("id, name, category, content_md, aliases").execute()
    rows = resp.data if isinstance(resp.data, list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        aliases = row.get("aliases")
        if not isinstance(aliases, list):
            continue
        for candidate in aliases:
            if not isinstance(candidate, str):
                continue
            if " ".join(candidate.strip().lower().split()) == alias_norm:
                return row
    return None


async def _tier_sop(db: Any, query: str) -> list[RetrievedSource]:
    """Tier 1: exact SOP category or alias match."""
    # Try category first
    row = await asyncio.to_thread(_search_sop_category_sync, db, query)
    if row:
        content = row.get("content_md") or ""
        if not content.strip():
            return []
        return [RetrievedSource(
            tier=SourceTier.SOP,
            source_id=str(row.get("category") or row.get("id", "")),
            title=str(row.get("name") or row.get("category", "")),
            content=content,
            confidence=0.9,
            meta={"match_type": "category", "category": row.get("category")},
        )]

    # Fallback to alias
    row = await asyncio.to_thread(_search_sop_alias_sync, db, query)
    if row:
        content = row.get("content_md") or ""
        if not content.strip():
            return []
        return [RetrievedSource(
            tier=SourceTier.SOP,
            source_id=str(row.get("category") or row.get("id", "")),
            title=str(row.get("name") or row.get("category", "")),
            content=content,
            confidence=0.7,
            meta={"match_type": "alias", "category": row.get("category")},
        )]

    return []


# ---------------------------------------------------------------------------
# Tier 2: Internal docs (keyword overlap in playbook_sops)
# ---------------------------------------------------------------------------


def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from query text."""
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return [w for w in words if len(w) >= _MIN_KEYWORD_LEN]


def _search_internal_docs_sync(db: Any, query: str) -> list[dict[str, Any]]:
    """Keyword overlap search across playbook_sops name/content."""
    keywords = _extract_keywords(query)
    if not keywords:
        return []

    resp = db.table("playbook_sops").select("id, name, category, content_md").execute()
    rows = resp.data if isinstance(resp.data, list) else []

    scored: list[tuple[int, dict[str, Any]]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name_lower = (row.get("name") or "").lower()
        content_preview = (row.get("content_md") or "")[:_KEYWORD_PREVIEW_CHARS].lower()
        searchable = name_lower + " " + content_preview
        hits = sum(1 for kw in keywords if kw in searchable)
        if hits > 0:
            scored.append((hits, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [row for _, row in scored[:_MAX_INTERNAL_RESULTS]]


async def _tier_internal(db: Any, query: str) -> list[RetrievedSource]:
    """Tier 2: keyword-overlap search across playbook_sops."""
    rows = await asyncio.to_thread(_search_internal_docs_sync, db, query)
    sources: list[RetrievedSource] = []
    for row in rows:
        content = row.get("content_md") or ""
        if not content.strip():
            continue
        sources.append(RetrievedSource(
            tier=SourceTier.INTERNAL,
            source_id=str(row.get("category") or row.get("id", "")),
            title=str(row.get("name") or row.get("category", "")),
            content=content,
            confidence=0.5,
            meta={"category": row.get("category")},
        ))
    return sources


# ---------------------------------------------------------------------------
# Tier 3: Similar historical tasks (agent_tasks)
# ---------------------------------------------------------------------------


def _search_similar_tasks_sync(
    db: Any,
    client_id: str,
    skill_id: str | None,
) -> list[dict[str, Any]]:
    """Find recent successful agent_tasks for same client+skill."""
    q = (
        db.table("agent_tasks")
        .select("id, clickup_task_id, skill_invoked, source_reference, status, created_at")
        .eq("client_id", client_id)
        .eq("status", "success")
    )
    if skill_id:
        q = q.eq("skill_invoked", skill_id)
    resp = q.order("created_at", desc=True).limit(_MAX_SIMILAR_TASKS).execute()
    rows = resp.data if isinstance(resp.data, list) else []
    return [r for r in rows if isinstance(r, dict)]


async def _tier_similar_tasks(
    db: Any,
    client_id: str | None,
    skill_id: str | None,
) -> list[RetrievedSource]:
    """Tier 3: similar historical tasks by client + skill."""
    if not client_id:
        return []

    rows = await asyncio.to_thread(_search_similar_tasks_sync, db, client_id, skill_id)
    if not rows:
        return []

    # Build lightweight summary as a single source
    lines: list[str] = []
    for row in rows:
        task_id = row.get("clickup_task_id") or row.get("id", "?")
        skill = row.get("skill_invoked") or "unknown"
        created = str(row.get("created_at") or "")[:10]
        lines.append(f"- Task {task_id} ({skill}) created {created}")

    return [RetrievedSource(
        tier=SourceTier.SIMILAR_TASK,
        source_id=f"agent_tasks:{client_id}",
        title=f"Recent tasks ({len(rows)})",
        content="\n".join(lines),
        confidence=0.4,
        meta={"task_count": len(rows), "client_id": client_id},
    )]


# ---------------------------------------------------------------------------
# Context cap enforcement
# ---------------------------------------------------------------------------


def _enforce_char_cap(sources: list[RetrievedSource], max_chars: int) -> list[RetrievedSource]:
    """Enforce hard character cap on total content. Sources must be pre-sorted by confidence."""
    if max_chars <= 0:
        return []

    result: list[RetrievedSource] = []
    remaining = max_chars

    for src in sources:
        content = src["content"]
        if remaining <= 0:
            break
        if len(content) <= remaining:
            result.append(src)
            remaining -= len(content)
        else:
            # Truncate last source to fit
            truncated = dict(src)
            truncated["content"] = content[:remaining]
            result.append(truncated)  # type: ignore[arg-type]
            remaining = 0

    return result


# ---------------------------------------------------------------------------
# Main retrieval function
# ---------------------------------------------------------------------------


async def retrieve_kb_context(
    *,
    query: str,
    client_id: str | None = None,
    skill_id: str | None = None,
    db: Any,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> RetrievalResult:
    """Run tiered retrieval cascade and return structured result.

    Tiers evaluated in order:
    1. SOP exact match (category/alias)
    2. Internal docs (keyword overlap)
    3. Similar historical tasks
    4. External (placeholder — always empty)
    """
    all_sources: list[RetrievedSource] = []
    tiers_searched: list[str] = []
    tiers_hit: list[str] = []

    # --- Tier 1: SOP ---
    tiers_searched.append(SourceTier.SOP)
    try:
        sop_sources = await _tier_sop(db, query)
        if sop_sources:
            all_sources.extend(sop_sources)
            tiers_hit.append(SourceTier.SOP)
    except Exception:
        logger.warning("C10C: Tier 1 (SOP) retrieval failed", exc_info=True)

    # --- Tier 2: Internal docs (only if no SOP hit) ---
    tiers_searched.append(SourceTier.INTERNAL)
    if not any(s["tier"] == SourceTier.SOP for s in all_sources):
        try:
            internal_sources = await _tier_internal(db, query)
            if internal_sources:
                all_sources.extend(internal_sources)
                tiers_hit.append(SourceTier.INTERNAL)
        except Exception:
            logger.warning("C10C: Tier 2 (internal) retrieval failed", exc_info=True)

    # --- Tier 3: Similar tasks ---
    tiers_searched.append(SourceTier.SIMILAR_TASK)
    try:
        task_sources = await _tier_similar_tasks(db, client_id, skill_id)
        if task_sources:
            all_sources.extend(task_sources)
            tiers_hit.append(SourceTier.SIMILAR_TASK)
    except Exception:
        logger.warning("C10C: Tier 3 (similar tasks) retrieval failed", exc_info=True)

    # --- Tier 4: External (placeholder) ---
    tiers_searched.append(SourceTier.EXTERNAL)

    # Sort by confidence descending for cap enforcement
    all_sources.sort(key=lambda s: s["confidence"], reverse=True)

    # Enforce character cap
    capped = _enforce_char_cap(all_sources, max_chars)

    total_chars = sum(len(s["content"]) for s in capped)
    overall_confidence = max((s["confidence"] for s in capped), default=0.0)

    return RetrievalResult(
        sources=capped,
        overall_confidence=overall_confidence,
        total_chars=total_chars,
        tiers_searched=tiers_searched,
        tiers_hit=tiers_hit,
    )
