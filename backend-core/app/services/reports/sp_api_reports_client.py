"""Async SP-API Reports API client.

This module intentionally stays domain-agnostic: it creates reports, polls for
completion, downloads report documents, and parses basic TSV/JSON payloads.
Domain-specific ingestion lives in later layers.
"""

from __future__ import annotations

import asyncio
import csv
import gzip
import io
import json
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Literal

import httpx

from .amazon_spapi_auth import (
    get_spapi_region_config,
    refresh_spapi_access_token,
)

REPORTS_API_VERSION = "2021-06-30"
TOKEN_REFRESH_INTERVAL_S = 55 * 60
TERMINAL_FAILURE_STATUSES = {"FATAL", "CANCELLED"}


class SpApiError(Exception):
    """Base exception for SP-API Reports client failures."""


class SpApiReportTimeout(SpApiError):
    """Raised when a report does not reach a terminal status before timeout."""


class SpApiReportFailed(SpApiError):
    """Raised when a report reaches FATAL or CANCELLED."""


class SpApiRateLimited(SpApiError):
    """Raised when SP-API keeps returning 429 after retry attempts."""


class SpApiTransportError(SpApiError):
    """Raised for malformed responses, auth refresh issues, or HTTP failures."""


SleepFn = Callable[[float], Awaitable[None]]
ClockFn = Callable[[], float]


def _to_sp_api_timestamp(value: datetime) -> str:
    normalized = value
    if normalized.tzinfo is None:
        normalized = normalized.replace(tzinfo=UTC)
    return normalized.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None
    return max(0.0, seconds)


def _json_dict(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError as exc:
        raise SpApiTransportError("SP-API response was not valid JSON") from exc
    if not isinstance(data, dict):
        raise SpApiTransportError("SP-API response JSON was not an object")
    return data


def _coerce_tsv_value(value: str | None) -> str | None:
    if value is None:
        return None
    return value if value != "" else None


class SpApiReportsClient:
    """Small async client for the SP-API Reports API."""

    def __init__(
        self,
        refresh_token: str,
        region_code: str,
        *,
        http_client: httpx.AsyncClient | None = None,
        sleep: SleepFn = asyncio.sleep,
        clock: ClockFn = time.monotonic,
        max_rate_limit_retries: int = 3,
    ) -> None:
        self.refresh_token = refresh_token
        self.region_code = region_code
        self.api_base_url = get_spapi_region_config(region_code)["api_base_url"].rstrip("/")
        self._http_client = http_client
        self._sleep = sleep
        self._clock = clock
        self._max_rate_limit_retries = max_rate_limit_retries
        self._access_token: str | None = None
        self._access_token_acquired_at: float | None = None
        self._token_lock = asyncio.Lock()

    async def create_report(
        self,
        report_type: str,
        *,
        marketplace_ids: list[str],
        data_start_time: datetime,
        data_end_time: datetime,
        report_options: dict[str, str] | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "reportType": report_type,
            "dataStartTime": _to_sp_api_timestamp(data_start_time),
            "dataEndTime": _to_sp_api_timestamp(data_end_time),
            "marketplaceIds": marketplace_ids,
        }
        if report_options:
            payload["reportOptions"] = report_options

        response = await self._request(
            "POST",
            f"/reports/{REPORTS_API_VERSION}/reports",
            json=payload,
        )
        report_id = _json_dict(response).get("reportId")
        if not isinstance(report_id, str) or not report_id:
            raise SpApiTransportError("createReport response missing reportId")
        return report_id

    async def wait_for_report(
        self,
        report_id: str,
        *,
        timeout_s: float = 900.0,
        initial_poll_s: float = 5.0,
        max_poll_s: float = 60.0,
    ) -> str:
        deadline = self._clock() + timeout_s
        poll_s = initial_poll_s

        while True:
            if self._clock() > deadline:
                raise SpApiReportTimeout(
                    f"Timed out waiting for SP-API report {report_id}"
                )

            response = await self._request(
                "GET",
                f"/reports/{REPORTS_API_VERSION}/reports/{report_id}",
            )
            data = _json_dict(response)
            status = str(data.get("processingStatus") or "").strip().upper()

            if status == "DONE":
                document_id = data.get("reportDocumentId")
                if not isinstance(document_id, str) or not document_id:
                    raise SpApiTransportError(
                        f"Report {report_id} finished without reportDocumentId"
                    )
                return document_id

            if status in TERMINAL_FAILURE_STATUSES:
                raise SpApiReportFailed(
                    f"SP-API report {report_id} ended with status {status}"
                )

            sleep_for = min(poll_s, max(0.0, deadline - self._clock()))
            if sleep_for <= 0:
                raise SpApiReportTimeout(
                    f"Timed out waiting for SP-API report {report_id}"
                )
            await self._sleep(sleep_for)
            poll_s = min(max_poll_s, poll_s * 1.5)

    async def download_report_document(self, report_document_id: str) -> bytes:
        response = await self._request(
            "GET",
            f"/reports/{REPORTS_API_VERSION}/documents/{report_document_id}",
        )
        data = _json_dict(response)
        document_url = data.get("url")
        if not isinstance(document_url, str) or not document_url:
            raise SpApiTransportError(
                f"Report document {report_document_id} response missing url"
            )

        document_response = await self._request(
            "GET",
            document_url,
            auth_required=False,
        )
        content = document_response.content
        compression = str(data.get("compressionAlgorithm") or "").upper()
        content_encoding = document_response.headers.get("content-encoding", "").lower()
        content_type = document_response.headers.get("content-type", "").lower()
        should_gunzip = (
            compression == "GZIP"
            or content_encoding == "gzip"
            or content_type == "application/gzip"
        )
        if not should_gunzip:
            return content

        try:
            return gzip.decompress(content)
        except OSError as exc:
            raise SpApiTransportError("Unable to gunzip SP-API report document") from exc

    async def fetch_report_rows(
        self,
        report_type: str,
        *,
        marketplace_ids: list[str],
        data_start_time: datetime,
        data_end_time: datetime,
        report_options: dict[str, str] | None = None,
        format: Literal["tsv", "json"] = "tsv",
    ) -> list[dict[str, Any]]:
        report_id = await self.create_report(
            report_type,
            marketplace_ids=marketplace_ids,
            data_start_time=data_start_time,
            data_end_time=data_end_time,
            report_options=report_options,
        )
        report_document_id = await self.wait_for_report(report_id)
        content = await self.download_report_document(report_document_id)

        if format == "json":
            return self._parse_json(content)
        return self._parse_tsv(content)

    async def _get_access_token(self) -> str:
        token_age = None
        if self._access_token_acquired_at is not None:
            token_age = self._clock() - self._access_token_acquired_at
        if self._access_token and token_age is not None and token_age < TOKEN_REFRESH_INTERVAL_S:
            return self._access_token

        async with self._token_lock:
            token_age = None
            if self._access_token_acquired_at is not None:
                token_age = self._clock() - self._access_token_acquired_at
            if (
                self._access_token
                and token_age is not None
                and token_age < TOKEN_REFRESH_INTERVAL_S
            ):
                return self._access_token

            try:
                self._access_token = await refresh_spapi_access_token(self.refresh_token)
            except Exception as exc:  # pragma: no cover - concrete type lives in auth module
                raise SpApiTransportError("Unable to refresh SP-API access token") from exc
            self._access_token_acquired_at = self._clock()
            return self._access_token

    async def _request(
        self,
        method: str,
        url: str,
        *,
        auth_required: bool = True,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        retries = 0
        while True:
            headers: dict[str, str] = {}
            if auth_required:
                headers["x-amz-access-token"] = await self._get_access_token()

            response = await self._send(method, url, headers=headers, json=json)
            if response.status_code == 429:
                if retries >= self._max_rate_limit_retries:
                    raise SpApiRateLimited(
                        f"SP-API rate limit persisted for {method} {url}"
                    )
                retry_after = _retry_after_seconds(response.headers.get("retry-after"))
                await self._sleep(retry_after if retry_after is not None else 1.0)
                retries += 1
                continue

            if response.status_code >= 400:
                detail = response.text[:300]
                raise SpApiTransportError(
                    f"SP-API request failed ({response.status_code}) for {method} {url}: {detail}"
                )
            return response

    async def _send(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any] | None,
    ) -> httpx.Response:
        request_url = url if url.startswith("http") else f"{self.api_base_url}{url}"
        try:
            if self._http_client:
                return await self._http_client.request(
                    method,
                    request_url,
                    headers=headers,
                    json=json,
                )

            async with httpx.AsyncClient(timeout=30) as client:
                return await client.request(
                    method,
                    request_url,
                    headers=headers,
                    json=json,
                )
        except httpx.HTTPError as exc:
            raise SpApiTransportError(
                f"SP-API transport error for {method} {request_url}: {exc}"
            ) from exc

    def _parse_tsv(self, content: bytes) -> list[dict[str, str | None]]:
        # Amazon's legacy TSV reports (GET_MERCHANT_LISTINGS_ALL_DATA,
        # GET_FBA_*, returns, etc.) are commonly cp1252-encoded, not UTF-8 —
        # fall back rather than blow up on bytes like 0xe9 ("é").
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("cp1252")
        reader = csv.DictReader(io.StringIO(text), delimiter="\t")
        return [
            {str(key): _coerce_tsv_value(value) for key, value in row.items() if key}
            for row in reader
        ]

    def _parse_json(self, content: bytes) -> list[dict[str, Any]]:
        # Preserve nested structures (dicts / lists) in the returned rows.
        # SP-API JSON reports like GET_SALES_AND_TRAFFIC_REPORT put the real
        # data inside nested lists (salesAndTrafficByAsin, salesAndTrafficByDate);
        # an earlier scalar-only filter here silently stripped those, surfacing
        # as an empty {} document downstream.
        try:
            parsed = json.loads(content.decode("utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise SpApiTransportError("SP-API report document was not valid JSON") from exc

        if isinstance(parsed, list):
            rows = parsed
        elif isinstance(parsed, dict):
            list_value = next(
                (
                    parsed[key]
                    for key in ("rows", "data", "reportData", "items")
                    if isinstance(parsed.get(key), list)
                ),
                None,
            )
            rows = list_value if list_value is not None else [parsed]
        else:
            raise SpApiTransportError("SP-API JSON report was not a list or object")

        result: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                raise SpApiTransportError("SP-API JSON report row was not an object")
            result.append({str(key): value for key, value in row.items()})
        return result
