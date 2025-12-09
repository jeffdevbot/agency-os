"""Bulk Operations Excel parser with multi-tab support and fuzzy column matching."""
from __future__ import annotations

from typing import Any
import pandas as pd


# Column mapping for Sponsored Products Campaigns tab
BULK_COLUMN_MAP = {
    "entity": ["Entity", "Record Type"],
    "product": ["Product", "Ad Product"],
    "campaign_id": ["Campaign ID"],
    "campaign_name": ["Campaign Name"],
    "ad_group_id": ["Ad Group ID"],
    "ad_group_name": ["Ad Group Name"],
    "portfolio_name": ["Portfolio Name", "Portfolio Name (Informational only)"],
    "match_type": ["Match Type"],
    "keyword": ["Keyword Text", "Targeting Expression"],
    "spend": ["Spend", "Cost"],
    "sales": ["Sales", "7 Day Total Sales", "14 Day Total Sales"],
    "clicks": ["Clicks"],
    "impressions": ["Impressions"],
    "orders": ["Orders", "7 Day Total Orders (#)"],
    "state": ["State"],
    "daily_budget": ["Daily Budget"],
    "default_bid": ["Ad Group Default Bid"],
    "bid": ["Bid"],
    "asin": ["ASIN (Informational only)", "ASIN", "Ad ID"],
    "sku": ["SKU"],
    "targeting_type": ["Targeting Type"],
    "start_date": ["Start Date"],
    "end_date": ["End Date"],
    "currency": ["Currency", "Budget Currency Code"],
    "placement": ["Placement"],
}


REQUIRED_BULK_COLUMNS = [
    "entity",
    "campaign_id",
    "campaign_name",
    "spend",
    "sales",
]


PREFERRED_SP_TAB_NAMES = [
    "Sponsored Products Campaigns",
    "Sponsored Products",
    "SP Campaigns",
]

EXPLICIT_BULK_TAB_NAMES = [
    "Bulk Sheet",
    "Search Terms",
]


def _normalize_header(value: str) -> str:
    """Lowercase + strip non-alphanumerics for tolerant matching."""
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def fuzzy_match_column(col_name: str, candidates: list[str]) -> bool:
    """Check if column name matches any candidate (case-insensitive)."""
    col_norm = _normalize_header(col_name)
    for cand in candidates:
        cand_norm = _normalize_header(cand)
        if col_norm == cand_norm or cand_norm in col_norm or col_norm in cand_norm:
            return True
    return False


def select_bulk_tab(excel_file: pd.ExcelFile) -> tuple[str, list[str]]:
    """
    Select the best tab from Bulk Excel file.

    Returns:
        Tuple of (selected_sheet_name, warnings)
    """
    warnings = []
    sheet_names = excel_file.sheet_names

    # Prefer explicitly named Bulk/STR tabs if present
    for explicit in EXPLICIT_BULK_TAB_NAMES:
        if explicit in sheet_names:
            return explicit, warnings

    # Prefer Sponsored Products tab
    for preferred in PREFERRED_SP_TAB_NAMES:
        if preferred in sheet_names:
            return preferred, warnings

    # Heuristic: find tab with required columns
    for sheet in sheet_names:
        try:
            df = excel_file.parse(sheet, nrows=5)  # Read first 5 rows to check headers
            columns = df.columns.tolist()

            # Check if critical headers are present
            has_entity = any(fuzzy_match_column(str(col), ["Entity", "Record Type"]) for col in columns)
            has_campaign = any(fuzzy_match_column(str(col), ["Campaign ID", "Campaign Name"]) for col in columns)
            has_spend = any(fuzzy_match_column(str(col), ["Spend", "Cost"]) for col in columns)
            has_sales = any(fuzzy_match_column(str(col), ["Sales"]) for col in columns)

            if has_entity and has_campaign and has_spend and has_sales:
                warnings.append(f"Using tab '{sheet}' (detected critical columns)")
                return sheet, warnings
        except Exception:
            continue

    raise ValueError(
        f"Could not find a tab with required columns (Entity, Campaign ID/Name, Spend, Sales). "
        f"Available tabs: {sheet_names}"
    )


def map_bulk_columns(df: pd.DataFrame) -> dict[str, str]:
    """Map DataFrame columns to internal keys using fuzzy matching."""
    column_map = {}
    df_columns = df.columns.tolist()

    for internal_key, candidates in BULK_COLUMN_MAP.items():
        for df_col in df_columns:
            if fuzzy_match_column(str(df_col), candidates):
                column_map[internal_key] = df_col
                break

    # Check for required columns
    missing = [key for key in REQUIRED_BULK_COLUMNS if key not in column_map]
    if missing:
        found_cols = [str(c) for c in df_columns[:20]]
        raise ValueError(
            f"Missing required Bulk columns: {missing}. Found columns: {found_cols}"
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


def parse_bulk_file(
    excel_file: pd.ExcelFile,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Parse Bulk Operations Excel file.

    Args:
        excel_file: pd.ExcelFile object

    Returns:
        Tuple of (cleaned DataFrame, metadata dict with warnings and dates)
    """
    # Select correct tab
    sheet_name, warnings = select_bulk_tab(excel_file)

    # Read the sheet
    df = excel_file.parse(sheet_name)

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
                map_bulk_columns(reheadered)
                return reheadered
            except ValueError:
                continue
        return frame

    # Map columns
    try:
        col_map = map_bulk_columns(df)
    except ValueError:
        df = _try_reheader(df)
        col_map = map_bulk_columns(df)

    # Rename to internal keys
    rename_map = {v: k for k, v in col_map.items()}
    df = df.rename(columns=rename_map)

    # Clean numeric columns
    numeric_cols = ["spend", "sales", "clicks", "impressions"]
    if "orders" in df.columns:
        numeric_cols.append("orders")
    if "daily_budget" in df.columns:
        numeric_cols.append("daily_budget")
    if "default_bid" in df.columns:
        numeric_cols.append("default_bid")
    if "bid" in df.columns:
        numeric_cols.append("bid")

    for col in numeric_cols:
        if col in df.columns:
            df[col] = clean_numeric(df[col])

    # Parse dates if present
    metadata = {"warnings": warnings}

    if "start_date" in df.columns:
        df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
        metadata["bulk_start_date"] = df["start_date"].min()

    if "end_date" in df.columns:
        df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")
        metadata["bulk_end_date"] = df["end_date"].max()

    # Currency detection
    if "currency" in df.columns:
        currency_values = df["currency"].dropna().unique()
        if len(currency_values) > 0:
            if "currency_code" not in metadata:
                metadata["currency_code"] = str(currency_values[0])
        else:
            if "currency_code" not in metadata:
                metadata["currency_code"] = "USD"
    else:
        if "currency_code" not in metadata:
            metadata["currency_code"] = "USD"

    # Don't filter rows - preserve all entity types for later processing
    # (Campaign rows needed for budget, Ad Group for spend, Keyword for analysis, etc.)

    return df, metadata
