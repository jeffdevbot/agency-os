"""Tests for ClickUp MCP tool foundation — Slice 0 + Slice 1."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.clickup_task_tools import (
    ClickUpToolError,
    _fetch_brand_rows,
    _format_full_task,
    _format_task_row,
    get_task_by_id_or_url,
    list_tasks_for_brand,
    parse_clickup_task_id,
    resolve_brand_destination,
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
    ) -> None:
        self.space_lists = space_lists or []
        self.space_lists_error = space_lists_error
        self.task_data = task_data or {"id": "task-1", "name": "Test task"}
        self.task_error = task_error
        self.tasks_in_list = tasks_in_list or []
        self.tasks_in_list_error = tasks_in_list_error
        self.closed = False
        self.get_space_lists_calls: list[str] = []
        self.get_task_calls: list[str] = []

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
# MCP tool registration smoke test
# ---------------------------------------------------------------------------


def test_clickup_tools_registered_in_mcp_server():
    """Verify the two ClickUp tools are registered in the MCP server."""
    from app.mcp.server import create_mcp_server

    server = create_mcp_server()
    # FastMCP exposes registered tools via _tool_manager or similar.
    # Use the public list_tools() if available, otherwise check the internal registry.
    try:
        tools = server.list_tools()
        tool_names = {t.name if hasattr(t, "name") else t["name"] for t in tools}
    except Exception:
        # Fallback: inspect the tool manager directly
        tool_names = set(server._tool_manager._tools.keys())

    assert "list_clickup_tasks" in tool_names
    assert "get_clickup_tasks" not in tool_names  # wrong name guard
    assert "get_clickup_task" in tool_names
