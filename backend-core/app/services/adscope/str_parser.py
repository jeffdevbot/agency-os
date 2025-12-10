"""Search Term Report (STR) parser with fuzzy column matching."""
from __future__ import annotations

import re
from typing import Any
import pandas as pd


# Column mapping: internal_key -> list of candidate header names
STR_COLUMN_MAP = {
    "search_term": ["Customer Search Term", "Query", "Search Term"],
    "spend": ["Spend", "Cost"],
    "sales": ["7 Day Total Sales", "Sales", "Total Sales", "Sales (7 day)"],
    "impressions": ["Impressions"],
    "clicks": ["Clicks"],
    "orders": ["7 Day Total Orders (#)", "Orders", "Total Orders (#)"],
    "match_type": ["Match Type"],
    "campaign_name": ["Campaign Name", "Campaign Name (Informational only)", "Campaign"],
    "ad_group_name": ["Ad Group Name", "Ad Group Name (Informational only)", "Ad Group"],
    "start_date": ["Start Date"],
    "end_date": ["End Date"],
    "currency": ["Currency", "Currency Code"],
    "ctr": ["Click-Thru Rate (CTR)", "Click-through Rate", "CTR"],
    "cpc": ["Cost Per Click (CPC)", "CPC"],
    "acos": ["Total Advertising Cost of Sales (ACOS)", "ACOS"],
    "roas": ["Total Return on Advertising Spend (ROAS)", "ROAS"],
    "conversion_rate": ["7 Day Conversion Rate", "Conversion Rate"],
}


REQUIRED_STR_COLUMNS = [
    "search_term",
    "spend",
    "sales",
    "impressions",
    "clicks",
    "match_type",
    "campaign_name",
]


def _normalize_header(value: str) -> str:
    """Lowercase + strip non-alphanumerics for tolerant matching."""
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def fuzzy_match_column(col_name: str, candidates: list[str]) -> bool:
    """Check if column name matches any candidate (tolerant case-insensitive)."""
    col_norm = _normalize_header(col_name)
    for cand in candidates:
        cand_norm = _normalize_header(cand)
        if col_norm == cand_norm or cand_norm in col_norm or col_norm in cand_norm:
            return True
    return False


def map_columns(df: pd.DataFrame) -> dict[str, str]:
    """Map DataFrame columns to internal keys using fuzzy matching."""
    column_map = {}
    df_columns = df.columns.tolist()

    for internal_key, candidates in STR_COLUMN_MAP.items():
        for df_col in df_columns:
            if fuzzy_match_column(df_col, candidates):
                column_map[internal_key] = df_col
                break

    # Extra spend detection: look for any column containing "spend" but not ROAS/ACOS
    if "spend" not in column_map:
        for df_col in df_columns:
            norm = _normalize_header(df_col)
            if "spend" in norm and "returnonadvertisingspend" not in norm and "roas" not in norm and "acos" not in norm:
                column_map["spend"] = df_col
                break

    # Check for required columns
    missing = [key for key in REQUIRED_STR_COLUMNS if key not in column_map]
    if missing:
        found_cols = [str(c) for c in df_columns[:15]]
        raise ValueError(
            f"Missing required STR columns: {missing}. Found columns: {found_cols}"
        )

    return column_map


def clean_numeric(series: pd.Series) -> pd.Series:
    """Clean numeric series: strip $, commas, handle non-numeric values."""
    # Convert to string first
    s = series.astype(str)

    # Replace common non-numeric values
    s = s.replace(["-", "NaN", "nan", "null", "None", ""], "0")

    # Remove currency symbols and commas
    s = s.str.replace("$", "", regex=False)
    s = s.str.replace("€", "", regex=False)
    s = s.str.replace("£", "", regex=False)
    s = s.str.replace(",", "", regex=False)
    s = s.str.replace(" ", "", regex=False)

    # Convert to numeric, coerce errors to 0
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


def tokenize_ngrams(text: str, n: int = 1) -> list[str]:
    """Tokenize search term into n-grams."""
    # Lowercase and split on whitespace
    words = text.lower().strip().split()

    if n == 1:
        return words
    elif n == 2:
        return [f"{words[i]} {words[i+1]}" for i in range(len(words) - 1)]
    else:
        return []


def parse_str_file(
    df: pd.DataFrame,
    brand_keywords: list[str] | None = None
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Parse Search Term Report DataFrame.

    Args:
        df: Raw DataFrame from CSV/Excel
        brand_keywords: Optional list of brand keywords for classification

    Returns:
        Tuple of (cleaned DataFrame, metadata dict)
    """
    def _try_reheader(frame: pd.DataFrame) -> pd.DataFrame:
        """Attempt to find the real header row within the first 15 rows."""
        max_scan = min(len(frame), 15)
        for idx in range(max_scan):
            header_candidate = [str(x) for x in frame.iloc[idx].tolist()]
            if all(h.strip() == "" for h in header_candidate):
                continue
            reheadered = frame.iloc[idx + 1 :].copy()
            reheadered.columns = header_candidate
            try:
                map_columns(reheadered)
                return reheadered
            except ValueError:
                continue
        return frame

    # Map columns, with header-row fallback
    try:
        col_map = map_columns(df)
    except ValueError:
        df = _try_reheader(df)
        col_map = map_columns(df)

    # Rename to internal keys
    rename_map = {v: k for k, v in col_map.items()}
    df = df.rename(columns=rename_map)

    # Fallback: if spend is still missing, try to find a column with "spend" in the name that is not ROAS/ACOS
    if "spend" not in df.columns:
        for col in df.columns:
            norm = _normalize_header(col)
            if "spend" in norm and "roas" not in norm and "acos" not in norm and "returnonadvertising" not in norm:
                df = df.rename(columns={col: "spend"})
                break

    # Clean numeric columns
    numeric_cols = ["spend", "sales", "impressions", "clicks"]
    if "orders" in df.columns:
        numeric_cols.append("orders")

    for col in numeric_cols:
        if col in df.columns:
            df[col] = clean_numeric(df[col])

    # Parse dates if present
    metadata = {}
    if "start_date" in df.columns:
        df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
        metadata["str_start_date"] = df["start_date"].min()

    if "end_date" in df.columns:
        df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")
        metadata["str_end_date"] = df["end_date"].max()

    # Currency detection
    if "currency" in df.columns:
        currency_values = df["currency"].dropna().unique()
        if len(currency_values) > 0:
            metadata["currency_code"] = str(currency_values[0])
        else:
            metadata["currency_code"] = "USD"
    else:
        metadata["currency_code"] = "USD"

    # Brand classification
    if brand_keywords:
        brand_pattern = "|".join([re.escape(kw.lower()) for kw in brand_keywords])
        df["is_branded"] = df["search_term"].str.lower().str.contains(
            brand_pattern, na=False, regex=True
        )
    else:
        df["is_branded"] = False

    # Add n-grams
    df["one_grams"] = df["search_term"].apply(lambda x: tokenize_ngrams(str(x), 1))
    df["two_grams"] = df["search_term"].apply(lambda x: tokenize_ngrams(str(x), 2))

    # Remove rows with empty search terms
    df = df[df["search_term"].astype(str).str.strip() != ""]

    return df, metadata
