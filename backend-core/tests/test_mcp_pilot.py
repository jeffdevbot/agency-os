from __future__ import annotations

import asyncio

from jose import jwt
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.mcp.server import create_mcp_server, get_mcp_protected_resource_metadata_path
from app.mcp.tools.wbr import (
    draft_wbr_email_for_client,
    get_wbr_summary_for_profile,
    list_wbr_profiles_for_client,
    resolve_client_matches,
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
    def __init__(self, clients, profiles):
        self._clients = clients
        self._profiles = profiles

    def table(self, name):
        if name == "agency_clients":
            return _FakeQuery(self._clients)
        if name == "wbr_profiles":
            return _FakeQuery(self._profiles)
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


def test_resolve_client_matches_filters_to_active_wbr_clients(monkeypatch):
    fake_db = _FakeDB(
        clients=[
            {"id": "c1", "name": "Whoosh"},
            {"id": "c2", "name": "Whoosh Canada"},
            {"id": "c3", "name": "Dormant"},
        ],
        profiles=[
            {"client_id": "c1", "marketplace_code": "US", "status": "active"},
            {"client_id": "c1", "marketplace_code": "CA", "status": "active"},
            {"client_id": "c2", "marketplace_code": "CA", "status": "active"},
            {"client_id": "c3", "marketplace_code": "US", "status": "draft"},
        ],
    )
    monkeypatch.setattr("app.mcp.tools.wbr._get_supabase_admin_client", lambda: fake_db)

    result = resolve_client_matches("whoosh")
    assert result == {
        "matches": [
            {
                "client_id": "c1",
                "client_name": "Whoosh",
                "active_wbr_marketplaces": ["CA", "US"],
            },
            {
                "client_id": "c2",
                "client_name": "Whoosh Canada",
                "active_wbr_marketplaces": ["CA"],
            },
        ]
    }


def test_resolve_client_tool_is_registered_and_returns_structured_output(monkeypatch):
    fake_db = _FakeDB(
        clients=[{"id": "c1", "name": "Basari World"}],
        profiles=[{"client_id": "c1", "marketplace_code": "MX", "status": "active"}],
    )
    monkeypatch.setattr("app.mcp.tools.wbr._get_supabase_admin_client", lambda: fake_db)

    server = create_mcp_server()
    _content, payload = asyncio.run(server.call_tool("resolve_client", {"query": "Basari"}))
    assert payload == {
        "matches": [
            {
                "client_id": "c1",
                "client_name": "Basari World",
                "active_wbr_marketplaces": ["MX"],
            }
        ]
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
    monkeypatch.setattr("app.mcp.tools.wbr.WBRProfileService", _FakeProfileService)
    monkeypatch.setattr("app.mcp.tools.wbr.WBRSnapshotService", _FakeSnapshotService)
    monkeypatch.setattr("app.mcp.tools.wbr.generate_email_draft", _fake_generate_email_draft)

    server = create_mcp_server()
    tools = asyncio.run(server.list_tools())
    names = {tool.name for tool in tools}
    assert names == {
        "draft_wbr_email",
        "get_wbr_summary",
        "list_wbr_profiles",
        "resolve_client",
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
