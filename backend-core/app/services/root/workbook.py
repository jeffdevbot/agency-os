"""Excel workbook generation for Root Keyword Analysis."""
from __future__ import annotations

import gc
import os
import tempfile
from typing import Any

import xlsxwriter

from .aggregate import HierarchyNode
from .weeks import WeekBucket


def build_root_workbook(
    nodes: list[HierarchyNode],
    week_buckets: list[WeekBucket],
    currency_symbol: str,
) -> str:
    """
    Build Excel workbook with hierarchical data and weekly metrics.

    Layout:
    - Single sheet with hierarchy in column A
    - Metric blocks (Clicks, Spend, CPC, Orders, Conversion Rate, Sales, ACoS)
    - Each metric has 4 weekly columns (most recent first)
    - 3-row header band: metric names (merged), Sunday date, Saturday date

    Args:
        nodes: List of HierarchyNode objects (already sorted)
        week_buckets: List of 4 WeekBucket objects (most recent first)
        currency_symbol: Currency symbol to use (€, £, or $)

    Returns:
        Path to generated Excel file
    """
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    tmp_path = tmp.name
    tmp.close()

    try:
        workbook = xlsxwriter.Workbook(tmp_path, {"nan_inf_to_errors": True})
        ws = workbook.add_worksheet("Root Keywords")

        # Define formats
        # Header band format (dark background, white text)
        header_fmt = workbook.add_format({
            "bold": True,
            "align": "center",
            "valign": "vcenter",
            "bg_color": "#3a3838",
            "font_color": "white",
            "border": 1,
        })

        # Date label formats (lighter background)
        date_fmt = workbook.add_format({
            "align": "center",
            "valign": "vcenter",
            "bg_color": "#666666",
            "font_color": "white",
            "border": 1,
            "font_size": 9,
        })

        # Zebra striping colors
        zebra_colors = ["#d9e1f2", "#fce4d6", "#ffffff"]

        # Format caches to avoid per-row format creation
        hierarchy_fmt_cache: dict[tuple[str, str], Any] = {}
        number_fmt_cache: dict[str, Any] = {}
        currency_fmt_cache: dict[str, Any] = {}
        percent_fmt_cache: dict[str, Any] = {}

        def get_hierarchy_fmt(bg_color: str, style: str):
            key = (bg_color, style)
            if key not in hierarchy_fmt_cache:
                fmt = {"align": "left", "valign": "vcenter", "bg_color": bg_color}
                if style == "bold":
                    fmt["bold"] = True
                elif style == "italic_bold":
                    fmt["bold"] = True
                    fmt["italic"] = True
                hierarchy_fmt_cache[key] = workbook.add_format(fmt)
            return hierarchy_fmt_cache[key]

        def get_number_fmt(bg_color: str):
            if bg_color not in number_fmt_cache:
                number_fmt_cache[bg_color] = workbook.add_format(
                    {"num_format": "#,##0", "align": "center", "bg_color": bg_color}
                )
            return number_fmt_cache[bg_color]

        def get_currency_fmt(bg_color: str):
            if bg_color not in currency_fmt_cache:
                currency_fmt_cache[bg_color] = workbook.add_format(
                    {"num_format": f"{currency_symbol}#,##0.00", "align": "center", "bg_color": bg_color}
                )
            return currency_fmt_cache[bg_color]

        def get_percent_fmt(bg_color: str):
            if bg_color not in percent_fmt_cache:
                percent_fmt_cache[bg_color] = workbook.add_format(
                    {"num_format": "0.00%", "align": "center", "bg_color": bg_color}
                )
            return percent_fmt_cache[bg_color]

        # Build header rows (rows 0-2)
        _build_header_rows(ws, workbook, week_buckets, header_fmt, date_fmt)

        # Set column widths
        ws.set_column(0, 0, 60)  # Column A: Hierarchy
        # Each metric has 4 weekly columns
        for col_idx in range(1, 1 + 7 * 4):  # 7 metrics × 4 weeks
            ws.set_column(col_idx, col_idx, 10)

        # Write data rows (starting from row 3)
        current_row = 3
        current_block = -1  # will increment on first AdType
        adtype_color_map: dict[tuple, str] = {}
        default_color = zebra_colors[0]

        for node in nodes:
            # Determine AdType block color
            adtype_path = tuple(node.full_path[:3]) if len(node.full_path) >= 3 else None
            if node.level == "AdType":
                current_block = (current_block + 1) % len(zebra_colors)
                adtype_color_map[adtype_path] = zebra_colors[current_block]

            if adtype_path and adtype_path in adtype_color_map:
                bg_color = adtype_color_map[adtype_path]
            else:
                bg_color = default_color

            # Determine hierarchy style
            if node.level in {"ProfileName", "PortfolioName"}:
                style = "bold"
            elif node.level == "AdType":
                style = "italic_bold"
            else:
                style = "normal"

            row_number_fmt = get_number_fmt(bg_color)
            row_currency_fmt = get_currency_fmt(bg_color)
            row_percent_fmt = get_percent_fmt(bg_color)
            row_hierarchy_fmt = get_hierarchy_fmt(bg_color, style)

            # Write hierarchy label
            ws.write_string(current_row, 0, node.get_display_label(), row_hierarchy_fmt)

            # Write metrics for each week (columns 1-28: 7 metrics × 4 weeks)
            # Metrics order: Clicks, Spend, CPC, Orders, Conversion Rate, Sales, ACoS
            col_idx = 1

            # For each metric block
            for metric_key, metric_format in [
                ("Click", row_number_fmt),
                ("Spend", row_currency_fmt),
                ("CPC", row_currency_fmt),
                ("Order14d", row_number_fmt),
                ("CVR", row_percent_fmt),
                ("Sales14d", row_currency_fmt),
                ("ACoS", row_percent_fmt),
            ]:
                # Write 4 weeks for this metric (most recent first: week 1, 2, 3, 4)
                for week_num in [1, 2, 3, 4]:
                    if week_num in node.metrics_by_week:
                        value = node.metrics_by_week[week_num].get(metric_key, 0.0)
                        ws.write_number(current_row, col_idx, value, metric_format)
                    else:
                        ws.write_number(current_row, col_idx, 0.0, metric_format)
                    col_idx += 1

            current_row += 1

        # Freeze panes (freeze header rows 0-2 and column A)
        ws.freeze_panes(3, 1)

        workbook.close()
        gc.collect()

        return tmp_path

    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        raise


def _build_header_rows(
    ws: Any,
    workbook: Any,
    week_buckets: list[WeekBucket],
    header_fmt: Any,
    date_fmt: Any,
):
    """
    Build the 3-row header band.

    Row 0: Metric names (merged across 4 weeks)
    Row 1: Sunday dates
    Row 2: Saturday dates
    """
    # Metric names in order
    metric_names = [
        "Clicks",
        "Spend",
        "$ CPC",
        "Orders",
        "Conversion Rate",
        "Sales",
        "ACoS",
    ]

    # Column A header
    ws.merge_range(0, 0, 2, 0, "Hierarchy", header_fmt)

    col_idx = 1

    # For each metric
    for metric_name in metric_names:
        # Merge metric name across 4 weeks (row 0)
        ws.merge_range(0, col_idx, 0, col_idx + 3, metric_name, header_fmt)

        # Write week dates (rows 1 and 2)
        for week_num in [1, 2, 3, 4]:
            bucket = week_buckets[week_num - 1]
            ws.write_string(1, col_idx, bucket.start_label, date_fmt)  # Sunday
            ws.write_string(2, col_idx, bucket.end_label, date_fmt)    # Saturday
            col_idx += 1

    # Add thin vertical borders between metric blocks
    # This is done by setting column widths with borders, but xlsxwriter doesn't support
    # column-level borders directly. We'll rely on the cell borders from the formats.
