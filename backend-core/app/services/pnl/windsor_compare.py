"""Compare Windsor settlement data against active Monthly P&L month totals."""

from __future__ import annotations

import csv
import io
import os
from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from supabase import Client

from .profiles import PNLNotFoundError, PNLValidationError


WINDSOR_SETTLEMENT_FIELDS = [
    "account_id",
    "v2_settlement_report_data_flat_file_v2__adjustment_id",
    "v2_settlement_report_data_flat_file_v2__amount",
    "v2_settlement_report_data_flat_file_v2__amount_description",
    "v2_settlement_report_data_flat_file_v2__amount_type",
    "v2_settlement_report_data_flat_file_v2__currency",
    "v2_settlement_report_data_flat_file_v2__deposit_date",
    "v2_settlement_report_data_flat_file_v2__fulfillment_id",
    "v2_settlement_report_data_flat_file_v2__marketplace_name",
    "v2_settlement_report_data_flat_file_v2__merchant_adjustment_item_id",
    "v2_settlement_report_data_flat_file_v2__merchant_order_id",
    "v2_settlement_report_data_flat_file_v2__merchant_order_item_id",
    "v2_settlement_report_data_flat_file_v2__order_id",
    "v2_settlement_report_data_flat_file_v2__order_item_code",
    "v2_settlement_report_data_flat_file_v2__posted_date",
    "v2_settlement_report_data_flat_file_v2__posted_date_time",
    "v2_settlement_report_data_flat_file_v2__promotion_id",
    "v2_settlement_report_data_flat_file_v2__quantity_purchased",
    "v2_settlement_report_data_flat_file_v2__settlement_end_date",
    "v2_settlement_report_data_flat_file_v2__settlement_id",
    "v2_settlement_report_data_flat_file_v2__settlement_start_date",
    "v2_settlement_report_data_flat_file_v2__shipment_id",
    "v2_settlement_report_data_flat_file_v2__sku",
    "v2_settlement_report_data_flat_file_v2__total_amount",
    "v2_settlement_report_data_flat_file_v2__transaction_type",
]

FIELD_AMOUNT = "v2_settlement_report_data_flat_file_v2__amount"
FIELD_AMOUNT_DESCRIPTION = "v2_settlement_report_data_flat_file_v2__amount_description"
FIELD_AMOUNT_TYPE = "v2_settlement_report_data_flat_file_v2__amount_type"
FIELD_MARKETPLACE_NAME = "v2_settlement_report_data_flat_file_v2__marketplace_name"
FIELD_ORDER_ID = "v2_settlement_report_data_flat_file_v2__order_id"
FIELD_POSTED_DATE = "v2_settlement_report_data_flat_file_v2__posted_date"
FIELD_SKU = "v2_settlement_report_data_flat_file_v2__sku"
FIELD_TRANSACTION_TYPE = "v2_settlement_report_data_flat_file_v2__transaction_type"

DEFAULT_TIMEOUT_SECONDS = 360
MIN_TIMEOUT_SECONDS = 60
VALID_MARKETPLACE_SCOPES = {"all", "amazon_com_only", "amazon_com_and_ca"}


@dataclass(frozen=True)
class WindsorMappingResult:
    classification: str
    bucket: str | None
    reason: str | None = None


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _normalize_key(value: Any) -> str:
    return _normalize(value).casefold()


def _parse_decimal(value: Any) -> Decimal:
    text = _normalize(value).replace(",", "")
    if not text:
        return Decimal("0")
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise PNLValidationError(f'Invalid Windsor settlement amount "{text}"') from exc


def _last_day_of_month(entry_month: date) -> date:
    return date(entry_month.year, entry_month.month, monthrange(entry_month.year, entry_month.month)[1])


def _bucket_sort_key(bucket: str) -> tuple[int, str]:
    return (0 if bucket != "unmapped" else 1, bucket)


def _row_matches_marketplace_scope(row: dict[str, Any], marketplace_scope: str) -> bool:
    if marketplace_scope == "all":
        return True

    if not _normalize(row.get(FIELD_MARKETPLACE_NAME)):
        return True

    allowed_marketplaces = {"amazon.com"}
    if marketplace_scope == "amazon_com_and_ca":
        allowed_marketplaces.add("amazon.ca")

    return _normalize_key(row.get(FIELD_MARKETPLACE_NAME)) in allowed_marketplaces


def _classify_windsor_row(row: dict[str, Any], amount: Decimal) -> WindsorMappingResult:
    transaction_type = _normalize_key(row.get(FIELD_TRANSACTION_TYPE))
    amount_type = _normalize_key(row.get(FIELD_AMOUNT_TYPE))
    description = _normalize_key(row.get(FIELD_AMOUNT_DESCRIPTION))

    is_refund_like = "refund" in transaction_type

    if not transaction_type and not amount_type and not description:
        return WindsorMappingResult("ignored", None, "blank_keys")

    if transaction_type == "servicefee" and amount_type == "cost of advertising":
        return WindsorMappingResult("mapped", "advertising")

    if transaction_type == "amazonfees" and amount_type in {
        "coupon participation fee",
        "coupon performance based fee",
    }:
        return WindsorMappingResult("mapped", "promotions_fees")

    if amount_type == "itemprice":
        if description == "principal":
            return WindsorMappingResult("mapped", "refunds" if is_refund_like else "product_sales")
        if description == "shipping":
            return WindsorMappingResult(
                "mapped",
                "shipping_credit_refunds" if is_refund_like else "shipping_credits",
            )
        if description in {"restockingfee", "goodwill"}:
            return WindsorMappingResult("mapped", "refunds")
        if description.startswith("gift"):
            return WindsorMappingResult(
                "mapped",
                "gift_wrap_credit_refunds" if is_refund_like else "gift_wrap_credits",
            )
        if description in {"tax", "shippingtax"}:
            return WindsorMappingResult("ignored", None, "sales_tax")

    if amount_type == "promotion":
        if description in {"principal", "shipping"}:
            if amount >= 0:
                return WindsorMappingResult("mapped", "promotional_rebate_refunds")
            return WindsorMappingResult("mapped", "promotional_rebates")

    if amount_type == "itemfees":
        if description == "commission":
            return WindsorMappingResult("mapped", "referral_fees")
        if description == "fbaperunitfulfillmentfee":
            return WindsorMappingResult("mapped", "fba_fees")
        if description in {"salestaxservicefee", "shippingchargeback", "refundcommission"}:
            return WindsorMappingResult("mapped", "other_transaction_fees")

    if amount_type == "itemwithheldtax":
        if description.startswith("marketplacefacilitator"):
            return WindsorMappingResult("mapped", "marketplace_withheld_tax")
        return WindsorMappingResult("ignored", None, "withheld_tax_other")

    if amount_type in {"fba inventory reimbursement", "mcf inventory reimbursement"}:
        return WindsorMappingResult("mapped", "fba_inventory_credit")

    if amount_type == "other-transaction":
        if description in {"disposalcomplete", "removalcomplete"}:
            return WindsorMappingResult("mapped", "fba_removal_order_fees")
        if description == "storage fee":
            return WindsorMappingResult("mapped", "fba_monthly_storage_fees")
        if description == "storagerenewalbilling":
            return WindsorMappingResult("mapped", "fba_long_term_storage_fees")
        if description == "subscription fee":
            return WindsorMappingResult("mapped", "subscription_fees")
        if description == "fba inbound placement service fee":
            return WindsorMappingResult("mapped", "inbound_placement_and_defect_fees")
        if "freight" in description or "dutie" in description:
            return WindsorMappingResult("mapped", "inbound_shipping_and_duties")
        if "liquidation" in description:
            return WindsorMappingResult("mapped", "liquidation_fees")
        if "transfer" in description or "to your account" in description:
            return WindsorMappingResult("mapped", "non_pnl_transfer")

    if transaction_type == "transfer":
        return WindsorMappingResult("mapped", "non_pnl_transfer")

    return WindsorMappingResult("unmapped", None, "no_bucket_rule")


class WindsorSettlementCompareService:
    def __init__(self, db: Client) -> None:
        self.db = db
        self.api_key = os.getenv("WINDSOR_API_KEY", "").strip()
        self.seller_url = os.getenv(
            "WINDSOR_SELLER_URL",
            "https://connectors.windsor.ai/amazon_sp",
        ).strip()
        configured_timeout = int(os.getenv("WBR_REQUEST_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
        self.timeout_seconds = max(configured_timeout, MIN_TIMEOUT_SECONDS)

    async def compare_month(
        self,
        profile_id: str,
        entry_month: str,
        marketplace_scope: str = "all",
    ) -> dict[str, Any]:
        profile = self._get_profile(profile_id)
        month_date = self._parse_entry_month(entry_month)
        date_from = month_date
        date_to = _last_day_of_month(month_date)
        resolved_marketplace_scope = self._parse_marketplace_scope(marketplace_scope)
        windsor_account_id = self._resolve_windsor_account_id(profile)
        csv_baseline = self._load_csv_baseline(profile_id, entry_month)
        all_windsor_rows = await self._fetch_rows(
            account_id=windsor_account_id,
            date_from=date_from,
            date_to=date_to,
        )
        windsor_rows, excluded_rows = self._split_rows_by_marketplace_scope(
            all_windsor_rows,
            resolved_marketplace_scope,
        )
        windsor_analysis = self._analyze_rows(windsor_rows)
        scope_diagnostics = self._build_scope_diagnostics(
            all_rows=all_windsor_rows,
            included_rows=windsor_rows,
            excluded_rows=excluded_rows,
            marketplace_scope=resolved_marketplace_scope,
        )

        return {
            "profile": {
                "id": str(profile.get("id") or ""),
                "client_id": str(profile.get("client_id") or ""),
                "marketplace_code": str(profile.get("marketplace_code") or ""),
                "currency_code": str(profile.get("currency_code") or ""),
            },
            "entry_month": entry_month,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "marketplace_scope": resolved_marketplace_scope,
            "windsor_account_id": windsor_account_id,
            "csv_baseline": csv_baseline,
            "windsor": windsor_analysis,
            "scope_diagnostics": scope_diagnostics,
            "comparison": {
                "bucket_deltas": self._build_bucket_deltas(
                    csv_baseline["bucket_totals"],
                    windsor_analysis["bucket_totals"],
                ),
            },
        }

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

    def _parse_entry_month(self, value: str) -> date:
        if not value or len(value) != 10:
            raise PNLValidationError("entry_month must be YYYY-MM-01")
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise PNLValidationError("entry_month must be YYYY-MM-01") from exc
        if parsed.day != 1:
            raise PNLValidationError("entry_month must be YYYY-MM-01")
        return parsed

    def _parse_marketplace_scope(self, value: str | None) -> str:
        scope = _normalize(value) or "all"
        if scope not in VALID_MARKETPLACE_SCOPES:
            raise PNLValidationError(
                "marketplace_scope must be one of: all, amazon_com_only, amazon_com_and_ca"
            )
        return scope

    def _split_rows_by_marketplace_scope(
        self,
        rows: list[dict[str, Any]],
        marketplace_scope: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if marketplace_scope == "all":
            return rows, []

        included_rows: list[dict[str, Any]] = []
        excluded_rows: list[dict[str, Any]] = []
        for row in rows:
            if _row_matches_marketplace_scope(row, marketplace_scope):
                included_rows.append(row)
            else:
                excluded_rows.append(row)
        return included_rows, excluded_rows

    def _resolve_windsor_account_id(self, profile: dict[str, Any]) -> str:
        client_id = str(profile.get("client_id") or "").strip()
        marketplace_code = str(profile.get("marketplace_code") or "").strip().upper()
        response = (
            self.db.table("wbr_profiles")
            .select("id, windsor_account_id")
            .eq("client_id", client_id)
            .eq("marketplace_code", marketplace_code)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise PNLValidationError(
                f"No matching WBR profile with Windsor account was found for {marketplace_code}"
            )
        account_id = _normalize(rows[0].get("windsor_account_id"))
        if not account_id:
            raise PNLValidationError(
                f"WBR profile for {marketplace_code} is missing windsor_account_id"
            )
        return account_id

    def _load_csv_baseline(self, profile_id: str, entry_month: str) -> dict[str, Any]:
        active_months_resp = (
            self.db.table("monthly_pnl_import_months")
            .select("id, import_id, entry_month")
            .eq("profile_id", profile_id)
            .eq("entry_month", entry_month)
            .eq("is_active", True)
            .order("created_at", desc=True)
            .execute()
        )
        active_month_rows = active_months_resp.data if isinstance(active_months_resp.data, list) else []
        if not active_month_rows:
            raise PNLValidationError(f"No active Monthly P&L import month exists for {entry_month}")

        import_month_ids = [str(row.get("id") or "").strip() for row in active_month_rows if row.get("id")]
        import_ids = list(
            {
                str(row.get("import_id") or "").strip()
                for row in active_month_rows
                if row.get("import_id")
            }
        )

        import_rows: list[dict[str, Any]] = []
        if import_ids:
            imports_resp = (
                self.db.table("monthly_pnl_imports")
                .select("id, source_type, source_filename, import_status, created_at, finished_at")
                .in_("id", import_ids)
                .execute()
            )
            import_rows = imports_resp.data if isinstance(imports_resp.data, list) else []
        import_by_id = {str(row.get("id") or "").strip(): row for row in import_rows}

        total_rows: list[dict[str, Any]] = []
        if import_month_ids:
            totals_resp = (
                self.db.table("monthly_pnl_import_month_bucket_totals")
                .select("import_month_id, ledger_bucket, amount")
                .in_("import_month_id", import_month_ids)
                .execute()
            )
            total_rows = totals_resp.data if isinstance(totals_resp.data, list) else []
        bucket_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for row in total_rows:
            bucket = _normalize(row.get("ledger_bucket"))
            import_month_id = _normalize(row.get("import_month_id"))
            if not bucket or import_month_id not in import_month_ids:
                continue
            bucket_totals[bucket] += _parse_decimal(row.get("amount"))

        active_imports: list[dict[str, Any]] = []
        for row in active_month_rows:
            import_id = _normalize(row.get("import_id"))
            import_row = import_by_id.get(import_id, {})
            active_imports.append(
                {
                    "import_month_id": _normalize(row.get("id")),
                    "import_id": import_id,
                    "source_type": _normalize(import_row.get("source_type")),
                    "source_filename": import_row.get("source_filename"),
                    "import_status": _normalize(import_row.get("import_status")),
                    "created_at": import_row.get("created_at"),
                    "finished_at": import_row.get("finished_at"),
                }
            )

        return {
            "active_imports": active_imports,
            "bucket_totals": self._serialize_bucket_totals(bucket_totals),
        }

    async def _fetch_rows(
        self,
        *,
        account_id: str,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        if not self.api_key:
            raise PNLValidationError("WINDSOR_API_KEY is not configured")
        if not self.seller_url:
            raise PNLValidationError("WINDSOR_SELLER_URL is not configured")

        params = {
            "api_key": self.api_key,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "fields": ",".join(WINDSOR_SETTLEMENT_FIELDS),
            "select_accounts": account_id,
        }

        timeout = httpx.Timeout(timeout=self.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(self.seller_url, params=params)

        if response.status_code >= 400:
            body_preview = response.text.strip().replace("\n", " ")[:220]
            raise PNLValidationError(
                f"Windsor settlement request failed: {response.status_code} :: {body_preview}"
            )

        body = response.text.lstrip("\ufeff").strip()
        if not body:
            return []

        content_type = response.headers.get("content-type", "").lower()
        if "json" in content_type or body.startswith("[") or body.startswith("{"):
            try:
                payload = response.json()
            except Exception as exc:  # noqa: BLE001
                raise PNLValidationError(f"Failed to decode Windsor settlement JSON: {exc}") from exc
            if isinstance(payload, list):
                return [row for row in payload if isinstance(row, dict)]
            if isinstance(payload, dict):
                for key in ("data", "results", "records"):
                    value = payload.get(key)
                    if isinstance(value, list):
                        return [row for row in value if isinstance(row, dict)]
            raise PNLValidationError("Unexpected Windsor settlement payload shape")

        return [dict(row) for row in csv.DictReader(io.StringIO(body))]

    def _analyze_rows(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        bucket_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        marketplace_totals: dict[str, dict[str, Any]] = {}
        combo_totals: dict[tuple[str, str, str], dict[str, Any]] = {}
        mapped_combo_totals_by_bucket: dict[str, dict[tuple[str, str, str], dict[str, Any]]] = defaultdict(dict)
        mapped_marketplace_totals_by_bucket: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        mapped_rows = 0
        ignored_rows = 0
        unmapped_rows = 0
        ignored_amount = Decimal("0")
        unmapped_amount = Decimal("0")

        for row in rows:
            amount = _parse_decimal(row.get(FIELD_AMOUNT))
            mapping = _classify_windsor_row(row, amount)
            marketplace_name = _normalize(row.get(FIELD_MARKETPLACE_NAME)) or "(blank)"
            marketplace_summary = marketplace_totals.setdefault(
                marketplace_name,
                {"marketplace_name": marketplace_name, "row_count": 0, "amount": Decimal("0")},
            )
            marketplace_summary["row_count"] += 1
            marketplace_summary["amount"] += amount

            combo_key = (
                _normalize(row.get(FIELD_TRANSACTION_TYPE)),
                _normalize(row.get(FIELD_AMOUNT_TYPE)),
                _normalize(row.get(FIELD_AMOUNT_DESCRIPTION)),
            )
            combo_summary = combo_totals.setdefault(
                combo_key,
                {
                    "transaction_type": combo_key[0],
                    "amount_type": combo_key[1],
                    "amount_description": combo_key[2],
                    "classification": mapping.classification,
                    "bucket": mapping.bucket,
                    "reason": mapping.reason,
                    "row_count": 0,
                    "amount": Decimal("0"),
                },
            )
            combo_summary["row_count"] += 1
            combo_summary["amount"] += amount

            if mapping.classification == "mapped" and mapping.bucket:
                bucket_totals[mapping.bucket] += amount
                mapped_rows += 1
                bucket_combo_totals = mapped_combo_totals_by_bucket[mapping.bucket]
                mapped_combo_summary = bucket_combo_totals.setdefault(
                    combo_key,
                    {
                        "transaction_type": combo_key[0],
                        "amount_type": combo_key[1],
                        "amount_description": combo_key[2],
                        "classification": mapping.classification,
                        "bucket": mapping.bucket,
                        "reason": mapping.reason,
                        "row_count": 0,
                        "amount": Decimal("0"),
                    },
                )
                mapped_combo_summary["row_count"] += 1
                mapped_combo_summary["amount"] += amount

                bucket_marketplace_totals = mapped_marketplace_totals_by_bucket[mapping.bucket]
                mapped_marketplace_summary = bucket_marketplace_totals.setdefault(
                    marketplace_name,
                    {"marketplace_name": marketplace_name, "row_count": 0, "amount": Decimal("0")},
                )
                mapped_marketplace_summary["row_count"] += 1
                mapped_marketplace_summary["amount"] += amount
            elif mapping.classification == "ignored":
                ignored_rows += 1
                ignored_amount += amount
            else:
                unmapped_rows += 1
                unmapped_amount += amount

        top_unmapped = [
            self._serialize_combo(summary)
            for summary in sorted(
                (summary for summary in combo_totals.values() if summary["classification"] == "unmapped"),
                key=lambda summary: (abs(summary["amount"]), summary["row_count"]),
                reverse=True,
            )[:25]
        ]
        top_ignored = [
            self._serialize_combo(summary)
            for summary in sorted(
                (summary for summary in combo_totals.values() if summary["classification"] == "ignored"),
                key=lambda summary: (abs(summary["amount"]), summary["row_count"]),
                reverse=True,
            )[:25]
        ]

        return {
            "row_count": len(rows),
            "mapped_row_count": mapped_rows,
            "ignored_row_count": ignored_rows,
            "unmapped_row_count": unmapped_rows,
            "ignored_amount": self._format_amount(ignored_amount),
            "unmapped_amount": self._format_amount(unmapped_amount),
            "bucket_totals": self._serialize_bucket_totals(bucket_totals),
            "marketplace_totals": [
                {
                    "marketplace_name": summary["marketplace_name"],
                    "row_count": summary["row_count"],
                    "amount": self._format_amount(summary["amount"]),
                }
                for summary in sorted(
                    marketplace_totals.values(),
                    key=lambda summary: (abs(summary["amount"]), summary["row_count"]),
                    reverse=True,
                )
            ],
            "mapped_bucket_drilldowns": [
                {
                    "bucket": bucket,
                    "combo_totals": [
                        self._serialize_combo(summary)
                        for summary in sorted(
                            mapped_combo_totals_by_bucket[bucket].values(),
                            key=lambda summary: (abs(summary["amount"]), summary["row_count"]),
                            reverse=True,
                        )
                    ],
                    "marketplace_totals": [
                        {
                            "marketplace_name": summary["marketplace_name"],
                            "row_count": summary["row_count"],
                            "amount": self._format_amount(summary["amount"]),
                        }
                        for summary in sorted(
                            mapped_marketplace_totals_by_bucket[bucket].values(),
                            key=lambda summary: (abs(summary["amount"]), summary["row_count"]),
                            reverse=True,
                        )
                    ],
                }
                for bucket in sorted(mapped_combo_totals_by_bucket, key=_bucket_sort_key)
            ],
            "top_unmapped_combos": top_unmapped,
            "top_ignored_combos": top_ignored,
        }

    def _build_bucket_deltas(
        self,
        csv_bucket_totals: dict[str, str],
        windsor_bucket_totals: dict[str, str],
    ) -> list[dict[str, Any]]:
        buckets = sorted(set(csv_bucket_totals) | set(windsor_bucket_totals), key=_bucket_sort_key)
        deltas: list[dict[str, Any]] = []
        for bucket in buckets:
            csv_amount = _parse_decimal(csv_bucket_totals.get(bucket))
            windsor_amount = _parse_decimal(windsor_bucket_totals.get(bucket))
            deltas.append(
                {
                    "bucket": bucket,
                    "csv_amount": self._format_amount(csv_amount),
                    "windsor_amount": self._format_amount(windsor_amount),
                    "delta_amount": self._format_amount(windsor_amount - csv_amount),
                }
            )
        deltas.sort(key=lambda row: abs(_parse_decimal(row["delta_amount"])), reverse=True)
        return deltas

    def _build_scope_diagnostics(
        self,
        *,
        all_rows: list[dict[str, Any]],
        included_rows: list[dict[str, Any]],
        excluded_rows: list[dict[str, Any]],
        marketplace_scope: str,
    ) -> dict[str, Any]:
        excluded_amount = sum((_parse_decimal(row.get(FIELD_AMOUNT)) for row in excluded_rows), Decimal("0"))
        blank_marketplace_rows = [
            row for row in excluded_rows if not _normalize(row.get(FIELD_MARKETPLACE_NAME))
        ]
        blank_marketplace_amount = sum(
            (_parse_decimal(row.get(FIELD_AMOUNT)) for row in blank_marketplace_rows),
            Decimal("0"),
        )
        excluded_analysis = self._analyze_rows(excluded_rows)
        blank_marketplace_analysis = self._analyze_rows(blank_marketplace_rows)

        return {
            "marketplace_scope": marketplace_scope,
            "total_row_count": len(all_rows),
            "included_row_count": len(included_rows),
            "excluded_row_count": len(excluded_rows),
            "excluded_amount": self._format_amount(excluded_amount),
            "blank_marketplace_row_count": len(blank_marketplace_rows),
            "blank_marketplace_amount": self._format_amount(blank_marketplace_amount),
            "excluded_marketplace_totals": excluded_analysis["marketplace_totals"],
            "excluded_bucket_totals": self._serialize_bucket_total_rows(excluded_analysis["bucket_totals"]),
            "top_excluded_combos": self._top_combo_summaries(excluded_rows),
            "blank_marketplace_bucket_totals": self._serialize_bucket_total_rows(
                blank_marketplace_analysis["bucket_totals"]
            ),
            "top_blank_marketplace_combos": self._top_combo_summaries(blank_marketplace_rows),
        }

    def _serialize_bucket_totals(self, totals: dict[str, Decimal]) -> dict[str, str]:
        return {
            bucket: self._format_amount(totals[bucket])
            for bucket in sorted(totals, key=_bucket_sort_key)
        }

    def _serialize_bucket_total_rows(self, totals: dict[str, str]) -> list[dict[str, Any]]:
        rows = [
            {"bucket": bucket, "amount": amount}
            for bucket, amount in totals.items()
            if _parse_decimal(amount) != 0
        ]
        rows.sort(key=lambda row: abs(_parse_decimal(row["amount"])), reverse=True)
        return rows

    def _top_combo_summaries(
        self,
        rows: list[dict[str, Any]],
        *,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        combo_totals: dict[tuple[str, str, str], dict[str, Any]] = {}

        for row in rows:
            amount = _parse_decimal(row.get(FIELD_AMOUNT))
            mapping = _classify_windsor_row(row, amount)
            combo_key = (
                _normalize(row.get(FIELD_TRANSACTION_TYPE)),
                _normalize(row.get(FIELD_AMOUNT_TYPE)),
                _normalize(row.get(FIELD_AMOUNT_DESCRIPTION)),
            )
            summary = combo_totals.setdefault(
                combo_key,
                {
                    "transaction_type": combo_key[0],
                    "amount_type": combo_key[1],
                    "amount_description": combo_key[2],
                    "classification": mapping.classification,
                    "bucket": mapping.bucket,
                    "reason": mapping.reason,
                    "row_count": 0,
                    "amount": Decimal("0"),
                },
            )
            summary["row_count"] += 1
            summary["amount"] += amount

        return [
            self._serialize_combo(summary)
            for summary in sorted(
                combo_totals.values(),
                key=lambda summary: (abs(summary["amount"]), summary["row_count"]),
                reverse=True,
            )[:limit]
        ]

    def _serialize_combo(self, summary: dict[str, Any]) -> dict[str, Any]:
        return {
            "transaction_type": summary["transaction_type"],
            "amount_type": summary["amount_type"],
            "amount_description": summary["amount_description"],
            "classification": summary["classification"],
            "bucket": summary["bucket"],
            "reason": summary["reason"],
            "row_count": summary["row_count"],
            "amount": self._format_amount(summary["amount"]),
        }

    @staticmethod
    def _format_amount(value: Decimal) -> str:
        return format(value.quantize(Decimal("0.01")), "f")
