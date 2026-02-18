"""Tests for C4A: ClickUp mutation reliability primitives."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.services.agencyclaw.clickup_reliability import (
    DuplicateCandidate,
    RetryExhaustedError,
    build_idempotency_key,
    check_duplicate,
    emit_orphan_event,
    retry_with_backoff,
)
from app.services.clickup import (
    ClickUpAPIError,
    ClickUpRateLimitError,
    ClickUpTask,
    ClickUpValidationError,
)


# ---------------------------------------------------------------------------
# 1) Idempotency key builder
# ---------------------------------------------------------------------------


class TestBuildIdempotencyKey:
    def test_deterministic_output(self):
        """Same inputs must produce the same key."""
        d = datetime(2026, 2, 17, tzinfo=timezone.utc)
        k1 = build_idempotency_key("brand-1", "Fix landing page", d)
        k2 = build_idempotency_key("brand-1", "Fix landing page", d)
        assert k1 == k2
        assert len(k1) == 64  # sha256 hex

    def test_different_brand_different_key(self):
        d = datetime(2026, 2, 17, tzinfo=timezone.utc)
        k1 = build_idempotency_key("brand-1", "Fix landing page", d)
        k2 = build_idempotency_key("brand-2", "Fix landing page", d)
        assert k1 != k2

    def test_different_title_different_key(self):
        d = datetime(2026, 2, 17, tzinfo=timezone.utc)
        k1 = build_idempotency_key("brand-1", "Fix landing page", d)
        k2 = build_idempotency_key("brand-1", "Update hero banner", d)
        assert k1 != k2

    def test_different_date_different_key(self):
        d1 = datetime(2026, 2, 17, tzinfo=timezone.utc)
        d2 = datetime(2026, 2, 18, tzinfo=timezone.utc)
        k1 = build_idempotency_key("brand-1", "Fix landing page", d1)
        k2 = build_idempotency_key("brand-1", "Fix landing page", d2)
        assert k1 != k2

    def test_normalization_lowercase(self):
        """Title normalization: lowercase."""
        d = datetime(2026, 2, 17, tzinfo=timezone.utc)
        k1 = build_idempotency_key("b", "Fix Landing Page", d)
        k2 = build_idempotency_key("b", "fix landing page", d)
        assert k1 == k2

    def test_normalization_whitespace_collapse(self):
        """Title normalization: collapse multiple spaces."""
        d = datetime(2026, 2, 17, tzinfo=timezone.utc)
        k1 = build_idempotency_key("b", "fix  landing   page", d)
        k2 = build_idempotency_key("b", "fix landing page", d)
        assert k1 == k2

    def test_normalization_trim(self):
        """Title normalization: strip leading/trailing whitespace."""
        d = datetime(2026, 2, 17, tzinfo=timezone.utc)
        k1 = build_idempotency_key("b", "  fix landing page  ", d)
        k2 = build_idempotency_key("b", "fix landing page", d)
        assert k1 == k2

    def test_empty_title(self):
        """Empty title should still produce a valid key."""
        d = datetime(2026, 2, 17, tzinfo=timezone.utc)
        key = build_idempotency_key("brand-1", "", d)
        assert len(key) == 64

    def test_defaults_to_today(self):
        """Without date, uses UTC today — key should be 64-char hex."""
        key = build_idempotency_key("brand-1", "Some Task")
        assert len(key) == 64


# ---------------------------------------------------------------------------
# 2) Duplicate suppression
# ---------------------------------------------------------------------------


class TestCheckDuplicate:
    def _make_db(self, rows: list[dict]) -> MagicMock:
        """Build a mock Supabase client that returns the given rows."""
        db = MagicMock()
        chain = db.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.limit.return_value
        response = MagicMock()
        response.data = rows
        chain.execute.return_value = response
        return db

    def test_found_duplicate(self):
        db = self._make_db([
            {
                "id": "task-abc",
                "clickup_task_id": "cu-123",
                "status": "completed",
                "created_at": "2026-02-17T10:00:00Z",
            }
        ])
        result = check_duplicate(db, "some-key")
        assert result is not None
        assert result["agent_task_id"] == "task-abc"
        assert result["clickup_task_id"] == "cu-123"
        assert result["status"] == "completed"

    def test_no_duplicate(self):
        db = self._make_db([])
        result = check_duplicate(db, "some-key")
        assert result is None

    def test_empty_key_returns_none(self):
        db = MagicMock()
        result = check_duplicate(db, "")
        assert result is None
        db.table.assert_not_called()

    def test_queries_correct_table_and_filters(self):
        db = self._make_db([])
        check_duplicate(db, "my-key", window_hours=12)

        db.table.assert_called_once_with("agent_tasks")
        select_call = db.table.return_value.select
        select_call.assert_called_once_with("id, clickup_task_id, status, created_at")
        eq_call = select_call.return_value.eq
        eq_call.assert_called_once_with("source_reference", "my-key")


# ---------------------------------------------------------------------------
# 3) Retry / backoff
# ---------------------------------------------------------------------------


class TestRetryWithBackoff:
    @pytest.mark.asyncio
    async def test_success_on_first_try(self):
        fn = AsyncMock(return_value="ok")
        result = await retry_with_backoff(fn, base_backoff_s=0)
        assert result == "ok"
        assert fn.call_count == 1

    @pytest.mark.asyncio
    async def test_success_after_retry(self):
        fn = AsyncMock(side_effect=[ClickUpAPIError("timeout"), "ok"])
        result = await retry_with_backoff(fn, max_attempts=3, base_backoff_s=0)
        assert result == "ok"
        assert fn.call_count == 2

    @pytest.mark.asyncio
    async def test_fail_after_max_retries(self):
        fn = AsyncMock(side_effect=ClickUpAPIError("always fails"))
        with pytest.raises(RetryExhaustedError) as exc_info:
            await retry_with_backoff(fn, max_attempts=3, base_backoff_s=0)
        assert exc_info.value.attempts == 3
        assert isinstance(exc_info.value.last_error, ClickUpAPIError)
        assert fn.call_count == 3

    @pytest.mark.asyncio
    async def test_rate_limit_is_retryable(self):
        fn = AsyncMock(side_effect=[ClickUpRateLimitError("429"), "ok"])
        result = await retry_with_backoff(fn, max_attempts=3, base_backoff_s=0)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_non_retryable_propagates_immediately(self):
        """ClickUpValidationError is not in the retryable set — must propagate."""
        fn = AsyncMock(side_effect=ClickUpValidationError("bad request"))
        with pytest.raises(ClickUpValidationError):
            await retry_with_backoff(fn, max_attempts=3, base_backoff_s=0)
        assert fn.call_count == 1  # no retry

    @pytest.mark.asyncio
    async def test_custom_retryable(self):
        fn = AsyncMock(side_effect=[ValueError("oops"), "ok"])
        result = await retry_with_backoff(
            fn, max_attempts=3, base_backoff_s=0, retryable=(ValueError,)
        )
        assert result == "ok"


# ---------------------------------------------------------------------------
# 4) Orphan detection
# ---------------------------------------------------------------------------


class TestEmitOrphanEvent:
    def test_emits_event_with_task(self):
        db = MagicMock()
        task = ClickUpTask(id="cu-456", url="https://app.clickup.com/t/cu-456")

        emit_orphan_event(
            db,
            clickup_task=task,
            idempotency_key="key-abc",
            client_id="client-1",
            employee_id="emp-1",
            error="DB insert failed",
        )

        db.table.assert_called_once_with("agent_events")
        insert_call = db.table.return_value.insert
        insert_call.assert_called_once()
        row = insert_call.call_args[0][0]
        assert row["event_type"] == "clickup_orphan"
        assert row["client_id"] == "client-1"
        assert row["employee_id"] == "emp-1"
        assert row["payload"]["clickup_task_id"] == "cu-456"
        assert row["payload"]["clickup_task_url"] == "https://app.clickup.com/t/cu-456"
        assert row["payload"]["idempotency_key"] == "key-abc"
        assert row["payload"]["error"] == "DB insert failed"

    def test_emits_event_without_task(self):
        db = MagicMock()

        emit_orphan_event(
            db,
            clickup_task=None,
            idempotency_key="key-xyz",
            error="Unknown error",
        )

        row = db.table.return_value.insert.call_args[0][0]
        assert row["event_type"] == "clickup_orphan"
        assert "clickup_task_id" not in row["payload"]
        assert row["payload"]["idempotency_key"] == "key-xyz"

    def test_omits_null_client_and_employee(self):
        db = MagicMock()

        emit_orphan_event(
            db,
            clickup_task=None,
            idempotency_key="key",
            client_id=None,
            employee_id=None,
            error="oops",
        )

        row = db.table.return_value.insert.call_args[0][0]
        assert "client_id" not in row
        assert "employee_id" not in row

    def test_db_failure_does_not_raise(self):
        """emit_orphan_event must never throw, even if DB fails."""
        db = MagicMock()
        db.table.return_value.insert.return_value.execute.side_effect = RuntimeError("DB down")

        # Should not raise
        emit_orphan_event(
            db,
            clickup_task=None,
            idempotency_key="key",
            error="oops",
        )
