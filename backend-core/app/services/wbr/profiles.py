"""Service layer for WBR profile and row management (v2 schema)."""

from __future__ import annotations

import re
from typing import Any

from postgrest.exceptions import APIError as PostgrestAPIError
from supabase import Client

VALID_WEEK_START_DAYS = {"sunday", "monday"}
VALID_STATUSES = {"draft", "active", "paused", "archived"}


# ------------------------------------------------------------------
# Errors
# ------------------------------------------------------------------


class WBRNotFoundError(Exception):
    """Resource not found."""


class WBRValidationError(Exception):
    """Business-rule or constraint violation."""


# ------------------------------------------------------------------
# Postgres error translation
# ------------------------------------------------------------------

_PG_CONSTRAINT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"uq_wbr_profiles_client_marketplace", re.IGNORECASE),
        "A profile already exists for this client and marketplace",
    ),
    (
        re.compile(r"uq_wbr_rows_profile_kind_label_active", re.IGNORECASE),
        "An active row with this label and kind already exists for this profile",
    ),
    (
        re.compile(r"wbr_rows_parent_row_id_fkey", re.IGNORECASE),
        "The specified parent_row_id does not exist",
    ),
    (
        re.compile(r"wbr_profiles_client_id_fkey", re.IGNORECASE),
        "The specified client_id does not exist",
    ),
    (
        re.compile(r"wbr_rows_check", re.IGNORECASE),
        "Invalid row_kind value",
    ),
    (
        re.compile(r"wbr_profiles_week_start_day_check", re.IGNORECASE),
        "week_start_day must be 'sunday' or 'monday'",
    ),
    (
        re.compile(r"wbr_profiles_status_check", re.IGNORECASE),
        "status must be one of: draft, active, paused, archived",
    ),
]


def _translate_pg_error(exc: PostgrestAPIError) -> WBRValidationError:
    """Turn a Postgrest APIError into a friendly WBRValidationError."""
    text = str(exc)
    for pattern, message in _PG_CONSTRAINT_PATTERNS:
        if pattern.search(text):
            return WBRValidationError(message)
    # DB trigger messages are already human-readable
    return WBRValidationError(text)


# ------------------------------------------------------------------
# Service
# ------------------------------------------------------------------


class WBRProfileService:
    def __init__(self, db: Client) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Profiles
    # ------------------------------------------------------------------

    def list_profiles(self, client_id: str) -> list[dict[str, Any]]:
        resp = (
            self.db.table("wbr_profiles")
            .select("*")
            .eq("client_id", client_id)
            .order("created_at")
            .execute()
        )
        return resp.data if isinstance(resp.data, list) else []

    def get_profile(self, profile_id: str) -> dict[str, Any]:
        resp = (
            self.db.table("wbr_profiles")
            .select("*")
            .eq("id", profile_id)
            .limit(1)
            .execute()
        )
        rows = resp.data if isinstance(resp.data, list) else []
        if not rows:
            raise WBRNotFoundError(f"Profile {profile_id} not found")
        return rows[0]

    def create_profile(self, payload: dict[str, Any], user_id: str | None = None) -> dict[str, Any]:
        _normalize_marketplace_code(payload)
        _validate_profile_fields(payload)

        # Check uniqueness on (client_id, marketplace_code)
        existing = (
            self.db.table("wbr_profiles")
            .select("id")
            .eq("client_id", payload["client_id"])
            .eq("marketplace_code", payload["marketplace_code"])
            .limit(1)
            .execute()
        )
        if existing.data:
            raise WBRValidationError(
                f"A profile already exists for client {payload['client_id']} / {payload['marketplace_code']}"
            )

        if user_id:
            payload["created_by"] = user_id
            payload["updated_by"] = user_id

        try:
            resp = self.db.table("wbr_profiles").insert(payload).execute()
        except PostgrestAPIError as exc:
            raise _translate_pg_error(exc) from exc
        rows = resp.data if isinstance(resp.data, list) else []
        if not rows:
            raise WBRValidationError("Failed to create profile")
        return rows[0]

    def update_profile(self, profile_id: str, updates: dict[str, Any], user_id: str | None = None) -> dict[str, Any]:
        self.get_profile(profile_id)

        _normalize_marketplace_code(updates)
        _validate_profile_fields(updates)

        if user_id:
            updates["updated_by"] = user_id

        try:
            resp = (
                self.db.table("wbr_profiles")
                .update(updates)
                .eq("id", profile_id)
                .execute()
            )
        except PostgrestAPIError as exc:
            raise _translate_pg_error(exc) from exc
        rows = resp.data if isinstance(resp.data, list) else []
        if not rows:
            raise WBRValidationError("Failed to update profile")
        return rows[0]

    # ------------------------------------------------------------------
    # Rows
    # ------------------------------------------------------------------

    def list_rows(self, profile_id: str, include_inactive: bool = False) -> list[dict[str, Any]]:
        self.get_profile(profile_id)

        q = (
            self.db.table("wbr_rows")
            .select("*")
            .eq("profile_id", profile_id)
            .order("sort_order")
        )
        if not include_inactive:
            q = q.eq("active", True)
        resp = q.execute()
        return resp.data if isinstance(resp.data, list) else []

    def create_row(self, profile_id: str, payload: dict[str, Any], user_id: str | None = None) -> dict[str, Any]:
        self.get_profile(profile_id)

        payload["profile_id"] = profile_id
        if user_id:
            payload["created_by"] = user_id
            payload["updated_by"] = user_id

        if payload.get("parent_row_id"):
            self._guard_inactive_parent(payload["parent_row_id"])

        try:
            resp = self.db.table("wbr_rows").insert(payload).execute()
        except PostgrestAPIError as exc:
            raise _translate_pg_error(exc) from exc
        rows = resp.data if isinstance(resp.data, list) else []
        if not rows:
            raise WBRValidationError("Failed to create row")
        return rows[0]

    def update_row(self, row_id: str, updates: dict[str, Any], user_id: str | None = None) -> dict[str, Any]:
        existing = self._get_row(row_id)

        if user_id:
            updates["updated_by"] = user_id

        # Don't allow changing profile_id
        updates.pop("profile_id", None)

        # If deactivating, guard against orphaning child rows
        if updates.get("active") is False and existing.get("active"):
            self._guard_parent_deactivation(existing)

        # Determine the effective parent after this update
        new_parent_id = updates.get("parent_row_id", existing.get("parent_row_id"))
        will_be_active = updates.get("active", existing.get("active"))
        if new_parent_id and will_be_active:
            self._guard_inactive_parent(new_parent_id)

        try:
            resp = (
                self.db.table("wbr_rows")
                .update(updates)
                .eq("id", row_id)
                .execute()
            )
        except PostgrestAPIError as exc:
            raise _translate_pg_error(exc) from exc
        rows = resp.data if isinstance(resp.data, list) else []
        if not rows:
            raise WBRValidationError("Failed to update row")
        return rows[0]

    def soft_delete_row(self, row_id: str, user_id: str | None = None) -> dict[str, Any]:
        existing = self._get_row(row_id)
        if not existing.get("active"):
            raise WBRValidationError(f"Row {row_id} is already inactive")

        self._guard_parent_deactivation(existing)

        updates: dict[str, Any] = {"active": False}
        if user_id:
            updates["updated_by"] = user_id

        try:
            resp = (
                self.db.table("wbr_rows")
                .update(updates)
                .eq("id", row_id)
                .execute()
            )
        except PostgrestAPIError as exc:
            raise _translate_pg_error(exc) from exc
        rows = resp.data if isinstance(resp.data, list) else []
        if not rows:
            raise WBRValidationError("Failed to deactivate row")
        return rows[0]

    def hard_delete_row(self, row_id: str) -> dict[str, Any]:
        existing = self._get_row(row_id)

        self._guard_parent_hard_delete(existing)
        self._guard_row_not_in_use(existing["id"])

        try:
            (
                self.db.table("wbr_rows")
                .delete()
                .eq("id", row_id)
                .execute()
            )
        except PostgrestAPIError as exc:
            raise _translate_pg_error(exc) from exc

        return existing

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_row(self, row_id: str) -> dict[str, Any]:
        resp = (
            self.db.table("wbr_rows")
            .select("*")
            .eq("id", row_id)
            .limit(1)
            .execute()
        )
        rows = resp.data if isinstance(resp.data, list) else []
        if not rows:
            raise WBRNotFoundError(f"Row {row_id} not found")
        return rows[0]

    def _guard_inactive_parent(self, parent_row_id: str) -> None:
        """Raise if the referenced parent row is inactive."""
        parent = self._get_row(parent_row_id)
        if not parent.get("active"):
            raise WBRValidationError(
                f"Cannot assign to inactive parent row {parent_row_id}"
            )

    def _guard_parent_deactivation(self, row: dict[str, Any]) -> None:
        """Raise if this is a parent row with active children."""
        if row.get("row_kind") != "parent":
            return
        children = (
            self.db.table("wbr_rows")
            .select("id")
            .eq("parent_row_id", row["id"])
            .eq("active", True)
            .limit(1)
            .execute()
        )
        if children.data:
            raise WBRValidationError(
                f"Cannot deactivate parent row {row['id']} while it has active child rows"
            )

    def _guard_parent_hard_delete(self, row: dict[str, Any]) -> None:
        """Raise if this parent row still has any children."""
        if row.get("row_kind") != "parent":
            return
        children = (
            self.db.table("wbr_rows")
            .select("id")
            .eq("parent_row_id", row["id"])
            .limit(1)
            .execute()
        )
        if children.data:
            raise WBRValidationError(
                f"Cannot permanently delete parent row {row['id']} while it still has child rows"
            )

    def _guard_row_not_in_use(self, row_id: str) -> None:
        asin_maps = (
            self.db.table("wbr_asin_row_map")
            .select("id")
            .eq("row_id", row_id)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        if asin_maps.data:
            raise WBRValidationError("Cannot permanently delete a row that still has active ASIN mappings")

        pacvue_maps = (
            self.db.table("wbr_pacvue_campaign_map")
            .select("id")
            .eq("row_id", row_id)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        if pacvue_maps.data:
            raise WBRValidationError("Cannot permanently delete a row that still has active campaign mappings")


# ------------------------------------------------------------------
# Validation helpers
# ------------------------------------------------------------------


def _normalize_marketplace_code(payload: dict[str, Any]) -> None:
    if "marketplace_code" in payload:
        payload["marketplace_code"] = payload["marketplace_code"].strip().upper()


def _validate_profile_fields(payload: dict[str, Any]) -> None:
    if "week_start_day" in payload and payload["week_start_day"] not in VALID_WEEK_START_DAYS:
        raise WBRValidationError(
            f"week_start_day must be one of: {', '.join(sorted(VALID_WEEK_START_DAYS))}"
        )
    if "status" in payload and payload["status"] not in VALID_STATUSES:
        raise WBRValidationError(
            f"status must be one of: {', '.join(sorted(VALID_STATUSES))}"
        )
