from __future__ import annotations

import pandas as pd

from app.services.ngram.campaigns import build_campaign_items, is_legacy_excluded_campaign


def test_build_campaign_items_matches_legacy_sorting_and_notes():
    df = pd.DataFrame(
        [
            {
                "Campaign Name": "Screen Shine - 90ct Wipes | SPA | Los. | Rsrch",
                "Query": "monitor cleaner",
                "Impression": 100,
                "Click": 8,
                "Spend": 12.5,
                "Order 14d": 1,
                "Sales 14d": 20.0,
            },
            {
                "Campaign Name": "Screen Shine - 90ct Wipes | SPA | Los. | Rsrch",
                "Query": "screen spray",
                "Impression": 80,
                "Click": 12,
                "Spend": 15.0,
                "Order 14d": 2,
                "Sales 14d": 35.0,
            },
        ]
    )

    result = build_campaign_items(df, respect_legacy_exclusions=True)

    assert result.campaigns_skipped == 0
    assert len(result.campaign_items) == 1

    item = result.campaign_items[0]
    assert item["campaign_name"] == "Screen Shine - 90ct Wipes | SPA | Los. | Rsrch"
    assert item["category_raw"] == "90ct Wipes"
    assert list(item["raw"]["Search Term"]) == ["screen spray", "monitor cleaner"]
    assert list(item["raw"]["Click"]) == [12, 8]
    assert "Search Term table has no rows." not in item["notes"]


def test_build_campaign_items_respects_legacy_keyword_exact_exclusions():
    df = pd.DataFrame(
        [
            {
                "Campaign Name": "Screen Shine - Duo | SPM | MKW | Ex. | Harv | 3 - gen | Perf - 1",
                "Query": "screen cleaner",
                "Impression": 50,
                "Click": 5,
                "Spend": 7.5,
                "Order 14d": 1,
                "Sales 14d": 12.0,
            },
            {
                "Campaign Name": "Screen Shine - Duo | SPM | PT | Ex. | Main | Perf",
                "Query": "spray cleaner",
                "Impression": 50,
                "Click": 5,
                "Spend": 7.5,
                "Order 14d": 1,
                "Sales 14d": 12.0,
            },
            {
                "Campaign Name": "Screen Shine - Duo | SPM | CT | Ex. | Rsrch",
                "Query": "phone cleaner",
                "Impression": 60,
                "Click": 6,
                "Spend": 8.5,
                "Order 14d": 1,
                "Sales 14d": 15.0,
            },
        ]
    )

    result = build_campaign_items(df, respect_legacy_exclusions=True)

    assert result.campaigns_skipped == 1
    assert [item["campaign_name"] for item in result.campaign_items] == [
        "Screen Shine - Duo | SPM | CT | Ex. | Rsrch",
        "Screen Shine - Duo | SPM | PT | Ex. | Main | Perf",
    ]


def test_is_legacy_excluded_campaign_scopes_exact_keyword_and_display_patterns():
    assert is_legacy_excluded_campaign("Tub Cold Plunge | SPM | SKW | Ex. | ice bath | Rank")
    assert is_legacy_excluded_campaign("Screen Shine - Duo | SPM | MKW | Ex. | Harv | 3 - gen | Perf - 1")
    assert is_legacy_excluded_campaign("Screen Shine - Duo | SDI | Views")
    assert is_legacy_excluded_campaign("Screen Shine - Duo | SDV | Views")
    assert is_legacy_excluded_campaign("Screen Shine - Duo SDI Views")

    assert not is_legacy_excluded_campaign("MiHIGH - Sauna Blanket | SPM | PT | Ex. | Main | Perf")
    assert not is_legacy_excluded_campaign("MiHIGH - Sauna Blanket | SPM | STPP | Ex. | Perf")
    assert not is_legacy_excluded_campaign("Screen Shine - Duo | SPM | CT | Ex. | Rsrch")
    assert not is_legacy_excluded_campaign("MiHIGH | SB | PC-Store | MKW | Ex.")
    assert not is_legacy_excluded_campaign("MiHIGH | SBV | PP | MKW | Ex.")
