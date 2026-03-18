"""WBR report snapshot persistence — create, list, and get snapshots.

Snapshots store a canonical digest (wbr_digest_v1) alongside optional raw
report data for reproducibility and downstream use (Claw, email drafts).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from supabase import Client

from .profiles import WBRNotFoundError, WBRValidationError
from .report_digest import DIGEST_VERSION, build_digest
from .section1_report import Section1ReportService
from .section2_report import Section2ReportService
from .section3_report import Section3ReportService


VALID_SNAPSHOT_KINDS = {"weekly_email", "manual", "claw_request"}


class WBRSnapshotService:
    def __init__(self, db: Client) -> None:
        self.db = db

    def _lookup_client_name(self, client_id: str | None) -> str | None:
        """Look up the agency client name for a wbr_profiles.client_id."""
        if not client_id:
            return None
        resp = (
            self.db.table("agency_clients")
            .select("name")
            .eq("id", client_id)
            .limit(1)
            .execute()
        )
        rows = resp.data if isinstance(resp.data, list) else []
        return rows[0]["name"] if rows else None

    def create_snapshot(
        self,
        profile_id: str,
        *,
        weeks: int = 4,
        snapshot_kind: str = "manual",
        include_raw: bool = False,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        """Build reports for all three sections, produce a digest, and persist."""
        if snapshot_kind not in VALID_SNAPSHOT_KINDS:
            raise WBRValidationError(
                f"Invalid snapshot_kind '{snapshot_kind}'. "
                f"Must be one of: {', '.join(sorted(VALID_SNAPSHOT_KINDS))}"
            )

        s1_svc = Section1ReportService(self.db)
        s2_svc = Section2ReportService(self.db)
        s3_svc = Section3ReportService(self.db)

        section1 = s1_svc.build_report(profile_id, weeks=weeks)
        section2 = s2_svc.build_report(profile_id, weeks=weeks)
        section3 = s3_svc.build_report(profile_id, weeks=weeks)

        # Enrich profile with agency client name so the digest gets the
        # real client identity, not just the WBR display_name fallback.
        profile = section1.get("profile") or {}
        client_name = self._lookup_client_name(profile.get("client_id"))
        if client_name:
            profile["client_name"] = client_name
            section1["profile"] = profile

        digest = build_digest(section1=section1, section2=section2, section3=section3)

        window = digest.get("window") or {}
        week_ending = window.get("week_ending")
        window_start = window.get("window_start")
        window_end = window.get("window_end")

        raw_report = None
        if include_raw:
            raw_report = {
                "section1": section1,
                "section2": section2,
                "section3": section3,
            }

        now = datetime.now(UTC).isoformat()

        row: dict[str, Any] = {
            "profile_id": profile_id,
            "snapshot_kind": snapshot_kind,
            "week_count": window.get("week_count", weeks),
            "week_ending": week_ending,
            "window_start": window_start or now[:10],
            "window_end": window_end or now[:10],
            "source_run_at": now,
            "digest_version": DIGEST_VERSION,
            "digest": digest,
        }

        if raw_report is not None:
            row["raw_report"] = raw_report

        if created_by:
            row["created_by"] = created_by

        response = self.db.table("wbr_report_snapshots").insert(row).execute()
        inserted = (response.data or [None])[0] if hasattr(response, "data") else None
        if not inserted:
            raise RuntimeError("Failed to persist WBR snapshot")

        return {
            "id": inserted.get("id"),
            "profile_id": profile_id,
            "snapshot_kind": snapshot_kind,
            "week_ending": week_ending,
            "window_start": window_start,
            "window_end": window_end,
            "digest_version": DIGEST_VERSION,
            "digest": digest,
            "created_at": inserted.get("created_at"),
        }

    def list_snapshots(
        self,
        profile_id: str,
        *,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Return recent snapshots for a profile (without full digest body)."""
        response = (
            self.db.table("wbr_report_snapshots")
            .select(
                "id, profile_id, snapshot_kind, week_count, week_ending, "
                "window_start, window_end, source_run_at, digest_version, created_at"
            )
            .eq("profile_id", profile_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        return rows

    def get_latest_snapshot(
        self,
        profile_id: str,
    ) -> dict[str, Any] | None:
        """Return the most recent snapshot for a profile, or None."""
        response = (
            self.db.table("wbr_report_snapshots")
            .select(
                "id, profile_id, snapshot_kind, week_count, week_ending, "
                "window_start, window_end, source_run_at, digest_version, "
                "digest, created_by, created_at"
            )
            .eq("profile_id", profile_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        return rows[0] if rows else None

    def get_or_create_snapshot(
        self,
        profile_id: str,
        *,
        weeks: int = 4,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        """Return the latest snapshot if one exists, otherwise create a fresh one."""
        latest = self.get_latest_snapshot(profile_id)
        if latest and latest.get("digest"):
            return latest
        result = self.create_snapshot(
            profile_id,
            weeks=weeks,
            snapshot_kind="claw_request",
            created_by=created_by,
        )
        return result

    def get_snapshot(
        self,
        profile_id: str,
        snapshot_id: str,
    ) -> dict[str, Any]:
        """Return a single snapshot with its full digest."""
        response = (
            self.db.table("wbr_report_snapshots")
            .select(
                "id, profile_id, snapshot_kind, week_count, week_ending, "
                "window_start, window_end, source_run_at, digest_version, "
                "digest, raw_report, created_by, created_at"
            )
            .eq("id", snapshot_id)
            .eq("profile_id", profile_id)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if not rows:
            raise WBRNotFoundError(f"Snapshot {snapshot_id} not found")
        return rows[0]
