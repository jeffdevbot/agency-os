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

            # Row 3: ASIN pipe string formula
            ws.write_string(2, 0, "ASINs for H10:", bold_fmt)
            # Use _xlfn.TEXTJOIN prefix for Excel compatibility (older versions need this)
            ws.write_formula(2, 1, '=_xlfn.TEXTJOIN("|",TRUE,A7:A5000)', pipe_string_fmt)

            # Row 4: Blank

            # Row 5: Column headers
            headers = [
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
                "",  # K (spacer)
                "← Analysis | H10 Data →",  # L (separator)
                # H10 Paste Zone (M-V)
                "ASIN",  # M
                "Product Details",  # N
                "Brand",  # O
                "Price",  # P
                "Ratings",  # Q
                "Review Count",  # R
                "BSR",  # S
                "Origin",  # T
                "Image URL",  # U
                "Product URL",  # V
                # VLOOKUP Enrichment (W-AA)
                "Title",  # W
                "Brand",  # X
                "Price",  # Y
                "Rating",  # Z
                "Reviews",  # AA
                # Action columns (AB-AC)
                "NE/NP",  # AB
                "Comments",  # AC
            ]

            for j, h in enumerate(headers):
                if j < 10:  # Main metrics (A-J)
                    ws.write_string(4, j, h, header_fmt)
                elif j == 10:  # Spacer (K)
                    pass
                elif j == 11:  # Separator (L)
                    ws.write_string(4, j, h, grey_hdr_fmt)
                elif j >= 12 and j <= 21:  # H10 paste zone (M-V)
                    ws.write_string(4, j, h, h10_zone_header_fmt)
                elif j >= 22 and j <= 26:  # VLOOKUP enrichment (W-AA)
                    ws.write_string(4, j, h, header_fmt)
                elif j >= 27:  # Action columns (AB-AC)
                    ws.write_string(4, j, h, grey_hdr_fmt)

            # Row 6: Instructions for H10 paste zone
            ws.write_string(5, 12, "1. Copy ASIN string from B3 → 2. Search Amazon → 3. Run H10 ASIN Grabber → 4. Paste data here", text_fmt)

            # Row 7+: Data rows (start=6 because enumerate is 0-indexed, so first row is index 6 = Excel row 7)
            asins_df = item["asins"]
            for i, row_data in enumerate(asins_df.itertuples(index=False), start=6):
                is_zebra = (i - 6) % 2 == 1

                # Column A: ASIN
                ws.write_string(i, 0, str(row_data.ASIN), zebra_text_fmt if is_zebra else text_fmt)

                # Columns B-F: Metrics
                ws.write_number(i, 1, float(row_data.Impression), zebra_number_fmt if is_zebra else number_fmt)
                ws.write_number(i, 2, float(row_data.Click), zebra_number_fmt if is_zebra else number_fmt)
                ws.write_number(i, 3, float(row_data.Spend), zebra_currency_fmt if is_zebra else currency_fmt)
                ws.write_number(i, 4, float(row_data[3]), zebra_number_fmt if is_zebra else number_fmt)  # Order 14d
                ws.write_number(i, 5, float(row_data[4]), zebra_currency_fmt if is_zebra else currency_fmt)  # Sales 14d

                # Columns G-J: Calculated metrics
                ws.write_number(i, 6, float(row_data.CTR), zebra_pct_fmt if is_zebra else pct_fmt)
                ws.write_number(i, 7, float(row_data.CVR), zebra_pct_fmt if is_zebra else pct_fmt)
                ws.write_number(i, 8, float(row_data.CPC), zebra_currency_fmt if is_zebra else currency_fmt)
                ws.write_number(i, 9, float(row_data.ACOS), zebra_pct_fmt if is_zebra else pct_fmt)

                # Column K: Spacer (blank)

                # Column L: Separator (blank)

                # Columns M-V: H10 paste zone (user fills manually, leave blank)

                # Columns W-AA: VLOOKUP enrichment formulas
                # Title: =IFERROR(VLOOKUP($A7,$M$7:$V$5000,2,FALSE),"")
                ws.write_formula(i, 22, f'=IFERROR(VLOOKUP($A{i+1},$M$7:$V$5000,2,FALSE),"")', zebra_text_fmt if is_zebra else text_fmt)
                # Brand: =IFERROR(VLOOKUP($A7,$M$7:$V$5000,3,FALSE),"")
                ws.write_formula(i, 23, f'=IFERROR(VLOOKUP($A{i+1},$M$7:$V$5000,3,FALSE),"")', zebra_text_fmt if is_zebra else text_fmt)
                # Price: =IFERROR(VLOOKUP($A7,$M$7:$V$5000,4,FALSE),"")
                ws.write_formula(i, 24, f'=IFERROR(VLOOKUP($A{i+1},$M$7:$V$5000,4,FALSE),"")', zebra_text_fmt if is_zebra else text_fmt)
                # Rating: =IFERROR(VLOOKUP($A7,$M$7:$V$5000,5,FALSE),"")
                ws.write_formula(i, 25, f'=IFERROR(VLOOKUP($A{i+1},$M$7:$V$5000,5,FALSE),"")', zebra_text_fmt if is_zebra else text_fmt)
                # Reviews: =IFERROR(VLOOKUP($A7,$M$7:$V$5000,6,FALSE),"")
                ws.write_formula(i, 26, f'=IFERROR(VLOOKUP($A{i+1},$M$7:$V$5000,6,FALSE),"")', zebra_text_fmt if is_zebra else text_fmt)

                # Columns AB-AC: Action columns (empty for user input)
                ws.write_string(i, 27, "", zebra_text_fmt if is_zebra else text_fmt)  # NE/NP
                ws.write_string(i, 28, "", zebra_text_fmt if is_zebra else text_fmt)  # Comments

            # Set column widths
            ws.set_column("A:A", 15)  # ASIN
            ws.set_column("B:F", 12)  # Metrics
            ws.set_column("G:J", 10)  # Calculated metrics
            ws.set_column("K:K", 3)  # Spacer
            ws.set_column("L:L", 3)  # Separator
            ws.set_column("M:M", 15)  # H10 ASIN
            ws.set_column("N:N", 60)  # H10 Product Details
            ws.set_column("O:O", 20)  # H10 Brand
            ws.set_column("P:V", 12)  # H10 other data
            ws.set_column("W:W", 60)  # Enriched Title
            ws.set_column("X:X", 20)  # Enriched Brand
            ws.set_column("Y:AA", 12)  # Enriched other data
            ws.set_column("AB:AB", 10)  # NE/NP
            ws.set_column("AC:AC", 30)  # Comments

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
