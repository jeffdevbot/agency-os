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
DEFAULT_REPORT_POLL_SECONDS = 30
DEFAULT_REPORT_MAX_POLLS = 60

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
            "purchases",
            "sales",
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
            "purchases",
            "sales",
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
        self.report_poll_seconds = max(
            int(os.getenv("WBR_AMAZON_ADS_REPORT_POLL_SECONDS", str(DEFAULT_REPORT_POLL_SECONDS))),
            10,
        )
        self.report_max_polls = max(
            int(os.getenv("WBR_AMAZON_ADS_REPORT_MAX_POLLS", str(DEFAULT_REPORT_MAX_POLLS))),
            1,
        )

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
        today = datetime.now(UTC).date()
        if date_to > today:
            raise WBRValidationError("date_to must be less than or equal to today")

        profile = self._get_profile(profile_id)
        ads_profile_id = self._require_amazon_ads_profile_id(profile)
        refresh_token = self._require_refresh_token(profile_id)

        chunks = _chunk_date_range(date_from, date_to, chunk_days)
        results = []
        for chunk_start, chunk_end in chunks:
            results.append(
                await self._enqueue_chunk(
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

        result = await self._enqueue_chunk(
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

    async def _enqueue_chunk(
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

        try:
            access_token = await refresh_access_token(refresh_token)
            report_jobs = await self._create_report_jobs(
                access_token=access_token,
                amazon_ads_profile_id=amazon_ads_profile_id,
                date_from=date_from,
                date_to=date_to,
            )
            self._update_sync_run_request_meta(
                run_id=run_id,
                request_meta={
                    "async_reports_v1": True,
                    "marketplace_code": marketplace_code,
                    "report_jobs": report_jobs,
                    "report_progress": self._build_report_progress(report_jobs),
                    "queued_at": datetime.now(UTC).isoformat(),
                },
            )
            return {
                "run": self._get_sync_run(run_id),
                "rows_fetched": 0,
                "rows_loaded": 0,
            }
        except WBRValidationError as exc:
            self._finalize_sync_run(
                run_id=run_id,
                status="error",
                rows_fetched=0,
                rows_loaded=0,
                error_message=str(exc),
            )
            raise
        except Exception as exc:  # noqa: BLE001
            self._finalize_sync_run(
                run_id=run_id,
                status="error",
                rows_fetched=0,
                rows_loaded=0,
                error_message=str(exc),
            )
            raise WBRValidationError("Failed to enqueue Amazon Ads campaign sync") from exc

    async def process_pending_runs(self, *, limit: int = 20) -> dict[str, Any]:
        runs = self._list_running_sync_runs(limit=limit)
        results: list[dict[str, Any]] = []

        for run in runs:
            request_meta = run.get("request_meta")
            if not isinstance(request_meta, dict) or not request_meta.get("async_reports_v1"):
                continue
            try:
                result = await self._process_pending_run(run)
            except Exception as exc:  # noqa: BLE001
                result = self._mark_run_error(run, exc)
            if result is not None:
                results.append(result)

        return {
            "runs_considered": len(runs),
            "runs_processed": len(results),
            "results": results,
        }

    async def _create_report_jobs(
        self,
        *,
        access_token: str,
        amazon_ads_profile_id: str,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        now = datetime.now(UTC).isoformat()
        jobs: list[dict[str, Any]] = []
        for definition in AMAZON_ADS_REPORT_DEFINITIONS:
            report_id = await self._create_campaign_report(
                access_token=access_token,
                amazon_ads_profile_id=amazon_ads_profile_id,
                date_from=date_from,
                date_to=date_to,
                report_definition=definition,
            )
            jobs.append(
                {
                    "report_id": report_id,
                    "status": "pending",
                    "poll_attempts": 0,
                    "next_poll_at": now,
                    "location": None,
                    "status_detail": None,
                    "campaign_type": definition.campaign_type,
                    "ad_product": definition.ad_product,
                    "report_type_id": definition.report_type_id,
                    "columns": definition.columns,
                }
            )
        return jobs

    async def _process_pending_run(self, run: dict[str, Any]) -> dict[str, Any] | None:
        request_meta = run.get("request_meta")
        if not isinstance(request_meta, dict):
            return None

        report_jobs = request_meta.get("report_jobs")
        if not isinstance(report_jobs, list) or not report_jobs:
            return None

        run_id = str(run.get("id") or "").strip()
        profile_id = str(run.get("profile_id") or "").strip()
        if not run_id or not profile_id:
            return None

        now = datetime.now(UTC)
        if self._all_report_jobs_completed(report_jobs):
            return await self._finalize_completed_run(run, request_meta, report_jobs)

        if not self._has_due_report_job(report_jobs, now):
            return None

        refresh_token = self._require_refresh_token(profile_id)
        access_token = await refresh_access_token(refresh_token)
        amazon_ads_profile_id = str(request_meta.get("amazon_ads_profile_id") or "").strip()
        if not amazon_ads_profile_id:
            raise WBRValidationError("Queued Amazon Ads sync run is missing amazon_ads_profile_id")

        updated_jobs = [dict(job) if isinstance(job, dict) else {} for job in report_jobs]
        for job in updated_jobs:
            if job.get("status") in {"completed", "failed"}:
                continue
            if not self._report_job_is_due(job, now):
                continue

            status = await self._get_report_status_once(
                access_token=access_token,
                amazon_ads_profile_id=amazon_ads_profile_id,
                report_id=str(job.get("report_id") or ""),
            )
            if status.status in {"COMPLETED", "SUCCESS"}:
                job["status"] = "completed"
                job["location"] = status.location
                job["completed_at"] = now.isoformat()
                job["status_detail"] = status.status
                continue

            if status.status in {"FAILURE", "FAILED", "CANCELLED"}:
                job["status"] = "failed"
                job["status_detail"] = status.status
                self._update_sync_run_request_meta(
                    run_id=run_id,
                    request_meta={
                        "report_jobs": updated_jobs,
                        "report_progress": self._build_report_progress(updated_jobs, final_status="error"),
                    },
                )
                finished = self._finalize_sync_run(
                    run_id=run_id,
                    status="error",
                    rows_fetched=int(run.get("rows_fetched") or 0),
                    rows_loaded=int(run.get("rows_loaded") or 0),
                    error_message=f"Amazon Ads report failed for {job.get('campaign_type')}: {status.status}",
                )
                return {"run_id": run_id, "status": "error", "run": finished}

            attempts = int(job.get("poll_attempts") or 0) + 1
            if attempts >= self.report_max_polls:
                job["status"] = "failed"
                job["status_detail"] = "poll_limit_exceeded"
                self._update_sync_run_request_meta(
                    run_id=run_id,
                    request_meta={
                        "report_jobs": updated_jobs,
                        "report_progress": self._build_report_progress(updated_jobs, final_status="error"),
                    },
                )
                finished = self._finalize_sync_run(
                    run_id=run_id,
                    status="error",
                    rows_fetched=int(run.get("rows_fetched") or 0),
                    rows_loaded=int(run.get("rows_loaded") or 0),
                    error_message=(
                        f"Amazon Ads report polling exceeded {self.report_max_polls} attempts "
                        f"for {job.get('campaign_type')}"
                    ),
                )
                return {"run_id": run_id, "status": "error", "run": finished}

            job["status"] = "processing"
            job["poll_attempts"] = attempts
            job["status_detail"] = status.status
            job["next_poll_at"] = (now + timedelta(seconds=self._next_poll_delay_seconds(attempts))).isoformat()

        self._update_sync_run_request_meta(
            run_id=run_id,
            request_meta={
                "report_jobs": updated_jobs,
                "report_progress": self._build_report_progress(updated_jobs),
            },
        )

        if self._all_report_jobs_completed(updated_jobs):
            refreshed_run = self._get_sync_run(run_id)
            refreshed_meta = refreshed_run.get("request_meta")
            if isinstance(refreshed_meta, dict):
                latest_jobs = refreshed_meta.get("report_jobs")
                if isinstance(latest_jobs, list):
                    return await self._finalize_completed_run(refreshed_run, refreshed_meta, latest_jobs)

        return {"run_id": run_id, "status": "running"}

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

    async def _get_report_status_once(
        self,
        *,
        access_token: str,
        amazon_ads_profile_id: str,
        report_id: str,
    ) -> AmazonAdsReportStatus:
        timeout = httpx.Timeout(timeout=self.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
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
        status = str(body.get("status") or body.get("processingStatus") or "").strip().upper() or "UNKNOWN"
        location = str(body.get("url") or body.get("location") or "").strip() or None
        return AmazonAdsReportStatus(report_id=report_id, status=status, location=location)

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
                        "purchases",
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

    def _list_running_sync_runs(self, *, limit: int = 20) -> list[dict[str, Any]]:
        response = (
            self.db.table("wbr_sync_runs")
            .select("*")
            .eq("source_type", "amazon_ads")
            .eq("status", "running")
            .order("created_at")
            .limit(limit)
            .execute()
        )
        return response.data if isinstance(response.data, list) else []

    def _get_sync_run(self, run_id: str) -> dict[str, Any]:
        response = self.db.table("wbr_sync_runs").select("*").eq("id", run_id).limit(1).execute()
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise WBRValidationError(f"WBR sync run {run_id} not found")
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

    def _build_report_progress(
        self,
        report_jobs: list[dict[str, Any]],
        *,
        final_status: str | None = None,
    ) -> dict[str, Any]:
        jobs = [job for job in report_jobs if isinstance(job, dict)]
        total_jobs = len(jobs)
        pending_jobs = sum(1 for job in jobs if str(job.get("status") or "") == "pending")
        processing_jobs = sum(1 for job in jobs if str(job.get("status") or "") == "processing")
        completed_jobs = sum(1 for job in jobs if str(job.get("status") or "") == "completed")
        failed_jobs = sum(1 for job in jobs if str(job.get("status") or "") == "failed")

        next_poll_at = None
        for value in sorted(
            {
                str(job.get("next_poll_at") or "").strip()
                for job in jobs
                if str(job.get("status") or "") in {"pending", "processing"}
            }
        ):
            if value:
                next_poll_at = value
                break

        if final_status == "success":
            phase = "completed"
            summary = f"Downloaded and finalized {completed_jobs}/{total_jobs} reports."
        elif final_status == "error" or failed_jobs > 0:
            phase = "failed"
            if failed_jobs > 0:
                summary = f"{completed_jobs}/{total_jobs} reports completed, {failed_jobs} failed."
            else:
                summary = "Worker hit an error before the queued reports could finish."
        elif total_jobs == 0:
            phase = "unknown"
            summary = "No Amazon Ads reports were queued."
        elif completed_jobs == total_jobs:
            phase = "ready_to_finalize"
            summary = f"All {total_jobs} reports are ready to download."
        elif processing_jobs > 0 or completed_jobs > 0:
            phase = "polling"
            waiting_jobs = pending_jobs + processing_jobs
            summary = f"{completed_jobs}/{total_jobs} reports ready, {waiting_jobs} still waiting on Amazon."
        else:
            phase = "queued"
            summary = f"Queued {total_jobs} Amazon Ads report requests."

        return {
            "phase": phase,
            "summary": summary,
            "total_jobs": total_jobs,
            "pending_jobs": pending_jobs,
            "processing_jobs": processing_jobs,
            "completed_jobs": completed_jobs,
            "failed_jobs": failed_jobs,
            "next_poll_at": next_poll_at,
        }

    def _all_report_jobs_completed(self, report_jobs: list[dict[str, Any]]) -> bool:
        return all(str(job.get("status") or "") == "completed" for job in report_jobs if isinstance(job, dict))

    def _has_due_report_job(self, report_jobs: list[dict[str, Any]], now: datetime) -> bool:
        return any(
            self._report_job_is_due(job, now)
            for job in report_jobs
            if isinstance(job, dict) and str(job.get("status") or "") not in {"completed", "failed"}
        )

    def _report_job_is_due(self, job: dict[str, Any], now: datetime) -> bool:
        next_poll_at = str(job.get("next_poll_at") or "").strip()
        if not next_poll_at:
            return True
        try:
            next_dt = datetime.fromisoformat(next_poll_at.replace("Z", "+00:00"))
        except ValueError:
            return True
        if next_dt.tzinfo is None:
            next_dt = next_dt.replace(tzinfo=UTC)
        return next_dt <= now

    def _next_poll_delay_seconds(self, attempts: int) -> int:
        base_delay = max(self.report_poll_seconds, 30)
        return min(base_delay * (2 ** max(attempts - 1, 0)), 120)

    def _mark_run_error(self, run: dict[str, Any], exc: Exception) -> dict[str, Any]:
        run_id = str(run.get("id") or "").strip()
        if not run_id:
            return {"run_id": "", "status": "error", "error_message": str(exc)}

        request_meta = run.get("request_meta")
        request_meta_update: dict[str, Any] = {
            "last_worker_error": str(exc),
            "last_worker_error_at": datetime.now(UTC).isoformat(),
        }
        if isinstance(request_meta, dict):
            report_jobs = request_meta.get("report_jobs")
            if isinstance(report_jobs, list):
                request_meta_update["report_progress"] = self._build_report_progress(
                    report_jobs,
                    final_status="error",
                )

        try:
            self._update_sync_run_request_meta(run_id=run_id, request_meta=request_meta_update)
            finished = self._finalize_sync_run(
                run_id=run_id,
                status="error",
                rows_fetched=int(run.get("rows_fetched") or 0),
                rows_loaded=int(run.get("rows_loaded") or 0),
                error_message=str(exc),
            )
            return {"run_id": run_id, "status": "error", "run": finished}
        except Exception:  # noqa: BLE001
            return {"run_id": run_id, "status": "error", "error_message": str(exc)}

    async def _finalize_completed_run(
        self,
        run: dict[str, Any],
        request_meta: dict[str, Any],
        report_jobs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        run_id = str(run.get("id") or "").strip()
        profile_id = str(run.get("profile_id") or "").strip()
        if not run_id or not profile_id:
            raise WBRValidationError("Queued Amazon Ads sync run is missing required ids")

        raw_rows: list[dict[str, Any]] = []
        for job in report_jobs:
            if not isinstance(job, dict):
                continue
            location = str(job.get("location") or "").strip()
            if not location:
                raise WBRValidationError(
                    f"Amazon Ads report {job.get('report_id')} completed without a download location"
                )
            rows = await self._download_report_rows(location)
            raw_rows.extend(
                [
                    {
                        **row,
                        "__campaign_type": str(job.get("campaign_type") or ""),
                        "__ad_product": str(job.get("ad_product") or ""),
                        "__report_type_id": str(job.get("report_type_id") or ""),
                    }
                    for row in rows
                ]
            )

        marketplace_code = str(request_meta.get("marketplace_code") or "").strip()
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
            date_from=date.fromisoformat(str(run.get("date_from"))),
            date_to=date.fromisoformat(str(run.get("date_to"))),
            facts=facts,
        )
        self._update_sync_run_request_meta(
            run_id=run_id,
            request_meta={
                "report_progress": self._build_report_progress(report_jobs, final_status="success"),
                "finalized_at": datetime.now(UTC).isoformat(),
            },
        )
        finished = self._finalize_sync_run(
            run_id=run_id,
            status="success",
            rows_fetched=len(raw_rows),
            rows_loaded=len(facts),
            error_message=None,
        )
        return {
            "run_id": run_id,
            "status": "success",
            "rows_fetched": len(raw_rows),
            "rows_loaded": len(facts),
            "run": finished,
        }

    def _report_headers(self, access_token: str, amazon_ads_profile_id: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Amazon-Advertising-API-ClientId": _api_client_id(),
            "Amazon-Advertising-API-Scope": amazon_ads_profile_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
