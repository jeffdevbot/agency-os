"""Parser for Campaign Report files (Root Keyword Analysis)."""
from __future__ import annotations

import io
import re
from typing import Any

import pandas as pd

# Required columns from Campaign Report (row 9 header, data starts row 10 in Excel = row 9 in pandas with header=8)
REQUIRED_COLS = [
    "Time",
    "CampaignName",
    "ProfileName",
    "PortfolioName",
    "Impression",
    "Click",
    "Spend",
    "Order14d",
    "SaleUnits14d",
    "Sales14d",
]

NUMERIC_COLS = ["Impression", "Click", "Spend", "Order14d", "SaleUnits14d", "Sales14d"]

# Currency symbols to detect before cleaning
CURRENCY_SYMBOLS = ["€", "£", "$"]


def clean_numeric(col: pd.Series) -> pd.Series:
    """Convert currency/numeric strings to floats, handling commas and parentheses."""
    s = col.astype(str)
    # Convert parentheses to negative: (100) → -100
    s = s.str.replace(r"\(([^)]*)\)", r"-\1", regex=True)
    # Remove commas and spaces
    s = s.str.replace(",", "", regex=False).str.replace(" ", "", regex=False)
    # Strip non-numeric chars except . and -
    s = s.str.replace(r"[^\d\.\-]", "", regex=True)
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


def detect_currency_symbol(df: pd.DataFrame) -> str:
    """
    Detect most frequent currency symbol in Spend column before numeric cleaning.
    Returns one of €, £, $ or defaults to €.
    """
    if "Spend" not in df.columns:
        return "€"

    # Sample first 100 rows to avoid performance hit on large files
    sample = df["Spend"].head(100).astype(str)

    counts = {}
    for symbol in CURRENCY_SYMBOLS:
        counts[symbol] = sample.str.contains(re.escape(symbol), regex=True).sum()

    # Pick most frequent, default to € if none found
    if max(counts.values()) == 0:
        return "€"

    return max(counts, key=counts.get)


def parse_campaign_name(campaign_name: Any) -> dict[str, str]:
    """
    Parse campaign name into hierarchy components using " | " delimiter.

    Format: Portfolio | Ad Type | Targeting | Sub-Type | Variant

    Rules:
    - Split by " | " (space-pipe-space)
    - If no pipe, treat whole string as Portfolio
    - Extra parts beyond position 4 are ignored
    - Underscores/hyphens within tokens are preserved
    - Handles NaN/None values by returning empty strings

    Returns dict with keys: Portfolio, AdType, Targeting, SubType, Variant
    """
    # Convert to string and handle NaN/None
    if campaign_name is None or (isinstance(campaign_name, float) and pd.isna(campaign_name)):
        campaign_name = ""
    else:
        campaign_name = str(campaign_name).strip()

    # If empty after conversion, return empty dict
    if not campaign_name:
        return {
            "Portfolio": "",
            "AdType": "",
            "Targeting": "",
            "SubType": "",
            "Variant": "",
        }

    parts = [p.strip() for p in campaign_name.split(" | ")]

    result = {
        "Portfolio": parts[0] if len(parts) > 0 else "",
        "AdType": parts[1] if len(parts) > 1 else "",
        "Targeting": parts[2] if len(parts) > 2 else "",
        "SubType": parts[3] if len(parts) > 3 else "",
        "Variant": parts[4] if len(parts) > 4 else "",
    }

    return result


def _load_dataframe(buffer: bytes, file_name: str) -> pd.DataFrame:
    """Load dataframe from buffer. Campaign Report has 8-row header."""
    if file_name.lower().endswith((".xlsx", ".xls")):
        # Header at row 9 in Excel = header=8 in pandas (0-indexed)
        return pd.read_excel(io.BytesIO(buffer), sheet_name=0, header=8)
    # CSV files typically don't have the 8-row header, assume header at row 0
    return pd.read_csv(io.BytesIO(buffer))


def _load_dataframe_path(path: str, original_name: str) -> pd.DataFrame:
    """Load dataframe from file path."""
    if original_name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(path, sheet_name=0, header=8)
    return pd.read_csv(path)


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names to standard set."""
    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", str(s).strip().lower())

    colmap = {}
    for col in df.columns:
        cl = norm(col)
        # Map various spellings to standard names
        if cl in {"time", "date", "datetime"}:
            colmap[col] = "Time"
        elif cl in {"campaignname", "campaign name", "campaign"}:
            colmap[col] = "CampaignName"
        elif cl in {"profilename", "profile name", "profile"}:
            colmap[col] = "ProfileName"
        elif cl in {"portfolioname", "portfolio name", "portfolio"}:
            colmap[col] = "PortfolioName"
        elif cl in {"impression", "impressions"}:
            colmap[col] = "Impression"
        elif cl in {"click", "clicks"}:
            colmap[col] = "Click"
        elif "spend" in cl:
            colmap[col] = "Spend"
        elif cl in {"order14d", "order 14d", "orders 14d", "14 day total orders (#)", "14 day total orders"}:
            colmap[col] = "Order14d"
        elif cl in {"saleunits14d", "sale units14d", "sale units 14d", "14 day total units"}:
            colmap[col] = "SaleUnits14d"
        elif cl in {"sales14d", "sales 14d", "14 day total sales"}:
            colmap[col] = "Sales14d"

    df = df.rename(columns=colmap)

    # Check for required columns
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        seen = [str(x) for x in df.columns.tolist()]
        raise ValueError(f"Missing required columns: {missing}. Found columns: {seen[:15]}")

    return df


def read_campaign_report(file_name: str, buf: bytes) -> tuple[pd.DataFrame, str]:
    """
    Read and parse Campaign Report from buffer.

    Returns:
        Tuple of (parsed dataframe, detected currency symbol)
    """
    df = _load_dataframe(buf, file_name)
    df = _normalize_columns(df)

    # Detect currency symbol BEFORE cleaning numeric columns
    currency_symbol = detect_currency_symbol(df)

    # Clean numeric columns
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = clean_numeric(df[col])

    # Parse Time column to datetime (UTC)
    df["Time"] = pd.to_datetime(df["Time"], errors="coerce", utc=True)

    # Parse campaign names into hierarchy components
    parsed_names = df["CampaignName"].apply(parse_campaign_name)
    df["Portfolio"] = parsed_names.apply(lambda x: x["Portfolio"])
    df["AdType"] = parsed_names.apply(lambda x: x["AdType"])
    df["Targeting"] = parsed_names.apply(lambda x: x["Targeting"])
    df["SubType"] = parsed_names.apply(lambda x: x["SubType"])
    df["Variant"] = parsed_names.apply(lambda x: x["Variant"])

    # Remove rows with invalid Time or empty campaign names
    df = df[df["Time"].notna()]
    df = df[df["Portfolio"].str.strip() != ""]

    return df, currency_symbol


def read_campaign_report_path(path: str, original_name: str) -> tuple[pd.DataFrame, str]:
    """
    Read and parse Campaign Report from file path.

    Returns:
        Tuple of (parsed dataframe, detected currency symbol)
    """
    df = _load_dataframe_path(path, original_name)
    df = _normalize_columns(df)

    # Detect currency symbol BEFORE cleaning numeric columns
    currency_symbol = detect_currency_symbol(df)

    # Clean numeric columns
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = clean_numeric(df[col])

    # Parse Time column to datetime (UTC)
    df["Time"] = pd.to_datetime(df["Time"], errors="coerce", utc=True)

    # Parse campaign names into hierarchy components
    parsed_names = df["CampaignName"].apply(parse_campaign_name)
    df["Portfolio"] = parsed_names.apply(lambda x: x["Portfolio"])
    df["AdType"] = parsed_names.apply(lambda x: x["AdType"])
    df["Targeting"] = parsed_names.apply(lambda x: x["Targeting"])
    df["SubType"] = parsed_names.apply(lambda x: x["SubType"])
    df["Variant"] = parsed_names.apply(lambda x: x["Variant"])

    # Remove rows with invalid Time or empty campaign names
    df = df[df["Time"].notna()]
    df = df[df["Portfolio"].str.strip() != ""]

    return df, currency_symbol
