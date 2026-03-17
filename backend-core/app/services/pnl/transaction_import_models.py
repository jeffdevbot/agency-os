"""Shared datatypes for Monthly P&L transaction imports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal


@dataclass
class ParsedRawRow:
    row_index: int
    posted_at: datetime | None
    release_at: datetime | None
    order_id: str | None
    sku: str | None
    raw_type: str | None
    raw_description: str | None
    entry_month: date | None
    amounts: dict[str, Decimal]
    raw_payload: dict[str, str]
    quantity: int | None = None


@dataclass
class LedgerEntry:
    entry_month: date
    posted_at: datetime | None
    order_id: str | None
    sku: str | None
    raw_type: str | None
    raw_description: str | None
    ledger_bucket: str
    amount: Decimal
    is_mapped: bool
    mapping_rule_id: str | None
    source_row_index: int


@dataclass
class MonthSlice:
    entry_month: date
    raw_rows: list[ParsedRawRow] = field(default_factory=list)
    ledger_entries: list[LedgerEntry] = field(default_factory=list)
    mapped_amount: Decimal = Decimal("0")
    unmapped_amount: Decimal = Decimal("0")


@dataclass
class MappingRule:
    id: str
    profile_id: str | None
    source_type: str
    match_spec: dict[str, str]
    match_operator: str
    target_bucket: str
    priority: int


@dataclass
class PreparedImport:
    raw_rows: list[ParsedRawRow]
    month_slices: dict[date, MonthSlice]
    sorted_months: list[date]
    period_start: date
    period_end: date
    import_scope: str
