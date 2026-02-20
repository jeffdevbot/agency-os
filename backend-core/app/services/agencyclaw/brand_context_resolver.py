"""C11D: Deterministic brand context resolver for AgencyClaw task creation.

Separates two concerns:
1. **Destination resolution** — which ClickUp space/list does the task go to?
2. **Brand context resolution** — which brand is this task for (metadata)?

The resolver is a pure function: takes pre-fetched brand data, returns a
structured result.  No DB access, no side effects, fully testable.

Resolution modes:
- explicit_brand:        brand_hint matched exactly one brand
- clarified_brand:       brand_hint matched via fuzzy/prefix
- client_level:          single brand, or shared destination + non-product request
- ambiguous_brand:       shared dest + product-scoped, or hint matched multiple
- ambiguous_destination: multiple brands with DIFFERENT ClickUp destinations
- no_destination:        no brands have ClickUp mappings
"""

from __future__ import annotations

import re
from typing import Any, Literal, TypedDict


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

ResolutionMode = Literal[
    "explicit_brand",
    "clarified_brand",
    "client_level",
    "ambiguous_brand",
    "ambiguous_destination",
    "no_destination",
]


class BrandResolution(TypedDict):
    mode: ResolutionMode
    destination: dict[str, Any] | None
    brand_context: dict[str, Any] | None
    candidates: list[dict[str, Any]]
    destination_groups: int


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_brand_context(
    brands: list[dict[str, Any]],
    brand_hint: str = "",
    task_text: str = "",
) -> BrandResolution:
    """Resolve brand context and ClickUp destination for a task.

    Args:
        brands: All brands for the client (caller fetches from DB).
        brand_hint: Optional user-provided brand name hint.
        task_text: Combined title + description for product-scope detection.

    Returns:
        BrandResolution with mode, destination, brand_context, and candidates.
    """
    mapped = [
        b for b in brands
        if isinstance(b, dict) and (b.get("clickup_space_id") or b.get("clickup_list_id"))
    ]

    if not mapped:
        return BrandResolution(
            mode="no_destination",
            destination=None,
            brand_context=None,
            candidates=[],
            destination_groups=0,
        )

    # --- Explicit brand hint path ---
    hint = (brand_hint or "").strip()
    if hint:
        matches = _fuzzy_match_brands(mapped, hint)
        if len(matches) == 1:
            brand = matches[0]
            exact = _is_exact_match(brand.get("name", ""), hint)
            return BrandResolution(
                mode="explicit_brand" if exact else "clarified_brand",
                destination=_pick_destination(brand),
                brand_context=_pick_brand_context(brand),
                candidates=matches,
                destination_groups=1,
            )
        if len(matches) > 1:
            return BrandResolution(
                mode="ambiguous_brand",
                destination=None,
                brand_context=None,
                candidates=matches,
                destination_groups=_count_destination_groups(matches),
            )
        # No match — show all mapped brands as candidates
        return BrandResolution(
            mode="ambiguous_brand",
            destination=None,
            brand_context=None,
            candidates=mapped,
            destination_groups=_count_destination_groups(mapped),
        )

    # --- No hint: single mapped brand shortcut ---
    if len(mapped) == 1:
        brand = mapped[0]
        return BrandResolution(
            mode="client_level",
            destination=_pick_destination(brand),
            brand_context=_pick_brand_context(brand),
            candidates=mapped,
            destination_groups=1,
        )

    # --- Multiple mapped brands: group by destination ---
    groups = _group_by_destination(mapped)

    if len(groups) == 1:
        # Shared destination — check product scope
        if _is_product_scoped(task_text):
            return BrandResolution(
                mode="ambiguous_brand",
                destination=None,
                brand_context=None,
                candidates=mapped,
                destination_groups=1,
            )
        # Client-level: destination is unambiguous, brand context is None
        return BrandResolution(
            mode="client_level",
            destination=_pick_destination(mapped[0]),
            brand_context=None,
            candidates=mapped,
            destination_groups=1,
        )

    # Multiple destination groups — must disambiguate
    return BrandResolution(
        mode="ambiguous_destination",
        destination=None,
        brand_context=None,
        candidates=mapped,
        destination_groups=len(groups),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize(name: str) -> str:
    """Lowercase, collapse whitespace, strip."""
    return " ".join(name.strip().lower().split())


def _is_exact_match(brand_name: str, hint: str) -> bool:
    return _normalize(brand_name) == _normalize(hint)


def _fuzzy_match_brands(
    brands: list[dict[str, Any]], hint: str,
) -> list[dict[str, Any]]:
    """Match brands by exact > prefix > contains against hint."""
    norm = _normalize(hint)
    if not norm:
        return []

    exact = [b for b in brands if _normalize(b.get("name", "")) == norm]
    if exact:
        return exact

    prefix = [b for b in brands if _normalize(b.get("name", "")).startswith(norm)]
    if prefix:
        return prefix

    contains = [b for b in brands if norm in _normalize(b.get("name", ""))]
    return contains


def _destination_key(brand: dict[str, Any]) -> tuple[str, str]:
    return (
        str(brand.get("clickup_space_id") or ""),
        str(brand.get("clickup_list_id") or ""),
    )


def _group_by_destination(
    brands: list[dict[str, Any]],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for b in brands:
        key = _destination_key(b)
        groups.setdefault(key, []).append(b)
    return groups


def _count_destination_groups(brands: list[dict[str, Any]]) -> int:
    return len(_group_by_destination(brands))


def _pick_destination(brand: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": brand.get("id"),
        "name": brand.get("name"),
        "clickup_space_id": brand.get("clickup_space_id"),
        "clickup_list_id": brand.get("clickup_list_id"),
    }


def _pick_brand_context(brand: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": brand.get("id"),
        "name": brand.get("name"),
    }


def _is_product_scoped(text: str) -> bool:
    """Check if text involves product-level operations.

    Reuses the keyword set from grounded_task_draft but avoids a circular
    import by inlining the check.
    """
    if not text:
        return False
    _PRODUCT_KEYWORDS = {
        "coupon", "discount", "listing", "catalog", "product",
        "sku", "asin", "promotion", "deal", "price",
    }
    # Tokenize on word boundaries so punctuation/hyphenated phrasing still
    # resolves product scope (e.g. "coupon?", "listing,", "product-level").
    words = set(re.findall(r"\w+", text.lower()))
    return bool(words & _PRODUCT_KEYWORDS)
