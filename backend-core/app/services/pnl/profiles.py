"""Monthly P&L profile management service."""

from __future__ import annotations

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
