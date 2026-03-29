from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
from supabase import Client

from ..wbr.profiles import WBRNotFoundError
from .campaigns import build_campaign_items
from .parser import ASIN_RE
from .workbook import build_workbook

NATIVE_NGRAM_BATCH_SIZE = 1000
NATIVE_NGRAM_SELECT = "report_date,campaign_name,search_term,impressions,clicks,spend,orders,sales"


@dataclass(frozen=True)
class NativeNgramTotals:
    impressions: int
    clicks: int
    spend: float
    orders: int
    sales: float


@dataclass(frozen=True)
class NativeNgramWorkbookResult:
    workbook_path: str
    filename: str
    rows_processed: int
    campaigns_included: int
    campaigns_skipped: int
    ad_product: str


@dataclass(frozen=True)
class NativeNgramPreflightSummary:
    ad_product: str
    profile_id: str
    profile_display_name: str
    marketplace_code: str | None
    date_from: str
    date_to: str
    raw_rows: int
    eligible_rows: int
    excluded_asin_rows: int
    excluded_incomplete_rows: int
    unique_campaigns: int
    unique_search_terms: int
    campaigns_included: int
    campaigns_skipped: int
    report_dates_present: int
    coverage_start: str | None
    coverage_end: str | None
    imported_totals: NativeNgramTotals
    workbook_input_totals: NativeNgramTotals
    warnings: list[str]


class NativeNgramWorkbookService:
    def __init__(self, db: Client) -> None:
        self.db = db

    def build_workbook_from_search_term_facts(
        self,
        *,
        profile_id: str,
        ad_product: str,
        date_from: date,
        date_to: date,
        respect_legacy_exclusions: bool,
        app_version: str,
        ai_prefills: dict[str, dict[str, list[str]]] | None = None,
    ) -> NativeNgramWorkbookResult:
        normalized_ad_product = str(ad_product or "").strip().upper()
        if normalized_ad_product != "SPONSORED_PRODUCTS":
            raise ValueError("Native workbook generation is currently enabled for Sponsored Products only.")

        profile = self._get_profile(profile_id)
        rows = self._load_search_term_rows(
            profile_id=profile_id,
            ad_product=normalized_ad_product,
            date_from=date_from,
            date_to=date_to,
        )
        if not rows:
            raise ValueError("No native search-term facts found for the selected profile and date range.")

        prepared = self._prepare_rows(rows)
        df = self._build_dataframe(prepared.records)
        if df.empty:
            raise ValueError("No eligible native search terms remained after normalization.")

        build_result = build_campaign_items(
            df,
            respect_legacy_exclusions=respect_legacy_exclusions,
        )
        campaign_items = build_result.campaign_items
        skipped_campaigns = build_result.campaigns_skipped

        if not campaign_items:
            raise ValueError("No eligible campaigns remained after native filters were applied.")

        workbook_path = build_workbook(campaign_items, app_version, ai_prefills=ai_prefills)
        display_name = str(profile.get("display_name") or profile.get("marketplace_code") or "native_ngram").strip()
        safe_name = re.sub(r"[^A-Za-z0-9]+", "_", display_name).strip("_") or "native_ngram"
        filename = f"{safe_name}_{date_from.isoformat()}_{date_to.isoformat()}_native_ngrams.xlsx"

        return NativeNgramWorkbookResult(
            workbook_path=workbook_path,
            filename=filename,
            rows_processed=int(df.shape[0]),
            campaigns_included=len(campaign_items),
            campaigns_skipped=skipped_campaigns,
            ad_product=normalized_ad_product,
        )

    def build_summary_from_search_term_facts(
        self,
        *,
        profile_id: str,
        ad_product: str,
        date_from: date,
        date_to: date,
        respect_legacy_exclusions: bool,
    ) -> NativeNgramPreflightSummary:
        normalized_ad_product = str(ad_product or "").strip().upper()
        if normalized_ad_product != "SPONSORED_PRODUCTS":
            raise ValueError("Native preflight summary is currently enabled for Sponsored Products only.")

        profile = self._get_profile(profile_id)
        rows = self._load_search_term_rows(
            profile_id=profile_id,
            ad_product=normalized_ad_product,
            date_from=date_from,
            date_to=date_to,
        )
        prepared = self._prepare_rows(rows)
        df = self._build_dataframe(prepared.records)
        build_result = (
            build_campaign_items(df, respect_legacy_exclusions=respect_legacy_exclusions)
            if not df.empty
            else None
        )

        report_dates = sorted(
            {
                str(row.get("report_date") or "").strip()
                for row in rows
                if str(row.get("report_date") or "").strip()
            }
        )
        coverage_start = report_dates[0] if report_dates else None
        coverage_end = report_dates[-1] if report_dates else None

        warnings: list[str] = []
        if not rows:
            warnings.append("No native search-term facts were found for the selected profile and date range.")
        else:
            if coverage_start and coverage_start > date_from.isoformat():
                warnings.append(
                    f"Imported data starts on {coverage_start}, after the requested start date {date_from.isoformat()}."
                )
            if coverage_end and coverage_end < date_to.isoformat():
                warnings.append(
                    f"Imported data ends on {coverage_end}, before the requested end date {date_to.isoformat()}."
                )
            if not prepared.records:
                warnings.append("Imported rows exist, but none remain after removing blank terms and ASIN-only queries.")
            elif respect_legacy_exclusions and build_result and build_result.campaigns_skipped > 0:
                warnings.append(
                    f"{build_result.campaigns_skipped} campaign(s) will be skipped by the legacy Ex./SDI/SDV exclusions."
                )

        return NativeNgramPreflightSummary(
            ad_product=normalized_ad_product,
            profile_id=profile_id,
            profile_display_name=str(profile.get("display_name") or profile.get("marketplace_code") or "").strip(),
            marketplace_code=(
                str(profile.get("marketplace_code")).strip() if profile.get("marketplace_code") is not None else None
            ),
            date_from=date_from.isoformat(),
            date_to=date_to.isoformat(),
            raw_rows=len(rows),
            eligible_rows=int(df.shape[0]),
            excluded_asin_rows=prepared.excluded_asin_rows,
            excluded_incomplete_rows=prepared.excluded_incomplete_rows,
            unique_campaigns=int(df["Campaign Name"].nunique()) if not df.empty else 0,
            unique_search_terms=int(df["Query"].nunique()) if not df.empty else 0,
            campaigns_included=len(build_result.campaign_items) if build_result else 0,
            campaigns_skipped=build_result.campaigns_skipped if build_result else 0,
            report_dates_present=len(report_dates),
            coverage_start=coverage_start,
            coverage_end=coverage_end,
            imported_totals=self._compute_imported_totals(rows),
            workbook_input_totals=self._compute_dataframe_totals(df),
            warnings=warnings,
        )

    def _get_profile(self, profile_id: str) -> dict[str, Any]:
        response = self.db.table("wbr_profiles").select("id,display_name,marketplace_code,status").eq("id", profile_id).limit(1).execute()
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise WBRNotFoundError(f"Profile {profile_id} not found")
        return rows[0]

    def _load_search_term_rows(
        self,
        *,
        profile_id: str,
        ad_product: str,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0

        while True:
            response = (
                self.db.table("search_term_daily_facts")
                .select(NATIVE_NGRAM_SELECT)
                .eq("profile_id", profile_id)
                .eq("ad_product", ad_product)
                .gte("report_date", date_from.isoformat())
                .lte("report_date", date_to.isoformat())
                .range(offset, offset + NATIVE_NGRAM_BATCH_SIZE - 1)
                .execute()
            )
            batch = response.data if isinstance(response.data, list) else []
            rows.extend([row for row in batch if isinstance(row, dict)])
            if len(batch) < NATIVE_NGRAM_BATCH_SIZE:
                break
            offset += NATIVE_NGRAM_BATCH_SIZE

        return rows

    def _prepare_rows(self, rows: list[dict[str, Any]]) -> "_PreparedNativeRows":
        records: list[dict[str, Any]] = []
        excluded_asin_rows = 0
        excluded_incomplete_rows = 0

        for row in rows:
            query = str(row.get("search_term") or "").strip()
            campaign_name = str(row.get("campaign_name") or "").strip()
            if not query or not campaign_name:
                excluded_incomplete_rows += 1
                continue
            if ASIN_RE.match(query.lower()):
                excluded_asin_rows += 1
                continue
            records.append(
                {
                    "Campaign Name": campaign_name,
                    "Query": query,
                    "Impression": int(row.get("impressions") or 0),
                    "Click": int(row.get("clicks") or 0),
                    "Spend": float(row.get("spend") or 0),
                    "Order 14d": int(row.get("orders") or 0),
                    "Sales 14d": float(row.get("sales") or 0),
                }
            )

        return _PreparedNativeRows(
            records=records,
            excluded_asin_rows=excluded_asin_rows,
            excluded_incomplete_rows=excluded_incomplete_rows,
        )

    def _build_dataframe(self, records: list[dict[str, Any]]) -> pd.DataFrame:
        if not records:
            return pd.DataFrame(
                columns=["Campaign Name", "Query", "Impression", "Click", "Spend", "Order 14d", "Sales 14d"]
            )

        df = pd.DataFrame.from_records(records)
        grouped = (
            df.groupby(["Campaign Name", "Query"], as_index=False)[
                ["Impression", "Click", "Spend", "Order 14d", "Sales 14d"]
            ]
            .sum()
        )

        return grouped.sort_values(["Campaign Name", "Click", "Sales 14d"], ascending=[True, False, False]).reset_index(drop=True)

    def _compute_imported_totals(self, rows: list[dict[str, Any]]) -> NativeNgramTotals:
        return NativeNgramTotals(
            impressions=sum(int(row.get("impressions") or 0) for row in rows),
            clicks=sum(int(row.get("clicks") or 0) for row in rows),
            spend=round(sum(float(row.get("spend") or 0) for row in rows), 2),
            orders=sum(int(row.get("orders") or 0) for row in rows),
            sales=round(sum(float(row.get("sales") or 0) for row in rows), 2),
        )

    def _compute_dataframe_totals(self, df: pd.DataFrame) -> NativeNgramTotals:
        if df.empty:
            return NativeNgramTotals(impressions=0, clicks=0, spend=0.0, orders=0, sales=0.0)

        return NativeNgramTotals(
            impressions=int(df["Impression"].sum()),
            clicks=int(df["Click"].sum()),
            spend=round(float(df["Spend"].sum()), 2),
            orders=int(df["Order 14d"].sum()),
            sales=round(float(df["Sales 14d"].sum()), 2),
        )


@dataclass(frozen=True)
class _PreparedNativeRows:
    records: list[dict[str, Any]]
    excluded_asin_rows: int
    excluded_incomplete_rows: int
