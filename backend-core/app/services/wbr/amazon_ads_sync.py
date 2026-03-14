from __future__ import annotations

import gzip
import json
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

import httpx
from supabase import Client

from .amazon_ads_auth import refresh_access_token
from .profiles import WBRNotFoundError, WBRValidationError

DEFAULT_TIMEOUT_SECONDS = 360
MIN_TIMEOUT_SECONDS = 60
DEFAULT_CHUNK_DAYS = 14
DEFAULT_DAILY_LOOKBACK_DAYS = 14
DEFAULT_REPORT_POLL_SECONDS = 3
DEFAULT_REPORT_MAX_POLLS = 100

AMAZON_ADS_API_URL = "https://advertising-api.amazon.com"
AMAZON_ADS_REPORT_CREATE_PATH = "/reporting/reports"


@dataclass(frozen=True)
class AmazonAdsReportDefinition:
    ad_product: str
    report_type_id: str
    campaign_type: str
    columns: list[str]


AMAZON_ADS_REPORT_DEFINITIONS = [
    AmazonAdsReportDefinition(
        ad_product="SPONSORED_PRODUCTS",
        report_type_id="spCampaigns",
        campaign_type="sponsored_products",
        columns=[
            "date",
            "campaignId",
            "campaignName",
            "impressions",
            "clicks",
            "cost",
            "purchases7d",
            "sales7d",
        ],
    ),
    AmazonAdsReportDefinition(
        ad_product="SPONSORED_BRANDS",
        report_type_id="sbCampaigns",
        campaign_type="sponsored_brands",
        columns=[
            "date",
            "campaignId",
            "campaignName",
            "impressions",
            "clicks",
            "cost",
            "purchases14d",
            "sales14d",
        ],
    ),
    AmazonAdsReportDefinition(
        ad_product="SPONSORED_DISPLAY",
        report_type_id="sdCampaigns",
        campaign_type="sponsored_display",
        columns=[
            "date",
            "campaignId",
            "campaignName",
            "impressions",
            "clicks",
            "cost",
            "purchases14d",
            "sales14d",
        ],
    ),
]


@dataclass(frozen=True)
class AggregatedAdsFact:
    report_date: date
    campaign_id: str | None
    campaign_name: str
    campaign_type: str
    impressions: int
    clicks: int
    spend: Decimal
    orders: int
    sales: Decimal
    currency_code: str | None
    source_payload: dict[str, Any]


@dataclass(frozen=True)
class AmazonAdsReportStatus:
    report_id: str
    status: str
    location: str | None


def _clean_numeric_text(value: Any) -> str:
    return str(value or "").strip().replace(",", "")


def _parse_int(value: Any) -> int:
    text = _clean_numeric_text(value)
    if not text:
        return 0
    try:
        return int(Decimal(text))
    except (InvalidOperation, ValueError) as exc:
        raise WBRValidationError(f'Invalid Amazon Ads integer value "{text}"') from exc


def _parse_decimal(value: Any) -> Decimal:
    text = _clean_numeric_text(value)
    if not text:
        return Decimal("0.00")
    try:
        return Decimal(text).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise WBRValidationError(f'Invalid Amazon Ads decimal value "{text}"') from exc


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


def _default_currency_code(marketplace_code: str | None) -> str | None:
    code = str(marketplace_code or "").strip().upper()
    if code == "CA":
        return "CAD"
    if code == "UK":
        return "GBP"
    if code == "MX":
        return "MXN"
    if code == "AU":
        return "AUD"
    if code == "JP":
        return "JPY"
    if code in {"DE", "FR", "IT", "ES", "NL", "SE", "PL", "BE"}:
        return "EUR"
    if code == "US":
        return "USD"
    return None


def _api_client_id() -> str:
    value = os.getenv("AMAZON_ADS_CLIENT_ID", "").strip()
    if not value:
        raise WBRValidationError("AMAZON_ADS_CLIENT_ID is not configured")
    return value


def _extract_first_present(row: dict[str, Any], *field_names: str) -> Any:
    for field_name in field_names:
        value = row.get(field_name)
        if value not in (None, ""):
            return value
    return None


class AmazonAdsSyncService:
    def __init__(self, db: Client) -> None:
        self.db = db
        configured_timeout = int(os.getenv("WBR_REQUEST_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
        self.timeout_seconds = max(configured_timeout, MIN_TIMEOUT_SECONDS)
        self.api_base_url = os.getenv("AMAZON_ADS_API_URL", AMAZON_ADS_API_URL).rstrip("/")
        self.report_poll_seconds = max(int(os.getenv("WBR_AMAZON_ADS_REPORT_POLL_SECONDS", str(DEFAULT_REPORT_POLL_SECONDS))), 1)
        self.report_max_polls = max(int(os.getenv("WBR_AMAZON_ADS_REPORT_MAX_POLLS", str(DEFAULT_REPORT_MAX_POLLS))), 1)

    def list_sync_runs(self, profile_id: str, *, source_type: str = "amazon_ads") -> list[dict[str, Any]]:
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
        profile = self._get_profile(profile_id)
        ads_profile_id = self._require_amazon_ads_profile_id(profile)
        refresh_token = self._require_refresh_token(profile_id)

        chunks = _chunk_date_range(date_from, date_to, chunk_days)
        results = []
        for chunk_start, chunk_end in chunks:
            results.append(
                await self._run_chunk(
                    profile_id=profile_id,
                    amazon_ads_profile_id=ads_profile_id,
                    refresh_token=refresh_token,
                    marketplace_code=str(profile.get("marketplace_code") or ""),
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
        ads_profile_id = self._require_amazon_ads_profile_id(profile)
        refresh_token = self._require_refresh_token(profile_id)
        lookback_days = int(profile.get("daily_rewrite_days") or DEFAULT_DAILY_LOOKBACK_DAYS)
        date_to = datetime.now(UTC).date()
        date_from = date_to - timedelta(days=max(lookback_days - 1, 0))

        result = await self._run_chunk(
            profile_id=profile_id,
            amazon_ads_profile_id=ads_profile_id,
            refresh_token=refresh_token,
            marketplace_code=str(profile.get("marketplace_code") or ""),
            date_from=date_from,
            date_to=date_to,
            job_type="daily_refresh",
            user_id=user_id,
        )

        return {
            "profile_id": profile_id,
            "job_type": "daily_refresh",
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "chunk": result,
        }

    async def _run_chunk(
        self,
        *,
        profile_id: str,
        amazon_ads_profile_id: str,
        refresh_token: str,
        marketplace_code: str,
        date_from: date,
        date_to: date,
        job_type: str,
        user_id: str | None,
    ) -> dict[str, Any]:
        run = self._create_sync_run(
            profile_id=profile_id,
            source_type="amazon_ads",
            job_type=job_type,
            date_from=date_from,
            date_to=date_to,
            request_meta={
                "amazon_ads_profile_id": amazon_ads_profile_id,
                "report_definitions": [
                    {
                        "ad_product": definition.ad_product,
                        "report_type_id": definition.report_type_id,
                        "campaign_type": definition.campaign_type,
                        "columns": definition.columns,
                    }
                    for definition in AMAZON_ADS_REPORT_DEFINITIONS
                ],
            },
            user_id=user_id,
        )
        run_id = str(run["id"])
        raw_rows: list[dict[str, Any]] = []

        try:
            raw_rows = await self._fetch_rows(
                amazon_ads_profile_id=amazon_ads_profile_id,
                refresh_token=refresh_token,
                date_from=date_from,
                date_to=date_to,
            )
            facts = self._aggregate_rows(raw_rows, marketplace_code=marketplace_code)
            if raw_rows and not facts:
                self._update_sync_run_request_meta(
                    run_id=run_id,
                    request_meta={
                        "debug_row_count": len(raw_rows),
                        "debug_first_row_keys": self._preview_first_row_keys(raw_rows),
                        "debug_first_row_preview": self._preview_first_row(raw_rows),
                    },
                )
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
            raise WBRValidationError("Failed to sync Amazon Ads campaign data") from exc

    async def _fetch_rows(
        self,
        *,
        amazon_ads_profile_id: str,
        refresh_token: str,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        access_token = await refresh_access_token(refresh_token)
        rows: list[dict[str, Any]] = []
        for definition in AMAZON_ADS_REPORT_DEFINITIONS:
            report_id = await self._create_campaign_report(
                access_token=access_token,
                amazon_ads_profile_id=amazon_ads_profile_id,
                date_from=date_from,
                date_to=date_to,
                report_definition=definition,
            )
            report = await self._wait_for_report(
                access_token=access_token,
                amazon_ads_profile_id=amazon_ads_profile_id,
                report_id=report_id,
            )
            if not report.location:
                raise WBRValidationError(
                    f"Amazon Ads {definition.campaign_type} report completed without a download location"
                )
            product_rows = await self._download_report_rows(report.location)
            rows.extend(
                [
                    {
                        **row,
                        "__campaign_type": definition.campaign_type,
                        "__ad_product": definition.ad_product,
                        "__report_type_id": definition.report_type_id,
                    }
                    for row in product_rows
                ]
            )
        return rows

    async def _create_campaign_report(
        self,
        *,
        access_token: str,
        amazon_ads_profile_id: str,
        date_from: date,
        date_to: date,
        report_definition: AmazonAdsReportDefinition,
    ) -> str:
        payload = {
            "name": (
                f"WBR {report_definition.campaign_type} {date_from.isoformat()} "
                f"to {date_to.isoformat()}"
            ),
            "startDate": date_from.isoformat(),
            "endDate": date_to.isoformat(),
            "configuration": {
                "adProduct": report_definition.ad_product,
                "groupBy": ["campaign"],
                "columns": report_definition.columns,
                "reportTypeId": report_definition.report_type_id,
                "timeUnit": "DAILY",
                "format": "GZIP_JSON",
            },
        }
        timeout = httpx.Timeout(timeout=self.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.api_base_url}{AMAZON_ADS_REPORT_CREATE_PATH}",
                json=payload,
                headers=self._report_headers(access_token, amazon_ads_profile_id),
            )

        if response.status_code not in {200, 202}:
            detail = response.text.strip().replace("\n", " ")[:300]
            raise WBRValidationError(
                f"Amazon Ads report create failed ({response.status_code}): {detail}"
            )

        body = response.json()
        report_id = str(body.get("reportId") or body.get("report_id") or "").strip()
        if not report_id:
            raise WBRValidationError("Amazon Ads report create response missing reportId")
        return report_id

    async def _wait_for_report(
        self,
        *,
        access_token: str,
        amazon_ads_profile_id: str,
        report_id: str,
    ) -> AmazonAdsReportStatus:
        timeout = httpx.Timeout(timeout=self.timeout_seconds)
        last_status = "UNKNOWN"
        async with httpx.AsyncClient(timeout=timeout) as client:
            for _ in range(self.report_max_polls):
                response = await client.get(
                    f"{self.api_base_url}{AMAZON_ADS_REPORT_CREATE_PATH}/{report_id}",
                    headers=self._report_headers(access_token, amazon_ads_profile_id),
                )
                if response.status_code >= 400:
                    detail = response.text.strip().replace("\n", " ")[:300]
                    raise WBRValidationError(
                        f"Amazon Ads report status failed ({response.status_code}): {detail}"
                    )
                body = response.json()
                status = str(body.get("status") or body.get("processingStatus") or "").strip().upper()
                location = str(body.get("url") or body.get("location") or "").strip() or None
                last_status = status or last_status
                current = AmazonAdsReportStatus(report_id=report_id, status=status, location=location)
                if status in {"COMPLETED", "SUCCESS"}:
                    return current
                if status in {"FAILURE", "FAILED", "CANCELLED"}:
                    detail = str(body.get("statusDetails") or body.get("failureReason") or status)
                    raise WBRValidationError(f"Amazon Ads report failed: {detail}")
                await self._sleep(self.report_poll_seconds)

        raise WBRValidationError(
            f"Amazon Ads report polling timed out after {self.report_max_polls * self.report_poll_seconds}s "
            f"(last status: {last_status})"
        )

    async def _download_report_rows(self, location: str) -> list[dict[str, Any]]:
        timeout = httpx.Timeout(timeout=self.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(location)

        if response.status_code >= 400:
            detail = response.text.strip().replace("\n", " ")[:300]
            raise WBRValidationError(
                f"Amazon Ads report download failed ({response.status_code}): {detail}"
            )

        raw_bytes = response.content
        if raw_bytes[:2] == b"\x1f\x8b":
            try:
                raw_bytes = gzip.decompress(raw_bytes)
            except Exception as exc:  # noqa: BLE001
                raise WBRValidationError(f"Failed to decompress Amazon Ads report: {exc}") from exc

        text = raw_bytes.decode("utf-8").strip()
        if not text:
            return []

        try:
            payload = json.loads(text)
        except Exception:
            rows: list[dict[str, Any]] = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception as exc:  # noqa: BLE001
                    raise WBRValidationError(f"Failed to decode Amazon Ads report row: {exc}") from exc
                if isinstance(row, dict):
                    rows.append(row)
            return rows

        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            for key in ("rows", "data", "report"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [row for row in value if isinstance(row, dict)]
        raise WBRValidationError("Unexpected Amazon Ads report payload shape")

    def _aggregate_rows(
        self,
        rows: list[dict[str, Any]],
        *,
        marketplace_code: str,
    ) -> list[AggregatedAdsFact]:
        by_key: dict[tuple[date, str, str], AggregatedAdsFact] = {}

        for row in rows:
            date_text = self._extract_report_date_text(row)
            campaign_name = self._extract_campaign_name(row)
            if not date_text or not campaign_name:
                continue

            try:
                report_date = self._parse_report_date(date_text)
            except ValueError as exc:
                raise WBRValidationError(f'Invalid Amazon Ads report date "{date_text}"') from exc

            campaign_id = self._extract_campaign_id(row)
            campaign_type = str(row.get("__campaign_type") or "sponsored_products").strip() or "sponsored_products"
            currency_code = (
                str(
                    row.get("currencyCode")
                    or row.get("currency_code")
                    or self._nested_get(row, "campaign", "currencyCode")
                    or self._nested_get(row, "accountInfo", "currencyCode")
                    or ""
                ).strip().upper()
                or None
            )
            currency_code = currency_code or _default_currency_code(marketplace_code)
            fact = AggregatedAdsFact(
                report_date=report_date,
                campaign_id=campaign_id,
                campaign_name=campaign_name,
                campaign_type=campaign_type,
                impressions=_parse_int(row.get("impressions")),
                clicks=_parse_int(row.get("clicks")),
                spend=_parse_decimal(row.get("cost") or row.get("spend")),
                orders=_parse_int(
                    _extract_first_present(
                        row,
                        "purchases7d",
                        "purchases14d",
                        "orders",
                        "attributedConversions14d",
                        "attributedConversions7d",
                        "conversions14d",
                        "conversions7d",
                    )
                ),
                sales=_parse_decimal(
                    _extract_first_present(
                        row,
                        "sales7d",
                        "sales14d",
                        "sales",
                        "attributedSales14d",
                        "attributedSales7d",
                    )
                ),
                currency_code=currency_code,
                source_payload=row,
            )

            key = (report_date, campaign_name, campaign_type)
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = fact
                continue

            resolved_currency = existing.currency_code or fact.currency_code
            if existing.currency_code and fact.currency_code and existing.currency_code != fact.currency_code:
                raise WBRValidationError(
                    f"Multiple currency codes found for {campaign_name} on {report_date.isoformat()}"
                )

            if existing.campaign_id and fact.campaign_id and existing.campaign_id != fact.campaign_id:
                merged_campaign_id = None
            else:
                merged_campaign_id = existing.campaign_id or fact.campaign_id

            existing_rows = existing.source_payload.get("source_rows")
            merged_payload: dict[str, Any] = {
                "source_rows": [
                    *(existing_rows if isinstance(existing_rows, list) else [existing.source_payload]),
                    row,
                ]
            }
            by_key[key] = AggregatedAdsFact(
                report_date=existing.report_date,
                campaign_id=merged_campaign_id,
                campaign_name=existing.campaign_name,
                campaign_type=existing.campaign_type,
                impressions=existing.impressions + fact.impressions,
                clicks=existing.clicks + fact.clicks,
                spend=(existing.spend + fact.spend).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                orders=existing.orders + fact.orders,
                sales=(existing.sales + fact.sales).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                currency_code=resolved_currency,
                source_payload=merged_payload,
            )

        return sorted(
            by_key.values(),
            key=lambda item: (item.report_date, item.campaign_type, item.campaign_name.lower()),
        )

    def _extract_report_date_text(self, row: dict[str, Any]) -> str:
        for value in (
            row.get("date"),
            row.get("reportDate"),
            row.get("report_date"),
            row.get("startDate"),
            row.get("start_date"),
            self._nested_get(row, "date"),
            self._nested_get(row, "dimensions", "date"),
            self._nested_get(row, "dimensionValues", "date"),
            self._nested_get(row, "metadata", "date"),
        ):
            text = str(value or "").strip()
            if text:
                return text
        return ""

    def _extract_campaign_name(self, row: dict[str, Any]) -> str:
        for value in (
            row.get("campaignName"),
            row.get("campaign_name"),
            row.get("campaign"),
            self._nested_get(row, "campaign", "campaignName"),
            self._nested_get(row, "campaign", "name"),
            self._nested_get(row, "campaignName"),
            self._nested_get(row, "dimensionValues", "campaignName"),
            self._nested_get(row, "dimensions", "campaignName"),
        ):
            if isinstance(value, dict):
                text = str(value.get("campaignName") or value.get("name") or "").strip()
            else:
                text = str(value or "").strip()
            if text:
                return text
        return ""

    def _extract_campaign_id(self, row: dict[str, Any]) -> str | None:
        for value in (
            row.get("campaignId"),
            row.get("campaign_id"),
            self._nested_get(row, "campaign", "campaignId"),
            self._nested_get(row, "campaign", "id"),
            self._nested_get(row, "dimensionValues", "campaignId"),
            self._nested_get(row, "dimensions", "campaignId"),
        ):
            text = str(value or "").strip()
            if text:
                return text
        return None

    def _parse_report_date(self, text: str) -> date:
        normalized = text.strip()
        if len(normalized) == 8 and normalized.isdigit():
            normalized = f"{normalized[:4]}-{normalized[4:6]}-{normalized[6:8]}"
        return date.fromisoformat(normalized[:10])

    def _nested_get(self, value: Any, *path: str) -> Any:
        current = value
        for key in path:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
        return current

    def _preview_first_row_keys(self, rows: list[dict[str, Any]]) -> list[str]:
        if not rows or not isinstance(rows[0], dict):
            return []
        return sorted(str(key) for key in rows[0].keys())[:50]

    def _preview_first_row(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not rows or not isinstance(rows[0], dict):
            return {}
        first = rows[0]
        preview: dict[str, Any] = {}
        for key, value in first.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                preview[str(key)] = value
            elif isinstance(value, dict):
                preview[str(key)] = {
                    str(inner_key): inner_value
                    for inner_key, inner_value in list(value.items())[:10]
                    if isinstance(inner_value, (str, int, float, bool)) or inner_value is None
                }
            else:
                preview[str(key)] = str(value)[:120]
            if len(preview) >= 20:
                break
        return preview

    def _replace_fact_window(
        self,
        *,
        profile_id: str,
        sync_run_id: str,
        date_from: date,
        date_to: date,
        facts: list[AggregatedAdsFact],
    ) -> None:
        (
            self.db.table("wbr_ads_campaign_daily")
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
                "campaign_id": fact.campaign_id,
                "campaign_name": fact.campaign_name,
                "campaign_type": fact.campaign_type,
                "impressions": fact.impressions,
                "clicks": fact.clicks,
                "spend": str(fact.spend),
                "orders": fact.orders,
                "sales": str(fact.sales),
                "currency_code": fact.currency_code,
                "source_payload": fact.source_payload,
            }
            for fact in facts
        ]

        for start in range(0, len(payloads), 500):
            chunk = payloads[start : start + 500]
            response = self.db.table("wbr_ads_campaign_daily").insert(chunk).execute()
            rows = response.data if isinstance(response.data, list) else []
            if len(rows) != len(chunk):
                raise WBRValidationError("Failed to store Amazon Ads campaign facts")

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

    def _require_amazon_ads_profile_id(self, profile: dict[str, Any]) -> str:
        value = str(profile.get("amazon_ads_profile_id") or "").strip()
        if not value:
            raise WBRValidationError("WBR profile is missing amazon_ads_profile_id")
        return value

    def _require_refresh_token(self, profile_id: str) -> str:
        response = (
            self.db.table("wbr_amazon_ads_connections")
            .select("amazon_ads_refresh_token")
            .eq("profile_id", profile_id)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        refresh_token = str(rows[0].get("amazon_ads_refresh_token") or "").strip() if rows else ""
        if not refresh_token:
            raise WBRValidationError("No Amazon Ads connection found. Connect first.")
        return refresh_token

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

    def _update_sync_run_request_meta(
        self,
        *,
        run_id: str,
        request_meta: dict[str, Any],
    ) -> None:
        response = self.db.table("wbr_sync_runs").select("request_meta").eq("id", run_id).limit(1).execute()
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            return
        existing_meta = rows[0].get("request_meta")
        merged_meta = existing_meta if isinstance(existing_meta, dict) else {}
        merged_meta = {**merged_meta, **request_meta}
        self.db.table("wbr_sync_runs").update({"request_meta": merged_meta}).eq("id", run_id).execute()

    def _report_headers(self, access_token: str, amazon_ads_profile_id: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Amazon-Advertising-API-ClientId": _api_client_id(),
            "Amazon-Advertising-API-Scope": amazon_ads_profile_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _sleep(self, seconds: int) -> None:
        import asyncio

        await asyncio.sleep(seconds)
