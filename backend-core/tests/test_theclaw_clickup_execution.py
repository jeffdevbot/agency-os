"""Tests for The Claw ClickUp execution helper (Phase 3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.services.theclaw.clickup_execution import (
    ClickUpExecutionResult,
    _build_task_description_md,
    _find_draft_task_by_id,
    execute_confirmed_task_creation,
)
from app.services.theclaw.runtime_state import (
    SESSION_DRAFT_TASKS_KEY,
    SESSION_PENDING_CONFIRMATION_KEY,
)


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FakeClickUpTask:
    id: str
    url: str | None = None


class FakeClickUpService:
    """In-memory ClickUp service for testing."""

    def __init__(
        self,
        *,
        spaces: list[dict[str, Any]] | None = None,
        create_result: FakeClickUpTask | None = None,
        create_error: Exception | None = None,
        list_spaces_error: Exception | None = None,
    ) -> None:
        self.spaces = spaces or []
        self.create_result = create_result or FakeClickUpTask(id="cu_999", url="https://app.clickup.com/t/cu_999")
        self.create_error = create_error
        self.list_spaces_error = list_spaces_error
        self.created_tasks: list[dict[str, Any]] = []
        self.closed = False

    async def list_spaces(self, *, team_id: str | None = None) -> list[dict[str, Any]]:
        if self.list_spaces_error:
            raise self.list_spaces_error
        return self.spaces

    async def create_task_in_space(
        self,
        space_id: str,
        name: str,
        description_md: str | None = None,
        assignee_ids: list[str] | None = None,
        override_list_id: str | None = None,
    ) -> FakeClickUpTask:
        if self.create_error:
            raise self.create_error
        self.created_tasks.append(
            {"space_id": space_id, "name": name, "description_md": description_md}
        )
        return self.create_result

    async def aclose(self) -> None:
        self.closed = True


def _make_session_context(
    *,
    draft_tasks: list[dict[str, Any]] | None = None,
    resolved_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ctx: dict[str, Any] = {}
    if draft_tasks is not None:
        ctx["theclaw_draft_tasks_v1"] = draft_tasks
    if resolved_context is not None:
        ctx["theclaw_resolved_context_v1"] = resolved_context
    return ctx


def _make_pending(
    *,
    task_id: str = "task-abc",
    task_title: str = "Launch campaign",
    clickup_space_id: str | None = None,
    clickup_space: str | None = None,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "task_title": task_title,
        "clickup_space_id": clickup_space_id,
        "clickup_space": clickup_space,
        "status": "pending",
        "notes": None,
    }


def _make_draft_task(
    *,
    task_id: str = "task-abc",
    title: str = "Launch campaign",
    status: str = "draft",
    clickup_task_id: str | None = None,
    clickup_task_url: str | None = None,
) -> dict[str, Any]:
    task: dict[str, Any] = {
        "id": task_id,
        "title": title,
        "marketplace": "US",
        "type": "PPC",
        "description": "Set up PPC campaign",
        "action": "Launch sponsored product ads",
        "specifics": None,
        "target_metric": "ACOS < 30%",
        "start_date": "2026-03-01",
        "deadline": "2026-03-15",
        "coupon_window": "N/A",
        "reference_docs": None,
        "source": "meeting_notes",
        "status": status,
        "asin_list": ["B0TESTTEST"],
    }
    if clickup_task_id:
        task["clickup_task_id"] = clickup_task_id
    if clickup_task_url:
        task["clickup_task_url"] = clickup_task_url
    return task


# ---------------------------------------------------------------------------
# Unit tests: _find_draft_task_by_id
# ---------------------------------------------------------------------------


def test_find_draft_task_by_id_found():
    tasks = [_make_draft_task(task_id="t1"), _make_draft_task(task_id="t2")]
    assert _find_draft_task_by_id(draft_tasks=tasks, task_id="t2") is tasks[1]


def test_find_draft_task_by_id_not_found():
    tasks = [_make_draft_task(task_id="t1")]
    assert _find_draft_task_by_id(draft_tasks=tasks, task_id="missing") is None


def test_find_draft_task_by_id_empty_id():
    tasks = [_make_draft_task(task_id="t1")]
    assert _find_draft_task_by_id(draft_tasks=tasks, task_id="") is None


# ---------------------------------------------------------------------------
# Unit tests: _build_task_description_md
# ---------------------------------------------------------------------------


def test_build_task_description_md_includes_key_fields():
    task = _make_draft_task()
    md = _build_task_description_md(task)
    assert "Set up PPC campaign" in md
    assert "**Marketplace:** US" in md
    assert "**Type:** PPC" in md
    assert "**ASINs:** B0TESTTEST" in md
    assert "*Created by The Claw*" in md


def test_build_task_description_md_skips_na_fields():
    task = _make_draft_task()
    task["coupon_window"] = "N/A"
    task["reference_docs"] = "n/a"
    md = _build_task_description_md(task)
    assert "Coupon Window" not in md
    assert "Reference Docs" not in md


# ---------------------------------------------------------------------------
# Integration tests: execute_confirmed_task_creation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_success_path_creates_task_and_updates_state(monkeypatch):
    fake_clickup = FakeClickUpService(
        spaces=[{"id": "sp1", "name": "Whoosh"}],
        create_result=FakeClickUpTask(id="cu_42", url="https://app.clickup.com/t/cu_42"),
    )
    monkeypatch.setattr(
        "app.services.theclaw.clickup_execution.get_clickup_service",
        lambda: fake_clickup,
    )

    session_ctx = _make_session_context(
        draft_tasks=[_make_draft_task()],
        resolved_context={"clickup_space": "Whoosh"},
    )
    pending = _make_pending()

    result, state_updates = await execute_confirmed_task_creation(
        session_context=session_ctx,
        pending_confirmation=pending,
    )

    assert result.success is True
    assert result.clickup_task_id == "cu_42"
    assert result.clickup_task_url == "https://app.clickup.com/t/cu_42"
    assert result.already_sent is False

    # Pending cleared.
    assert state_updates[SESSION_PENDING_CONFIRMATION_KEY] is None

    # Draft task updated to sent with linkage.
    tasks = state_updates[SESSION_DRAFT_TASKS_KEY]
    assert len(tasks) == 1
    assert tasks[0]["status"] == "sent"
    assert tasks[0]["clickup_task_id"] == "cu_42"
    assert tasks[0]["clickup_task_url"] == "https://app.clickup.com/t/cu_42"

    # ClickUp API called once.
    assert len(fake_clickup.created_tasks) == 1
    assert fake_clickup.created_tasks[0]["space_id"] == "sp1"
    assert fake_clickup.created_tasks[0]["name"] == "Launch campaign"


@pytest.mark.asyncio
async def test_success_with_direct_space_id(monkeypatch):
    fake_clickup = FakeClickUpService(
        create_result=FakeClickUpTask(id="cu_55"),
    )
    monkeypatch.setattr(
        "app.services.theclaw.clickup_execution.get_clickup_service",
        lambda: fake_clickup,
    )

    session_ctx = _make_session_context(draft_tasks=[_make_draft_task()])
    pending = _make_pending(clickup_space_id="direct-space-123")

    result, state_updates = await execute_confirmed_task_creation(
        session_context=session_ctx,
        pending_confirmation=pending,
    )

    assert result.success is True
    # Should not have called list_spaces since space_id was provided directly.
    assert len(fake_clickup.created_tasks) == 1
    assert fake_clickup.created_tasks[0]["space_id"] == "direct-space-123"


@pytest.mark.asyncio
async def test_idempotency_already_sent_skips_create(monkeypatch):
    call_count = 0

    def _counting_get_clickup():
        nonlocal call_count
        call_count += 1
        return FakeClickUpService()

    monkeypatch.setattr(
        "app.services.theclaw.clickup_execution.get_clickup_service",
        _counting_get_clickup,
    )

    session_ctx = _make_session_context(
        draft_tasks=[
            _make_draft_task(
                status="sent",
                clickup_task_id="cu_existing",
                clickup_task_url="https://app.clickup.com/t/cu_existing",
            )
        ],
    )
    pending = _make_pending()

    result, state_updates = await execute_confirmed_task_creation(
        session_context=session_ctx,
        pending_confirmation=pending,
    )

    assert result.success is True
    assert result.already_sent is True
    assert result.clickup_task_id == "cu_existing"
    assert result.clickup_task_url == "https://app.clickup.com/t/cu_existing"
    assert state_updates[SESSION_PENDING_CONFIRMATION_KEY] is None
    # ClickUp service should never have been instantiated.
    assert call_count == 0


@pytest.mark.asyncio
async def test_missing_task_id_in_pending_fails_closed(monkeypatch):
    session_ctx = _make_session_context(draft_tasks=[_make_draft_task()])
    pending = _make_pending(task_id="")

    result, state_updates = await execute_confirmed_task_creation(
        session_context=session_ctx,
        pending_confirmation=pending,
    )

    assert result.success is False
    assert "no task id" in result.error_message.lower()
    assert state_updates[SESSION_PENDING_CONFIRMATION_KEY] is None


@pytest.mark.asyncio
async def test_draft_task_not_found_fails_closed(monkeypatch):
    session_ctx = _make_session_context(draft_tasks=[_make_draft_task(task_id="other-id")])
    pending = _make_pending(task_id="nonexistent")

    result, state_updates = await execute_confirmed_task_creation(
        session_context=session_ctx,
        pending_confirmation=pending,
    )

    assert result.success is False
    assert "not found" in result.error_message.lower()
    assert state_updates[SESSION_PENDING_CONFIRMATION_KEY] is None


@pytest.mark.asyncio
async def test_missing_destination_fails_closed(monkeypatch):
    fake_clickup = FakeClickUpService(spaces=[])
    monkeypatch.setattr(
        "app.services.theclaw.clickup_execution.get_clickup_service",
        lambda: fake_clickup,
    )

    session_ctx = _make_session_context(draft_tasks=[_make_draft_task()])
    pending = _make_pending()  # No space_id, no space name.

    result, state_updates = await execute_confirmed_task_creation(
        session_context=session_ctx,
        pending_confirmation=pending,
    )

    assert result.success is False
    assert "no clickup destination" in result.error_message.lower()
    # Pending cleared — retrying without context change won't help.
    assert state_updates[SESSION_PENDING_CONFIRMATION_KEY] is None
    # No create call.
    assert len(fake_clickup.created_tasks) == 0


@pytest.mark.asyncio
async def test_clickup_config_error_keeps_pending(monkeypatch):
    from app.services.clickup import ClickUpConfigurationError

    monkeypatch.setattr(
        "app.services.theclaw.clickup_execution.get_clickup_service",
        lambda: (_ for _ in ()).throw(ClickUpConfigurationError("CLICKUP_API_TOKEN not set")),
    )

    session_ctx = _make_session_context(draft_tasks=[_make_draft_task()])
    pending = _make_pending()

    result, state_updates = await execute_confirmed_task_creation(
        session_context=session_ctx,
        pending_confirmation=pending,
    )

    assert result.success is False
    assert "not configured" in result.error_message.lower()
    # Pending kept — config fix allows retry.
    assert SESSION_PENDING_CONFIRMATION_KEY not in state_updates


@pytest.mark.asyncio
async def test_clickup_api_error_keeps_pending_for_retry(monkeypatch):
    from app.services.clickup import ClickUpAPIError

    fake_clickup = FakeClickUpService(
        spaces=[{"id": "sp1", "name": "Whoosh"}],
        create_error=ClickUpAPIError("500 Internal Server Error"),
    )
    monkeypatch.setattr(
        "app.services.theclaw.clickup_execution.get_clickup_service",
        lambda: fake_clickup,
    )

    session_ctx = _make_session_context(
        draft_tasks=[_make_draft_task()],
        resolved_context={"clickup_space": "Whoosh"},
    )
    pending = _make_pending()

    result, state_updates = await execute_confirmed_task_creation(
        session_context=session_ctx,
        pending_confirmation=pending,
    )

    assert result.success is False
    assert "retry" in result.error_message.lower()
    # Pending kept for retry.
    assert SESSION_PENDING_CONFIRMATION_KEY not in state_updates
    # Draft task not marked sent.
    draft = session_ctx["theclaw_draft_tasks_v1"][0]
    assert draft["status"] == "draft"


@pytest.mark.asyncio
async def test_space_name_resolution_from_resolved_context(monkeypatch):
    fake_clickup = FakeClickUpService(
        spaces=[{"id": "sp-resolved", "name": "Acme Corp"}],
        create_result=FakeClickUpTask(id="cu_77"),
    )
    monkeypatch.setattr(
        "app.services.theclaw.clickup_execution.get_clickup_service",
        lambda: fake_clickup,
    )

    session_ctx = _make_session_context(
        draft_tasks=[_make_draft_task()],
        resolved_context={"clickup_space": "Acme Corp"},
    )
    # Pending has no space info — falls through to resolved_context.
    pending = _make_pending()

    result, _ = await execute_confirmed_task_creation(
        session_context=session_ctx,
        pending_confirmation=pending,
    )

    assert result.success is True
    assert fake_clickup.created_tasks[0]["space_id"] == "sp-resolved"


@pytest.mark.asyncio
async def test_multiple_draft_tasks_only_target_updated(monkeypatch):
    fake_clickup = FakeClickUpService(
        spaces=[{"id": "sp1", "name": "Whoosh"}],
        create_result=FakeClickUpTask(id="cu_88"),
    )
    monkeypatch.setattr(
        "app.services.theclaw.clickup_execution.get_clickup_service",
        lambda: fake_clickup,
    )

    tasks = [
        _make_draft_task(task_id="task-abc", title="Target task"),
        _make_draft_task(task_id="task-other", title="Other task"),
    ]
    session_ctx = _make_session_context(
        draft_tasks=tasks,
        resolved_context={"clickup_space": "Whoosh"},
    )
    pending = _make_pending(task_id="task-abc")

    result, state_updates = await execute_confirmed_task_creation(
        session_context=session_ctx,
        pending_confirmation=pending,
    )

    assert result.success is True
    updated_tasks = state_updates[SESSION_DRAFT_TASKS_KEY]
    assert len(updated_tasks) == 2
    assert updated_tasks[0]["status"] == "sent"
    assert updated_tasks[0]["clickup_task_id"] == "cu_88"
    assert updated_tasks[1]["status"] == "draft"
    assert updated_tasks[1].get("clickup_task_id") is None


# ---------------------------------------------------------------------------
# Direct list_id destination path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_direct_list_id_skips_space_resolution(monkeypatch):
    """When clickup_list_id is set on pending, create_task_in_list is called directly."""
    created_in_lists: list[dict[str, Any]] = []

    class ListOnlyClickUp(FakeClickUpService):
        async def create_task_in_list(self, list_id, name, description_md=None, assignee_ids=None):
            created_in_lists.append({"list_id": list_id, "name": name})
            return FakeClickUpTask(id="cu_list_77", url="https://app.clickup.com/t/cu_list_77")

        async def create_task_in_space(self, *args, **kwargs):
            raise AssertionError("create_task_in_space should not be called with direct list_id")

    fake_clickup = ListOnlyClickUp()
    monkeypatch.setattr(
        "app.services.theclaw.clickup_execution.get_clickup_service",
        lambda: fake_clickup,
    )

    session_ctx = _make_session_context(draft_tasks=[_make_draft_task()])
    pending = _make_pending()
    pending["clickup_list_id"] = "list-direct-123"

    result, state_updates = await execute_confirmed_task_creation(
        session_context=session_ctx,
        pending_confirmation=pending,
    )

    assert result.success is True
    assert result.clickup_task_id == "cu_list_77"
    assert len(created_in_lists) == 1
    assert created_in_lists[0]["list_id"] == "list-direct-123"


# ---------------------------------------------------------------------------
# Unexpected exception safety
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unexpected_exception_from_get_service_returns_error(monkeypatch):
    """Non-ClickUpError from get_clickup_service is caught and returns a result."""
    monkeypatch.setattr(
        "app.services.theclaw.clickup_execution.get_clickup_service",
        lambda: (_ for _ in ()).throw(ValueError("bad rate limit env")),
    )

    session_ctx = _make_session_context(draft_tasks=[_make_draft_task()])
    pending = _make_pending()

    result, state_updates = await execute_confirmed_task_creation(
        session_context=session_ctx,
        pending_confirmation=pending,
    )

    assert result.success is False
    assert "not configured" in result.error_message.lower()
    # Pending kept — config fix allows retry.
    assert SESSION_PENDING_CONFIRMATION_KEY not in state_updates


@pytest.mark.asyncio
async def test_unexpected_exception_during_create_returns_retry(monkeypatch):
    """Non-ClickUpError during create (e.g., encoding bug) is caught and retryable."""

    class BuggyClickUp(FakeClickUpService):
        async def create_task_in_space(self, *args, **kwargs):
            raise RuntimeError("unexpected httpx internal error")

    fake_clickup = BuggyClickUp(spaces=[{"id": "sp1", "name": "Whoosh"}])
    monkeypatch.setattr(
        "app.services.theclaw.clickup_execution.get_clickup_service",
        lambda: fake_clickup,
    )

    session_ctx = _make_session_context(
        draft_tasks=[_make_draft_task()],
        resolved_context={"clickup_space": "Whoosh"},
    )
    pending = _make_pending()

    result, state_updates = await execute_confirmed_task_creation(
        session_context=session_ctx,
        pending_confirmation=pending,
    )

    assert result.success is False
    assert "unexpected error" in result.error_message.lower()
    # Pending kept for retry.
    assert SESSION_PENDING_CONFIRMATION_KEY not in state_updates
