"""Monthly P&L report service.

Builds a monthly profit & loss statement from active ledger entries
and optional COGS data.  All derived totals (net revenue, gross profit,
net earnings) are computed at query time — never stored.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from supabase import Client

from .profiles import PNLNotFoundError, PNLValidationError

# ── Report line-item definitions ─────────────────────────────────────
# Each tuple: (key, label, category, list_of_source_buckets | None)
# None means "derived" — computed from other line items.

REVENUE_BUCKETS = [
    ("product_sales", "Product Sales", "revenue"),
    ("shipping_credits", "Shipping Credits", "revenue"),
    ("gift_wrap_credits", "Gift Wrap Credits", "revenue"),
    ("promotional_rebate_refunds", "Promotional Rebate Refunds", "revenue"),
    ("fba_liquidation_proceeds", "FBA Liquidation Proceeds", "revenue"),
]

REFUND_BUCKETS = [
    ("refunds", "Product Refunds", "refunds"),
    ("fba_inventory_credit", "FBA Inventory Credits", "refunds"),
    ("shipping_credit_refunds", "Shipping Credit Refunds", "refunds"),
    ("gift_wrap_credit_refunds", "Gift Wrap Credit Refunds", "refunds"),
    ("promotional_rebates", "Promotional Rebates", "refunds"),
    ("a_to_z_guarantee_claims", "A-to-z Guarantee Claims", "refunds"),
    ("chargebacks", "Chargebacks", "refunds"),
]

EXPENSE_BUCKETS = [
    ("referral_fees", "Referral Fees", "expenses"),
    ("fba_fees", "FBA Fulfillment Fees", "expenses"),
    ("other_transaction_fees", "Other Transaction Fees", "expenses"),
    ("fba_monthly_storage_fees", "FBA Monthly Storage Fees", "expenses"),
    ("fba_long_term_storage_fees", "FBA Long-Term Storage Fees", "expenses"),
    ("fba_removal_order_fees", "FBA Removal / Disposal Fees", "expenses"),
    ("subscription_fees", "Subscription Fees", "expenses"),
    ("inbound_placement_and_defect_fees", "Inbound Placement & Defect Fees", "expenses"),
    ("inbound_shipping_and_duties", "Inbound Shipping Fees & Duties", "expenses"),
    ("liquidation_fees", "Liquidation Fees", "expenses"),
    ("promotions_fees", "Promotions Fees", "expenses"),
    ("advertising", "Advertising", "expenses"),
    ("service_fee", "Other Service Fees", "expenses"),
]

def _q(d: Decimal) -> str:
    """Quantize to 2 decimal places and return string."""
    return format(d.quantize(Decimal("0.01")), "f")


def _resolve_months(
    filter_mode: str,
    start_month: str | None,
    end_month: str | None,
) -> tuple[date, date]:
    """Return (start, end) first-of-month dates for the requested range."""
    today = datetime.now(UTC).date()
    first_of_this_month = date(today.year, today.month, 1)

    if filter_mode == "ytd":
        return date(today.year, 1, 1), first_of_this_month
    elif filter_mode in ("last_3", "last_6", "last_12"):
        # "last_N" = current month + previous N-1 months (N total)
        n = {"last_3": 3, "last_6": 6, "last_12": 12}[filter_mode]
        m = today.month - (n - 1)
        y = today.year
        while m < 1:
            m += 12
            y -= 1
        return date(y, m, 1), first_of_this_month
    elif filter_mode == "range":
        if not start_month or not end_month:
            raise PNLValidationError("start_month and end_month required for range filter")
        try:
            s = date.fromisoformat(start_month)
            e = date.fromisoformat(end_month)
        except ValueError as exc:
            raise PNLValidationError(f"Invalid date format: {exc}") from exc
        return date(s.year, s.month, 1), date(e.year, e.month, 1)
    else:
        raise PNLValidationError(f"Unknown filter_mode: {filter_mode}")


def _month_range(start: date, end: date) -> list[str]:
    """Generate list of YYYY-MM-DD first-of-month strings from start to end inclusive."""
    months: list[str] = []
    y, m = start.year, start.month
    while date(y, m, 1) <= end:
        months.append(date(y, m, 1).isoformat())
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


# ── Report service ───────────────────────────────────────────────────


class PNLReportService:
    def __init__(self, db: Client) -> None:
        self.db = db

    def build_report(
        self,
        profile_id: str,
        *,
        filter_mode: str = "ytd",
        start_month: str | None = None,
        end_month: str | None = None,
    ) -> dict[str, Any]:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.build_report_async(
                    profile_id,
                    filter_mode=filter_mode,
                    start_month=start_month,
                    end_month=end_month,
                )
            )
        raise RuntimeError("build_report() cannot run inside an event loop; use build_report_async()")

    async def build_report_async(
        self,
        profile_id: str,
        *,
        filter_mode: str = "ytd",
        start_month: str | None = None,
        end_month: str | None = None,
    ) -> dict[str, Any]:
        """Build the full P&L report for a profile."""
        profile = await asyncio.to_thread(self._get_profile, profile_id)
        period_start, period_end = _resolve_months(filter_mode, start_month, end_month)
        month_keys = _month_range(period_start, period_end)

        if not month_keys:
            return self._empty_report(profile, month_keys)

        bucket_totals, cogs_totals, unmapped_totals, active_months = await asyncio.gather(
            asyncio.to_thread(self._load_ledger_totals, profile_id, period_start, period_end),
            asyncio.to_thread(self._load_cogs_totals, profile_id, period_start, period_end),
            asyncio.to_thread(self._load_unmapped_totals, profile_id, period_start, period_end),
            asyncio.to_thread(self._load_active_months, profile_id, period_start, period_end),
        )

        # Build line items
        line_items: list[dict[str, Any]] = []

        # Revenue section
        for key, label, cat in REVENUE_BUCKETS:
            line_items.append(self._bucket_line(key, label, cat, month_keys, bucket_totals))
        line_items.append(self._derived_line(
            "total_gross_revenue", "Total Gross Revenue", "summary",
            month_keys, [b[0] for b in REVENUE_BUCKETS], bucket_totals,
        ))

        # Refunds & adjustments section
        for key, label, cat in REFUND_BUCKETS:
            line_items.append(self._bucket_line(key, label, cat, month_keys, bucket_totals))
        line_items.append(self._derived_line(
            "total_refunds", "Total Refunds & Adjustments", "summary",
            month_keys, [b[0] for b in REFUND_BUCKETS], bucket_totals,
        ))

        # Net Revenue = Gross Revenue + Refunds/Adjustments
        net_rev_sources = (
            [b[0] for b in REVENUE_BUCKETS]
            + [b[0] for b in REFUND_BUCKETS]
        )
        line_items.append(self._derived_line(
            "total_net_revenue", "Total Net Revenue", "summary",
            month_keys, net_rev_sources, bucket_totals,
        ))

        # COGS
        cogs_line = self._cogs_line(month_keys, cogs_totals)
        line_items.append(cogs_line)

        # Gross Profit = Net Revenue - COGS
        gross_profit_months: dict[str, str] = {}
        net_rev_line = next(l for l in line_items if l["key"] == "total_net_revenue")
        for mk in month_keys:
            nr = Decimal(net_rev_line["months"].get(mk, "0"))
            c = Decimal(cogs_line["months"].get(mk, "0"))
            gross_profit_months[mk] = _q(nr - c)
        line_items.append({
            "key": "gross_profit",
            "label": "Gross Profit",
            "category": "summary",
            "is_derived": True,
            "months": gross_profit_months,
        })

        # Expenses section
        for key, label, cat in EXPENSE_BUCKETS:
            line_items.append(self._bucket_line(key, label, cat, month_keys, bucket_totals))
        line_items.append(self._derived_line(
            "total_expenses", "Total Expenses", "summary",
            month_keys, [b[0] for b in EXPENSE_BUCKETS], bucket_totals,
        ))

        # Net Earnings = Gross Profit + Total Expenses (expenses are negative)
        net_earnings_months: dict[str, str] = {}
        total_exp_line = next(l for l in line_items if l["key"] == "total_expenses")
        for mk in month_keys:
            gp = Decimal(gross_profit_months[mk])
            exp = Decimal(total_exp_line["months"].get(mk, "0"))
            net_earnings_months[mk] = _q(gp + exp)
        line_items.append({
            "key": "net_earnings",
            "label": "Net Earnings",
            "category": "bottom_line",
            "is_derived": True,
            "months": net_earnings_months,
        })

        # Warnings
        warnings = self._build_warnings(
            month_keys, cogs_totals, unmapped_totals, active_months,
        )

        return {
            "profile": profile,
            "months": month_keys,
            "line_items": line_items,
            "warnings": warnings,
        }

    # ── Helpers ───────────────────────────────────────────────────────

    def _empty_report(
        self, profile: dict[str, Any], month_keys: list[str]
    ) -> dict[str, Any]:
        return {
            "profile": profile,
            "months": month_keys,
            "line_items": [],
            "warnings": [],
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

    def _load_ledger_totals(
        self, profile_id: str, start: date, end: date
    ) -> dict[str, dict[str, Decimal]]:
        """Return {bucket: {month_iso: total}} from active import months only."""
        active_ids = self._active_import_month_ids(profile_id, start, end)
        if not active_ids:
            return {}

        summary_totals = self._load_bucket_totals_from_summary_table(
            profile_id=profile_id,
            start=start,
            end=end,
            active_import_month_ids=active_ids,
        )
        if summary_totals is not None:
            return summary_totals

        rpc_totals = self._load_ledger_totals_via_rpc(profile_id, start, end)
        if rpc_totals is not None:
            return rpc_totals

        raise RuntimeError(
            "Failed to load Monthly P&L ledger totals from both summary table and RPC."
        )

    def _load_bucket_totals_from_summary_table(
        self,
        *,
        profile_id: str,
        start: date,
        end: date,
        active_import_month_ids: set[str],
    ) -> dict[str, dict[str, Decimal]] | None:
        try:
            response = (
                self.db.table("monthly_pnl_import_month_bucket_totals")
                .select("import_month_id, entry_month, ledger_bucket, amount")
                .eq("profile_id", profile_id)
                .gte("entry_month", start.isoformat())
                .lte("entry_month", end.isoformat())
                .execute()
            )
        except Exception:
            return None

        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            return None

        totals: dict[str, dict[str, Decimal]] = {}
        matched_row_count = 0
        for row in rows:
            if str(row.get("import_month_id") or "") not in active_import_month_ids:
                continue
            bucket = row.get("ledger_bucket")
            month = row.get("entry_month")
            if not bucket or not month:
                continue
            matched_row_count += 1
            amount = Decimal(str(row.get("amount", "0")))
            if bucket not in totals:
                totals[bucket] = {}
            totals[bucket][month] = totals[bucket].get(month, Decimal("0")) + amount

        if matched_row_count == 0:
            return None
        return totals

    def _load_ledger_totals_via_rpc(
        self, profile_id: str, start: date, end: date
    ) -> dict[str, dict[str, Decimal]] | None:
        try:
            response = self.db.rpc(
                "pnl_report_bucket_totals",
                {
                    "p_profile_id": profile_id,
                    "p_start_month": start.isoformat(),
                    "p_end_month": end.isoformat(),
                },
            ).execute()
        except Exception:
            return None

        rows = response.data
        if not isinstance(rows, list):
            return None

        totals: dict[str, dict[str, Decimal]] = {}
        for row in rows:
            bucket = row.get("ledger_bucket")
            month = row.get("entry_month")
            if not bucket or not month:
                continue
            amount = Decimal(str(row.get("amount", "0")))
            if bucket not in totals:
                totals[bucket] = {}
            totals[bucket][month] = totals[bucket].get(month, Decimal("0")) + amount
        return totals

    def _active_import_month_ids(
        self, profile_id: str, start: date, end: date
    ) -> set[str]:
        response = (
            self.db.table("monthly_pnl_import_months")
            .select("id")
            .eq("profile_id", profile_id)
            .eq("is_active", True)
            .gte("entry_month", start.isoformat())
            .lte("entry_month", end.isoformat())
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        return {str(r["id"]) for r in rows}

    def _load_cogs_totals(
        self, profile_id: str, start: date, end: date
    ) -> dict[str, Decimal]:
        """Return {month_iso: total_cogs}."""
        response = (
            self.db.table("monthly_pnl_cogs_monthly")
            .select("entry_month, amount")
            .eq("profile_id", profile_id)
            .gte("entry_month", start.isoformat())
            .lte("entry_month", end.isoformat())
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        totals: dict[str, Decimal] = {}
        for row in rows:
            month = row["entry_month"]
            amount = Decimal(str(row["amount"]))
            totals[month] = totals.get(month, Decimal("0")) + amount
        return totals

    def _load_unmapped_totals(
        self, profile_id: str, start: date, end: date
    ) -> dict[str, Decimal]:
        """Return {month_iso: unmapped_amount} from active import months."""
        response = (
            self.db.table("monthly_pnl_import_months")
            .select("entry_month, unmapped_amount")
            .eq("profile_id", profile_id)
            .eq("is_active", True)
            .gte("entry_month", start.isoformat())
            .lte("entry_month", end.isoformat())
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        totals: dict[str, Decimal] = {}
        for row in rows:
            amt = Decimal(str(row.get("unmapped_amount", "0")))
            if amt != 0:
                totals[row["entry_month"]] = amt
        return totals

    def _load_active_months(
        self, profile_id: str, start: date, end: date
    ) -> set[str]:
        """Return set of month ISOs that have active data."""
        response = (
            self.db.table("monthly_pnl_import_months")
            .select("entry_month")
            .eq("profile_id", profile_id)
            .eq("is_active", True)
            .gte("entry_month", start.isoformat())
            .lte("entry_month", end.isoformat())
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        return {row["entry_month"] for row in rows}

    def _bucket_line(
        self,
        key: str,
        label: str,
        category: str,
        month_keys: list[str],
        bucket_totals: dict[str, dict[str, Decimal]],
    ) -> dict[str, Any]:
        bucket_data = bucket_totals.get(key, {})
        months = {mk: _q(bucket_data.get(mk, Decimal("0"))) for mk in month_keys}
        return {
            "key": key,
            "label": label,
            "category": category,
            "is_derived": False,
            "months": months,
        }

    def _derived_line(
        self,
        key: str,
        label: str,
        category: str,
        month_keys: list[str],
        source_buckets: list[str],
        bucket_totals: dict[str, dict[str, Decimal]],
    ) -> dict[str, Any]:
        months: dict[str, str] = {}
        for mk in month_keys:
            total = Decimal("0")
            for bucket in source_buckets:
                total += bucket_totals.get(bucket, {}).get(mk, Decimal("0"))
            months[mk] = _q(total)
        return {
            "key": key,
            "label": label,
            "category": category,
            "is_derived": True,
            "months": months,
        }

    def _cogs_line(
        self,
        month_keys: list[str],
        cogs_totals: dict[str, Decimal],
    ) -> dict[str, Any]:
        months = {mk: _q(cogs_totals.get(mk, Decimal("0"))) for mk in month_keys}
        return {
            "key": "cogs",
            "label": "Cost of Goods Sold",
            "category": "cogs",
            "is_derived": False,
            "months": months,
        }

    def _build_warnings(
        self,
        month_keys: list[str],
        cogs_totals: dict[str, Decimal],
        unmapped_totals: dict[str, Decimal],
        active_months: set[str],
    ) -> list[dict[str, Any]]:
        warnings: list[dict[str, Any]] = []

        # Missing COGS
        missing_cogs = [mk for mk in month_keys if mk not in cogs_totals]
        if missing_cogs:
            warnings.append({
                "type": "missing_cogs",
                "message": "COGS data not uploaded for these months — gross profit will be overstated",
                "months": missing_cogs,
            })

        # Unmapped rows
        unmapped_months = [mk for mk in month_keys if mk in unmapped_totals]
        if unmapped_months:
            warnings.append({
                "type": "unmapped_rows",
                "message": "Some transaction rows could not be mapped to P&L categories",
                "months": unmapped_months,
            })

        # Missing data (no active import for month)
        missing_data = [mk for mk in month_keys if mk not in active_months]
        if missing_data:
            warnings.append({
                "type": "missing_data",
                "message": "No transaction data uploaded for these months",
                "months": missing_data,
            })

        return warnings
