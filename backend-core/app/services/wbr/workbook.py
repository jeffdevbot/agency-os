from __future__ import annotations

import gc
import os
import re
import tempfile
from dataclasses import dataclass
from typing import Any

import xlsxwriter
from supabase import Client

from .profiles import WBRNotFoundError
from .section1_report import Section1ReportService
from .section2_report import Section2ReportService
from .section3_report import Section3ReportService


@dataclass(frozen=True)
class MetricDefinition:
    key: str
    title: str
    kind: str


SECTION1_METRICS = [
    MetricDefinition("page_views", "Page Views", "integer"),
    MetricDefinition("unit_sales", "Unit Sales", "integer"),
    MetricDefinition("conversion_rate", "Conversion Rate", "percent"),
    MetricDefinition("sales", "Sales", "decimal"),
]

SECTION2_METRICS = [
    MetricDefinition("impressions", "Impressions", "integer"),
    MetricDefinition("clicks", "Clicks", "integer"),
    MetricDefinition("ctr_pct", "CTR", "percent"),
    MetricDefinition("ad_spend", "Ad Spend", "decimal"),
    MetricDefinition("cpc", "CPC", "decimal"),
    MetricDefinition("ad_orders", "Ad Orders", "integer"),
    MetricDefinition("ad_conversion_rate", "Ad CVR", "percent"),
    MetricDefinition("ad_sales", "Ad Sales", "decimal"),
    MetricDefinition("acos_pct", "ACoS", "percent"),
    MetricDefinition("tacos_pct", "TACoS", "percent"),
]


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def _sanitize_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return cleaned or "wbr"


def _section1_row_has_activity(row: dict[str, Any]) -> bool:
    return any(
        int(week.get("page_views") or 0) > 0
        or int(week.get("unit_sales") or 0) > 0
        or _to_float(week.get("sales")) > 0
        for week in row.get("weeks", [])
    )


def _section1_sort_key(row: dict[str, Any]) -> tuple[float, int, str]:
    page_views_total = sum(int(week.get("page_views") or 0) for week in row.get("weeks", []))
    return (-page_views_total, int(row.get("sort_order") or 0), str(row.get("row_label") or "").lower())


def _build_section1_display_rows(rows: list[dict[str, Any]], hide_empty_rows: bool) -> list[dict[str, Any]]:
    rows_to_display = [row for row in rows if _section1_row_has_activity(row)] if hide_empty_rows else list(rows)
    children_by_parent: dict[str, list[dict[str, Any]]] = {}
    roots: list[dict[str, Any]] = []
    for row in rows_to_display:
        parent_id = str(row.get("parent_row_id") or "").strip()
        if parent_id:
            children_by_parent.setdefault(parent_id, []).append(row)
        else:
            roots.append(row)

    roots.sort(key=_section1_sort_key)
    for children in children_by_parent.values():
        children.sort(key=_section1_sort_key)

    ordered: list[dict[str, Any]] = []
    for root in roots:
        ordered.append(root)
        ordered.extend(children_by_parent.get(str(root.get("id")), []))
    return ordered


def _section2_row_has_activity(row: dict[str, Any]) -> bool:
    return any(
        int(week.get("impressions") or 0) > 0
        or int(week.get("clicks") or 0) > 0
        or _to_float(week.get("ad_spend")) > 0
        or int(week.get("ad_orders") or 0) > 0
        or _to_float(week.get("ad_sales")) > 0
        for week in row.get("weeks", [])
    )


def _build_section2_display_rows(
    rows: list[dict[str, Any]], hide_empty_rows: bool, reference_row_order: list[str]
) -> list[dict[str, Any]]:
    rows_to_display = [row for row in rows if _section2_row_has_activity(row)] if hide_empty_rows else list(rows)
    order_map = {row_id: index for index, row_id in enumerate(reference_row_order)}

    def compare_key(row: dict[str, Any]) -> tuple[int, int, str]:
        reference_index = order_map.get(str(row.get("id")), 10**9)
        return (reference_index, int(row.get("sort_order") or 0), str(row.get("row_label") or "").lower())

    children_by_parent: dict[str, list[dict[str, Any]]] = {}
    roots: list[dict[str, Any]] = []
    for row in rows_to_display:
        parent_id = str(row.get("parent_row_id") or "").strip()
        if parent_id:
            children_by_parent.setdefault(parent_id, []).append(row)
        else:
            roots.append(row)

    roots.sort(key=compare_key)
    for children in children_by_parent.values():
        children.sort(key=compare_key)

    ordered: list[dict[str, Any]] = []
    for root in roots:
        ordered.append(root)
        ordered.extend(children_by_parent.get(str(root.get("id")), []))
    return ordered


def _section3_row_has_activity(row: dict[str, Any]) -> bool:
    return (
        int(row.get("instock") or 0) > 0
        or int(row.get("working") or 0) > 0
        or int(row.get("reserved_plus_fc_transfer") or 0) > 0
        or int(row.get("receiving_plus_intransit") or 0) > 0
        or int(row.get("returns_week_1") or 0) > 0
        or int(row.get("returns_week_2") or 0) > 0
    )


def _build_section3_display_rows(
    rows: list[dict[str, Any]], hide_empty_rows: bool, reference_row_order: list[str]
) -> list[dict[str, Any]]:
    rows_to_display = [row for row in rows if _section3_row_has_activity(row)] if hide_empty_rows else list(rows)
    order_map = {row_id: index for index, row_id in enumerate(reference_row_order)}

    def compare_key(row: dict[str, Any]) -> tuple[int, int, str]:
        reference_index = order_map.get(str(row.get("id")), 10**9)
        return (reference_index, int(row.get("sort_order") or 0), str(row.get("row_label") or "").lower())

    children_by_parent: dict[str, list[dict[str, Any]]] = {}
    roots: list[dict[str, Any]] = []
    for row in rows_to_display:
        parent_id = str(row.get("parent_row_id") or "").strip()
        if parent_id:
            children_by_parent.setdefault(parent_id, []).append(row)
        else:
            roots.append(row)

    roots.sort(key=compare_key)
    for children in children_by_parent.values():
        children.sort(key=compare_key)

    ordered: list[dict[str, Any]] = []
    for root in roots:
        ordered.append(root)
        ordered.extend(children_by_parent.get(str(root.get("id")), []))
    return ordered


def _build_section1_totals(rows: list[dict[str, Any]], weeks: list[dict[str, Any]]) -> dict[str, list[float]]:
    top_level_rows = [row for row in rows if not row.get("parent_row_id")]
    totals: dict[str, list[float]] = {metric.key: [] for metric in SECTION1_METRICS}
    for week_index in range(len(weeks)):
        page_views = sum(int(row["weeks"][week_index].get("page_views") or 0) for row in top_level_rows)
        unit_sales = sum(int(row["weeks"][week_index].get("unit_sales") or 0) for row in top_level_rows)
        sales = sum(_to_float(row["weeks"][week_index].get("sales")) for row in top_level_rows)

        totals["page_views"].append(float(page_views))
        totals["unit_sales"].append(float(unit_sales))
        totals["sales"].append(sales)
        totals["conversion_rate"].append(0.0 if page_views == 0 else unit_sales / page_views)
    return totals


def _build_section2_totals(rows: list[dict[str, Any]], weeks: list[dict[str, Any]]) -> dict[str, list[float]]:
    top_level_rows = [row for row in rows if not row.get("parent_row_id")]
    totals: dict[str, list[float]] = {metric.key: [] for metric in SECTION2_METRICS}
    for week_index in range(len(weeks)):
        impressions = sum(int(row["weeks"][week_index].get("impressions") or 0) for row in top_level_rows)
        clicks = sum(int(row["weeks"][week_index].get("clicks") or 0) for row in top_level_rows)
        ad_spend = sum(_to_float(row["weeks"][week_index].get("ad_spend")) for row in top_level_rows)
        ad_orders = sum(int(row["weeks"][week_index].get("ad_orders") or 0) for row in top_level_rows)
        ad_sales = sum(_to_float(row["weeks"][week_index].get("ad_sales")) for row in top_level_rows)
        business_sales = sum(_to_float(row["weeks"][week_index].get("business_sales")) for row in top_level_rows)

        totals["impressions"].append(float(impressions))
        totals["clicks"].append(float(clicks))
        totals["ctr_pct"].append(0.0 if impressions == 0 else clicks / impressions)
        totals["ad_spend"].append(ad_spend)
        totals["cpc"].append(0.0 if clicks == 0 else ad_spend / clicks)
        totals["ad_orders"].append(float(ad_orders))
        totals["ad_conversion_rate"].append(0.0 if clicks == 0 else ad_orders / clicks)
        totals["ad_sales"].append(ad_sales)
        totals["acos_pct"].append(0.0 if ad_sales == 0 else ad_spend / ad_sales)
        totals["tacos_pct"].append(0.0 if business_sales == 0 else ad_spend / business_sales)
    return totals


def _build_section3_totals(rows: list[dict[str, Any]], returns_weeks: list[dict[str, Any]], week_count: int) -> dict[str, float | None]:
    top_level_rows = [row for row in rows if not row.get("parent_row_id")]
    total_instock = sum(int(row.get("instock") or 0) for row in top_level_rows)
    total_reserved = sum(int(row.get("reserved_plus_fc_transfer") or 0) for row in top_level_rows)
    total_receiving = sum(int(row.get("receiving_plus_intransit") or 0) for row in top_level_rows)
    total_supply = total_instock + total_reserved + total_receiving
    total_unit_sales_4w = sum(int(row.get("_unit_sales_4w") or 0) for row in top_level_rows)
    avg_weekly_sales = total_unit_sales_4w / week_count if week_count > 0 else 0
    total_wos = None if avg_weekly_sales == 0 else round(total_supply / avg_weekly_sales)

    returns_window_count = len(returns_weeks) or 1
    total_returns_2w = sum(int(row.get("returns_week_1") or 0) + int(row.get("returns_week_2") or 0) for row in top_level_rows)
    total_unit_sales_2w = sum(int(row.get("_unit_sales_2w") or 0) for row in top_level_rows)
    avg_returns = total_returns_2w / returns_window_count
    avg_sales = total_unit_sales_2w / returns_window_count
    total_return_rate = None if avg_sales == 0 else avg_returns / avg_sales

    return {
        "instock": float(total_instock),
        "working": float(sum(int(row.get("working") or 0) for row in top_level_rows)),
        "reserved_plus_fc_transfer": float(total_reserved),
        "receiving_plus_intransit": float(total_receiving),
        "weeks_of_stock": total_wos,
        "returns_week_1": float(sum(int(row.get("returns_week_1") or 0) for row in top_level_rows)),
        "returns_week_2": float(sum(int(row.get("returns_week_2") or 0) for row in top_level_rows)),
        "return_rate": total_return_rate,
    }


def _write_style_cell(
    worksheet: Any,
    row_index: int,
    row: dict[str, Any],
    style_parent_fmt: Any,
    style_child_fmt: Any,
) -> None:
    row_label = str(row.get("row_label") or "")
    fmt = style_parent_fmt if row.get("row_kind") == "parent" else style_child_fmt
    worksheet.write_string(row_index, 0, row_label, fmt)


def build_wbr_workbook(
    section1_report: dict[str, Any],
    section2_report: dict[str, Any],
    section3_report: dict[str, Any],
    *,
    profile_display_name: str,
    marketplace_code: str,
    hide_empty_rows: bool = False,
    newest_first: bool = True,
) -> tuple[str, str]:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    tmp_path = tmp.name
    tmp.close()

    filename = f"{_sanitize_filename_part(profile_display_name)}-{_sanitize_filename_part(marketplace_code)}-wbr.xlsx"

    try:
        workbook = xlsxwriter.Workbook(tmp_path, {"nan_inf_to_errors": True})

        header_group_fmt = workbook.add_format(
            {
                "bold": True,
                "align": "center",
                "valign": "vcenter",
                "bg_color": "#3a3838",
                "font_color": "white",
                "border": 1,
            }
        )
        header_detail_fmt = workbook.add_format(
            {
                "bold": True,
                "align": "center",
                "valign": "vcenter",
                "bg_color": "#f7faff",
                "font_color": "#4c576f",
                "border": 1,
            }
        )
        style_parent_fmt = workbook.add_format({"bold": True, "align": "left", "valign": "vcenter", "border": 1})
        style_child_fmt = workbook.add_format({"align": "left", "valign": "vcenter", "border": 1, "indent": 1})
        total_label_fmt = workbook.add_format(
            {"bold": True, "align": "left", "valign": "vcenter", "border": 1, "bg_color": "#f8fafc"}
        )
        integer_fmt = workbook.add_format({"num_format": "#,##0", "align": "right", "border": 1})
        decimal_fmt = workbook.add_format({"num_format": "#,##0.00", "align": "right", "border": 1})
        percent_fmt = workbook.add_format({"num_format": "0.0%", "align": "right", "border": 1})
        whole_number_fmt = workbook.add_format({"num_format": "0", "align": "right", "border": 1})
        total_integer_fmt = workbook.add_format(
            {"num_format": "#,##0", "align": "right", "border": 1, "bold": True, "bg_color": "#f8fafc"}
        )
        total_decimal_fmt = workbook.add_format(
            {"num_format": "#,##0.00", "align": "right", "border": 1, "bold": True, "bg_color": "#f8fafc"}
        )
        total_percent_fmt = workbook.add_format(
            {"num_format": "0.0%", "align": "right", "border": 1, "bold": True, "bg_color": "#f8fafc"}
        )
        total_whole_number_fmt = workbook.add_format(
            {"num_format": "0", "align": "right", "border": 1, "bold": True, "bg_color": "#f8fafc"}
        )

        section1_rows = _build_section1_display_rows(section1_report.get("rows", []), hide_empty_rows)
        reference_row_order = [str(row.get("id")) for row in section1_rows]
        section2_rows = _build_section2_display_rows(section2_report.get("rows", []), hide_empty_rows, reference_row_order)
        section3_rows = _build_section3_display_rows(section3_report.get("rows", []), hide_empty_rows, reference_row_order)

        section1_weeks = list(section1_report.get("weeks", []))
        section2_weeks = list(section2_report.get("weeks", []))
        section3_returns_weeks = list(section3_report.get("returns_weeks", []))
        week_indexes_1 = list(range(len(section1_weeks)))
        week_indexes_2 = list(range(len(section2_weeks)))
        if newest_first:
            week_indexes_1.reverse()
            week_indexes_2.reverse()

        ws1 = workbook.add_worksheet("Traffic + Sales")
        _write_horizontal_metric_sheet(
            ws1,
            rows=section1_rows,
            weeks=section1_weeks,
            display_week_indexes=week_indexes_1,
            metrics=SECTION1_METRICS,
            totals=_build_section1_totals(section1_rows, section1_weeks),
            header_group_fmt=header_group_fmt,
            header_detail_fmt=header_detail_fmt,
            style_parent_fmt=style_parent_fmt,
            style_child_fmt=style_child_fmt,
            total_label_fmt=total_label_fmt,
            integer_fmt=integer_fmt,
            decimal_fmt=decimal_fmt,
            percent_fmt=percent_fmt,
            whole_number_fmt=whole_number_fmt,
            total_integer_fmt=total_integer_fmt,
            total_decimal_fmt=total_decimal_fmt,
            total_percent_fmt=total_percent_fmt,
            total_whole_number_fmt=total_whole_number_fmt,
        )

        ws2 = workbook.add_worksheet("Advertising")
        _write_horizontal_metric_sheet(
            ws2,
            rows=section2_rows,
            weeks=section2_weeks,
            display_week_indexes=week_indexes_2,
            metrics=SECTION2_METRICS,
            totals=_build_section2_totals(section2_rows, section2_weeks),
            header_group_fmt=header_group_fmt,
            header_detail_fmt=header_detail_fmt,
            style_parent_fmt=style_parent_fmt,
            style_child_fmt=style_child_fmt,
            total_label_fmt=total_label_fmt,
            integer_fmt=integer_fmt,
            decimal_fmt=decimal_fmt,
            percent_fmt=percent_fmt,
            whole_number_fmt=whole_number_fmt,
            total_integer_fmt=total_integer_fmt,
            total_decimal_fmt=total_decimal_fmt,
            total_percent_fmt=total_percent_fmt,
            total_whole_number_fmt=total_whole_number_fmt,
        )

        ws3 = workbook.add_worksheet("Inventory + Returns")
        _write_section3_sheet(
            ws3,
            rows=section3_rows,
            returns_weeks=section3_returns_weeks,
            totals=_build_section3_totals(section3_rows, section3_returns_weeks, len(section3_report.get("weeks", []))),
            header_detail_fmt=header_detail_fmt,
            style_parent_fmt=style_parent_fmt,
            style_child_fmt=style_child_fmt,
            total_label_fmt=total_label_fmt,
            integer_fmt=integer_fmt,
            percent_fmt=percent_fmt,
            whole_number_fmt=whole_number_fmt,
            total_integer_fmt=total_integer_fmt,
            total_percent_fmt=total_percent_fmt,
            total_whole_number_fmt=total_whole_number_fmt,
        )

        workbook.close()
        gc.collect()
        return tmp_path, filename
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        raise


def _metric_format(metric: MetricDefinition, integer_fmt: Any, decimal_fmt: Any, percent_fmt: Any, whole_number_fmt: Any) -> Any:
    if metric.kind == "integer":
        return integer_fmt
    if metric.kind == "decimal":
        return decimal_fmt
    if metric.kind == "percent":
        return percent_fmt
    return whole_number_fmt


def _total_metric_format(
    metric: MetricDefinition, total_integer_fmt: Any, total_decimal_fmt: Any, total_percent_fmt: Any, total_whole_number_fmt: Any
) -> Any:
    if metric.kind == "integer":
        return total_integer_fmt
    if metric.kind == "decimal":
        return total_decimal_fmt
    if metric.kind == "percent":
        return total_percent_fmt
    return total_whole_number_fmt


def _write_horizontal_metric_sheet(
    worksheet: Any,
    *,
    rows: list[dict[str, Any]],
    weeks: list[dict[str, Any]],
    display_week_indexes: list[int],
    metrics: list[MetricDefinition],
    totals: dict[str, list[float]],
    header_group_fmt: Any,
    header_detail_fmt: Any,
    style_parent_fmt: Any,
    style_child_fmt: Any,
    total_label_fmt: Any,
    integer_fmt: Any,
    decimal_fmt: Any,
    percent_fmt: Any,
    whole_number_fmt: Any,
    total_integer_fmt: Any,
    total_decimal_fmt: Any,
    total_percent_fmt: Any,
    total_whole_number_fmt: Any,
) -> None:
    worksheet.set_column(0, 0, 34)
    worksheet.merge_range(0, 0, 1, 0, "Style", header_group_fmt)

    col_index = 1
    for metric in metrics:
        worksheet.merge_range(0, col_index, 0, col_index + len(display_week_indexes) - 1, metric.title, header_group_fmt)
        for offset, week_index in enumerate(display_week_indexes):
            worksheet.write_string(1, col_index + offset, str(weeks[week_index].get("label") or ""), header_detail_fmt)
            worksheet.set_column(col_index + offset, col_index + offset, 13)
        col_index += len(display_week_indexes)

    row_index = 2
    for row in rows:
        _write_style_cell(worksheet, row_index, row, style_parent_fmt, style_child_fmt)
        col_index = 1
        for metric in metrics:
            fmt = _metric_format(metric, integer_fmt, decimal_fmt, percent_fmt, whole_number_fmt)
            for week_index in display_week_indexes:
                value = row.get("weeks", [])[week_index].get(metric.key)
                worksheet.write_number(row_index, col_index, _to_float(value), fmt)
                col_index += 1
        row_index += 1

    worksheet.write_string(row_index, 0, "Total", total_label_fmt)
    col_index = 1
    for metric in metrics:
        total_fmt = _total_metric_format(
            metric, total_integer_fmt, total_decimal_fmt, total_percent_fmt, total_whole_number_fmt
        )
        for week_index in display_week_indexes:
            worksheet.write_number(row_index, col_index, float(totals[metric.key][week_index]), total_fmt)
            col_index += 1

    worksheet.freeze_panes(2, 1)


def _write_section3_sheet(
    worksheet: Any,
    *,
    rows: list[dict[str, Any]],
    returns_weeks: list[dict[str, Any]],
    totals: dict[str, float | None],
    header_detail_fmt: Any,
    style_parent_fmt: Any,
    style_child_fmt: Any,
    total_label_fmt: Any,
    integer_fmt: Any,
    percent_fmt: Any,
    whole_number_fmt: Any,
    total_integer_fmt: Any,
    total_percent_fmt: Any,
    total_whole_number_fmt: Any,
) -> None:
    newest_returns_label = str(returns_weeks[-1].get("label") or "") if len(returns_weeks) >= 1 else ""
    older_returns_label = str(returns_weeks[-2].get("label") or "") if len(returns_weeks) >= 2 else ""
    headers = [
        "Style",
        "Instock",
        "Working",
        "Reserved / FC Transfer",
        "Receiving / Intransit",
        "Weeks of Stock",
        newest_returns_label,
        older_returns_label,
        "%",
    ]
    widths = [34, 12, 12, 20, 20, 14, 14, 14, 10]
    for col_index, (header, width) in enumerate(zip(headers, widths)):
        worksheet.write_string(0, col_index, header, header_detail_fmt)
        worksheet.set_column(col_index, col_index, width)

    row_index = 1
    for row in rows:
        _write_style_cell(worksheet, row_index, row, style_parent_fmt, style_child_fmt)
        worksheet.write_number(row_index, 1, float(int(row.get("instock") or 0)), integer_fmt)
        worksheet.write_number(row_index, 2, float(int(row.get("working") or 0)), integer_fmt)
        worksheet.write_number(row_index, 3, float(int(row.get("reserved_plus_fc_transfer") or 0)), integer_fmt)
        worksheet.write_number(row_index, 4, float(int(row.get("receiving_plus_intransit") or 0)), integer_fmt)
        worksheet.write_blank(row_index, 5, None, whole_number_fmt) if row.get("weeks_of_stock") is None else worksheet.write_number(
            row_index, 5, float(row.get("weeks_of_stock") or 0), whole_number_fmt
        )
        worksheet.write_number(row_index, 6, float(int(row.get("returns_week_1") or 0)), integer_fmt)
        worksheet.write_number(row_index, 7, float(int(row.get("returns_week_2") or 0)), integer_fmt)
        worksheet.write_blank(row_index, 8, None, percent_fmt) if row.get("return_rate") is None else worksheet.write_number(
            row_index, 8, float(row.get("return_rate") or 0), percent_fmt
        )
        row_index += 1

    worksheet.write_string(row_index, 0, "Total", total_label_fmt)
    worksheet.write_number(row_index, 1, float(totals.get("instock") or 0), total_integer_fmt)
    worksheet.write_number(row_index, 2, float(totals.get("working") or 0), total_integer_fmt)
    worksheet.write_number(row_index, 3, float(totals.get("reserved_plus_fc_transfer") or 0), total_integer_fmt)
    worksheet.write_number(row_index, 4, float(totals.get("receiving_plus_intransit") or 0), total_integer_fmt)
    if totals.get("weeks_of_stock") is None:
        worksheet.write_blank(row_index, 5, None, total_whole_number_fmt)
    else:
        worksheet.write_number(row_index, 5, float(totals.get("weeks_of_stock") or 0), total_whole_number_fmt)
    worksheet.write_number(row_index, 6, float(totals.get("returns_week_1") or 0), total_integer_fmt)
    worksheet.write_number(row_index, 7, float(totals.get("returns_week_2") or 0), total_integer_fmt)
    if totals.get("return_rate") is None:
        worksheet.write_blank(row_index, 8, None, total_percent_fmt)
    else:
        worksheet.write_number(row_index, 8, float(totals.get("return_rate") or 0), total_percent_fmt)

    worksheet.freeze_panes(1, 1)


class WbrWorkbookExportService:
    def __init__(self, db: Client) -> None:
        self.db = db
        self.section1 = Section1ReportService(db)
        self.section2 = Section2ReportService(db)
        self.section3 = Section3ReportService(db)

    def build_export(
        self,
        profile_id: str,
        *,
        weeks: int = 4,
        hide_empty_rows: bool = False,
        newest_first: bool = True,
    ) -> tuple[str, str]:
        profile = self._get_profile(profile_id)
        section1_report = self.section1.build_report(profile_id, weeks=weeks)
        section2_report = self.section2.build_report(profile_id, weeks=weeks)
        section3_report = self.section3.build_report(profile_id, weeks=weeks)
        return build_wbr_workbook(
            section1_report,
            section2_report,
            section3_report,
            profile_display_name=str(profile.get("display_name") or "wbr"),
            marketplace_code=str(profile.get("marketplace_code") or ""),
            hide_empty_rows=hide_empty_rows,
            newest_first=newest_first,
        )

    def _get_profile(self, profile_id: str) -> dict[str, Any]:
        response = self.db.table("wbr_profiles").select("*").eq("id", profile_id).limit(1).execute()
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise WBRNotFoundError(f"Profile {profile_id} not found")
        return rows[0]
