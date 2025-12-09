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

        # Hierarchy column format
        hierarchy_fmt = workbook.add_format({
            "align": "left",
            "valign": "vcenter",
        })

        hierarchy_bold_fmt = workbook.add_format({
            "align": "left",
            "valign": "vcenter",
            "bold": True,
        })

        hierarchy_italic_bold_fmt = workbook.add_format({
            "align": "left",
            "valign": "vcenter",
            "bold": True,
            "italic": True,
        })

        # Data formats
        number_fmt = workbook.add_format({"num_format": "#,##0", "align": "center"})
        currency_fmt = workbook.add_format({
            "num_format": f"{currency_symbol}#,##0.00",
            "align": "center",
        })
        percent_fmt = workbook.add_format({"num_format": "0.00%", "align": "center"})

        # Zebra striping formats (alternating row colors)
        zebra_colors = ["#d9e1f2", "#fce4d6", "#ffffff"]

        # Build header rows (rows 0-2)
        _build_header_rows(ws, workbook, week_buckets, header_fmt, date_fmt)

        # Set column widths
        ws.set_column(0, 0, 60)  # Column A: Hierarchy
        # Each metric has 4 weekly columns
        for col_idx in range(1, 1 + 7 * 4):  # 7 metrics × 4 weeks
            ws.set_column(col_idx, col_idx, 10)

        # Write data rows (starting from row 3)
        current_row = 3
        current_block = 0
        last_adtype_path = None

        for node in nodes:
            # Determine row format based on hierarchy level
            if node.level == "ProfileName":
                row_fmt = hierarchy_bold_fmt
            elif node.level == "PortfolioName":
                row_fmt = hierarchy_bold_fmt
            elif node.level == "AdType":
                row_fmt = hierarchy_italic_bold_fmt
                # Change block color when AdType block changes (for visual grouping)
                adtype_path = tuple(node.full_path[:3])  # Profile + Portfolio + AdType
                if adtype_path != last_adtype_path:
                    current_block = (current_block + 1) % len(zebra_colors)
                    last_adtype_path = adtype_path
            else:
                row_fmt = hierarchy_fmt

            # Get zebra color for this block
            bg_color = zebra_colors[current_block]

            # Create formats with background color for this row
            row_number_fmt = workbook.add_format({
                "num_format": "#,##0",
                "align": "center",
                "bg_color": bg_color,
            })
            row_currency_fmt = workbook.add_format({
                "num_format": f"{currency_symbol}#,##0.00",
                "align": "center",
                "bg_color": bg_color,
            })
            row_percent_fmt = workbook.add_format({
                "num_format": "0.00%",
                "align": "center",
                "bg_color": bg_color,
            })
            row_hierarchy_fmt = workbook.add_format({
                "align": "left",
                "valign": "vcenter",
                "bg_color": bg_color,
                "bold": row_fmt.bold,
                "italic": row_fmt.italic if hasattr(row_fmt, "italic") else False,
            })

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
