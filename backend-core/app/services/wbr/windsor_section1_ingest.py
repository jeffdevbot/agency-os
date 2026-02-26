import csv
import io
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from supabase import Client


WINDSOR_SECTION1_FIELDS = [
    "account_id",
    "date",
    "sales_and_traffic_report_by_date__childasin",
    "sales_and_traffic_report_by_date__parentasin",
    "sales_and_traffic_report_by_date__trafficbyasin_pageviews",
    "sales_and_traffic_report_by_date__salesbyasin_unitsordered",
    "sales_and_traffic_report_by_date__salesbyasin_orderedproductsales_amount",
    "sales_and_traffic_report_by_date__salesbyasin_orderedproductsales_currencycode",
]

FIELD_ACCOUNT_ID = "account_id"
FIELD_DATE = "date"
FIELD_CHILD_ASIN = "sales_and_traffic_report_by_date__childasin"
FIELD_PARENT_ASIN = "sales_and_traffic_report_by_date__parentasin"
FIELD_PAGE_VIEWS = "sales_and_traffic_report_by_date__trafficbyasin_pageviews"
FIELD_UNIT_SALES = "sales_and_traffic_report_by_date__salesbyasin_unitsordered"
FIELD_ORDERED_SALES = "sales_and_traffic_report_by_date__salesbyasin_orderedproductsales_amount"
FIELD_CURRENCY_CODE = "sales_and_traffic_report_by_date__salesbyasin_orderedproductsales_currencycode"

DEFAULT_TIMEOUT_SECONDS = 360
MIN_TIMEOUT_SECONDS = 300


class WindsorSection1IngestError(Exception):
    pass


def previous_full_week_chunks(weeks: int) -> list[tuple[date, date]]:
    """Return most-recent-first full Sunday-Saturday week windows."""
    if weeks <= 0:
        return []

    today_utc = datetime.now(timezone.utc).date()
    dow_sun0 = (today_utc.weekday() + 1) % 7
    current_week_start = today_utc - timedelta(days=dow_sun0)
    previous_week_end = current_week_start - timedelta(days=1)

    chunks: list[tuple[date, date]] = []
    for i in range(weeks):
        end = previous_week_end - timedelta(days=i * 7)
        start = end - timedelta(days=6)
        chunks.append((start, end))
    return chunks


class WindsorSection1IngestService:
    def __init__(self, db: Client) -> None:
        self.db = db
        self.api_key = os.getenv("WINDSOR_API_KEY", "").strip()
        self.seller_url = os.getenv("WINDSOR_SELLER_URL", "https://connectors.windsor.ai/amazon_sp").strip()
        configured_timeout = int(os.getenv("WBR_REQUEST_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
        self.timeout_seconds = max(configured_timeout, MIN_TIMEOUT_SECONDS)
        if not self.api_key:
            raise WindsorSection1IngestError("WINDSOR_API_KEY is not configured")
        if not self.seller_url:
            raise WindsorSection1IngestError("WINDSOR_SELLER_URL is not configured")

    async def ingest_range(
        self,
        *,
        client_id: str,
        account_id: str,
        date_from: date,
        date_to: date,
        initiated_by: str | None = None,
    ) -> dict[str, Any]:
        if date_from > date_to:
            raise WindsorSection1IngestError("date_from must be <= date_to")

        run_id = self._create_run(
            client_id=client_id,
            account_id=account_id,
            date_from=date_from,
            date_to=date_to,
            initiated_by=initiated_by,
        )

        try:
            raw_rows = await self._fetch_rows(account_id=account_id, date_from=date_from, date_to=date_to)
            normalized_rows = self._normalize_rows(
                rows=raw_rows,
                client_id=client_id,
                account_id=account_id,
            )
            mapping = self._load_mapping(client_id=client_id, account_id=account_id)
            daily_rows = self._aggregate_daily(rows=normalized_rows, asin_mapping=mapping)

            self._replace_raw_rows(
                run_id=run_id,
                client_id=client_id,
                account_id=account_id,
                date_from=date_from,
                date_to=date_to,
                rows=normalized_rows,
            )
            self._replace_daily_rows(
                client_id=client_id,
                account_id=account_id,
                date_from=date_from,
                date_to=date_to,
                rows=daily_rows,
            )

            self._finish_run(
                run_id=run_id,
                status="success",
                rows_fetched=len(raw_rows),
                rows_loaded=len(normalized_rows),
                error_message=None,
            )

            return {
                "ok": True,
                "run_id": run_id,
                "client_id": client_id,
                "account_id": account_id,
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
                "rows_fetched": len(raw_rows),
                "rows_loaded": len(normalized_rows),
                "daily_rows_loaded": len(daily_rows),
                "timeout_seconds": self.timeout_seconds,
            }
        except Exception as exc:  # noqa: BLE001
            self._finish_run(
                run_id=run_id,
                status="error",
                rows_fetched=0,
                rows_loaded=0,
                error_message=str(exc),
            )
            raise

    async def ingest_previous_full_weeks(
        self,
        *,
        client_id: str,
        account_id: str,
        weeks: int,
        initiated_by: str | None = None,
    ) -> dict[str, Any]:
        chunks = previous_full_week_chunks(weeks)
        chunk_results = []
        for start, end in chunks:
            result = await self.ingest_range(
                client_id=client_id,
                account_id=account_id,
                date_from=start,
                date_to=end,
                initiated_by=initiated_by,
            )
            chunk_results.append(result)

        return {
            "ok": True,
            "client_id": client_id,
            "account_id": account_id,
            "weeks": weeks,
            "chunks": [
                {"date_from": start.isoformat(), "date_to": end.isoformat()} for start, end in chunks
            ],
            "results": chunk_results,
        }

    async def _fetch_rows(self, *, account_id: str, date_from: date, date_to: date) -> list[dict[str, Any]]:
        base_params = {
            "api_key": self.api_key,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "fields": ",".join(WINDSOR_SECTION1_FIELDS),
        }
        account_id_norm = account_id.strip()
        attempts: list[tuple[str, dict[str, str], bool]] = [
            (
                "scoped_csv",
                {**base_params, "select_accounts": account_id_norm, "_renderer": "csv"},
                True,
            ),
            (
                "scoped_default_renderer",
                {**base_params, "select_accounts": account_id_norm},
                True,
            ),
            (
                "all_accounts_csv",
                {**base_params, "_renderer": "csv"},
                False,
            ),
            (
                "all_accounts_default_renderer",
                {**base_params},
                False,
            ),
        ]

        errors: list[str] = []
        for attempt_name, params, is_scoped in attempts:
            response = await self._request_windsor(params)
            if response.status_code < 400:
                rows = self._parse_response_rows(response)
                if not is_scoped:
                    rows = [
                        row for row in rows if str(row.get(FIELD_ACCOUNT_ID) or "").strip() == account_id_norm
                    ]
                return rows

            body_preview = response.text.strip().replace("\n", " ")[:220]
            errors.append(
                f"{attempt_name} -> {response.status_code} at {self._safe_request_url(params)} :: {body_preview}"
            )
            if response.status_code in (401, 403):
                break

        joined_errors = " | ".join(errors)
        raise WindsorSection1IngestError(f"Windsor request failed after retries: {joined_errors}")

    async def _request_windsor(self, params: dict[str, str]) -> httpx.Response:
        timeout = httpx.Timeout(timeout=self.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.get(self.seller_url, params=params)

    def _parse_response_rows(self, response: httpx.Response) -> list[dict[str, Any]]:
        body = response.text.strip()
        if not body:
            return []

        content_type = response.headers.get("content-type", "").lower()
        if "json" in content_type or body.startswith("[") or body.startswith("{"):
            try:
                payload = response.json()
            except Exception as exc:  # noqa: BLE001
                raise WindsorSection1IngestError(f"Failed to decode Windsor JSON: {exc}") from exc
            if isinstance(payload, list):
                return [row for row in payload if isinstance(row, dict)]
            if isinstance(payload, dict):
                data = payload.get("data")
                if isinstance(data, list):
                    return [row for row in data if isinstance(row, dict)]
                results = payload.get("results")
                if isinstance(results, list):
                    return [row for row in results if isinstance(row, dict)]
            raise WindsorSection1IngestError("Unexpected Windsor JSON payload shape")

        reader = csv.DictReader(io.StringIO(body))
        return [dict(row) for row in reader]

    def _normalize_rows(
        self,
        *,
        rows: list[dict[str, Any]],
        client_id: str,
        account_id: str,
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for row in rows:
            source_account = str(row.get(FIELD_ACCOUNT_ID) or account_id).strip()
            report_date_raw = str(row.get(FIELD_DATE) or "").strip()
            child_asin = str(row.get(FIELD_CHILD_ASIN) or "").strip()
            if not report_date_raw or not child_asin:
                continue
            try:
                report_date = date.fromisoformat(report_date_raw[:10])
            except ValueError:
                continue

            parent_asin = str(row.get(FIELD_PARENT_ASIN) or "").strip() or None
            marketplace_code = _derive_marketplace_code(source_account)
            currency_code = str(row.get(FIELD_CURRENCY_CODE) or "").strip() or _default_currency(marketplace_code)
            page_views = _safe_int(row.get(FIELD_PAGE_VIEWS))
            unit_sales = _safe_int(row.get(FIELD_UNIT_SALES))
            ordered_sales = round(_safe_float(row.get(FIELD_ORDERED_SALES)), 2)

            normalized.append(
                {
                    "client_id": client_id,
                    "account_id": source_account,
                    "marketplace_code": marketplace_code,
                    "report_date": report_date.isoformat(),
                    "child_asin": child_asin,
                    "parent_asin": parent_asin,
                    "currency_code": currency_code,
                    "page_views": page_views,
                    "unit_sales": unit_sales,
                    "ordered_sales": ordered_sales,
                    "source_payload": row,
                }
            )
        return normalized

    def _load_mapping(self, *, client_id: str, account_id: str) -> dict[str, str]:
        response = (
            self.db.table("wbr_asin_group_mapping")
            .select("child_asin,group_label")
            .eq("client_id", client_id)
            .eq("account_id", account_id)
            .eq("active", True)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        return {
            str(row.get("child_asin")): str(row.get("group_label"))
            for row in rows
            if row.get("child_asin") and row.get("group_label")
        }

    def _aggregate_daily(
        self,
        *,
        rows: list[dict[str, Any]],
        asin_mapping: dict[str, str],
    ) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str, str, str, str, str], dict[str, Any]] = {}
        for row in rows:
            group_label = asin_mapping.get(row["child_asin"], "UNMAPPED")
            key = (
                row["client_id"],
                row["account_id"],
                row["marketplace_code"],
                row["report_date"],
                group_label,
                row["currency_code"],
            )
            if key not in grouped:
                grouped[key] = {
                    "client_id": row["client_id"],
                    "account_id": row["account_id"],
                    "marketplace_code": row["marketplace_code"],
                    "report_date": row["report_date"],
                    "group_label": group_label,
                    "currency_code": row["currency_code"],
                    "page_views": 0,
                    "unit_sales": 0,
                    "sales": 0.0,
                    "source_row_count": 0,
                }
            grouped[key]["page_views"] += row["page_views"]
            grouped[key]["unit_sales"] += row["unit_sales"]
            grouped[key]["sales"] = round(grouped[key]["sales"] + row["ordered_sales"], 2)
            grouped[key]["source_row_count"] += 1

        return list(grouped.values())

    def _replace_raw_rows(
        self,
        *,
        run_id: str,
        client_id: str,
        account_id: str,
        date_from: date,
        date_to: date,
        rows: list[dict[str, Any]],
    ) -> None:
        (
            self.db.table("wbr_windsor_sales_traffic_raw")
            .delete()
            .eq("client_id", client_id)
            .eq("account_id", account_id)
            .gte("report_date", date_from.isoformat())
            .lte("report_date", date_to.isoformat())
            .execute()
        )
        if not rows:
            return

        insert_rows = []
        for row in rows:
            insert_rows.append(
                {
                    "ingest_run_id": run_id,
                    "client_id": row["client_id"],
                    "account_id": row["account_id"],
                    "marketplace_code": row["marketplace_code"],
                    "report_date": row["report_date"],
                    "child_asin": row["child_asin"],
                    "parent_asin": row["parent_asin"],
                    "currency_code": row["currency_code"],
                    "page_views": row["page_views"],
                    "unit_sales": row["unit_sales"],
                    "ordered_sales": row["ordered_sales"],
                    "source_payload": row["source_payload"],
                }
            )
        _insert_batches(self.db, "wbr_windsor_sales_traffic_raw", insert_rows)

    def _replace_daily_rows(
        self,
        *,
        client_id: str,
        account_id: str,
        date_from: date,
        date_to: date,
        rows: list[dict[str, Any]],
    ) -> None:
        (
            self.db.table("wbr_section1_daily")
            .delete()
            .eq("client_id", client_id)
            .eq("account_id", account_id)
            .gte("report_date", date_from.isoformat())
            .lte("report_date", date_to.isoformat())
            .execute()
        )
        if not rows:
            return
        _insert_batches(self.db, "wbr_section1_daily", rows)

    def _create_run(
        self,
        *,
        client_id: str,
        account_id: str,
        date_from: date,
        date_to: date,
        initiated_by: str | None,
    ) -> str:
        payload = {
            "source": "windsor",
            "report_preset": "get_sales_and_traffic_report_by_asin",
            "account_id": account_id,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "status": "running",
            "rows_fetched": 0,
            "rows_loaded": 0,
            "request_url": self.seller_url,
            "initiated_by": initiated_by,
            "meta": {
                "client_id": client_id,
                "fields": WINDSOR_SECTION1_FIELDS,
                "timeout_seconds": self.timeout_seconds,
            },
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        response = self.db.table("wbr_ingest_runs").insert(payload).execute()
        rows = response.data if isinstance(response.data, list) else []
        if not rows or not rows[0].get("id"):
            raise WindsorSection1IngestError("Failed to create WBR ingest run")
        return str(rows[0]["id"])

    def _finish_run(
        self,
        *,
        run_id: str,
        status: str,
        rows_fetched: int,
        rows_loaded: int,
        error_message: str | None,
    ) -> None:
        payload = {
            "status": status,
            "rows_fetched": rows_fetched,
            "rows_loaded": rows_loaded,
            "error_message": error_message,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        self.db.table("wbr_ingest_runs").update(payload).eq("id", run_id).execute()

    def _safe_request_url(self, params: dict[str, str]) -> str:
        safe_params = {**params, "api_key": "***"}
        return f"{self.seller_url}?{urlencode(safe_params)}"


def _derive_marketplace_code(account_id: str) -> str:
    parts = account_id.rsplit("-", 1)
    if len(parts) == 2 and parts[1]:
        return parts[1].upper()
    return "UNKNOWN"


def _default_currency(marketplace_code: str) -> str:
    marketplace = (marketplace_code or "").upper()
    if marketplace == "CA":
        return "CAD"
    if marketplace == "US":
        return "USD"
    return "UNKNOWN"


def _safe_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    try:
        return int(float(str(value).replace(",", "")))
    except (ValueError, TypeError):
        return 0


def _safe_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0


def _insert_batches(db: Client, table_name: str, rows: list[dict[str, Any]], batch_size: int = 500) -> None:
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        db.table(table_name).insert(batch).execute()
