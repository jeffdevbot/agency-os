"""Direct SP-API business compare sync.

This service intentionally writes to ``wbr_business_asin_daily__compare`` only.
It is for A/B comparison against the Windsor-loaded
``wbr_business_asin_daily`` table and must not be wired into nightly sync yet.

SP-API field mapping for ``GET_SALES_AND_TRAFFIC_REPORT``:

| SP-API source field | Compare table column |
| --- | --- |
| requested report day | report_date |
| salesAndTrafficByAsin[].childAsin | child_asin |
| salesAndTrafficByAsin[].parentAsin | parent_asin |
| salesAndTrafficByAsin[].salesByAsin.orderedProductSales.currencyCode, or marketplace default | currency_code |
| salesAndTrafficByAsin[].salesByAsin.unitsOrdered | unit_sales |
| salesAndTrafficByAsin[].salesByAsin.orderedProductSales.amount | sales |
| salesAndTrafficByAsin[].trafficByAsin.pageViews, or browserPageViews + mobileAppPageViews | page_views |
| one SP-API ASIN object | source_row_count = 1, source_payload |

Amazon's Sales and Traffic report exposes date aggregates and ASIN aggregates
as separate arrays. For per-day-per-child-ASIN rows, we request one
``GET_SALES_AND_TRAFFIC_REPORT`` per day using ``asinGranularity=CHILD`` and
``dateGranularity=DAY``.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time as datetime_time, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Protocol

from supabase import Client

from ..reports.sp_api_reports_client import SpApiReportsClient
from .profiles import WBRNotFoundError, WBRValidationError

COMPARE_TABLE = "wbr_business_asin_daily__compare"
REPORT_TYPE_SALES_AND_TRAFFIC = "GET_SALES_AND_TRAFFIC_REPORT"
DEFAULT_CREATE_REPORT_SPACING_S = 60.0
DEFAULT_INSERT_CHUNK_SIZE = 1000

MARKETPLACE_IDS_BY_CODE = {
    "CA": "A2EUQ1WTGCTBG2",
    "US": "ATVPDKIKX0DER",
    "MX": "A1AM78C64UM0Y8",
    "UK": "A1F83G8C2ARO7P",
    "GB": "A1F83G8C2ARO7P",
    "AU": "A39IBJ37TRP1C6",
    "IE": "A28R8C7NBKEWEA",
    "ES": "A1RKKUPIHCS9HS",
    "FR": "A13V1IB3VIYZZH",
    "BE": "AMEN7PMS3EDWL",
    "NL": "A1805IZSGTT6HS",
    "DE": "A1PA6795UKMFR9",
    "IT": "APJ6JRA9NG5V4",
    "SE": "A2NODRKZP88ZB9",
    "PL": "A1C3SOZRARQ6R3",
}

DEFAULT_CURRENCY_BY_MARKETPLACE_CODE = {
    "CA": "CAD",
    "US": "USD",
    "MX": "MXN",
    "UK": "GBP",
    "GB": "GBP",
    "AU": "AUD",
    "IE": "EUR",
    "ES": "EUR",
    "FR": "EUR",
    "BE": "EUR",
    "NL": "EUR",
    "DE": "EUR",
    "IT": "EUR",
    "SE": "SEK",
    "PL": "PLN",
}


class SalesAndTrafficClient(Protocol):
    async def fetch_report_rows(
        self,
        report_type: str,
        *,
        marketplace_ids: list[str],
        data_start_time: datetime,
        data_end_time: datetime,
        report_options: dict[str, str] | None = None,
        format: str = "json",
    ) -> list[dict[str, Any]]:
        ...


ClientFactory = Callable[[str, str], SalesAndTrafficClient]
SleepFn = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class SpApiBusinessFact:
    report_date: date
    child_asin: str
    parent_asin: str | None
    currency_code: str
    page_views: int
    unit_sales: int
    sales: Decimal
    source_row_count: int
    source_payload: dict[str, Any]


def _default_client_factory(refresh_token: str, region_code: str) -> SalesAndTrafficClient:
    return SpApiReportsClient(refresh_token, region_code)


def _day_start(value: date) -> datetime:
    return datetime.combine(value, datetime_time.min, tzinfo=UTC)


def _day_end_inclusive(value: date) -> datetime:
    # GET_SALES_AND_TRAFFIC_REPORT truncates dataStartTime/dataEndTime to dates and
    # treats both endpoints as INCLUSIVE at date granularity. Passing next-day-
    # midnight as data_end_time (the natural "exclusive end" pattern) makes Amazon
    # return TWO days of data — both `salesAndTrafficByDate` entries and an
    # aggregated `salesAndTrafficByAsin` rolled up across the pair. The day-by-day
    # loop below relies on each call returning a single day; double-counting
    # surfaces immediately on the per-ASIN totals. Anchoring data_end_time at
    # 23:59:59.999999 of the same UTC date keeps Amazon scoped to one date.
    return datetime.combine(value, datetime_time.max, tzinfo=UTC)


def _date_range(date_from: date, date_to: date) -> list[date]:
    if date_from > date_to:
        raise WBRValidationError("date_from must be <= date_to")
    days = []
    cursor = date_from
    while cursor <= date_to:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _parse_decimal(value: Any) -> Decimal:
    text = str(value if value is not None else "").strip().replace(",", "")
    if not text:
        return Decimal("0.00")
    try:
        return Decimal(text).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise WBRValidationError(f'Invalid SP-API decimal value "{text}"') from exc


def _parse_int(value: Any) -> int:
    text = str(value if value is not None else "").strip().replace(",", "")
    if not text:
        return 0
    try:
        return int(Decimal(text))
    except (InvalidOperation, ValueError) as exc:
        raise WBRValidationError(f'Invalid SP-API integer value "{text}"') from exc


def _money_amount(value: dict[str, Any]) -> Any:
    return value.get("amount", value.get("Amount"))


def _money_currency(value: dict[str, Any]) -> str:
    return str(
        value.get("currencyCode")
        or value.get("CurrencyCode")
        or value.get("currency_code")
        or ""
    ).strip().upper()


def _page_views(traffic_by_asin: dict[str, Any]) -> int:
    if traffic_by_asin.get("pageViews") is not None:
        return _parse_int(traffic_by_asin.get("pageViews"))
    browser = _parse_int(traffic_by_asin.get("browserPageViews"))
    mobile = _parse_int(traffic_by_asin.get("mobileAppPageViews"))
    return browser + mobile


class SpApiBusinessCompareService:
    def __init__(
        self,
        db: Client,
        *,
        client_factory: ClientFactory = _default_client_factory,
        sleep: SleepFn = asyncio.sleep,
        create_report_spacing_s: float = DEFAULT_CREATE_REPORT_SPACING_S,
    ) -> None:
        self.db = db
        self._client_factory = client_factory
        self._sleep = sleep
        self.create_report_spacing_s = create_report_spacing_s

    async def run_compare(
        self,
        *,
        profile_id: str,
        date_from: date,
        date_to: date,
    ) -> dict[str, Any]:
        started_at = time.monotonic()
        warnings: list[str] = []
        days = _date_range(date_from, date_to)
        profile = self._get_profile(profile_id)
        client_id = str(profile.get("client_id") or "").strip()
        marketplace_code = str(profile.get("marketplace_code") or "").strip().upper()
        marketplace_id = MARKETPLACE_IDS_BY_CODE.get(marketplace_code)
        if not marketplace_id:
            raise WBRValidationError(
                f"Marketplace {marketplace_code or '<blank>'} is not mapped for SP-API business compare"
            )
        default_currency_code = DEFAULT_CURRENCY_BY_MARKETPLACE_CODE[marketplace_code]

        connection = self._get_spapi_connection(client_id)
        refresh_token = str(connection.get("refresh_token") or "").strip()
        region_code = str(connection.get("region_code") or "").strip()
        if not refresh_token:
            raise WBRValidationError("Stored SP-API connection has no refresh token")
        if not region_code:
            raise WBRValidationError("Stored SP-API connection has no region_code")

        client = self._client_factory(refresh_token, region_code)
        # Persist per-day instead of accumulating-then-upserting at the end. SP-API's
        # createReport rate limit (~1/min) means a multi-day backfill can blow up
        # midway with SpApiRateLimited. Without per-day saves, every successful day
        # before the failure was discarded — we lost work we'd already paid for.
        # On mid-run failure we still re-raise so the caller (and UI) sees the
        # error, but day-1's rows are already in the DB; a retry resumes cleanly.
        total_rows_fetched = 0
        total_rows_written = 0
        reports_requested = 0
        days_completed = 0
        mid_run_exception: Exception | None = None

        for index, report_day in enumerate(days):
            try:
                rows = await client.fetch_report_rows(
                    REPORT_TYPE_SALES_AND_TRAFFIC,
                    marketplace_ids=[marketplace_id],
                    data_start_time=_day_start(report_day),
                    data_end_time=_day_end_inclusive(report_day),
                    report_options={
                        "asinGranularity": "CHILD",
                        "dateGranularity": "DAY",
                    },
                    format="json",
                )
            except Exception as exc:  # noqa: BLE001
                mid_run_exception = exc
                warnings.append(f"Failed on {report_day.isoformat()}: {exc}")
                break

            reports_requested += 1
            day_facts = self._transform_report_rows(
                rows,
                report_date=report_day,
                default_currency_code=default_currency_code,
            )
            if not rows or not day_facts:
                warnings.append(f"No ASIN rows returned for {report_day.isoformat()}")
            else:
                total_rows_fetched += len(day_facts)
                total_rows_written += self._upsert_compare_facts(
                    profile_id=profile_id, facts=day_facts
                )
            days_completed += 1

            if index < len(days) - 1 and self.create_report_spacing_s > 0:
                await self._sleep(self.create_report_spacing_s)

        if mid_run_exception is not None:
            # Partial progress is already persisted; re-raise so the caller surfaces
            # the failure. A subsequent retry will skip the already-upserted days
            # because the upsert is idempotent on (profile_id, report_date, child_asin).
            raise mid_run_exception

        return {
            "profile_id": profile_id,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "rows_fetched": total_rows_fetched,
            "rows_written": total_rows_written,
            "reports_requested": reports_requested,
            "days_requested": len(days),
            "days_completed": days_completed,
            "elapsed_seconds": round(time.monotonic() - started_at, 3),
            "warnings": warnings,
        }

    def _transform_report_rows(
        self,
        rows: list[dict[str, Any]],
        *,
        report_date: date,
        default_currency_code: str,
    ) -> list[SpApiBusinessFact]:
        by_key: dict[tuple[date, str], SpApiBusinessFact] = {}
        asin_rows: list[dict[str, Any]] = []
        for row in rows:
            if isinstance(row.get("salesAndTrafficByAsin"), list):
                asin_rows.extend(
                    item
                    for item in row["salesAndTrafficByAsin"]
                    if isinstance(item, dict)
                )
            else:
                asin_rows.append(row)

        for row in asin_rows:
            child_asin = str(row.get("childAsin") or "").strip().upper()
            if not child_asin:
                continue

            sales_by_asin = _as_dict(row.get("salesByAsin"))
            traffic_by_asin = _as_dict(row.get("trafficByAsin"))
            ordered_sales = _as_dict(sales_by_asin.get("orderedProductSales"))
            currency_code = _money_currency(ordered_sales) or default_currency_code
            fact = SpApiBusinessFact(
                report_date=report_date,
                child_asin=child_asin,
                parent_asin=str(row.get("parentAsin") or "").strip().upper() or None,
                currency_code=currency_code,
                page_views=_page_views(traffic_by_asin),
                unit_sales=_parse_int(sales_by_asin.get("unitsOrdered")),
                sales=_parse_decimal(_money_amount(ordered_sales)),
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
            by_key[key] = SpApiBusinessFact(
                report_date=existing.report_date,
                child_asin=existing.child_asin,
                parent_asin=existing.parent_asin or fact.parent_asin,
                currency_code=existing.currency_code,
                page_views=existing.page_views + fact.page_views,
                unit_sales=existing.unit_sales + fact.unit_sales,
                sales=(existing.sales + fact.sales).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ),
                source_row_count=existing.source_row_count + fact.source_row_count,
                source_payload={
                    "source_rows": [
                        *(
                            existing.source_payload.get("source_rows")
                            if isinstance(existing.source_payload.get("source_rows"), list)
                            else [existing.source_payload]
                        ),
                        row,
                    ]
                },
            )

        return sorted(by_key.values(), key=lambda item: (item.report_date, item.child_asin))

    def _upsert_compare_facts(
        self,
        *,
        profile_id: str,
        facts: list[SpApiBusinessFact],
    ) -> int:
        if not facts:
            return 0

        payloads = [
            {
                "profile_id": profile_id,
                "sync_run_id": None,
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

        rows_written = 0
        for start in range(0, len(payloads), DEFAULT_INSERT_CHUNK_SIZE):
            chunk = payloads[start : start + DEFAULT_INSERT_CHUNK_SIZE]
            response = (
                self.db.table(COMPARE_TABLE)
                .upsert(
                    chunk,
                    on_conflict="profile_id,report_date,child_asin",
                )
                .execute()
            )
            rows = response.data if isinstance(response.data, list) else []
            rows_written += len(rows) if rows else len(chunk)
        return rows_written

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
