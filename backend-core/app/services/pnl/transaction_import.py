"""Amazon Monthly Unified Transaction Report import service.

Handles CSV parsing, raw-row storage, ledger expansion, mapping rule
application, and month-slice activation for the Monthly P&L system.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, date
from decimal import Decimal, InvalidOperation
from typing import Any

from supabase import Client

from .profiles import PNLDuplicateFileError, PNLNotFoundError, PNLValidationError

SOURCE_TYPE = "amazon_transaction_upload"

# ── CSV header aliases ───────────────────────────────────────────────

HEADER_ALIASES: dict[str, set[str]] = {
    "date_time": {"datetime", "date/time", "date"},
    "settlement_id": {"settlementid", "settlement id"},
    "type": {"type"},
    "order_id": {"orderid", "order id"},
    "sku": {"sku"},
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

# ── Column → ledger bucket direct mapping ────────────────────────────
# For normal Order/Refund rows, these CSV columns map 1:1 to buckets.

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


def _parse_datetime(value: str) -> datetime | None:
    if not value.strip():
        return None
    for fmt in ("%b %d, %Y %I:%M:%S %p %Z", "%b %d, %Y %I:%M:%S %p", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y %H:%M:%S"):
        try:
            return datetime.strptime(value.strip(), fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    # Try date-only formats
    for fmt in ("%b %d, %Y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _entry_month_from_dt(dt: datetime) -> date:
    """Normalize a datetime to first-of-month date."""
    return date(dt.year, dt.month, 1)


# ── Parsed structures ────────────────────────────────────────────────


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
    amounts: dict[str, Decimal]  # column_name → amount
    raw_payload: dict[str, str]


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


# ── CSV Parsing ──────────────────────────────────────────────────────


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

    # Find header row
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
        raise PNLValidationError(
            "Transaction file must include date/time and type columns"
        )

    data_rows = all_rows[header_row_index + 1 :]
    return header_values, header_map, data_rows


def parse_raw_rows(
    header_values: list[str],
    header_map: dict[str, int],
    data_rows: list[list[str]],
) -> list[ParsedRawRow]:
    """Convert CSV data rows into ParsedRawRow objects."""
    results: list[ParsedRawRow] = []
    for row_index, row in enumerate(data_rows):
        raw_type = _pick(row, header_map, "type")
        if not raw_type:
            continue

        posted_at = _parse_datetime(_pick(row, header_map, "date_time"))
        release_at = _parse_datetime(_pick(row, header_map, "transaction_release_date"))

        # Canonical month: Transaction Release Date first, fallback to date/time
        canonical_dt = release_at or posted_at
        entry_month = _entry_month_from_dt(canonical_dt) if canonical_dt else None

        order_id = _pick(row, header_map, "order_id") or None
        sku = _pick(row, header_map, "sku") or None
        raw_description = _pick(row, header_map, "description") or None

        # Extract financial amounts from all mapped columns
        amounts: dict[str, Decimal] = {}
        for col_name in COLUMN_BUCKET_MAP:
            val = _parse_decimal(_pick(row, header_map, col_name))
            if val != 0:
                amounts[col_name] = val

        # Also capture the "other" column
        other_val = _parse_decimal(_pick(row, header_map, "other"))
        if other_val != 0:
            amounts["other"] = other_val

        raw_payload = {
            header_values[i]: (row[i] if i < len(row) else "")
            for i in range(len(header_values))
            if header_values[i]
        }

        results.append(ParsedRawRow(
            row_index=row_index,
            posted_at=posted_at,
            release_at=release_at,
            order_id=order_id,
            sku=sku,
            raw_type=raw_type,
            raw_description=raw_description,
            entry_month=entry_month,
            amounts=amounts,
            raw_payload=raw_payload,
        ))

    if not results:
        raise PNLValidationError("Transaction file contained no data rows")
    return results


# ── Mapping rule evaluation ──────────────────────────────────────────


def _match_rule(rule: MappingRule, raw_type: str | None, raw_description: str | None) -> bool:
    spec = rule.match_spec
    if rule.match_operator == "exact_fields":
        for key, expected_val in spec.items():
            if key == "type":
                if (raw_type or "").strip() != expected_val:
                    return False
            elif key == "description":
                if (raw_description or "").strip() != expected_val:
                    return False
            else:
                return False
        return True
    elif rule.match_operator == "contains":
        for key, expected_val in spec.items():
            if key == "type":
                if expected_val.lower() not in (raw_type or "").lower():
                    return False
            elif key == "description":
                if expected_val.lower() not in (raw_description or "").lower():
                    return False
        return True
    elif rule.match_operator == "starts_with":
        for key, expected_val in spec.items():
            if key == "type":
                if not (raw_type or "").lower().startswith(expected_val.lower()):
                    return False
            elif key == "description":
                if not (raw_description or "").lower().startswith(expected_val.lower()):
                    return False
        return True
    return False


def find_matching_rule(
    rules: list[MappingRule],
    raw_type: str | None,
    raw_description: str | None,
    profile_id: str | None = None,
) -> MappingRule | None:
    """Find the best matching rule. Profile-specific rules beat global rules."""
    profile_matches: list[MappingRule] = []
    global_matches: list[MappingRule] = []

    for rule in rules:
        if not _match_rule(rule, raw_type, raw_description):
            continue
        if rule.profile_id and rule.profile_id == profile_id:
            profile_matches.append(rule)
        elif not rule.profile_id:
            global_matches.append(rule)

    # Profile-specific rules always win before priority
    candidates = profile_matches if profile_matches else global_matches
    if not candidates:
        return None

    # Lower priority number = higher priority
    candidates.sort(key=lambda r: r.priority)
    return candidates[0]


# ── Ledger expansion ─────────────────────────────────────────────────


def expand_raw_row_to_ledger(
    raw_row: ParsedRawRow,
    rules: list[MappingRule],
    profile_id: str | None,
) -> list[LedgerEntry]:
    """Expand a single raw row into ledger entries.

    For normal Order/Refund rows, each financial column becomes a ledger entry.
    For special rows (Service Fee, FBA Inventory Fee, Transfer, Adjustment, etc.),
    the matching rule determines the bucket and we use the 'total' or 'other'
    amount columns.
    """
    if raw_row.entry_month is None:
        return []

    raw_type = raw_row.raw_type
    raw_description = raw_row.raw_description

    # Check if a mapping rule matches this row type
    rule = find_matching_rule(rules, raw_type, raw_description, profile_id)

    # For rows matched by a type-based rule (Service Fee, FBA Inventory Fee,
    # Transfer, Adjustment), the rule determines the single bucket.
    # The amount comes from the "other" or "total" column (whichever is non-zero),
    # or the sum of all amount columns.
    is_type_rule_row = rule is not None and raw_type not in ("Order", "Refund", "")

    entries: list[LedgerEntry] = []

    if is_type_rule_row:
        # Single-bucket row driven by mapping rule
        # Use "other" amount if available, otherwise sum all amounts
        amount = raw_row.amounts.get("other", Decimal("0"))
        if amount == 0:
            amount = sum(raw_row.amounts.values(), Decimal("0"))
        if amount != 0:
            entries.append(LedgerEntry(
                entry_month=raw_row.entry_month,
                posted_at=raw_row.posted_at,
                order_id=raw_row.order_id,
                sku=raw_row.sku,
                raw_type=raw_type,
                raw_description=raw_description,
                ledger_bucket=rule.target_bucket,
                amount=amount,
                is_mapped=True,
                mapping_rule_id=rule.id,
                source_row_index=raw_row.row_index,
            ))
    else:
        # Normal Order/Refund row: expand each financial column into its own entry
        is_refund = (raw_type or "").strip() == "Refund"
        for col_name, amount in raw_row.amounts.items():
            if col_name == "other":
                # "other" column on normal rows → unmapped unless there's a rule
                entries.append(LedgerEntry(
                    entry_month=raw_row.entry_month,
                    posted_at=raw_row.posted_at,
                    order_id=raw_row.order_id,
                    sku=raw_row.sku,
                    raw_type=raw_type,
                    raw_description=raw_description,
                    ledger_bucket="unmapped",
                    amount=amount,
                    is_mapped=False,
                    mapping_rule_id=None,
                    source_row_index=raw_row.row_index,
                ))
                continue

            base_bucket = COLUMN_BUCKET_MAP.get(col_name)
            if not base_bucket:
                continue

            # For refund rows, adjust bucket names for revenue columns
            bucket = base_bucket
            if is_refund:
                if base_bucket == "product_sales":
                    bucket = "refunds"
                elif base_bucket == "shipping_credits":
                    bucket = "shipping_credit_refunds"
                elif base_bucket == "gift_wrap_credits":
                    bucket = "gift_wrap_credit_refunds"
                elif base_bucket == "promotional_rebates":
                    bucket = "promotional_rebate_refunds"

            entries.append(LedgerEntry(
                entry_month=raw_row.entry_month,
                posted_at=raw_row.posted_at,
                order_id=raw_row.order_id,
                sku=raw_row.sku,
                raw_type=raw_type,
                raw_description=raw_description,
                ledger_bucket=bucket,
                amount=amount,
                is_mapped=True,
                mapping_rule_id=None,
                source_row_index=raw_row.row_index,
            ))

    return entries


# ── Import orchestration ─────────────────────────────────────────────


class TransactionImportService:
    def __init__(self, db: Client) -> None:
        self.db = db

    def import_file(
        self,
        *,
        profile_id: str,
        file_name: str,
        file_bytes: bytes,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Full import pipeline: parse → store → expand → activate."""
        # 1. Validate profile exists
        profile = self._get_profile(profile_id)

        # 2. Compute file hash for duplicate guard
        file_sha256 = hashlib.sha256(file_bytes).hexdigest()

        # 3. Check for duplicate
        self._check_duplicate(profile_id, file_sha256)

        # 4. Parse CSV
        header_values, header_map, data_rows = parse_transaction_csv(file_bytes)
        raw_rows = parse_raw_rows(header_values, header_map, data_rows)

        # 5. Load mapping rules
        rules = self._load_mapping_rules(
            marketplace_code=str(profile.get("marketplace_code", "US")),
            profile_id=profile_id,
        )

        # 6. Expand raw rows into ledger entries, grouped by month
        months: dict[date, MonthSlice] = {}
        for raw_row in raw_rows:
            if raw_row.entry_month is None:
                continue
            if raw_row.entry_month not in months:
                months[raw_row.entry_month] = MonthSlice(entry_month=raw_row.entry_month)
            month_slice = months[raw_row.entry_month]
            month_slice.raw_rows.append(raw_row)

            entries = expand_raw_row_to_ledger(raw_row, rules, profile_id)
            for entry in entries:
                month_slice.ledger_entries.append(entry)
                if entry.is_mapped:
                    month_slice.mapped_amount += entry.amount
                else:
                    month_slice.unmapped_amount += entry.amount

        if not months:
            raise PNLValidationError("No rows with valid dates found in transaction file")

        # 7. Determine period and scope
        sorted_months = sorted(months.keys())
        period_start = sorted_months[0]
        period_end = sorted_months[-1]
        if len(sorted_months) == 1:
            import_scope = "single_month"
        elif len(sorted_months) >= 10:
            import_scope = "full_year"
        else:
            import_scope = "multi_month"

        # 8. Create import record
        import_record = self._create_import(
            profile_id=profile_id,
            file_name=file_name,
            file_sha256=file_sha256,
            period_start=period_start.isoformat(),
            period_end=period_end.isoformat(),
            import_scope=import_scope,
            row_count=len(raw_rows),
            user_id=user_id,
        )
        import_id = str(import_record["id"])

        try:
            # 9. Update import status to running
            self._update_import_status(import_id, "running")

            # 10. Process each month slice
            month_summaries: list[dict[str, Any]] = []
            for entry_month in sorted_months:
                month_slice = months[entry_month]
                summary = self._process_month_slice(
                    import_id=import_id,
                    profile_id=profile_id,
                    month_slice=month_slice,
                )
                month_summaries.append(summary)

            # 11. Update import to success
            self._update_import_status(import_id, "success")

            # 12. Re-read import so response reflects final status/timestamps
            final_import = self._get_import(import_id)

            return {
                "import": final_import,
                "months": month_summaries,
                "summary": {
                    "total_raw_rows": len(raw_rows),
                    "total_months": len(sorted_months),
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "import_scope": import_scope,
                },
            }

        except Exception as exc:
            self._update_import_status(import_id, "error", error_message=str(exc))
            raise

    def _get_profile(self, profile_id: str) -> dict[str, Any]:
        response = (
            self.db.table("monthly_pnl_profiles")
            .select("*")
            .eq("id", profile_id)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise PNLNotFoundError(f"P&L profile {profile_id} not found")
        return rows[0]

    def _get_import(self, import_id: str) -> dict[str, Any]:
        response = (
            self.db.table("monthly_pnl_imports")
            .select("*")
            .eq("id", import_id)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise PNLNotFoundError(f"Import {import_id} not found")
        return rows[0]

    def _check_duplicate(self, profile_id: str, file_sha256: str) -> None:
        response = (
            self.db.table("monthly_pnl_imports")
            .select("id, import_status")
            .eq("profile_id", profile_id)
            .eq("source_type", SOURCE_TYPE)
            .eq("source_file_sha256", file_sha256)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if rows:
            status = rows[0].get("import_status")
            # Allow retry of same file after a previous errored import
            if status in ("success", "running"):
                raise PNLDuplicateFileError(
                    f"This file has already been imported (import {rows[0]['id']})"
                )

    def _load_mapping_rules(
        self, marketplace_code: str, profile_id: str
    ) -> list[MappingRule]:
        response = (
            self.db.table("monthly_pnl_mapping_rules")
            .select("*")
            .eq("source_type", SOURCE_TYPE)
            .eq("marketplace_code", marketplace_code)
            .eq("active", True)
            .order("priority")
            .execute()
        )
        rows = response.data if isinstance(rows_data := response.data, list) else []
        rules: list[MappingRule] = []
        for row in rows_data if isinstance(rows_data, list) else []:
            spec = row.get("match_spec") or {}
            if isinstance(spec, str):
                spec = json.loads(spec)
            rules.append(MappingRule(
                id=str(row["id"]),
                profile_id=row.get("profile_id"),
                source_type=row.get("source_type", SOURCE_TYPE),
                match_spec=spec,
                match_operator=row.get("match_operator", "exact_fields"),
                target_bucket=row["target_bucket"],
                priority=row.get("priority", 100),
            ))
        return rules

    def _create_import(
        self,
        *,
        profile_id: str,
        file_name: str,
        file_sha256: str,
        period_start: str,
        period_end: str,
        import_scope: str,
        row_count: int,
        user_id: str | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "profile_id": profile_id,
            "source_type": SOURCE_TYPE,
            "source_filename": file_name,
            "source_file_sha256": file_sha256,
            "period_start": period_start,
            "period_end": period_end,
            "import_scope": import_scope,
            "import_status": "pending",
            "row_count": row_count,
            "started_at": datetime.now(UTC).isoformat(),
        }
        if user_id:
            payload["initiated_by"] = user_id
        response = self.db.table("monthly_pnl_imports").insert(payload).execute()
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise PNLValidationError("Failed to create import record")
        return rows[0]

    def _update_import_status(
        self, import_id: str, status: str, *, error_message: str | None = None
    ) -> None:
        payload: dict[str, Any] = {"import_status": status}
        if status in ("success", "error"):
            payload["finished_at"] = datetime.now(UTC).isoformat()
        if error_message:
            payload["error_message"] = error_message
        self.db.table("monthly_pnl_imports").update(payload).eq("id", import_id).execute()

    def _process_month_slice(
        self,
        *,
        import_id: str,
        profile_id: str,
        month_slice: MonthSlice,
    ) -> dict[str, Any]:
        entry_month = month_slice.entry_month

        # 1. Create import_month record (starts as 'pending')
        import_month = self._create_import_month(
            import_id=import_id,
            profile_id=profile_id,
            entry_month=entry_month,
            raw_row_count=len(month_slice.raw_rows),
            ledger_row_count=len(month_slice.ledger_entries),
            mapped_amount=month_slice.mapped_amount,
            unmapped_amount=month_slice.unmapped_amount,
        )
        import_month_id = str(import_month["id"])

        try:
            # 2. Insert raw rows
            self._insert_raw_rows(
                import_id=import_id,
                import_month_id=import_month_id,
                profile_id=profile_id,
                raw_rows=month_slice.raw_rows,
            )

            # 3. Insert ledger entries
            self._insert_ledger_entries(
                import_id=import_id,
                import_month_id=import_month_id,
                profile_id=profile_id,
                entry_month=entry_month,
                entries=month_slice.ledger_entries,
            )

            # 4. Atomically activate: deactivate old, activate new (single RPC tx)
            self._activate_month_slice(
                profile_id=profile_id,
                import_month_id=import_month_id,
                entry_month=entry_month,
            )

            # 5. Mark import month as success only after data + activation complete
            self._update_import_month_status(import_month_id, "success")

        except Exception:
            # Mark month slice as error so it's auditable / visible in QA
            self._update_import_month_status(import_month_id, "error")
            raise

        return {
            "entry_month": entry_month.isoformat(),
            "import_month_id": import_month_id,
            "raw_row_count": len(month_slice.raw_rows),
            "ledger_row_count": len(month_slice.ledger_entries),
            "mapped_amount": str(month_slice.mapped_amount),
            "unmapped_amount": str(month_slice.unmapped_amount),
            "is_active": True,
        }

    def _create_import_month(
        self,
        *,
        import_id: str,
        profile_id: str,
        entry_month: date,
        raw_row_count: int,
        ledger_row_count: int,
        mapped_amount: Decimal,
        unmapped_amount: Decimal,
    ) -> dict[str, Any]:
        payload = {
            "import_id": import_id,
            "profile_id": profile_id,
            "source_type": SOURCE_TYPE,
            "entry_month": entry_month.isoformat(),
            "import_status": "pending",
            "raw_row_count": raw_row_count,
            "ledger_row_count": ledger_row_count,
            "mapped_amount": str(mapped_amount),
            "unmapped_amount": str(unmapped_amount),
        }
        response = self.db.table("monthly_pnl_import_months").insert(payload).execute()
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise PNLValidationError("Failed to create import month record")
        return rows[0]

    def _insert_raw_rows(
        self,
        *,
        import_id: str,
        import_month_id: str,
        profile_id: str,
        raw_rows: list[ParsedRawRow],
    ) -> None:
        payloads = [
            {
                "import_id": import_id,
                "import_month_id": import_month_id,
                "profile_id": profile_id,
                "source_type": SOURCE_TYPE,
                "row_index": rr.row_index,
                "posted_at": rr.posted_at.isoformat() if rr.posted_at else None,
                "release_at": rr.release_at.isoformat() if rr.release_at else None,
                "order_id": rr.order_id,
                "sku": rr.sku,
                "raw_type": rr.raw_type,
                "raw_description": rr.raw_description,
                "raw_payload": rr.raw_payload,
            }
            for rr in raw_rows
        ]
        for start in range(0, len(payloads), 500):
            chunk = payloads[start : start + 500]
            self.db.table("monthly_pnl_raw_rows").insert(chunk).execute()

    def _insert_ledger_entries(
        self,
        *,
        import_id: str,
        import_month_id: str,
        profile_id: str,
        entry_month: date,
        entries: list[LedgerEntry],
    ) -> None:
        payloads = [
            {
                "import_id": import_id,
                "import_month_id": import_month_id,
                "profile_id": profile_id,
                "entry_month": entry_month.isoformat(),
                "posted_at": e.posted_at.isoformat() if e.posted_at else None,
                "order_id": e.order_id,
                "sku": e.sku,
                "source_type": SOURCE_TYPE,
                "raw_type": e.raw_type,
                "raw_description": e.raw_description,
                "ledger_bucket": e.ledger_bucket,
                "amount": str(e.amount),
                "is_mapped": e.is_mapped,
                "mapping_rule_id": e.mapping_rule_id,
                "source_row_index": e.source_row_index,
            }
            for e in entries
        ]
        for start in range(0, len(payloads), 500):
            chunk = payloads[start : start + 500]
            self.db.table("monthly_pnl_ledger_entries").insert(chunk).execute()

    def _update_import_month_status(self, import_month_id: str, status: str) -> None:
        (
            self.db.table("monthly_pnl_import_months")
            .update({"import_status": status})
            .eq("id", import_month_id)
            .execute()
        )

    def _activate_month_slice(
        self,
        *,
        profile_id: str,
        import_month_id: str,
        entry_month: date,
    ) -> None:
        """Atomic activation via RPC: deactivate old + activate new in one tx."""
        self.db.rpc(
            "pnl_activate_month_slice",
            {
                "p_profile_id": profile_id,
                "p_source_type": SOURCE_TYPE,
                "p_entry_month": entry_month.isoformat(),
                "p_import_month_id": import_month_id,
            },
        ).execute()
