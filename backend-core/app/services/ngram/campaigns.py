from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .analytics import build_ngram, derive_category

LEGACY_EXACT_KEYWORD_EXCLUSION_PATTERNS = (
    ("SPM", "SKW", "Ex."),
    ("SPM", "MKW", "Ex."),
)
LEGACY_DISPLAY_EXCLUSION_MARKERS = ("SDI", "SDV")


def _campaign_segments(campaign_name: str) -> list[str]:
    return [segment.strip() for segment in str(campaign_name or "").split("|")]


def is_legacy_excluded_campaign(campaign_name: str) -> bool:
    campaign_text = str(campaign_name or "")
    segments = _campaign_segments(campaign_name)
    segments_upper = [segment.upper() for segment in segments]

    if any(marker in campaign_text for marker in LEGACY_DISPLAY_EXCLUSION_MARKERS):
        return True

    for pattern in LEGACY_EXACT_KEYWORD_EXCLUSION_PATTERNS:
        pattern_upper = [segment.upper() for segment in pattern]
        pattern_length = len(pattern_upper)
        for idx in range(0, len(segments_upper) - pattern_length + 1):
            if segments_upper[idx : idx + pattern_length] == pattern_upper:
                return True

    return False


@dataclass(frozen=True)
class CampaignBuildResult:
    campaign_items: list[dict[str, Any]]
    campaigns_skipped: int


def build_campaign_items(
    df: pd.DataFrame,
    *,
    respect_legacy_exclusions: bool = True,
) -> CampaignBuildResult:
    campaign_items: list[dict[str, Any]] = []
    campaigns_skipped = 0

    for camp, sub in df.groupby("Campaign Name"):
        cname = str(camp)
        if respect_legacy_exclusions and is_legacy_excluded_campaign(cname):
            campaigns_skipped += 1
            continue

        category_raw, category_key, cat_notes = derive_category(cname)

        mono = build_ngram(sub, 1)
        bi = build_ngram(sub, 2)
        tri = build_ngram(sub, 3)

        raw = sub.rename(columns={"Query": "Search Term"})[
            ["Search Term", "Impression", "Click", "Spend", "Order 14d", "Sales 14d"]
        ].copy()
        raw["NE/NP"] = ""
        raw["Comments"] = ""
        raw = raw.sort_values(["Click", "Sales 14d"], ascending=[False, False]).reset_index(drop=True)

        notes = list(cat_notes)
        if mono.empty:
            notes.append("Monogram table has no rows.")
        if bi.empty:
            notes.append("Bigram table has no rows.")
        if tri.empty:
            notes.append("Trigram table has no rows.")
        if raw.empty:
            notes.append("Search Term table has no rows.")

        campaign_items.append(
            {
                "campaign_name": cname,
                "category_raw": category_raw,
                "category_key": category_key,
                "mono": mono,
                "bi": bi,
                "tri": tri,
                "raw": raw,
                "notes": notes,
            }
        )

    return CampaignBuildResult(
        campaign_items=campaign_items,
        campaigns_skipped=campaigns_skipped,
    )
