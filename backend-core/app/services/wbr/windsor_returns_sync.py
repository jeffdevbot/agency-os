"""Windsor returns sync – FBA customer returns feed."""

from __future__ import annotations

import csv
import io
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
from supabase import Client

from .profiles import WBRNotFoundError, WBRValidationError

RETURNS_FIELDS = [
    "account_id",
    "date",
    "fba_fulfillment_customer_returns_data__asin",
    "fba_fulfillment_customer_returns_data__sku",
    "fba_fulfillment_customer_returns_data__quantity",
    "fba_fulfillment_customer_returns_data__return_date",
    "fba_fulfillment_customer_returns_data__product_name",
]

FIELD_ACCOUNT_ID = "account_id"
FIELD_ASIN = "fba_fulfillment_customer_returns_data__asin"
FIELD_QUANTITY = "fba_fulfillment_customer_returns_data__quantity"
FIELD_RETURN_DATE = "fba_fulfillment_customer_returns_data__return_date"
FIELD_DATE = "date"

DEFAULT_TIMEOUT_SECONDS = 360
MIN_TIMEOUT_SECONDS = 60
DEFAULT_RETURNS_LOOKBACK_DAYS = 28


@dataclass(frozen=True)
class AggregatedReturnFact:
    return_date: date
    child_asin: str
    return_units: int
    source_row_count: int
    source_payload: dict[str, Any]


def _clean_int(value: Any) -> int:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return 0
    try:
        return int(float(text))
    except (ValueError, TypeError):
        return 0


def _parse_return_date(row: dict[str, Any]) -> date | None:
    """Extract the return date, preferring the return-specific field."""
    for field in (FIELD_RETURN_DATE, FIELD_DATE):
        text = str(row.get(field) or "").strip()
        if not text:
            continue
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            continue
    return None


class WindsorReturnsSyncService:
    def __init__(self, db: Client) -> None:
        self.db = db
        self.api_key = os.getenv("WINDSOR_API_KEY", "").strip()
        self.returns_url = os.getenv(
            "WINDSOR_RETURNS_URL",
            "https://connectors.windsor.ai/amazon_sp",
        ).strip()
        configured_timeout = int(os.getenv("WBR_REQUEST_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
        self.timeout_seconds = max(configured_timeout, MIN_TIMEOUT_SECONDS)

    async def refresh_returns(
        self,
        *,
        profile_id: str,
        lookback_days: int = DEFAULT_RETURNS_LOOKBACK_DAYS,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        profile = self._get_profile(profile_id)
        account_id = self._require_windsor_account_id(profile)

        date_to = datetime.now(UTC).date()
        date_from = date_to - timedelta(days=max(lookback_days - 1, 0))

        run = self._create_sync_run(
            profile_id=profile_id,
            source_type="windsor_returns",
            job_type="daily_refresh",
            date_from=date_from,
            date_to=date_to,
            request_meta={"account_id": account_id, "lookback_days": lookback_days},
            user_id=user_id,
        )
        run_id = str(run["id"])
        raw_rows: list[dict[str, Any]] = []

        try:
            raw_rows = await self._fetch_returns(
                account_id=account_id,
                date_from=date_from,
                date_to=date_to,
            )

            facts = self._aggregate_returns(raw_rows, expected_account_id=account_id)

            self._replace_returns_window(
                profile_id=profile_id,
                sync_run_id=run_id,
                date_from=date_from,
                date_to=date_to,
                facts=facts,
            )

            finished = self._finalize_sync_run(
                run_id=run_id,
                status="success",
                rows_fetched=len(raw_rows),
                rows_loaded=len(facts),
                error_message=None,
            )
            return {
                "run": finished,
                "rows_fetched": len(raw_rows),
                "rows_loaded": len(facts),
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
            }
        except Exception as exc:
            self._finalize_sync_run(
                run_id=run_id,
                status="error",
                rows_fetched=len(raw_rows),
                rows_loaded=0,
                error_message=str(exc),
            )
            if isinstance(exc, (WBRValidationError, WBRNotFoundError)):
                raise
            raise WBRValidationError("Failed to sync Windsor returns data") from exc

    def _aggregate_returns(
        self,
        rows: list[dict[str, Any]],
        *,
        expected_account_id: str,
    ) -> list[AggregatedReturnFact]:
        by_key: dict[tuple[date, str], AggregatedReturnFact] = {}

        for row in rows:
            acct = str(row.get(FIELD_ACCOUNT_ID) or expected_account_id).strip()
            if acct != expected_account_id:
                continue

            asin = str(row.get(FIELD_ASIN) or "").strip().upper()
            if not asin:
                continue

            return_date = _parse_return_date(row)
            if return_date is None:
                continue

            quantity = _clean_int(row.get(FIELD_QUANTITY))

            key = (return_date, asin)
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = AggregatedReturnFact(
                    return_date=return_date,
                    child_asin=asin,
                    return_units=quantity,
                    source_row_count=1,
                    source_payload=row,
                )
            else:
                existing_rows = existing.source_payload.get("source_rows")
                merged_payload: dict[str, Any] = {
                    "source_rows": [
                        *(existing_rows if isinstance(existing_rows, list) else [existing.source_payload]),
                        row,
                    ]
                }
                by_key[key] = AggregatedReturnFact(
                    return_date=return_date,
                    child_asin=asin,
                    return_units=existing.return_units + quantity,
                    source_row_count=existing.source_row_count + 1,
                    source_payload=merged_payload,
                )

        return sorted(by_key.values(), key=lambda f: (f.return_date, f.child_asin))

    def _replace_returns_window(
        self,
        *,
        profile_id: str,
        sync_run_id: str,
        date_from: date,
        date_to: date,
        facts: list[AggregatedReturnFact],
    ) -> None:
        (
            self.db.table("wbr_returns_asin_daily")
            .delete()
            .eq("profile_id", profile_id)
            .gte("return_date", date_from.isoformat())
            .lte("return_date", date_to.isoformat())
            .execute()
        )

        if not facts:
            return

        payloads = [
            {
                "profile_id": profile_id,
                "sync_run_id": sync_run_id,
                "return_date": fact.return_date.isoformat(),
                "child_asin": fact.child_asin,
                "return_units": fact.return_units,
                "source_row_count": fact.source_row_count,
                "source_payload": fact.source_payload,
            }
            for fact in facts
        ]

        for start in range(0, len(payloads), 500):
            chunk = payloads[start : start + 500]
            response = self.db.table("wbr_returns_asin_daily").insert(chunk).execute()
            rows = response.data if isinstance(response.data, list) else []
            if len(rows) != len(chunk):
                raise WBRValidationError("Failed to store returns facts")

    async def _fetch_returns(
        self,
        *,
        account_id: str,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        if not self.api_key:
            raise WBRValidationError("WINDSOR_API_KEY is not configured")

        params = {
            "api_key": self.api_key,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "fields": ",".join(RETURNS_FIELDS),
            "select_accounts": account_id,
        }

        timeout = httpx.Timeout(timeout=self.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(self.returns_url, params=params)

        if response.status_code >= 400:
            body_preview = response.text.strip().replace("\n", " ")[:220]
            raise WBRValidationError(
                f"Windsor returns request failed: {response.status_code} :: {body_preview}"
            )

        body = response.text.strip()
        if not body:
            return []

        content_type = response.headers.get("content-type", "").lower()
        if "json" in content_type or body.startswith("[") or body.startswith("{"):
            try:
                payload = response.json()
            except Exception as exc:
                raise WBRValidationError(f"Failed to decode Windsor returns JSON: {exc}") from exc
            if isinstance(payload, list):
                return [row for row in payload if isinstance(row, dict)]
            if isinstance(payload, dict):
                for key in ("data", "results"):
                    value = payload.get(key)
                    if isinstance(value, list):
                        return [row for row in value if isinstance(row, dict)]
            raise WBRValidationError("Unexpected Windsor returns payload shape")

        return [dict(row) for row in csv.DictReader(io.StringIO(body))]

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

    def _require_windsor_account_id(self, profile: dict[str, Any]) -> str:
        account_id = str(profile.get("windsor_account_id") or "").strip()
        if not account_id:
            raise WBRValidationError("WBR profile is missing windsor_account_id")
        return account_id

    def _create_sync_run(
        self,
        *,
        profile_id: str,
        source_type: str,
        job_type: str,
        date_from: date,
        date_to: date,
        request_meta: dict[str, Any],
        user_id: str | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "profile_id": profile_id,
            "source_type": source_type,
            "job_type": job_type,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "status": "running",
            "request_meta": request_meta,
        }
        if user_id:
            payload["initiated_by"] = user_id
        response = self.db.table("wbr_sync_runs").insert(payload).execute()
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise WBRValidationError("Failed to create WBR sync run")
        return rows[0]

    def _finalize_sync_run(
        self,
        *,
        run_id: str,
        status: str,
        rows_fetched: int,
        rows_loaded: int,
        error_message: str | None,
    ) -> dict[str, Any]:
        response = (
            self.db.table("wbr_sync_runs")
            .update(
                {
                    "status": status,
                    "rows_fetched": rows_fetched,
                    "rows_loaded": rows_loaded,
                    "error_message": error_message,
                    "finished_at": datetime.now(UTC).isoformat(),
                }
            )
            .eq("id", run_id)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise WBRValidationError("Failed to finalize WBR sync run")
        return rows[0]
