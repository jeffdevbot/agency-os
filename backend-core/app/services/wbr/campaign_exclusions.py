"""Campaign exclusion service for WBR managed-subset setups."""

from __future__ import annotations

import csv
import io
from typing import Any

from supabase import Client

from .profiles import WBRNotFoundError, WBRValidationError

CSV_IMPORT_ALLOWED_EXTENSIONS = (".csv",)
CSV_IMPORT_COLUMN_ALIASES = {
    "campaign_name": {"campaign_name", "campaign name", "name"},
    "scope_status": {"scope_status", "scope status", "status"},
    "exclusion_reason": {"exclusion_reason", "exclusion reason", "reason", "notes"},
}
_BATCH_SIZE = 500
_EXCLUDE_STATUSES = {"exclude", "excluded", "ignore", "ignored", "out_of_scope", "out of scope"}
_CLEAR_STATUSES = {"", "include", "included", "clear", "cleared"}


def _decode_csv_text(file_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise WBRValidationError("Unable to decode campaign exclusion CSV")


def _canonicalize_column_name(value: str) -> str:
    return value.strip().lower().replace("_", " ")


def _resolve_column(fieldnames: list[str], aliases: set[str]) -> str | None:
    canonical_to_original = {_canonicalize_column_name(name): name for name in fieldnames if name}
    for alias in aliases:
        original = canonical_to_original.get(_canonicalize_column_name(alias))
        if original:
            return original
    return None


class CampaignExclusionService:
    def __init__(self, db: Client) -> None:
        self.db = db

    def list_exclusions(self, profile_id: str) -> list[dict[str, Any]]:
        self._get_profile(profile_id)
        response = (
            self.db.table("wbr_campaign_exclusions")
            .select("id, profile_id, campaign_name, exclusion_source, exclusion_reason, active, created_at, updated_at")
            .eq("profile_id", profile_id)
            .eq("active", True)
            .order("campaign_name")
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        return rows

    def export_exclusions_csv(self, profile_id: str) -> str:
        items = self.list_exclusions(profile_id)
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=["campaign_name", "scope_status", "exclusion_reason"],
            lineterminator="\n",
        )
        writer.writeheader()
        for item in items:
            writer.writerow(
                {
                    "campaign_name": item.get("campaign_name") or "",
                    "scope_status": "excluded",
                    "exclusion_reason": item.get("exclusion_reason") or "",
                }
            )
        return output.getvalue()

    def import_exclusions_csv(
        self,
        *,
        profile_id: str,
        file_name: str,
        file_bytes: bytes,
        user_id: str | None = None,
    ) -> dict[str, int]:
        self._validate_csv_file_name(file_name)
        self._get_profile(profile_id)

        text = _decode_csv_text(file_bytes)
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise WBRValidationError("Campaign exclusion CSV must include a header row")

        fieldnames = [name for name in reader.fieldnames if name]
        campaign_name_column = _resolve_column(fieldnames, CSV_IMPORT_COLUMN_ALIASES["campaign_name"])
        scope_status_column = _resolve_column(fieldnames, CSV_IMPORT_COLUMN_ALIASES["scope_status"])
        reason_column = _resolve_column(fieldnames, CSV_IMPORT_COLUMN_ALIASES["exclusion_reason"])

        if not campaign_name_column:
            raise WBRValidationError("Campaign exclusion CSV must include a campaign_name column")

        active_exclusions = self._list_active_exclusions_by_campaign(profile_id)
        seen_campaigns: set[str] = set()
        to_insert: list[dict[str, Any]] = []
        exclusion_ids_to_deactivate: list[str] = []
        rows_excluded = 0
        rows_cleared = 0
        rows_unchanged = 0

        for index, row in enumerate(reader, start=2):
            campaign_name = str(row.get(campaign_name_column) or "").strip()
            if not campaign_name:
                raise WBRValidationError(f"Campaign exclusion CSV row {index} is missing campaign_name")
            if campaign_name in seen_campaigns:
                raise WBRValidationError(f'Campaign exclusion CSV contains duplicate campaign_name "{campaign_name}"')
            seen_campaigns.add(campaign_name)

            scope_status = str(row.get(scope_status_column) or "").strip().lower() if scope_status_column else "excluded"
            if scope_status not in _EXCLUDE_STATUSES | _CLEAR_STATUSES:
                raise WBRValidationError(
                    f'Campaign exclusion CSV row {index} has unsupported scope_status "{scope_status}"'
                )
            exclusion_reason = str(row.get(reason_column) or "").strip() if reason_column else ""
            current = active_exclusions.get(campaign_name)

            if scope_status in _EXCLUDE_STATUSES:
                if current:
                    rows_unchanged += 1
                    continue
                payload: dict[str, Any] = {
                    "profile_id": profile_id,
                    "campaign_name": campaign_name,
                    "exclusion_source": "imported",
                    "exclusion_reason": exclusion_reason or None,
                    "active": True,
                }
                if user_id:
                    payload["created_by"] = user_id
                    payload["updated_by"] = user_id
                to_insert.append(payload)
                rows_excluded += 1
                continue

            if current and current.get("id"):
                exclusion_ids_to_deactivate.append(str(current["id"]))
                rows_cleared += 1
            else:
                rows_unchanged += 1

        self._deactivate_exclusion_ids(exclusion_ids_to_deactivate, user_id=user_id)
        self._insert_exclusion_payloads(to_insert)

        return {
            "rows_read": len(seen_campaigns),
            "rows_excluded": rows_excluded,
            "rows_cleared": rows_cleared,
            "rows_unchanged": rows_unchanged,
        }

    def _get_profile(self, profile_id: str) -> dict[str, Any]:
        response = (
            self.db.table("wbr_profiles")
            .select("id")
            .eq("id", profile_id)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise WBRNotFoundError(f"Profile {profile_id} not found")
        return rows[0]

    def _validate_csv_file_name(self, file_name: str) -> None:
        lower_name = (file_name or "").lower()
        if not lower_name.endswith(CSV_IMPORT_ALLOWED_EXTENSIONS):
            raise WBRValidationError("Campaign exclusion import supports .csv files only")

    def _list_active_exclusions_by_campaign(self, profile_id: str) -> dict[str, dict[str, Any]]:
        response = (
            self.db.table("wbr_campaign_exclusions")
            .select("id, campaign_name")
            .eq("profile_id", profile_id)
            .eq("active", True)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        return {
            str(row["campaign_name"]): row
            for row in rows
            if isinstance(row, dict) and row.get("campaign_name")
        }

    def _deactivate_exclusion_ids(self, exclusion_ids: list[str], *, user_id: str | None = None) -> None:
        if not exclusion_ids:
            return
        updates: dict[str, Any] = {"active": False}
        if user_id:
            updates["updated_by"] = user_id
        for start in range(0, len(exclusion_ids), _BATCH_SIZE):
            chunk = exclusion_ids[start:start + _BATCH_SIZE]
            (
                self.db.table("wbr_campaign_exclusions")
                .update(updates)
                .in_("id", chunk)
                .execute()
            )

    def _insert_exclusion_payloads(self, payloads: list[dict[str, Any]]) -> None:
        if not payloads:
            return
        for start in range(0, len(payloads), _BATCH_SIZE):
            chunk = payloads[start:start + _BATCH_SIZE]
            response = self.db.table("wbr_campaign_exclusions").insert(chunk).execute()
            rows = response.data if isinstance(response.data, list) else []
            if len(rows) != len(chunk):
                raise WBRValidationError("Failed to save campaign exclusions")
