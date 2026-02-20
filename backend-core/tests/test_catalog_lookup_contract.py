from app.services.agencyclaw.catalog_lookup_contract import (
    CATALOG_LOOKUP_STAGE_LABELS,
    DEFAULT_LIMIT,
    CatalogLookupCandidate,
    CatalogLookupResponse,
    derive_resolution_status,
)


def test_default_limit_and_stage_labels_contract() -> None:
    assert DEFAULT_LIMIT == 10
    assert CATALOG_LOOKUP_STAGE_LABELS == (
        "catalog_lookup_request",
        "catalog_lookup_match",
        "catalog_lookup_resolution",
    )


def test_output_shape_example_with_exact_resolution() -> None:
    candidates = (
        CatalogLookupCandidate(
            asin="B012345678",
            sku="SKU-123",
            title="Thorinox Garlic Press",
            confidence=0.99,
            match_reason="exact_asin",
        ),
    )
    response = CatalogLookupResponse(
        candidates=candidates,
        resolution_status=derive_resolution_status(candidates),
    )

    payload = response.to_dict()
    assert payload["resolution_status"] == "exact"
    assert isinstance(payload["candidates"], list)
    assert payload["candidates"][0]["asin"] == "B012345678"
    assert payload["candidates"][0]["sku"] == "SKU-123"
    assert payload["candidates"][0]["title"] == "Thorinox Garlic Press"
    assert payload["candidates"][0]["confidence"] == 0.99
    assert payload["candidates"][0]["match_reason"] == "exact_asin"


def test_ambiguous_resolution_semantics_with_multiple_exact_candidates() -> None:
    candidates = (
        CatalogLookupCandidate(
            asin="B012345678",
            sku="SKU-123",
            title="Thorinox Garlic Press Black",
            confidence=0.98,
            match_reason="exact_sku",
        ),
        CatalogLookupCandidate(
            asin="B087654321",
            sku="SKU-123",
            title="Thorinox Garlic Press Silver",
            confidence=0.97,
            match_reason="exact_sku",
        ),
    )

    assert derive_resolution_status(candidates) == "ambiguous"


def test_none_resolution_semantics_with_no_candidates() -> None:
    assert derive_resolution_status(()) == "none"
