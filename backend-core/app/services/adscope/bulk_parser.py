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
    "bidding_strategy": ["Bidding Strategy"],
    "percentage": ["Percentage"],
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
    """
    Check if column name matches any candidate (case-insensitive).
    Includes protections against false positives (e.g. "Cost Type" matching "Cost").
    """
    col_norm = _normalize_header(col_name)
    
    # First pass: exact match (normalized)
    for cand in candidates:
        cand_norm = _normalize_header(cand)
        if col_norm == cand_norm:
            return True

    # Second pass: substring matching with exclusions
    for cand in candidates:
        cand_norm = _normalize_header(cand)
        
        # Prevent "Cost Type" / "Cost Model" from matching "Cost" (spend)
        if cand_norm in ["cost", "spend"] and len(col_norm) > len(cand_norm):
            if "type" in col_norm or "model" in col_norm:
                continue
                
        # Prevent "Spend" from matching "ROAS" candidates (symmetric protection)
        if col_norm == "spend" and ("roas" in cand_norm or "return" in cand_norm):
            continue
            
        if cand_norm in col_norm or col_norm in cand_norm:
            return True
            
    return False



CAMPAIGN_TAB_PATTERNS = {
    "SP": ["Sponsored Products Campaigns", "Sponsored Products", "SP Campaigns"],
    "SB": ["Sponsored Brands Campaigns", "Sponsored Brands", "SB Campaigns"],
    "SD": ["Sponsored Display Campaigns", "Sponsored Display", "SD Campaigns"],
    # Lower priority fallbacks if we want to catch generic names
    "Generic": ["Bulk Sheet", "Search Terms"]
}


def identify_campaign_tabs(excel_file: pd.ExcelFile) -> list[str]:
    """
    Identify all relevant campaign tabs to process.
    
    Returns:
        List of sheet names.
    """
    sheet_names = excel_file.sheet_names
    selected_tabs = []
    
    # 1. Look for specific ad type tabs (SP, SB, SD)
    for ad_type, patterns in CAMPAIGN_TAB_PATTERNS.items():
        if ad_type == "Generic":
            continue
        for pattern in patterns:
            if pattern in sheet_names:
                selected_tabs.append(pattern)
                break # Only take the first match per ad type to avoid dupe processing if files vary
    
    # 2. If we found specific tabs, return them
    if selected_tabs:
        return selected_tabs
        
    # 3. Fallback: Generic names (only if no specific tabs found)
    for pattern in CAMPAIGN_TAB_PATTERNS["Generic"]:
        if pattern in sheet_names:
            return [pattern]
            
    # 4. Last Resort: Heuristic scan for ANY valid tab (same as before)
    # We return the first one that looks like a bulk sheet
    for sheet in sheet_names:
        try:
            df = excel_file.parse(sheet, nrows=5)
            columns = df.columns.tolist()
            
            has_entity = any(fuzzy_match_column(str(col), ["Entity", "Record Type"]) for col in columns)
            has_campaign = any(fuzzy_match_column(str(col), ["Campaign ID", "Campaign Name"]) for col in columns)
            
            if has_entity and has_campaign:
                return [sheet]
        except Exception:
            continue
            
    raise ValueError(
        f"Could not find any recognized campaign tabs. Available tabs: {sheet_names}"
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
    # Relaxed requirement: We might have partial data in some tabs, 
    # but we need at least Entity and Spend/Sales to be useful.
    # We will log warnings for missing cols instead of crashing hard on multi-tab.
    missing = [key for key in REQUIRED_BULK_COLUMNS if key not in column_map]
    if missing:
        found_cols = [str(c) for c in df_columns[:20]]
        # raise ValueError(
        #     f"Missing required Bulk columns: {missing}. Found columns: {found_cols}"
        # )
        # For now, let's keep raising error but maybe catch it in the loop
        pass 

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


def _process_single_sheet(
    df: pd.DataFrame, 
    sheet_name: str
) -> tuple[pd.DataFrame, list[str]]:
    """Process a single sheet: reheader, map columns, clean types."""
    warnings = []
    
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
                # Quick check if mapping works
                m = map_bulk_columns(reheadered)
                if all(k in m for k in ["entity", "spend"]): # Min viable
                    return reheadered
            except ValueError:
                continue
        return frame

    # 1. Map columns (try reheader if needed)
    try:
        col_map = map_bulk_columns(df)
        # If crucial columns missing, try reheader
        if "entity" not in col_map or "spend" not in col_map:
             df = _try_reheader(df)
             col_map = map_bulk_columns(df)
    except ValueError:
        df = _try_reheader(df)
        col_map = map_bulk_columns(df)

    # 2. Check required columns again
    missing = [key for key in REQUIRED_BULK_COLUMNS if key not in col_map]
    if missing:
        warnings.append(f"Sheet '{sheet_name}' skipped: Missing required columns {missing}")
        return pd.DataFrame(), warnings

    # 3. Rename
    rename_map = {v: k for k, v in col_map.items()}
    df = df.rename(columns=rename_map)

    # Clean Entity column (critical for filtering)
    if "entity" in df.columns:
        df["entity"] = df["entity"].astype(str).str.strip().str.title()

    # 4. Clean numerics
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

    # 5. Dates
    if "start_date" in df.columns:
        df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    if "end_date" in df.columns:
        df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")

    # 6. Add source tab info (optional, helpful for debug)
    df["_source_tab"] = sheet_name

    # 7. Backfill "product" column if missing (critical for Ad Type Mix)
    if "product" not in df.columns:
        # Infer from sheet name patterns
        normalized_sheet = sheet_name.lower()
        if "sponsored products" in normalized_sheet:
            df["product"] = "Sponsored Products"
        elif "sponsored brands" in normalized_sheet:
            df["product"] = "Sponsored Brands"
        elif "sponsored display" in normalized_sheet:
            df["product"] = "Sponsored Display"
    
    # 8. Backfill "entity" if missing (fallback specific to SD/SB sometimes)
    # If we are in a known campaign tab but Entity is missing, assume Campaign rows if they look like it
    # (Skipping for now to avoid over-engineering, focus on Product backfill)

    return df, warnings


def parse_bulk_file(
    excel_file: pd.ExcelFile,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Parse Bulk Operations Excel file (multi-tab).

    Args:
        excel_file: pd.ExcelFile object

    Returns:
        Tuple of (merged DataFrame, metadata dict with warnings and dates)
    """
    target_sheets = identify_campaign_tabs(excel_file)
    
    dfs = []
    all_warnings = [f"Processing tabs: {', '.join(target_sheets)}"]
    
    metadata = {}
    
    for sheet in target_sheets:
        try:
            raw_df = excel_file.parse(sheet)
            processed_df, sheet_warnings = _process_single_sheet(raw_df, sheet)
            
            if sheet_warnings:
                all_warnings.extend(sheet_warnings)
                
            if not processed_df.empty:
                dfs.append(processed_df)
                
                # Metadata extraction (best effort from first valid sheet)
                if "currency_code" not in metadata:
                    if "currency" in processed_df.columns:
                        vals = processed_df["currency"].dropna().unique()
                        if len(vals) > 0:
                            metadata["currency_code"] = str(vals[0])
        except Exception as e:
            all_warnings.append(f"Error processing sheet '{sheet}': {str(e)}")
            continue
            
    if not dfs:
        raise ValueError("No valid data found in any of the campaign tabs.")
        
    # Merge all
    final_df = pd.concat(dfs, ignore_index=True)
    
    # Global metadata
    if "start_date" in final_df.columns:
        metadata["bulk_start_date"] = final_df["start_date"].min()
    if "end_date" in final_df.columns:
        metadata["bulk_end_date"] = final_df["end_date"].max()
        
    if "currency_code" not in metadata:
        metadata["currency_code"] = "USD"
        
    metadata["warnings"] = all_warnings
    
    return final_df, metadata

