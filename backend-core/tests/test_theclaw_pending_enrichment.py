"""Tests for pending confirmation destination enrichment."""

from __future__ import annotations

from typing import Any

import pytest

from app.services.theclaw.clickup_execution import enrich_pending_confirmation_destination


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------


class FakeClickUpService:
    """Minimal fake for enrichment tests."""

    def __init__(
        self,
        *,
        spaces: list[dict[str, Any]] | None = None,
        list_spaces_error: Exception | None = None,
    ) -> None:
        self.spaces = spaces or []
        self.list_spaces_error = list_spaces_error
        self.list_spaces_called = False
        self.closed = False

    async def list_spaces(self, *, team_id: str | None = None) -> list[dict[str, Any]]:
        self.list_spaces_called = True
        if self.list_spaces_error:
            raise self.list_spaces_error
        return self.spaces

    async def aclose(self) -> None:
        self.closed = True


# ---------------------------------------------------------------------------
# Space name → space_id enrichment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enriches_space_name_to_space_id(monkeypatch):
    """Pending with only clickup_space gets clickup_space_id resolved."""
    fake_clickup = FakeClickUpService(spaces=[{"id": "sp42", "name": "Whoosh"}])
    monkeypatch.setattr(
        "app.services.theclaw.clickup_execution.get_clickup_service",
        lambda: fake_clickup,
    )

    pending = {
        "task_id": "t1",
        "task_title": "Launch campaign",
        "clickup_space": "Whoosh",
        "clickup_space_id": None,
        "clickup_list_id": None,
        "status": "pending",
        "notes": None,
    }
    result = await enrich_pending_confirmation_destination(
        pending=pending,
        resolved_ctx=None,
    )

    assert result["clickup_space_id"] == "sp42"
    assert result["task_id"] == "t1"
    assert fake_clickup.list_spaces_called is True
    assert fake_clickup.closed is True


@pytest.mark.asyncio
async def test_enriches_from_resolved_context_fallback(monkeypatch):
    """When pending has no clickup_space, falls back to resolved_ctx."""
    fake_clickup = FakeClickUpService(spaces=[{"id": "sp99", "name": "Acme"}])
    monkeypatch.setattr(
        "app.services.theclaw.clickup_execution.get_clickup_service",
        lambda: fake_clickup,
    )

    pending = {
        "task_id": "t2",
        "task_title": "Test task",
        "clickup_space": None,
        "clickup_space_id": None,
        "clickup_list_id": None,
        "status": "pending",
        "notes": None,
    }
    resolved_ctx = {"clickup_space": "Acme"}
    result = await enrich_pending_confirmation_destination(
        pending=pending,
        resolved_ctx=resolved_ctx,
    )

    assert result["clickup_space_id"] == "sp99"
    assert fake_clickup.list_spaces_called is True


@pytest.mark.asyncio
async def test_case_insensitive_space_match(monkeypatch):
    """Space name matching is case-insensitive."""
    fake_clickup = FakeClickUpService(spaces=[{"id": "sp10", "name": "BigBrand"}])
    monkeypatch.setattr(
        "app.services.theclaw.clickup_execution.get_clickup_service",
        lambda: fake_clickup,
    )

    pending = {
        "task_id": "t3",
        "task_title": "Test",
        "clickup_space": "bigbrand",
        "clickup_space_id": None,
        "clickup_list_id": None,
        "status": "pending",
        "notes": None,
    }
    result = await enrich_pending_confirmation_destination(
        pending=pending,
        resolved_ctx=None,
    )

    assert result["clickup_space_id"] == "sp10"


# ---------------------------------------------------------------------------
# Existing IDs preserved — no lookup attempted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_existing_space_id_preserved_no_lookup(monkeypatch):
    """When clickup_space_id is already set, no list_spaces call is made."""
    fake_clickup = FakeClickUpService(spaces=[{"id": "sp42", "name": "Whoosh"}])
    monkeypatch.setattr(
        "app.services.theclaw.clickup_execution.get_clickup_service",
        lambda: fake_clickup,
    )

    pending = {
        "task_id": "t4",
        "task_title": "Test",
        "clickup_space": "Whoosh",
        "clickup_space_id": "sp-already",
        "clickup_list_id": None,
        "status": "pending",
        "notes": None,
    }
    result = await enrich_pending_confirmation_destination(
        pending=pending,
        resolved_ctx=None,
    )

    assert result is pending  # Same object — no mutation.
    assert fake_clickup.list_spaces_called is False


@pytest.mark.asyncio
async def test_existing_list_id_preserved_no_lookup(monkeypatch):
    """When clickup_list_id is already set, no space lookup is attempted."""
    fake_clickup = FakeClickUpService(spaces=[{"id": "sp42", "name": "Whoosh"}])
    monkeypatch.setattr(
        "app.services.theclaw.clickup_execution.get_clickup_service",
        lambda: fake_clickup,
    )

    pending = {
        "task_id": "t5",
        "task_title": "Test",
        "clickup_space": "Whoosh",
        "clickup_space_id": None,
        "clickup_list_id": "list-direct-99",
        "status": "pending",
        "notes": None,
    }
    result = await enrich_pending_confirmation_destination(
        pending=pending,
        resolved_ctx=None,
    )

    assert result is pending
    assert fake_clickup.list_spaces_called is False


# ---------------------------------------------------------------------------
# Fail-open: errors do not crash
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clickup_api_error_returns_pending_unchanged(monkeypatch):
    """ClickUp API error during list_spaces returns pending unchanged."""
    fake_clickup = FakeClickUpService(
        list_spaces_error=RuntimeError("API unavailable"),
    )
    monkeypatch.setattr(
        "app.services.theclaw.clickup_execution.get_clickup_service",
        lambda: fake_clickup,
    )

    pending = {
        "task_id": "t6",
        "task_title": "Test",
        "clickup_space": "Whoosh",
        "clickup_space_id": None,
        "clickup_list_id": None,
        "status": "pending",
        "notes": None,
    }
    result = await enrich_pending_confirmation_destination(
        pending=pending,
        resolved_ctx=None,
    )

    assert result is pending
    assert result.get("clickup_space_id") is None


@pytest.mark.asyncio
async def test_clickup_config_error_returns_pending_unchanged(monkeypatch):
    """get_clickup_service() failure returns pending unchanged."""
    monkeypatch.setattr(
        "app.services.theclaw.clickup_execution.get_clickup_service",
        lambda: (_ for _ in ()).throw(ValueError("missing env var")),
    )

    pending = {
        "task_id": "t7",
        "task_title": "Test",
        "clickup_space": "Whoosh",
        "clickup_space_id": None,
        "clickup_list_id": None,
        "status": "pending",
        "notes": None,
    }
    result = await enrich_pending_confirmation_destination(
        pending=pending,
        resolved_ctx=None,
    )

    assert result is pending


@pytest.mark.asyncio
async def test_no_space_name_anywhere_returns_unchanged(monkeypatch):
    """No clickup_space in pending or resolved_ctx — no lookup attempted."""
    service_created = False

    def _should_not_be_called():
        nonlocal service_created
        service_created = True
        return FakeClickUpService()

    monkeypatch.setattr(
        "app.services.theclaw.clickup_execution.get_clickup_service",
        _should_not_be_called,
    )

    pending = {
        "task_id": "t8",
        "task_title": "Test",
        "clickup_space": None,
        "clickup_space_id": None,
        "clickup_list_id": None,
        "status": "pending",
        "notes": None,
    }
    result = await enrich_pending_confirmation_destination(
        pending=pending,
        resolved_ctx=None,
    )

    assert result is pending
    assert service_created is False


@pytest.mark.asyncio
async def test_space_name_not_found_returns_unchanged(monkeypatch):
    """Space name exists but doesn't match any ClickUp space — no enrichment."""
    fake_clickup = FakeClickUpService(spaces=[{"id": "sp1", "name": "OtherBrand"}])
    monkeypatch.setattr(
        "app.services.theclaw.clickup_execution.get_clickup_service",
        lambda: fake_clickup,
    )

    pending = {
        "task_id": "t9",
        "task_title": "Test",
        "clickup_space": "Whoosh",
        "clickup_space_id": None,
        "clickup_list_id": None,
        "status": "pending",
        "notes": None,
    }
    result = await enrich_pending_confirmation_destination(
        pending=pending,
        resolved_ctx=None,
    )

    assert result is pending
    assert result.get("clickup_space_id") is None
    assert fake_clickup.list_spaces_called is True


# ---------------------------------------------------------------------------
# Runtime wrapper: same-turn resolved context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enrich_wrapper_uses_same_turn_resolved_context(monkeypatch):
    """_enrich_pending_destination_if_present prefers same-turn resolved context over session."""
    from app.services.theclaw.pending_confirmation_runtime import enrich_pending_destination_if_present

    fake_clickup = FakeClickUpService(spaces=[{"id": "sp-same-turn", "name": "NewBrand"}])
    monkeypatch.setattr(
        "app.services.theclaw.clickup_execution.get_clickup_service",
        lambda: fake_clickup,
    )

    state_updates = {
        "theclaw_pending_confirmation_v1": {
            "task_id": "t10",
            "task_title": "Test",
            "clickup_space": None,
            "clickup_space_id": None,
            "clickup_list_id": None,
            "status": "pending",
            "notes": None,
        },
        # Same-turn resolved context with the space name.
        "theclaw_resolved_context_v1": {
            "client": "NewBrand",
            "clickup_space": "NewBrand",
        },
    }
    # Session context has a *different* space — should NOT be used.
    session_context = {
        "theclaw_resolved_context_v1": {
            "client": "OldBrand",
            "clickup_space": "OldBrand",
        },
    }

    result = await enrich_pending_destination_if_present(
        state_updates=state_updates,
        session_context=session_context,
    )

    pending = result["theclaw_pending_confirmation_v1"]
    assert pending["clickup_space_id"] == "sp-same-turn"
    assert fake_clickup.list_spaces_called is True
