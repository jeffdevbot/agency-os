from __future__ import annotations

import hashlib
import re
from typing import List

import numpy as np
import pandas as pd

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

TOKEN_RE = re.compile(r"[^\w\s-]+", re.UNICODE)


def clean_query_str(q: str) -> str:
    q = str(q).strip().lower()
    q = TOKEN_RE.sub(" ", q)
    q = re.sub(r"_+", " ", q)
    q = re.sub(r"-{2,}", "-", q)
    return re.sub(r"\s+", " ", q).strip()


def build_ngram(df: pd.DataFrame, n: int) -> pd.DataFrame:
    cols_out = [
        "N-gram",
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

    work = df[["Query", "Impression", "Click", "Spend", "Order 14d", "Sales 14d"]].copy()
    work["__tokens"] = work["Query"].map(clean_query_str).str.split()

    def row_ngrams(tokens: List[str]):
        length = len(tokens)
        if length < n:
            return []
        return [" ".join(tokens[i : i + n]) for i in range(length - n + 1)]

    work["N-gram"] = work["__tokens"].apply(row_ngrams)
    work = work.loc[
        work["N-gram"].str.len() > 0,
        ["N-gram", "Impression", "Click", "Spend", "Order 14d", "Sales 14d"],
    ]
    work = work.explode("N-gram", ignore_index=True)

    grouped = work.groupby("N-gram", as_index=False).sum(numeric_only=True)
    grouped["CTR"] = (grouped["Click"] / grouped["Impression"]).replace([np.inf, -np.inf], 0).fillna(0)
    grouped["CVR"] = (grouped["Order 14d"] / grouped["Click"]).replace([np.inf, -np.inf], 0).fillna(0)
    grouped["CPC"] = (grouped["Spend"] / grouped["Click"]).replace([np.inf, -np.inf], 0).fillna(0)
    grouped["ACOS"] = (grouped["Spend"] / grouped["Sales 14d"]).replace([np.inf, -np.inf], 0).fillna(0)
    grouped["NE/NP"] = ""
    grouped["Comments"] = ""

    return (
        grouped[cols_out]
        .sort_values(["Click", "Sales 14d"], ascending=[False, False])
        .reset_index(drop=True)
    )


def derive_category(campaign_name: str):
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
    h = hashlib.md5(category_key.encode("utf-8")).hexdigest()
    idx = int(h[:8], 16) % len(PALETTE)
    return PALETTE[idx]
