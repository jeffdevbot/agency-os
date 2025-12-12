import pandas as pd

from app.services.adscope.views import compute_wasted_spend_sp


def test_compute_wasted_spend_sp_summary_and_sorting():
    df = pd.DataFrame(
        [
            {
                "campaign_name": "C1",
                "ad_group_name": "AG1",
                "search_term": "term a",
                "targeting": "close-match",
                "match_type": "-",
                "impressions": 100,
                "clicks": 10,
                "spend": 50.0,
                "sales": 0.0,
                "orders": 0,
            },
            {
                "campaign_name": "C1",
                "ad_group_name": "AG1",
                "search_term": "term b",
                "targeting": "asin=\"B000\"",
                "match_type": "-",
                "impressions": 200,
                "clicks": 20,
                "spend": 120.0,
                "sales": 0.0,
                "orders": 0,
            },
            {
                "campaign_name": "C2",
                "ad_group_name": "AG2",
                "search_term": "term c",
                "targeting": "keyword",
                "match_type": "exact",
                "impressions": 50,
                "clicks": 5,
                "spend": 30.0,
                "sales": 200.0,
                "orders": 2,
            },
        ]
    )

    view = compute_wasted_spend_sp(df)

    assert view["scope"].lower().startswith("sponsored products")
    assert view["summary"]["total_ad_spend"] == 200.0
    assert view["summary"]["total_wasted_spend"] == 170.0
    assert view["summary"]["wasted_targets_count"] == 2
    assert view["summary"]["wasted_campaigns_count"] == 1
    assert view["summary"]["wasted_spend_pct"] == 170.0 / 200.0

    # Top wasted targets sorted desc by spend
    assert view["top_wasted_targets"][0]["spend"] == 120.0
    assert view["top_wasted_targets"][1]["spend"] == 50.0

    # Campaign rollup exists and has wasted %
    assert view["campaign_rollup"][0]["campaign_name"] == "C1"
    assert view["campaign_rollup"][0]["campaign_spend"] == 170.0
    assert view["campaign_rollup"][0]["campaign_wasted_spend"] == 170.0
    assert view["campaign_rollup"][0]["campaign_wasted_pct"] == 1.0
