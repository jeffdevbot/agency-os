"""Tests for C11D: Brand context resolver (shared-destination aware).

Pure unit tests — no mocks needed since the resolver is a pure function.
"""

from __future__ import annotations

import pytest

from app.services.agencyclaw.brand_context_resolver import (
    BrandResolution,
    resolve_brand_context,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _brand(
    name: str = "Brand A",
    brand_id: str = "b1",
    space_id: str | None = "sp1",
    list_id: str | None = "l1",
) -> dict:
    return {
        "id": brand_id,
        "name": name,
        "clickup_space_id": space_id,
        "clickup_list_id": list_id,
    }


# ---------------------------------------------------------------------------
# No-destination cases
# ---------------------------------------------------------------------------


class TestNoDestination:
    def test_empty_list(self):
        result = resolve_brand_context([])
        assert result["mode"] == "no_destination"
        assert result["destination"] is None
        assert result["candidates"] == []

    def test_brands_without_mappings(self):
        result = resolve_brand_context([
            _brand("Orphan", space_id=None, list_id=None),
        ])
        assert result["mode"] == "no_destination"

    def test_non_dict_entries_ignored(self):
        result = resolve_brand_context(["not-a-dict", None, 42])  # type: ignore[list-item]
        assert result["mode"] == "no_destination"


# ---------------------------------------------------------------------------
# Single brand (client_level)
# ---------------------------------------------------------------------------


class TestSingleBrand:
    def test_single_mapped_brand_client_level(self):
        result = resolve_brand_context([_brand("Alpha")])
        assert result["mode"] == "client_level"
        assert result["destination"]["clickup_list_id"] == "l1"
        assert result["brand_context"]["name"] == "Alpha"
        assert result["destination_groups"] == 1

    def test_single_mapped_with_unmapped_siblings(self):
        """Only mapped brands are considered; unmapped siblings ignored."""
        result = resolve_brand_context([
            _brand("Mapped", space_id="sp1", list_id="l1"),
            _brand("Orphan", brand_id="b2", space_id=None, list_id=None),
        ])
        assert result["mode"] == "client_level"
        assert result["brand_context"]["name"] == "Mapped"


# ---------------------------------------------------------------------------
# Explicit brand hint
# ---------------------------------------------------------------------------


class TestExplicitHint:
    def test_exact_match(self):
        brands = [
            _brand("Alpha", brand_id="b1"),
            _brand("Beta", brand_id="b2", space_id="sp2", list_id="l2"),
        ]
        result = resolve_brand_context(brands, brand_hint="Alpha")
        assert result["mode"] == "explicit_brand"
        assert result["brand_context"]["id"] == "b1"

    def test_exact_match_case_insensitive(self):
        result = resolve_brand_context([_brand("Alpha Pro")], brand_hint="alpha pro")
        assert result["mode"] == "explicit_brand"

    def test_prefix_match(self):
        brands = [
            _brand("Alpha Pro", brand_id="b1"),
            _brand("Beta", brand_id="b2", space_id="sp2", list_id="l2"),
        ]
        result = resolve_brand_context(brands, brand_hint="alpha")
        assert result["mode"] == "clarified_brand"
        assert result["brand_context"]["id"] == "b1"

    def test_contains_match(self):
        brands = [
            _brand("Super Alpha Max", brand_id="b1"),
            _brand("Beta", brand_id="b2", space_id="sp2", list_id="l2"),
        ]
        result = resolve_brand_context(brands, brand_hint="alpha")
        assert result["mode"] == "clarified_brand"
        assert result["brand_context"]["id"] == "b1"

    def test_hint_multiple_matches_ambiguous(self):
        brands = [
            _brand("Alpha Pro", brand_id="b1"),
            _brand("Alpha Lite", brand_id="b2", space_id="sp2", list_id="l2"),
        ]
        result = resolve_brand_context(brands, brand_hint="Alpha")
        assert result["mode"] == "ambiguous_brand"
        assert len(result["candidates"]) == 2

    def test_hint_no_match_shows_all(self):
        brands = [
            _brand("Alpha", brand_id="b1"),
            _brand("Beta", brand_id="b2", space_id="sp2", list_id="l2"),
        ]
        result = resolve_brand_context(brands, brand_hint="Zeta")
        assert result["mode"] == "ambiguous_brand"
        assert len(result["candidates"]) == 2  # all mapped brands as fallback

    def test_hint_whitespace_only_treated_as_no_hint(self):
        result = resolve_brand_context([_brand("Alpha")], brand_hint="   ")
        assert result["mode"] == "client_level"


# ---------------------------------------------------------------------------
# Shared destination (same space_id + list_id)
# ---------------------------------------------------------------------------


class TestSharedDestination:
    def test_non_product_request_client_level(self):
        brands = [
            _brand("A", brand_id="b1", space_id="sp1", list_id="l1"),
            _brand("B", brand_id="b2", space_id="sp1", list_id="l1"),
        ]
        result = resolve_brand_context(brands, task_text="update ad copy")
        assert result["mode"] == "client_level"
        assert result["destination"] is not None
        assert result["brand_context"] is None  # no specific brand
        assert result["destination_groups"] == 1

    def test_product_scoped_request_ambiguous(self):
        brands = [
            _brand("A", brand_id="b1", space_id="sp1", list_id="l1"),
            _brand("B", brand_id="b2", space_id="sp1", list_id="l1"),
        ]
        result = resolve_brand_context(brands, task_text="create coupon for listing")
        assert result["mode"] == "ambiguous_brand"
        assert result["destination_groups"] == 1

    def test_empty_task_text_client_level(self):
        brands = [
            _brand("A", brand_id="b1", space_id="sp1", list_id="l1"),
            _brand("B", brand_id="b2", space_id="sp1", list_id="l1"),
        ]
        result = resolve_brand_context(brands, task_text="")
        assert result["mode"] == "client_level"


# ---------------------------------------------------------------------------
# Different destinations (ambiguous_destination)
# ---------------------------------------------------------------------------


class TestDifferentDestinations:
    def test_two_different_dests(self):
        brands = [
            _brand("A", brand_id="b1", space_id="sp1", list_id="l1"),
            _brand("B", brand_id="b2", space_id="sp2", list_id="l2"),
        ]
        result = resolve_brand_context(brands)
        assert result["mode"] == "ambiguous_destination"
        assert result["destination_groups"] == 2
        assert result["destination"] is None

    def test_three_destinations(self):
        brands = [
            _brand("A", brand_id="b1", space_id="sp1", list_id="l1"),
            _brand("B", brand_id="b2", space_id="sp2", list_id="l2"),
            _brand("C", brand_id="b3", space_id="sp3", list_id="l3"),
        ]
        result = resolve_brand_context(brands)
        assert result["mode"] == "ambiguous_destination"
        assert result["destination_groups"] == 3

    def test_mixed_shared_and_different(self):
        """Two brands share one dest, third has different dest."""
        brands = [
            _brand("A", brand_id="b1", space_id="sp1", list_id="l1"),
            _brand("B", brand_id="b2", space_id="sp1", list_id="l1"),
            _brand("C", brand_id="b3", space_id="sp2", list_id="l2"),
        ]
        result = resolve_brand_context(brands)
        assert result["mode"] == "ambiguous_destination"
        assert result["destination_groups"] == 2


# ---------------------------------------------------------------------------
# Product-scope detection
# ---------------------------------------------------------------------------


class TestProductScope:
    @pytest.mark.parametrize("text", [
        "create coupon for product",
        "update listing copy",
        "set ASIN price",
        "new sku promotion",
        "catalog discount",
        "product deal setup",
        "coupon?",
        "listing,",
        "product-level update",
    ])
    def test_product_keywords_detected(self, text: str):
        brands = [
            _brand("A", brand_id="b1", space_id="sp1", list_id="l1"),
            _brand("B", brand_id="b2", space_id="sp1", list_id="l1"),
        ]
        result = resolve_brand_context(brands, task_text=text)
        assert result["mode"] == "ambiguous_brand"

    @pytest.mark.parametrize("text", [
        "update ad copy",
        "review quarterly report",
        "fix landing page",
        "schedule meeting",
    ])
    def test_non_product_text_client_level(self, text: str):
        brands = [
            _brand("A", brand_id="b1", space_id="sp1", list_id="l1"),
            _brand("B", brand_id="b2", space_id="sp1", list_id="l1"),
        ]
        result = resolve_brand_context(brands, task_text=text)
        assert result["mode"] == "client_level"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_brand_with_space_only(self):
        result = resolve_brand_context([_brand("A", space_id="sp1", list_id=None)])
        assert result["mode"] == "client_level"
        assert result["destination"]["clickup_space_id"] == "sp1"
        assert result["destination"]["clickup_list_id"] is None

    def test_brand_with_list_only(self):
        result = resolve_brand_context([_brand("A", space_id=None, list_id="l1")])
        assert result["mode"] == "client_level"
        assert result["destination"]["clickup_list_id"] == "l1"

    def test_destination_grouping_ignores_unmapped(self):
        """Unmapped brands don't affect destination group count."""
        brands = [
            _brand("Mapped", brand_id="b1", space_id="sp1", list_id="l1"),
            _brand("Unmapped", brand_id="b2", space_id=None, list_id=None),
        ]
        result = resolve_brand_context(brands)
        assert result["mode"] == "client_level"
        assert result["destination_groups"] == 1

    def test_candidates_only_include_mapped(self):
        brands = [
            _brand("Mapped", brand_id="b1", space_id="sp1", list_id="l1"),
            _brand("Unmapped", brand_id="b2", space_id=None, list_id=None),
        ]
        result = resolve_brand_context(brands)
        assert len(result["candidates"]) == 1
        assert result["candidates"][0]["name"] == "Mapped"
