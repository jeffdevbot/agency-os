from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import auth


class _QueryChain:
    def __init__(self, response=None, error: Exception | None = None):
        self._response = response
        self._error = error

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        if self._error is not None:
            raise self._error
        return self._response


class _FakeDb:
    def __init__(self, response=None, error: Exception | None = None):
        self._response = response
        self._error = error

    def table(self, _name: str):
        return _QueryChain(response=self._response, error=self._error)


class _MappedDb:
    def __init__(self, responses: dict[str, object]):
        self._responses = responses

    def table(self, name: str):
        response = self._responses.get(name, SimpleNamespace(data=[]))
        return _QueryChain(response=response)


def test_require_admin_user_retries_after_transient_supabase_error(monkeypatch):
    admin_response = SimpleNamespace(data=[{"id": "u1", "team_role": "admin"}])
    clients = iter(
        [
            _FakeDb(error=Exception("ConnectionTerminated error_code:1")),
            _FakeDb(response=admin_response),
        ]
    )

    monkeypatch.setattr(auth, "_supabase_admin_client", None)
    monkeypatch.setattr(auth, "_get_supabase_admin_client", lambda: next(clients))

    result = auth.require_admin_user({"sub": "u1"})

    assert result == {"sub": "u1"}


def test_require_admin_user_returns_generic_error_after_repeated_failure(monkeypatch):
    clients = iter(
        [
            _FakeDb(error=Exception("ConnectionTerminated error_code:1")),
            _FakeDb(error=Exception("ConnectionTerminated error_code:1")),
        ]
    )

    monkeypatch.setattr(auth, "_supabase_admin_client", None)
    monkeypatch.setattr(auth, "_get_supabase_admin_client", lambda: next(clients))

    with pytest.raises(HTTPException) as exc_info:
        auth.require_admin_user({"sub": "u1"})

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Failed to validate admin access"


def test_assert_tool_access_allows_explicit_tool_access(monkeypatch):
    monkeypatch.setattr(
        auth,
        "_fetch_profile_rows",
        lambda _user_id: [{"id": "u1", "is_admin": False, "allowed_tools": ["ngram-2"]}],
    )

    profile = auth.assert_tool_access({"sub": "u1"}, "ngram-2")

    assert profile["id"] == "u1"


def test_assert_wbr_profile_tool_access_denies_unassigned_client(monkeypatch):
    monkeypatch.setattr(
        auth,
        "_fetch_profile_rows",
        lambda _user_id: [{"id": "u1", "is_admin": False, "allowed_tools": ["ngram-2"]}],
    )
    monkeypatch.setattr(
        auth,
        "_get_supabase_admin_client",
        lambda: _MappedDb(
            {
                "wbr_profiles": SimpleNamespace(data=[{"id": "profile-1", "client_id": "client-1"}]),
                "client_assignments": SimpleNamespace(data=[{"client_id": "client-2"}]),
            }
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        auth.assert_wbr_profile_tool_access({"sub": "u1"}, "profile-1", "ngram-2")

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Client access required"
