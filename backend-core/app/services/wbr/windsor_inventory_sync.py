"""Windsor inventory sync – AFN inventory + restock recommendations feeds."""

from __future__ import annotations

import csv
import io
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import httpx
from supabase import Client

from .profiles import WBRNotFoundError, WBRValidationError

# ---------------------------------------------------------------------------
# AFN inventory feed fields
# ---------------------------------------------------------------------------
AFN_INVENTORY_FIELDS = [
    "account_id",
    "fba_myi_unsuppressed_inventory_data__asin",
    "fba_myi_unsuppressed_inventory_data__sku",
    "fba_myi_unsuppressed_inventory_data__afn_fulfillable_quantity",
    "fba_myi_unsuppressed_inventory_data__afn_inbound_working_quantity",
    "fba_myi_unsuppressed_inventory_data__afn_inbound_shipped_quantity",
    "fba_myi_unsuppressed_inventory_data__afn_inbound_receiving_quantity",
    "fba_myi_unsuppressed_inventory_data__afn_reserved_quantity",
    "fba_myi_unsuppressed_inventory_data__afn_reserved_future_supply",
    "fba_myi_unsuppressed_inventory_data__product_name",
]

# ---------------------------------------------------------------------------
# Restock recommendations feed fields
# ---------------------------------------------------------------------------
RESTOCK_FIELDS = [
    "account_id",
    "restock_inventory_recommendations_report__asin",
    "restock_inventory_recommendations_report__merchant_sku",
    "restock_inventory_recommendations_report__available",
    "restock_inventory_recommendations_report__working",
    "restock_inventory_recommendations_report__fc_transfer",
    "restock_inventory_recommendations_report__fc_processing",
    "restock_inventory_recommendations_report__receiving",
    "restock_inventory_recommendations_report__shipped",
    "restock_inventory_recommendations_report__inbound",
    "restock_inventory_recommendations_report__units_sold_last_30_days",
    "restock_inventory_recommendations_report__product_name",
    "restock_inventory_recommendations_report__condition",
    "restock_inventory_recommendations_report__fulfilled_by",
]

DEFAULT_TIMEOUT_SECONDS = 360
MIN_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class AggregatedInventoryFact:
    child_asin: str
    instock: int
    working: int
    reserved_quantity: int
    fc_transfer: int
    fc_processing: int
    reserved_plus_fc_transfer: int
    receiving: int
    intransit: int
    receiving_plus_intransit: int
    source_row_count: int
    source_payload: dict[str, Any]


def _clean_int(value: Any) -> int:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return 0
    try:
        return int(float(text))
    except (ValueError, TypeError):
        return 0


class WindsorInventorySyncService:
    def __init__(self, db: Client) -> None:
        self.db = db
        self.api_key = os.getenv("WINDSOR_API_KEY", "").strip()
        self.afn_url = os.getenv(
            "WINDSOR_AFN_INVENTORY_URL",
            "https://connectors.windsor.ai/amazon_sp",
        ).strip()
        self.restock_url = os.getenv(
            "WINDSOR_RESTOCK_URL",
            "https://connectors.windsor.ai/amazon_sp",
        ).strip()
        configured_timeout = int(os.getenv("WBR_REQUEST_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
        self.timeout_seconds = max(configured_timeout, MIN_TIMEOUT_SECONDS)

    async def refresh_inventory(
        self,
        *,
        profile_id: str,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        profile = self._get_profile(profile_id)
        account_id = self._require_windsor_account_id(profile)
        snapshot_date = datetime.now(UTC).date()

        run = self._create_sync_run(
            profile_id=profile_id,
            source_type="windsor_inventory",
            job_type="daily_refresh",
            date_from=snapshot_date,
            date_to=snapshot_date,
            request_meta={"account_id": account_id},
            user_id=user_id,
        )
        run_id = str(run["id"])

        afn_rows: list[dict[str, Any]] = []
        restock_rows: list[dict[str, Any]] = []

        try:
            afn_rows = await self._fetch_windsor(
                url=self.afn_url,
                account_id=account_id,
                fields=AFN_INVENTORY_FIELDS,
            )
            restock_rows = await self._fetch_windsor(
                url=self.restock_url,
                account_id=account_id,
                fields=RESTOCK_FIELDS,
            )

            facts, afn_only_asins = self._aggregate_inventory(
                afn_rows=afn_rows,
                restock_rows=restock_rows,
                expected_account_id=account_id,
            )

            self._replace_snapshot(
                profile_id=profile_id,
                sync_run_id=run_id,
                snapshot_date=snapshot_date,
                facts=facts,
            )

            total_raw = len(afn_rows) + len(restock_rows)
            finished = self._finalize_sync_run(
                run_id=run_id,
                status="success",
                rows_fetched=total_raw,
                rows_loaded=len(facts),
                error_message=None,
            )
            return {
                "run": finished,
                "rows_fetched": total_raw,
                "rows_loaded": len(facts),
                "snapshot_date": snapshot_date.isoformat(),
                "afn_only_asin_count": len(afn_only_asins),
                "afn_only_asins": afn_only_asins,
            }
        except Exception as exc:
            total_raw = len(afn_rows) + len(restock_rows)
            self._finalize_sync_run(
                run_id=run_id,
                status="error",
                rows_fetched=total_raw,
                rows_loaded=0,
                error_message=str(exc),
            )
            if isinstance(exc, (WBRValidationError, WBRNotFoundError)):
                raise
            raise WBRValidationError("Failed to sync Windsor inventory data") from exc

    def _aggregate_inventory(
        self,
        *,
        afn_rows: list[dict[str, Any]],
        restock_rows: list[dict[str, Any]],
        expected_account_id: str,
    ) -> tuple[list[AggregatedInventoryFact], list[str]]:
        # Build per-ASIN reserved quantity from AFN feed
        afn_reserved: dict[str, int] = {}
        afn_payloads: dict[str, list[dict[str, Any]]] = {}
        afn_counts: dict[str, int] = {}

        for row in afn_rows:
            acct = str(row.get("account_id") or expected_account_id).strip()
            if acct != expected_account_id:
                continue
            asin = str(
                row.get("fba_myi_unsuppressed_inventory_data__asin") or ""
            ).strip().upper()
            if not asin:
                continue
            reserved = _clean_int(
                row.get("fba_myi_unsuppressed_inventory_data__afn_reserved_quantity")
            )
            afn_reserved[asin] = afn_reserved.get(asin, 0) + reserved
            afn_payloads.setdefault(asin, []).append(row)
            afn_counts[asin] = afn_counts.get(asin, 0) + 1

        # Build per-ASIN restock quantities, filtering to condition=New
        restock_agg: dict[str, dict[str, int]] = {}
        restock_payloads: dict[str, list[dict[str, Any]]] = {}
        restock_counts: dict[str, int] = {}

        for row in restock_rows:
            acct = str(row.get("account_id") or expected_account_id).strip()
            if acct != expected_account_id:
                continue
            condition = str(
                row.get("restock_inventory_recommendations_report__condition") or ""
            ).strip()
            if condition and condition.lower() != "new":
                continue
            asin = str(
                row.get("restock_inventory_recommendations_report__asin") or ""
            ).strip().upper()
            if not asin:
                continue

            available = _clean_int(row.get("restock_inventory_recommendations_report__available"))
            working = _clean_int(row.get("restock_inventory_recommendations_report__working"))
            fc_transfer = _clean_int(row.get("restock_inventory_recommendations_report__fc_transfer"))
            fc_processing = _clean_int(row.get("restock_inventory_recommendations_report__fc_processing"))
            receiving = _clean_int(row.get("restock_inventory_recommendations_report__receiving"))
            shipped = _clean_int(row.get("restock_inventory_recommendations_report__shipped"))

            existing = restock_agg.get(asin)
            if existing is None:
                restock_agg[asin] = {
                    "available": available,
                    "working": working,
                    "fc_transfer": fc_transfer,
                    "fc_processing": fc_processing,
                    "receiving": receiving,
                    "shipped": shipped,
                }
            else:
                existing["available"] += available
                existing["working"] += working
                existing["fc_transfer"] += fc_transfer
                existing["fc_processing"] += fc_processing
                existing["receiving"] += receiving
                existing["shipped"] += shipped

            restock_payloads.setdefault(asin, []).append(row)
            restock_counts[asin] = restock_counts.get(asin, 0) + 1

        # ---- v1 inclusion rule ------------------------------------------------
        # Only emit facts for ASINs that have at least one New-condition restock
        # row.  AFN reserved is enriched onto those ASINs but is NOT sufficient
        # on its own to create a fact, because the AFN feed does not carry a
        # condition field — including AFN-only ASINs would risk inflating
        # Reserved + FC Transfer with non-New (Used / Refurbished) inventory.
        #
        # Known trade-off: if an ASIN has FBA reserved units but no restock
        # row at all (rare — usually means the ASIN was recently removed from
        # the restock recommendations), it will be excluded.  These ASINs are
        # tracked in `afn_only_asins` and surfaced in the sync run response so
        # operators can spot silent drops.
        # -------------------------------------------------------------------
        afn_only_asins = sorted(set(afn_reserved.keys()) - set(restock_agg.keys()))
        all_asins = sorted(restock_agg.keys())
        facts: list[AggregatedInventoryFact] = []

        for asin in all_asins:
            r = restock_agg.get(asin, {})
            instock = r.get("available", 0)
            working = r.get("working", 0)
            fc_transfer = r.get("fc_transfer", 0)
            fc_processing = r.get("fc_processing", 0)
            receiving = r.get("receiving", 0)
            intransit = r.get("shipped", 0)
            reserved_quantity = afn_reserved.get(asin, 0)

            reserved_plus_fc_transfer = reserved_quantity + fc_transfer + fc_processing
            receiving_plus_intransit = receiving + intransit

            source_count = afn_counts.get(asin, 0) + restock_counts.get(asin, 0)
            payload: dict[str, Any] = {}
            afn_p = afn_payloads.get(asin)
            restock_p = restock_payloads.get(asin)
            if afn_p:
                payload["afn_rows"] = afn_p
            if restock_p:
                payload["restock_rows"] = restock_p

            facts.append(
                AggregatedInventoryFact(
                    child_asin=asin,
                    instock=instock,
                    working=working,
                    reserved_quantity=reserved_quantity,
                    fc_transfer=fc_transfer,
                    fc_processing=fc_processing,
                    reserved_plus_fc_transfer=reserved_plus_fc_transfer,
                    receiving=receiving,
                    intransit=intransit,
                    receiving_plus_intransit=receiving_plus_intransit,
                    source_row_count=source_count,
                    source_payload=payload,
                )
            )

        return facts, afn_only_asins

    def _replace_snapshot(
        self,
        *,
        profile_id: str,
        sync_run_id: str,
        snapshot_date: date,
        facts: list[AggregatedInventoryFact],
    ) -> None:
        (
            self.db.table("wbr_inventory_asin_snapshots")
            .delete()
            .eq("profile_id", profile_id)
            .eq("snapshot_date", snapshot_date.isoformat())
            .execute()
        )

        if not facts:
            return

        payloads = [
            {
                "profile_id": profile_id,
                "sync_run_id": sync_run_id,
                "snapshot_date": snapshot_date.isoformat(),
                "child_asin": fact.child_asin,
                "instock": fact.instock,
                "working": fact.working,
                "reserved_quantity": fact.reserved_quantity,
                "fc_transfer": fact.fc_transfer,
                "fc_processing": fact.fc_processing,
                "reserved_plus_fc_transfer": fact.reserved_plus_fc_transfer,
                "receiving": fact.receiving,
                "intransit": fact.intransit,
                "receiving_plus_intransit": fact.receiving_plus_intransit,
                "source_row_count": fact.source_row_count,
                "source_payload": fact.source_payload,
            }
            for fact in facts
        ]

        for start in range(0, len(payloads), 500):
            chunk = payloads[start : start + 500]
            response = self.db.table("wbr_inventory_asin_snapshots").insert(chunk).execute()
            rows = response.data if isinstance(response.data, list) else []
            if len(rows) != len(chunk):
                raise WBRValidationError("Failed to store inventory snapshot facts")

    async def _fetch_windsor(
        self,
        *,
        url: str,
        account_id: str,
        fields: list[str],
    ) -> list[dict[str, Any]]:
        if not self.api_key:
            raise WBRValidationError("WINDSOR_API_KEY is not configured")

        params = {
            "api_key": self.api_key,
            "fields": ",".join(fields),
            "select_accounts": account_id,
        }

        timeout = httpx.Timeout(timeout=self.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, params=params)

        if response.status_code >= 400:
            body_preview = response.text.strip().replace("\n", " ")[:220]
            raise WBRValidationError(
                f"Windsor inventory request failed: {response.status_code} :: {body_preview}"
            )

        body = response.text.strip()
        if not body:
            return []

        content_type = response.headers.get("content-type", "").lower()
        if "json" in content_type or body.startswith("[") or body.startswith("{"):
            try:
                payload = response.json()
            except Exception as exc:
                raise WBRValidationError(f"Failed to decode Windsor inventory JSON: {exc}") from exc
            if isinstance(payload, list):
                return [row for row in payload if isinstance(row, dict)]
            if isinstance(payload, dict):
                for key in ("data", "results"):
                    value = payload.get(key)
                    if isinstance(value, list):
                        return [row for row in value if isinstance(row, dict)]
            raise WBRValidationError("Unexpected Windsor inventory payload shape")

        return [dict(row) for row in csv.DictReader(io.StringIO(body))]

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
