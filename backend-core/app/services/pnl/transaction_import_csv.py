"""CSV parsing helpers for Monthly P&L transaction imports."""

from __future__ import annotations

import csv
import io
import re
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from .profiles import PNLValidationError
from .transaction_import_models import ParsedRawRow

HEADER_ALIASES: dict[str, set[str]] = {
    "date_time": {"datetime", "date/time", "date"},
    "settlement_id": {"settlementid", "settlement id"},
    "type": {"type"},
    "order_id": {"orderid", "order id"},
    "sku": {"sku"},
    "quantity": {"quantity", "qty"},
    "description": {"description"},
    "product_sales": {"productsales", "product sales"},
    "product_sales_tax": {"productsalestax", "product sales tax"},
    "shipping_credits": {"shippingcredits", "shipping credits"},
    "shipping_credits_tax": {"shippingcreditstax", "shipping credits tax"},
    "gift_wrap_credits": {"giftwrapcredits", "gift wrap credits"},
    "giftwrap_credits_tax": {"giftwrapcreditstax", "giftwrap credits tax"},
    "promotional_rebates": {"promotionalrebates", "promotional rebates"},
    "promotional_rebates_tax": {"promotionalrebatestax", "promotional rebates tax"},
    "marketplace_withheld_tax": {"marketplacewithheldtax", "marketplace withheld tax"},
    "selling_fees": {"sellingfees", "selling fees"},
    "fba_fees": {"fbafees", "fba fees"},
    "other_transaction_fees": {"othertransactionfees", "other transaction fees"},
    "other": {"other"},
    "total": {"total"},
    "transaction_status": {"transactionstatus", "transaction status"},
    "transaction_release_date": {"transactionreleasedate", "transaction release date"},
}

COLUMN_BUCKET_MAP: dict[str, str] = {
    "product_sales": "product_sales",
    "shipping_credits": "shipping_credits",
    "gift_wrap_credits": "gift_wrap_credits",
    "promotional_rebates": "promotional_rebates",
    "marketplace_withheld_tax": "marketplace_withheld_tax",
    "selling_fees": "referral_fees",
    "fba_fees": "fba_fees",
    "other_transaction_fees": "other_transaction_fees",
}

UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")


def _canonicalize_header(value: Any) -> str:
    return re.sub(r"[^a-z0-9/]+", "", str(value or "").strip().lower())


def _map_headers(header_values: list[str]) -> dict[str, int]:
    header_map: dict[str, int] = {}
    for idx, raw in enumerate(header_values):
        canon = _canonicalize_header(raw)
        if not canon:
            continue
        for field_name, aliases in HEADER_ALIASES.items():
            if canon in {_canonicalize_header(a) for a in aliases} and field_name not in header_map:
                header_map[field_name] = idx
    return header_map


def _pick(row: list[str], header_map: dict[str, int], field: str) -> str:
    idx = header_map.get(field)
    if idx is None or idx >= len(row):
        return ""
    return (row[idx] or "").strip()


def _parse_decimal(value: str) -> Decimal:
    cleaned = value.strip().replace(",", "")
    if not cleaned:
        return Decimal("0")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return Decimal("0")


def _parse_int(value: str) -> int | None:
    cleaned = value.strip().replace(",", "")
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def _parse_datetime(value: str) -> datetime | None:
    raw = value.strip()
    if not raw:
        return None

    candidates = [raw]
    tz_stripped = re.sub(r"\s+[A-Z]{2,5}$", "", raw)
    if tz_stripped != raw:
        candidates.append(tz_stripped)

    for candidate in candidates:
        for fmt in (
            "%b %d, %Y %I:%M:%S %p %Z",
            "%b %d, %Y %I:%M:%S %p",
            "%Y-%m-%dT%H:%M:%S",
            "%m/%d/%Y %H:%M:%S",
        ):
            try:
                return datetime.strptime(candidate, fmt).replace(tzinfo=UTC)
            except ValueError:
                continue
    for candidate in candidates:
        for fmt in ("%b %d, %Y", "%m/%d/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(candidate, fmt).replace(tzinfo=UTC)
            except ValueError:
                continue
    return None


def _entry_month_from_dt(dt: datetime) -> date:
    return date(dt.year, dt.month, 1)


def parse_transaction_csv(file_bytes: bytes) -> tuple[list[str], dict[str, int], list[list[str]]]:
    """Parse CSV bytes into (header_values, header_map, data_rows)."""
    text: str | None = None
    if file_bytes.startswith(UTF16_BOMS):
        try:
            text = file_bytes.decode("utf-16")
        except UnicodeDecodeError as exc:
            raise PNLValidationError("Unable to decode UTF-16 transaction file") from exc
    else:
        for encoding in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                text = file_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
    if text is None:
        raise PNLValidationError("Unable to decode transaction file")

    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters="\t,")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = "," if "," in sample else "\t"

    all_rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    if not all_rows:
        raise PNLValidationError("Transaction file is empty")

    header_row_index = -1
    header_values: list[str] = []
    header_map: dict[str, int] = {}
    for idx, row in enumerate(all_rows):
        values = [str(c).strip() for c in row]
        mapped = _map_headers(values)
        if "date_time" in mapped and "type" in mapped:
            header_row_index = idx
            header_values = values
            header_map = mapped
            break

    if header_row_index < 0:
        raise PNLValidationError("Transaction file must include date/time and type columns")

    return header_values, header_map, all_rows[header_row_index + 1 :]


def parse_raw_rows(
    header_values: list[str],
    header_map: dict[str, int],
    data_rows: list[list[str]],
) -> list[ParsedRawRow]:
    results: list[ParsedRawRow] = []
    for row_index, row in enumerate(data_rows):
        raw_type = _pick(row, header_map, "type") or None
        raw_description = _pick(row, header_map, "description") or None
        if not raw_type and not raw_description:
            continue

        posted_at = _parse_datetime(_pick(row, header_map, "date_time"))
        release_at = _parse_datetime(_pick(row, header_map, "transaction_release_date"))
        canonical_dt = posted_at or release_at
        entry_month = _entry_month_from_dt(canonical_dt) if canonical_dt else None

        amounts: dict[str, Decimal] = {}
        for col_name in COLUMN_BUCKET_MAP:
            val = _parse_decimal(_pick(row, header_map, col_name))
            if val != 0:
                amounts[col_name] = val

        other_val = _parse_decimal(_pick(row, header_map, "other"))
        if other_val != 0:
            amounts["other"] = other_val

        raw_payload = {
            header_values[i]: (row[i] if i < len(row) else "")
            for i in range(len(header_values))
            if header_values[i]
        }

        results.append(
            ParsedRawRow(
                row_index=row_index,
                posted_at=posted_at,
                release_at=release_at,
                order_id=_pick(row, header_map, "order_id") or None,
                sku=_pick(row, header_map, "sku") or None,
                quantity=_parse_int(_pick(row, header_map, "quantity")),
                raw_type=raw_type,
                raw_description=raw_description,
                entry_month=entry_month,
                amounts=amounts,
                raw_payload=raw_payload,
            )
        )

    if not results:
        raise PNLValidationError("Transaction file contained no data rows")
    return results
