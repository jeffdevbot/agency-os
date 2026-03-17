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


def _normalize_sku(value: Any) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        raise PNLValidationError("sku is required")
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
                "error_message, started_at, finished_at, created_at, updated_at, raw_meta"
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

    def list_sku_cogs(
        self,
        profile_id: str,
        start_month: str,
        end_month: str,
    ) -> list[dict[str, Any]]:
        self.get_profile(profile_id)
        if not re.fullmatch(r"\d{4}-\d{2}-01", start_month) or not re.fullmatch(r"\d{4}-\d{2}-01", end_month):
            raise PNLValidationError("start_month and end_month must be YYYY-MM-01")

        active_months_resp = (
            self.db.table("monthly_pnl_import_months")
            .select("id, entry_month")
            .eq("profile_id", profile_id)
            .eq("is_active", True)
            .gte("entry_month", start_month)
            .lte("entry_month", end_month)
            .order("entry_month")
            .execute()
        )
        active_month_rows = (
            active_months_resp.data if isinstance(active_months_resp.data, list) else []
        )
        active_month_ids = {
            str(row.get("id") or "").strip()
            for row in active_month_rows
            if row.get("id")
        }
        if not active_month_ids:
            return []

        sku_units_resp = (
            self.db.table("monthly_pnl_import_month_sku_units")
            .select("import_month_id, entry_month, sku, net_units")
            .eq("profile_id", profile_id)
            .gte("entry_month", start_month)
            .lte("entry_month", end_month)
            .order("entry_month")
            .execute()
        )
        sku_unit_rows = sku_units_resp.data if isinstance(sku_units_resp.data, list) else []

        cogs_resp = (
            self.db.table("monthly_pnl_sku_cogs")
            .select("sku, unit_cost")
            .eq("profile_id", profile_id)
            .execute()
        )
        cogs_rows = cogs_resp.data if isinstance(cogs_resp.data, list) else []
        unit_cost_by_sku: dict[str, str] = {}
        for row in cogs_rows:
            sku = str(row.get("sku") or "").strip()
            if not sku:
                continue
            unit_cost_by_sku[sku] = format(
                Decimal(str(row.get("unit_cost") or "0")).quantize(Decimal("0.0001")),
                "f",
            )

        sku_summary: dict[str, dict[str, Any]] = {}
        for row in sku_unit_rows:
            import_month_id = str(row.get("import_month_id") or "").strip()
            if import_month_id not in active_month_ids:
                continue

            sku = str(row.get("sku") or "").strip()
            month = str(row.get("entry_month") or "").strip()
            net_units = int(row.get("net_units") or 0)
            if not sku or not month or net_units == 0:
                continue

            summary = sku_summary.setdefault(
                sku,
                {
                    "sku": sku,
                    "unit_cost": unit_cost_by_sku.get(sku),
                    "months": {},
                    "total_units": 0,
                    "missing_cost": sku not in unit_cost_by_sku,
                },
            )
            summary["months"][month] = int(summary["months"].get(month, 0)) + net_units
            summary["total_units"] += net_units

        return sorted(
            sku_summary.values(),
            key=lambda row: (not row["missing_cost"], row["sku"].lower()),
        )

    def save_sku_cogs(
        self,
        profile_id: str,
        entries: list[dict[str, Any]],
    ) -> None:
        self.get_profile(profile_id)

        normalized: dict[str, Decimal | None] = {}
        for entry in entries:
            sku = _normalize_sku(entry.get("sku"))
            raw_unit_cost = entry.get("unit_cost")
            if raw_unit_cost in (None, ""):
                normalized[sku] = None
                continue
            try:
                amount = Decimal(str(raw_unit_cost)).quantize(Decimal("0.0001"))
            except (InvalidOperation, ValueError) as exc:
                raise PNLValidationError(f"Invalid unit_cost for {sku}") from exc
            if amount < 0:
                raise PNLValidationError(f"unit_cost cannot be negative for {sku}")
            normalized[sku] = amount

        existing_resp = (
            self.db.table("monthly_pnl_sku_cogs")
            .select("id, sku")
            .eq("profile_id", profile_id)
            .execute()
        )
        existing_rows = existing_resp.data if isinstance(existing_resp.data, list) else []
        existing_by_sku = {}
        for row in existing_rows:
            sku = str(row.get("sku") or "").strip()
            if sku:
                existing_by_sku[sku] = row

        for sku, unit_cost in normalized.items():
            existing = existing_by_sku.get(sku)
            if unit_cost is None:
                if existing:
                    (
                        self.db.table("monthly_pnl_sku_cogs")
                        .delete()
                        .eq("id", existing["id"])
                        .execute()
                    )
                continue

            payload = {
                "profile_id": profile_id,
                "sku": sku,
                "unit_cost": format(unit_cost, "f"),
            }
            if existing:
                (
                    self.db.table("monthly_pnl_sku_cogs")
                    .update({"unit_cost": payload["unit_cost"]})
                    .eq("id", existing["id"])
                    .execute()
                )
            else:
                self.db.table("monthly_pnl_sku_cogs").insert(payload).execute()
