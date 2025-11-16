from __future__ import annotations

import io
import os
import re
import tempfile

import pandas as pd

NUMERIC_COLS = ["Impression", "Click", "Spend", "Order 14d", "Sales 14d"]
ASIN_RE = re.compile(r"^[a-z0-9]{10}$", re.I)


def clean_numeric(col: pd.Series) -> pd.Series:
    s = col.astype(str)
    s = s.str.replace(r"\(([^)]*)\)", r"-\1", regex=True)
    s = s.str.replace(",", "", regex=False).str.replace(" ", "", regex=False)
    s = s.str.replace(r"[^\d\.\-]", "", regex=True)
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


def _load_dataframe(buffer: bytes, file_name: str) -> pd.DataFrame:
    if file_name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(buffer), sheet_name=0, header=8)
    return pd.read_csv(io.BytesIO(buffer))


def _load_dataframe_path(path: str, original_name: str) -> pd.DataFrame:
    if original_name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(path, sheet_name=0, header=8)
    return pd.read_csv(path)


def read_backview(file_name: str, buf: bytes) -> pd.DataFrame:
    df = _load_dataframe(buf, file_name)
    return _normalize_columns(df)


def read_backview_path(path: str, original_name: str) -> pd.DataFrame:
    df = _load_dataframe_path(path, original_name)
    return _normalize_columns(df)


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", str(s).strip().lower())

    colmap = {}
    for col in df.columns:
        cl = norm(col)
        if cl in {"customer search term", "query", "search term", "customer_search_term"}:
            colmap[col] = "Query"
        elif cl in {"impression", "impressions"}:
            colmap[col] = "Impression"
        elif cl in {"click", "clicks"}:
            colmap[col] = "Click"
        elif "spend" in cl:
            colmap[col] = "Spend"
        elif cl in {"order 14d", "orders 14d", "14 day total orders (#)", "14 day total orders", "total orders 14d"}:
            colmap[col] = "Order 14d"
        elif cl in {"sales 14d", "14 day total sales", "14 day total sales (cad)", "14 day total sales (usd)"}:
            colmap[col] = "Sales 14d"
        elif cl in {"campaign name", "campaign", "campaignname"}:
            colmap[col] = "Campaign Name"

    df = df.rename(columns=colmap)
    needed = ["Query", "Impression", "Click", "Spend", "Order 14d", "Sales 14d", "Campaign Name"]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        seen = [str(x) for x in df.columns.tolist()]
        raise ValueError(f"Missing columns: {missing}. Saw columns: {seen[:12]}")

    for col in NUMERIC_COLS:
        df[col] = clean_numeric(df[col])

    df["Query"] = df["Query"].astype(str)
    df = df[df["Query"].str.strip().str.lower().str.match(ASIN_RE) == False]

    return df[needed]
