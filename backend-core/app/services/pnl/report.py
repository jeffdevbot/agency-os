"""Monthly P&L report service.

Builds a monthly profit & loss statement from active ledger entries
and optional COGS data.  All derived totals (net revenue, gross profit,
net earnings) are computed at query time — never stored.
"""

from __future__ import annotations

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
]

REFUND_BUCKETS = [
    ("refunds", "Product Refunds", "refunds"),
    ("shipping_credit_refunds", "Shipping Credit Refunds", "refunds"),
    ("gift_wrap_credit_refunds", "Gift Wrap Credit Refunds", "refunds"),
    ("promotional_rebate_refunds", "Promotional Rebate Refunds", "refunds"),
]

PROMO_BUCKETS = [
    ("promotional_rebates", "Promotional Rebates", "promos"),
]

EXPENSE_BUCKETS = [
    ("referral_fees", "Referral Fees", "expenses"),
    ("fba_fees", "FBA Fulfillment Fees", "expenses"),
    ("advertising", "Advertising", "expenses"),
    ("subscription_fees", "Subscription Fees", "expenses"),
    ("fba_monthly_storage_fees", "FBA Monthly Storage Fees", "expenses"),
    ("fba_long_term_storage_fees", "FBA Long-Term Storage Fees", "expenses"),
    ("fba_removal_order_fees", "FBA Removal / Disposal Fees", "expenses"),
    ("inbound_placement_and_defect_fees", "Inbound Placement & Defect Fees", "expenses"),
    ("other_transaction_fees", "Other Transaction Fees", "expenses"),
    ("marketplace_withheld_tax", "Marketplace Withheld Tax", "expenses"),
    ("service_fee", "Other Service Fees", "expenses"),
    ("fba_inventory_credit", "FBA Inventory Credits", "expenses"),
]

# Buckets excluded from the P&L (non-operational)
NON_PNL_BUCKETS = {"non_pnl_transfer", "unmapped"}


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
    elif filter_mode == "last_3":
        m = today.month - 3
        y = today.year
        while m < 1:
            m += 12
            y -= 1
        return date(y, m, 1), first_of_this_month
    elif filter_mode == "last_6":
        m = today.month - 6
        y = today.year
        while m < 1:
            m += 12
            y -= 1
        return date(y, m, 1), first_of_this_month
    elif filter_mode == "last_12":
        m = today.month - 12
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
        """Build the full P&L report for a profile."""
        profile = self._get_profile(profile_id)
        period_start, period_end = _resolve_months(filter_mode, start_month, end_month)
        month_keys = _month_range(period_start, period_end)

        if not month_keys:
            return self._empty_report(profile, month_keys)

        # Load ledger bucket totals per month (only from active import months)
        bucket_totals = self._load_ledger_totals(profile_id, period_start, period_end)

        # Load COGS per month
        cogs_totals = self._load_cogs_totals(profile_id, period_start, period_end)

        # Load warnings data
        unmapped_totals = self._load_unmapped_totals(profile_id, period_start, period_end)
        active_months = self._load_active_months(profile_id, period_start, period_end)

        # Build line items
        line_items: list[dict[str, Any]] = []

        # Revenue section
        for key, label, cat in REVENUE_BUCKETS:
            line_items.append(self._bucket_line(key, label, cat, month_keys, bucket_totals))
        line_items.append(self._derived_line(
            "total_gross_revenue", "Total Gross Revenue", "summary",
            month_keys, [b[0] for b in REVENUE_BUCKETS], bucket_totals,
        ))

        # Refunds section
        for key, label, cat in REFUND_BUCKETS:
            line_items.append(self._bucket_line(key, label, cat, month_keys, bucket_totals))
        line_items.append(self._derived_line(
            "total_refunds", "Total Refunds", "summary",
            month_keys, [b[0] for b in REFUND_BUCKETS], bucket_totals,
        ))

        # Promos
        for key, label, cat in PROMO_BUCKETS:
            line_items.append(self._bucket_line(key, label, cat, month_keys, bucket_totals))

        # Net Revenue = Gross Revenue + Refunds + Promos
        net_rev_sources = (
            [b[0] for b in REVENUE_BUCKETS]
            + [b[0] for b in REFUND_BUCKETS]
            + [b[0] for b in PROMO_BUCKETS]
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
        # Query ledger entries joined through active import_months
        response = (
            self.db.table("monthly_pnl_ledger_entries")
            .select("entry_month, ledger_bucket, amount, import_month_id")
            .eq("profile_id", profile_id)
            .gte("entry_month", start.isoformat())
            .lte("entry_month", end.isoformat())
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []

        # Load active import_month IDs to filter
        active_ids = self._active_import_month_ids(profile_id, start, end)

        totals: dict[str, dict[str, Decimal]] = {}
        for row in rows:
            if row.get("import_month_id") not in active_ids:
                continue
            bucket = row["ledger_bucket"]
            month = row["entry_month"]
            amount = Decimal(str(row["amount"]))
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
            .select("entry_month, cogs_amount")
            .eq("profile_id", profile_id)
            .gte("entry_month", start.isoformat())
            .lte("entry_month", end.isoformat())
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        totals: dict[str, Decimal] = {}
        for row in rows:
            month = row["entry_month"]
            amount = Decimal(str(row["cogs_amount"]))
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
