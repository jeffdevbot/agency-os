from __future__ import annotations

import hashlib
import re
from typing import List

import numpy as np
import pandas as pd

# Color palette for category visualization (same as N-Gram)
PALETTE = [
    "#4C78A8",
    "#F58518",
    "#54A24B",
    "#EECA3B",
    "#B279A2",
    "#FF9DA6",
    "#9D755D",
    "#2978B5",
    "#8F8F8F",
    "#A0CBE8",
    "#FFBE7D",
    "#59A14F",
    "#F2CF5B",
    "#B6992D",
    "#AF7AA1",
    "#FF9DA7",
    "#D3D3D3",
    "#76B7B2",
    "#E15759",
    "#F28E2B",
]


def calculate_asin_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate per-ASIN metrics from Search Term Report data.

    Returns DataFrame with columns:
    - ASIN
    - Impression, Click, Spend, Order 14d, Sales 14d
    - CTR, CVR, CPC, ACOS (calculated)
    - NE/NP (empty, for user to fill)
    - Comments (empty, for user to fill)
    """
    cols_out = [
        "ASIN",
        "Impression",
        "Click",
        "Spend",
        "Order 14d",
        "Sales 14d",
        "CTR",
        "CVR",
        "CPC",
        "ACOS",
        "NE/NP",
        "Comments",
    ]

    if df.empty:
        return pd.DataFrame(columns=cols_out)

    # Group by ASIN (Query column contains ASINs after parser filtering)
    work = df[["Query", "Impression", "Click", "Spend", "Order 14d", "Sales 14d"]].copy()
    work = work.rename(columns={"Query": "ASIN"})

    # Aggregate metrics by ASIN
    grouped = work.groupby("ASIN", as_index=False).sum(numeric_only=True)

    # Calculate derived metrics with division-by-zero guards
    grouped["CTR"] = (grouped["Click"] / grouped["Impression"]).replace([np.inf, -np.inf], 0).fillna(0)
    grouped["CVR"] = (grouped["Order 14d"] / grouped["Click"]).replace([np.inf, -np.inf], 0).fillna(0)
    grouped["CPC"] = (grouped["Spend"] / grouped["Click"]).replace([np.inf, -np.inf], 0).fillna(0)
    grouped["ACOS"] = (grouped["Spend"] / grouped["Sales 14d"]).replace([np.inf, -np.inf], 0).fillna(0)

    # Add empty columns for user input
    grouped["NE/NP"] = ""
    grouped["Comments"] = ""

    # Sort by Click descending, then Sales 14d descending
    return (
        grouped[cols_out]
        .sort_values(["Click", "Sales 14d"], ascending=[False, False])
        .reset_index(drop=True)
    )


def derive_category(campaign_name: str):
    """
    Derive category from campaign name (same logic as N-Gram).

    Returns tuple: (category_raw, category_key, notes)

    Examples:
    - "Brand X - Product Targeting | Campaign ID" → "Product Targeting"
    - "Brand Y - Competitor" → "Competitor"
    - "Brand Z" → "Brand Z"
    """
    notes: List[str] = []
    s = str(campaign_name)
    parts = s.split("|", 1)
    if len(parts) == 1:
        notes.append("No `|` detected—category derived from full name.")
        left = s.strip()
    else:
        left = parts[0].strip()
    if " - " in left:
        category_raw = left.rsplit(" - ", 1)[-1].strip()
    else:
        notes.append("Used left chunk as category (no spaced hyphen).")
        category_raw = left.strip()
    category_key = re.sub(r"\s+", " ", category_raw).strip().lower()
    if not category_key:
        notes.append("Category empty; assigned '(uncategorized)'.")
        category_raw = "(uncategorized)"
        category_key = "(uncategorized)"
    return category_raw, category_key, notes


def color_for_category(category_key: str) -> str:
    """
    Generate consistent color for category using hash-based palette selection.
    Same category always gets same color.
    """
    h = hashlib.md5(category_key.encode("utf-8")).hexdigest()
    idx = int(h[:8], 16) % len(PALETTE)
    return PALETTE[idx]
