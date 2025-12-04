from __future__ import annotations

import gc
import os
import re
import tempfile
from datetime import datetime
from typing import Dict, List

import pandas as pd
from pandas.api.types import is_categorical_dtype, is_object_dtype, is_string_dtype

from .analytics import color_for_category

START_ROW = 3


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _is_dark(hex_color: str) -> bool:
    r, g, b = _hex_to_rgb(hex_color)
    luma = 0.299 * r + 0.587 * g + 0.114 * b
    return luma < 140


def _quote_sheet_name(name: str) -> str:
    escaped = name.replace("'", "''")
    return f"'{escaped}'"


def _excel_str_literal(text: str) -> str:
    # Escape double quotes for Excel formulas and wrap in quotes
    return '"' + str(text).replace('"', '""') + '"'


def _build_ne_summary_formula(sheet_infos: list[tuple[str, str]]) -> str:
    parts: list[str] = []
    for sheet_name, campaign_name in sheet_infos:
        sheet_ref = _quote_sheet_name(sheet_name)
        camp_literal = _excel_str_literal(campaign_name)
        # Bounded ranges to avoid Excel repair issues with full-column spills
        ne_term_range = f"{sheet_ref}!AN$6:AN$5000"
        ne_flag_range = f"{sheet_ref}!AT$6:AT$5000"
        mono_range = f"{sheet_ref}!AX$6:AX$5000"
        bi_range = f"{sheet_ref}!AY$6:AY$5000"
        tri_range = f"{sheet_ref}!AZ$6:AZ$5000"
        parts.append(
            f"FILTER(CHOOSE({{1,2,3,4,5}},"
            f"{camp_literal},{ne_term_range},\"\",\"\",\"\"),"
            f"({ne_flag_range}=\"NE\")*({ne_term_range}<>\"\"),\"\")"
        )
        parts.append(
            f"FILTER(CHOOSE({{1,2,3,4,5}},"
            f"{camp_literal},\"\",{mono_range},{bi_range},{tri_range}),"
            f"({mono_range}<>\"\")+({bi_range}<>\"\")+({tri_range}<>\"\"),\"\")"
        )
    if not parts:
        return '""'
    joined = ",".join(parts)
    return f"LET(_all,VSTACK({joined}),IF(ROWS(_all)=0,\"\",_all))"


def make_unique_sheet_name(name: str, used_lower: set) -> str:
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


def build_workbook(campaign_items: List[Dict], app_version: str):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as out_tmp:
        out_path = out_tmp.name

    with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
        book = writer.book

        header_fmt = book.add_format({"bg_color": "#FFCC99", "bold": False, "border": 1})
        grey_hdr_fmt = book.add_format({"bg_color": "#F2F2F2", "bold": True, "border": 1})
        title_fmt = book.add_format({"bold": True, "underline": True, "bottom": 2, "bottom_color": "#0077CC"})
        pct_fmt = book.add_format({"num_format": "0.00%"})
        two_dec_fmt = book.add_format({"num_format": "0.00"})
        bold_fmt = book.add_format({"bold": True})
        wrap_fmt = book.add_format({"text_wrap": True})
        back_fmt = book.add_format({"color": "#666666", "italic": True, "underline": 1})

        def write_pretty_table(ws, start_col: int, title: str, dfx: pd.DataFrame):
            ws.write_string(START_ROW + 0, start_col, title, title_fmt)
            cols = list(dfx.columns)
            text_columns: set[str] = set()
            for j, col in enumerate(cols):
                fmt = grey_hdr_fmt if col in ("NE/NP", "Comments") else header_fmt
                ws.write_string(START_ROW + 2, start_col + j, col, fmt)
                series = dfx[col]
                if (
                    is_string_dtype(series.dtype)
                    or is_object_dtype(series.dtype)
                    or is_categorical_dtype(series.dtype)
                    or col in {"N-gram", "Search Term", "Query"}
                ):
                    text_columns.add(col)
            for i, row in enumerate(dfx.itertuples(index=False), start=START_ROW + 3):
                for j, val in enumerate(row):
                    col_name = cols[j]
                    if col_name in ("CTR", "CVR", "ACOS"):
                        ws.write_number(i, start_col + j, float(val or 0), pct_fmt)
                    elif col_name == "CPC":
                        ws.write_number(i, start_col + j, float(val or 0), two_dec_fmt)
                    elif col_name in text_columns:
                        text_val = "" if pd.isna(val) else str(val)
                        ws.write_string(i, start_col + j, text_val)
                    else:
                        ws.write(i, start_col + j, val)
            return start_col + len(cols) + 1

        summary_ws = book.add_worksheet("Summary")
        writer.sheets["Summary"] = summary_ws
        summary_ws.freeze_panes(1, 2)

        sum_headers = [
            "Campaign",
            "Category",
            "Search Terms",
            "Monograms",
            "Bigrams",
            "Trigrams",
            "Notes / Warnings",
        ]

        hdr_fmt = book.add_format(
            {"bold": True, "bg_color": "#F2F2F2", "border": 1, "align": "left", "valign": "vcenter"}
        )
        for j, h in enumerate(sum_headers):
            summary_ws.write_string(0, j, h, hdr_fmt)

        text_left = book.add_format({"border": 1, "align": "left", "valign": "top"})
        text_left_wrap = book.add_format({"border": 1, "align": "left", "valign": "top", "text_wrap": True})
        count_center = book.add_format({"border": 1, "align": "center", "valign": "vcenter"})
        link_fmt_center = book.add_format({"border": 1, "align": "left", "valign": "vcenter", "color": "blue", "underline": 1})
        zebra_fmt = book.add_format({"bg_color": "#FAFAFA"})

        summary_ws.set_column("A:A", 60)
        summary_ws.set_column("B:B", 28)
        summary_ws.set_column("C:F", 13)
        summary_ws.set_column("G:G", 60)

        runinfo_fmt = book.add_format({"italic": True, "font_color": "#666666"})
        summary_ws.write_string(0, 9, f"Generated: {datetime.now():%Y-%m-%d %H:%M}", runinfo_fmt)
        summary_ws.write_string(1, 9, f"Version: {app_version}", runinfo_fmt)

        row = 1
        sheet_name_map: Dict[str, str] = {}
        cat_color: Dict[str, str] = {}
        used_lower = set()
        for item in campaign_items:
            cat_color[item["category_key"]] = color_for_category(item["category_key"])
            sheet_name = make_unique_sheet_name(item["campaign_name"], used_lower)
            item["sheet_name"] = sheet_name
            sheet_name_map[item["campaign_name"]] = sheet_name

        # NE Summary sheet immediately after Summary
        ne_summary_ws = book.add_worksheet("NE Summary")
        writer.sheets["NE Summary"] = ne_summary_ws
        ne_hdr_fmt = book.add_format(
            {"bold": True, "bg_color": "#0066CC", "font_color": "#FFFFFF", "border": 1, "align": "center", "valign": "vcenter"}
        )
        ne_cols = ["Campaign", "NE Keywords", "Monogram", "Bigram", "Trigram"]
        for j, col_name in enumerate(ne_cols):
            ne_summary_ws.write_string(0, j, col_name, ne_hdr_fmt)
        sheet_infos = [(item["sheet_name"], item["campaign_name"]) for item in campaign_items]
    ne_formula = _build_ne_summary_formula(sheet_infos)
    ne_summary_ws.write_formula(1, 0, ne_formula)
        ne_summary_ws.set_column("A:A", 50)
        ne_summary_ws.set_column("B:B", 60)
        ne_summary_ws.set_column("C:E", 30)
        ne_summary_ws.freeze_panes(1, 0)

        for item in campaign_items:
            cname = item["campaign_name"]
            cat_raw = item["category_raw"]
            color_hex = cat_color[item["category_key"]]
            font_color = "#FFFFFF" if _is_dark(color_hex) else "#000000"
            cat_fmt = book.add_format(
                {"border": 1, "align": "left", "valign": "vcenter", "bg_color": color_hex, "font_color": font_color, "bold": True}
            )
            summary_ws.write_string(row, 0, str(cname), text_left)
            summary_ws.write_string(row, 1, str(cat_raw), cat_fmt)
            summary_ws.write_number(row, 2, len(item["raw"]), count_center)
            summary_ws.write_number(row, 3, len(item["mono"]), count_center)
            summary_ws.write_number(row, 4, len(item["bi"]), count_center)
            summary_ws.write_number(row, 5, len(item["tri"]), count_center)
            notes_text = "; ".join(item["notes"]) if item["notes"] else ""
            summary_ws.write_string(row, 6, notes_text, text_left_wrap)
            sheet_name_map[cname] = item["sheet_name"]
            row += 1

        for item in campaign_items:
            sheet_name = item["sheet_name"]
            ws = book.add_worksheet(sheet_name)
            ws.set_tab_color(cat_color[item["category_key"]])
            ws.write_string(0, 0, "Campaign:", bold_fmt)
            ws.write_string(0, 1, str(item["campaign_name"]), wrap_fmt)
            ws.write_url(1, 0, "internal:'Summary'!A1", back_fmt, "← Back to Summary")
            ws.set_row(0, 24)
            ws.set_column(1, 1, 60)

            col = 0
            col = write_pretty_table(ws, col, "Monogram", item["mono"])
            mono_start_col = 0
            col = write_pretty_table(ws, col, "Bigram", item["bi"])
            bigram_start_col = 13
            col = write_pretty_table(ws, col, "Trigram", item["tri"])
            trigram_start_col = 26
            write_pretty_table(ws, col, "Search Term", item["raw"])

            placeholder_base_col = 49
            placeholder_headers = ["Monogram", "Bigram", "Trigram"]
            for offset, label in enumerate(placeholder_headers):
                ws.write_string(START_ROW + 2, placeholder_base_col + offset, label, bold_fmt)

            first_data_excel_row = START_ROW + 4
            for r_i in range(len(item["mono"])):
                excel_row = first_data_excel_row + r_i
                ws.write_formula(
                    (START_ROW + 3) + r_i,
                    mono_start_col + 10,
                    f'=IF(ISNUMBER(MATCH(A{excel_row},AX:AX,0)),"NP","")',
                )
            for r_i in range(len(item["bi"])):
                excel_row = first_data_excel_row + r_i
                ws.write_formula(
                    (START_ROW + 3) + r_i,
                    bigram_start_col + 10,
                    f'=IF(ISNUMBER(MATCH(N{excel_row},AY:AY,0)),"NP","")',
                )
            for r_i in range(len(item["tri"])):
                excel_row = first_data_excel_row + r_i
                ws.write_formula(
                    (START_ROW + 3) + r_i,
                    trigram_start_col + 10,
                    f'=IF(ISNUMBER(MATCH(AA{excel_row},AZ:AZ,0)),"NP","")',
                )

            ws.set_zoom(110)

        last_data_row = row - 1
        r = 1
        for item in campaign_items:
            sname = sheet_name_map[item["campaign_name"]]
            summary_ws.write_url(r, 0, f"internal:{_quote_sheet_name(sname)}!A1", link_fmt_center, item["campaign_name"])
            if r % 2 == 0:
                summary_ws.set_row(r, None, zebra_fmt)
            r += 1
        summary_ws.autofilter(0, 0, last_data_row, len(sum_headers) - 1)

    gc.collect()
    return out_path
