from __future__ import annotations

import asyncio

from jose import jwt
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.mcp.server import create_mcp_server, get_mcp_protected_resource_metadata_path
from app.mcp.tools.clients import resolve_client_matches
from app.mcp.tools.pnl import (
    draft_monthly_pnl_email_for_client,
    get_monthly_pnl_email_brief_for_client,
    get_monthly_pnl_report_for_profile,
    list_monthly_pnl_profiles_for_client,
)
from app.mcp.tools.wbr import (
    draft_wbr_email_for_client,
    get_wbr_summary_for_profile,
    list_wbr_profiles_for_client,
)


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows
        self._filters: list[tuple[str, object]] = []
        self._limit: int | None = None
        self._order_key: str | None = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        self._filters.append((key, value))
        return self

    def limit(self, value):
        self._limit = value
        return self

    def order(self, key, *_args, **_kwargs):
        self._order_key = key
        return self

    def execute(self):
        rows = self._rows
        for key, value in self._filters:
            rows = [row for row in rows if row.get(key) == value]
        if self._order_key:
            rows = sorted(rows, key=lambda row: str(row.get(self._order_key) or ""))
        if self._limit is not None:
            rows = rows[: self._limit]

        class _Resp:
            data = rows

        return _Resp()


class _FakeDB:
    def __init__(
        self,
        clients,
        profiles,
        pnl_profiles=None,
        pnl_import_months=None,
        brands=None,
        assignments=None,
        roles=None,
        team_members=None,
    ):
        self._clients = clients
        self._profiles = profiles
        self._pnl_profiles = pnl_profiles or []
        self._pnl_import_months = pnl_import_months or []
        self._brands = brands or []
        self._assignments = assignments or []
        self._roles = roles or []
        self._team_members = team_members or []

    def table(self, name):
        if name == "agency_clients":
            return _FakeQuery(self._clients)
        if name == "brands":
            return _FakeQuery(self._brands)
        if name == "wbr_profiles":
            return _FakeQuery(self._profiles)
        if name == "monthly_pnl_profiles":
            return _FakeQuery(self._pnl_profiles)
        if name == "monthly_pnl_import_months":
            return _FakeQuery(self._pnl_import_months)
        if name == "client_assignments":
            return _FakeQuery(self._assignments)
        if name == "agency_roles":
            return _FakeQuery(self._roles)
        if name == "profiles":
            return _FakeQuery(self._team_members)
        raise AssertionError(f"unexpected table {name}")


def _make_token(*, user_id: str, email: str) -> str:
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": settings.supabase_jwt_audience,
            "iss": settings.supabase_issuer,
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )


def test_mcp_mount_requires_bearer_auth(monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", "test-secret")
    monkeypatch.setattr(settings, "mcp_pilot_allowed_user_id", "user-123")
    monkeypatch.setattr(settings, "mcp_pilot_allowed_email", "jeff@example.com")
    monkeypatch.setattr(settings, "mcp_public_base_url", "http://localhost:8000/mcp")

    with TestClient(app) as client:
        response = client.get("/mcp/")
    assert response.status_code == 401
    assert response.json()["error"] == "invalid_token"
    assert response.json()["error_description"] == "Authentication required"
    assert "resource_metadata=" in response.headers["www-authenticate"]


def test_mcp_mount_accepts_allowlisted_user(monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", "test-secret")
    monkeypatch.setattr(settings, "mcp_pilot_allowed_user_id", "user-123")
    monkeypatch.setattr(settings, "mcp_pilot_allowed_email", "jeff@example.com")
    monkeypatch.setattr(settings, "mcp_public_base_url", "http://localhost:8000/mcp")

    token = _make_token(user_id="user-123", email="jeff@example.com")
    with TestClient(app) as client:
        response = client.post(
            "/mcp/",
            headers={"Authorization": f"Bearer {token}"},
            json={"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}},
        )
    assert response.status_code != 401
    assert response.status_code != 403
    assert response.status_code < 500


def test_mcp_mount_rejects_non_allowlisted_user(monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", "test-secret")
    monkeypatch.setattr(settings, "mcp_pilot_allowed_user_id", "user-123")
    monkeypatch.setattr(settings, "mcp_pilot_allowed_email", "jeff@example.com")
    monkeypatch.setattr(settings, "mcp_public_base_url", "http://localhost:8000/mcp")

    token = _make_token(user_id="other-user", email="other@example.com")
    with TestClient(app) as client:
        response = client.get("/mcp/", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["error"] == "invalid_token"


def test_mcp_protected_resource_metadata_route(monkeypatch):
    monkeypatch.setattr(settings, "mcp_public_base_url", "http://localhost:8000/mcp")

    with TestClient(app) as client:
        response = client.get(get_mcp_protected_resource_metadata_path())

    assert response.status_code == 200
    assert response.json() == {
        "resource": "http://localhost:8000/mcp",
        "authorization_servers": [settings.supabase_issuer],
        "bearer_methods_supported": ["header"],
        "resource_name": "Agency OS MCP",
    }


def test_mcp_protected_resource_metadata_route_allows_claude_origin():
    with TestClient(app) as client:
        preflight = client.options(
            get_mcp_protected_resource_metadata_path(),
            headers={
                "Origin": "https://claude.ai",
                "Access-Control-Request-Method": "GET",
            },
        )
        response = client.get(
            get_mcp_protected_resource_metadata_path(),
            headers={"Origin": "https://claude.ai"},
        )

    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "https://claude.ai"
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://claude.ai"


def test_resolve_client_matches_returns_shared_reporting_metadata(monkeypatch):
    fake_db = _FakeDB(
        clients=[
            {
                "id": "c1",
                "name": "Whoosh",
                "status": "active",
                "company_name": "Whoosh Inc.",
                "email": "hello@whoosh.test",
                "phone": "555-1111",
                "notes": "Priority client",
                "context_summary": "Premium cleaning brand.",
                "target_audience": "Parents with young kids",
                "positioning_notes": "Lead with convenience and safety.",
            },
            {"id": "c2", "name": "Whoosh Canada", "status": "active"},
            {"id": "c3", "name": "Dormant", "status": "inactive"},
        ],
        profiles=[
            {"client_id": "c1", "marketplace_code": "US", "status": "active"},
            {"client_id": "c1", "marketplace_code": "CA", "status": "active"},
            {"client_id": "c2", "marketplace_code": "CA", "status": "active"},
            {"client_id": "c3", "marketplace_code": "US", "status": "draft"},
        ],
        pnl_profiles=[
            {"id": "pp1", "client_id": "c1", "marketplace_code": "US"},
            {"id": "pp2", "client_id": "c2", "marketplace_code": "CA"},
        ],
        pnl_import_months=[
            {"profile_id": "pp1", "is_active": True},
            {"profile_id": "pp2", "is_active": True},
        ],
        brands=[
            {
                "id": "b1",
                "client_id": "c1",
                "name": "Whoosh Core",
                "product_keywords": ["spray", "cleaner"],
                "amazon_marketplaces": ["US", "CA"],
                "clickup_space_id": "space-1",
                "clickup_list_id": "list-1",
            }
        ],
        assignments=[
            {
                "id": "a1",
                "client_id": "c1",
                "brand_id": "b1",
                "team_member_id": "tm1",
                "role_id": "r1",
            }
        ],
        roles=[{"id": "r1", "slug": "brand_manager", "name": "Brand Manager"}],
        team_members=[
            {
                "id": "tm1",
                "email": "owner@agency.test",
                "display_name": "Alex",
                "full_name": "Alex Owner",
                "employment_status": "active",
                "bench_status": "assigned",
                "clickup_user_id": "cu-1",
                "slack_user_id": "su-1",
            }
        ],
    )
    monkeypatch.setattr("app.mcp.tools.clients._get_supabase_admin_client", lambda: fake_db)

    result = resolve_client_matches("whoosh")
    assert result == {
        "matches": [
            {
                "client_id": "c1",
                "client_name": "Whoosh",
                "client_status": "active",
                "company_name": "Whoosh Inc.",
                "primary_email": "hello@whoosh.test",
                "phone": "555-1111",
                "active_wbr_marketplaces": ["CA", "US"],
                "active_monthly_pnl_marketplaces": ["US"],
                "brands": [
                    {
                        "brand_id": "b1",
                        "brand_name": "Whoosh Core",
                        "product_keywords": ["spray", "cleaner"],
                        "amazon_marketplaces": ["US", "CA"],
                        "clickup_space_id": "space-1",
                        "clickup_list_id": "list-1",
                        "has_clickup_space": True,
                        "has_clickup_list": True,
                    }
                ],
                "team_assignments": [
                    {
                        "assignment_id": "a1",
                        "team_member_id": "tm1",
                        "team_member_name": "Alex",
                        "team_member_email": "owner@agency.test",
                        "employment_status": "active",
                        "bench_status": "assigned",
                        "clickup_user_id": "cu-1",
                        "slack_user_id": "su-1",
                        "role_slug": "brand_manager",
                        "role_name": "Brand Manager",
                        "scope": "brand",
                        "brand_id": "b1",
                        "brand_name": "Whoosh Core",
                    }
                ],
                "context": {
                    "notes": "Priority client",
                    "context_summary": "Premium cleaning brand.",
                    "target_audience": "Parents with young kids",
                    "positioning_notes": "Lead with convenience and safety.",
                },
                "capabilities": {
                    "has_wbr": True,
                    "has_monthly_pnl": True,
                    "has_brands": True,
                    "has_clickup_destinations": True,
                    "has_team_assignments": True,
                },
            },
            {
                "client_id": "c2",
                "client_name": "Whoosh Canada",
                "client_status": "active",
                "company_name": None,
                "primary_email": None,
                "phone": None,
                "active_wbr_marketplaces": ["CA"],
                "active_monthly_pnl_marketplaces": ["CA"],
                "brands": [],
                "team_assignments": [],
                "context": {
                    "notes": None,
                    "context_summary": None,
                    "target_audience": None,
                    "positioning_notes": None,
                },
                "capabilities": {
                    "has_wbr": True,
                    "has_monthly_pnl": True,
                    "has_brands": False,
                    "has_clickup_destinations": False,
                    "has_team_assignments": False,
                },
            },
        ]
    }


def test_resolve_client_tool_is_registered_and_returns_structured_output(monkeypatch):
    fake_db = _FakeDB(
        clients=[{"id": "c1", "name": "Basari World", "status": "active"}],
        profiles=[{"client_id": "c1", "marketplace_code": "MX", "status": "active"}],
    )
    monkeypatch.setattr("app.mcp.tools.clients._get_supabase_admin_client", lambda: fake_db)

    server = create_mcp_server()
    _content, payload = asyncio.run(server.call_tool("resolve_client", {"query": "Basari"}))
    assert payload == {
        "matches": [
            {
                "client_id": "c1",
                "client_name": "Basari World",
                "client_status": "active",
                "company_name": None,
                "primary_email": None,
                "phone": None,
                "active_wbr_marketplaces": ["MX"],
                "active_monthly_pnl_marketplaces": [],
                "brands": [],
                "team_assignments": [],
                "context": {
                    "notes": None,
                    "context_summary": None,
                    "target_audience": None,
                    "positioning_notes": None,
                },
                "capabilities": {
                    "has_wbr": True,
                    "has_monthly_pnl": False,
                    "has_brands": False,
                    "has_clickup_destinations": False,
                    "has_team_assignments": False,
                },
            }
        ]
    }


def test_resolve_client_matches_can_return_clients_without_report_coverage(monkeypatch):
    fake_db = _FakeDB(
        clients=[
            {"id": "c1", "name": "Whoosh", "status": "active"},
            {"id": "c3", "name": "Dormant", "status": "inactive"},
        ],
        profiles=[],
    )
    monkeypatch.setattr("app.mcp.tools.clients._get_supabase_admin_client", lambda: fake_db)

    result = resolve_client_matches("Dormant")
    assert result == {
        "matches": [
            {
                "client_id": "c3",
                "client_name": "Dormant",
                "client_status": "inactive",
                "company_name": None,
                "primary_email": None,
                "phone": None,
                "active_wbr_marketplaces": [],
                "active_monthly_pnl_marketplaces": [],
                "brands": [],
                "team_assignments": [],
                "context": {
                    "notes": None,
                    "context_summary": None,
                    "target_audience": None,
                    "positioning_notes": None,
                },
                "capabilities": {
                    "has_wbr": False,
                    "has_monthly_pnl": False,
                    "has_brands": False,
                    "has_clickup_destinations": False,
                    "has_team_assignments": False,
                },
            },
        ]
    }


def test_list_monthly_pnl_profiles_for_client_returns_active_profiles(monkeypatch):
    fake_db = _FakeDB(
        clients=[{"id": "c1", "name": "Whoosh"}],
        profiles=[],
        pnl_profiles=[
            {
                "id": "pp2",
                "client_id": "c1",
                "marketplace_code": "CA",
                "currency_code": "CAD",
                "status": "active",
            },
            {
                "id": "pp1",
                "client_id": "c1",
                "marketplace_code": "US",
                "currency_code": "USD",
                "status": "active",
            },
            {
                "id": "pp3",
                "client_id": "c1",
                "marketplace_code": "MX",
                "currency_code": "USD",
                "status": "draft",
            },
        ],
        pnl_import_months=[
            {"profile_id": "pp1", "entry_month": "2025-11-01", "is_active": True},
            {"profile_id": "pp1", "entry_month": "2025-12-01", "is_active": True},
            {"profile_id": "pp2", "entry_month": "2026-01-01", "is_active": True},
            {"profile_id": "pp3", "entry_month": "2026-02-01", "is_active": False},
        ],
    )
    monkeypatch.setattr("app.mcp.tools.pnl._get_supabase_admin_client", lambda: fake_db)

    result = list_monthly_pnl_profiles_for_client("c1")
    assert result == {
        "profiles": [
            {
                "profile_id": "pp2",
                "client_id": "c1",
                "client_name": "Whoosh",
                "marketplace_code": "CA",
                "currency_code": "CAD",
                "status": "active",
                "first_active_month": "2026-01-01",
                "last_active_month": "2026-01-01",
                "active_month_count": 1,
            },
            {
                "profile_id": "pp1",
                "client_id": "c1",
                "client_name": "Whoosh",
                "marketplace_code": "US",
                "currency_code": "USD",
                "status": "active",
                "first_active_month": "2025-11-01",
                "last_active_month": "2025-12-01",
                "active_month_count": 2,
            },
        ]
    }


def test_get_monthly_pnl_report_for_profile_wraps_report(monkeypatch):
    fake_db = _FakeDB(
        clients=[{"id": "c1", "name": "Whoosh"}],
        profiles=[],
    )

    class _FakePNLProfileService:
        def __init__(self, _db):
            pass

        def get_profile(self, profile_id):
            assert profile_id == "pp1"
            return {
                "id": "pp1",
                "client_id": "c1",
                "marketplace_code": "US",
                "currency_code": "USD",
                "status": "active",
            }

    class _FakePNLReportService:
        def __init__(self, _db):
            pass

        async def build_report_async(self, profile_id, *, filter_mode, start_month, end_month):
            assert profile_id == "pp1"
            assert filter_mode == "range"
            assert start_month == "2025-11-01"
            assert end_month == "2025-12-01"
            return {
                "profile": {"id": "pp1"},
                "months": ["2025-11-01", "2025-12-01"],
                "line_items": [{"key": "net_earnings", "months": {"2025-11-01": "100.00"}}],
                "warnings": [{"type": "missing_cogs"}],
            }

    monkeypatch.setattr("app.mcp.tools.pnl._get_supabase_admin_client", lambda: fake_db)
    monkeypatch.setattr("app.mcp.tools.pnl.PNLProfileService", _FakePNLProfileService)
    monkeypatch.setattr("app.mcp.tools.pnl.PNLReportService", _FakePNLReportService)

    result = asyncio.run(
        get_monthly_pnl_report_for_profile(
            "pp1",
            filter_mode="range",
            start_month="2025-11-01",
            end_month="2025-12-01",
        )
    )
    assert result == {
        "profile": {
            "id": "pp1",
            "profile_id": "pp1",
            "client_id": "c1",
            "client_name": "Whoosh",
            "marketplace_code": "US",
            "currency_code": "USD",
            "status": "active",
        },
        "months": ["2025-11-01", "2025-12-01"],
        "line_items": [{"key": "net_earnings", "months": {"2025-11-01": "100.00"}}],
        "warnings": [{"type": "missing_cogs"}],
    }


def test_get_monthly_pnl_email_brief_for_client_wraps_service(monkeypatch):
    fake_db = _FakeDB(
        clients=[{"id": "c1", "name": "Whoosh"}],
        profiles=[],
    )

    class _FakeBriefService:
        def __init__(self, _db):
            pass

        async def build_client_brief_async(
            self,
            client_id,
            report_month,
            *,
            marketplace_codes=None,
            comparison_mode="auto",
        ):
            assert client_id == "c1"
            assert report_month == "2026-02-01"
            assert marketplace_codes == ["US", "CA"]
            assert comparison_mode == "auto"
            return {
                "client": {"client_id": "c1", "client_name": "Whoosh"},
                "report_month": "2026-02-01",
                "sections": [{"marketplace_code": "US"}, {"marketplace_code": "CA"}],
            }

    monkeypatch.setattr("app.mcp.tools.pnl._get_supabase_admin_client", lambda: fake_db)
    monkeypatch.setattr("app.mcp.tools.pnl.PNLEmailBriefService", _FakeBriefService)

    result = asyncio.run(
        get_monthly_pnl_email_brief_for_client(
            "c1",
            report_month="2026-02-01",
            marketplace_codes=["US", "CA"],
            comparison_mode="auto",
        )
    )
    assert result == {
        "client": {"client_id": "c1", "client_name": "Whoosh"},
        "report_month": "2026-02-01",
        "sections": [{"marketplace_code": "US"}, {"marketplace_code": "CA"}],
    }


def test_draft_monthly_pnl_email_for_client_normalizes_result(monkeypatch):
    monkeypatch.setattr("app.mcp.tools.pnl._get_supabase_admin_client", lambda: object())

    async def _fake_generate_email_draft(
        _db,
        client_id,
        *,
        report_month,
        marketplace_codes=None,
        comparison_mode="auto",
        recipient_name=None,
        sender_name=None,
        sender_role=None,
        agency_name=None,
        created_by=None,
    ):
        assert client_id == "c1"
        assert report_month == "2026-02-01"
        assert marketplace_codes == ["US"]
        assert comparison_mode == "auto"
        assert recipient_name == "Billy"
        assert sender_name is None
        assert created_by is None
        return {
            "id": "pd1",
            "client_id": "c1",
            "report_month": "2026-02-01",
            "draft_kind": "monthly_pnl_highlights_email",
            "prompt_version": "monthly_pnl_email_v1",
            "comparison_mode_requested": "auto",
            "comparison_mode_used": "yoy_preferred",
            "marketplace_scope": "US",
            "profile_ids": ["pp1"],
            "subject": "Subject line",
            "body": "Email body",
            "model": "gpt-5-mini",
            "created_at": "2026-03-23T18:00:00+00:00",
        }

    monkeypatch.setattr("app.mcp.tools.pnl.generate_email_draft", _fake_generate_email_draft)

    result = asyncio.run(
        draft_monthly_pnl_email_for_client(
            "c1",
            report_month="2026-02-01",
            marketplace_codes=["US"],
            recipient_name="Billy",
        )
    )
    assert result == {
        "draft_id": "pd1",
        "client_id": "c1",
        "report_month": "2026-02-01",
        "draft_kind": "monthly_pnl_highlights_email",
        "prompt_version": "monthly_pnl_email_v1",
        "comparison_mode_requested": "auto",
        "comparison_mode_used": "yoy_preferred",
        "marketplace_scope": "US",
        "profile_ids": ["pp1"],
        "subject": "Subject line",
        "body": "Email body",
        "model": "gpt-5-mini",
        "created_at": "2026-03-23T18:00:00+00:00",
    }


def test_list_wbr_profiles_for_client_returns_active_profiles(monkeypatch):
    fake_db = _FakeDB(
        clients=[{"id": "c1", "name": "Whoosh"}],
        profiles=[
            {
                "id": "p2",
                "client_id": "c1",
                "display_name": "Whoosh CA",
                "marketplace_code": "CA",
                "status": "active",
            },
            {
                "id": "p1",
                "client_id": "c1",
                "display_name": "Whoosh US",
                "marketplace_code": "US",
                "status": "active",
            },
            {
                "id": "p3",
                "client_id": "c1",
                "display_name": "Whoosh Draft",
                "marketplace_code": "MX",
                "status": "draft",
            },
        ],
    )
    monkeypatch.setattr("app.mcp.tools.wbr._get_supabase_admin_client", lambda: fake_db)

    result = list_wbr_profiles_for_client("c1")
    assert result == {
        "profiles": [
            {
                "profile_id": "p2",
                "client_id": "c1",
                "client_name": "Whoosh",
                "display_name": "Whoosh CA",
                "marketplace_code": "CA",
                "status": "active",
            },
            {
                "profile_id": "p1",
                "client_id": "c1",
                "client_name": "Whoosh",
                "display_name": "Whoosh US",
                "marketplace_code": "US",
                "status": "active",
            },
        ]
    }


def test_get_wbr_summary_for_profile_wraps_snapshot(monkeypatch):
    fake_db = _FakeDB(
        clients=[{"id": "c1", "name": "Basari World"}],
        profiles=[],
    )

    class _FakeProfileService:
        def __init__(self, _db):
            pass

        def get_profile(self, profile_id):
            assert profile_id == "p1"
            return {
                "id": "p1",
                "client_id": "c1",
                "display_name": "Basari MX",
                "marketplace_code": "MX",
                "status": "active",
            }

    class _FakeSnapshotService:
        def __init__(self, _db):
            pass

        def get_or_create_snapshot(self, profile_id):
            assert profile_id == "p1"
            return {
                "id": "s1",
                "snapshot_kind": "claw_request",
                "source_run_at": "2026-03-21T12:00:00+00:00",
                "created_at": "2026-03-21T12:01:00+00:00",
                "digest": {
                    "digest_version": "wbr_digest_v1",
                    "window": {"week_ending": "2026-03-14"},
                },
            }

    monkeypatch.setattr("app.mcp.tools.wbr._get_supabase_admin_client", lambda: fake_db)
    monkeypatch.setattr("app.mcp.tools.clients._get_supabase_admin_client", lambda: fake_db)
    monkeypatch.setattr("app.mcp.tools.wbr.WBRProfileService", _FakeProfileService)
    monkeypatch.setattr("app.mcp.tools.wbr.WBRSnapshotService", _FakeSnapshotService)

    result = get_wbr_summary_for_profile("p1")
    assert result == {
        "profile": {
            "profile_id": "p1",
            "client_id": "c1",
            "client_name": "Basari World",
            "display_name": "Basari MX",
            "marketplace_code": "MX",
        },
        "snapshot": {
            "snapshot_id": "s1",
            "snapshot_kind": "claw_request",
            "source_run_at": "2026-03-21T12:00:00+00:00",
            "created_at": "2026-03-21T12:01:00+00:00",
        },
        "digest": {
            "digest_version": "wbr_digest_v1",
            "window": {"week_ending": "2026-03-14"},
        },
    }


def test_draft_wbr_email_for_client_normalizes_result(monkeypatch):
    monkeypatch.setattr("app.mcp.tools.wbr._get_supabase_admin_client", lambda: object())

    async def _fake_generate_email_draft(_db, client_id, *, created_by=None):
        assert client_id == "c1"
        assert created_by is None
        return {
            "id": "d1",
            "client_id": "c1",
            "snapshot_group_key": "week_ending:2026-03-14",
            "marketplace_scope": "CA,MX",
            "snapshot_ids": ["s1", "s2"],
            "subject": "Subject line",
            "body": "Email body",
            "model": "gpt-5-mini",
            "created_at": "2026-03-21T14:00:00+00:00",
        }

    monkeypatch.setattr("app.mcp.tools.wbr.generate_email_draft", _fake_generate_email_draft)

    result = asyncio.run(draft_wbr_email_for_client("c1"))
    assert result == {
        "draft_id": "d1",
        "client_id": "c1",
        "snapshot_group_key": "week_ending:2026-03-14",
        "draft_kind": "weekly_client_email",
        "prompt_version": "wbr_email_v2",
        "marketplace_scope": "CA,MX",
        "snapshot_ids": ["s1", "s2"],
        "subject": "Subject line",
        "body": "Email body",
        "model": "gpt-5-mini",
        "created_at": "2026-03-21T14:00:00+00:00",
    }


def test_wbr_tools_are_registered(monkeypatch):
    fake_db = _FakeDB(
        clients=[{"id": "c1", "name": "Whoosh"}],
        profiles=[{"client_id": "c1", "marketplace_code": "US", "status": "active"}],
        pnl_profiles=[
            {
                "id": "pp1",
                "client_id": "c1",
                "marketplace_code": "US",
                "currency_code": "USD",
                "status": "active",
            }
        ],
        pnl_import_months=[
            {
                "profile_id": "pp1",
                "entry_month": "2025-12-01",
                "is_active": True,
            }
        ],
    )

    class _FakeProfileService:
        def __init__(self, _db):
            pass

        def list_profiles(self, _client_id):
            return [
                {
                    "id": "p1",
                    "client_id": "c1",
                    "display_name": "Whoosh US",
                    "marketplace_code": "US",
                    "status": "active",
                }
            ]

        def get_profile(self, _profile_id):
            return {
                "id": "p1",
                "client_id": "c1",
                "display_name": "Whoosh US",
                "marketplace_code": "US",
                "status": "active",
            }

    class _FakeSnapshotService:
        def __init__(self, _db):
            pass

        def get_or_create_snapshot(self, _profile_id):
            return {
                "id": "s1",
                "snapshot_kind": "claw_request",
                "source_run_at": None,
                "created_at": None,
                "digest": {"digest_version": "wbr_digest_v1"},
            }

    async def _fake_generate_email_draft(_db, _client_id, *, created_by=None):
        return {
            "id": "d1",
            "snapshot_group_key": "week_ending:2026-03-14",
            "marketplace_scope": "US",
            "snapshot_ids": ["s1"],
            "subject": "Subject",
            "body": "Body",
            "model": "gpt-5-mini",
            "created_at": "2026-03-21T14:00:00+00:00",
        }

    monkeypatch.setattr("app.mcp.tools.wbr._get_supabase_admin_client", lambda: fake_db)
    monkeypatch.setattr("app.mcp.tools.clients._get_supabase_admin_client", lambda: fake_db)
    monkeypatch.setattr("app.mcp.tools.wbr.WBRProfileService", _FakeProfileService)
    monkeypatch.setattr("app.mcp.tools.wbr.WBRSnapshotService", _FakeSnapshotService)
    monkeypatch.setattr("app.mcp.tools.wbr.generate_email_draft", _fake_generate_email_draft)
    monkeypatch.setattr("app.mcp.tools.pnl._get_supabase_admin_client", lambda: fake_db)

    class _FakePNLProfileService:
        def __init__(self, _db):
            pass

        def list_profiles(self, _client_id):
            return [
                {
                    "id": "pp1",
                    "client_id": "c1",
                    "marketplace_code": "US",
                    "currency_code": "USD",
                    "status": "active",
                }
            ]

        def get_profile(self, _profile_id):
            return {
                "id": "pp1",
                "client_id": "c1",
                "marketplace_code": "US",
                "currency_code": "USD",
                "status": "active",
            }

    class _FakePNLReportService:
        def __init__(self, _db):
            pass

        async def build_report_async(self, _profile_id, *, filter_mode, start_month, end_month):
            assert filter_mode == "last_3"
            assert start_month is None
            assert end_month is None
            return {
                "profile": {"id": "pp1"},
                "months": ["2025-12-01"],
                "line_items": [{"key": "net_earnings", "months": {"2025-12-01": "50.00"}}],
                "warnings": [],
            }

    class _FakePNLEmailBriefService:
        def __init__(self, _db):
            pass

        async def build_client_brief_async(
            self,
            client_id,
            report_month,
            *,
            marketplace_codes=None,
            comparison_mode="auto",
        ):
            assert client_id == "c1"
            assert report_month == "2026-02-01"
            assert marketplace_codes == ["US"]
            assert comparison_mode == "auto"
            return {
                "client": {"client_id": "c1", "client_name": "Whoosh"},
                "report_month": "2026-02-01",
                "comparison_mode_used": "yoy_preferred",
                "sections": [{"marketplace_code": "US"}],
            }

    async def _fake_generate_pnl_email_draft(
        _db,
        _client_id,
        *,
        report_month,
        marketplace_codes=None,
        comparison_mode="auto",
        recipient_name=None,
        sender_name=None,
        sender_role=None,
        agency_name=None,
        created_by=None,
    ):
        assert report_month == "2026-02-01"
        assert marketplace_codes == ["US"]
        return {
            "id": "pd1",
            "report_month": "2026-02-01",
            "comparison_mode_requested": "auto",
            "comparison_mode_used": "yoy_preferred",
            "marketplace_scope": "US",
            "profile_ids": ["pp1"],
            "subject": "Monthly P&L draft",
            "body": "Hi Team,",
            "model": "gpt-5-mini",
            "created_at": "2026-03-23T18:00:00+00:00",
        }

    monkeypatch.setattr("app.mcp.tools.pnl.PNLProfileService", _FakePNLProfileService)
    monkeypatch.setattr("app.mcp.tools.pnl.PNLReportService", _FakePNLReportService)
    monkeypatch.setattr("app.mcp.tools.pnl.PNLEmailBriefService", _FakePNLEmailBriefService)
    monkeypatch.setattr("app.mcp.tools.pnl.generate_email_draft", _fake_generate_pnl_email_draft)

    server = create_mcp_server()
    tools = asyncio.run(server.list_tools())
    names = {tool.name for tool in tools}
    assert names == {
        "draft_wbr_email",
        "draft_monthly_pnl_email",
        "get_monthly_pnl_email_brief",
        "get_wbr_summary",
        "get_monthly_pnl_report",
        "list_wbr_profiles",
        "list_monthly_pnl_profiles",
        "resolve_client",
        "list_clickup_tasks",
        "get_clickup_task",
        "resolve_team_member",
        "prepare_clickup_task",
        "create_clickup_task",
    }

    _content, payload = asyncio.run(server.call_tool("list_wbr_profiles", {"client_id": "c1"}))
    assert payload == {
        "profiles": [
            {
                "profile_id": "p1",
                "client_id": "c1",
                "client_name": "Whoosh",
                "display_name": "Whoosh US",
                "marketplace_code": "US",
                "status": "active",
            }
        ]
    }

    _content, payload = asyncio.run(server.call_tool("get_wbr_summary", {"profile_id": "p1"}))
    assert payload["profile"]["profile_id"] == "p1"

    _content, payload = asyncio.run(server.call_tool("draft_wbr_email", {"client_id": "c1"}))
    assert payload["draft_id"] == "d1"

    _content, payload = asyncio.run(server.call_tool("resolve_client", {"query": "Whoosh"}))
    assert payload == {
        "matches": [
            {
                "client_id": "c1",
                "client_name": "Whoosh",
                "client_status": None,
                "company_name": None,
                "primary_email": None,
                "phone": None,
                "active_wbr_marketplaces": ["US"],
                "active_monthly_pnl_marketplaces": ["US"],
                "brands": [],
                "team_assignments": [],
                "context": {
                    "notes": None,
                    "context_summary": None,
                    "target_audience": None,
                    "positioning_notes": None,
                },
                "capabilities": {
                    "has_wbr": True,
                    "has_monthly_pnl": True,
                    "has_brands": False,
                    "has_clickup_destinations": False,
                    "has_team_assignments": False,
                },
            }
        ]
    }

    _content, payload = asyncio.run(server.call_tool("list_monthly_pnl_profiles", {"client_id": "c1"}))
    assert payload == {
        "profiles": [
            {
                "profile_id": "pp1",
                "client_id": "c1",
                "client_name": "Whoosh",
                "marketplace_code": "US",
                "currency_code": "USD",
                "status": "active",
                "first_active_month": "2025-12-01",
                "last_active_month": "2025-12-01",
                "active_month_count": 1,
            }
        ]
    }

    _content, payload = asyncio.run(server.call_tool("get_monthly_pnl_report", {"profile_id": "pp1"}))
    assert payload["profile"]["profile_id"] == "pp1"

    _content, payload = asyncio.run(
        server.call_tool(
            "get_monthly_pnl_email_brief",
            {
                "client_id": "c1",
                "report_month": "2026-02-01",
                "marketplace_codes": ["US"],
            },
        )
    )
    assert payload["comparison_mode_used"] == "yoy_preferred"

    _content, payload = asyncio.run(
        server.call_tool(
            "draft_monthly_pnl_email",
            {
                "client_id": "c1",
                "report_month": "2026-02-01",
                "marketplace_codes": ["US"],
            },
        )
    )
    assert payload["draft_id"] == "pd1"
