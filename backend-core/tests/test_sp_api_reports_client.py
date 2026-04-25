from __future__ import annotations

import gzip
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from app.services.reports import sp_api_reports_client as reports_client_module
from app.services.reports.sp_api_reports_client import (
    SpApiRateLimited,
    SpApiReportFailed,
    SpApiReportsClient,
    SpApiReportTimeout,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sp_api"
START = datetime(2026, 1, 1, tzinfo=UTC)
END = datetime(2026, 1, 2, tzinfo=UTC)


class FakeClock:
    def __init__(self) -> None:
        self.current = 0.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.current

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.current += seconds


@pytest.fixture(autouse=True)
def _stub_access_token(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_refresh(refresh_token: str) -> str:
        assert refresh_token == "refresh-token"
        return "access-token"

    monkeypatch.setattr(
        reports_client_module,
        "refresh_spapi_access_token",
        fake_refresh,
    )


def _client(
    handler: httpx.MockTransport,
    *,
    clock: FakeClock | None = None,
) -> tuple[SpApiReportsClient, httpx.AsyncClient]:
    http_client = httpx.AsyncClient(transport=handler)
    fake_clock = clock or FakeClock()
    return (
        SpApiReportsClient(
            "refresh-token",
            "NA",
            http_client=http_client,
            sleep=fake_clock.sleep,
            clock=fake_clock.now,
            # Tests assert exact sleep durations; jitter would make those
            # assertions flaky. Production paths use the default jitter window.
            rate_limit_jitter_seconds=0.0,
        ),
        http_client,
    )


@pytest.mark.asyncio
async def test_fetch_report_rows_happy_path_gzip_tsv() -> None:
    requests: list[httpx.Request] = []
    gzipped_report = (FIXTURE_DIR / "sales_and_traffic.tsv.gz").read_bytes()

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST" and request.url.path == "/reports/2021-06-30/reports":
            assert request.headers["x-amz-access-token"] == "access-token"
            return httpx.Response(200, json={"reportId": "report-1"})
        if request.url.path == "/reports/2021-06-30/reports/report-1":
            return httpx.Response(
                200,
                json={"processingStatus": "DONE", "reportDocumentId": "doc-1"},
            )
        if request.url.path == "/reports/2021-06-30/documents/doc-1":
            return httpx.Response(
                200,
                json={
                    "url": "https://documents.example.test/report.tsv.gz",
                    "compressionAlgorithm": "GZIP",
                },
            )
        if request.url.host == "documents.example.test":
            return httpx.Response(200, content=gzipped_report)
        return httpx.Response(404)

    client, http_client = _client(httpx.MockTransport(handler))
    try:
        rows = await client.fetch_report_rows(
            "GET_SALES_AND_TRAFFIC_REPORT",
            marketplace_ids=["ATVPDKIKX0DER"],
            data_start_time=START,
            data_end_time=END,
        )
    finally:
        await http_client.aclose()

    assert rows == [
        {"asin": "B000TEST01", "sessions": "12", "sales": "34.50"},
        {"asin": "B000TEST02", "sessions": "8", "sales": None},
    ]
    assert [request.url.path for request in requests[:3]] == [
        "/reports/2021-06-30/reports",
        "/reports/2021-06-30/reports/report-1",
        "/reports/2021-06-30/documents/doc-1",
    ]


@pytest.mark.asyncio
async def test_wait_for_report_poll_backoff_grows() -> None:
    clock = FakeClock()
    statuses = ["IN_PROGRESS", "IN_QUEUE", "IN_PROGRESS", "DONE"]

    async def handler(request: httpx.Request) -> httpx.Response:
        status = statuses.pop(0)
        payload = {"processingStatus": status}
        if status == "DONE":
            payload["reportDocumentId"] = "doc-1"
        return httpx.Response(200, json=payload)

    client, http_client = _client(httpx.MockTransport(handler), clock=clock)
    try:
        document_id = await client.wait_for_report(
            "report-1",
            timeout_s=60,
            initial_poll_s=2,
            max_poll_s=10,
        )
    finally:
        await http_client.aclose()

    assert document_id == "doc-1"
    assert clock.sleeps == [2, 3.0, 4.5]


@pytest.mark.asyncio
async def test_create_report_retries_after_429_retry_after_header() -> None:
    clock = FakeClock()
    attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"retry-after": "2.5"})
        return httpx.Response(200, json={"reportId": "report-1"})

    client, http_client = _client(httpx.MockTransport(handler), clock=clock)
    try:
        report_id = await client.create_report(
            "GET_SALES_AND_TRAFFIC_REPORT",
            marketplace_ids=["ATVPDKIKX0DER"],
            data_start_time=START,
            data_end_time=END,
        )
    finally:
        await http_client.aclose()

    assert report_id == "report-1"
    assert attempts == 2
    assert clock.sleeps == [2.5]


@pytest.mark.asyncio
async def test_create_report_raises_when_rate_limit_persists() -> None:
    clock = FakeClock()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"retry-after": "1"})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = SpApiReportsClient(
        "refresh-token",
        "NA",
        http_client=http_client,
        sleep=clock.sleep,
        clock=clock.now,
        max_rate_limit_retries=1,
        rate_limit_jitter_seconds=0.0,
    )
    try:
        with pytest.raises(SpApiRateLimited):
            await client.create_report(
                "GET_SALES_AND_TRAFFIC_REPORT",
                marketplace_ids=["ATVPDKIKX0DER"],
                data_start_time=START,
                data_end_time=END,
            )
    finally:
        await http_client.aclose()

    assert clock.sleeps == [1.0]


@pytest.mark.asyncio
async def test_create_report_429_without_retry_after_uses_long_default() -> None:
    # Regression: SP-API doesn't always send a retry-after header on 429s. The
    # Distex 2026-04-25 incident showed 4 successive 429s on createReport with
    # no header, and our 1s default burned through all retries before the
    # 1-per-minute bucket refilled. Default fallback is now 60s.
    clock = FakeClock()
    attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429)  # no retry-after header
        return httpx.Response(200, json={"reportId": "report-1"})

    client, http_client = _client(httpx.MockTransport(handler), clock=clock)
    try:
        report_id = await client.create_report(
            "GET_SALES_AND_TRAFFIC_REPORT",
            marketplace_ids=["ATVPDKIKX0DER"],
            data_start_time=START,
            data_end_time=END,
        )
    finally:
        await http_client.aclose()

    assert report_id == "report-1"
    assert attempts == 2
    # Jitter is disabled in the test helper, so we get the exact default.
    assert clock.sleeps == [60.0]


@pytest.mark.asyncio
async def test_wait_for_report_raises_on_fatal_status() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"processingStatus": "FATAL"})

    client, http_client = _client(httpx.MockTransport(handler))
    try:
        with pytest.raises(SpApiReportFailed, match="FATAL"):
            await client.wait_for_report("report-1")
    finally:
        await http_client.aclose()


@pytest.mark.asyncio
async def test_wait_for_report_raises_on_timeout() -> None:
    clock = FakeClock()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"processingStatus": "IN_PROGRESS"})

    client, http_client = _client(httpx.MockTransport(handler), clock=clock)
    try:
        with pytest.raises(SpApiReportTimeout):
            await client.wait_for_report(
                "report-1",
                timeout_s=5,
                initial_poll_s=2,
                max_poll_s=10,
            )
    finally:
        await http_client.aclose()

    assert clock.sleeps == [2, 3.0]


@pytest.mark.asyncio
async def test_download_uncompressed_document() -> None:
    raw_report = "asin\tsessions\nB000TEST01\t12\n".encode()

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/reports/2021-06-30/documents/doc-1":
            return httpx.Response(200, json={"url": "https://documents.example.test/report.tsv"})
        if request.url.host == "documents.example.test":
            return httpx.Response(200, content=raw_report)
        return httpx.Response(404)

    client, http_client = _client(httpx.MockTransport(handler))
    try:
        content = await client.download_report_document("doc-1")
    finally:
        await http_client.aclose()

    assert content == raw_report


@pytest.mark.asyncio
async def test_fetch_report_rows_cp1252_tsv_fallback() -> None:
    raw_report = "asin\ttitle\nB000TEST01\tCafé déluxe\n".encode("cp1252")

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/reports/2021-06-30/reports":
            return httpx.Response(200, json={"reportId": "report-1"})
        if request.url.path == "/reports/2021-06-30/reports/report-1":
            return httpx.Response(
                200,
                json={"processingStatus": "DONE", "reportDocumentId": "doc-1"},
            )
        if request.url.path == "/reports/2021-06-30/documents/doc-1":
            return httpx.Response(200, json={"url": "https://documents.example.test/report.tsv"})
        if request.url.host == "documents.example.test":
            return httpx.Response(200, content=raw_report)
        return httpx.Response(404)

    client, http_client = _client(httpx.MockTransport(handler))
    try:
        rows = await client.fetch_report_rows(
            "GET_MERCHANT_LISTINGS_ALL_DATA",
            marketplace_ids=["A2EUQ1WTGCTBG2"],
            data_start_time=START,
            data_end_time=END,
        )
    finally:
        await http_client.aclose()

    assert rows == [{"asin": "B000TEST01", "title": "Café déluxe"}]


@pytest.mark.asyncio
async def test_fetch_report_rows_json_format() -> None:
    json_report = (FIXTURE_DIR / "report.json").read_bytes()

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/reports/2021-06-30/reports":
            return httpx.Response(200, json={"reportId": "report-1"})
        if request.url.path == "/reports/2021-06-30/reports/report-1":
            return httpx.Response(
                200,
                json={"processingStatus": "DONE", "reportDocumentId": "doc-1"},
            )
        if request.url.path == "/reports/2021-06-30/documents/doc-1":
            return httpx.Response(200, json={"url": "https://documents.example.test/report.json"})
        if request.url.host == "documents.example.test":
            return httpx.Response(200, content=json_report)
        return httpx.Response(404)

    client, http_client = _client(httpx.MockTransport(handler))
    try:
        rows = await client.fetch_report_rows(
            "GET_JSON_REPORT",
            marketplace_ids=["ATVPDKIKX0DER"],
            data_start_time=START,
            data_end_time=END,
            format="json",
        )
    finally:
        await http_client.aclose()

    assert rows == [
        {
            "asin": "B000TEST01",
            "sessions": 12,
            "conversionRate": 0.25,
            "note": None,
        },
        {
            "asin": "B000TEST02",
            "sessions": 8,
            "conversionRate": 0.125,
            "note": "synthetic",
        },
    ]


@pytest.mark.asyncio
async def test_fetch_report_rows_json_preserves_nested_structure() -> None:
    # Regression: GET_SALES_AND_TRAFFIC_REPORT returns a single top-level object
    # whose real data lives in nested lists (salesAndTrafficByAsin, etc.). An
    # earlier scalar-only filter in _parse_json silently stripped those nested
    # values and returned [{}], surfacing downstream as the "empty {} document"
    # symptom we chased with Amazon support.
    import json as _json

    document = {
        "reportSpecification": {
            "reportType": "GET_SALES_AND_TRAFFIC_REPORT",
            "marketplaceIds": ["A2EUQ1WTGCTBG2"],
        },
        "salesAndTrafficByDate": [
            {"date": "2026-04-15", "salesByDate": {"orderedProductSales": {"amount": 42.0}}}
        ],
        "salesAndTrafficByAsin": [
            {
                "childAsin": "B000TEST01",
                "parentAsin": "B000PARENT1",
                "salesByAsin": {
                    "orderedProductSales": {"amount": 10.5, "currencyCode": "CAD"},
                    "unitsOrdered": 3,
                },
                "trafficByAsin": {"pageViews": 120},
            }
        ],
    }
    raw_bytes = _json.dumps(document).encode("utf-8")

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/reports/2021-06-30/reports":
            return httpx.Response(200, json={"reportId": "report-1"})
        if request.url.path == "/reports/2021-06-30/reports/report-1":
            return httpx.Response(
                200,
                json={"processingStatus": "DONE", "reportDocumentId": "doc-1"},
            )
        if request.url.path == "/reports/2021-06-30/documents/doc-1":
            return httpx.Response(200, json={"url": "https://documents.example.test/report.json"})
        if request.url.host == "documents.example.test":
            return httpx.Response(200, content=raw_bytes)
        return httpx.Response(404)

    client, http_client = _client(httpx.MockTransport(handler))
    try:
        rows = await client.fetch_report_rows(
            "GET_SALES_AND_TRAFFIC_REPORT",
            marketplace_ids=["A2EUQ1WTGCTBG2"],
            data_start_time=START,
            data_end_time=END,
            format="json",
        )
    finally:
        await http_client.aclose()

    assert len(rows) == 1
    row = rows[0]
    assert isinstance(row.get("salesAndTrafficByAsin"), list)
    assert isinstance(row.get("salesAndTrafficByDate"), list)
    assert isinstance(row.get("reportSpecification"), dict)
    asin_rows = row["salesAndTrafficByAsin"]
    assert asin_rows[0]["childAsin"] == "B000TEST01"
    assert asin_rows[0]["salesByAsin"]["orderedProductSales"]["amount"] == 10.5
    assert asin_rows[0]["trafficByAsin"]["pageViews"] == 120
