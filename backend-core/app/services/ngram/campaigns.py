from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .analytics import build_ngram, derive_category

LEGACY_EXCLUSION_MARKERS = ("Ex.", "SDI", "SDV")


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
        if respect_legacy_exclusions and any(marker in cname for marker in LEGACY_EXCLUSION_MARKERS):
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
