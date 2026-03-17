from __future__ import annotations

import asyncio
import gc
import os
import re
import tempfile
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import xlsxwriter
from supabase import Client

from .report import PNLReportService


SUMMARY_KEYS = {
    "total_gross_revenue",
    "total_refunds",
    "total_net_revenue",
    "gross_profit",
    "total_expenses",
    "net_earnings",
    "cogs",
    "contribution_margin",
    "net_margin",
    "payout_amount",
    "payout_percent",
}

CURRENCY_KEYS_IN_PERCENT_VIEW = {
    "product_sales",
    "shipping_credits",
    "gift_wrap_credits",
    "promotional_rebate_refunds",
    "fba_liquidation_proceeds",
    "total_gross_revenue",
    "total_net_revenue",
    "payout_amount",
}
GROSS_REVENUE_PERCENT_KEYS = {
    "refunds",
    "fba_inventory_credit",
    "shipping_credit_refunds",
    "gift_wrap_credit_refunds",
    "promotional_rebates",
    "a_to_z_guarantee_claims",
    "chargebacks",
    "total_refunds",
}

ZERO_TOLERANCE = Decimal("0.000001")


@dataclass(frozen=True)
class PresentedLineItem:
    key: str
    label: str
    category: str
    is_derived: bool
    months: dict[str, Decimal]
    display_format: str
    total_value: Decimal


def _sanitize_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return cleaned or "amazon-pnl"


def _month_label(month_iso: str) -> str:
    year = int(month_iso[0:4])
    month = int(month_iso[5:7])
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return f"{month_names[month - 1]} {year}"


def _to_decimal(value: Any) -> Decimal:
    return Decimal(str(value or "0"))


def _line_total(months: dict[str, Decimal], month_keys: list[str]) -> Decimal:
    return sum((months.get(month, Decimal("0")) for month in month_keys), Decimal("0"))


def _has_any_cogs(months: list[str], cogs_line: dict[str, Any] | None) -> bool:
    if not cogs_line:
        return False
    return any(abs(_to_decimal(cogs_line.get("months", {}).get(month))) > ZERO_TOLERANCE for month in months)


def _build_margin_row(
    key: str,
    label: str,
    months: list[str],
    profit_line: dict[str, Any],
    revenue_line: dict[str, Any],
) -> PresentedLineItem:
    month_values: dict[str, Decimal] = {}
    for month in months:
        revenue = _to_decimal(revenue_line["months"].get(month))
        profit = _to_decimal(profit_line["months"].get(month))
        month_values[month] = Decimal("0") if revenue == 0 else ((profit / revenue) * Decimal("100"))

    total_revenue = _line_total({month: _to_decimal(revenue_line["months"].get(month)) for month in months}, months)
    total_profit = _line_total({month: _to_decimal(profit_line["months"].get(month)) for month in months}, months)
    total_margin = Decimal("0") if total_revenue == 0 else ((total_profit / total_revenue) * Decimal("100"))

    return PresentedLineItem(
        key=key,
        label=label,
        category="summary",
        is_derived=True,
        months=month_values,
        display_format="percent",
        total_value=total_margin,
    )


def _build_payout_percent_row(
    months: list[str],
    payout_line: PresentedLineItem,
    revenue_line: dict[str, Any],
) -> PresentedLineItem:
    month_values: dict[str, Decimal] = {}
    for month in months:
        revenue = _to_decimal(revenue_line["months"].get(month))
        payout = payout_line.months.get(month, Decimal("0"))
        month_values[month] = Decimal("0") if revenue == 0 else ((payout / revenue) * Decimal("100"))

    total_revenue = _line_total(
        {month: _to_decimal(revenue_line["months"].get(month)) for month in months},
        months,
    )
    total_payout = _line_total(payout_line.months, months)
    total_percent = Decimal("0") if total_revenue == 0 else ((total_payout / total_revenue) * Decimal("100"))

    return PresentedLineItem(
        key="payout_percent",
        label="Payout (%)",
        category="summary",
        is_derived=True,
        months=month_values,
        display_format="percent",
        total_value=total_percent,
    )


def _build_presented_line_items(
    months: list[str],
    line_items: list[dict[str, Any]],
    mode: str,
) -> list[PresentedLineItem]:
    cogs_line = next((item for item in line_items if item.get("key") == "cogs"), None)
    revenue_line = next((item for item in line_items if item.get("key") == "total_net_revenue"), None)
    gross_revenue_line = next((item for item in line_items if item.get("key") == "total_gross_revenue"), None)
    profit_line = next((item for item in line_items if item.get("key") == "net_earnings"), None)
    has_any_cogs = _has_any_cogs(months, cogs_line)

    renamed_items: list[PresentedLineItem] = []
    for item in line_items:
        item_months = {
            month: _to_decimal(item.get("months", {}).get(month))
            for month in months
        }
        label = str(item.get("label") or "")
        if item.get("key") == "cogs":
            item_months = {month: -amount for month, amount in item_months.items()}
        elif not has_any_cogs and item.get("key") == "net_earnings":
            label = "Contribution Profit"

        renamed_items.append(
            PresentedLineItem(
                key=str(item.get("key") or ""),
                label=label,
                category=str(item.get("category") or ""),
                is_derived=bool(item.get("is_derived")),
                months=item_months,
                display_format="currency",
                total_value=_line_total(item_months, months),
            )
        )

    payout_presented_line = next((item for item in renamed_items if item.key == "payout_amount"), None)
    presented_items = [item for item in renamed_items if item.key != "payout_amount"]

    if revenue_line and profit_line:
        presented_items.append(
            _build_margin_row(
                "net_margin" if has_any_cogs else "contribution_margin",
                "Net Margin (%)" if has_any_cogs else "Contribution Margin (%)",
                months,
                profit_line,
                revenue_line,
            )
        )
    if payout_presented_line is not None:
        presented_items.append(payout_presented_line)
        if revenue_line is not None:
            presented_items.append(_build_payout_percent_row(months, payout_presented_line, revenue_line))

    if mode == "dollars" or not revenue_line:
        return presented_items

    percent_items: list[PresentedLineItem] = []
    for item in presented_items:
        if item.display_format == "percent":
            percent_items.append(item)
            continue
        if item.key in CURRENCY_KEYS_IN_PERCENT_VIEW:
            percent_items.append(item)
            continue

        denominator_line = (
            gross_revenue_line
            if item.key in GROSS_REVENUE_PERCENT_KEYS and gross_revenue_line is not None
            else revenue_line
        )
        denominator_months = {
            month: _to_decimal(denominator_line.get("months", {}).get(month))
            for month in months
        }
        denominator_total = _line_total(denominator_months, months)

        percent_months: dict[str, Decimal] = {}
        for month in months:
            revenue = denominator_months.get(month, Decimal("0"))
            amount = item.months.get(month, Decimal("0"))
            percent_months[month] = Decimal("0") if revenue == 0 else ((amount / revenue) * Decimal("100"))

        total_percent = (
            Decimal("0")
            if denominator_total == 0
            else ((_line_total(item.months, months) / denominator_total) * Decimal("100"))
        )
        percent_items.append(
            PresentedLineItem(
                key=item.key,
                label=item.label,
                category=item.category,
                is_derived=item.is_derived,
                months=percent_months,
                display_format="percent",
                total_value=total_percent,
            )
        )
    return percent_items


def _format_range_label(months: list[str]) -> str:
    if not months:
        return "Custom Range"
    if len(months) == 1:
        return _month_label(months[0])
    return f"{_month_label(months[0])} - {_month_label(months[-1])}"


def build_pnl_workbook(
    report: dict[str, Any],
    *,
    profile_display_name: str,
    marketplace_code: str,
    currency_code: str,
    show_totals: bool = True,
) -> tuple[str, str]:
    months = [str(month) for month in report.get("months", [])]
    line_items = list(report.get("line_items", []))
    dollars_items = _build_presented_line_items(months, line_items, "dollars")
    percent_items = _build_presented_line_items(months, line_items, "percent")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    tmp_path = tmp.name
    tmp.close()

    filename = f"{_sanitize_filename_part(profile_display_name)}-{_sanitize_filename_part(marketplace_code)}-pnl.xlsx"

    try:
        workbook = xlsxwriter.Workbook(tmp_path, {"nan_inf_to_errors": True})

        title_fmt = workbook.add_format(
            {
                "bold": True,
                "align": "center",
                "valign": "vcenter",
                "bg_color": "#3a3838",
                "font_color": "white",
                "border": 1,
                "font_size": 14,
            }
        )
        header_fmt = workbook.add_format(
            {
                "bold": True,
                "align": "center",
                "valign": "vcenter",
                "bg_color": "#f7faff",
                "font_color": "#4c576f",
                "border": 1,
            }
        )
        meta_label_fmt = workbook.add_format(
            {
                "bold": True,
                "align": "left",
                "valign": "vcenter",
                "bg_color": "#f7faff",
                "font_color": "#4c576f",
                "border": 1,
            }
        )
        meta_value_fmt = workbook.add_format({"align": "left", "valign": "vcenter", "border": 1})
        label_fmt = workbook.add_format({"align": "left", "valign": "vcenter", "border": 1})
        summary_label_fmt = workbook.add_format(
            {"bold": True, "align": "left", "valign": "vcenter", "border": 1, "bg_color": "#f1f5f9"}
        )
        net_label_fmt = workbook.add_format(
            {"bold": True, "align": "left", "valign": "vcenter", "border": 1, "bg_color": "#0f172a", "font_color": "white"}
        )

        currency_symbol = "$" if currency_code.upper() in {"USD", "CAD"} else ""
        currency_num_format = (
            f'{currency_symbol}#,##0.00;({currency_symbol}#,##0.00)'
            if currency_symbol
            else '#,##0.00;(#,##0.00)'
        )
        summary_currency_num_format = currency_num_format
        currency_fmt = workbook.add_format({"num_format": currency_num_format, "align": "right", "border": 1})
        summary_currency_fmt = workbook.add_format(
            {"num_format": summary_currency_num_format, "align": "right", "border": 1, "bold": True, "bg_color": "#f1f5f9"}
        )
        net_currency_fmt = workbook.add_format(
            {
                "num_format": (
                    f'{currency_symbol}#,##0.00;({currency_symbol}#,##0.00)'
                    if currency_symbol
                    else '#,##0.00;(#,##0.00)'
                ),
                "align": "right",
                "border": 1,
                "bold": True,
                "bg_color": "#0f172a",
                "font_color": "white",
            }
        )
        percent_fmt = workbook.add_format({"num_format": "0.0%;(0.0%)", "align": "right", "border": 1})
        summary_percent_fmt = workbook.add_format(
            {"num_format": "0.0%;(0.0%)", "align": "right", "border": 1, "bold": True, "bg_color": "#f1f5f9"}
        )
        net_percent_fmt = workbook.add_format(
            {"num_format": "0.0%;(0.0%)", "align": "right", "border": 1, "bold": True, "bg_color": "#0f172a", "font_color": "white"}
        )

        _write_pnl_sheet(
            workbook.add_worksheet("Dollars"),
            sheet_title="Amazon P&L - Dollars",
            profile_display_name=profile_display_name,
            marketplace_code=marketplace_code,
            currency_code=currency_code,
            range_label=_format_range_label(months),
            months=months,
            line_items=dollars_items,
            show_totals=show_totals,
            title_fmt=title_fmt,
            header_fmt=header_fmt,
            meta_label_fmt=meta_label_fmt,
            meta_value_fmt=meta_value_fmt,
            label_fmt=label_fmt,
            summary_label_fmt=summary_label_fmt,
            net_label_fmt=net_label_fmt,
            currency_fmt=currency_fmt,
            summary_currency_fmt=summary_currency_fmt,
            net_currency_fmt=net_currency_fmt,
            percent_fmt=percent_fmt,
            summary_percent_fmt=summary_percent_fmt,
            net_percent_fmt=net_percent_fmt,
        )
        _write_pnl_sheet(
            workbook.add_worksheet("% of Revenue"),
            sheet_title="Amazon P&L - % of Revenue",
            profile_display_name=profile_display_name,
            marketplace_code=marketplace_code,
            currency_code=currency_code,
            range_label=_format_range_label(months),
            months=months,
            line_items=percent_items,
            show_totals=show_totals,
            title_fmt=title_fmt,
            header_fmt=header_fmt,
            meta_label_fmt=meta_label_fmt,
            meta_value_fmt=meta_value_fmt,
            label_fmt=label_fmt,
            summary_label_fmt=summary_label_fmt,
            net_label_fmt=net_label_fmt,
            currency_fmt=currency_fmt,
            summary_currency_fmt=summary_currency_fmt,
            net_currency_fmt=net_currency_fmt,
            percent_fmt=percent_fmt,
            summary_percent_fmt=summary_percent_fmt,
            net_percent_fmt=net_percent_fmt,
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


def _write_pnl_sheet(
    worksheet: Any,
    *,
    sheet_title: str,
    profile_display_name: str,
    marketplace_code: str,
    currency_code: str,
    range_label: str,
    months: list[str],
    line_items: list[PresentedLineItem],
    show_totals: bool,
    title_fmt: Any,
    header_fmt: Any,
    meta_label_fmt: Any,
    meta_value_fmt: Any,
    label_fmt: Any,
    summary_label_fmt: Any,
    net_label_fmt: Any,
    currency_fmt: Any,
    summary_currency_fmt: Any,
    net_currency_fmt: Any,
    percent_fmt: Any,
    summary_percent_fmt: Any,
    net_percent_fmt: Any,
) -> None:
    last_col = len(months) + (1 if show_totals else 0)
    worksheet.set_column(0, 0, 34)
    worksheet.set_column(1, last_col, 14)

    worksheet.merge_range(0, 0, 0, last_col, sheet_title, title_fmt)
    worksheet.write_string(1, 0, "Account", meta_label_fmt)
    worksheet.write_string(1, 1, profile_display_name, meta_value_fmt)
    worksheet.write_string(1, 2, "Marketplace", meta_label_fmt)
    worksheet.write_string(1, 3, marketplace_code.upper(), meta_value_fmt)
    worksheet.write_string(2, 0, "Visible Range", meta_label_fmt)
    worksheet.write_string(2, 1, range_label, meta_value_fmt)
    worksheet.write_string(2, 2, "Currency", meta_label_fmt)
    worksheet.write_string(2, 3, currency_code.upper(), meta_value_fmt)

    header_row = 4
    worksheet.write_string(header_row, 0, "Line Item", header_fmt)
    for index, month in enumerate(months, start=1):
        worksheet.write_string(header_row, index, _month_label(month), header_fmt)
    if show_totals:
        worksheet.write_string(header_row, len(months) + 1, "Total", header_fmt)

    row_index = header_row + 1
    if not line_items:
        worksheet.merge_range(row_index, 0, row_index, last_col, "No data available for the selected range.", meta_value_fmt)
        worksheet.freeze_panes(header_row + 1, 1)
        return

    for item in line_items:
        if item.key == "payout_amount":
            row_index += 1

        is_net_row = item.key == "net_earnings"
        is_summary_row = item.key in SUMMARY_KEYS

        if is_net_row:
            current_label_fmt = net_label_fmt
            current_currency_fmt = net_currency_fmt
            current_percent_fmt = net_percent_fmt
        elif is_summary_row:
            current_label_fmt = summary_label_fmt
            current_currency_fmt = summary_currency_fmt
            current_percent_fmt = summary_percent_fmt
        else:
            current_label_fmt = label_fmt
            current_currency_fmt = currency_fmt
            current_percent_fmt = percent_fmt

        value_fmt = current_percent_fmt if item.display_format == "percent" else current_currency_fmt
        worksheet.write_string(row_index, 0, item.label, current_label_fmt)
        for col_index, month in enumerate(months, start=1):
            raw_value = item.months.get(month, Decimal("0"))
            cell_value = float(raw_value / Decimal("100")) if item.display_format == "percent" else float(raw_value)
            worksheet.write_number(row_index, col_index, cell_value, value_fmt)
        if show_totals:
            total_value = float(item.total_value / Decimal("100")) if item.display_format == "percent" else float(item.total_value)
            worksheet.write_number(row_index, len(months) + 1, total_value, value_fmt)
        row_index += 1

    worksheet.freeze_panes(header_row + 1, 1)


class PNLWorkbookExportService:
    def __init__(self, db: Client) -> None:
        self.db = db
        self.report_service = PNLReportService(db)

    async def build_export_async(
        self,
        profile_id: str,
        *,
        filter_mode: str = "ytd",
        start_month: str | None = None,
        end_month: str | None = None,
        show_totals: bool = True,
    ) -> tuple[str, str]:
        report = await self.report_service.build_report_async(
            profile_id,
            filter_mode=filter_mode,
            start_month=start_month,
            end_month=end_month,
        )
        profile = report["profile"]
        client_name = await asyncio.to_thread(self._get_client_name, str(profile.get("client_id") or ""))
        return await asyncio.to_thread(
            build_pnl_workbook,
            report,
            profile_display_name=client_name or "amazon-pnl",
            marketplace_code=str(profile.get("marketplace_code") or "amazon"),
            currency_code=str(profile.get("currency_code") or "USD"),
            show_totals=show_totals,
        )

    def _get_client_name(self, client_id: str) -> str:
        if not client_id:
            return ""
        response = (
            self.db.table("agency_clients")
            .select("name")
            .eq("id", client_id)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            return ""
        return str(rows[0].get("name") or "").strip()
