"""Read-only SP-API listings preview for WBR onboarding."""

from __future__ import annotations

from dataclasses import asdict, fields
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Protocol

from supabase import Client

from ..reports.sp_api_reports_client import SpApiReportsClient
from .listing_imports import (
    LISTING_HEADER_ALIASES,
    ParsedListingRecord,
    _canonicalize_header,
    _parse_dict_rows,
)
from .profiles import WBRNotFoundError, WBRValidationError
from .spapi_business_sync import MARKETPLACE_IDS_BY_CODE

REPORT_TYPE_MERCHANT_LISTINGS = "GET_MERCHANT_LISTINGS_ALL_DATA"


class ListingsReportsClient(Protocol):
    async def fetch_report_rows(
        self,
        report_type: str,
        *,
        marketplace_ids: list[str],
        data_start_time: datetime,
        data_end_time: datetime,
        report_options: dict[str, str] | None = None,
        format: str = "tsv",
    ) -> list[dict[str, Any]]: ...


ClientFactory = Callable[[str, str], ListingsReportsClient]


def _default_client_factory(refresh_token: str, region_code: str) -> SpApiReportsClient:
    return SpApiReportsClient(refresh_token, region_code)


def _mapped_source_columns(raw_row: dict[str, Any]) -> set[str]:
    record_fields = {
        field.name
        for field in fields(ParsedListingRecord)
        if field.name != "raw_payload"
    }
    mapped_aliases = {
        alias
        for field_name, aliases in LISTING_HEADER_ALIASES.items()
        if field_name in record_fields
        for alias in aliases
    }
    return {
        key
        for key in raw_row
        if _canonicalize_header(key) in mapped_aliases
    }


class SpApiListingsFetchService:
    def __init__(
        self,
        db: Client,
        *,
        client_factory: ClientFactory = _default_client_factory,
    ) -> None:
        self.db = db
        self._client_factory = client_factory

    async def fetch_listings(self, *, profile_id: str) -> dict[str, Any]:
        """Fetch GET_MERCHANT_LISTINGS_ALL_DATA and return a normalized preview."""
        profile = self._get_profile(profile_id)
        client_id = str(profile.get("client_id") or "").strip()
        marketplace_code = str(profile.get("marketplace_code") or "").strip().upper()
        marketplace_id = MARKETPLACE_IDS_BY_CODE.get(marketplace_code)
        if not marketplace_id:
            raise WBRValidationError(
                f"Marketplace {marketplace_code or '<blank>'} is not mapped for SP-API listings"
            )

        connection = self._get_spapi_connection(client_id)
        refresh_token = str(connection.get("refresh_token") or "").strip()
        region_code = str(connection.get("region_code") or "").strip()
        if not refresh_token:
            raise WBRValidationError("Stored SP-API connection has no refresh token")
        if not region_code:
            raise WBRValidationError("Stored SP-API connection has no region_code")

        now = datetime.now(UTC)
        client = self._client_factory(refresh_token, region_code)
        raw_rows = await client.fetch_report_rows(
            REPORT_TYPE_MERCHANT_LISTINGS,
            marketplace_ids=[marketplace_id],
            data_start_time=now - timedelta(days=1),
            data_end_time=now,
            format="tsv",
        )
        parsed = _parse_dict_rows(raw_rows, source_type="amazon_spapi", sheet_title=None)

        mapped_columns = _mapped_source_columns(raw_rows[0]) if raw_rows else set()
        unmapped_columns = set(raw_rows[0].keys()) - mapped_columns if raw_rows else set()

        return {
            "profile_id": profile_id,
            "marketplace_code": marketplace_code,
            "marketplace_id": marketplace_id,
            "rows_fetched": len(raw_rows),
            "rows_parsed": len(parsed.records),
            "duplicate_rows_merged": parsed.duplicate_rows_merged,
            "unmapped_columns": sorted(unmapped_columns),
            "sample_records": [
                asdict(record)
                for record in parsed.records[:5]
            ],
        }

    def _get_profile(self, profile_id: str) -> dict[str, Any]:
        response = (
            self.db.table("wbr_profiles")
            .select("*")
            .eq("id", profile_id)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise WBRNotFoundError(f"Profile {profile_id} not found")
        return rows[0]

    def _get_spapi_connection(self, client_id: str) -> dict[str, Any]:
        response = (
            self.db.table("report_api_connections")
            .select("*")
            .eq("client_id", client_id)
            .eq("provider", "amazon_spapi")
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise WBRValidationError(
                "No Amazon Seller API connection found for this client"
            )
        return rows[0]
