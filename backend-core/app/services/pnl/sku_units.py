"""Helpers for deriving Monthly P&L sold-unit summaries by SKU."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable


@dataclass(frozen=True)
class SkuUnitSourceRow:
    sku: str | None
    quantity: int | None
    raw_type: str | None
    product_sales: Decimal


def signed_sku_units(row: SkuUnitSourceRow) -> int:
    sku = (row.sku or "").strip()
    if not sku or not row.quantity or row.quantity <= 0:
        return 0

    raw_type = (row.raw_type or "").strip().lower()
    if raw_type == "order" and row.product_sales > 0:
        return row.quantity
    if raw_type == "refund" and row.product_sales < 0:
        return -row.quantity
    return 0


def summarize_sku_units(rows: Iterable[SkuUnitSourceRow]) -> dict[str, dict[str, int]]:
    totals: dict[str, dict[str, int]] = {}
    for row in rows:
        sku = (row.sku or "").strip()
        signed_units = signed_sku_units(row)
        if not sku or signed_units == 0:
            continue

        current = totals.setdefault(
            sku,
            {"net_units": 0, "order_row_count": 0, "refund_row_count": 0},
        )
        current["net_units"] += signed_units
        if signed_units > 0:
            current["order_row_count"] += 1
        else:
            current["refund_row_count"] += 1
    return totals
