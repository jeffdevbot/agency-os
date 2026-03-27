from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
from supabase import Client

from ..wbr.profiles import WBRNotFoundError
from .analytics import build_ngram, derive_category
from .parser import ASIN_RE
from .workbook import build_workbook

NATIVE_NGRAM_BATCH_SIZE = 1000
NATIVE_NGRAM_SELECT = "campaign_name,search_term,impressions,clicks,spend,orders,sales"
LEGACY_EXCLUSION_MARKERS = ("Ex.", "SDI", "SDV")


@dataclass(frozen=True)
class NativeNgramWorkbookResult:
    workbook_path: str
    filename: str
    rows_processed: int
    campaigns_included: int
    campaigns_skipped: int
    ad_product: str


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

        df = self._build_dataframe(rows)
        if df.empty:
            raise ValueError("No eligible native search terms remained after normalization.")

        campaign_items: list[dict[str, Any]] = []
        skipped_campaigns = 0

        for camp, sub in df.groupby("Campaign Name"):
            cname = str(camp)
            if respect_legacy_exclusions and any(marker in cname for marker in LEGACY_EXCLUSION_MARKERS):
                skipped_campaigns += 1
                continue

            category_raw, category_key, cat_notes = derive_category(cname)
            mono = build_ngram(sub, 1)
            bi = build_ngram(sub, 2)
            tri = build_ngram(sub, 3)

            raw = sub.rename(columns={"Query": "Search Term"})[
                ["Search Term", "Impression", "Click", "Spend", "Order 14d", "Sales 14d"]
            ].copy()
            raw["NE/NP"] = ""
            raw["Comments"] = ""
            raw = raw.sort_values(["Click", "Sales 14d"], ascending=[False, False]).reset_index(drop=True)

            notes = list(cat_notes)
            if mono.empty:
                notes.append("Monogram table has no rows.")
            if bi.empty:
                notes.append("Bigram table has no rows.")
            if tri.empty:
                notes.append("Trigram table has no rows.")
            if raw.empty:
                notes.append("Search Term table has no rows.")

            campaign_items.append(
                {
                    "campaign_name": cname,
                    "category_raw": category_raw,
                    "category_key": category_key,
                    "mono": mono,
                    "bi": bi,
                    "tri": tri,
                    "raw": raw,
                    "notes": notes,
                }
            )

        if not campaign_items:
            raise ValueError("No eligible campaigns remained after native filters were applied.")

        workbook_path = build_workbook(campaign_items, app_version)
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

    def _build_dataframe(self, rows: list[dict[str, Any]]) -> pd.DataFrame:
        records: list[dict[str, Any]] = []
        for row in rows:
            query = str(row.get("search_term") or "").strip()
            campaign_name = str(row.get("campaign_name") or "").strip()
            if not query or not campaign_name:
                continue
            if ASIN_RE.match(query.lower()):
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
