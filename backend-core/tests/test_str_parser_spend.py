"""Test STR parser spend column detection with edge cases."""
import pandas as pd
import pytest
from app.services.adscope.str_parser import parse_str_file, _normalize_header


def test_normalize_header_with_non_breaking_space():
    """Test that non-breaking spaces are handled correctly."""
    # Non-breaking space (U+00A0)
    assert _normalize_header("Spend\xa0") == "spend"
    assert _normalize_header("\xa0Spend") == "spend"
    assert _normalize_header("Spend \xa0") == "spend"

    # Regular trailing space
    assert _normalize_header("Spend ") == "spend"
    assert _normalize_header(" Spend") == "spend"

    # Mixed whitespace
    assert _normalize_header(" Spend\xa0 ") == "spend"


def test_spend_column_with_non_breaking_space():
    """Test parsing when Spend column has non-breaking space."""
    # Create DataFrame with non-breaking space in Spend header
    df = pd.DataFrame({
        "Start Date": ["2024-01-01"],
        "End Date": ["2024-01-31"],
        "Campaign Name": ["Test Campaign"],
        "Ad Group Name": ["Test Ad Group"],
        "Customer Search Term": ["test keyword"],
        "Match Type": ["Exact"],
        "Impressions": [100],
        "Clicks": [10],
        "Spend\xa0": [50.0],  # Non-breaking space
        "7 Day Total Sales": [200.0],
    })

    result_df, metadata = parse_str_file(df)

    # Should successfully map spend column
    assert "spend" in result_df.columns
    assert result_df["spend"].iloc[0] == 50.0


def test_spend_column_with_trailing_space():
    """Test parsing when Spend column has trailing regular space."""
    df = pd.DataFrame({
        "Start Date": ["2024-01-01"],
        "End Date": ["2024-01-31"],
        "Campaign Name": ["Test Campaign"],
        "Ad Group Name": ["Test Ad Group"],
        "Customer Search Term": ["test keyword"],
        "Match Type": ["Exact"],
        "Impressions": [100],
        "Clicks": [10],
        "Spend ": [50.0],  # Trailing space
        "7 Day Total Sales": [200.0],
    })

    result_df, metadata = parse_str_file(df)

    assert "spend" in result_df.columns
    assert result_df["spend"].iloc[0] == 50.0


def test_spend_column_variations():
    """Test various valid spend column names."""
    test_cases = [
        "Spend",
        "spend",
        "SPEND",
        "Spend\xa0",  # Non-breaking space
        " Spend ",    # Regular spaces
        "Cost",       # Alternative name
    ]

    for spend_col_name in test_cases:
        df = pd.DataFrame({
            "Start Date": ["2024-01-01"],
            "End Date": ["2024-01-31"],
            "Campaign Name": ["Test Campaign"],
            "Ad Group Name": ["Test Ad Group"],
            "Customer Search Term": ["test keyword"],
            "Match Type": ["Exact"],
            "Impressions": [100],
            "Clicks": [10],
            spend_col_name: [50.0],
            "7 Day Total Sales": [200.0],
        })

        result_df, metadata = parse_str_file(df)
        assert "spend" in result_df.columns, f"Failed to map '{spend_col_name}' to spend"
        assert result_df["spend"].iloc[0] == 50.0


def test_spend_not_confused_with_roas():
    """Test that ROAS columns are not mistaken for Spend."""
    df = pd.DataFrame({
        "Start Date": ["2024-01-01"],
        "End Date": ["2024-01-31"],
        "Campaign Name": ["Test Campaign"],
        "Ad Group Name": ["Test Ad Group"],
        "Customer Search Term": ["test keyword"],
        "Match Type": ["Exact"],
        "Impressions": [100],
        "Clicks": [10],
        "Spend": [50.0],  # Real spend column
        "Total Return on Advertising Spend (ROAS)": [4.0],  # Should not be confused
        "7 Day Total Sales": [200.0],
    })

    result_df, metadata = parse_str_file(df)

    assert "spend" in result_df.columns
    assert result_df["spend"].iloc[0] == 50.0
    assert "roas" in result_df.columns
    assert result_df["roas"].iloc[0] == 4.0


def test_missing_spend_column_error():
    """Test that missing spend column raises clear error."""
    df = pd.DataFrame({
        "Start Date": ["2024-01-01"],
        "End Date": ["2024-01-31"],
        "Campaign Name": ["Test Campaign"],
        "Ad Group Name": ["Test Ad Group"],
        "Customer Search Term": ["test keyword"],
        "Match Type": ["Exact"],
        "Impressions": [100],
        "Clicks": [10],
        # No Spend column
        "7 Day Total Sales": [200.0],
    })

    with pytest.raises(ValueError) as exc_info:
        parse_str_file(df)

    error_msg = str(exc_info.value)
    assert "spend" in error_msg.lower()
    assert "Missing required STR columns" in error_msg or "CRITICAL" in error_msg
