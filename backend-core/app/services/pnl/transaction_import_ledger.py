"""Rule matching and ledger expansion for Monthly P&L transaction imports."""

from __future__ import annotations

from decimal import Decimal

from .transaction_import_csv import COLUMN_BUCKET_MAP
from .transaction_import_models import LedgerEntry, MappingRule, ParsedRawRow


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
    if rule.match_operator == "contains":
        for key, expected_val in spec.items():
            if key == "type":
                if expected_val.lower() not in (raw_type or "").lower():
                    return False
            elif key == "description":
                if expected_val.lower() not in (raw_description or "").lower():
                    return False
        return True
    if rule.match_operator == "starts_with":
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
    profile_matches: list[MappingRule] = []
    global_matches: list[MappingRule] = []

    for rule in rules:
        if not _match_rule(rule, raw_type, raw_description):
            continue
        if rule.profile_id and rule.profile_id == profile_id:
            profile_matches.append(rule)
        elif not rule.profile_id:
            global_matches.append(rule)

    candidates = profile_matches if profile_matches else global_matches
    if not candidates:
        return None

    candidates.sort(key=lambda r: r.priority)
    return candidates[0]


def expand_raw_row_to_ledger(
    raw_row: ParsedRawRow,
    rules: list[MappingRule],
    profile_id: str | None,
) -> list[LedgerEntry]:
    if raw_row.entry_month is None:
        return []

    raw_type = raw_row.raw_type
    raw_description = raw_row.raw_description
    normalized_type = (raw_type or "").strip()
    rule = find_matching_rule(rules, raw_type, raw_description, profile_id)
    is_type_rule_row = rule is not None and normalized_type not in ("Order", "Refund")

    entries: list[LedgerEntry] = []
    if normalized_type == "Liquidations":
        handled_columns = {"product_sales", "other_transaction_fees"}
        if raw_row.amounts.get("product_sales", Decimal("0")) != 0:
            entries.append(
                LedgerEntry(
                    entry_month=raw_row.entry_month,
                    posted_at=raw_row.posted_at,
                    order_id=raw_row.order_id,
                    sku=raw_row.sku,
                    raw_type=raw_type,
                    raw_description=raw_description,
                    ledger_bucket="fba_liquidation_proceeds",
                    amount=raw_row.amounts["product_sales"],
                    is_mapped=True,
                    mapping_rule_id=None,
                    source_row_index=raw_row.row_index,
                )
            )
        if raw_row.amounts.get("other_transaction_fees", Decimal("0")) != 0:
            entries.append(
                LedgerEntry(
                    entry_month=raw_row.entry_month,
                    posted_at=raw_row.posted_at,
                    order_id=raw_row.order_id,
                    sku=raw_row.sku,
                    raw_type=raw_type,
                    raw_description=raw_description,
                    ledger_bucket="liquidation_fees",
                    amount=raw_row.amounts["other_transaction_fees"],
                    is_mapped=True,
                    mapping_rule_id=None,
                    source_row_index=raw_row.row_index,
                )
            )
        for col_name, amount in raw_row.amounts.items():
            if col_name in handled_columns or amount == 0:
                continue
            entries.append(
                LedgerEntry(
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
                )
            )
        return entries

    if is_type_rule_row:
        amount = sum(raw_row.amounts.values(), Decimal("0"))
        if amount != 0:
            entries.append(
                LedgerEntry(
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
                )
            )
    else:
        is_refund = normalized_type == "Refund"
        for col_name, amount in raw_row.amounts.items():
            if col_name == "other":
                if normalized_type == "Order":
                    bucket = "other_transaction_fees"
                    is_mapped = True
                elif normalized_type == "Refund":
                    bucket = "refunds"
                    is_mapped = True
                else:
                    bucket = "unmapped"
                    is_mapped = False
                entries.append(
                    LedgerEntry(
                        entry_month=raw_row.entry_month,
                        posted_at=raw_row.posted_at,
                        order_id=raw_row.order_id,
                        sku=raw_row.sku,
                        raw_type=raw_type,
                        raw_description=raw_description,
                        ledger_bucket=bucket,
                        amount=amount,
                        is_mapped=is_mapped,
                        mapping_rule_id=None,
                        source_row_index=raw_row.row_index,
                    )
                )
                continue

            base_bucket = COLUMN_BUCKET_MAP.get(col_name)
            if not base_bucket:
                continue

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

            entries.append(
                LedgerEntry(
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
                )
            )

    return _coalesce_entries_by_bucket(entries)


def _coalesce_entries_by_bucket(entries: list[LedgerEntry]) -> list[LedgerEntry]:
    merged: dict[str, LedgerEntry] = {}
    for entry in entries:
        existing = merged.get(entry.ledger_bucket)
        if existing is None:
            merged[entry.ledger_bucket] = LedgerEntry(
                entry_month=entry.entry_month,
                posted_at=entry.posted_at,
                order_id=entry.order_id,
                sku=entry.sku,
                raw_type=entry.raw_type,
                raw_description=entry.raw_description,
                ledger_bucket=entry.ledger_bucket,
                amount=entry.amount,
                is_mapped=entry.is_mapped,
                mapping_rule_id=entry.mapping_rule_id,
                source_row_index=entry.source_row_index,
            )
            continue

        existing.amount += entry.amount
        existing.is_mapped = existing.is_mapped and entry.is_mapped
        if existing.mapping_rule_id is None:
            existing.mapping_rule_id = entry.mapping_rule_id

    return [entry for entry in merged.values() if entry.amount != 0]
