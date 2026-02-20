"""Tests for clickup_task_list_weekly: intent classification, formatting, and handler."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.routes.slack import (
    _WEEKLY_TASK_CAP,
    _classify_message,
    _current_week_range_ms,
    _format_task_line,
    _format_weekly_tasks_response,
    _handle_weekly_tasks,
)


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------


class TestClassifyWeeklyTasks:
    """_classify_message should route weekly task queries correctly."""

    @pytest.mark.parametrize(
        "text",
        [
            "what's being worked on this week for Distex",
            "What is being worked on this week for Distex",
            "what's the tasks for Distex",
            "show tasks for Distex",
            "show me tasks for Distex",
            "list tasks for Distex",
            "weekly tasks for Distex",
            "tasks for Distex",
            "tasks for Distex this week",
            "this week's tasks for Distex",
        ],
    )
    def test_weekly_tasks_with_client(self, text: str):
        intent, params = _classify_message(text)
        assert intent == "weekly_tasks"
        assert params.get("client_name", "").lower().strip() == "distex"

    @pytest.mark.parametrize(
        "text",
        [
            "what's being worked on this week",
            "show tasks",
            "list tasks",
            "weekly tasks",
        ],
    )
    def test_weekly_tasks_no_client(self, text: str):
        intent, params = _classify_message(text)
        assert intent == "weekly_tasks"
        assert params.get("client_name", "") == ""

    def test_ngram_no_legacy_intent(self):
        intent, _ = _classify_message("start ngram research")
        assert intent == "help"

    def test_switch_still_works(self):
        intent, params = _classify_message("switch to Acme")
        assert intent == "switch_client"
        assert params["client_name"] == "acme"

    def test_help_default(self):
        intent, _ = _classify_message("hello")
        assert intent == "help"

    def test_multi_word_client_name(self):
        intent, params = _classify_message("tasks for Acme Corp International")
        assert intent == "weekly_tasks"
        assert "acme corp international" in params["client_name"].lower()

    def test_client_name_trailing_punctuation_is_sanitized(self):
        intent, params = _classify_message("what's being worked on this week for Distex?")
        assert intent == "weekly_tasks"
        assert params.get("client_name", "") == "distex"


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


class TestFormatTaskLine:
    def test_basic_task(self):
        task = {"name": "Fix bug", "url": "https://app.clickup.com/t/abc", "status": {"status": "in progress"}}
        line = _format_task_line(task)
        assert "<https://app.clickup.com/t/abc|Fix bug>" in line
        assert "[in progress]" in line

    def test_task_no_url(self):
        task = {"name": "Fix bug", "status": {"status": "open"}}
        line = _format_task_line(task)
        assert "Fix bug" in line
        assert "<" not in line

    def test_task_with_assignees(self):
        task = {
            "name": "Task",
            "url": "",
            "status": {"status": "open"},
            "assignees": [{"username": "alice"}, {"username": "bob"}],
        }
        line = _format_task_line(task)
        assert "alice" in line
        assert "bob" in line


class TestFormatWeeklyTasksResponse:
    def test_no_tasks(self):
        result = _format_weekly_tasks_response(
            client_name="Distex",
            tasks=[],
            total_fetched=0,
            brand_names=["Brand A"],
        )
        assert "No tasks found" in result
        assert "Distex" in result
        assert "Brand A" in result

    def test_some_tasks(self):
        tasks = [{"name": f"Task {i}", "id": str(i), "status": {"status": "open"}} for i in range(5)]
        result = _format_weekly_tasks_response(
            client_name="Distex",
            tasks=tasks,
            total_fetched=5,
            brand_names=["Brand A"],
        )
        assert "5 tasks" in result
        assert "Task 0" in result
        assert "Showing" not in result  # No truncation

    def test_truncation_notice(self):
        tasks = [{"name": f"Task {i}", "id": str(i), "status": {"status": "open"}} for i in range(_WEEKLY_TASK_CAP)]
        result = _format_weekly_tasks_response(
            client_name="Distex",
            tasks=tasks,
            total_fetched=_WEEKLY_TASK_CAP + 50,
            brand_names=["Brand A"],
        )
        assert f"Showing {_WEEKLY_TASK_CAP} of {_WEEKLY_TASK_CAP + 50}" in result

    def test_no_brands(self):
        result = _format_weekly_tasks_response(
            client_name="Distex",
            tasks=[],
            total_fetched=0,
            brand_names=[],
        )
        assert "no brands" in result


# ---------------------------------------------------------------------------
# Week range helper
# ---------------------------------------------------------------------------


class TestCurrentWeekRange:
    def test_returns_monday_to_next_monday(self):
        start_ms, end_ms = _current_week_range_ms()
        assert start_ms < end_ms
        # Difference should be exactly 7 days in ms
        assert end_ms - start_ms == 7 * 24 * 60 * 60 * 1000


# ---------------------------------------------------------------------------
# Handler integration (mocked services)
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


class TestHandleWeeklyTasks:
    """Integration tests for _handle_weekly_tasks with mocked dependencies."""

    def _make_mocks(self, **session_overrides):
        session = FakeSession(**session_overrides)
        session_svc = MagicMock()
        session_svc.get_or_create_session.return_value = session
        session_svc.find_client_matches.return_value = [{"id": "client-1", "name": "Distex"}]
        session_svc.get_client_name.return_value = "Distex"
        session_svc.get_all_brand_destinations_for_client.return_value = [
            {"id": "brand-1", "name": "Brand A", "clickup_space_id": "sp1", "clickup_list_id": "list1"},
        ]
        slack = AsyncMock()
        return session_svc, slack

    @pytest.mark.asyncio
    async def test_happy_path_with_client_hint(self):
        session_svc, slack = self._make_mocks()
        mock_tasks = [
            {"id": "t1", "name": "Task 1", "url": "https://clickup.com/t/t1", "status": {"status": "open"}},
            {"id": "t2", "name": "Task 2", "url": "https://clickup.com/t/t2", "status": {"status": "done"}},
        ]

        with patch("app.api.routes.slack.get_clickup_service") as mock_cu:
            cu_instance = AsyncMock()
            cu_instance.get_tasks_in_list_all_pages.return_value = mock_tasks
            mock_cu.return_value = cu_instance

            await _handle_weekly_tasks(
                slack_user_id="U123",
                channel="C1",
                client_name_hint="Distex",
                session_service=session_svc,
                slack=slack,
            )

        slack.post_message.assert_called_once()
        msg = slack.post_message.call_args.kwargs.get("text", "")
        assert "Task 1" in msg
        assert "Task 2" in msg
        assert "Distex" in msg

    @pytest.mark.asyncio
    async def test_ambiguous_client(self):
        session_svc, slack = self._make_mocks()
        session_svc.find_client_matches.return_value = [
            {"id": "c1", "name": "Distex US"},
            {"id": "c2", "name": "Distex CA"},
        ]

        await _handle_weekly_tasks(
            slack_user_id="U123",
            channel="C1",
            client_name_hint="Distex",
            session_service=session_svc,
            slack=slack,
        )

        slack.post_message.assert_called_once()
        call_kwargs = slack.post_message.call_args.kwargs
        assert "Multiple clients" in call_kwargs.get("text", "")
        assert call_kwargs.get("blocks") is not None

    @pytest.mark.asyncio
    async def test_no_matching_client(self):
        session_svc, slack = self._make_mocks()
        session_svc.find_client_matches.return_value = []

        await _handle_weekly_tasks(
            slack_user_id="U123",
            channel="C1",
            client_name_hint="NonExistent",
            session_service=session_svc,
            slack=slack,
        )

        msg = slack.post_message.call_args.kwargs.get("text", "")
        assert "couldn't find" in msg.lower()

    @pytest.mark.asyncio
    async def test_no_active_client_no_hint(self):
        session_svc, slack = self._make_mocks(active_client_id=None)
        session_svc.list_clients_for_picker.return_value = [{"id": "c1", "name": "Acme"}]

        await _handle_weekly_tasks(
            slack_user_id="U123",
            channel="C1",
            client_name_hint="",
            session_service=session_svc,
            slack=slack,
        )

        msg = slack.post_message.call_args.kwargs.get("text", "")
        assert "which client" in msg.lower()

    @pytest.mark.asyncio
    async def test_no_brand_mapping(self):
        session_svc, slack = self._make_mocks()
        session_svc.get_all_brand_destinations_for_client.return_value = []

        await _handle_weekly_tasks(
            slack_user_id="U123",
            channel="C1",
            client_name_hint="Distex",
            session_service=session_svc,
            slack=slack,
        )

        msg = slack.post_message.call_args.kwargs.get("text", "")
        assert "no brands" in msg.lower() or "clickup mapping" in msg.lower()

    @pytest.mark.asyncio
    async def test_clickup_failure(self):
        session_svc, slack = self._make_mocks()

        with patch("app.api.routes.slack.get_clickup_service") as mock_cu:
            mock_cu.side_effect = ClickUpConfigurationError("CLICKUP_API_TOKEN not set")

            await _handle_weekly_tasks(
                slack_user_id="U123",
                channel="C1",
                client_name_hint="Distex",
                session_service=session_svc,
                slack=slack,
            )

        msg = slack.post_message.call_args.kwargs.get("text", "")
        assert "failed" in msg.lower() or "clickup" in msg.lower()

    @pytest.mark.asyncio
    async def test_no_tasks_found(self):
        session_svc, slack = self._make_mocks()

        with patch("app.api.routes.slack.get_clickup_service") as mock_cu:
            cu_instance = AsyncMock()
            cu_instance.get_tasks_in_list_all_pages.return_value = []
            mock_cu.return_value = cu_instance

            await _handle_weekly_tasks(
                slack_user_id="U123",
                channel="C1",
                client_name_hint="Distex",
                session_service=session_svc,
                slack=slack,
            )

        msg = slack.post_message.call_args.kwargs.get("text", "")
        assert "no tasks found" in msg.lower()

    @pytest.mark.asyncio
    async def test_truncation_at_cap(self):
        session_svc, slack = self._make_mocks()
        oversized = [
            {"id": f"t{i}", "name": f"Task {i}", "status": {"status": "open"}}
            for i in range(_WEEKLY_TASK_CAP + 50)
        ]

        with patch("app.api.routes.slack.get_clickup_service") as mock_cu:
            cu_instance = AsyncMock()
            cu_instance.get_tasks_in_list_all_pages.return_value = oversized
            mock_cu.return_value = cu_instance

            await _handle_weekly_tasks(
                slack_user_id="U123",
                channel="C1",
                client_name_hint="Distex",
                session_service=session_svc,
                slack=slack,
            )

        msg = slack.post_message.call_args.kwargs.get("text", "")
        assert f"Showing {_WEEKLY_TASK_CAP}" in msg

    @pytest.mark.asyncio
    async def test_deduplicates_tasks_across_brands(self):
        """Same task appearing in multiple brand lists should not be duplicated."""
        session_svc, slack = self._make_mocks()
        session_svc.get_all_brand_destinations_for_client.return_value = [
            {"id": "b1", "name": "Brand A", "clickup_space_id": "sp1", "clickup_list_id": "list1"},
            {"id": "b2", "name": "Brand B", "clickup_space_id": "sp2", "clickup_list_id": "list2"},
        ]
        shared_task = {"id": "t1", "name": "Shared Task", "status": {"status": "open"}}

        with patch("app.api.routes.slack.get_clickup_service") as mock_cu:
            cu_instance = AsyncMock()
            # Both brands return the same task
            cu_instance.get_tasks_in_list_all_pages.return_value = [shared_task]
            mock_cu.return_value = cu_instance

            await _handle_weekly_tasks(
                slack_user_id="U123",
                channel="C1",
                client_name_hint="Distex",
                session_service=session_svc,
                slack=slack,
            )

        msg = slack.post_message.call_args.kwargs.get("text", "")
        assert msg.count("Shared Task") == 1

    @pytest.mark.asyncio
    async def test_uses_active_client_when_no_hint(self):
        session_svc, slack = self._make_mocks(active_client_id="client-1")

        with patch("app.api.routes.slack.get_clickup_service") as mock_cu:
            cu_instance = AsyncMock()
            cu_instance.get_tasks_in_list_all_pages.return_value = [
                {"id": "t1", "name": "Active Task", "status": {"status": "open"}},
            ]
            mock_cu.return_value = cu_instance

            await _handle_weekly_tasks(
                slack_user_id="U123",
                channel="C1",
                client_name_hint="",
                session_service=session_svc,
                slack=slack,
            )

        session_svc.get_all_brand_destinations_for_client.assert_called_with("client-1")
        msg = slack.post_message.call_args.kwargs.get("text", "")
        assert "Active Task" in msg


# Need to import the exception for the clickup failure test
from app.services.clickup import ClickUpConfigurationError
