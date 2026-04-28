"""xlsx export for the Sales Mix report (mirrors WBR workbook style)."""

from __future__ import annotations

import re
import tempfile
from typing import Any

import xlsxwriter


def _sanitize_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", value or "report")
    cleaned = cleaned.strip("-")
    return cleaned or "report"


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def build_sales_mix_workbook(
    report: dict[str, Any],
    *,
    profile_display_name: str,
    marketplace_code: str,
) -> tuple[str, str]:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    tmp_path = tmp.name
    tmp.close()

    filename = (
        f"{_sanitize_filename_part(profile_display_name)}-"
        f"{_sanitize_filename_part(marketplace_code)}-"
        f"sales-mix-{report.get('date_from')}-to-{report.get('date_to')}.xlsx"
    )

    workbook = xlsxwriter.Workbook(tmp_path, {"nan_inf_to_errors": True})
    try:
        header_fmt = workbook.add_format(
            {
                "bold": True,
                "align": "center",
                "valign": "vcenter",
                "bg_color": "#3a3838",
                "font_color": "white",
                "border": 1,
            }
        )
        sub_header_fmt = workbook.add_format(
            {
                "bold": True,
                "align": "left",
                "valign": "vcenter",
                "bg_color": "#f7faff",
                "font_color": "#4c576f",
                "border": 1,
            }
        )
        label_fmt = workbook.add_format({"align": "left", "valign": "vcenter", "border": 1})
        bold_label_fmt = workbook.add_format(
            {"bold": True, "align": "left", "valign": "vcenter", "border": 1, "bg_color": "#f8fafc"}
        )
        decimal_fmt = workbook.add_format({"num_format": "#,##0.00", "align": "right", "border": 1})
        integer_fmt = workbook.add_format({"num_format": "#,##0", "align": "right", "border": 1})
        percent_fmt = workbook.add_format({"num_format": "0.0%", "align": "right", "border": 1})
        bold_decimal_fmt = workbook.add_format(
            {"num_format": "#,##0.00", "align": "right", "border": 1, "bold": True, "bg_color": "#f8fafc"}
        )
        bold_integer_fmt = workbook.add_format(
            {"num_format": "#,##0", "align": "right", "border": 1, "bold": True, "bg_color": "#f8fafc"}
        )
        bold_percent_fmt = workbook.add_format(
            {"num_format": "0.0%", "align": "right", "border": 1, "bold": True, "bg_color": "#f8fafc"}
        )

        _write_summary_sheet(
            workbook,
            report,
            profile_display_name=profile_display_name,
            marketplace_code=marketplace_code,
            header_fmt=header_fmt,
            sub_header_fmt=sub_header_fmt,
            label_fmt=label_fmt,
            bold_label_fmt=bold_label_fmt,
            decimal_fmt=decimal_fmt,
            integer_fmt=integer_fmt,
            percent_fmt=percent_fmt,
            bold_decimal_fmt=bold_decimal_fmt,
            bold_integer_fmt=bold_integer_fmt,
            bold_percent_fmt=bold_percent_fmt,
        )

        _write_weekly_sheet(
            workbook,
            report,
            header_fmt=header_fmt,
            label_fmt=label_fmt,
            decimal_fmt=decimal_fmt,
            integer_fmt=integer_fmt,
            percent_fmt=percent_fmt,
            bold_label_fmt=bold_label_fmt,
            bold_decimal_fmt=bold_decimal_fmt,
            bold_integer_fmt=bold_integer_fmt,
            bold_percent_fmt=bold_percent_fmt,
        )

        _write_ad_type_sheet(
            workbook,
            report,
            header_fmt=header_fmt,
            label_fmt=label_fmt,
            decimal_fmt=decimal_fmt,
            integer_fmt=integer_fmt,
        )

    finally:
        workbook.close()

    return tmp_path, filename


def _write_summary_sheet(
    workbook: Any,
    report: dict[str, Any],
    *,
    profile_display_name: str,
    marketplace_code: str,
    header_fmt: Any,
    sub_header_fmt: Any,
    label_fmt: Any,
    bold_label_fmt: Any,
    decimal_fmt: Any,
    integer_fmt: Any,
    percent_fmt: Any,
    bold_decimal_fmt: Any,
    bold_integer_fmt: Any,
    bold_percent_fmt: Any,
) -> None:
    worksheet = workbook.add_worksheet("Summary")
    worksheet.set_column(0, 0, 32)
    worksheet.set_column(1, 1, 20)

    worksheet.merge_range(0, 0, 0, 1, "Sales Mix", header_fmt)
    worksheet.write(1, 0, "Profile", sub_header_fmt)
    worksheet.write(1, 1, f"{profile_display_name} ({marketplace_code})", label_fmt)
    worksheet.write(2, 0, "Window", sub_header_fmt)
    worksheet.write(2, 1, f"{report.get('date_from')} → {report.get('date_to')}", label_fmt)
    worksheet.write(3, 0, "Weeks", sub_header_fmt)
    worksheet.write(3, 1, len(report.get("weeks", [])), integer_fmt)

    filters = report.get("filters", {}) or {}
    parent_options = {item["id"]: item.get("row_label") or item["id"] for item in report.get("parent_row_options", [])}
    parent_filter = filters.get("parent_row_ids") or []
    ad_filter = filters.get("ad_types") or []
    worksheet.write(4, 0, "Parent rows", sub_header_fmt)
    worksheet.write(
        4,
        1,
        ", ".join(parent_options.get(pid, pid) for pid in parent_filter) if parent_filter else "All",
        label_fmt,
    )
    worksheet.write(5, 0, "Ad types", sub_header_fmt)
    worksheet.write(5, 1, ", ".join(ad_filter) if ad_filter else "All", label_fmt)

    totals = report.get("totals") or {}
    rows = [
        ("Total business sales", "decimal", totals.get("business_sales")),
        ("Ad sales", "decimal", totals.get("ad_sales")),
        ("Organic sales", "decimal", totals.get("organic_sales")),
        ("Brand sales", "decimal", totals.get("brand_sales")),
        ("Category sales", "decimal", totals.get("category_sales")),
        ("Unmapped ad sales", "decimal", totals.get("unmapped_ad_sales")),
        ("Ad spend", "decimal", totals.get("ad_spend")),
        ("Ad orders", "integer", totals.get("ad_orders")),
        ("Ads share of business", "percent", totals.get("ads_share_of_business_pct")),
        ("Mapping coverage", "percent", totals.get("mapping_coverage_pct")),
    ]
    start_row = 7
    worksheet.merge_range(start_row, 0, start_row, 1, "Totals", sub_header_fmt)
    for offset, (label, kind, value) in enumerate(rows, start=start_row + 1):
        worksheet.write(offset, 0, label, bold_label_fmt)
        if kind == "decimal":
            worksheet.write_number(offset, 1, _to_float(value), bold_decimal_fmt)
        elif kind == "integer":
            worksheet.write_number(offset, 1, _to_float(value), bold_integer_fmt)
        elif kind == "percent":
            worksheet.write_number(offset, 1, _to_float(value), bold_percent_fmt)
        else:
            worksheet.write(offset, 1, value or "", label_fmt)

    coverage = report.get("coverage") or {}
    warn_rows = list(coverage.get("warnings") or [])
    if warn_rows:
        warn_start = start_row + len(rows) + 3
        worksheet.merge_range(warn_start, 0, warn_start, 1, "Coverage warnings", sub_header_fmt)
        for offset, message in enumerate(warn_rows, start=warn_start + 1):
            worksheet.merge_range(offset, 0, offset, 1, message, label_fmt)


def _write_weekly_sheet(
    workbook: Any,
    report: dict[str, Any],
    *,
    header_fmt: Any,
    label_fmt: Any,
    decimal_fmt: Any,
    integer_fmt: Any,
    percent_fmt: Any,
    bold_label_fmt: Any,
    bold_decimal_fmt: Any,
    bold_integer_fmt: Any,
    bold_percent_fmt: Any,
) -> None:
    worksheet = workbook.add_worksheet("Weekly")
    columns = [
        ("Week", "label"),
        ("Start", "label"),
        ("End", "label"),
        ("Business sales", "decimal"),
        ("Ad sales", "decimal"),
        ("Organic sales", "decimal"),
        ("Brand sales", "decimal"),
        ("Category sales", "decimal"),
        ("Unmapped ad sales", "decimal"),
        ("Ad spend", "decimal"),
        ("Ad orders", "integer"),
        ("Ads %", "percent"),
        ("Mapping coverage %", "percent"),
        ("Coverage warning", "label"),
    ]
    for index, (heading, _kind) in enumerate(columns):
        worksheet.write(0, index, heading, header_fmt)
    worksheet.set_column(0, 0, 28)
    worksheet.set_column(1, 2, 12)
    worksheet.set_column(3, 11, 16)
    worksheet.set_column(12, 13, 22)

    weekly = report.get("weekly") or []
    for row_index, week in enumerate(weekly, start=1):
        ad_sales = _to_float(week.get("ad_sales"))
        business_sales = _to_float(week.get("business_sales"))
        ads_pct = ad_sales / business_sales if business_sales > 0 else 0.0
        coverage = week.get("coverage") or {}
        coverage_pct = coverage.get("mapping_coverage_pct")
        coverage_pct_value = _to_float(coverage_pct) if coverage_pct is not None else 0.0
        warning = (
            "below threshold"
            if coverage.get("below_threshold")
            else ("no data" if not coverage.get("data_present") else "")
        )
        values = [
            week.get("label"),
            week.get("start"),
            week.get("end"),
            business_sales,
            ad_sales,
            _to_float(week.get("organic_sales")),
            _to_float(week.get("brand_sales")),
            _to_float(week.get("category_sales")),
            _to_float(week.get("unmapped_ad_sales")),
            _to_float(week.get("ad_spend")),
            _to_float(week.get("ad_orders")),
            ads_pct,
            coverage_pct_value,
            warning,
        ]
        for col_index, ((_heading, kind), value) in enumerate(zip(columns, values)):
            if kind == "label":
                worksheet.write(row_index, col_index, value or "", label_fmt)
            elif kind == "decimal":
                worksheet.write_number(row_index, col_index, _to_float(value), decimal_fmt)
            elif kind == "integer":
                worksheet.write_number(row_index, col_index, _to_float(value), integer_fmt)
            elif kind == "percent":
                worksheet.write_number(row_index, col_index, _to_float(value), percent_fmt)

    if weekly:
        totals = report.get("totals") or {}
        ad_sales = _to_float(totals.get("ad_sales"))
        business_sales = _to_float(totals.get("business_sales"))
        ads_pct = ad_sales / business_sales if business_sales > 0 else 0.0
        last_row = len(weekly) + 1
        worksheet.write(last_row, 0, "Totals", bold_label_fmt)
        worksheet.write(last_row, 1, "", bold_label_fmt)
        worksheet.write(last_row, 2, "", bold_label_fmt)
        worksheet.write_number(last_row, 3, business_sales, bold_decimal_fmt)
        worksheet.write_number(last_row, 4, ad_sales, bold_decimal_fmt)
        worksheet.write_number(last_row, 5, _to_float(totals.get("organic_sales")), bold_decimal_fmt)
        worksheet.write_number(last_row, 6, _to_float(totals.get("brand_sales")), bold_decimal_fmt)
        worksheet.write_number(last_row, 7, _to_float(totals.get("category_sales")), bold_decimal_fmt)
        worksheet.write_number(last_row, 8, _to_float(totals.get("unmapped_ad_sales")), bold_decimal_fmt)
        worksheet.write_number(last_row, 9, _to_float(totals.get("ad_spend")), bold_decimal_fmt)
        worksheet.write_number(last_row, 10, _to_float(totals.get("ad_orders")), bold_integer_fmt)
        worksheet.write_number(last_row, 11, ads_pct, bold_percent_fmt)
        coverage_total = totals.get("mapping_coverage_pct")
        worksheet.write_number(
            last_row,
            12,
            _to_float(coverage_total) if coverage_total is not None else 0.0,
            bold_percent_fmt,
        )
        worksheet.write(last_row, 13, "", bold_label_fmt)


def _write_ad_type_sheet(
    workbook: Any,
    report: dict[str, Any],
    *,
    header_fmt: Any,
    label_fmt: Any,
    decimal_fmt: Any,
    integer_fmt: Any,
) -> None:
    worksheet = workbook.add_worksheet("Ad Type Breakdown")
    worksheet.set_column(0, 0, 28)
    worksheet.set_column(1, 1, 22)
    worksheet.set_column(2, 4, 16)

    headings = ("Week", "Ad Type", "Ad sales", "Ad spend", "Ad orders")
    for index, heading in enumerate(headings):
        worksheet.write(0, index, heading, header_fmt)

    row_index = 1
    for week in report.get("weekly") or []:
        breakdown = week.get("ad_type_breakdown") or []
        for entry in breakdown:
            worksheet.write(row_index, 0, week.get("label") or "", label_fmt)
            worksheet.write(row_index, 1, entry.get("label") or entry.get("ad_type") or "", label_fmt)
            worksheet.write_number(row_index, 2, _to_float(entry.get("ad_sales")), decimal_fmt)
            worksheet.write_number(row_index, 3, _to_float(entry.get("ad_spend")), decimal_fmt)
            worksheet.write_number(row_index, 4, _to_float(entry.get("ad_orders")), integer_fmt)
            row_index += 1
