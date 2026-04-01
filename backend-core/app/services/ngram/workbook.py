from __future__ import annotations

import gc
import os
import re
import tempfile
from datetime import datetime
from typing import Dict, List

import pandas as pd
from pandas.api.types import is_categorical_dtype, is_object_dtype, is_string_dtype

from .analytics import clean_query_str, color_for_category

START_ROW = 3
SCRATCHPAD_HEADERS = ["Monogram", "Bigram", "Trigram"]
SCRATCHPAD_BASE_COL = 51
AI_REVIEW_HEADERS = ["AI Recommendation", "AI Confidence", "AI Reason"]


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
        mono_range = f"{sheet_ref}!AZ$6:AZ$5000"
        bi_range = f"{sheet_ref}!BA$6:BA$5000"
        tri_range = f"{sheet_ref}!BB$6:BB$5000"
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


def make_unique_sheet_name(name: str, used_lower: set[str]) -> str:
    name = re.sub(r"[:\\\/\?\*\[\]]", " ", str(name))
    name = re.sub(r"\s+", " ", name).strip() or "Sheet"
    # Excel disallows sheet names that start/end with apostrophe.
    base = name[:31].strip("'").strip() or "Sheet"
    candidate = base
    i = 2
    while candidate.lower() in used_lower:
        suffix = f" ({i})"
        candidate = (base[: 31 - len(suffix)] + suffix)[:31]
        i += 1
    used_lower.add(candidate.lower())
    return candidate


def _normalize_prefill_values(values: list[str] | None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values or []:
        text = str(value or "").strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        out.append(text)
    return out


def _normalize_search_term_key(value: str | None) -> str:
    return str(value or "").strip().casefold()


def _normalize_exact_prefill_keys(values: list[str] | None) -> set[str]:
    return {
        _normalize_search_term_key(value)
        for value in values or []
        if _normalize_search_term_key(value)
    }


def _derive_review_prefills(
    campaign_reviews: Dict[str, Dict[str, str | None]] | None,
) -> tuple[dict[str, list[str]], set[str]]:
    direct_prefills = {"mono": [], "bi": [], "tri": []}
    exact_negative_keys: set[str] = set()

    for search_term_key, review in (campaign_reviews or {}).items():
        if str(review.get("recommendation") or "").strip().upper() != "NEGATE":
            continue

        cleaned_term = clean_query_str(search_term_key)
        token_count = len([token for token in cleaned_term.split(" ") if token])
        if token_count == 1:
            direct_prefills["mono"].append(cleaned_term)
        elif token_count == 2:
            direct_prefills["bi"].append(cleaned_term)
        elif token_count == 3:
            direct_prefills["tri"].append(cleaned_term)
        elif token_count > 3:
            exact_negative_keys.add(search_term_key)

    return direct_prefills, exact_negative_keys


def build_workbook(
    campaign_items: List[Dict],
    app_version: str,
    ai_prefills: Dict[str, Dict[str, List[str]]] | None = None,
    ai_term_reviews: Dict[str, Dict[str, Dict[str, str | None]]] | None = None,
    ai_summary: Dict[str, str | float | None] | None = None,
):
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
                fmt = grey_hdr_fmt if col in ("NE/NP", "Comments", *AI_REVIEW_HEADERS) else header_fmt
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
        if ai_summary:
            if ai_summary.get("preview_run_id"):
                summary_ws.write_string(2, 9, f"AI Preview Run: {ai_summary['preview_run_id']}", runinfo_fmt)
            if ai_summary.get("model"):
                summary_ws.write_string(3, 9, f"AI Model: {ai_summary['model']}", runinfo_fmt)
            if ai_summary.get("prompt_version"):
                summary_ws.write_string(4, 9, f"AI Prompt Version: {ai_summary['prompt_version']}", runinfo_fmt)
            if ai_summary.get("spend_threshold") is not None:
                summary_ws.write_string(5, 9, f"AI Threshold: {ai_summary['spend_threshold']}", runinfo_fmt)

        row = 1
        sheet_name_map: Dict[str, str] = {}
        cat_color: Dict[str, str] = {}
        used_lower = set()
        for item in campaign_items:
            cat_color[item["category_key"]] = color_for_category(item["category_key"])
            sheet_name = make_unique_sheet_name(item["campaign_name"], used_lower)
            item["sheet_name"] = sheet_name
            sheet_name_map[item["campaign_name"]] = sheet_name

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
            raw_with_ai = item["raw"].copy()
            campaign_prefills = ai_prefills.get(item["campaign_name"], {}) if ai_prefills else {}
            explicit_exact_negative_keys = _normalize_exact_prefill_keys(campaign_prefills.get("exact"))
            campaign_review_lookup = ai_term_reviews.get(item["campaign_name"], {}) if ai_term_reviews else {}
            review_prefills, derived_exact_negative_keys = _derive_review_prefills(campaign_review_lookup)
            exact_negative_keys = explicit_exact_negative_keys or derived_exact_negative_keys
            if exact_negative_keys:
                search_term_keys = raw_with_ai["Search Term"].map(lambda value: _normalize_search_term_key(str(value)))
                raw_with_ai["NE/NP"] = search_term_keys.map(lambda key: "NE" if key in exact_negative_keys else "")
            if campaign_review_lookup:
                search_terms = raw_with_ai["Search Term"].map(lambda value: _normalize_search_term_key(str(value)))
                raw_with_ai["AI Recommendation"] = search_terms.map(
                    lambda key: str(campaign_review_lookup.get(key, {}).get("recommendation") or "")
                )
                raw_with_ai["AI Confidence"] = search_terms.map(
                    lambda key: str(campaign_review_lookup.get(key, {}).get("confidence") or "")
                )
                raw_with_ai["AI Reason"] = search_terms.map(
                    lambda key: str(campaign_review_lookup.get(key, {}).get("reason_tag") or "")
                )
            else:
                raw_with_ai["AI Recommendation"] = ""
                raw_with_ai["AI Confidence"] = ""
                raw_with_ai["AI Reason"] = ""
            write_pretty_table(ws, col, "Search Term", raw_with_ai)

            for offset, label in enumerate(SCRATCHPAD_HEADERS):
                ws.write_string(START_ROW + 2, SCRATCHPAD_BASE_COL + offset, label, bold_fmt)

            for offset, key in enumerate(("mono", "bi", "tri")):
                merged_prefills = _normalize_prefill_values(
                    [*(campaign_prefills.get(key) or []), *review_prefills.get(key, [])]
                )
                for row_offset, gram in enumerate(merged_prefills):
                    ws.write_string(START_ROW + 3 + row_offset, SCRATCHPAD_BASE_COL + offset, gram)

            first_data_excel_row = START_ROW + 4
            for r_i in range(len(item["mono"])):
                excel_row = first_data_excel_row + r_i
                ws.write_formula(
                    (START_ROW + 3) + r_i,
                    mono_start_col + 10,
                    f'=IF(ISNUMBER(MATCH(A{excel_row},AZ:AZ,0)),"NP","")',
                )
            for r_i in range(len(item["bi"])):
                excel_row = first_data_excel_row + r_i
                ws.write_formula(
                    (START_ROW + 3) + r_i,
                    bigram_start_col + 10,
                    f'=IF(ISNUMBER(MATCH(N{excel_row},BA:BA,0)),"NP","")',
                )
            for r_i in range(len(item["tri"])):
                excel_row = first_data_excel_row + r_i
                ws.write_formula(
                    (START_ROW + 3) + r_i,
                    trigram_start_col + 10,
                    f'=IF(ISNUMBER(MATCH(AA{excel_row},BB:BB,0)),"NP","")',
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
