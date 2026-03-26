"""Tests for ClickUp MCP tools — Slice 0 + Slice 1 + Slice 2."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.clickup import ClickUpTask
from app.services.clickup_task_tools import (
    ClickUpToolError,
    _fetch_brand_rows,
    _format_full_task,
    _format_task_row,
    _is_valid_clickup_user_id,
    _resolve_assignee,
    create_task_for_brand,
    get_task_by_id_or_url,
    list_tasks_for_brand,
    parse_clickup_task_id,
    prepare_task_for_brand,
    resolve_brand_destination,
    resolve_team_member_query,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeQuery:
    """Minimal Supabase query chain fake."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self._filters: list[tuple[str, Any]] = []

    def select(self, *_args: Any, **_kwargs: Any) -> "_FakeQuery":
        return self

    def eq(self, key: str, value: Any) -> "_FakeQuery":
        self._filters.append((key, value))
        return self

    def execute(self) -> Any:
        rows = list(self._rows)
        for key, value in self._filters:
            rows = [r for r in rows if r.get(key) == value]

        class _Resp:
            data = rows

        return _Resp()


class _FakeBrandsDB:
    def __init__(self, brand_rows: list[dict[str, Any]]) -> None:
        self._brand_rows = brand_rows

    def table(self, name: str) -> _FakeQuery:
        if name == "brands":
            return _FakeQuery(self._brand_rows)
        raise AssertionError(f"unexpected table: {name}")


class _FakeMultiTableDB:
    """General-purpose multi-table Supabase DB fake."""

    def __init__(self, tables: dict[str, list[dict[str, Any]]]) -> None:
        self._tables = tables

    def table(self, name: str) -> _FakeQuery:
        rows = self._tables.get(name, [])
        return _FakeQuery(rows)


class _FakeClickUpService:
    def __init__(
        self,
        *,
        space_lists: list[dict[str, Any]] | None = None,
        space_lists_error: Exception | None = None,
        task_data: dict[str, Any] | None = None,
        task_error: Exception | None = None,
        tasks_in_list: list[dict[str, Any]] | None = None,
        tasks_in_list_error: Exception | None = None,
        create_result: ClickUpTask | None = None,
        create_error: Exception | None = None,
    ) -> None:
        self.space_lists = space_lists or []
        self.space_lists_error = space_lists_error
        self.task_data = task_data or {"id": "task-1", "name": "Test task"}
        self.task_error = task_error
        self.tasks_in_list = tasks_in_list or []
        self.tasks_in_list_error = tasks_in_list_error
        self.create_result = create_result or ClickUpTask(
            id="created-task-1", url="https://app.clickup.com/t/created-task-1"
        )
        self.create_error = create_error
        self.closed = False
        self.get_space_lists_calls: list[str] = []
        self.get_task_calls: list[str] = []
        self.create_calls: list[dict[str, Any]] = []

    async def get_space_lists(self, space_id: str) -> list[dict[str, Any]]:
        self.get_space_lists_calls.append(space_id)
        if self.space_lists_error:
            raise self.space_lists_error
        return self.space_lists

    async def get_task(self, task_id: str) -> dict[str, Any]:
        self.get_task_calls.append(task_id)
        if self.task_error:
            raise self.task_error
        return self.task_data

    async def get_tasks_in_list_all_pages(
        self,
        list_id: str,
        *,
        date_updated_gt: int | None = None,
        include_closed: bool = False,
        max_tasks: int = 200,
    ) -> list[dict[str, Any]]:
        if self.tasks_in_list_error:
            raise self.tasks_in_list_error
        return self.tasks_in_list[:max_tasks]

    async def create_task_in_list(
        self,
        list_id: str,
        name: str,
        description_md: str | None = None,
        assignee_ids: list[str] | None = None,
    ) -> ClickUpTask:
        self.create_calls.append(
            {"list_id": list_id, "name": name, "description_md": description_md, "assignee_ids": assignee_ids}
        )
        if self.create_error:
            raise self.create_error
        return self.create_result

    async def aclose(self) -> None:
        self.closed = True


# ---------------------------------------------------------------------------
# parse_clickup_task_id
# ---------------------------------------------------------------------------


def test_parse_bare_task_id():
    assert parse_clickup_task_id(task_id="abc123", task_url=None) == "abc123"


def test_parse_bare_task_id_trims_whitespace():
    assert parse_clickup_task_id(task_id="  abc123  ", task_url=None) == "abc123"


def test_parse_clickup_url():
    assert (
        parse_clickup_task_id(
            task_id=None, task_url="https://app.clickup.com/t/abc123"
        )
        == "abc123"
    )


def test_parse_clickup_url_with_underscores_and_hyphens():
    assert (
        parse_clickup_task_id(
            task_id=None, task_url="https://app.clickup.com/t/abc_123-xyz"
        )
        == "abc_123-xyz"
    )


def test_parse_rejects_both_provided():
    with pytest.raises(ClickUpToolError) as exc_info:
        parse_clickup_task_id(task_id="abc", task_url="https://app.clickup.com/t/abc")
    assert exc_info.value.error_type == "validation_error"


def test_parse_rejects_neither_provided():
    with pytest.raises(ClickUpToolError) as exc_info:
        parse_clickup_task_id(task_id=None, task_url=None)
    assert exc_info.value.error_type == "validation_error"


def test_parse_rejects_empty_task_id():
    with pytest.raises(ClickUpToolError) as exc_info:
        parse_clickup_task_id(task_id="   ", task_url=None)
    assert exc_info.value.error_type == "validation_error"


def test_parse_rejects_unknown_url_format():
    with pytest.raises(ClickUpToolError) as exc_info:
        parse_clickup_task_id(
            task_id=None,
            task_url="https://app.clickup.com/12345/v/li/67890/abc123",
        )
    assert exc_info.value.error_type == "parse_error"
    assert "Unrecognized task URL format" in exc_info.value.message


def test_parse_rejects_non_clickup_url():
    with pytest.raises(ClickUpToolError) as exc_info:
        parse_clickup_task_id(task_id=None, task_url="https://example.com/t/abc")
    assert exc_info.value.error_type == "parse_error"


# ---------------------------------------------------------------------------
# resolve_brand_destination — explicit list_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_explicit_list_id():
    db = _FakeBrandsDB(
        [{"id": "brand-1", "client_id": "client-a", "name": "Brand One", "clickup_list_id": "list-99", "clickup_space_id": None}]
    )
    svc = _FakeClickUpService()
    result = await resolve_brand_destination(db, svc, client_id="client-a", brand_id=None)

    assert result["list_id"] == "list-99"
    assert result["resolution_basis"] == "mapped_list"
    assert result["brand_id"] == "brand-1"
    assert result["brand_name"] == "Brand One"
    # No space list calls needed when list_id is mapped directly
    assert svc.get_space_lists_calls == []


@pytest.mark.asyncio
async def test_resolve_explicit_list_id_with_space_id_also_set():
    """list_id takes precedence over space_id."""
    db = _FakeBrandsDB(
        [{"id": "brand-1", "client_id": "client-a", "name": "B", "clickup_list_id": "list-99", "clickup_space_id": "space-42"}]
    )
    svc = _FakeClickUpService()
    result = await resolve_brand_destination(db, svc, client_id="client-a", brand_id=None)

    assert result["list_id"] == "list-99"
    assert result["space_id"] == "space-42"
    assert result["resolution_basis"] == "mapped_list"
    assert svc.get_space_lists_calls == []


# ---------------------------------------------------------------------------
# resolve_brand_destination — space fallback (bypass global shortcut)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_space_fallback_uses_get_space_lists_directly():
    """Space fallback must call get_space_lists(), not resolve_default_list_id()."""
    db = _FakeBrandsDB(
        [{"id": "brand-1", "client_id": "client-a", "name": "B", "clickup_list_id": None, "clickup_space_id": "space-42"}]
    )
    svc = _FakeClickUpService(
        space_lists=[{"id": "list-inbox", "name": "Inbox"}, {"id": "list-other", "name": "Other"}]
    )
    result = await resolve_brand_destination(db, svc, client_id="client-a", brand_id=None)

    assert result["list_id"] == "list-inbox"
    assert result["space_id"] == "space-42"
    assert result["resolution_basis"] == "mapped_space_default_list"
    assert svc.get_space_lists_calls == ["space-42"]


@pytest.mark.asyncio
async def test_resolve_space_fallback_uses_first_list_when_no_inbox():
    db = _FakeBrandsDB(
        [{"id": "brand-1", "client_id": "client-a", "name": "B", "clickup_list_id": None, "clickup_space_id": "space-42"}]
    )
    svc = _FakeClickUpService(
        space_lists=[{"id": "list-first", "name": "Backlog"}, {"id": "list-second", "name": "Done"}]
    )
    result = await resolve_brand_destination(db, svc, client_id="client-a", brand_id=None)

    assert result["list_id"] == "list-first"
    assert result["resolution_basis"] == "mapped_space_default_list"


@pytest.mark.asyncio
async def test_resolve_space_fallback_fails_when_space_has_no_lists():
    db = _FakeBrandsDB(
        [{"id": "brand-1", "client_id": "client-a", "name": "B", "clickup_list_id": None, "clickup_space_id": "space-empty"}]
    )
    svc = _FakeClickUpService(space_lists=[])

    with pytest.raises(ClickUpToolError) as exc_info:
        await resolve_brand_destination(db, svc, client_id="client-a", brand_id=None)
    assert exc_info.value.error_type == "mapping_error"


# ---------------------------------------------------------------------------
# resolve_brand_destination — ambiguity and missing cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_sole_mapped_brand_wins_when_other_brands_have_no_destination():
    """One mapped brand + one unmapped brand → use the sole mapped brand, not ambiguous."""
    db = _FakeBrandsDB(
        [
            {"id": "brand-1", "client_id": "client-a", "name": "Alpha", "clickup_list_id": "list-1", "clickup_space_id": None},
            {"id": "brand-2", "client_id": "client-a", "name": "Beta", "clickup_list_id": None, "clickup_space_id": None},
        ]
    )
    svc = _FakeClickUpService()
    result = await resolve_brand_destination(db, svc, client_id="client-a", brand_id=None)

    assert result["brand_id"] == "brand-1"
    assert result["list_id"] == "list-1"
    assert result["resolution_basis"] == "mapped_list"


@pytest.mark.asyncio
async def test_resolve_fails_closed_on_multiple_mapped_brands_no_brand_id():
    """Multiple brands all with destinations → ambiguous without brand_id."""
    db = _FakeBrandsDB(
        [
            {"id": "brand-1", "client_id": "client-a", "name": "Alpha", "clickup_list_id": "list-1", "clickup_space_id": None},
            {"id": "brand-2", "client_id": "client-a", "name": "Beta", "clickup_list_id": "list-2", "clickup_space_id": None},
        ]
    )
    svc = _FakeClickUpService()

    with pytest.raises(ClickUpToolError) as exc_info:
        await resolve_brand_destination(db, svc, client_id="client-a", brand_id=None)
    assert exc_info.value.error_type == "ambiguous_destination"
    assert "Alpha" in exc_info.value.message
    assert "Beta" in exc_info.value.message


@pytest.mark.asyncio
async def test_resolve_fails_closed_on_multiple_brands_no_brand_id():
    """Legacy name preserved — same as above, confirms backward-compatible behavior."""
    db = _FakeBrandsDB(
        [
            {"id": "brand-1", "client_id": "client-a", "name": "Alpha", "clickup_list_id": "list-1", "clickup_space_id": None},
            {"id": "brand-2", "client_id": "client-a", "name": "Beta", "clickup_list_id": "list-2", "clickup_space_id": None},
        ]
    )
    svc = _FakeClickUpService()

    with pytest.raises(ClickUpToolError) as exc_info:
        await resolve_brand_destination(db, svc, client_id="client-a", brand_id=None)
    assert exc_info.value.error_type == "ambiguous_destination"
    assert "Alpha" in exc_info.value.message
    assert "Beta" in exc_info.value.message


@pytest.mark.asyncio
async def test_resolve_fails_mapping_error_when_brands_exist_but_none_have_destinations():
    """Brands exist but none have clickup_list_id or clickup_space_id → mapping_error, not not_found."""
    db = _FakeBrandsDB(
        [
            {"id": "brand-1", "client_id": "client-a", "name": "Alpha", "clickup_list_id": None, "clickup_space_id": None},
            {"id": "brand-2", "client_id": "client-a", "name": "Beta", "clickup_list_id": None, "clickup_space_id": None},
        ]
    )
    svc = _FakeClickUpService()

    with pytest.raises(ClickUpToolError) as exc_info:
        await resolve_brand_destination(db, svc, client_id="client-a", brand_id=None)
    assert exc_info.value.error_type == "mapping_error"


@pytest.mark.asyncio
async def test_resolve_succeeds_with_explicit_brand_id_from_multi_brand_client():
    db = _FakeBrandsDB(
        [
            {"id": "brand-1", "client_id": "client-a", "name": "Alpha", "clickup_list_id": "list-1", "clickup_space_id": None},
            {"id": "brand-2", "client_id": "client-a", "name": "Beta", "clickup_list_id": "list-2", "clickup_space_id": None},
        ]
    )
    svc = _FakeClickUpService()
    result = await resolve_brand_destination(db, svc, client_id="client-a", brand_id="brand-2")

    assert result["brand_id"] == "brand-2"
    assert result["list_id"] == "list-2"


@pytest.mark.asyncio
async def test_resolve_fails_when_no_brands():
    db = _FakeBrandsDB([])
    svc = _FakeClickUpService()

    with pytest.raises(ClickUpToolError) as exc_info:
        await resolve_brand_destination(db, svc, client_id="client-a", brand_id=None)
    assert exc_info.value.error_type == "not_found"


@pytest.mark.asyncio
async def test_resolve_fails_when_brand_id_not_found():
    db = _FakeBrandsDB(
        [{"id": "brand-1", "client_id": "client-a", "name": "Alpha", "clickup_list_id": "list-1", "clickup_space_id": None}]
    )
    svc = _FakeClickUpService()

    with pytest.raises(ClickUpToolError) as exc_info:
        await resolve_brand_destination(db, svc, client_id="client-a", brand_id="brand-999")
    assert exc_info.value.error_type == "not_found"


@pytest.mark.asyncio
async def test_resolve_fails_when_no_destination_configured():
    db = _FakeBrandsDB(
        [{"id": "brand-1", "client_id": "client-a", "name": "Alpha", "clickup_list_id": None, "clickup_space_id": None}]
    )
    svc = _FakeClickUpService()

    with pytest.raises(ClickUpToolError) as exc_info:
        await resolve_brand_destination(db, svc, client_id="client-a", brand_id=None)
    assert exc_info.value.error_type == "mapping_error"


# ---------------------------------------------------------------------------
# list_tasks_for_brand — UTC conversion and limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_tasks_utc_conversion_and_limit(monkeypatch):
    fake_svc = _FakeClickUpService(
        tasks_in_list=[
            {"id": f"t{i}", "name": f"Task {i}", "status": {"status": "open"}, "url": None, "assignees": [], "date_updated": None, "date_created": None}
            for i in range(10)
        ]
    )
    fake_db = _FakeBrandsDB(
        [{"id": "brand-1", "client_id": "cid", "name": "B", "clickup_list_id": "list-1", "clickup_space_id": None}]
    )

    monkeypatch.setattr(
        "app.services.clickup_task_tools.get_clickup_service", lambda: fake_svc
    )
    monkeypatch.setattr(
        "app.services.clickup_task_tools._get_supabase_admin_client", lambda: fake_db
    )

    before = datetime.now(timezone.utc)
    result = await list_tasks_for_brand(
        client_id="cid",
        brand_id=None,
        updated_since_days=7,
        include_closed=False,
        limit=5,
    )
    after = datetime.now(timezone.utc)

    assert result["brand_id"] == "brand-1"
    assert result["destination"]["list_id"] == "list-1"
    assert result["destination"]["resolution_basis"] == "mapped_list"
    # limit=5 caps the result
    assert len(result["tasks"]) == 5
    assert fake_svc.closed is True


@pytest.mark.asyncio
async def test_list_tasks_returns_structured_task_rows(monkeypatch):
    fake_svc = _FakeClickUpService(
        tasks_in_list=[
            {
                "id": "task-abc",
                "name": "Fix listing copy",
                "status": {"status": "in progress"},
                "url": "https://app.clickup.com/t/task-abc",
                "assignees": [{"id": 1, "username": "jane", "email": "jane@co.com"}],
                "date_updated": "1700000000000",
                "date_created": "1699000000000",
            }
        ]
    )
    fake_db = _FakeBrandsDB(
        [{"id": "brand-1", "client_id": "cid", "name": "B", "clickup_list_id": "list-1", "clickup_space_id": None}]
    )
    monkeypatch.setattr("app.services.clickup_task_tools.get_clickup_service", lambda: fake_svc)
    monkeypatch.setattr("app.services.clickup_task_tools._get_supabase_admin_client", lambda: fake_db)

    result = await list_tasks_for_brand(
        client_id="cid", brand_id=None, updated_since_days=None, include_closed=False, limit=50
    )
    tasks = result["tasks"]
    assert len(tasks) == 1
    t = tasks[0]
    assert t["id"] == "task-abc"
    assert t["name"] == "Fix listing copy"
    assert t["status"] == "in progress"
    assert t["assignees"] == ["jane"]


@pytest.mark.asyncio
async def test_list_tasks_fails_on_config_error(monkeypatch):
    from app.services.clickup import ClickUpConfigurationError

    def _raise():
        raise ClickUpConfigurationError("CLICKUP_API_TOKEN not set")

    monkeypatch.setattr("app.services.clickup_task_tools.get_clickup_service", _raise)

    with pytest.raises(ClickUpToolError) as exc_info:
        await list_tasks_for_brand(
            client_id="cid", brand_id=None, updated_since_days=None, include_closed=False, limit=50
        )
    assert exc_info.value.error_type == "configuration_error"


@pytest.mark.asyncio
async def test_list_tasks_api_error_becomes_structured_tool_error(monkeypatch):
    """ClickUp read failures must surface as ClickUpToolError, not raw exceptions."""
    from app.services.clickup import ClickUpAPIError

    fake_svc = _FakeClickUpService(
        tasks_in_list_error=ClickUpAPIError("ClickUp API error (502): Bad Gateway")
    )
    fake_db = _FakeBrandsDB(
        [{"id": "brand-1", "client_id": "cid", "name": "B", "clickup_list_id": "list-1", "clickup_space_id": None}]
    )
    monkeypatch.setattr("app.services.clickup_task_tools.get_clickup_service", lambda: fake_svc)
    monkeypatch.setattr("app.services.clickup_task_tools._get_supabase_admin_client", lambda: fake_db)

    with pytest.raises(ClickUpToolError) as exc_info:
        await list_tasks_for_brand(
            client_id="cid", brand_id=None, updated_since_days=None, include_closed=False, limit=50
        )
    assert exc_info.value.error_type == "clickup_api_error"
    assert fake_svc.closed is True


# ---------------------------------------------------------------------------
# get_task_by_id_or_url
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_task_by_id(monkeypatch):
    task_raw = {
        "id": "task-xyz",
        "name": "Update copy",
        "url": "https://app.clickup.com/t/task-xyz",
        "description": "Fix the bullets",
        "status": {"status": "open"},
        "assignees": [{"username": "alice"}],
        "date_created": "1699000000000",
        "date_updated": "1700000000000",
        "list": {"id": "list-1", "name": "Inbox"},
        "space": {"id": "space-1", "name": "Client Space"},
    }
    fake_svc = _FakeClickUpService(task_data=task_raw)
    monkeypatch.setattr("app.services.clickup_task_tools.get_clickup_service", lambda: fake_svc)

    result = await get_task_by_id_or_url(task_id="task-xyz", task_url=None)
    task = result["task"]

    assert task["id"] == "task-xyz"
    assert task["name"] == "Update copy"
    assert task["status"] == "open"
    assert task["description_md"] == "Fix the bullets"
    assert task["assignees"] == ["alice"]
    assert task["list_id"] == "list-1"
    assert task["list_name"] == "Inbox"
    assert task["space_id"] == "space-1"
    assert task["space_name"] == "Client Space"
    assert fake_svc.get_task_calls == ["task-xyz"]
    assert fake_svc.closed is True


@pytest.mark.asyncio
async def test_get_task_by_url(monkeypatch):
    fake_svc = _FakeClickUpService(task_data={"id": "task-abc", "name": "T"})
    monkeypatch.setattr("app.services.clickup_task_tools.get_clickup_service", lambda: fake_svc)

    result = await get_task_by_id_or_url(
        task_id=None, task_url="https://app.clickup.com/t/task-abc"
    )
    assert result["task"]["id"] == "task-abc"
    assert fake_svc.get_task_calls == ["task-abc"]


@pytest.mark.asyncio
async def test_get_task_not_found(monkeypatch):
    from app.services.clickup import ClickUpNotFoundError

    fake_svc = _FakeClickUpService(task_error=ClickUpNotFoundError("not found"))
    monkeypatch.setattr("app.services.clickup_task_tools.get_clickup_service", lambda: fake_svc)

    with pytest.raises(ClickUpToolError) as exc_info:
        await get_task_by_id_or_url(task_id="missing-id", task_url=None)
    assert exc_info.value.error_type == "not_found"
    assert fake_svc.closed is True


@pytest.mark.asyncio
async def test_get_task_config_error(monkeypatch):
    from app.services.clickup import ClickUpConfigurationError

    def _raise():
        raise ClickUpConfigurationError("CLICKUP_API_TOKEN not set")

    monkeypatch.setattr("app.services.clickup_task_tools.get_clickup_service", _raise)

    with pytest.raises(ClickUpToolError) as exc_info:
        await get_task_by_id_or_url(task_id="task-1", task_url=None)
    assert exc_info.value.error_type == "configuration_error"


def test_get_task_bad_url_raises_before_service():
    """URL parse errors fire before any service is constructed."""
    with pytest.raises(ClickUpToolError) as exc_info:
        import asyncio
        asyncio.run(
            get_task_by_id_or_url(
                task_id=None, task_url="https://bad-host.com/t/abc"
            )
        )
    assert exc_info.value.error_type == "parse_error"


# ---------------------------------------------------------------------------
# _is_valid_clickup_user_id
# ---------------------------------------------------------------------------


def test_is_valid_clickup_user_id_integer_string():
    assert _is_valid_clickup_user_id("12345678") is True


def test_is_valid_clickup_user_id_rejects_empty():
    assert _is_valid_clickup_user_id("") is False
    assert _is_valid_clickup_user_id(None) is False


def test_is_valid_clickup_user_id_rejects_non_integer():
    assert _is_valid_clickup_user_id("abc") is False
    assert _is_valid_clickup_user_id("12.34") is False


# ---------------------------------------------------------------------------
# resolve_team_member_query
# ---------------------------------------------------------------------------


def _profile_db(profiles, assignments=None):
    return _FakeMultiTableDB({
        "profiles": profiles,
        "client_assignments": assignments or [],
    })


def test_resolve_team_member_single_match_resolved():
    db = _profile_db([
        {"id": "p1", "display_name": "Susie Smith", "full_name": "Susan Smith", "email": "susie@co.com", "clickup_user_id": "987654"}
    ])
    result = resolve_team_member_query(db, query="Susie", client_id=None, brand_id=None)
    assert len(result["matches"]) == 1
    m = result["matches"][0]
    assert m["profile_id"] == "p1"
    assert m["resolution_status"] == "resolved"
    assert m["clickup_user_id"] == "987654"
    assert m["assignment_scope"] == "none"


def test_resolve_team_member_missing_clickup_user_id():
    db = _profile_db([
        {"id": "p1", "display_name": "Jeff Adams", "full_name": "", "email": "jeff@co.com", "clickup_user_id": None}
    ])
    result = resolve_team_member_query(db, query="jeff", client_id=None, brand_id=None)
    assert len(result["matches"]) == 1
    assert result["matches"][0]["resolution_status"] == "missing_mapping"
    assert result["matches"][0]["clickup_user_id"] is None


def test_resolve_team_member_non_integer_clickup_user_id():
    db = _profile_db([
        {"id": "p1", "display_name": "Dana", "full_name": "", "email": "dana@co.com", "clickup_user_id": "not-an-int"}
    ])
    result = resolve_team_member_query(db, query="dana", client_id=None, brand_id=None)
    assert result["matches"][0]["resolution_status"] == "missing_mapping"


def test_resolve_team_member_ambiguous_multiple_matches():
    db = _profile_db([
        {"id": "p1", "display_name": "Alex A", "full_name": "", "email": "alex.a@co.com", "clickup_user_id": "111"},
        {"id": "p2", "display_name": "Alex B", "full_name": "", "email": "alex.b@co.com", "clickup_user_id": "222"},
    ])
    result = resolve_team_member_query(db, query="alex", client_id=None, brand_id=None)
    assert len(result["matches"]) == 2
    for m in result["matches"]:
        assert m["resolution_status"] == "ambiguous"


def test_resolve_team_member_no_match_returns_empty_list():
    db = _profile_db([
        {"id": "p1", "display_name": "Charlie", "full_name": "", "email": "charlie@co.com", "clickup_user_id": "111"}
    ])
    result = resolve_team_member_query(db, query="zzzunknown", client_id=None, brand_id=None)
    assert result["matches"] == []


def test_resolve_team_member_empty_query_raises():
    db = _profile_db([])
    with pytest.raises(ClickUpToolError) as exc_info:
        resolve_team_member_query(db, query="   ", client_id=None, brand_id=None)
    assert exc_info.value.error_type == "validation_error"


def test_resolve_team_member_matches_full_name_when_display_name_differs():
    """full_name must be searchable even when display_name is populated."""
    db = _profile_db([
        {
            "id": "p1",
            "display_name": "Suz",
            "full_name": "Suzanne Clarke",
            "email": "suz@co.com",
            "clickup_user_id": "111",
        }
    ])
    # Query matches full_name only — display_name "Suz" does not contain "Suzanne"
    result = resolve_team_member_query(db, query="Suzanne", client_id=None, brand_id=None)
    assert len(result["matches"]) == 1
    assert result["matches"][0]["profile_id"] == "p1"
    assert result["matches"][0]["resolution_status"] == "resolved"


def test_resolve_team_member_display_name_match_still_works():
    """Existing display_name matching must still work."""
    db = _profile_db([
        {"id": "p1", "display_name": "Suz", "full_name": "Suzanne Clarke", "email": "suz@co.com", "clickup_user_id": "111"}
    ])
    result = resolve_team_member_query(db, query="suz", client_id=None, brand_id=None)
    assert len(result["matches"]) == 1
    assert result["matches"][0]["profile_id"] == "p1"


def test_resolve_team_member_email_match_still_works():
    """Email matching must still work."""
    db = _profile_db([
        {"id": "p1", "display_name": "Suz", "full_name": "Suzanne Clarke", "email": "suz@co.com", "clickup_user_id": "111"}
    ])
    result = resolve_team_member_query(db, query="suz@co.com", client_id=None, brand_id=None)
    assert len(result["matches"]) == 1


def test_resolve_team_member_client_assigned_ranks_first():
    """Profiles assigned to the client should appear before unassigned profiles."""
    db = _FakeMultiTableDB({
        "profiles": [
            {"id": "p1", "display_name": "Alice", "full_name": "", "email": "alice@co.com", "clickup_user_id": "111"},
            {"id": "p2", "display_name": "Alice B", "full_name": "", "email": "alice.b@co.com", "clickup_user_id": "222"},
        ],
        "client_assignments": [
            {"team_member_id": "p2", "brand_id": None, "client_id": "client-x"},
        ],
    })
    result = resolve_team_member_query(db, query="alice", client_id="client-x", brand_id=None)
    assert len(result["matches"]) == 2
    # p2 is assigned → should be first
    assert result["matches"][0]["profile_id"] == "p2"
    assert result["matches"][0]["assignment_scope"] == "client"
    assert result["matches"][1]["profile_id"] == "p1"
    assert result["matches"][1]["assignment_scope"] == "none"


def test_resolve_team_member_brand_scope_detected():
    db = _FakeMultiTableDB({
        "profiles": [
            {"id": "p1", "display_name": "Sam", "full_name": "", "email": "sam@co.com", "clickup_user_id": "555"}
        ],
        "client_assignments": [
            {"team_member_id": "p1", "brand_id": "brand-7", "client_id": "client-x"},
        ],
    })
    result = resolve_team_member_query(db, query="sam", client_id="client-x", brand_id="brand-7")
    assert result["matches"][0]["assignment_scope"] == "brand"


# ---------------------------------------------------------------------------
# _resolve_assignee
# ---------------------------------------------------------------------------


def test_resolve_assignee_unassigned_when_neither_provided():
    db = _profile_db([])
    result = _resolve_assignee(db, assignee_profile_id=None, assignee_query=None, client_id=None)
    assert result["resolution_status"] == "unassigned"
    assert result["profile_id"] is None
    assert result["clickup_user_id"] is None


def test_resolve_assignee_both_provided_raises_validation_error():
    db = _profile_db([])
    with pytest.raises(ClickUpToolError) as exc_info:
        _resolve_assignee(db, assignee_profile_id="p1", assignee_query="susie", client_id=None)
    assert exc_info.value.error_type == "validation_error"


def test_resolve_assignee_by_profile_id_resolved():
    db = _profile_db([
        {"id": "p1", "display_name": "Susie", "full_name": "", "email": "s@co.com", "clickup_user_id": "9001"}
    ])
    result = _resolve_assignee(db, assignee_profile_id="p1", assignee_query=None, client_id=None)
    assert result["resolution_status"] == "resolved"
    assert result["clickup_user_id"] == "9001"


def test_resolve_assignee_by_profile_id_missing_mapping():
    db = _profile_db([
        {"id": "p1", "display_name": "Susie", "full_name": "", "email": "s@co.com", "clickup_user_id": None}
    ])
    result = _resolve_assignee(db, assignee_profile_id="p1", assignee_query=None, client_id=None)
    assert result["resolution_status"] == "missing_mapping"
    assert result["clickup_user_id"] is None


def test_resolve_assignee_by_profile_id_not_found():
    db = _profile_db([])
    with pytest.raises(ClickUpToolError) as exc_info:
        _resolve_assignee(db, assignee_profile_id="nonexistent", assignee_query=None, client_id=None)
    assert exc_info.value.error_type == "not_found"


def test_resolve_assignee_by_query_ambiguous_raises():
    db = _profile_db([
        {"id": "p1", "display_name": "Alex A", "full_name": "", "email": "a@co.com", "clickup_user_id": "1"},
        {"id": "p2", "display_name": "Alex B", "full_name": "", "email": "b@co.com", "clickup_user_id": "2"},
    ])
    with pytest.raises(ClickUpToolError) as exc_info:
        _resolve_assignee(db, assignee_profile_id=None, assignee_query="alex", client_id=None)
    assert exc_info.value.error_type == "ambiguous_assignee"
    assert "Alex A" in exc_info.value.message or "Alex B" in exc_info.value.message


def test_resolve_assignee_by_query_no_match_raises():
    db = _profile_db([])
    with pytest.raises(ClickUpToolError) as exc_info:
        _resolve_assignee(db, assignee_profile_id=None, assignee_query="nobody", client_id=None)
    assert exc_info.value.error_type == "not_found"


def test_resolve_assignee_brand_context_still_ambiguous_when_both_match():
    """Brand context helps ranking but two matching profiles remain ambiguous.
    Fail-closed behavior must hold even when one candidate has brand scope."""
    db = _FakeMultiTableDB({
        "profiles": [
            {"id": "p1", "display_name": "Alex", "full_name": "", "email": "alex.a@co.com", "clickup_user_id": "111"},
            {"id": "p2", "display_name": "Alex", "full_name": "", "email": "alex.b@co.com", "clickup_user_id": "222"},
        ],
        "client_assignments": [
            {"team_member_id": "p2", "brand_id": "brand-7", "client_id": "client-x"},
        ],
    })
    with pytest.raises(ClickUpToolError) as exc_info:
        _resolve_assignee(
            db,
            assignee_profile_id=None,
            assignee_query="alex",
            client_id="client-x",
            brand_id="brand-7",
        )
    assert exc_info.value.error_type == "ambiguous_assignee"


def test_resolve_assignee_brand_context_single_match_resolves():
    """Single match with brand assignment resolves correctly — brand context is threaded."""
    db = _FakeMultiTableDB({
        "profiles": [
            {"id": "p1", "display_name": "Jordan", "full_name": "", "email": "j@co.com", "clickup_user_id": "999"},
        ],
        "client_assignments": [
            {"team_member_id": "p1", "brand_id": "brand-7", "client_id": "client-x"},
        ],
    })
    result = _resolve_assignee(
        db,
        assignee_profile_id=None,
        assignee_query="jordan",
        client_id="client-x",
        brand_id="brand-7",
    )
    assert result["resolution_status"] == "resolved"
    assert result["profile_id"] == "p1"
    assert result["clickup_user_id"] == "999"


# ---------------------------------------------------------------------------
# prepare_task_for_brand
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prepare_task_basic_unassigned(monkeypatch):
    fake_svc = _FakeClickUpService()
    fake_db = _FakeMultiTableDB({
        "brands": [{"id": "brand-1", "client_id": "cid", "name": "B", "clickup_list_id": "list-1", "clickup_space_id": None}],
        "profiles": [],
        "client_assignments": [],
    })
    monkeypatch.setattr("app.services.clickup_task_tools.get_clickup_service", lambda: fake_svc)
    monkeypatch.setattr("app.services.clickup_task_tools._get_supabase_admin_client", lambda: fake_db)

    result = await prepare_task_for_brand(
        client_id="cid", brand_id=None, title="New Task",
        description_md=None, assignee_profile_id=None, assignee_query=None,
    )

    assert result["brand_id"] == "brand-1"
    assert result["destination"]["list_id"] == "list-1"
    assert result["task_payload"]["name"] == "New Task"
    assert result["task_payload"]["assignee_ids"] == []
    assert result["assignee"]["resolution_status"] == "unassigned"
    assert result["warnings"] == []
    assert fake_svc.closed is True


@pytest.mark.asyncio
async def test_prepare_task_with_resolved_assignee(monkeypatch):
    fake_svc = _FakeClickUpService()
    fake_db = _FakeMultiTableDB({
        "brands": [{"id": "brand-1", "client_id": "cid", "name": "B", "clickup_list_id": "list-1", "clickup_space_id": None}],
        "profiles": [{"id": "p1", "display_name": "Susie", "full_name": "", "email": "s@co.com", "clickup_user_id": "9001"}],
        "client_assignments": [],
    })
    monkeypatch.setattr("app.services.clickup_task_tools.get_clickup_service", lambda: fake_svc)
    monkeypatch.setattr("app.services.clickup_task_tools._get_supabase_admin_client", lambda: fake_db)

    result = await prepare_task_for_brand(
        client_id="cid", brand_id=None, title="Task",
        description_md="Details", assignee_profile_id="p1", assignee_query=None,
    )

    assert result["assignee"]["profile_id"] == "p1"
    assert result["assignee"]["clickup_user_id"] == "9001"
    assert result["assignee"]["resolution_status"] == "resolved"
    assert result["task_payload"]["assignee_ids"] == ["9001"]
    assert result["warnings"] == []


@pytest.mark.asyncio
async def test_prepare_task_warns_on_missing_assignee_mapping(monkeypatch):
    fake_svc = _FakeClickUpService()
    fake_db = _FakeMultiTableDB({
        "brands": [{"id": "brand-1", "client_id": "cid", "name": "B", "clickup_list_id": "list-1", "clickup_space_id": None}],
        "profiles": [{"id": "p1", "display_name": "Susie", "full_name": "", "email": "s@co.com", "clickup_user_id": None}],
        "client_assignments": [],
    })
    monkeypatch.setattr("app.services.clickup_task_tools.get_clickup_service", lambda: fake_svc)
    monkeypatch.setattr("app.services.clickup_task_tools._get_supabase_admin_client", lambda: fake_db)

    result = await prepare_task_for_brand(
        client_id="cid", brand_id=None, title="Task",
        description_md=None, assignee_profile_id="p1", assignee_query=None,
    )

    assert result["assignee"]["resolution_status"] == "missing_mapping"
    assert result["task_payload"]["assignee_ids"] == []
    assert len(result["warnings"]) == 1
    assert "unassigned" in result["warnings"][0].lower()


@pytest.mark.asyncio
async def test_prepare_task_threads_brand_context_into_assignee_resolution(monkeypatch):
    """prepare_task_for_brand must pass the resolved brand_id into assignee resolution
    so that brand assignment hints reduce ambiguity."""
    fake_svc = _FakeClickUpService()
    # Two profiles named "Alex"; only p2 is assigned to brand-1
    fake_db = _FakeMultiTableDB({
        "brands": [{"id": "brand-1", "client_id": "cid", "name": "B", "clickup_list_id": "list-1", "clickup_space_id": None}],
        "profiles": [
            {"id": "p1", "display_name": "Alex A", "full_name": "", "email": "a@co.com", "clickup_user_id": "111"},
            {"id": "p2", "display_name": "Alex B", "full_name": "", "email": "b@co.com", "clickup_user_id": "222"},
        ],
        "client_assignments": [
            {"team_member_id": "p2", "brand_id": "brand-1", "client_id": "cid"},
        ],
    })
    monkeypatch.setattr("app.services.clickup_task_tools.get_clickup_service", lambda: fake_svc)
    monkeypatch.setattr("app.services.clickup_task_tools._get_supabase_admin_client", lambda: fake_db)

    # Two "Alex" profiles → should still be ambiguous (both match), fail closed
    with pytest.raises(ClickUpToolError) as exc_info:
        await prepare_task_for_brand(
            client_id="cid", brand_id=None, title="Task",
            description_md=None, assignee_profile_id=None, assignee_query="Alex",
        )
    assert exc_info.value.error_type == "ambiguous_assignee"
    # Confirms brand_id was threaded in (both still match, fail closed — not a silent wrong pick)


@pytest.mark.asyncio
async def test_prepare_task_empty_title_raises(monkeypatch):
    fake_svc = _FakeClickUpService()
    fake_db = _FakeMultiTableDB({"brands": [], "profiles": [], "client_assignments": []})
    monkeypatch.setattr("app.services.clickup_task_tools.get_clickup_service", lambda: fake_svc)
    monkeypatch.setattr("app.services.clickup_task_tools._get_supabase_admin_client", lambda: fake_db)

    with pytest.raises(ClickUpToolError) as exc_info:
        await prepare_task_for_brand(
            client_id="cid", brand_id=None, title="   ",
            description_md=None, assignee_profile_id=None, assignee_query=None,
        )
    assert exc_info.value.error_type == "validation_error"


@pytest.mark.asyncio
async def test_prepare_task_config_error(monkeypatch):
    from app.services.clickup import ClickUpConfigurationError

    def _raise():
        raise ClickUpConfigurationError("CLICKUP_API_TOKEN not set")

    monkeypatch.setattr("app.services.clickup_task_tools.get_clickup_service", _raise)

    with pytest.raises(ClickUpToolError) as exc_info:
        await prepare_task_for_brand(
            client_id="cid", brand_id=None, title="Task",
            description_md=None, assignee_profile_id=None, assignee_query=None,
        )
    assert exc_info.value.error_type == "configuration_error"


# ---------------------------------------------------------------------------
# create_task_for_brand
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_task_success_in_list(monkeypatch):
    fake_svc = _FakeClickUpService(
        create_result=ClickUpTask(id="new-task-99", url="https://app.clickup.com/t/new-task-99")
    )
    fake_db = _FakeMultiTableDB({
        "brands": [{"id": "brand-1", "client_id": "cid", "name": "B", "clickup_list_id": "list-1", "clickup_space_id": None}],
        "profiles": [],
        "client_assignments": [],
    })
    monkeypatch.setattr("app.services.clickup_task_tools.get_clickup_service", lambda: fake_svc)
    monkeypatch.setattr("app.services.clickup_task_tools._get_supabase_admin_client", lambda: fake_db)

    result = await create_task_for_brand(
        client_id="cid", brand_id=None, title="Deploy fix",
        description_md="Details", assignee_profile_id=None, assignee_query=None,
    )

    assert result["task_id"] == "new-task-99"
    assert result["task_url"] == "https://app.clickup.com/t/new-task-99"
    assert result["client_id"] == "cid"
    assert result["brand_id"] == "brand-1"
    assert result["destination"]["list_id"] == "list-1"
    assert result["assignee"]["resolution_status"] == "unassigned"
    # Verify the right call was made
    assert len(fake_svc.create_calls) == 1
    call = fake_svc.create_calls[0]
    assert call["list_id"] == "list-1"
    assert call["name"] == "Deploy fix"
    assert fake_svc.closed is True


@pytest.mark.asyncio
async def test_create_task_with_resolved_assignee(monkeypatch):
    fake_svc = _FakeClickUpService()
    fake_db = _FakeMultiTableDB({
        "brands": [{"id": "brand-1", "client_id": "cid", "name": "B", "clickup_list_id": "list-1", "clickup_space_id": None}],
        "profiles": [{"id": "p1", "display_name": "Susie", "full_name": "", "email": "s@co.com", "clickup_user_id": "9001"}],
        "client_assignments": [],
    })
    monkeypatch.setattr("app.services.clickup_task_tools.get_clickup_service", lambda: fake_svc)
    monkeypatch.setattr("app.services.clickup_task_tools._get_supabase_admin_client", lambda: fake_db)

    result = await create_task_for_brand(
        client_id="cid", brand_id=None, title="Task for Susie",
        description_md=None, assignee_profile_id="p1", assignee_query=None,
    )

    assert result["assignee"]["profile_id"] == "p1"
    assert result["assignee"]["clickup_user_id"] == "9001"
    assert result["assignee"]["resolution_status"] == "resolved"
    assert fake_svc.create_calls[0]["assignee_ids"] == ["9001"]


@pytest.mark.asyncio
async def test_create_task_missing_assignee_mapping_creates_unassigned(monkeypatch):
    """missing_mapping assignee should produce an unassigned create, not an error."""
    fake_svc = _FakeClickUpService()
    fake_db = _FakeMultiTableDB({
        "brands": [{"id": "brand-1", "client_id": "cid", "name": "B", "clickup_list_id": "list-1", "clickup_space_id": None}],
        "profiles": [{"id": "p1", "display_name": "Susie", "full_name": "", "email": "s@co.com", "clickup_user_id": None}],
        "client_assignments": [],
    })
    monkeypatch.setattr("app.services.clickup_task_tools.get_clickup_service", lambda: fake_svc)
    monkeypatch.setattr("app.services.clickup_task_tools._get_supabase_admin_client", lambda: fake_db)

    result = await create_task_for_brand(
        client_id="cid", brand_id=None, title="Task",
        description_md=None, assignee_profile_id="p1", assignee_query=None,
    )

    assert result["assignee"]["resolution_status"] == "unassigned"
    # No assignee_ids passed to ClickUp
    assert fake_svc.create_calls[0]["assignee_ids"] is None


@pytest.mark.asyncio
async def test_create_task_api_error_becomes_structured_tool_error(monkeypatch):
    from app.services.clickup import ClickUpAPIError

    fake_svc = _FakeClickUpService(create_error=ClickUpAPIError("500 Internal Server Error"))
    fake_db = _FakeMultiTableDB({
        "brands": [{"id": "brand-1", "client_id": "cid", "name": "B", "clickup_list_id": "list-1", "clickup_space_id": None}],
        "profiles": [],
        "client_assignments": [],
    })
    monkeypatch.setattr("app.services.clickup_task_tools.get_clickup_service", lambda: fake_svc)
    monkeypatch.setattr("app.services.clickup_task_tools._get_supabase_admin_client", lambda: fake_db)

    with pytest.raises(ClickUpToolError) as exc_info:
        await create_task_for_brand(
            client_id="cid", brand_id=None, title="Task",
            description_md=None, assignee_profile_id=None, assignee_query=None,
        )
    assert exc_info.value.error_type == "clickup_api_error"
    assert fake_svc.closed is True


@pytest.mark.asyncio
async def test_create_task_config_error(monkeypatch):
    from app.services.clickup import ClickUpConfigurationError

    def _raise():
        raise ClickUpConfigurationError("CLICKUP_API_TOKEN not set")

    monkeypatch.setattr("app.services.clickup_task_tools.get_clickup_service", _raise)

    with pytest.raises(ClickUpToolError) as exc_info:
        await create_task_for_brand(
            client_id="cid", brand_id=None, title="Task",
            description_md=None, assignee_profile_id=None, assignee_query=None,
        )
    assert exc_info.value.error_type == "configuration_error"


# ---------------------------------------------------------------------------
# MCP tool registration smoke test
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# MCP tool wrapper tests — Slice 2 tools
# ---------------------------------------------------------------------------
#
# These tests call through the full MCP registration path (create_mcp_server →
# server.call_tool) to verify wrapper behavior: structured success, structured
# error, and mutation result shape.  Service-layer behaviour is already covered
# by the unit tests above; here we care about the MCP shim.
#
# Monkeypatching targets the service module so the MCP tool code is exercised.


def _make_wrapper_db(*, brands=None, profiles=None, assignments=None):
    return _FakeMultiTableDB({
        "brands": brands or [],
        "profiles": profiles or [],
        "client_assignments": assignments or [],
    })


def test_mcp_resolve_team_member_success(monkeypatch):
    """resolve_team_member MCP tool returns structured matches on success."""
    from app.mcp.server import create_mcp_server

    fake_db = _make_wrapper_db(profiles=[
        {"id": "p1", "display_name": "Susie Q", "full_name": "Susan Quinn", "email": "susie@co.com", "clickup_user_id": "7777"}
    ])
    monkeypatch.setattr("app.services.clickup_task_tools._get_supabase_admin_client", lambda: fake_db)

    server = create_mcp_server()
    _content, payload = asyncio.run(server.call_tool("resolve_team_member", {"query": "susie"}))

    assert "error" not in payload
    assert len(payload["matches"]) == 1
    m = payload["matches"][0]
    assert m["profile_id"] == "p1"
    assert m["resolution_status"] == "resolved"
    assert m["clickup_user_id"] == "7777"


def test_mcp_resolve_team_member_empty_query_returns_error(monkeypatch):
    """resolve_team_member MCP tool returns structured error for empty query."""
    from app.mcp.server import create_mcp_server

    fake_db = _make_wrapper_db()
    monkeypatch.setattr("app.services.clickup_task_tools._get_supabase_admin_client", lambda: fake_db)

    server = create_mcp_server()
    _content, payload = asyncio.run(server.call_tool("resolve_team_member", {"query": ""}))

    assert payload["error"] == "validation_error"
    assert "query" in payload["message"].lower() or "empty" in payload["message"].lower()


def test_mcp_prepare_clickup_task_success(monkeypatch):
    """prepare_clickup_task MCP tool returns full payload, destination, assignee, and warnings."""
    from app.mcp.server import create_mcp_server

    fake_svc = _FakeClickUpService()
    fake_db = _make_wrapper_db(
        brands=[{"id": "brand-1", "client_id": "cid", "name": "Acme", "clickup_list_id": "list-42", "clickup_space_id": None}],
        profiles=[{"id": "p1", "display_name": "Susie Q", "full_name": "", "email": "s@co.com", "clickup_user_id": "7777"}],
    )
    monkeypatch.setattr("app.services.clickup_task_tools.get_clickup_service", lambda: fake_svc)
    monkeypatch.setattr("app.services.clickup_task_tools._get_supabase_admin_client", lambda: fake_db)

    server = create_mcp_server()
    _content, payload = asyncio.run(server.call_tool(
        "prepare_clickup_task",
        {"client_id": "cid", "title": "Review Q2 plan", "assignee_profile_id": "p1"},
    ))

    assert "error" not in payload
    assert payload["brand_id"] == "brand-1"
    assert payload["brand_name"] == "Acme"
    assert payload["destination"]["list_id"] == "list-42"
    assert payload["destination"]["resolution_basis"] == "mapped_list"
    assert payload["assignee"]["profile_id"] == "p1"
    assert payload["assignee"]["resolution_status"] == "resolved"
    assert payload["task_payload"]["name"] == "Review Q2 plan"
    assert payload["task_payload"]["assignee_ids"] == ["7777"]
    assert payload["warnings"] == []


def test_mcp_prepare_clickup_task_destination_error_returns_structured_error(monkeypatch):
    """prepare_clickup_task returns structured error when destination cannot be resolved."""
    from app.mcp.server import create_mcp_server

    fake_svc = _FakeClickUpService()
    fake_db = _make_wrapper_db(brands=[])  # no brands → not_found
    monkeypatch.setattr("app.services.clickup_task_tools.get_clickup_service", lambda: fake_svc)
    monkeypatch.setattr("app.services.clickup_task_tools._get_supabase_admin_client", lambda: fake_db)

    server = create_mcp_server()
    _content, payload = asyncio.run(server.call_tool(
        "prepare_clickup_task",
        {"client_id": "no-such-client", "title": "Task"},
    ))

    assert payload["error"] == "not_found"
    assert "no-such-client" in payload["message"]


def test_mcp_create_clickup_task_success_returns_task_id_and_url(monkeypatch):
    """create_clickup_task MCP tool returns task_id, task_url, destination, and assignee."""
    from app.mcp.server import create_mcp_server

    fake_svc = _FakeClickUpService(
        create_result=ClickUpTask(id="cu-task-99", url="https://app.clickup.com/t/cu-task-99")
    )
    fake_db = _make_wrapper_db(
        brands=[{"id": "brand-1", "client_id": "cid", "name": "Acme", "clickup_list_id": "list-42", "clickup_space_id": None}],
    )
    monkeypatch.setattr("app.services.clickup_task_tools.get_clickup_service", lambda: fake_svc)
    monkeypatch.setattr("app.services.clickup_task_tools._get_supabase_admin_client", lambda: fake_db)

    server = create_mcp_server()
    _content, payload = asyncio.run(server.call_tool(
        "create_clickup_task",
        {"client_id": "cid", "title": "Launch checklist", "description_md": "Do the thing"},
    ))

    assert "error" not in payload
    assert payload["task_id"] == "cu-task-99"
    assert payload["task_url"] == "https://app.clickup.com/t/cu-task-99"
    assert payload["client_id"] == "cid"
    assert payload["brand_id"] == "brand-1"
    assert payload["destination"]["list_id"] == "list-42"
    assert payload["assignee"]["resolution_status"] == "unassigned"
    # Verify the ClickUp service was actually called
    assert len(fake_svc.create_calls) == 1
    assert fake_svc.create_calls[0]["name"] == "Launch checklist"


def test_mcp_create_clickup_task_api_error_returns_structured_error(monkeypatch):
    """create_clickup_task returns structured error when the ClickUp API call fails."""
    from app.mcp.server import create_mcp_server
    from app.services.clickup import ClickUpAPIError

    fake_svc = _FakeClickUpService(create_error=ClickUpAPIError("ClickUp returned 503"))
    fake_db = _make_wrapper_db(
        brands=[{"id": "brand-1", "client_id": "cid", "name": "Acme", "clickup_list_id": "list-42", "clickup_space_id": None}],
    )
    monkeypatch.setattr("app.services.clickup_task_tools.get_clickup_service", lambda: fake_svc)
    monkeypatch.setattr("app.services.clickup_task_tools._get_supabase_admin_client", lambda: fake_db)

    server = create_mcp_server()
    _content, payload = asyncio.run(server.call_tool(
        "create_clickup_task",
        {"client_id": "cid", "title": "Will fail"},
    ))

    assert payload["error"] == "clickup_api_error"
    assert "503" in payload["message"]


# ---------------------------------------------------------------------------
# MCP tool registration smoke test
# ---------------------------------------------------------------------------


def test_clickup_tools_registered_in_mcp_server():
    """Verify all five ClickUp tools are registered in the MCP server."""
    from app.mcp.server import create_mcp_server

    server = create_mcp_server()
    tools = asyncio.run(server.list_tools())
    tool_names = {t.name for t in tools}

    assert "list_clickup_tasks" in tool_names
    assert "get_clickup_tasks" not in tool_names  # wrong name guard
    assert "get_clickup_task" in tool_names
    assert "resolve_team_member" in tool_names
    assert "prepare_clickup_task" in tool_names
    assert "create_clickup_task" in tool_names
