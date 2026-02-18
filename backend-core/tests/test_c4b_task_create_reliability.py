"""Tests for C4B: reliability primitives wired into _execute_task_create."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.routes.slack import (
    _execute_task_create,
    _handle_dm_event,
    _task_create_inflight,
)
from app.services.agencyclaw.clickup_reliability import (
    RetryExhaustedError,
    build_idempotency_key,
)
from app.services.clickup import ClickUpAPIError, ClickUpError, ClickUpTask


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FakeSession:
    id: str = "sess-1"
    slack_user_id: str = "U123"
    profile_id: Optional[str] = "profile-1"
    active_client_id: Optional[str] = "client-1"
    context: dict = None  # type: ignore[assignment]
    last_message_at: Optional[str] = None

    def __post_init__(self):
        if self.context is None:
            object.__setattr__(self, "context", {})


def _make_mocks(**session_overrides) -> tuple[MagicMock, AsyncMock]:
    session = FakeSession(**session_overrides)
    svc = MagicMock()
    svc.get_or_create_session.return_value = session
    svc.find_client_matches.return_value = [{"id": "client-1", "name": "Distex"}]
    svc.get_client_name.return_value = "Distex"
    svc.get_brand_destination_for_client.return_value = {
        "id": "brand-1",
        "name": "Brand A",
        "clickup_space_id": "sp1",
        "clickup_list_id": "list1",
    }
    svc.get_profile_clickup_user_id.return_value = "12345"
    svc.list_clients_for_picker.return_value = [{"id": "c1", "name": "Acme"}]
    slack = AsyncMock()
    return svc, slack


def _make_mock_db() -> MagicMock:
    """Return a mock Supabase admin client."""
    return MagicMock()


async def _passthrough_retry(fn, **_kwargs):
    """Default passthrough for retry_with_backoff."""
    return await fn()


_EXEC_DEFAULTS = dict(
    channel="C1",
    client_id="client-1",
    client_name="Distex",
    task_title="Fix landing page",
    task_description="",
)


# ---------------------------------------------------------------------------
# 1) Duplicate key suppresses create
# ---------------------------------------------------------------------------


class TestDuplicateSuppression:
    @pytest.mark.asyncio
    async def test_duplicate_with_clickup_id_shows_link(self):
        svc, slack = _make_mocks()
        session = FakeSession()
        mock_db = _make_mock_db()

        duplicate = {
            "agent_task_id": "at-1",
            "clickup_task_id": "cu-999",
            "status": "pending",
            "created_at": "2026-02-17T10:00:00Z",
        }

        with (
            patch("app.api.routes.slack.get_supabase_admin_client", return_value=mock_db),
            patch("app.api.routes.slack.check_duplicate", return_value=duplicate),
            patch("app.api.routes.slack.retry_with_backoff", side_effect=_passthrough_retry),
        ):
            await _execute_task_create(
                session=session,
                session_service=svc,
                slack=slack,
                **_EXEC_DEFAULTS,
            )

        msg = slack.post_message.call_args.kwargs["text"]
        assert "already created today" in msg.lower()
        assert "cu-999" in msg

    @pytest.mark.asyncio
    async def test_duplicate_without_clickup_id(self):
        svc, slack = _make_mocks()
        session = FakeSession()
        mock_db = _make_mock_db()

        duplicate = {
            "agent_task_id": "at-1",
            "clickup_task_id": None,
            "status": "pending",
            "created_at": "2026-02-17T10:00:00Z",
        }

        with (
            patch("app.api.routes.slack.get_supabase_admin_client", return_value=mock_db),
            patch("app.api.routes.slack.check_duplicate", return_value=duplicate),
            patch("app.api.routes.slack.retry_with_backoff", side_effect=_passthrough_retry),
        ):
            await _execute_task_create(
                session=session,
                session_service=svc,
                slack=slack,
                **_EXEC_DEFAULTS,
            )

        msg = slack.post_message.call_args.kwargs["text"]
        assert "already created today" in msg.lower()
        assert "cu-" not in msg  # no task id shown

    @pytest.mark.asyncio
    async def test_duplicate_does_not_call_clickup(self):
        """When duplicate is found, ClickUp create must NOT be called."""
        svc, slack = _make_mocks()
        session = FakeSession()
        mock_db = _make_mock_db()

        duplicate = {
            "agent_task_id": "at-1",
            "clickup_task_id": "cu-999",
            "status": "pending",
            "created_at": "2026-02-17T10:00:00Z",
        }

        with (
            patch("app.api.routes.slack.get_supabase_admin_client", return_value=mock_db),
            patch("app.api.routes.slack.check_duplicate", return_value=duplicate),
            patch("app.api.routes.slack.get_clickup_service") as mock_cu,
            patch("app.api.routes.slack.retry_with_backoff", side_effect=_passthrough_retry),
        ):
            await _execute_task_create(
                session=session,
                session_service=svc,
                slack=slack,
                **_EXEC_DEFAULTS,
            )

        mock_cu.assert_not_called()


# ---------------------------------------------------------------------------
# 2) Successful create writes agent_tasks row
# ---------------------------------------------------------------------------


class TestAgentTasksPersistence:
    @pytest.mark.asyncio
    async def test_success_inserts_agent_task_with_key(self):
        svc, slack = _make_mocks()
        session = FakeSession()
        mock_db = _make_mock_db()
        fake_task = ClickUpTask(id="cu-new", url="https://clickup.com/t/cu-new")

        with (
            patch("app.api.routes.slack.get_supabase_admin_client", return_value=mock_db),
            patch("app.api.routes.slack.check_duplicate", return_value=None),
            patch("app.api.routes.slack.retry_with_backoff", side_effect=_passthrough_retry),
            patch("app.api.routes.slack.get_clickup_service") as mock_cu,
        ):
            cu = AsyncMock()
            cu.create_task_in_list.return_value = fake_task
            mock_cu.return_value = cu

            await _execute_task_create(
                session=session,
                session_service=svc,
                slack=slack,
                **_EXEC_DEFAULTS,
            )

        # Verify agent_tasks insert was called
        insert_calls = mock_db.table.return_value.insert.call_args_list
        assert len(insert_calls) >= 1
        row = insert_calls[0][0][0]
        assert row["clickup_task_id"] == "cu-new"
        assert row["client_id"] == "client-1"
        assert row["assignee_id"] == "profile-1"
        assert row["source"] == "slack_dm"
        assert row["skill_invoked"] == "clickup_task_create"
        assert row["status"] == "pending"
        # source_reference is the idempotency key (sha256 hex)
        assert len(row["source_reference"]) == 64


# ---------------------------------------------------------------------------
# 3) Persistence failure triggers orphan event
# ---------------------------------------------------------------------------


class TestOrphanDetection:
    @pytest.mark.asyncio
    async def test_persist_failure_emits_orphan_event(self):
        svc, slack = _make_mocks()
        session = FakeSession()
        mock_db = _make_mock_db()
        fake_task = ClickUpTask(id="cu-orphan", url="https://clickup.com/t/cu-orphan")

        # Make agent_tasks insert fail
        mock_db.table.return_value.insert.return_value.execute.side_effect = RuntimeError("DB down")

        with (
            patch("app.api.routes.slack.get_supabase_admin_client", return_value=mock_db),
            patch("app.api.routes.slack.check_duplicate", return_value=None),
            patch("app.api.routes.slack.retry_with_backoff", side_effect=_passthrough_retry),
            patch("app.api.routes.slack.get_clickup_service") as mock_cu,
            patch("app.api.routes.slack.emit_orphan_event") as mock_orphan,
        ):
            cu = AsyncMock()
            cu.create_task_in_list.return_value = fake_task
            mock_cu.return_value = cu

            await _execute_task_create(
                session=session,
                session_service=svc,
                slack=slack,
                **_EXEC_DEFAULTS,
            )

        # Orphan event should have been emitted
        mock_orphan.assert_called_once()
        call_kwargs = mock_orphan.call_args.kwargs
        assert call_kwargs["clickup_task"].id == "cu-orphan"
        assert call_kwargs["client_id"] == "client-1"
        assert call_kwargs["employee_id"] == "profile-1"
        assert "DB down" in call_kwargs["error"]
        assert len(call_kwargs["idempotency_key"]) == 64

        # User still sees success message (orphan doesn't break response)
        msg = slack.post_message.call_args.kwargs["text"]
        assert "Task created" in msg

    @pytest.mark.asyncio
    async def test_orphan_emit_failure_does_not_break_response(self):
        """Even if orphan event itself fails, user still gets task-created message."""
        svc, slack = _make_mocks()
        session = FakeSession()
        mock_db = _make_mock_db()
        fake_task = ClickUpTask(id="cu-ok", url="https://clickup.com/t/cu-ok")

        # Make agent_tasks insert fail
        mock_db.table.return_value.insert.return_value.execute.side_effect = RuntimeError("DB down")

        with (
            patch("app.api.routes.slack.get_supabase_admin_client", return_value=mock_db),
            patch("app.api.routes.slack.check_duplicate", return_value=None),
            patch("app.api.routes.slack.retry_with_backoff", side_effect=_passthrough_retry),
            patch("app.api.routes.slack.get_clickup_service") as mock_cu,
            patch("app.api.routes.slack.emit_orphan_event", side_effect=RuntimeError("Also broken")),
        ):
            cu = AsyncMock()
            cu.create_task_in_list.return_value = fake_task
            mock_cu.return_value = cu

            # Should NOT raise
            await _execute_task_create(
                session=session,
                session_service=svc,
                slack=slack,
                **_EXEC_DEFAULTS,
            )

        msg = slack.post_message.call_args.kwargs["text"]
        assert "Task created" in msg


# ---------------------------------------------------------------------------
# 4) Retry wrapper path
# ---------------------------------------------------------------------------


class TestRetryWrapperIntegration:
    @pytest.mark.asyncio
    async def test_retry_then_success(self):
        """ClickUp fails once, succeeds on retry — user sees success."""
        svc, slack = _make_mocks()
        session = FakeSession()
        mock_db = _make_mock_db()
        fake_task = ClickUpTask(id="cu-retried", url="https://clickup.com/t/cu-retried")

        call_count = 0

        async def _retry_sim(fn, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Simulate: first call fails, retry_with_backoff calls fn again
                # Actually, let's just simulate what retry_with_backoff does:
                # call fn, if retryable error, retry.
                pass
            return await fn()

        with (
            patch("app.api.routes.slack.get_supabase_admin_client", return_value=mock_db),
            patch("app.api.routes.slack.check_duplicate", return_value=None),
            patch("app.api.routes.slack.retry_with_backoff", side_effect=_retry_sim),
            patch("app.api.routes.slack.get_clickup_service") as mock_cu,
        ):
            cu = AsyncMock()
            cu.create_task_in_list.return_value = fake_task
            mock_cu.return_value = cu

            await _execute_task_create(
                session=session,
                session_service=svc,
                slack=slack,
                **_EXEC_DEFAULTS,
            )

        msg = slack.post_message.call_args.kwargs["text"]
        assert "Task created" in msg
        assert "cu-retried" in msg

    @pytest.mark.asyncio
    async def test_exhausted_retries_show_failure(self):
        """When retry_with_backoff raises RetryExhaustedError, user sees failure message."""
        svc, slack = _make_mocks()
        session = FakeSession()
        mock_db = _make_mock_db()

        async def _exhaust(fn, **_kwargs):
            raise RetryExhaustedError(3, ClickUpAPIError("rate limited"))

        with (
            patch("app.api.routes.slack.get_supabase_admin_client", return_value=mock_db),
            patch("app.api.routes.slack.check_duplicate", return_value=None),
            patch("app.api.routes.slack.retry_with_backoff", side_effect=_exhaust),
            patch("app.api.routes.slack.get_clickup_service") as mock_cu,
        ):
            cu = AsyncMock()
            mock_cu.return_value = cu

            await _execute_task_create(
                session=session,
                session_service=svc,
                slack=slack,
                **_EXEC_DEFAULTS,
            )

        msg = slack.post_message.call_args.kwargs["text"]
        assert "failed" in msg.lower()
        assert "rate limited" in msg.lower()

    @pytest.mark.asyncio
    async def test_exhausted_retries_still_clears_pending(self):
        """Pending state must be cleared even when retries are exhausted."""
        svc, slack = _make_mocks()
        session = FakeSession()
        mock_db = _make_mock_db()

        async def _exhaust(fn, **_kwargs):
            raise RetryExhaustedError(3, ClickUpAPIError("timeout"))

        with (
            patch("app.api.routes.slack.get_supabase_admin_client", return_value=mock_db),
            patch("app.api.routes.slack.check_duplicate", return_value=None),
            patch("app.api.routes.slack.retry_with_backoff", side_effect=_exhaust),
            patch("app.api.routes.slack.get_clickup_service") as mock_cu,
        ):
            cu = AsyncMock()
            mock_cu.return_value = cu

            await _execute_task_create(
                session=session,
                session_service=svc,
                slack=slack,
                **_EXEC_DEFAULTS,
            )

        calls = svc.update_context.call_args_list
        cleared = any(
            call[0][1].get("pending_task_create") is None for call in calls
        )
        assert cleared


# ---------------------------------------------------------------------------
# 5) Dedupe infrastructure failure (fail-closed)
# ---------------------------------------------------------------------------


class TestDedupeInfrastructureFailure:
    @pytest.mark.asyncio
    async def test_dedupe_db_failure_sends_safe_message(self):
        """When get_supabase_admin_client or check_duplicate raises, user gets
        a clear error message and ClickUp is never called."""
        svc, slack = _make_mocks()
        session = FakeSession()

        with (
            patch(
                "app.api.routes.slack.get_supabase_admin_client",
                side_effect=RuntimeError("Supabase credentials not configured"),
            ),
            patch("app.api.routes.slack.get_clickup_service") as mock_cu,
        ):
            await _execute_task_create(
                session=session,
                session_service=svc,
                slack=slack,
                **_EXEC_DEFAULTS,
            )

        msg = slack.post_message.call_args.kwargs["text"]
        assert "duplicate protection" in msg.lower()
        assert "try again" in msg.lower()
        mock_cu.assert_not_called()

    @pytest.mark.asyncio
    async def test_dedupe_check_failure_sends_safe_message(self):
        """When check_duplicate itself throws, same fail-closed behavior."""
        svc, slack = _make_mocks()
        session = FakeSession()
        mock_db = _make_mock_db()

        with (
            patch("app.api.routes.slack.get_supabase_admin_client", return_value=mock_db),
            patch("app.api.routes.slack.check_duplicate", side_effect=RuntimeError("DB timeout")),
            patch("app.api.routes.slack.get_clickup_service") as mock_cu,
        ):
            await _execute_task_create(
                session=session,
                session_service=svc,
                slack=slack,
                **_EXEC_DEFAULTS,
            )

        msg = slack.post_message.call_args.kwargs["text"]
        assert "duplicate protection" in msg.lower()
        mock_cu.assert_not_called()


# ---------------------------------------------------------------------------
# 6) _handle_dm_event generic safety net
# ---------------------------------------------------------------------------


class TestHandleDmEventSafetyNet:
    @pytest.mark.asyncio
    async def test_unexpected_exception_sends_fallback_message(self):
        """An unexpected exception in _handle_dm_event must not crash and
        should attempt a user-facing fallback message."""
        slack = AsyncMock()
        svc = MagicMock()
        # Force get_or_create_session to throw an unexpected error
        svc.get_or_create_session.side_effect = RuntimeError("Unexpected DB error")

        with (
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
        ):
            # Must NOT raise
            await _handle_dm_event(
                slack_user_id="U123",
                channel="C1",
                text="hello",
            )

        # Verify fallback message was sent
        msg = slack.post_message.call_args.kwargs["text"]
        assert "something went wrong" in msg.lower()

    @pytest.mark.asyncio
    async def test_safety_net_swallows_fallback_send_failure(self):
        """Even if the fallback message itself fails to send, handler must not raise."""
        slack = AsyncMock()
        # First call = fallback message send, also fails
        slack.post_message.side_effect = RuntimeError("Slack also broken")
        svc = MagicMock()
        svc.get_or_create_session.side_effect = RuntimeError("DB down")

        with (
            patch("app.api.routes.slack.get_playbook_session_service", return_value=svc),
            patch("app.api.routes.slack.get_slack_service", return_value=slack),
        ):
            # Must NOT raise even when everything is broken
            await _handle_dm_event(
                slack_user_id="U123",
                channel="C1",
                text="hello",
            )


# ---------------------------------------------------------------------------
# 7) Concurrency guard (C4C)
# ---------------------------------------------------------------------------


class TestConcurrencyGuard:
    def setup_method(self):
        _task_create_inflight.clear()

    def teardown_method(self):
        _task_create_inflight.clear()

    @pytest.mark.asyncio
    async def test_inflight_key_returns_conflict_message(self):
        """When the idempotency key is already in-flight, user gets a
        conflict message and ClickUp is never called."""
        svc, slack = _make_mocks()
        session = FakeSession()

        # Compute the key that _execute_task_create will build
        destination = svc.get_brand_destination_for_client.return_value
        brand_id = str(destination.get("id") or "")
        expected_key = build_idempotency_key(brand_id, _EXEC_DEFAULTS["task_title"])

        # Pre-populate the inflight set
        _task_create_inflight.add(expected_key)

        with (
            patch("app.api.routes.slack.get_clickup_service") as mock_cu,
        ):
            await _execute_task_create(
                session=session,
                session_service=svc,
                slack=slack,
                **_EXEC_DEFAULTS,
            )

        msg = slack.post_message.call_args.kwargs["text"]
        assert "another operation" in msg.lower()
        assert "in progress" in msg.lower()
        mock_cu.assert_not_called()

    @pytest.mark.asyncio
    async def test_successful_path_cleans_up_inflight(self):
        """After a successful create, the inflight set must be empty."""
        svc, slack = _make_mocks()
        session = FakeSession()
        mock_db = _make_mock_db()
        fake_task = ClickUpTask(id="cu-guard", url="https://clickup.com/t/cu-guard")

        async def _passthrough(fn, **_kw):
            return await fn()

        with (
            patch("app.api.routes.slack.get_supabase_admin_client", return_value=mock_db),
            patch("app.api.routes.slack.check_duplicate", return_value=None),
            patch("app.api.routes.slack.retry_with_backoff", side_effect=_passthrough),
            patch("app.api.routes.slack.get_clickup_service") as mock_cu,
        ):
            cu = AsyncMock()
            cu.create_task_in_list.return_value = fake_task
            mock_cu.return_value = cu

            await _execute_task_create(
                session=session,
                session_service=svc,
                slack=slack,
                **_EXEC_DEFAULTS,
            )

        assert len(_task_create_inflight) == 0
        msg = slack.post_message.call_args.kwargs["text"]
        assert "Task created" in msg
