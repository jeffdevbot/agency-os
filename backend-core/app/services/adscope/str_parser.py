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
    "product_targeting_expression": [
        "Product Targeting Expression",
        "Resolved Product Targeting Expression (Informational only)",
        "Targeting",
    ],
    "targeting": ["Targeting"],  # Auto campaigns use this field
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
    # Replace non-breaking spaces and other whitespace variants with regular space first
    normalized = str(value).replace("\xa0", " ").replace("\u00a0", " ").strip()
    # Then remove all non-alphanumerics
    return "".join(ch for ch in normalized.lower() if ch.isalnum())


def fuzzy_match_column(col_name: str, candidates: list[str]) -> bool:
    """Check if column name matches any candidate (tolerant case-insensitive)."""
    col_norm = _normalize_header(col_name)

    # First pass: exact matches only (highest priority)
    for cand in candidates:
        cand_norm = _normalize_header(cand)
        if col_norm == cand_norm:
            return True

    # Second pass: substring matching with exclusions to prevent false matches
    for cand in candidates:
        cand_norm = _normalize_header(cand)

        # Prevent "spend" from matching compound metrics containing "spend"
        # e.g., "Spend" should not match "Total Return on Advertising Spend (ROAS)"
        if cand_norm == "spend" and len(col_norm) > 5:
            if "return" in col_norm or "roas" in col_norm or "acos" in col_norm:
                continue
        # SYMMETRIC FIX: Prevent "Spend" column from matching compound "ROAS" candidate
        if col_norm == "spend" and len(cand_norm) > 5:
            if "return" in cand_norm or "roas" in cand_norm or "acos" in cand_norm:
                continue

        # Prevent "cost" from matching CPC or other cost-per-X metrics
        if cand_norm == "cost" and len(col_norm) > 4:
            if "perclick" in col_norm or "cpc" in col_norm or "per" in col_norm:
                continue
        # SYMMETRIC FIX: Prevent "Cost" column from matching compound "CPC" candidate
        if col_norm == "cost" and len(cand_norm) > 4:
             if "perclick" in cand_norm or "cpc" in cand_norm or "per" in cand_norm:
                continue

        # Prevent generic terms from matching overly specific compound metrics
        # e.g., "Cost" shouldn't match "Cost Per Click (CPC)"
        if len(cand_norm) <= 5 and len(col_norm) > len(cand_norm) * 2:
            # If candidate is short and column is much longer, check for specific metric terms
            specific_metric_terms = ["perclick", "cpc", "clickthru", "ctr", "perorder",
                                     "peracquisition", "rate"]
            if any(term in col_norm for term in specific_metric_terms):
                # Only match if candidate also has these terms
                if not any(term in cand_norm for term in specific_metric_terms):
                    continue

        if cand_norm in col_norm or col_norm in cand_norm:
            return True

    return False


def map_columns(df: pd.DataFrame, debug: bool = True) -> dict[str, str]:
    """Map DataFrame columns to internal keys using fuzzy matching."""
    column_map = {}
    df_columns = df.columns.tolist()

    if debug:
        # Log raw headers with repr() to show hidden characters
        print(f"[STR Parser] Raw column headers: {repr(df_columns)}")
        print(f"[STR Parser] Normalized headers:")
        for col in df_columns:
            print(f"  '{col}' -> '{_normalize_header(col)}'")

    for internal_key, candidates in STR_COLUMN_MAP.items():
        for df_col in df_columns:
            if fuzzy_match_column(df_col, candidates):
                column_map[internal_key] = df_col
                if debug and internal_key == "spend":
                    print(f"[STR Parser] Matched 'spend' to column '{df_col}'")
                break

    # Extra spend detection: look for any column containing "spend" but not ROAS/ACOS
    if "spend" not in column_map:
        if debug:
            print("[STR Parser] Spend not found in initial mapping, trying fallback...")
        for df_col in df_columns:
            norm = _normalize_header(df_col)
            if debug:
                print(f"  Checking '{df_col}' (normalized: '{norm}')")
            if "spend" in norm and "returnonadvertisingspend" not in norm and "roas" not in norm and "acos" not in norm and "advertisingcostofsales" not in norm:
                column_map["spend"] = df_col
                if debug:
                    print(f"[STR Parser] Fallback matched 'spend' to column '{df_col}'")
                break

    # Check for required columns
    missing = [key for key in REQUIRED_STR_COLUMNS if key not in column_map]
    if missing:
        # Build detailed error with raw and normalized headers
        header_debug = "\n".join([
            f"  '{col}' -> normalized: '{_normalize_header(col)}'"
            for col in df_columns[:20]
        ])
        raise ValueError(
            f"Missing required STR columns: {missing}\n"
            f"Raw columns with normalization (first 20):\n{header_debug}\n"
            f"Total columns: {len(df_columns)}"
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
        print(f"[STR Parser] Scanning first {max_scan} rows for header row...")

        # First, try to find a row that contains a spend-like header
        for idx in range(max_scan):
            header_candidate = [str(x) for x in frame.iloc[idx].tolist()]
            if all(h.strip() == "" for h in header_candidate):
                continue

            # Check if this row has a spend-like column
            has_spend = any(
                "spend" in _normalize_header(h) and
                "roas" not in _normalize_header(h) and
                "acos" not in _normalize_header(h)
                for h in header_candidate
            )

            if has_spend:
                print(f"[STR Parser] Found potential header row at index {idx} (has spend-like column)")
                reheadered = frame.iloc[idx + 1 :].copy()
                reheadered.columns = header_candidate
                try:
                    map_columns(reheadered, debug=True)
                    print(f"[STR Parser] Successfully mapped columns using row {idx} as header")
                    return reheadered
                except ValueError as e:
                    print(f"[STR Parser] Row {idx} mapping failed: {e}")
                    continue

        # Fallback: try any non-empty row
        print("[STR Parser] No spend-like header found, trying any non-empty row...")
        for idx in range(max_scan):
            header_candidate = [str(x) for x in frame.iloc[idx].tolist()]
            if all(h.strip() == "" for h in header_candidate):
                continue
            reheadered = frame.iloc[idx + 1 :].copy()
            reheadered.columns = header_candidate
            try:
                map_columns(reheadered, debug=True)
                print(f"[STR Parser] Successfully mapped columns using row {idx} as header")
                return reheadered
            except ValueError:
                continue

        print("[STR Parser] Could not find valid header row in first 15 rows")
        return frame

    # Map columns, with header-row fallback
    print("[STR Parser] Attempting initial column mapping...")
    try:
        col_map = map_columns(df, debug=True)
    except ValueError as e:
        print(f"[STR Parser] Initial mapping failed: {e}")
        print("[STR Parser] Trying header row detection...")
        df = _try_reheader(df)
        col_map = map_columns(df, debug=True)

    print(f"[STR Parser] Column mapping successful: {col_map}")

    # Rename to internal keys
    rename_map = {v: k for k, v in col_map.items()}
    df = df.rename(columns=rename_map)

    # Final spend verification and fallback
    if "spend" not in df.columns:
        print("[STR Parser] WARNING: spend column still missing after rename, trying final fallback...")
        print(f"[STR Parser] Current columns: {df.columns.tolist()}")
        for col in df.columns:
            norm = _normalize_header(col)
            print(f"  Checking '{col}' (normalized: '{norm}')")
            if "spend" in norm and "roas" not in norm and "acos" not in norm and "returnonadvertising" not in norm and "advertisingcostofsales" not in norm:
                print(f"[STR Parser] Final fallback matched 'spend' to column '{col}'")
                df = df.rename(columns={col: "spend"})
                break

        # If still not found, raise detailed error
        if "spend" not in df.columns:
            header_debug = "\n".join([
                f"  '{col}' -> normalized: '{_normalize_header(col)}'"
                for col in df.columns[:30]
            ])
            raise ValueError(
                f"CRITICAL: Spend column not found after all fallback attempts.\n"
                f"Final columns with normalization (first 30):\n{header_debug}\n"
                f"Total columns: {len(df.columns)}\n"
                f"Column mapping used: {col_map}"
            )

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
