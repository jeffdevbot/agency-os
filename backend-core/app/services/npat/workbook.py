from __future__ import annotations

import gc
import os
import re
import tempfile
from datetime import datetime
from typing import Dict, List

import pandas as pd

from .analytics import color_for_category


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _is_dark(hex_color: str) -> bool:
    """Determine if color is dark (for text contrast)."""
    r, g, b = _hex_to_rgb(hex_color)
    luma = 0.299 * r + 0.587 * g + 0.114 * b
    return luma < 140


def _quote_sheet_name(name: str) -> str:
    """Quote sheet name for Excel formulas."""
    escaped = name.replace("'", "''")
    return f"'{escaped}'"


def make_unique_sheet_name(name: str, used_lower: set) -> str:
    """Generate unique sheet name within Excel's 31-character limit."""
    name = re.sub(r"[:\\\/\?\*\[\]]", " ", str(name))
    name = re.sub(r"\s+", " ", name).strip() or "Sheet"
    base = name[:31]
    candidate = base
    i = 2
    while candidate.lower() in used_lower:
        suffix = f" ({i})"
        candidate = (base[: 31 - len(suffix)] + suffix)[:31]
        i += 1
    used_lower.add(candidate.lower())
    return candidate


def build_npat_workbook(campaign_items: List[Dict], app_version: str):
    """
    Generate N-PAT workbook with summary sheet and per-campaign ASIN analysis.

    Each campaign sheet includes:
    - Row 1: Campaign name
    - Row 2: ASIN pipe string formula for H10 lookup
    - Row 4: Column headers
    - Row 6+: Data rows with ASIN metrics, H10 paste zone, VLOOKUP enrichment

    campaign_items format:
    [
        {
            "campaign_name": str,
            "category_raw": str,
            "category_key": str,
            "asins": pd.DataFrame,  # From calculate_asin_metrics()
            "notes": list[str],
        },
        ...
    ]
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as out_tmp:
        out_path = out_tmp.name

    with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
        book = writer.book

        # Define formats
        header_fmt = book.add_format({
            "bg_color": "#0066CC",
            "font_color": "#FFFFFF",
            "bold": True,
            "border": 1,
            "align": "center",
            "valign": "vcenter"
        })
        grey_hdr_fmt = book.add_format({
            "bg_color": "#CCCCCC",
            "bold": True,
            "border": 1,
            "align": "center",
            "valign": "vcenter"
        })
        h10_zone_header_fmt = book.add_format({
            "bg_color": "#0066CC",
            "font_color": "#FFFFFF",
            "bold": True,
            "border": 1,
            "align": "left",
            "valign": "vcenter"
        })
        pipe_string_fmt = book.add_format({
            "bg_color": "#E6F2FF",
            "border": 5,
            "border_color": "#0066CC",
            "font_name": "Courier New",
            "align": "left"
        })
        bold_fmt = book.add_format({"bold": True})
        wrap_fmt = book.add_format({"text_wrap": True})
        pct_fmt = book.add_format({"num_format": "0.00%", "border": 1})
        currency_fmt = book.add_format({"num_format": "$#,##0.00", "border": 1})
        number_fmt = book.add_format({"num_format": "#,##0", "border": 1, "align": "center"})
        text_fmt = book.add_format({"border": 1, "align": "left"})
        zebra_fmt = book.add_format({"bg_color": "#F2F2F2", "border": 1})
        zebra_number_fmt = book.add_format({"bg_color": "#F2F2F2", "num_format": "#,##0", "border": 1, "align": "center"})
        zebra_currency_fmt = book.add_format({"bg_color": "#F2F2F2", "num_format": "$#,##0.00", "border": 1})
        zebra_pct_fmt = book.add_format({"bg_color": "#F2F2F2", "num_format": "0.00%", "border": 1})
        zebra_text_fmt = book.add_format({"bg_color": "#F2F2F2", "border": 1, "align": "left"})

        # Create Summary sheet
        summary_ws = book.add_worksheet("Summary")
        writer.sheets["Summary"] = summary_ws
        summary_ws.freeze_panes(1, 0)

        sum_headers = ["Campaign", "ASINs", "Total Spend", "Notes / Warnings"]
        hdr_fmt = book.add_format({
            "bold": True,
            "bg_color": "#F2F2F2",
            "border": 1,
            "align": "left",
            "valign": "vcenter"
        })
        for j, h in enumerate(sum_headers):
            summary_ws.write_string(0, j, h, hdr_fmt)

        text_left = book.add_format({"border": 1, "align": "left", "valign": "top"})
        text_left_wrap = book.add_format({"border": 1, "align": "left", "valign": "top", "text_wrap": True})
        count_center = book.add_format({"border": 1, "align": "center", "valign": "vcenter"})
        spend_fmt = book.add_format({"border": 1, "num_format": "$#,##0", "align": "right", "valign": "vcenter"})
        link_fmt_center = book.add_format({
            "border": 1,
            "align": "left",
            "valign": "vcenter",
            "color": "blue",
            "underline": 1
        })
        summary_zebra_fmt = book.add_format({"bg_color": "#FAFAFA"})

        summary_ws.set_column("A:A", 60)
        summary_ws.set_column("B:B", 12)
        summary_ws.set_column("C:C", 15)
        summary_ws.set_column("D:D", 60)

        runinfo_fmt = book.add_format({"italic": True, "font_color": "#666666"})
        summary_ws.write_string(0, 5, f"Generated: {datetime.now():%Y-%m-%d %H:%M}", runinfo_fmt)
        summary_ws.write_string(1, 5, f"Version: {app_version}", runinfo_fmt)

        # Generate unique sheet names
        row = 1
        sheet_name_map: Dict[str, str] = {}
        cat_color: Dict[str, str] = {}
        used_lower = set()
        for item in campaign_items:
            cat_color[item["category_key"]] = color_for_category(item["category_key"])
            sheet_name = make_unique_sheet_name(item["campaign_name"], used_lower)
            item["sheet_name"] = sheet_name
            sheet_name_map[item["campaign_name"]] = sheet_name

        # Write summary rows
        for item in campaign_items:
            cname = item["campaign_name"]
            cat_raw = item["category_raw"]
            asins_df = item["asins"]
            total_spend = asins_df["Spend"].sum() if not asins_df.empty else 0
            asin_count = len(asins_df)

            summary_ws.write_string(row, 0, str(cname), text_left)
            summary_ws.write_number(row, 1, asin_count, count_center)
            summary_ws.write_number(row, 2, total_spend, spend_fmt)
            notes_text = "; ".join(item["notes"]) if item["notes"] else ""
            summary_ws.write_string(row, 3, notes_text, text_left_wrap)
            row += 1

        # Create campaign sheets
        back_fmt = book.add_format({"color": "#666666", "italic": True, "underline": 1})

        for item in campaign_items:
            sheet_name = item["sheet_name"]
            ws = book.add_worksheet(sheet_name)
            ws.set_tab_color(cat_color[item["category_key"]])

            # Row 1: Campaign name
            ws.write_string(0, 0, "Campaign:", bold_fmt)
            ws.write_string(0, 1, str(item["campaign_name"]), wrap_fmt)
            ws.set_row(0, 24)
            ws.set_column(1, 1, 60)

            # Row 2: Back to Summary link
            ws.write_url(1, 0, "internal:'Summary'!A1", back_fmt, "← Back to Summary")

            # Row 3: ASIN pipe string (pre-computed in Python, not a formula)
            ws.write_string(2, 0, "ASINs for H10:", bold_fmt)
            # Generate pipe-delimited ASIN string from data
            asins_df = item["asins"]
            asin_list = asins_df["ASIN"].tolist()
            asin_pipe_string = "|".join(asin_list)
            ws.write_string(2, 1, asin_pipe_string, pipe_string_fmt)

            # Row 4: Blank

            # Row 5: Explanation texts
            vlookup_explain_fmt = book.add_format({"italic": True, "font_size": 9, "font_color": "#666666", "align": "left"})
            h10_explain_fmt = book.add_format({"italic": True, "font_size": 9, "font_color": "#666666", "align": "left"})
            ws.write_string(4, 10, "← Auto-calculated from H10 data →", vlookup_explain_fmt)
            ws.write_string(4, 16, "← Paste H10 ASIN Grabber CSV here (copy B3 → search Amazon → run H10 → paste)", h10_explain_fmt)

            # Row 6: Column headers
            main_headers = [
                "ASIN",  # A
                "Impression",  # B
                "Click",  # C
                "Spend",  # D
                "Order 14d",  # E
                "Sales 14d",  # F
                "CTR",  # G
                "CVR",  # H
                "CPC",  # I
                "ACOS",  # J
            ]

            vlookup_headers = [
                "Product Details",  # K
                "URL",  # L
                "Price $",  # M
                "BSR",  # N
                "Ratings",  # O
                "Review Count",  # P
            ]

            h10_paste_headers = [
                "Product Details",  # Q
                "ASIN",  # R
                "URL",  # S
                "Image URL",  # T
                "Brand",  # U
                "Origin",  # V
                "Price $",  # W
                "BSR",  # X
                "Ratings",  # Y
                "Review Count",  # Z
            ]

            action_headers = [
                "NE/NP",  # AA
                "Comments",  # AB
            ]

            # Write main headers (A-J) - blue background
            for j, h in enumerate(main_headers):
                ws.write_string(5, j, h, header_fmt)

            # Create format for VLOOKUP headers (slightly different color)
            vlookup_header_fmt = book.add_format({
                "bg_color": "#4A90E2",  # Lighter blue
                "font_color": "#FFFFFF",
                "bold": True,
                "border": 1,
                "align": "center",
                "valign": "vcenter"
            })

            # Write VLOOKUP headers (K-P) - lighter blue background
            for j, h in enumerate(vlookup_headers):
                ws.write_string(5, 10 + j, h, vlookup_header_fmt)

            # Write H10 paste zone headers (Q-Z) - blue background
            for j, h in enumerate(h10_paste_headers):
                ws.write_string(5, 16 + j, h, h10_zone_header_fmt)

            # Write action column headers (AA-AB) - grey background
            for j, h in enumerate(action_headers):
                ws.write_string(5, 26 + j, h, grey_hdr_fmt)

            # Row 7+: Data rows (start=6 because enumerate is 0-indexed, so first row is index 6 = Excel row 7)
            # Note: asins_df already loaded above for pipe string generation
            for i, row_data in enumerate(asins_df.itertuples(index=False), start=6):
                is_zebra = (i - 6) % 2 == 1

                # Columns A-J: Main ASIN metrics
                ws.write_string(i, 0, str(row_data.ASIN), zebra_text_fmt if is_zebra else text_fmt)
                ws.write_number(i, 1, float(row_data.Impression), zebra_number_fmt if is_zebra else number_fmt)
                ws.write_number(i, 2, float(row_data.Click), zebra_number_fmt if is_zebra else number_fmt)
                ws.write_number(i, 3, float(row_data.Spend), zebra_currency_fmt if is_zebra else currency_fmt)
                ws.write_number(i, 4, float(row_data[3]), zebra_number_fmt if is_zebra else number_fmt)  # Order 14d
                ws.write_number(i, 5, float(row_data[4]), zebra_currency_fmt if is_zebra else currency_fmt)  # Sales 14d
                ws.write_number(i, 6, float(row_data.CTR), zebra_pct_fmt if is_zebra else pct_fmt)
                ws.write_number(i, 7, float(row_data.CVR), zebra_pct_fmt if is_zebra else pct_fmt)
                ws.write_number(i, 8, float(row_data.CPC), zebra_currency_fmt if is_zebra else currency_fmt)
                ws.write_number(i, 9, float(row_data.ACOS), zebra_pct_fmt if is_zebra else pct_fmt)

                # Columns K-P: Auto-populated VLOOKUP fields (use INDEX/MATCH to lookup from H10 data)
                # K: Product Details - =IFERROR(INDEX($Q$7:$Q$5000,MATCH($A7,$R$7:$R$5000,0)),"")
                ws.write_formula(i, 10, f'=IFERROR(INDEX($Q$7:$Q$5000,MATCH($A{i+1},$R$7:$R$5000,0)),"")', zebra_text_fmt if is_zebra else text_fmt)
                # L: URL - =IFERROR(INDEX($S$7:$S$5000,MATCH($A7,$R$7:$R$5000,0)),"")
                ws.write_formula(i, 11, f'=IFERROR(INDEX($S$7:$S$5000,MATCH($A{i+1},$R$7:$R$5000,0)),"")', zebra_text_fmt if is_zebra else text_fmt)
                # M: Price $ - =IFERROR(INDEX($W$7:$W$5000,MATCH($A7,$R$7:$R$5000,0)),"")
                ws.write_formula(i, 12, f'=IFERROR(INDEX($W$7:$W$5000,MATCH($A{i+1},$R$7:$R$5000,0)),"")', zebra_text_fmt if is_zebra else text_fmt)
                # N: BSR - =IFERROR(INDEX($X$7:$X$5000,MATCH($A7,$R$7:$R$5000,0)),"")
                ws.write_formula(i, 13, f'=IFERROR(INDEX($X$7:$X$5000,MATCH($A{i+1},$R$7:$R$5000,0)),"")', zebra_text_fmt if is_zebra else text_fmt)
                # O: Ratings - =IFERROR(INDEX($Y$7:$Y$5000,MATCH($A7,$R$7:$R$5000,0)),"")
                ws.write_formula(i, 14, f'=IFERROR(INDEX($Y$7:$Y$5000,MATCH($A{i+1},$R$7:$R$5000,0)),"")', zebra_text_fmt if is_zebra else text_fmt)
                # P: Review Count - =IFERROR(INDEX($Z$7:$Z$5000,MATCH($A7,$R$7:$R$5000,0)),"")
                ws.write_formula(i, 15, f'=IFERROR(INDEX($Z$7:$Z$5000,MATCH($A{i+1},$R$7:$R$5000,0)),"")', zebra_text_fmt if is_zebra else text_fmt)

                # Columns Q-Z: H10 paste zone (leave blank for user to paste H10 data)
                # User will paste: Product Details, ASIN, URL, Image URL, Brand, Origin, Price $, BSR, Ratings, Review Count

                # Columns AA-AB: Action columns (empty for user input)
                ws.write_string(i, 26, "", zebra_text_fmt if is_zebra else text_fmt)  # NE/NP
                ws.write_string(i, 27, "", zebra_text_fmt if is_zebra else text_fmt)  # Comments

            # Set column widths
            ws.set_column("A:A", 15)  # ASIN
            ws.set_column("B:F", 12)  # Metrics (Impression, Click, Spend, Order, Sales)
            ws.set_column("G:J", 10)  # Calculated metrics (CTR, CVR, CPC, ACOS)
            ws.set_column("K:K", 50)  # VLOOKUP: Product Details
            ws.set_column("L:L", 40)  # VLOOKUP: URL
            ws.set_column("M:M", 12)  # VLOOKUP: Price $
            ws.set_column("N:N", 12)  # VLOOKUP: BSR
            ws.set_column("O:O", 10)  # VLOOKUP: Ratings
            ws.set_column("P:P", 12)  # VLOOKUP: Review Count
            ws.set_column("Q:Q", 50)  # H10: Product Details
            ws.set_column("R:R", 15)  # H10: ASIN
            ws.set_column("S:S", 40)  # H10: URL
            ws.set_column("T:T", 40)  # H10: Image URL
            ws.set_column("U:U", 20)  # H10: Brand
            ws.set_column("V:V", 15)  # H10: Origin
            ws.set_column("W:W", 12)  # H10: Price $
            ws.set_column("X:X", 12)  # H10: BSR
            ws.set_column("Y:Y", 10)  # H10: Ratings
            ws.set_column("Z:Z", 12)  # H10: Review Count
            ws.set_column("AA:AA", 10)  # NE/NP
            ws.set_column("AB:AB", 30)  # Comments

            # Freeze panes at row 6 (headers always visible)
            ws.freeze_panes(6, 0)

            # Set zoom
            ws.set_zoom(90)

        # Add links from summary to campaign sheets
        last_data_row = len(campaign_items)
        r = 1
        for item in campaign_items:
            sname = sheet_name_map[item["campaign_name"]]
            summary_ws.write_url(r, 0, f"internal:{_quote_sheet_name(sname)}!A1", link_fmt_center, item["campaign_name"])
            if r % 2 == 0:
                summary_ws.set_row(r, None, summary_zebra_fmt)
            r += 1

        summary_ws.autofilter(0, 0, last_data_row, len(sum_headers) - 1)

    gc.collect()
    return out_path
