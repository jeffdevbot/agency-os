"""Tests for clickup_task_create (C2): intent, thin-task clarification, draft confirm, handler."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.routes.slack import (
    _classify_message,
    _execute_task_create,
    _handle_create_task,
    _handle_pending_task_continuation,
)
from app.services.clickup import (
    ClickUpConfigurationError,
    ClickUpError,
    ClickUpTask,
)


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


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------


class TestClassifyCreateTask:
    @pytest.mark.parametrize(
        "text,expected_client,expected_title",
        [
            ("create task for Distex: Fix landing page", "distex", "Fix landing page"),
            ("Create a task for Distex: Fix landing page", "distex", "Fix landing page"),
            ("add task for Distex: Fix landing page", "distex", "Fix landing page"),
            ("new task for Distex: Fix landing page", "distex", "Fix landing page"),
            ("create task: Fix landing page", "", "Fix landing page"),
            ("add a task: Update copy", "", "Update copy"),
        ],
    )
    def test_create_task_with_title(self, text: str, expected_client: str, expected_title: str):
        intent, params = _classify_message(text)
        assert intent == "create_task"
        assert params["client_name"].lower().strip() == expected_client
        assert params["task_title"] == expected_title

    def test_title_casing_preserved(self):
        """Task title should keep original casing, not be lowercased."""
        intent, params = _classify_message("create task for Distex: Prime Promotions Q4")
        assert intent == "create_task"
        assert params["task_title"] == "Prime Promotions Q4"

    @pytest.mark.parametrize(
        "text,expected_client",
        [
            ("create task for Distex", "distex"),
            ("create a task for Distex", "distex"),
            ("add task for Distex", "distex"),
            ("new task for Acme Corp", "acme corp"),
        ],
    )
    def test_create_task_no_title(self, text: str, expected_client: str):
        intent, params = _classify_message(text)
        assert intent == "create_task"
        assert params["client_name"].lower().strip() == expected_client
        assert params["task_title"] == ""

    def test_create_task_no_client_no_title(self):
        intent, params = _classify_message("create task")
        assert intent == "create_task"
        assert params["client_name"] == ""
        assert params["task_title"] == ""

    @pytest.mark.parametrize(
        "text",
        [
            "create anyway",
            "create as draft",
            "just create it",
            "yes, create",
            "yes create it",
        ],
    )
    def test_confirm_draft_patterns(self, text: str):
        intent, _ = _classify_message(text)
        assert intent == "confirm_draft_task"

    def test_ngram_not_captured_as_create(self):
        """Ngram intent should still take priority over create_task."""
        intent, _ = _classify_message("start ngram research")
        assert intent == "create_ngram_task"

    def test_weekly_tasks_not_captured_as_create(self):
        intent, _ = _classify_message("show tasks for Distex")
        assert intent == "weekly_tasks"


# ---------------------------------------------------------------------------
# _handle_create_task
# ---------------------------------------------------------------------------


class TestHandleCreateTask:
    @pytest.mark.asyncio
    async def test_no_title_asks_for_title(self):
        svc, slack = _make_mocks()
        await _handle_create_task(
            slack_user_id="U123",
            channel="C1",
            client_name_hint="Distex",
            task_title="",
            session_service=svc,
            slack=slack,
        )
        svc.update_context.assert_called_once()
        ctx = svc.update_context.call_args[0][1]
        assert ctx["pending_task_create"]["awaiting"] == "title"
        assert ctx["pending_task_create"]["client_id"] == "client-1"
        msg = slack.post_message.call_args.kwargs["text"]
        assert "title" in msg.lower()

    @pytest.mark.asyncio
    async def test_has_title_asks_confirm_or_details(self):
        svc, slack = _make_mocks()
        await _handle_create_task(
            slack_user_id="U123",
            channel="C1",
            client_name_hint="Distex",
            task_title="Fix landing page",
            session_service=svc,
            slack=slack,
        )
        ctx = svc.update_context.call_args[0][1]
        assert ctx["pending_task_create"]["awaiting"] == "confirm_or_details"
        assert ctx["pending_task_create"]["task_title"] == "Fix landing page"
        msg = slack.post_message.call_args.kwargs["text"]
        assert "create anyway" in msg.lower()

    @pytest.mark.asyncio
    async def test_ambiguous_client(self):
        svc, slack = _make_mocks()
        svc.find_client_matches.return_value = [
            {"id": "c1", "name": "Distex US"},
            {"id": "c2", "name": "Distex CA"},
        ]
        await _handle_create_task(
            slack_user_id="U123",
            channel="C1",
            client_name_hint="Distex",
            task_title="Fix it",
            session_service=svc,
            slack=slack,
        )
        msg = slack.post_message.call_args.kwargs["text"]
        assert "multiple" in msg.lower()

    @pytest.mark.asyncio
    async def test_no_matching_client(self):
        svc, slack = _make_mocks()
        svc.find_client_matches.return_value = []
        await _handle_create_task(
            slack_user_id="U123",
            channel="C1",
            client_name_hint="FakeClient",
            task_title="Fix it",
            session_service=svc,
            slack=slack,
        )
        msg = slack.post_message.call_args.kwargs["text"]
        assert "couldn't find" in msg.lower()

    @pytest.mark.asyncio
    async def test_no_client_hint_uses_active(self):
        svc, slack = _make_mocks(active_client_id="client-1")
        await _handle_create_task(
            slack_user_id="U123",
            channel="C1",
            client_name_hint="",
            task_title="Fix landing page",
            session_service=svc,
            slack=slack,
        )
        ctx = svc.update_context.call_args[0][1]
        assert ctx["pending_task_create"]["client_id"] == "client-1"

    @pytest.mark.asyncio
    async def test_no_client_hint_no_active_shows_picker(self):
        svc, slack = _make_mocks(active_client_id=None)
        await _handle_create_task(
            slack_user_id="U123",
            channel="C1",
            client_name_hint="",
            task_title="Fix landing page",
            session_service=svc,
            slack=slack,
        )
        msg = slack.post_message.call_args.kwargs["text"]
        assert "which client" in msg.lower()


# ---------------------------------------------------------------------------
# _execute_task_create
# ---------------------------------------------------------------------------


class TestExecuteTaskCreate:
    @pytest.mark.asyncio
    async def test_happy_path_returns_url(self):
        svc, slack = _make_mocks()
        session = FakeSession()
        fake_task = ClickUpTask(id="task123", url="https://app.clickup.com/t/task123")

        with patch("app.api.routes.slack.get_clickup_service") as mock_cu:
            cu = AsyncMock()
            cu.create_task_in_list.return_value = fake_task
            mock_cu.return_value = cu

            await _execute_task_create(
                channel="C1",
                session=session,
                session_service=svc,
                slack=slack,
                client_id="client-1",
                client_name="Distex",
                task_title="Fix landing page",
                task_description="Detailed description here",
            )

        msg = slack.post_message.call_args.kwargs["text"]
        assert "https://app.clickup.com/t/task123" in msg
        assert "Fix landing page" in msg
        assert "draft" not in msg.lower()  # has description, so not a draft

    @pytest.mark.asyncio
    async def test_draft_shows_draft_notice(self):
        svc, slack = _make_mocks()
        session = FakeSession()
        fake_task = ClickUpTask(id="task123", url="https://app.clickup.com/t/task123")

        with patch("app.api.routes.slack.get_clickup_service") as mock_cu:
            cu = AsyncMock()
            cu.create_task_in_list.return_value = fake_task
            mock_cu.return_value = cu

            await _execute_task_create(
                channel="C1",
                session=session,
                session_service=svc,
                slack=slack,
                client_id="client-1",
                client_name="Distex",
                task_title="Fix landing page",
                task_description="",
            )

        msg = slack.post_message.call_args.kwargs["text"]
        assert "draft" in msg.lower()

    @pytest.mark.asyncio
    async def test_no_brand_mapping_fails_closed(self):
        svc, slack = _make_mocks()
        svc.get_brand_destination_for_client.return_value = None
        session = FakeSession()

        await _execute_task_create(
            channel="C1",
            session=session,
            session_service=svc,
            slack=slack,
            client_id="client-1",
            client_name="Distex",
            task_title="Fix it",
            task_description="",
        )

        msg = slack.post_message.call_args.kwargs["text"]
        assert "no brand" in msg.lower() or "clickup mapping" in msg.lower()

    @pytest.mark.asyncio
    async def test_no_profile_fails(self):
        svc, slack = _make_mocks()
        session = FakeSession(profile_id=None)

        await _execute_task_create(
            channel="C1",
            session=session,
            session_service=svc,
            slack=slack,
            client_id="client-1",
            client_name="Distex",
            task_title="Fix it",
            task_description="",
        )

        msg = slack.post_message.call_args.kwargs["text"]
        assert "profile" in msg.lower()

    @pytest.mark.asyncio
    async def test_clickup_failure(self):
        svc, slack = _make_mocks()
        session = FakeSession()

        with patch("app.api.routes.slack.get_clickup_service") as mock_cu:
            cu = AsyncMock()
            cu.create_task_in_list.side_effect = ClickUpError("timeout")
            mock_cu.return_value = cu

            await _execute_task_create(
                channel="C1",
                session=session,
                session_service=svc,
                slack=slack,
                client_id="client-1",
                client_name="Distex",
                task_title="Fix it",
                task_description="details",
            )

        msg = slack.post_message.call_args.kwargs["text"]
        assert "failed" in msg.lower()

    @pytest.mark.asyncio
    async def test_clears_pending_context_on_success(self):
        svc, slack = _make_mocks()
        session = FakeSession()
        fake_task = ClickUpTask(id="t1", url="https://clickup.com/t/t1")

        with patch("app.api.routes.slack.get_clickup_service") as mock_cu:
            cu = AsyncMock()
            cu.create_task_in_list.return_value = fake_task
            mock_cu.return_value = cu

            await _execute_task_create(
                channel="C1",
                session=session,
                session_service=svc,
                slack=slack,
                client_id="client-1",
                client_name="Distex",
                task_title="Fix it",
                task_description="",
            )

        # update_context should have been called to clear pending_task_create
        calls = svc.update_context.call_args_list
        cleared = any(
            call[0][1].get("pending_task_create") is None
            for call in calls
        )
        assert cleared

    @pytest.mark.asyncio
    async def test_clears_pending_context_on_failure(self):
        svc, slack = _make_mocks()
        session = FakeSession()

        with patch("app.api.routes.slack.get_clickup_service") as mock_cu:
            cu = AsyncMock()
            cu.create_task_in_list.side_effect = ClickUpError("boom")
            mock_cu.return_value = cu

            await _execute_task_create(
                channel="C1",
                session=session,
                session_service=svc,
                slack=slack,
                client_id="client-1",
                client_name="Distex",
                task_title="Fix it",
                task_description="",
            )

        calls = svc.update_context.call_args_list
        cleared = any(
            call[0][1].get("pending_task_create") is None
            for call in calls
        )
        assert cleared

    @pytest.mark.asyncio
    async def test_includes_brand_name_in_response(self):
        svc, slack = _make_mocks()
        session = FakeSession()
        fake_task = ClickUpTask(id="t1", url="https://clickup.com/t/t1")

        with patch("app.api.routes.slack.get_clickup_service") as mock_cu:
            cu = AsyncMock()
            cu.create_task_in_list.return_value = fake_task
            mock_cu.return_value = cu

            await _execute_task_create(
                channel="C1",
                session=session,
                session_service=svc,
                slack=slack,
                client_id="client-1",
                client_name="Distex",
                task_title="Fix it",
                task_description="desc",
            )

        msg = slack.post_message.call_args.kwargs["text"]
        assert "Brand A" in msg

    @pytest.mark.asyncio
    async def test_clears_pending_on_no_profile(self):
        """Early failure (no profile) must still clear pending_task_create."""
        svc, slack = _make_mocks()
        session = FakeSession(profile_id=None)

        await _execute_task_create(
            channel="C1",
            session=session,
            session_service=svc,
            slack=slack,
            client_id="client-1",
            client_name="Distex",
            task_title="Fix it",
            task_description="",
        )

        calls = svc.update_context.call_args_list
        cleared = any(
            call[0][1].get("pending_task_create") is None for call in calls
        )
        assert cleared

    @pytest.mark.asyncio
    async def test_clears_pending_on_no_brand_mapping(self):
        """Early failure (no brand) must still clear pending_task_create."""
        svc, slack = _make_mocks()
        svc.get_brand_destination_for_client.return_value = None
        session = FakeSession()

        await _execute_task_create(
            channel="C1",
            session=session,
            session_service=svc,
            slack=slack,
            client_id="client-1",
            client_name="Distex",
            task_title="Fix it",
            task_description="",
        )

        calls = svc.update_context.call_args_list
        cleared = any(
            call[0][1].get("pending_task_create") is None for call in calls
        )
        assert cleared

    @pytest.mark.asyncio
    async def test_list_only_brand_works(self):
        """Brand with clickup_list_id but no clickup_space_id should still create tasks."""
        svc, slack = _make_mocks()
        svc.get_brand_destination_for_client.return_value = {
            "id": "brand-2",
            "name": "List-Only Brand",
            "clickup_space_id": None,
            "clickup_list_id": "list42",
        }
        session = FakeSession()
        fake_task = ClickUpTask(id="t1", url="https://clickup.com/t/t1")

        with patch("app.api.routes.slack.get_clickup_service") as mock_cu:
            cu = AsyncMock()
            cu.create_task_in_list.return_value = fake_task
            mock_cu.return_value = cu

            await _execute_task_create(
                channel="C1",
                session=session,
                session_service=svc,
                slack=slack,
                client_id="client-1",
                client_name="Distex",
                task_title="Fix it",
                task_description="desc",
            )

        cu.create_task_in_list.assert_called_once()
        assert cu.create_task_in_list.call_args.kwargs["list_id"] == "list42"
        msg = slack.post_message.call_args.kwargs["text"]
        assert "Task created" in msg

    @pytest.mark.asyncio
    async def test_space_only_brand_falls_back(self):
        """Brand with clickup_space_id but no clickup_list_id should use space fallback."""
        svc, slack = _make_mocks()
        svc.get_brand_destination_for_client.return_value = {
            "id": "brand-3",
            "name": "Space-Only Brand",
            "clickup_space_id": "sp99",
            "clickup_list_id": None,
        }
        session = FakeSession()
        fake_task = ClickUpTask(id="t1", url="https://clickup.com/t/t1")

        with patch("app.api.routes.slack.get_clickup_service") as mock_cu:
            cu = AsyncMock()
            cu.create_task_in_space.return_value = fake_task
            mock_cu.return_value = cu

            await _execute_task_create(
                channel="C1",
                session=session,
                session_service=svc,
                slack=slack,
                client_id="client-1",
                client_name="Distex",
                task_title="Fix it",
                task_description="desc",
            )

        cu.create_task_in_space.assert_called_once()
        assert cu.create_task_in_space.call_args.kwargs["space_id"] == "sp99"


# ---------------------------------------------------------------------------
# Pending-state continuation
# ---------------------------------------------------------------------------


class TestPendingTaskContinuation:
    @pytest.mark.asyncio
    async def test_title_continuation(self):
        """When awaiting title, user's message becomes the title."""
        svc, slack = _make_mocks()
        pending = {"awaiting": "title", "client_id": "client-1", "client_name": "Distex"}
        session = FakeSession(context={"pending_task_create": pending})

        consumed = await _handle_pending_task_continuation(
            channel="C1",
            text="Fix the landing page",
            session=session,
            session_service=svc,
            slack=slack,
            pending=pending,
        )

        assert consumed is True
        ctx = svc.update_context.call_args[0][1]
        assert ctx["pending_task_create"]["awaiting"] == "confirm_or_details"
        assert ctx["pending_task_create"]["task_title"] == "Fix the landing page"
        msg = slack.post_message.call_args.kwargs["text"]
        assert "create anyway" in msg.lower()

    @pytest.mark.asyncio
    async def test_confirm_draft_continuation(self):
        """When awaiting confirm, 'create anyway' triggers creation."""
        svc, slack = _make_mocks()
        pending = {
            "awaiting": "confirm_or_details",
            "client_id": "client-1",
            "client_name": "Distex",
            "task_title": "Fix landing page",
        }
        session = FakeSession(context={"pending_task_create": pending})
        fake_task = ClickUpTask(id="t1", url="https://clickup.com/t/t1")

        with patch("app.api.routes.slack.get_clickup_service") as mock_cu:
            cu = AsyncMock()
            cu.create_task_in_list.return_value = fake_task
            mock_cu.return_value = cu

            consumed = await _handle_pending_task_continuation(
                channel="C1",
                text="create anyway",
                session=session,
                session_service=svc,
                slack=slack,
                pending=pending,
            )

        assert consumed is True
        msg = slack.post_message.call_args.kwargs["text"]
        assert "https://clickup.com/t/t1" in msg
        assert "draft" in msg.lower()

    @pytest.mark.asyncio
    async def test_description_continuation(self):
        """When awaiting confirm, non-confirm text becomes description."""
        svc, slack = _make_mocks()
        pending = {
            "awaiting": "confirm_or_details",
            "client_id": "client-1",
            "client_name": "Distex",
            "task_title": "Fix landing page",
        }
        session = FakeSession(context={"pending_task_create": pending})
        fake_task = ClickUpTask(id="t1", url="https://clickup.com/t/t1")

        with patch("app.api.routes.slack.get_clickup_service") as mock_cu:
            cu = AsyncMock()
            cu.create_task_in_list.return_value = fake_task
            mock_cu.return_value = cu

            consumed = await _handle_pending_task_continuation(
                channel="C1",
                text="The hero section copy needs updating for Q2 campaign.",
                session=session,
                session_service=svc,
                slack=slack,
                pending=pending,
            )

        assert consumed is True
        # Verify task was created with description
        cu.create_task_in_list.assert_called_once()
        call_kwargs = cu.create_task_in_list.call_args.kwargs
        assert call_kwargs["name"] == "Fix landing page"
        assert "Q2 campaign" in call_kwargs["description_md"]
        msg = slack.post_message.call_args.kwargs["text"]
        assert "draft" not in msg.lower()  # has description

    @pytest.mark.asyncio
    async def test_known_intent_not_consumed_as_description(self):
        """When awaiting confirm_or_details, a known intent should NOT be consumed as description."""
        svc, slack = _make_mocks()
        pending = {
            "awaiting": "confirm_or_details",
            "client_id": "client-1",
            "client_name": "Distex",
            "task_title": "Fix landing page",
        }
        session = FakeSession(context={"pending_task_create": pending})

        consumed = await _handle_pending_task_continuation(
            channel="C1",
            text="switch to Acme",
            session=session,
            session_service=svc,
            slack=slack,
            pending=pending,
        )

        assert consumed is False
        # Should have cleared pending state
        ctx = svc.update_context.call_args[0][1]
        assert ctx["pending_task_create"] is None

    @pytest.mark.asyncio
    async def test_known_intent_not_consumed_as_title(self):
        """When awaiting title, a known intent should NOT be consumed as the task title."""
        svc, slack = _make_mocks()
        pending = {"awaiting": "title", "client_id": "client-1", "client_name": "Distex"}
        session = FakeSession(context={"pending_task_create": pending})

        consumed = await _handle_pending_task_continuation(
            channel="C1",
            text="switch to Acme",
            session=session,
            session_service=svc,
            slack=slack,
            pending=pending,
        )

        assert consumed is False
        # Should have cleared pending state
        ctx = svc.update_context.call_args[0][1]
        assert ctx["pending_task_create"] is None

    @pytest.mark.asyncio
    async def test_empty_title_does_not_consume(self):
        """Empty text when awaiting title should fall through."""
        svc, slack = _make_mocks()
        pending = {"awaiting": "title", "client_id": "c1", "client_name": "Distex"}
        session = FakeSession(context={"pending_task_create": pending})

        consumed = await _handle_pending_task_continuation(
            channel="C1",
            text="   ",
            session=session,
            session_service=svc,
            slack=slack,
            pending=pending,
        )
        assert consumed is False

    @pytest.mark.asyncio
    async def test_unknown_awaiting_clears_state(self):
        """Unknown awaiting state should clear pending and not consume."""
        svc, slack = _make_mocks()
        pending = {"awaiting": "something_invalid"}
        session = FakeSession(context={"pending_task_create": pending})

        consumed = await _handle_pending_task_continuation(
            channel="C1",
            text="hello",
            session=session,
            session_service=svc,
            slack=slack,
            pending=pending,
        )
        assert consumed is False
        ctx = svc.update_context.call_args[0][1]
        assert ctx["pending_task_create"] is None


# ---------------------------------------------------------------------------
# C1 regression: existing intents still work
# ---------------------------------------------------------------------------


class TestC1RegressionFromC2:
    def test_switch_client_still_works(self):
        intent, params = _classify_message("switch to Acme")
        assert intent == "switch_client"

    def test_ngram_still_works(self):
        intent, _ = _classify_message("start ngram research")
        assert intent == "create_ngram_task"

    def test_weekly_tasks_still_works(self):
        intent, params = _classify_message("what's being worked on this week for Distex")
        assert intent == "weekly_tasks"

    def test_help_default_still_works(self):
        intent, _ = _classify_message("hello there")
        assert intent == "help"
