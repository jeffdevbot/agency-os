"""Tests for WBR summary renderer, get_latest_snapshot, and skill registration."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.wbr.report_digest import DIGEST_VERSION
from app.services.wbr.wbr_summary_renderer import render_wbr_summary


# ---------------------------------------------------------------------------
# Shared digest fixture
# ---------------------------------------------------------------------------

def _make_digest(
    *,
    sales: float = 12450.0,
    sales_wow: float | None = 0.20,
    units: int = 1200,
    page_views: int = 55000,
    ad_spend: float = 1800.0,
    ad_sales: float = 7000.0,
    acos: float | None = 0.257,
    tacos: float | None = 0.15,
    wos: float | None = 6.5,
    return_rate: float | None = 0.033,
    wins: list[str] | None = None,
    concerns: list[str] | None = None,
    notes: list[str] | None = None,
) -> dict:
    return {
        "digest_version": DIGEST_VERSION,
        "profile": {
            "profile_id": "profile-1",
            "client_name": "Whoosh",
            "marketplace_code": "US",
            "display_name": "Whoosh US",
        },
        "window": {
            "week_count": 4,
            "window_start": "2026-02-16",
            "window_end": "2026-03-15",
            "week_labels": [
                "16-Feb to 22-Feb",
                "23-Feb to 01-Mar",
                "02-Mar to 08-Mar",
                "09-Mar to 15-Mar",
            ],
            "week_ending": "2026-03-15",
        },
        "headline_metrics": {
            "section1": {
                "total_sales": sales,
                "total_sales_wow": sales_wow,
                "total_unit_sales": units,
                "total_unit_sales_wow": 0.10,
                "total_page_views": page_views,
                "total_page_views_wow": 0.05,
            },
            "section2": {
                "total_ad_spend": ad_spend,
                "total_ad_spend_wow": -0.10,
                "total_ad_sales": ad_sales,
                "total_ad_sales_wow": 0.17,
                "acos": acos,
                "tacos": tacos,
                "ctr": 0.032,
                "cvr": 0.071,
                "total_impressions": 11000,
                "total_clicks": 350,
                "total_ad_orders": 25,
            },
            "section3": {
                "weeks_of_stock": wos,
                "return_rate": return_rate,
            },
        },
        "wins": wins if wins is not None else ["Sales up +20% WoW"],
        "concerns": concerns if concerns is not None else [],
        "data_quality_notes": notes if notes is not None else [],
        "section_summaries": {"section1": [], "section2": [], "section3": []},
    }


# ---------------------------------------------------------------------------
# Renderer tests
# ---------------------------------------------------------------------------


class TestRenderWbrSummary:
    def test_header_and_window(self):
        text = render_wbr_summary(_make_digest())
        assert "*WBR Summary — Whoosh US*" in text
        assert "Week ending 2026-03-15" in text
        assert "4-week window" in text

    def test_key_metrics_present(self):
        text = render_wbr_summary(_make_digest())
        assert "*Key Metrics*" in text
        assert "Sales: $12,450" in text
        assert "+20% WoW" in text
        assert "Units: 1,200" in text
        assert "Ad Spend: $1,800" in text
        assert "ACoS: 26%" in text
        assert "TACoS: 15%" in text
        assert "Weeks of Stock: 6.5" in text
        assert "Return Rate: 3%" in text

    def test_wins_section(self):
        text = render_wbr_summary(_make_digest(wins=["Sales up +20% WoW"]))
        assert "*Wins*" in text
        assert "• Sales up +20% WoW" in text

    def test_concerns_section(self):
        text = render_wbr_summary(_make_digest(concerns=["ACoS at 40%"]))
        assert "*Concerns*" in text
        assert "• ACoS at 40%" in text

    def test_data_notes_section(self):
        text = render_wbr_summary(_make_digest(notes=["Section 1: 3 unmapped ASINs"]))
        assert "*Data Notes*" in text
        assert "• Section 1: 3 unmapped ASINs" in text

    def test_empty_sections_omitted(self):
        text = render_wbr_summary(_make_digest(wins=[], concerns=[], notes=[]))
        assert "*Wins*" not in text
        assert "*Concerns*" not in text
        assert "*Data Notes*" not in text

    def test_null_metrics_omitted(self):
        text = render_wbr_summary(_make_digest(tacos=None, wos=None, return_rate=None))
        assert "TACoS" not in text
        assert "Weeks of Stock" not in text
        assert "Return Rate" not in text

    def test_display_name_fallback(self):
        digest = _make_digest()
        digest["profile"]["client_name"] = ""
        text = render_wbr_summary(digest)
        assert "*WBR Summary — Whoosh US*" in text

    def test_empty_digest(self):
        digest = {
            "digest_version": DIGEST_VERSION,
            "profile": {},
            "window": {},
            "headline_metrics": {"section1": {}, "section2": {}, "section3": {}},
            "wins": [],
            "concerns": [],
            "data_quality_notes": [],
            "section_summaries": {},
        }
        text = render_wbr_summary(digest)
        assert "*WBR Summary — Unknown*" in text
        assert "*Key Metrics*" not in text


# ---------------------------------------------------------------------------
# Fake Supabase for service tests
# ---------------------------------------------------------------------------


class _FakeTable:
    def __init__(self, rows: list[dict], parent=None):
        self._rows = rows
        self._filters_eq: dict = {}
        self._pending_op: str | None = None
        self._pending_data: dict | None = None
        self._order_col: str | None = None
        self._order_desc: bool = False
        self._limit_n: int | None = None
        self._parent = parent

    def select(self, *args, **kwargs):
        self._pending_op = "select"
        return self

    def eq(self, col, val):
        self._filters_eq[col] = val
        return self

    def order(self, col, *, desc=False):
        self._order_col = col
        self._order_desc = desc
        return self

    def limit(self, n):
        self._limit_n = n
        return self

    def range(self, start, end):
        return self

    def gte(self, col, val):
        return self

    def lte(self, col, val):
        return self

    def in_(self, col, vals):
        return self

    def filter(self, col, op, val):
        return self

    def insert(self, data):
        self._pending_op = "insert"
        self._pending_data = data
        return self

    def execute(self):
        if self._pending_op == "insert" and self._parent:
            row = {**self._pending_data, "id": "snap-new-1", "created_at": "2026-03-18T16:00:00Z"}
            self._parent.inserts.append(row)
            resp = MagicMock()
            resp.data = [row]
            return resp

        filtered = self._rows
        if self._filters_eq:
            filtered = [
                row for row in filtered
                if all(row.get(col) == val for col, val in self._filters_eq.items())
            ]
        if self._order_col and self._order_desc:
            filtered = sorted(filtered, key=lambda r: r.get(self._order_col, ""), reverse=True)
        if self._limit_n:
            filtered = filtered[:self._limit_n]
        resp = MagicMock()
        resp.data = filtered
        return resp


class _FakeSupabase:
    def __init__(self, tables: dict[str, list[dict]] | None = None):
        self._tables = {name: list(rows) for name, rows in (tables or {}).items()}
        self.inserts: list[dict] = []

    def table(self, name: str):
        rows = self._tables.get(name, [])
        return _FakeTable(rows, parent=self)


# ---------------------------------------------------------------------------
# get_latest_snapshot tests
# ---------------------------------------------------------------------------


class TestGetLatestSnapshot:
    def test_returns_latest_by_created_at(self):
        from app.services.wbr.report_snapshots import WBRSnapshotService

        fake_db = _FakeSupabase(tables={
            "wbr_report_snapshots": [
                {"id": "snap-old", "profile_id": "profile-1", "created_at": "2026-03-10T12:00:00Z",
                 "digest": {"digest_version": DIGEST_VERSION}},
                {"id": "snap-new", "profile_id": "profile-1", "created_at": "2026-03-18T12:00:00Z",
                 "digest": {"digest_version": DIGEST_VERSION}},
            ],
        })
        svc = WBRSnapshotService(fake_db)
        result = svc.get_latest_snapshot("profile-1")
        assert result is not None
        assert result["id"] == "snap-new"

    def test_returns_none_when_empty(self):
        from app.services.wbr.report_snapshots import WBRSnapshotService

        fake_db = _FakeSupabase(tables={"wbr_report_snapshots": []})
        svc = WBRSnapshotService(fake_db)
        result = svc.get_latest_snapshot("profile-1")
        assert result is None

    def test_filters_by_profile(self):
        from app.services.wbr.report_snapshots import WBRSnapshotService

        fake_db = _FakeSupabase(tables={
            "wbr_report_snapshots": [
                {"id": "snap-other", "profile_id": "profile-2", "created_at": "2026-03-18T12:00:00Z",
                 "digest": {"digest_version": DIGEST_VERSION}},
            ],
        })
        svc = WBRSnapshotService(fake_db)
        result = svc.get_latest_snapshot("profile-1")
        assert result is None


# ---------------------------------------------------------------------------
# get_or_create_snapshot tests
# ---------------------------------------------------------------------------


class TestGetOrCreateSnapshot:
    def test_returns_existing_when_available(self):
        from app.services.wbr.report_snapshots import WBRSnapshotService

        existing = {
            "id": "snap-1", "profile_id": "profile-1",
            "created_at": "2026-03-18T12:00:00Z",
            "digest": {"digest_version": DIGEST_VERSION, "profile": {"client_name": "Whoosh"}},
        }
        fake_db = _FakeSupabase(tables={"wbr_report_snapshots": [existing]})
        svc = WBRSnapshotService(fake_db)
        result = svc.get_or_create_snapshot("profile-1")
        assert result["id"] == "snap-1"
        assert len(fake_db.inserts) == 0  # no new snapshot created

    def test_rebuilds_when_newer_successful_sync_exists(self):
        from app.services.wbr.report_snapshots import WBRSnapshotService

        existing = {
            "id": "snap-1",
            "profile_id": "profile-1",
            "created_at": "2026-03-18T12:00:00Z",
            "source_run_at": "2026-03-18T12:00:00Z",
            "digest": {"digest_version": DIGEST_VERSION, "profile": {"client_name": "Whoosh"}},
        }
        profile = {
            "id": "profile-1",
            "client_id": "client-1",
            "display_name": "Whoosh US",
            "marketplace_code": "US",
            "week_start_day": "sunday",
        }
        fake_db = _FakeSupabase(
            tables={
                "wbr_report_snapshots": [existing],
                "wbr_sync_runs": [
                    {
                        "id": "run-1",
                        "profile_id": "profile-1",
                        "source_type": "amazon_ads",
                        "status": "success",
                        "finished_at": "2026-03-22T23:31:16Z",
                    }
                ],
                "wbr_profiles": [profile],
                "agency_clients": [{"id": "client-1", "name": "Whoosh"}],
                "wbr_rows": [],
                "wbr_asin_row_map": [],
                "wbr_business_asin_daily": [],
                "wbr_ads_campaign_daily": [],
                "wbr_inventory_asin_snapshots": [],
                "wbr_returns_asin_daily": [],
            }
        )
        svc = WBRSnapshotService(fake_db)

        result = svc.get_or_create_snapshot("profile-1")

        assert result["id"] == "snap-new-1"
        assert result["snapshot_kind"] == "claw_request"
        assert len(fake_db.inserts) == 1

    def test_creates_when_none_exists(self):
        from app.services.wbr.report_snapshots import WBRSnapshotService

        profile = {
            "id": "profile-1", "client_id": "client-1",
            "display_name": "Whoosh US", "marketplace_code": "US",
            "week_start_day": "sunday",
        }
        fake_db = _FakeSupabase(tables={
            "wbr_report_snapshots": [],
            "wbr_profiles": [profile],
            "agency_clients": [{"id": "client-1", "name": "Whoosh"}],
            "wbr_rows": [],
            "wbr_asin_row_map": [],
            "wbr_business_asin_daily": [],
            "wbr_ads_campaign_daily": [],
            "wbr_inventory_asin_snapshots": [],
            "wbr_returns_asin_daily": [],
        })
        svc = WBRSnapshotService(fake_db)
        result = svc.get_or_create_snapshot("profile-1")
        assert result["id"] == "snap-new-1"
        assert result["snapshot_kind"] == "claw_request"
        assert len(fake_db.inserts) == 1


# ---------------------------------------------------------------------------
# Skill registration test
# ---------------------------------------------------------------------------


class TestWbrSummarySkillRegistration:
    def test_skill_loads_from_disk(self):
        from app.services.theclaw.skill_registry import load_skills, get_skill_by_id

        skills = load_skills(force_reload=True)
        skill_ids = [s.skill_id for s in skills]
        assert "wbr_summary" in skill_ids

        skill = get_skill_by_id("wbr_summary")
        assert skill is not None
        assert skill.name == "WBR Summary"
        assert skill.primary_category == "wbr"
        assert "wbr" in skill.trigger_hints
        assert skill.system_prompt  # non-empty
