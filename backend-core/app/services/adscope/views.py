"""View computations for AdScope audit."""
from __future__ import annotations

from typing import Any
import pandas as pd
import numpy as np
from datetime import timedelta


def _normalize_header(value: str) -> str:
    """Lowercase + strip non-alphanumerics for tolerant matching."""
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def _ensure_required_column(df: pd.DataFrame, target: str) -> pd.DataFrame:
    """
    If a column normalizes to the target, rename it to the target so downstream logic doesn't KeyError.
    """
    if target in df.columns:
        return df

    for col in df.columns:
        if _normalize_header(col) == _normalize_header(target):
            df = df.rename(columns={col: target})
            break
    return df

def compute_overview(bulk_df: pd.DataFrame, str_df: pd.DataFrame) -> dict[str, Any]:
    """Compute overview metrics."""
    # Use Bulk for top-level metrics to include all ad types (SP, SB, SD)
    # Filter for Entity="Campaign" to avoid double counting
    campaign_rows = bulk_df[bulk_df["entity"] == "Campaign"].copy()
    
    if not campaign_rows.empty:
        total_spend = float(campaign_rows["spend"].sum())
        total_sales = float(campaign_rows["sales"].sum())
        total_impressions = float(campaign_rows["impressions"].sum())
        total_clicks = float(campaign_rows["clicks"].sum())
        total_orders = float(campaign_rows["orders"].sum()) if "orders" in campaign_rows.columns else 0.0
    else:
        # Fallback to STR if Bulk has no campaigns (unlikely but safe)
        total_spend = float(str_df["spend"].sum())
        total_sales = float(str_df["sales"].sum())
        total_impressions = float(str_df["impressions"].sum())
        total_clicks = float(str_df["clicks"].sum())
        total_orders = float(str_df["orders"].sum()) if "orders" in str_df.columns else 0.0

    acos = total_spend / total_sales if total_sales > 0 else 0.0
    roas = total_sales / total_spend if total_spend > 0 else 0.0

    # Ad type mix from Bulk (Entity='Campaign' with Product column)
    if "product" in campaign_rows.columns:
        ad_type_spend = campaign_rows.groupby("product")["spend"].sum().to_dict()
        total_campaign_spend = sum(ad_type_spend.values())

        ad_type_mix = [
            {
                "type": ad_type,
                "spend": float(spend),
                "percentage": float(spend / total_campaign_spend) if total_campaign_spend > 0 else 0.0
            }
            for ad_type, spend in sorted(ad_type_spend.items(), key=lambda x: x[1], reverse=True)
        ]
    else:
        ad_type_mix = []

    # Targeting mix (manual vs auto) from Bulk campaigns
    targeting_mix = {"manual_spend": 0.0, "auto_spend": 0.0, "manual_percent": 0.0}
    if "targeting_type" in campaign_rows.columns:
        for _, row in campaign_rows.iterrows():
            targeting_type = str(row.get("targeting_type", "")).lower()
            spend = float(row.get("spend", 0))

            if "manual" in targeting_type:
                targeting_mix["manual_spend"] += spend
            elif "auto" in targeting_type:
                targeting_mix["auto_spend"] += spend

        total_targeting_spend = targeting_mix["manual_spend"] + targeting_mix["auto_spend"]
        if total_targeting_spend > 0:
            targeting_mix["manual_percent"] = targeting_mix["manual_spend"] / total_targeting_spend

    return {
        "spend": total_spend,
        "sales": total_sales,
        "acos": acos,
        "roas": roas,
        "impressions": total_impressions,
        "clicks": total_clicks,
        "orders": total_orders,
        "ad_type_mix": ad_type_mix,
        "targeting_mix": targeting_mix,
    }


def compute_money_pits(bulk_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Compute money pits (top 20% spenders, max 50)."""
    # Use Product Ad rows (Entity='Product Ad') or Keyword rows with ASIN
    product_rows = bulk_df[bulk_df["entity"].isin(["Product Ad", "Keyword"])].copy()

    if product_rows.empty:
        return []

    # Group by ASIN if available
    if "asin" in product_rows.columns:
        grouped = product_rows.groupby("asin").agg({
            "spend": "sum",
            "sales": "sum",
            "state": "first",  # Take first state
        }).reset_index()

        grouped["acos"] = grouped.apply(
            lambda row: float(row["spend"] / row["sales"]) if row["sales"] > 0 else 0.0,
            axis=1
        )

        # Top 20% by spend
        threshold = grouped["spend"].quantile(0.8)
        top_spenders = grouped[grouped["spend"] >= threshold].copy()

        # Sort: enabled first, then by spend desc
        top_spenders["state_priority"] = top_spenders["state"].apply(
            lambda x: 0 if str(x).lower() == "enabled" else 1
        )
        top_spenders = top_spenders.sort_values(
            ["state_priority", "spend"],
            ascending=[True, False]
        ).head(50)

        return [
            {
                "asin": row["asin"],
                "product_name": "",  # Not available in bulk file
                "spend": float(row["spend"]),
                "sales": float(row["sales"]),
                "acos": float(row["acos"]),
                "state": str(row["state"]) if pd.notna(row["state"]) else "enabled",
            }
            for _, row in top_spenders.iterrows()
        ]
    else:
        return []


def compute_waste_bin(str_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Compute waste bin (terms with spend > 50, sales = 0)."""
    waste = str_df[(str_df["spend"] > 50) & (str_df["sales"] == 0)].copy()

    waste = waste.sort_values("spend", ascending=False).head(100)

    return [
        {
            "search_term": row["search_term"],
            "spend": float(row["spend"]),
            "clicks": float(row["clicks"]),
        }
        for _, row in waste.iterrows()
    ]


def compute_brand_analysis(str_df: pd.DataFrame) -> dict[str, Any]:
    """Compute branded vs generic analysis."""
    branded = str_df[str_df["is_branded"] == True]
    generic = str_df[str_df["is_branded"] == False]

    def aggregate(df):
        spend = float(df["spend"].sum())
        sales = float(df["sales"].sum())
        acos = spend / sales if sales > 0 else 0.0
        return {"spend": spend, "sales": sales, "acos": acos}

    return {
        "branded": aggregate(branded),
        "generic": aggregate(generic),
    }


def compute_match_types(str_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Compute match type analysis."""
    if "match_type" not in str_df.columns:
        return []

    grouped = str_df.groupby("match_type").agg({
        "spend": "sum",
        "sales": "sum",
        "clicks": "sum",
    }).reset_index()

    grouped["acos"] = grouped.apply(
        lambda row: float(row["spend"] / row["sales"]) if row["sales"] > 0 else 0.0,
        axis=1
    )
    grouped["cpc"] = grouped.apply(
        lambda row: float(row["spend"] / row["clicks"]) if row["clicks"] > 0 else 0.0,
        axis=1
    )

    grouped = grouped.sort_values("spend", ascending=False)

    return [
        {
            "type": row["match_type"],
            "spend": float(row["spend"]),
            "sales": float(row["sales"]),
            "acos": float(row["acos"]),
            "cpc": float(row["cpc"]),
        }
        for _, row in grouped.iterrows()
    ]


def compute_placements(bulk_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Compute placement analysis."""
    if "placement" not in bulk_df.columns:
        return []

    # Filter to rows with placement data
    placement_rows = bulk_df[bulk_df["placement"].notna()].copy()

    if placement_rows.empty:
        return []

    grouped = placement_rows.groupby("placement").agg({
        "spend": "sum",
        "sales": "sum",
        "clicks": "sum",
    }).reset_index()

    grouped["acos"] = grouped.apply(
        lambda row: float(row["spend"] / row["sales"]) if row["sales"] > 0 else 0.0,
        axis=1
    )
    grouped["cpc"] = grouped.apply(
        lambda row: float(row["spend"] / row["clicks"]) if row["clicks"] > 0 else 0.0,
        axis=1
    )

    return [
        {
            "placement": row["placement"],
            "spend": float(row["spend"]),
            "acos": float(row["acos"]),
            "cpc": float(row["cpc"]),
        }
        for _, row in grouped.iterrows()
    ]


def compute_keyword_leaderboard(bulk_df: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    """Compute keyword winners and losers."""
    # Use Keyword rows
    keyword_rows = bulk_df[bulk_df["entity"] == "Keyword"].copy()

    if keyword_rows.empty or "keyword" not in keyword_rows.columns:
        return {"winners": [], "losers": []}

    # Calculate ROAS
    keyword_rows["roas"] = keyword_rows.apply(
        lambda row: float(row["sales"] / row["spend"]) if row["spend"] > 0 else 0.0,
        axis=1
    )

    # Winners: top 10 by sales
    winners = keyword_rows.nlargest(10, "sales")

    # Losers: top 10 by spend with ROAS < 2
    losers_df = keyword_rows[keyword_rows["roas"] < 2.0]
    losers = losers_df.nlargest(10, "spend")

    def format_keyword(row):
        return {
            "text": str(row.get("keyword", "")),
            "match_type": str(row.get("match_type", "")) if pd.notna(row.get("match_type")) else "",
            "campaign": str(row.get("campaign_name", "")),
            "spend": float(row.get("spend", 0)),
            "sales": float(row.get("sales", 0)),
            "roas": float(row.get("roas", 0)),
            "state": str(row.get("state", "enabled")) if pd.notna(row.get("state")) else "enabled",
        }

    return {
        "winners": [format_keyword(row) for _, row in winners.iterrows()],
        "losers": [format_keyword(row) for _, row in losers.iterrows()],
    }


def compute_budget_cappers(bulk_df: pd.DataFrame, metadata: dict[str, Any]) -> list[dict[str, Any]]:
    """Compute campaigns hitting budget caps (utilization > 0.9)."""
    # Build campaign ID -> daily budget map from Campaign rows
    campaign_rows = bulk_df[bulk_df["entity"] == "Campaign"].copy()

    if campaign_rows.empty or "daily_budget" not in campaign_rows.columns:
        return []

    budget_map = {}
    for _, row in campaign_rows.iterrows():
        campaign_id = row.get("campaign_id")
        daily_budget = float(row.get("daily_budget", 0))
        if daily_budget > 0:
            budget_map[campaign_id] = {
                "name": str(row.get("campaign_name", "")),
                "daily_budget": daily_budget,
                "state": str(row.get("state", "enabled")),
            }

    # Sum spend for each campaign (non-Campaign rows)
    non_campaign_rows = bulk_df[bulk_df["entity"] != "Campaign"].copy()
    campaign_spend = non_campaign_rows.groupby("campaign_id")["spend"].sum().to_dict()

    # Calculate average daily spend (assume 60-day range unless dates indicate otherwise)
    days_in_range = 60
    if "bulk_start_date" in metadata and "bulk_end_date" in metadata:
        start = metadata["bulk_start_date"]
        end = metadata["bulk_end_date"]
        if pd.notna(start) and pd.notna(end):
            delta_days = (end - start).days + 1  # inclusive
            if delta_days > 0:
                days_in_range = delta_days

    results = []
    for campaign_id, budget_info in budget_map.items():
        total_spend = campaign_spend.get(campaign_id, 0.0)
        avg_daily_spend = total_spend / days_in_range if days_in_range > 0 else 0.0
        utilization = avg_daily_spend / budget_info["daily_budget"] if budget_info["daily_budget"] > 0 else 0.0

        if utilization > 0.9:
            # Get ROAS from campaign row if available
            campaign_row = campaign_rows[campaign_rows["campaign_id"] == campaign_id]
            roas = 0.0
            if not campaign_row.empty:
                sales = float(campaign_row.iloc[0].get("sales", 0))
                roas = sales / total_spend if total_spend > 0 else 0.0

            results.append({
                "campaign_name": budget_info["name"],
                "daily_budget": budget_info["daily_budget"],
                "avg_daily_spend": avg_daily_spend,
                "utilization": utilization,
                "roas": roas,
                "state": budget_info["state"],
            })

    # Sort: enabled first, then by utilization desc
    results.sort(key=lambda x: (0 if x["state"].lower() == "enabled" else 1, -x["utilization"]))

    return results


def compute_campaign_scatter(bulk_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Compute campaign-level data for scatter plot."""
    campaign_rows = bulk_df[bulk_df["entity"] == "Campaign"].copy()

    if campaign_rows.empty:
        return []

    campaign_rows["acos"] = campaign_rows.apply(
        lambda row: float(row["spend"] / row["sales"]) if row["sales"] > 0 else 0.0,
        axis=1
    )

    return [
        {
            "id": str(row.get("campaign_id", "")),
            "name": str(row.get("campaign_name", "")),
            "spend": float(row.get("spend", 0)),
            "acos": float(row.get("acos", 0)),
            "ad_type": str(row.get("product", "")) if pd.notna(row.get("product")) else "",
        }
        for _, row in campaign_rows.iterrows()
    ]


def compute_ngrams(str_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Compute n-gram analysis (1-gram and 2-gram)."""
    results = []

    # 1-grams
    one_gram_rows = []
    for _, row in str_df.iterrows():
        grams = row.get("one_grams", [])
        if isinstance(grams, list):
            for gram in grams:
                one_gram_rows.append({
                    "gram": gram,
                    "spend": row["spend"],
                    "sales": row["sales"],
                })

    if one_gram_rows:
        one_gram_df = pd.DataFrame(one_gram_rows)
        one_gram_agg = one_gram_df.groupby("gram").agg({
            "spend": "sum",
            "sales": "sum",
        }).reset_index()
        one_gram_agg["count"] = one_gram_df.groupby("gram").size().values
        one_gram_agg["acos"] = one_gram_agg.apply(
            lambda r: float(r["spend"] / r["sales"]) if r["sales"] > 0 else 0.0,
            axis=1
        )

        for _, row in one_gram_agg.nlargest(50, "spend").iterrows():
            results.append({
                "gram": str(row["gram"]),
                "type": "1-gram",
                "spend": float(row["spend"]),
                "sales": float(row["sales"]),
                "acos": float(row["acos"]),
                "count": int(row["count"]),
            })

    # 2-grams
    two_gram_rows = []
    for _, row in str_df.iterrows():
        grams = row.get("two_grams", [])
        if isinstance(grams, list):
            for gram in grams:
                two_gram_rows.append({
                    "gram": gram,
                    "spend": row["spend"],
                    "sales": row["sales"],
                })

    if two_gram_rows:
        two_gram_df = pd.DataFrame(two_gram_rows)
        two_gram_agg = two_gram_df.groupby("gram").agg({
            "spend": "sum",
            "sales": "sum",
        }).reset_index()
        two_gram_agg["count"] = two_gram_df.groupby("gram").size().values
        two_gram_agg["acos"] = two_gram_agg.apply(
            lambda r: float(r["spend"] / r["sales"]) if r["sales"] > 0 else 0.0,
            axis=1
        )

        for _, row in two_gram_agg.nlargest(50, "spend").iterrows():
            results.append({
                "gram": str(row["gram"]),
                "type": "2-gram",
                "spend": float(row["spend"]),
                "sales": float(row["sales"]),
                "acos": float(row["acos"]),
                "count": int(row["count"]),
            })

    return results


def compute_duplicates(bulk_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Compute keywords used in multiple campaigns."""
    keyword_rows = bulk_df[bulk_df["entity"] == "Keyword"].copy()

    if keyword_rows.empty or "keyword" not in keyword_rows.columns:
        return []

    # Group by keyword + match_type
    if "match_type" in keyword_rows.columns:
        grouped = keyword_rows.groupby(["keyword", "match_type"]).agg({
            "campaign_name": lambda x: list(x.unique())
        }).reset_index()

        grouped["campaign_count"] = grouped["campaign_name"].apply(len)

        # Filter to duplicates
        duplicates = grouped[grouped["campaign_count"] > 1].copy()

        return [
            {
                "keyword": str(row["keyword"]),
                "match_type": str(row["match_type"]),
                "campaign_count": int(row["campaign_count"]),
                "campaigns": list(row["campaign_name"]),
            }
            for _, row in duplicates.nlargest(100, "campaign_count").iterrows()
        ]
    else:
        return []


def compute_portfolios(bulk_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Compute portfolio-level metrics."""
    if "portfolio_name" not in bulk_df.columns:
        return []

    portfolio_rows = bulk_df[bulk_df["portfolio_name"].notna()].copy()

    if portfolio_rows.empty:
        return []

    grouped = portfolio_rows.groupby("portfolio_name").agg({
        "spend": "sum",
        "sales": "sum",
    }).reset_index()

    grouped["acos"] = grouped.apply(
        lambda row: float(row["spend"] / row["sales"]) if row["sales"] > 0 else 0.0,
        axis=1
    )

    grouped = grouped.sort_values("spend", ascending=False)

    return [
        {
            "name": str(row["portfolio_name"]),
            "spend": float(row["spend"]),
            "sales": float(row["sales"]),
            "acos": float(row["acos"]),
        }
        for _, row in grouped.iterrows()
    ]


def compute_price_sensitivity(bulk_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Compute price sensitivity (ASIN average price vs CVR)."""
    # Use Product Ad rows
    product_rows = bulk_df[bulk_df["entity"] == "Product Ad"].copy()

    if product_rows.empty or "asin" not in product_rows.columns:
        return []

    # Ensure required numeric columns exist
    if not all(col in product_rows.columns for col in ["sales", "orders", "clicks"]):
        return []

    # Group by ASIN
    grouped = product_rows.groupby("asin").agg({
        "sales": "sum",
        "orders": "sum",
        "clicks": "sum",
    }).reset_index()

    # Calculate avg price and CVR
    grouped["avg_price"] = grouped.apply(
        lambda row: float(row["sales"] / row["orders"]) if row["orders"] > 0 else 0.0,
        axis=1
    )
    grouped["cvr"] = grouped.apply(
        lambda row: float(row["orders"] / row["clicks"]) if row["clicks"] > 0 else 0.0,
        axis=1
    )

    # Filter out zero values
    filtered = grouped[(grouped["avg_price"] > 0) & (grouped["cvr"] > 0)].copy()

    return [
        {
            "asin": str(row["asin"]),
            "avg_price": float(row["avg_price"]),
            "cvr": float(row["cvr"]),
        }
        for _, row in filtered.head(200).iterrows()
    ]


def compute_zombies(bulk_df: pd.DataFrame) -> dict[str, Any]:
    """Compute zombie ad groups (active but zero impressions)."""
    # Ad Group rows
    adgroup_rows = bulk_df[bulk_df["entity"] == "Ad Group"].copy()

    if adgroup_rows.empty:
        return {"total_active_ad_groups": 0, "zombie_count": 0, "zombie_list": []}

    # Active ad groups
    if "state" in adgroup_rows.columns:
        active = adgroup_rows[adgroup_rows["state"].str.lower() == "enabled"]
    else:
        active = adgroup_rows
    total_active = len(active)

    # Zombies: active with zero impressions
    if "impressions" in active.columns:
        zombies = active[active["impressions"] == 0]
    else:
        zombies = active[active.get("impressions", 0) == 0]
    zombie_count = len(zombies)

    zombie_list = [
        f"{row['campaign_name']} / {row['ad_group_name']}"
        for _, row in zombies.head(100).iterrows()
        if pd.notna(row.get("ad_group_name"))
    ]

    return {
        "total_active_ad_groups": total_active,
        "zombie_count": zombie_count,
        "zombie_list": zombie_list,
    }


def compute_all_views(
    bulk_df: pd.DataFrame,
    str_df: pd.DataFrame,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Compute all 13 views."""
    # Basic column sanity checks to surface clear errors instead of KeyErrors
    for required in ["spend", "sales", "impressions", "clicks"]:
        str_df = _ensure_required_column(str_df, required)
    for required in ["spend", "sales"]:
        bulk_df = _ensure_required_column(bulk_df, required)

    missing_str = [col for col in ["spend", "sales", "impressions", "clicks"] if col not in str_df.columns]
    missing_bulk = [col for col in ["spend", "sales"] if col not in bulk_df.columns]
    if missing_str:
        raise ValueError(f"STR missing required columns: {missing_str}. Found STR columns: {list(str_df.columns)}")
    if missing_bulk:
        raise ValueError(f"Bulk file missing required columns: {missing_bulk}. Found Bulk columns: {list(bulk_df.columns)}")

    return {
        "overview": compute_overview(bulk_df, str_df),
        "money_pits": compute_money_pits(bulk_df),
        "waste_bin": compute_waste_bin(str_df),
        "brand_analysis": compute_brand_analysis(str_df),
        "match_types": compute_match_types(str_df),
        "placements": compute_placements(bulk_df),
        "keyword_leaderboard": compute_keyword_leaderboard(bulk_df),
        "budget_cappers": compute_budget_cappers(bulk_df, metadata),
        "campaign_scatter": compute_campaign_scatter(bulk_df),
        "n_grams": compute_ngrams(str_df),
        "duplicates": compute_duplicates(bulk_df),
        "portfolios": compute_portfolios(bulk_df),
        "price_sensitivity": compute_price_sensitivity(bulk_df),
        "zombies": compute_zombies(bulk_df),
        "ad_types": compute_ad_types(bulk_df),
        "sponsored_products": {
            **compute_sp_targeting(bulk_df),
            "match_types": compute_sp_match_types(str_df),
        },
    }

def compute_sp_targeting(bulk_df: pd.DataFrame) -> dict[str, Any]:
    """Compute Sponsored Products breakdown by targeting type (Auto vs Manual)."""
    # Filter to SP campaigns only
    campaign_rows = bulk_df[
        (bulk_df["entity"] == "Campaign") &
        (bulk_df["product"].str.lower().str.contains("sponsored products", na=False))
    ].copy()

    if campaign_rows.empty:
        return {"targeting_breakdown": [], "match_types": []}

    # --- Section 1: Auto vs Manual breakdown ---
    targeting_breakdown = []
    if "targeting_type" in campaign_rows.columns:
        grouped = campaign_rows.groupby("targeting_type").agg({
            "campaign_id": "nunique",
            "spend": "sum",
            "sales": "sum",
            "impressions": "sum",
            "clicks": "sum",
            "orders": "sum"
        }).reset_index()

        grouped = grouped.rename(columns={"campaign_id": "campaigns"})

        # Calculate derived metrics
        for _, row in grouped.iterrows():
            spend = float(row["spend"])
            sales = float(row["sales"])
            clicks = float(row["clicks"])
            impressions = float(row["impressions"])
            orders = float(row["orders"])

            targeting_breakdown.append({
                "targeting_type": str(row["targeting_type"]),
                "campaigns": int(row["campaigns"]),
                "spend": spend,
                "sales": sales,
                "cpc": spend / clicks if clicks > 0 else 0.0,
                "ctr": clicks / impressions if impressions > 0 else 0.0,
                "cvr": orders / clicks if clicks > 0 else 0.0,
                "acos": spend / sales if sales > 0 else 0.0,
            })

    return {
        "targeting_breakdown": targeting_breakdown,
    }


def _derive_targeting_type(row: pd.Series) -> str:
    """
    Derive the targeting type from match_type and product_targeting_expression.

    Returns one of:
    - Keyword types: Exact, Phrase, Broad, Modified Broad
    - Auto types: Close-Match, Loose-Match, Substitutes, Complements
    - Product targeting: ASIN, Expanded ASIN, Category
    """
    match_type = str(row.get("match_type", "")).strip().lower()
    targeting_expr = str(row.get("product_targeting_expression", "")).strip().lower()
    targeting = str(row.get("targeting", "")).strip().lower()

    # Normalize known match types (keyword targeting)
    match_type_map = {
        "exact": "Exact",
        "phrase": "Phrase",
        "broad": "Broad",
        "modified broad": "Modified Broad",
        "negativeexact": "Negative Exact",
        "negativephrase": "Negative Phrase",
    }
    if match_type in match_type_map:
        return match_type_map[match_type]

    # Auto targeting types (often in match_type or targeting column)
    auto_type_map = {
        "close-match": "Close-Match",
        "closematch": "Close-Match",
        "loose-match": "Loose-Match",
        "loosematch": "Loose-Match",
        "substitutes": "Substitutes",
        "complements": "Complements",
    }
    if match_type in auto_type_map:
        return auto_type_map[match_type]
    if targeting in auto_type_map:
        return auto_type_map[targeting]

    # Product targeting - check BOTH match_type and targeting_expr for patterns
    # Amazon sometimes puts the expression in match_type column directly
    combined_expr = f"{match_type} {targeting_expr}".lower()

    if "expanded" in combined_expr:
        return "Expanded ASIN"
    if "asin=" in combined_expr or "asin-" in combined_expr or match_type.startswith("asin"):
        return "ASIN"
    if "category=" in combined_expr or "category-" in combined_expr or match_type.startswith("category"):
        return "Category"

    # Fallback: if we have a targeting column value
    if targeting and targeting not in ("", "nan", "-", "none"):
        return targeting.title().replace("-", " ")

    # Last resort: check if match_type looks like product targeting we missed
    if match_type and match_type not in ("", "nan", "-", "none"):
        # If it contains "=" it's likely a targeting expression we didn't categorize
        if "=" in match_type:
            return "Product Targeting"
        return match_type.title()

    return "Unknown"


def compute_sp_match_types(str_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Compute SP match type breakdown with full metrics."""
    if str_df.empty:
        return []

    # Create a copy to avoid modifying the original
    df = str_df.copy()

    # Derive targeting type for each row
    df["targeting_type"] = df.apply(_derive_targeting_type, axis=1)

    grouped = df.groupby("targeting_type").agg({
        "spend": "sum",
        "sales": "sum",
        "impressions": "sum",
        "clicks": "sum",
        "orders": "sum",
    }).reset_index()

    # Add count of targets per targeting type
    type_counts = df.groupby("targeting_type").size().reset_index(name="target_count")
    grouped = grouped.merge(type_counts, on="targeting_type", how="left")

    results = []
    for _, row in grouped.iterrows():
        spend = float(row["spend"])
        sales = float(row["sales"])
        clicks = float(row["clicks"])
        impressions = float(row["impressions"])
        orders = float(row["orders"])
        target_count = int(row["target_count"])

        results.append({
            "match_type": str(row["targeting_type"]),
            "target_count": target_count,
            "spend": spend,
            "sales": sales,
            "cpc": spend / clicks if clicks > 0 else 0.0,
            "ctr": clicks / impressions if impressions > 0 else 0.0,
            "cvr": orders / clicks if clicks > 0 else 0.0,
            "acos": spend / sales if sales > 0 else 0.0,
        })

    # Sort by spend descending
    results.sort(key=lambda x: x["spend"], reverse=True)
    return results


def compute_ad_types(bulk_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Compute metrics by Ad Type (Sponsored Products, Brands, Display)."""
    # Use Campaign rows to get the distinct ad types and their campaign-level spend
    # However, to get detailed metrics like Sales/Orders which might be attributed to ad groups/keywords, 
    # we should look at where the data is most complete. 
    # For Bulksheets, 'Record Type'='Campaign' usually has rolled up Spend/Sales for SP/SB/SD.
    
    campaign_rows = bulk_df[bulk_df["entity"] == "Campaign"].copy()
    
    if campaign_rows.empty:
        return []

    # Ensure product column exists (it distinguishes SP/SB/SD)
    if "product" not in campaign_rows.columns:
        return []

    # Group by 'product' (e.g. 'Sponsored Products', 'Sponsored Brands')
    grouped = campaign_rows.groupby("product").agg({
        "campaign_id": "nunique", # Count active campaigns
        "spend": "sum",
        "sales": "sum",
        "impressions": "sum",
        "clicks": "sum",
        "orders": "sum"
    }).reset_index()

    grouped = grouped.rename(columns={"campaign_id": "active_campaigns"})

    # Calculate derived metrics
    grouped["acos"] = grouped.apply(
        lambda row: float(row["spend"] / row["sales"]) if row["sales"] > 0 else 0.0, axis=1
    )
    grouped["roas"] = grouped.apply(
        lambda row: float(row["sales"] / row["spend"]) if row["spend"] > 0 else 0.0, axis=1
    )
    grouped["cpc"] = grouped.apply(
        lambda row: float(row["spend"] / row["clicks"]) if row["clicks"] > 0 else 0.0, axis=1
    )
    grouped["ctr"] = grouped.apply(
        lambda row: float(row["clicks"] / row["impressions"]) if row["impressions"] > 0 else 0.0, axis=1
    )
    grouped["cvr"] = grouped.apply(
        lambda row: float(row["orders"] / row["clicks"]) if row["clicks"] > 0 else 0.0, axis=1
    )

    return [
        {
            "ad_type": str(row["product"]),
            "active_campaigns": int(row["active_campaigns"]),
            "spend": float(row["spend"]),
            "sales": float(row["sales"]),
            "impressions": float(row["impressions"]),
            "clicks": float(row["clicks"]),
            "orders": float(row["orders"]),
            "acos": float(row["acos"]),
            "roas": float(row["roas"]),
            "cpc": float(row["cpc"]),
            "ctr": float(row["ctr"]),
            "cvr": float(row["cvr"]),
        }
        for _, row in grouped.iterrows()
    ]
