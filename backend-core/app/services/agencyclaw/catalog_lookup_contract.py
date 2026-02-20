"""Contract types and semantics for the C12C catalog_lookup skill."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Final, Literal

ResolutionStatus = Literal["exact", "ambiguous", "none"]
MatchReason = Literal[
    "exact_asin",
    "exact_sku",
    "prefix_asin",
    "prefix_sku",
    "token_contains_title",
]

DEFAULT_LIMIT: Final[int] = 10
MAX_LIMIT: Final[int] = 25
CATALOG_LOOKUP_STAGE_LABELS: Final[tuple[str, ...]] = (
    "catalog_lookup_request",
    "catalog_lookup_match",
    "catalog_lookup_resolution",
)


@dataclass(frozen=True)
class CatalogLookupCandidate:
    asin: str | None
    sku: str | None
    title: str
    confidence: float
    match_reason: MatchReason

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CatalogLookupResponse:
    candidates: tuple[CatalogLookupCandidate, ...]
    resolution_status: ResolutionStatus

    def to_dict(self) -> dict[str, object]:
        return {
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "resolution_status": self.resolution_status,
        }


def derive_resolution_status(candidates: tuple[CatalogLookupCandidate, ...]) -> ResolutionStatus:
    """Apply deterministic contract semantics for exact/ambiguous/none."""
    if not candidates:
        return "none"

    exact_reasons = {"exact_asin", "exact_sku"}
    exact_candidates = tuple(
        candidate for candidate in candidates if candidate.match_reason in exact_reasons
    )

    if len(exact_candidates) == 1:
        return "exact"

    return "ambiguous"
