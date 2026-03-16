"""Monthly P&L profile management service."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
from typing import Any

from postgrest.exceptions import APIError as PostgrestAPIError
from supabase import Client


class PNLNotFoundError(Exception):
    pass


class PNLValidationError(Exception):
    pass


class PNLDuplicateFileError(PNLValidationError):
    """Raised when a file with the same SHA-256 has already been imported."""

    pass


_PG_CONSTRAINT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"uq_monthly_pnl_profiles_client_marketplace", re.IGNORECASE),
        "A P&L profile already exists for this client and marketplace",
    ),
    (
        re.compile(r"monthly_pnl_profiles_client_id_fkey", re.IGNORECASE),
        "The specified client_id does not exist",
    ),
]


def _translate_pg_error(exc: PostgrestAPIError) -> PNLValidationError:
    """Turn a PostgREST APIError into a friendly PNLValidationError."""
    text = str(exc)
    for pattern, message in _PG_CONSTRAINT_PATTERNS:
        if pattern.search(text):
            return PNLValidationError(message)
    return PNLValidationError(text)


def _normalize_marketplace_code(code: str) -> str:
    cleaned = (code or "").strip().upper()
    if not cleaned:
        raise PNLValidationError("marketplace_code is required")
    return cleaned


class PNLProfileService:
    def __init__(self, db: Client) -> None:
        self.db = db

    def get_profile(self, profile_id: str) -> dict[str, Any]:
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

    def list_profiles(self, client_id: str) -> list[dict[str, Any]]:
        response = (
            self.db.table("monthly_pnl_profiles")
            .select("*")
            .eq("client_id", client_id)
            .order("created_at", desc=True)
            .execute()
        )
        return response.data if isinstance(response.data, list) else []

    def create_profile(
        self,
        *,
        client_id: str,
        marketplace_code: str,
        currency_code: str = "USD",
        notes: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        mc = _normalize_marketplace_code(marketplace_code)
        payload: dict[str, Any] = {
            "client_id": client_id,
            "marketplace_code": mc,
            "currency_code": currency_code,
        }
        if notes:
            payload["notes"] = notes
        if user_id:
            payload["created_by"] = user_id
            payload["updated_by"] = user_id
        try:
            response = self.db.table("monthly_pnl_profiles").insert(payload).execute()
        except PostgrestAPIError as exc:
            raise _translate_pg_error(exc) from exc
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise PNLValidationError("Failed to create P&L profile")
        return rows[0]

    def list_imports(self, profile_id: str) -> list[dict[str, Any]]:
        self.get_profile(profile_id)
        response = (
            self.db.table("monthly_pnl_imports")
            .select(
                "id, profile_id, source_type, source_filename, import_status, row_count, "
                "error_message, started_at, finished_at, created_at, updated_at"
            )
            .eq("profile_id", profile_id)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        return response.data if isinstance(response.data, list) else []

    def list_import_months(self, profile_id: str) -> list[dict[str, Any]]:
        self.get_profile(profile_id)
        response = (
            self.db.table("monthly_pnl_import_months")
            .select("*")
            .eq("profile_id", profile_id)
            .order("entry_month", desc=True)
            .limit(100)
            .execute()
        )
        return response.data if isinstance(response.data, list) else []

    def get_import_summary(self, profile_id: str, import_id: str) -> dict[str, Any]:
        self.get_profile(profile_id)
        imp_resp = (
            self.db.table("monthly_pnl_imports")
            .select("*")
            .eq("id", import_id)
            .eq("profile_id", profile_id)
            .limit(1)
            .execute()
        )
        imp_rows = imp_resp.data if isinstance(imp_resp.data, list) else []
        if not imp_rows:
            raise PNLNotFoundError(f"Import {import_id} not found")

        months_resp = (
            self.db.table("monthly_pnl_import_months")
            .select("*")
            .eq("import_id", import_id)
            .order("entry_month")
            .execute()
        )
        months = months_resp.data if isinstance(months_resp.data, list) else []

        return {"import": imp_rows[0], "months": months}

    def list_cogs_month_totals(self, profile_id: str) -> list[dict[str, Any]]:
        self.get_profile(profile_id)

        active_months_resp = (
            self.db.table("monthly_pnl_import_months")
            .select("entry_month")
            .eq("profile_id", profile_id)
            .eq("is_active", True)
            .order("entry_month")
            .limit(36)
            .execute()
        )
        active_month_rows = (
            active_months_resp.data if isinstance(active_months_resp.data, list) else []
        )
        active_months = {
            str(row.get("entry_month") or "").strip()
            for row in active_month_rows
            if row.get("entry_month")
        }

        cogs_resp = (
            self.db.table("monthly_pnl_cogs_monthly")
            .select("entry_month, amount")
            .eq("profile_id", profile_id)
            .order("entry_month")
            .execute()
        )
        cogs_rows = cogs_resp.data if isinstance(cogs_resp.data, list) else []
        totals_by_month: dict[str, Decimal] = {}
        for row in cogs_rows:
            entry_month = str(row.get("entry_month") or "").strip()
            if not entry_month:
                continue
            totals_by_month[entry_month] = totals_by_month.get(entry_month, Decimal("0")) + Decimal(
                str(row.get("amount") or "0")
            )

        all_months = sorted(active_months | set(totals_by_month.keys()))
        return [
            {
                "entry_month": month,
                "amount": format(totals_by_month.get(month, Decimal("0")).quantize(Decimal("0.01")), "f"),
                "has_data": month in active_months,
            }
            for month in all_months
        ]

    def save_cogs_month_totals(
        self,
        profile_id: str,
        entries: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        self.get_profile(profile_id)

        normalized: dict[str, Decimal | None] = {}
        for entry in entries:
            raw_month = str(entry.get("entry_month") or "").strip()
            if not re.fullmatch(r"\d{4}-\d{2}-01", raw_month):
                raise PNLValidationError("entry_month must be the first day of a month (YYYY-MM-01)")
            raw_amount = entry.get("amount")
            if raw_amount in (None, ""):
                normalized[raw_month] = None
                continue
            try:
                normalized[raw_month] = Decimal(str(raw_amount)).quantize(Decimal("0.01"))
            except (InvalidOperation, ValueError) as exc:
                raise PNLValidationError(f"Invalid COGS amount for {raw_month}") from exc

        existing_resp = (
            self.db.table("monthly_pnl_cogs_monthly")
            .select("id, entry_month, sku, asin, amount")
            .eq("profile_id", profile_id)
            .execute()
        )
        existing_rows = existing_resp.data if isinstance(existing_resp.data, list) else []
        existing_month_totals = {
            str(row.get("entry_month") or "").strip(): row
            for row in existing_rows
            if not row.get("sku") and not row.get("asin") and row.get("entry_month")
        }

        for entry_month, amount in normalized.items():
            existing = existing_month_totals.get(entry_month)
            if amount is None:
                if existing:
                    (
                        self.db.table("monthly_pnl_cogs_monthly")
                        .delete()
                        .eq("id", existing["id"])
                        .execute()
                    )
                continue

            payload = {
                "profile_id": profile_id,
                "entry_month": entry_month,
                "amount": format(amount, "f"),
            }
            if existing:
                (
                    self.db.table("monthly_pnl_cogs_monthly")
                    .update({"amount": payload["amount"]})
                    .eq("id", existing["id"])
                    .execute()
                )
            else:
                self.db.table("monthly_pnl_cogs_monthly").insert(payload).execute()

        return self.list_cogs_month_totals(profile_id)
