from __future__ import annotations

import csv
import io
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

import httpx
from supabase import Client

from .profiles import WBRNotFoundError, WBRValidationError
from .windsor_inventory_sync import WindsorInventorySyncService
from .windsor_returns_sync import WindsorReturnsSyncService

WINDSOR_BUSINESS_FIELDS = [
    "account_id",
    "date",
    "sales_and_traffic_report_by_date__childasin",
    "sales_and_traffic_report_by_date__parentasin",
    "sales_and_traffic_report_by_date__salesbyasin_orderedproductsales_amount",
    "sales_and_traffic_report_by_date__salesbyasin_orderedproductsales_currencycode",
    "sales_and_traffic_report_by_date__salesbyasin_unitsordered",
    "sales_and_traffic_report_by_date__trafficbyasin_pageviews",
]

FIELD_ACCOUNT_ID = "account_id"
FIELD_DATE = "date"
FIELD_CHILD_ASIN = "sales_and_traffic_report_by_date__childasin"
FIELD_PARENT_ASIN = "sales_and_traffic_report_by_date__parentasin"
FIELD_SALES = "sales_and_traffic_report_by_date__salesbyasin_orderedproductsales_amount"
FIELD_CURRENCY = "sales_and_traffic_report_by_date__salesbyasin_orderedproductsales_currencycode"
FIELD_UNIT_SALES = "sales_and_traffic_report_by_date__salesbyasin_unitsordered"
FIELD_PAGE_VIEWS = "sales_and_traffic_report_by_date__trafficbyasin_pageviews"

DEFAULT_TIMEOUT_SECONDS = 360
MIN_TIMEOUT_SECONDS = 60
DEFAULT_CHUNK_DAYS = 7
DEFAULT_DAILY_LOOKBACK_DAYS = 14


@dataclass(frozen=True)
class AggregatedBusinessFact:
    report_date: date
    child_asin: str
    parent_asin: str | None
    currency_code: str
    page_views: int
    unit_sales: int
    sales: Decimal
    source_row_count: int
    source_payload: dict[str, Any]


def _clean_numeric_text(value: Any) -> str:
    return str(value or "").strip().replace(",", "")


def _parse_int(value: Any) -> int:
    text = _clean_numeric_text(value)
    if not text:
        return 0
    try:
        return int(Decimal(text))
    except (InvalidOperation, ValueError) as exc:
        raise WBRValidationError(f'Invalid Windsor integer value "{text}"') from exc


def _parse_decimal(value: Any) -> Decimal:
    text = _clean_numeric_text(value)
    if not text:
        return Decimal("0.00")
    try:
        return Decimal(text).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise WBRValidationError(f'Invalid Windsor decimal value "{text}"') from exc


def _chunk_date_range(date_from: date, date_to: date, chunk_days: int) -> list[tuple[date, date]]:
    if chunk_days <= 0:
        raise WBRValidationError("chunk_days must be > 0")
    if date_from > date_to:
        raise WBRValidationError("date_from must be <= date_to")

    chunks: list[tuple[date, date]] = []
    cursor = date_from
    while cursor <= date_to:
        chunk_end = min(cursor + timedelta(days=chunk_days - 1), date_to)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def _default_currency_code(account_id: str) -> str:
    suffix = account_id.rsplit("-", 1)[-1].upper() if "-" in account_id else ""
    if suffix == "CA":
        return "CAD"
    if suffix == "UK":
        return "GBP"
    if suffix == "MX":
        return "MXN"
    if suffix == "AU":
        return "AUD"
    if suffix == "JP":
        return "JPY"
    if suffix in {"DE", "FR", "IT", "ES", "NL", "SE", "PL", "BE"}:
        return "EUR"
    return "USD"


class WindsorBusinessSyncService:
    def __init__(self, db: Client) -> None:
        self.db = db
        self.api_key = os.getenv("WINDSOR_API_KEY", "").strip()
        self.seller_url = os.getenv(
            "WINDSOR_SELLER_URL",
            "https://connectors.windsor.ai/amazon_sp",
        ).strip()
        configured_timeout = int(os.getenv("WBR_REQUEST_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
        self.timeout_seconds = max(configured_timeout, MIN_TIMEOUT_SECONDS)
        self._inventory_sync = WindsorInventorySyncService(db)
        self._returns_sync = WindsorReturnsSyncService(db)

    def list_sync_runs(self, profile_id: str, *, source_type: str = "windsor_business") -> list[dict[str, Any]]:
        self._get_profile(profile_id)
        response = (
            self.db.table("wbr_sync_runs")
            .select("*")
            .eq("profile_id", profile_id)
            .eq("source_type", source_type)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        return response.data if isinstance(response.data, list) else []

    async def run_backfill(
        self,
        *,
        profile_id: str,
        date_from: date,
        date_to: date,
        chunk_days: int = DEFAULT_CHUNK_DAYS,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        today = datetime.now(UTC).date()
        if date_to > today:
            raise WBRValidationError("date_to must be less than or equal to today")

        profile = self._get_profile(profile_id)
        account_id = self._require_windsor_account_id(profile)

        chunks = _chunk_date_range(date_from, date_to, chunk_days)
        results = []
        for chunk_start, chunk_end in chunks:
            results.append(
                await self._run_chunk(
                    profile_id=profile_id,
                    account_id=account_id,
                    date_from=chunk_start,
                    date_to=chunk_end,
                    job_type="backfill",
                    user_id=user_id,
                )
            )

        return {
            "profile_id": profile_id,
            "job_type": "backfill",
            "chunk_days": chunk_days,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "chunks": results,
        }

    async def run_daily_refresh(
        self,
        *,
        profile_id: str,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        profile = self._get_profile(profile_id)
        account_id = self._require_windsor_account_id(profile)
        lookback_days = int(profile.get("daily_rewrite_days") or DEFAULT_DAILY_LOOKBACK_DAYS)
        date_to = datetime.now(UTC).date()
        date_from = date_to - timedelta(days=max(lookback_days - 1, 0))

        result = await self._run_chunk(
            profile_id=profile_id,
            account_id=account_id,
            date_from=date_from,
            date_to=date_to,
            job_type="daily_refresh",
            user_id=user_id,
        )

        # Section 3: inventory + returns (best-effort, don't block Section 1)
        section3 = await self._run_section3(profile_id=profile_id, user_id=user_id)

        return {
            "profile_id": profile_id,
            "job_type": "daily_refresh",
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "chunk": result,
            "section3": section3,
        }

    async def _run_section3(
        self,
        *,
        profile_id: str,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Run inventory + returns syncs. Errors are captured, not raised."""
        section3: dict[str, Any] = {"inventory": None, "returns": None}
        try:
            section3["inventory"] = await self._inventory_sync.refresh_inventory(
                profile_id=profile_id, user_id=user_id
            )
        except Exception as exc:  # noqa: BLE001
            section3["inventory"] = {"status": "error", "detail": str(exc)}
        try:
            section3["returns"] = await self._returns_sync.refresh_returns(
                profile_id=profile_id, user_id=user_id
            )
        except Exception as exc:  # noqa: BLE001
            section3["returns"] = {"status": "error", "detail": str(exc)}
        return section3

    async def _run_chunk(
        self,
        *,
        profile_id: str,
        account_id: str,
        date_from: date,
        date_to: date,
        job_type: str,
        user_id: str | None,
    ) -> dict[str, Any]:
        run = self._create_sync_run(
            profile_id=profile_id,
            source_type="windsor_business",
            job_type=job_type,
            date_from=date_from,
            date_to=date_to,
            request_meta={
                "account_id": account_id,
                "fields": WINDSOR_BUSINESS_FIELDS,
            },
            user_id=user_id,
        )
        run_id = str(run["id"])
        raw_rows: list[dict[str, Any]] = []

        try:
            raw_rows = await self._fetch_rows(account_id=account_id, date_from=date_from, date_to=date_to)
            facts = self._aggregate_rows(raw_rows, expected_account_id=account_id)
            self._replace_fact_window(
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
            }
        except WBRValidationError as exc:
            self._finalize_sync_run(
                run_id=run_id,
                status="error",
                rows_fetched=len(raw_rows),
                rows_loaded=0,
                error_message=str(exc),
            )
            raise
        except Exception as exc:  # noqa: BLE001
            self._finalize_sync_run(
                run_id=run_id,
                status="error",
                rows_fetched=len(raw_rows),
                rows_loaded=0,
                error_message=str(exc),
            )
            raise WBRValidationError("Failed to sync Windsor business data") from exc

    async def _fetch_rows(self, *, account_id: str, date_from: date, date_to: date) -> list[dict[str, Any]]:
        if not self.api_key:
            raise WBRValidationError("WINDSOR_API_KEY is not configured")
        if not self.seller_url:
            raise WBRValidationError("WINDSOR_SELLER_URL is not configured")

        params = {
            "api_key": self.api_key,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "fields": ",".join(WINDSOR_BUSINESS_FIELDS),
            "select_accounts": account_id,
        }

        timeout = httpx.Timeout(timeout=self.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(self.seller_url, params=params)

        if response.status_code >= 400:
            body_preview = response.text.strip().replace("\n", " ")[:220]
            raise WBRValidationError(
                f"Windsor business request failed: {response.status_code} :: {body_preview}"
            )

        body = response.text.strip()
        if not body:
            return []

        content_type = response.headers.get("content-type", "").lower()
        if "json" in content_type or body.startswith("[") or body.startswith("{"):
            try:
                payload = response.json()
            except Exception as exc:  # noqa: BLE001
                raise WBRValidationError(f"Failed to decode Windsor business JSON: {exc}") from exc
            if isinstance(payload, list):
                return [row for row in payload if isinstance(row, dict)]
            if isinstance(payload, dict):
                for key in ("data", "results"):
                    value = payload.get(key)
                    if isinstance(value, list):
                        return [row for row in value if isinstance(row, dict)]
            raise WBRValidationError("Unexpected Windsor business payload shape")

        return [dict(row) for row in csv.DictReader(io.StringIO(body))]

    def _aggregate_rows(
        self,
        rows: list[dict[str, Any]],
        *,
        expected_account_id: str,
    ) -> list[AggregatedBusinessFact]:
        by_key: dict[tuple[date, str], AggregatedBusinessFact] = {}

        for row in rows:
            account_id = str(row.get(FIELD_ACCOUNT_ID) or expected_account_id).strip()
            if account_id != expected_account_id:
                continue

            date_text = str(row.get(FIELD_DATE) or "").strip()
            child_asin = str(row.get(FIELD_CHILD_ASIN) or "").strip().upper()
            if not date_text or not child_asin:
                continue

            try:
                report_date = date.fromisoformat(date_text[:10])
            except ValueError as exc:
                raise WBRValidationError(f'Invalid Windsor business date "{date_text}"') from exc

            currency_code = (
                str(row.get(FIELD_CURRENCY) or "").strip().upper()
                or _default_currency_code(account_id)
            )
            fact = AggregatedBusinessFact(
                report_date=report_date,
                child_asin=child_asin,
                parent_asin=str(row.get(FIELD_PARENT_ASIN) or "").strip() or None,
                currency_code=currency_code,
                page_views=_parse_int(row.get(FIELD_PAGE_VIEWS)),
                unit_sales=_parse_int(row.get(FIELD_UNIT_SALES)),
                sales=_parse_decimal(row.get(FIELD_SALES)),
                source_row_count=1,
                source_payload=row,
            )

            key = (report_date, child_asin)
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = fact
                continue

            if existing.currency_code != fact.currency_code:
                raise WBRValidationError(
                    f"Multiple currency codes found for {child_asin} on {report_date.isoformat()}"
                )

            existing_rows = existing.source_payload.get("source_rows")
            merged_payload: dict[str, Any] = {
                "source_rows": [
                    *(existing_rows if isinstance(existing_rows, list) else [existing.source_payload]),
                    row,
                ]
            }
            by_key[key] = AggregatedBusinessFact(
                report_date=existing.report_date,
                child_asin=existing.child_asin,
                parent_asin=existing.parent_asin or fact.parent_asin,
                currency_code=existing.currency_code,
                page_views=existing.page_views + fact.page_views,
                unit_sales=existing.unit_sales + fact.unit_sales,
                sales=(existing.sales + fact.sales).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                source_row_count=existing.source_row_count + 1,
                source_payload=merged_payload,
            )

        return sorted(by_key.values(), key=lambda item: (item.report_date, item.child_asin))

    def _replace_fact_window(
        self,
        *,
        profile_id: str,
        sync_run_id: str,
        date_from: date,
        date_to: date,
        facts: list[AggregatedBusinessFact],
    ) -> None:
        (
            self.db.table("wbr_business_asin_daily")
            .delete()
            .eq("profile_id", profile_id)
            .gte("report_date", date_from.isoformat())
            .lte("report_date", date_to.isoformat())
            .execute()
        )

        if not facts:
            return

        payloads = [
            {
                "profile_id": profile_id,
                "sync_run_id": sync_run_id,
                "report_date": fact.report_date.isoformat(),
                "child_asin": fact.child_asin,
                "parent_asin": fact.parent_asin,
                "currency_code": fact.currency_code,
                "page_views": fact.page_views,
                "unit_sales": fact.unit_sales,
                "sales": str(fact.sales),
                "source_row_count": fact.source_row_count,
                "source_payload": fact.source_payload,
            }
            for fact in facts
        ]

        for start in range(0, len(payloads), 500):
            chunk = payloads[start : start + 500]
            response = self.db.table("wbr_business_asin_daily").insert(chunk).execute()
            rows = response.data if isinstance(response.data, list) else []
            if len(rows) != len(chunk):
                raise WBRValidationError("Failed to store Windsor business facts")

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
