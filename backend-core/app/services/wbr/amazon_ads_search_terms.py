from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .amazon_ads_sync import (
    AmazonAdsReportDefinition,
    AmazonAdsSyncService,
    WBRValidationError,
    _default_currency_code,
    _extract_first_present,
    _parse_decimal,
    _parse_int,
)


# ------------------------------------------------------------------
# Report definitions
#
# Only Sponsored Products (spSearchTerm) is active.
# The Amazon Ads v3 reporting API requires groupBy=["searchTerm"] for
# search-term reports — NOT "campaign" (which is correct for spCampaigns
# but is rejected for spSearchTerm with:
#   "configuration invalid groupBy values: (campaign). Allowed values: (searchTerm)").
#
# SB (sbSearchTerm) and SD (sdSearchTerm) search-term support is intentionally
# disabled here until their exact report contracts are verified:
#   - allowed groupBy values
#   - allowed columns
#   - retention window
#   - response field names
# Do not re-enable SB/SD without confirming the live API contract.
# ------------------------------------------------------------------

SEARCH_TERM_REPORT_DEFINITIONS: list[AmazonAdsReportDefinition] = [
    AmazonAdsReportDefinition(
        ad_product="SPONSORED_PRODUCTS",
        report_type_id="spSearchTerm",
        campaign_type="sponsored_products",
        group_by=["searchTerm"],
        columns=[
            "date",
            "campaignId",
            "campaignName",
            "adGroupId",
            "adGroupName",
            "keywordId",
            "keyword",
            "keywordType",
            "targeting",
            "searchTerm",
            "matchType",
            "impressions",
            "clicks",
            "cost",
            "purchases7d",
            "sales7d",
        ],
    ),
    # SB and SD search-term definitions are omitted here intentionally.
    # See comment above before re-enabling.
]

# Observed retention window for spSearchTerm reports (calendar days inclusive).
# This matches the live Amazon Ads API behaviour seen in testing.
STR_SP_OBSERVED_RETENTION_DAYS = 60


@dataclass(frozen=True)
class SearchTermDailyFact:
    report_date: date
    campaign_type: str
    campaign_id: str | None
    campaign_name: str
    campaign_name_head: str | None
    campaign_name_parts: list[str]
    ad_group_id: str | None
    ad_group_name: str | None
    keyword_id: str | None
    keyword: str | None
    keyword_type: str | None
    targeting: str | None
    search_term: str
    match_type: str | None
    impressions: int
    clicks: int
    spend: Decimal
    orders: int
    sales: Decimal
    currency_code: str | None
    source_payload: dict[str, Any]


class AmazonAdsSearchTermSyncService(AmazonAdsSyncService):
    source_type = "amazon_ads_search_terms"

    def list_sync_runs(self, profile_id: str, *, source_type: str = source_type) -> list[dict[str, Any]]:
        return super().list_sync_runs(profile_id, source_type=source_type)

    def _build_initial_report_jobs(self, *, queued_at: str) -> list[dict[str, Any]]:
        return [
            {
                "report_id": None,
                "status": "create_pending",
                "create_attempts": 0,
                "poll_attempts": 0,
                "next_poll_at": queued_at,
                "location": None,
                "status_detail": "queued_for_create",
                "campaign_type": definition.campaign_type,
                "ad_product": definition.ad_product,
                "report_type_id": definition.report_type_id,
                "group_by": definition.group_by,
                "columns": definition.columns,
            }
            for definition in SEARCH_TERM_REPORT_DEFINITIONS
        ]

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
        queued_at = datetime.now(UTC).isoformat()
        report_jobs = self._build_initial_report_jobs(queued_at=queued_at)
        run = self._create_sync_run(
            profile_id=profile_id,
            source_type=self.source_type,
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
                        "group_by": definition.group_by,
                        "columns": definition.columns,
                    }
                    for definition in SEARCH_TERM_REPORT_DEFINITIONS
                ],
                "async_reports_v1": True,
                "marketplace_code": marketplace_code,
                "report_jobs": report_jobs,
                "report_progress": self._build_report_progress(report_jobs),
                "queued_at": queued_at,
            },
            user_id=user_id,
        )
        run_id = str(run["id"])

        try:
            access_token = await self._refresh_access_token(refresh_token)
            report_jobs = await self._create_or_resume_report_jobs(
                access_token=access_token,
                amazon_ads_profile_id=amazon_ads_profile_id,
                report_jobs=report_jobs,
                date_from=date_from,
                date_to=date_to,
            )
            self._persist_report_jobs(run_id=run_id, report_jobs=report_jobs)
            failed_job = next(
                (
                    job
                    for job in report_jobs
                    if isinstance(job, dict) and str(job.get("status") or "") == "failed"
                ),
                None,
            )
            if failed_job is not None:
                finished = self._finalize_sync_run(
                    run_id=run_id,
                    status="error",
                    rows_fetched=0,
                    rows_loaded=0,
                    error_message=str(failed_job.get("error_message") or "Amazon Ads search-term report create failed"),
                )
                return {"run": finished, "rows_fetched": 0, "rows_loaded": 0}
            return {"run": self._get_sync_run(run_id), "rows_fetched": 0, "rows_loaded": 0}
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
            raise WBRValidationError("Failed to enqueue Amazon Ads search-term sync") from exc

    def _list_running_sync_runs(self, *, limit: int = 20) -> list[dict[str, Any]]:
        response = (
            self.db.table("wbr_sync_runs")
            .select("*")
            .eq("source_type", self.source_type)
            .eq("status", "running")
            .order("created_at")
            .limit(limit)
            .execute()
        )
        return response.data if isinstance(response.data, list) else []

    def _aggregate_rows(
        self,
        rows: list[dict[str, Any]],
        *,
        marketplace_code: str,
    ) -> list[SearchTermDailyFact]:
        # Dedup key includes keyword_id and targeting so that:
        #   - the same search term triggered by different keywords in the same
        #     campaign/ad group is stored as separate rows (keyword targeting)
        #   - auto-targeting rows (keyword_id=None) with different targeting
        #     expressions are also stored as separate rows
        # Both match Amazon report semantics for spSearchTerm.
        by_key: dict[
            tuple[date, str, str, str | None, str | None, str | None, str, str | None],
            SearchTermDailyFact,
        ] = {}

        for row in rows:
            date_text = self._extract_report_date_text(row)
            campaign_name = self._extract_campaign_name(row).strip()
            search_term = self._extract_search_term(row)
            if not date_text or not campaign_name or not search_term:
                continue

            try:
                report_date = self._parse_report_date(date_text)
            except ValueError as exc:
                raise WBRValidationError(f'Invalid Amazon Ads report date "{date_text}"') from exc

            campaign_type = str(row.get("__campaign_type") or "sponsored_products").strip() or "sponsored_products"
            campaign_id = self._extract_campaign_id(row)
            ad_group_id = self._extract_ad_group_id(row)
            ad_group_name = self._extract_ad_group_name(row)
            keyword_id = self._extract_keyword_id(row)
            keyword = self._extract_keyword(row)
            keyword_type = self._extract_keyword_type(row)
            targeting = self._extract_targeting(row)
            match_type = self._extract_match_type(row)
            currency_code = (
                str(
                    row.get("currencyCode")
                    or row.get("currency_code")
                    or self._nested_get(row, "accountInfo", "currencyCode")
                    or ""
                ).strip().upper()
                or None
            )
            currency_code = currency_code or _default_currency_code(marketplace_code)
            campaign_head, campaign_parts = self._parse_campaign_name_context(campaign_name)
            fact = SearchTermDailyFact(
                report_date=report_date,
                campaign_type=campaign_type,
                campaign_id=campaign_id,
                campaign_name=campaign_name,
                campaign_name_head=campaign_head,
                campaign_name_parts=campaign_parts,
                ad_group_id=ad_group_id,
                ad_group_name=ad_group_name,
                keyword_id=keyword_id,
                keyword=keyword,
                keyword_type=keyword_type,
                targeting=targeting,
                search_term=search_term,
                match_type=match_type,
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

            key = (
                report_date,
                campaign_type,
                campaign_name,
                ad_group_name,
                keyword_id,
                targeting,
                search_term,
                match_type,
            )
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = fact
                continue

            resolved_currency = existing.currency_code or fact.currency_code
            if existing.currency_code and fact.currency_code and existing.currency_code != fact.currency_code:
                raise WBRValidationError(
                    f"Multiple currency codes found for {campaign_name} / {search_term} on {report_date.isoformat()}"
                )

            existing_rows = existing.source_payload.get("source_rows")
            merged_payload: dict[str, Any] = {
                "source_rows": [
                    *(existing_rows if isinstance(existing_rows, list) else [existing.source_payload]),
                    row,
                ]
            }
            by_key[key] = SearchTermDailyFact(
                report_date=existing.report_date,
                campaign_type=existing.campaign_type,
                campaign_id=self._merge_optional_id(existing.campaign_id, fact.campaign_id),
                campaign_name=existing.campaign_name,
                campaign_name_head=existing.campaign_name_head,
                campaign_name_parts=existing.campaign_name_parts,
                ad_group_id=self._merge_optional_id(existing.ad_group_id, fact.ad_group_id),
                ad_group_name=self._merge_optional_text(existing.ad_group_name, fact.ad_group_name),
                keyword_id=self._merge_optional_id(existing.keyword_id, fact.keyword_id),
                keyword=self._merge_optional_text(existing.keyword, fact.keyword),
                keyword_type=self._merge_optional_text(existing.keyword_type, fact.keyword_type),
                targeting=self._merge_optional_text(existing.targeting, fact.targeting),
                search_term=existing.search_term,
                match_type=self._merge_optional_text(existing.match_type, fact.match_type),
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
            key=lambda item: (
                item.report_date,
                item.campaign_type,
                item.campaign_name.lower(),
                (item.ad_group_name or "").lower(),
                item.search_term.lower(),
            ),
        )

    def _replace_fact_window(
        self,
        *,
        profile_id: str,
        sync_run_id: str,
        date_from: date,
        date_to: date,
        facts: list[SearchTermDailyFact],
    ) -> None:
        (
            self.db.table("search_term_daily_facts")
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
                "campaign_type": fact.campaign_type,
                "campaign_id": fact.campaign_id,
                "campaign_name": fact.campaign_name,
                "campaign_name_head": fact.campaign_name_head,
                "campaign_name_parts": fact.campaign_name_parts,
                "ad_group_id": fact.ad_group_id,
                "ad_group_name": fact.ad_group_name,
                "keyword_id": fact.keyword_id,
                "keyword": fact.keyword,
                "keyword_type": fact.keyword_type,
                "targeting": fact.targeting,
                "search_term": fact.search_term,
                "match_type": fact.match_type,
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
            response = self.db.table("search_term_daily_facts").insert(chunk).execute()
            rows = response.data if isinstance(response.data, list) else []
            if len(rows) != len(chunk):
                raise WBRValidationError("Failed to store Amazon Ads search-term facts")

    async def _finalize_completed_run(
        self,
        run: dict[str, Any],
        request_meta: dict[str, Any],
        report_jobs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        run_id = str(run.get("id") or "").strip()
        profile_id = str(run.get("profile_id") or "").strip()
        if not run_id or not profile_id:
            raise WBRValidationError("Queued Amazon Ads search-term sync run is missing required ids")

        raw_rows: list[dict[str, Any]] = []
        for job in report_jobs:
            if not isinstance(job, dict):
                continue
            location = str(job.get("location") or "").strip()
            if not location:
                raise WBRValidationError(
                    f"Amazon Ads search-term report {job.get('report_id')} completed without a download location"
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

    # ------------------------------------------------------------------
    # Field extractors
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_search_term(row: dict[str, Any]) -> str:
        for value in (
            row.get("searchTerm"),
            row.get("customerSearchTerm"),
            row.get("customer_search_term"),
            row.get("query"),
            AmazonAdsSearchTermSyncService._nested_static_get(row, "dimensionValues", "searchTerm"),
            AmazonAdsSearchTermSyncService._nested_static_get(row, "dimensions", "searchTerm"),
            AmazonAdsSearchTermSyncService._nested_static_get(row, "dimensionValues", "query"),
            AmazonAdsSearchTermSyncService._nested_static_get(row, "dimensions", "query"),
        ):
            text = str(value or "").strip()
            if text:
                return text
        return ""

    @staticmethod
    def _extract_keyword_id(row: dict[str, Any]) -> str | None:
        for value in (
            row.get("keywordId"),
            row.get("keyword_id"),
            AmazonAdsSearchTermSyncService._nested_static_get(row, "dimensionValues", "keywordId"),
            AmazonAdsSearchTermSyncService._nested_static_get(row, "dimensions", "keywordId"),
        ):
            text = str(value or "").strip()
            if text:
                return text
        return None

    @staticmethod
    def _extract_keyword(row: dict[str, Any]) -> str | None:
        for value in (
            row.get("keyword"),
            row.get("keywordText"),
            AmazonAdsSearchTermSyncService._nested_static_get(row, "dimensionValues", "keyword"),
            AmazonAdsSearchTermSyncService._nested_static_get(row, "dimensions", "keyword"),
        ):
            text = str(value or "").strip()
            if text:
                return text
        return None

    @staticmethod
    def _extract_keyword_type(row: dict[str, Any]) -> str | None:
        for value in (
            row.get("keywordType"),
            row.get("keyword_type"),
            AmazonAdsSearchTermSyncService._nested_static_get(row, "dimensionValues", "keywordType"),
            AmazonAdsSearchTermSyncService._nested_static_get(row, "dimensions", "keywordType"),
        ):
            text = str(value or "").strip()
            if text:
                return text
        return None

    @staticmethod
    def _extract_targeting(row: dict[str, Any]) -> str | None:
        for value in (
            row.get("targeting"),
            row.get("targetingExpression"),
            row.get("resolvedTargetingExpression"),
            AmazonAdsSearchTermSyncService._nested_static_get(row, "dimensionValues", "targeting"),
            AmazonAdsSearchTermSyncService._nested_static_get(row, "dimensions", "targeting"),
        ):
            text = str(value or "").strip()
            if text:
                return text
        return None

    @staticmethod
    def _extract_ad_group_id(row: dict[str, Any]) -> str | None:
        for value in (
            row.get("adGroupId"),
            row.get("ad_group_id"),
            AmazonAdsSearchTermSyncService._nested_static_get(row, "adGroup", "adGroupId"),
            AmazonAdsSearchTermSyncService._nested_static_get(row, "adGroup", "id"),
            AmazonAdsSearchTermSyncService._nested_static_get(row, "dimensionValues", "adGroupId"),
            AmazonAdsSearchTermSyncService._nested_static_get(row, "dimensions", "adGroupId"),
        ):
            text = str(value or "").strip()
            if text:
                return text
        return None

    @staticmethod
    def _extract_ad_group_name(row: dict[str, Any]) -> str | None:
        for value in (
            row.get("adGroupName"),
            row.get("ad_group_name"),
            AmazonAdsSearchTermSyncService._nested_static_get(row, "adGroup", "adGroupName"),
            AmazonAdsSearchTermSyncService._nested_static_get(row, "adGroup", "name"),
            AmazonAdsSearchTermSyncService._nested_static_get(row, "dimensionValues", "adGroupName"),
            AmazonAdsSearchTermSyncService._nested_static_get(row, "dimensions", "adGroupName"),
        ):
            text = str(value or "").strip()
            if text:
                return text
        return None

    @staticmethod
    def _extract_match_type(row: dict[str, Any]) -> str | None:
        for value in (
            row.get("matchType"),
            row.get("match_type"),
            AmazonAdsSearchTermSyncService._nested_static_get(row, "dimensionValues", "matchType"),
            AmazonAdsSearchTermSyncService._nested_static_get(row, "dimensions", "matchType"),
        ):
            text = str(value or "").strip()
            if text:
                return text
        return None

    @staticmethod
    def _parse_campaign_name_context(campaign_name: str) -> tuple[str | None, list[str]]:
        parts = [part.strip() for part in re.split(r"\s*\|\s*", str(campaign_name or "").strip()) if part.strip()]
        if not parts:
            return None, []
        return parts[0], parts

    @staticmethod
    def _merge_optional_id(existing: str | None, incoming: str | None) -> str | None:
        if existing and incoming and existing != incoming:
            return None
        return existing or incoming

    @staticmethod
    def _merge_optional_text(existing: str | None, incoming: str | None) -> str | None:
        if existing and incoming and existing != incoming:
            return None
        return existing or incoming

    @staticmethod
    def _nested_static_get(value: Any, *path: str) -> Any:
        current = value
        for key in path:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
        return current

    async def _refresh_access_token(self, refresh_token: str) -> str:
        from .amazon_ads_auth import refresh_access_token

        return await refresh_access_token(refresh_token)
