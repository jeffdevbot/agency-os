from __future__ import annotations

import pandas as pd

from app.services.ngram.campaigns import build_campaign_items


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


def test_build_campaign_items_respects_legacy_exclusions():
    df = pd.DataFrame(
        [
            {
                "Campaign Name": "Screen Shine - 90ct Wipes | Ex. | Archive",
                "Query": "screen cleaner",
                "Impression": 50,
                "Click": 5,
                "Spend": 7.5,
                "Order 14d": 1,
                "Sales 14d": 12.0,
            },
            {
                "Campaign Name": "Screen Shine - 90ct Wipes | SPA | Los. | Rsrch",
                "Query": "spray cleaner",
                "Impression": 50,
                "Click": 5,
                "Spend": 7.5,
                "Order 14d": 1,
                "Sales 14d": 12.0,
            },
        ]
    )

    result = build_campaign_items(df, respect_legacy_exclusions=True)

    assert result.campaigns_skipped == 1
    assert [item["campaign_name"] for item in result.campaign_items] == [
        "Screen Shine - 90ct Wipes | SPA | Los. | Rsrch"
    ]
