"""Tests for WBR report digest and snapshot services + endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import wbr
from app.services.wbr.report_digest import DIGEST_VERSION, build_digest


# ---------------------------------------------------------------------------
# Shared test data builders
# ---------------------------------------------------------------------------

_PROFILE = {
    "id": "profile-1",
    "client_id": "client-1",
    "client_name": "Whoosh",
    "display_name": "Whoosh US",
    "marketplace_code": "US",
    "week_start_day": "sunday",
}

_WEEKS = [
    {"start": "2026-03-02", "end": "2026-03-08", "label": "02-Mar to 08-Mar"},
    {"start": "2026-03-09", "end": "2026-03-15", "label": "09-Mar to 15-Mar"},
]


def _make_section1(
    *,
    profile: dict | None = None,
    weeks: list | None = None,
    sales: tuple[float, float] = (1000.0, 1200.0),
    units: tuple[int, int] = (100, 120),
    page_views: tuple[int, int] = (5000, 5500),
) -> dict:
    return {
        "profile": profile or _PROFILE,
        "weeks": weeks or _WEEKS,
        "rows": [
            {
                "id": "row-1",
                "row_label": "Product Line A",
                "row_kind": "parent",
                "parent_row_id": None,
                "sort_order": 1,
                "weeks": [
                    {"page_views": page_views[0], "unit_sales": units[0], "sales": str(sales[0]), "conversion_rate": 0.02},
                    {"page_views": page_views[1], "unit_sales": units[1], "sales": str(sales[1]), "conversion_rate": 0.022},
                ],
            },
        ],
        "qa": {
            "active_row_count": 1,
            "mapped_asin_count": 5,
            "unmapped_asin_count": 0,
            "unmapped_fact_rows": 0,
            "fact_row_count": 50,
        },
    }


def _make_section2(
    *,
    spend: tuple[float, float] = (200.0, 180.0),
    ad_sales: tuple[float, float] = (600.0, 700.0),
) -> dict:
    return {
        "profile": _PROFILE,
        "weeks": _WEEKS,
        "rows": [
            {
                "id": "row-1",
                "row_label": "Product Line A",
                "row_kind": "parent",
                "parent_row_id": None,
                "sort_order": 1,
                "weeks": [
                    {
                        "impressions": 10000,
                        "clicks": 300,
                        "ctr_pct": 0.03,
                        "ad_spend": str(spend[0]),
                        "cpc": "0.67",
                        "ad_orders": 20,
                        "ad_conversion_rate": 0.067,
                        "ad_sales": str(ad_sales[0]),
                        "acos_pct": 0.333,
                        "business_sales": "1000.00",
                        "tacos_pct": 0.20,
                        "tacos_available": True,
                    },
                    {
                        "impressions": 11000,
                        "clicks": 350,
                        "ctr_pct": 0.032,
                        "ad_spend": str(spend[1]),
                        "cpc": "0.51",
                        "ad_orders": 25,
                        "ad_conversion_rate": 0.071,
                        "ad_sales": str(ad_sales[1]),
                        "acos_pct": 0.257,
                        "business_sales": "1200.00",
                        "tacos_pct": 0.15,
                        "tacos_available": True,
                    },
                ],
            },
        ],
        "qa": {
            "active_row_count": 1,
            "mapped_campaign_count": 10,
            "unmapped_campaign_count": 0,
            "unmapped_campaign_samples": [],
            "unmapped_fact_rows": 0,
            "fact_row_count": 70,
        },
    }


def _make_section3() -> dict:
    return {
        "profile": _PROFILE,
        "weeks": _WEEKS,
        "rows": [
            {
                "id": "row-1",
                "row_label": "Product Line A",
                "row_kind": "parent",
                "parent_row_id": None,
                "sort_order": 1,
                "instock": 500,
                "working": 10,
                "reserved_plus_fc_transfer": 50,
                "receiving_plus_intransit": 100,
                "weeks_of_stock": 6.5,
                "returns_week_1": 5,
                "returns_week_2": 3,
                "return_rate": 0.033,
                "_unit_sales_4w": 400,
                "_unit_sales_2w": 200,
            },
        ],
        "returns_weeks": [
            {"start": "2026-03-02", "end": "2026-03-08", "label": "02-Mar to 08-Mar"},
            {"start": "2026-03-09", "end": "2026-03-15", "label": "09-Mar to 15-Mar"},
        ],
        "totals": {
            "weeks_of_stock": 6.5,
            "return_rate": 0.033,
        },
        "qa": {
            "active_row_count": 1,
            "mapped_asin_count": 5,
            "unmapped_inventory_asin_count": 0,
            "inventory_fact_count": 5,
            "returns_fact_count": 8,
            "business_fact_count": 50,
        },
    }


# ---------------------------------------------------------------------------
# Digest unit tests
# ---------------------------------------------------------------------------


class TestBuildDigest:
    def test_digest_version_and_profile(self):
        digest = build_digest(
            section1=_make_section1(),
            section2=_make_section2(),
            section3=_make_section3(),
        )
        assert digest["digest_version"] == DIGEST_VERSION
        assert digest["profile"]["profile_id"] == "profile-1"
        assert digest["profile"]["marketplace_code"] == "US"
        assert digest["profile"]["display_name"] == "Whoosh US"

    def test_window_structure(self):
        digest = build_digest(
            section1=_make_section1(),
            section2=_make_section2(),
            section3=_make_section3(),
        )
        window = digest["window"]
        assert window["week_count"] == 2
        assert window["window_start"] == "2026-03-02"
        assert window["window_end"] == "2026-03-15"
        assert window["week_ending"] == "2026-03-15"
        assert len(window["week_labels"]) == 2

    def test_section1_headline_metrics(self):
        digest = build_digest(
            section1=_make_section1(sales=(1000.0, 1200.0), units=(100, 120)),
            section2=_make_section2(),
            section3=_make_section3(),
        )
        s1 = digest["headline_metrics"]["section1"]
        assert s1["total_sales"] == 1200.0
        assert s1["total_unit_sales"] == 120
        # +20% WoW
        assert s1["total_sales_wow"] == 0.2

    def test_section2_headline_metrics(self):
        digest = build_digest(
            section1=_make_section1(),
            section2=_make_section2(spend=(200.0, 180.0), ad_sales=(600.0, 700.0)),
            section3=_make_section3(),
        )
        s2 = digest["headline_metrics"]["section2"]
        assert s2["total_ad_spend"] == 180.0
        assert s2["total_ad_sales"] == 700.0
        assert s2["acos"] is not None

    def test_section3_headline_metrics(self):
        digest = build_digest(
            section1=_make_section1(),
            section2=_make_section2(),
            section3=_make_section3(),
        )
        s3 = digest["headline_metrics"]["section3"]
        assert s3["weeks_of_stock"] == 6.5
        assert s3["return_rate"] == 0.033

    def test_wins_and_concerns(self):
        # Sales up 20% should generate a win
        digest = build_digest(
            section1=_make_section1(sales=(1000.0, 1200.0)),
            section2=_make_section2(),
            section3=_make_section3(),
        )
        assert any("Sales up" in w for w in digest["wins"])

    def test_concern_for_low_stock(self):
        s3 = _make_section3()
        s3["totals"]["weeks_of_stock"] = 2.0
        s3["rows"][0]["weeks_of_stock"] = 2.0
        digest = build_digest(
            section1=_make_section1(),
            section2=_make_section2(),
            section3=s3,
        )
        assert any("Low stock" in c for c in digest["concerns"])

    def test_data_quality_notes_empty_when_clean(self):
        digest = build_digest(
            section1=_make_section1(),
            section2=_make_section2(),
            section3=_make_section3(),
        )
        assert digest["data_quality_notes"] == []

    def test_data_quality_notes_when_unmapped(self):
        s1 = _make_section1()
        s1["qa"]["unmapped_asin_count"] = 3
        s1["qa"]["unmapped_fact_rows"] = 15
        digest = build_digest(
            section1=s1,
            section2=_make_section2(),
            section3=_make_section3(),
        )
        assert len(digest["data_quality_notes"]) == 1
        assert "3 unmapped ASIN" in digest["data_quality_notes"][0]

    def test_section_summaries_structure(self):
        digest = build_digest(
            section1=_make_section1(),
            section2=_make_section2(),
            section3=_make_section3(),
        )
        s1_summaries = digest["section_summaries"]["section1"]
        assert len(s1_summaries) == 1
        assert s1_summaries[0]["label"] == "Product Line A"
        assert "latest_week" in s1_summaries[0]

        s3_summaries = digest["section_summaries"]["section3"]
        assert len(s3_summaries) == 1
        assert s3_summaries[0]["instock"] == 500
        assert s3_summaries[0]["weeks_of_stock"] == 6.5

    def test_empty_report_produces_valid_digest(self):
        empty = {
            "profile": _PROFILE,
            "weeks": [],
            "rows": [],
            "qa": {"active_row_count": 0, "mapped_asin_count": 0, "unmapped_asin_count": 0, "unmapped_fact_rows": 0, "fact_row_count": 0},
        }
        empty_s3 = {**empty, "totals": {}, "returns_weeks": []}
        digest = build_digest(section1=empty, section2=empty, section3=empty_s3)
        assert digest["digest_version"] == DIGEST_VERSION
        assert digest["window"]["week_count"] == 0
        assert digest["headline_metrics"]["section1"]["total_sales"] == 0.0

    def test_digest_top_level_keys(self):
        digest = build_digest(
            section1=_make_section1(),
            section2=_make_section2(),
            section3=_make_section3(),
        )
        expected_keys = {
            "digest_version", "profile", "window", "headline_metrics",
            "wins", "concerns", "data_quality_notes", "section_summaries",
        }
        assert set(digest.keys()) == expected_keys


# ---------------------------------------------------------------------------
# Fake Supabase for snapshot service tests
# ---------------------------------------------------------------------------


class _FakeTable:
    def __init__(self, rows: list[dict], parent: _FakeSupabase | None = None):
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
# Snapshot service unit tests
# ---------------------------------------------------------------------------


class TestSnapshotService:
    def _make_fake_db(self):
        """Shared fake DB with agency_clients table for snapshot service tests."""
        # Use a profile without client_name to match real wbr_profiles shape
        real_profile = {
            "id": "profile-1",
            "client_id": "client-1",
            "display_name": "Whoosh US",
            "marketplace_code": "US",
            "week_start_day": "sunday",
        }
        return _FakeSupabase(tables={
            "wbr_profiles": [real_profile],
            "agency_clients": [{"id": "client-1", "name": "Whoosh"}],
            "wbr_rows": [],
            "wbr_asin_row_map": [],
            "wbr_business_asin_daily": [],
            "wbr_ads_campaign_daily": [],
            "wbr_inventory_asin_snapshots": [],
            "wbr_returns_asin_daily": [],
            "wbr_report_snapshots": [],
        })

    def test_create_snapshot_builds_digest(self, monkeypatch):
        from app.services.wbr.report_snapshots import WBRSnapshotService

        fake_db = self._make_fake_db()

        svc = WBRSnapshotService(fake_db)
        result = svc.create_snapshot("profile-1", weeks=4, snapshot_kind="manual")

        assert result["id"] == "snap-new-1"
        assert result["digest_version"] == DIGEST_VERSION
        assert result["digest"]["digest_version"] == DIGEST_VERSION
        assert result["digest"]["profile"]["profile_id"] == "profile-1"
        assert len(fake_db.inserts) == 1

    def test_create_snapshot_enriches_client_name(self):
        from app.services.wbr.report_snapshots import WBRSnapshotService

        fake_db = self._make_fake_db()
        svc = WBRSnapshotService(fake_db)
        result = svc.create_snapshot("profile-1", weeks=4, snapshot_kind="manual")

        # client_name should come from agency_clients.name, not display_name
        assert result["digest"]["profile"]["client_name"] == "Whoosh"
        assert result["digest"]["profile"]["display_name"] == "Whoosh US"

    def test_create_snapshot_invalid_kind_raises(self):
        from app.services.wbr.report_snapshots import WBRSnapshotService
        from app.services.wbr.profiles import WBRValidationError

        fake_db = self._make_fake_db()
        svc = WBRSnapshotService(fake_db)
        with pytest.raises(WBRValidationError, match="Invalid snapshot_kind"):
            svc.create_snapshot("profile-1", snapshot_kind="bogus")

    def test_list_snapshots(self):
        from app.services.wbr.report_snapshots import WBRSnapshotService

        fake_db = _FakeSupabase(tables={
            "wbr_report_snapshots": [
                {"id": "snap-1", "profile_id": "profile-1", "snapshot_kind": "manual",
                 "week_count": 4, "week_ending": "2026-03-15", "window_start": "2026-02-16",
                 "window_end": "2026-03-15", "source_run_at": "2026-03-18T12:00:00Z",
                 "digest_version": DIGEST_VERSION, "created_at": "2026-03-18T12:00:00Z"},
                {"id": "snap-2", "profile_id": "profile-2", "snapshot_kind": "manual",
                 "week_count": 4, "week_ending": "2026-03-15", "window_start": "2026-02-16",
                 "window_end": "2026-03-15", "source_run_at": "2026-03-18T12:00:00Z",
                 "digest_version": DIGEST_VERSION, "created_at": "2026-03-18T12:00:00Z"},
            ],
        })

        svc = WBRSnapshotService(fake_db)
        results = svc.list_snapshots("profile-1")
        assert len(results) == 1
        assert results[0]["id"] == "snap-1"

    def test_get_snapshot(self):
        from app.services.wbr.report_snapshots import WBRSnapshotService

        fake_db = _FakeSupabase(tables={
            "wbr_report_snapshots": [
                {"id": "snap-1", "profile_id": "profile-1", "snapshot_kind": "manual",
                 "week_count": 4, "week_ending": "2026-03-15", "digest": {"digest_version": DIGEST_VERSION},
                 "raw_report": None,
                 "window_start": "2026-02-16", "window_end": "2026-03-15",
                 "source_run_at": "2026-03-18T12:00:00Z", "digest_version": DIGEST_VERSION,
                 "created_by": None, "created_at": "2026-03-18T12:00:00Z"},
            ],
        })

        svc = WBRSnapshotService(fake_db)
        result = svc.get_snapshot("profile-1", "snap-1")
        assert result["id"] == "snap-1"
        assert result["digest"]["digest_version"] == DIGEST_VERSION

    def test_get_snapshot_returns_raw_report_when_present(self):
        from app.services.wbr.report_snapshots import WBRSnapshotService

        raw = {"section1": {"rows": []}, "section2": {"rows": []}, "section3": {"rows": []}}
        fake_db = _FakeSupabase(tables={
            "wbr_report_snapshots": [
                {"id": "snap-1", "profile_id": "profile-1", "snapshot_kind": "manual",
                 "week_count": 4, "week_ending": "2026-03-15",
                 "digest": {"digest_version": DIGEST_VERSION},
                 "raw_report": raw,
                 "window_start": "2026-02-16", "window_end": "2026-03-15",
                 "source_run_at": "2026-03-18T12:00:00Z", "digest_version": DIGEST_VERSION,
                 "created_by": None, "created_at": "2026-03-18T12:00:00Z"},
            ],
        })

        svc = WBRSnapshotService(fake_db)
        result = svc.get_snapshot("profile-1", "snap-1")
        assert result["raw_report"] is not None
        assert "section1" in result["raw_report"]

    def test_get_snapshot_not_found(self):
        from app.services.wbr.report_snapshots import WBRSnapshotService
        from app.services.wbr.profiles import WBRNotFoundError

        fake_db = _FakeSupabase(tables={"wbr_report_snapshots": []})
        svc = WBRSnapshotService(fake_db)
        with pytest.raises(WBRNotFoundError):
            svc.get_snapshot("profile-1", "nonexistent")


# ---------------------------------------------------------------------------
# Router endpoint tests
# ---------------------------------------------------------------------------


def _override_admin():
    return {"sub": "user-123"}


class _FakeSnapshotService:
    def __init__(self):
        self.create_calls: list[dict] = []
        self.list_calls: list[dict] = []
        self.get_calls: list[dict] = []

    def create_snapshot(self, profile_id, *, weeks=4, snapshot_kind="manual", include_raw=False, created_by=None):
        from app.services.wbr.report_snapshots import VALID_SNAPSHOT_KINDS
        from app.services.wbr.profiles import WBRValidationError
        if snapshot_kind not in VALID_SNAPSHOT_KINDS:
            raise WBRValidationError(
                f"Invalid snapshot_kind '{snapshot_kind}'. "
                f"Must be one of: {', '.join(sorted(VALID_SNAPSHOT_KINDS))}"
            )
        self.create_calls.append({
            "profile_id": profile_id, "weeks": weeks,
            "snapshot_kind": snapshot_kind, "include_raw": include_raw,
        })
        return {
            "id": "snap-new-1",
            "profile_id": profile_id,
            "snapshot_kind": snapshot_kind,
            "week_ending": "2026-03-15",
            "window_start": "2026-02-16",
            "window_end": "2026-03-15",
            "digest_version": DIGEST_VERSION,
            "digest": {"digest_version": DIGEST_VERSION, "profile": {}},
            "created_at": "2026-03-18T16:00:00Z",
        }

    def list_snapshots(self, profile_id, *, limit=10):
        self.list_calls.append({"profile_id": profile_id, "limit": limit})
        return [
            {"id": "snap-1", "profile_id": profile_id, "snapshot_kind": "manual",
             "week_count": 4, "week_ending": "2026-03-15", "created_at": "2026-03-18T12:00:00Z"},
        ]

    def get_snapshot(self, profile_id, snapshot_id):
        self.get_calls.append({"profile_id": profile_id, "snapshot_id": snapshot_id})
        if snapshot_id == "nonexistent":
            from app.services.wbr.profiles import WBRNotFoundError
            raise WBRNotFoundError("Snapshot nonexistent not found")
        return {
            "id": snapshot_id,
            "profile_id": profile_id,
            "digest": {"digest_version": DIGEST_VERSION},
            "created_at": "2026-03-18T12:00:00Z",
        }


class TestSnapshotEndpoints:
    def _setup(self, monkeypatch):
        fake = _FakeSnapshotService()
        monkeypatch.setattr(wbr, "_get_snapshot_service", lambda: fake)
        app.dependency_overrides[wbr.require_admin_user] = _override_admin
        return fake

    def _teardown(self):
        app.dependency_overrides.pop(wbr.require_admin_user, None)

    def test_create_snapshot(self, monkeypatch):
        fake = self._setup(monkeypatch)
        try:
            with TestClient(app) as client:
                resp = client.post(
                    "/admin/wbr/profiles/profile-1/snapshots",
                    json={"weeks": 4, "snapshot_kind": "weekly_email"},
                )
            assert resp.status_code == 200
            body = resp.json()
            assert body["ok"] is True
            assert body["snapshot"]["id"] == "snap-new-1"
            assert body["snapshot"]["digest_version"] == DIGEST_VERSION
            assert fake.create_calls[0]["snapshot_kind"] == "weekly_email"
        finally:
            self._teardown()

    def test_list_snapshots(self, monkeypatch):
        fake = self._setup(monkeypatch)
        try:
            with TestClient(app) as client:
                resp = client.get("/admin/wbr/profiles/profile-1/snapshots")
            assert resp.status_code == 200
            body = resp.json()
            assert body["ok"] is True
            assert len(body["snapshots"]) == 1
            assert fake.list_calls[0]["profile_id"] == "profile-1"
        finally:
            self._teardown()

    def test_get_snapshot(self, monkeypatch):
        fake = self._setup(monkeypatch)
        try:
            with TestClient(app) as client:
                resp = client.get("/admin/wbr/profiles/profile-1/snapshots/snap-1")
            assert resp.status_code == 200
            body = resp.json()
            assert body["ok"] is True
            assert body["snapshot"]["id"] == "snap-1"
        finally:
            self._teardown()

    def test_get_snapshot_not_found(self, monkeypatch):
        self._setup(monkeypatch)
        try:
            with TestClient(app) as client:
                resp = client.get("/admin/wbr/profiles/profile-1/snapshots/nonexistent")
            assert resp.status_code == 404
        finally:
            self._teardown()

    def test_create_snapshot_invalid_kind_returns_400(self, monkeypatch):
        self._setup(monkeypatch)
        try:
            with TestClient(app) as client:
                resp = client.post(
                    "/admin/wbr/profiles/profile-1/snapshots",
                    json={"weeks": 4, "snapshot_kind": "bogus"},
                )
            assert resp.status_code == 400
            assert "Invalid snapshot_kind" in resp.json()["detail"]
        finally:
            self._teardown()

    def test_create_snapshot_requires_auth(self):
        with TestClient(app) as client:
            resp = client.post(
                "/admin/wbr/profiles/profile-1/snapshots",
                json={"weeks": 4},
            )
        assert resp.status_code in (401, 403)
