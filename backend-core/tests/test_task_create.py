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
    svc.get_brands_with_context_for_client.return_value = [
        {"id": "brand-1", "name": "Brand A", "clickup_space_id": "sp1", "clickup_list_id": "list1"},
    ]
    svc.get_profile_clickup_user_id.return_value = "12345"
    svc.list_clients_for_picker.return_value = [{"id": "c1", "name": "Acme"}]
    slack = AsyncMock()
    return svc, slack


from contextlib import contextmanager


@contextmanager
def _mock_reliability():
    """Patch C4A reliability helpers so existing C2 tests pass unchanged.

    - check_duplicate returns None (no duplicate)
    - retry_with_backoff is passthrough (just calls fn)
    - get_supabase_admin_client returns a mock DB
    """
    mock_db = MagicMock()

    async def _passthrough_retry(fn, **_kwargs):
        return await fn()

    with (
        patch("app.api.routes.slack.check_duplicate", return_value=None),
        patch("app.api.routes.slack.retry_with_backoff", side_effect=_passthrough_retry),
        patch("app.api.routes.slack.get_supabase_admin_client", return_value=mock_db),
    ):
        yield mock_db


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

    def test_ngram_no_legacy_intent_classifier(self):
        """Ngram requests should no longer route via deterministic intent classifier."""
        intent, _ = _classify_message("start ngram research")
        assert intent == "help"

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
        assert "confirm" in msg.lower()

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

        with _mock_reliability(), patch("app.api.routes.slack.get_clickup_service") as mock_cu:
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

        with _mock_reliability(), patch("app.api.routes.slack.get_clickup_service") as mock_cu:
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

        with _mock_reliability(), patch("app.api.routes.slack.get_clickup_service") as mock_cu:
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

        with _mock_reliability(), patch("app.api.routes.slack.get_clickup_service") as mock_cu:
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

        with _mock_reliability(), patch("app.api.routes.slack.get_clickup_service") as mock_cu:
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

        with _mock_reliability(), patch("app.api.routes.slack.get_clickup_service") as mock_cu:
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

        with _mock_reliability(), patch("app.api.routes.slack.get_clickup_service") as mock_cu:
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

        with _mock_reliability(), patch("app.api.routes.slack.get_clickup_service") as mock_cu:
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
        assert "confirm" in msg.lower()

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

        with _mock_reliability(), patch("app.api.routes.slack.get_clickup_service") as mock_cu:
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

        with _mock_reliability(), patch("app.api.routes.slack.get_clickup_service") as mock_cu:
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

    def test_ngram_no_legacy_intent(self):
        intent, _ = _classify_message("start ngram research")
        assert intent == "help"

    def test_weekly_tasks_still_works(self):
        intent, params = _classify_message("what's being worked on this week for Distex")
        assert intent == "weekly_tasks"

    def test_help_default_still_works(self):
        intent, _ = _classify_message("hello there")
        assert intent == "help"


# ---------------------------------------------------------------------------
# C10C.1: ASIN clarification flow
# ---------------------------------------------------------------------------


class TestAsinClarificationFlow:
    """Integration tests for the ASIN ambiguity guardrail in the confirm path."""

    @pytest.mark.asyncio
    async def test_confirm_with_asin_needed_asks_for_asin(self):
        """When enriched draft has open_questions, confirm asks for ASIN instead of creating."""
        svc, slack = _make_mocks()
        pending = {
            "awaiting": "confirm_or_details",
            "client_id": "client-1",
            "client_name": "Distex",
            "task_title": "Create coupon for summer sale",
        }
        session = FakeSession(context={"pending_task_create": pending})

        # Mock _enrich_task_draft to return a draft with open_questions
        mock_draft = {
            "title": "Create coupon for summer sale",
            "description": "Per SOP: Coupon Setup",
            "checklist": [],
            "citations": [],
            "confidence": 0.9,
            "needs_clarification": True,
            "clarification_question": "Please provide ASIN(s) or say \"create with ASIN pending\".",
            "open_questions": ["ASIN(s) or SKU(s) required for this product-scoped task."],
            "source_tiers_used": ["sop"],
        }

        with patch("app.api.routes.slack._enrich_task_draft", new_callable=AsyncMock, return_value=mock_draft):
            consumed = await _handle_pending_task_continuation(
                channel="C1",
                text="create anyway",
                session=session,
                session_service=svc,
                slack=slack,
                pending=pending,
            )

        assert consumed is True
        # Should have asked for ASIN, not created the task
        msg = slack.post_message.call_args.kwargs["text"]
        assert "ASIN" in msg
        # Pending state should be updated to asin_or_pending
        ctx = svc.update_context.call_args[0][1]
        assert ctx["pending_task_create"]["awaiting"] == "asin_or_pending"

    @pytest.mark.asyncio
    async def test_confirm_with_asin_pending_paraphrase_creates_unresolved(self):
        """Natural-language ASIN deferral in confirm state should create unresolved task directly."""
        svc, slack = _make_mocks()
        pending = {
            "awaiting": "confirm_or_details",
            "client_id": "client-1",
            "client_name": "Distex",
            "task_title": "Set up 20% coupon for Thorinox",
        }
        session = FakeSession(context={"pending_task_create": pending})
        fake_task = ClickUpTask(id="t1", url="https://clickup.com/t/t1")

        mock_draft = {
            "title": "Set up 20% coupon for Thorinox",
            "description": "Per SOP: Coupon Setup",
            "checklist": ["Validate coupon window"],
            "citations": [{"title": "Coupons Promotion SOP"}],
            "confidence": 0.95,
            "needs_clarification": True,
            "clarification_question": "Please provide ASIN(s) or SKU(s).",
            "open_questions": ["ASIN(s) or SKU(s) required for this product-scoped task."],
            "source_tiers_used": ["sop"],
        }

        with (
            _mock_reliability(),
            patch("app.api.routes.slack._enrich_task_draft", new_callable=AsyncMock, return_value=mock_draft),
            patch("app.api.routes.slack.get_clickup_service") as mock_cu,
        ):
            cu = AsyncMock()
            cu.create_task_in_list.return_value = fake_task
            mock_cu.return_value = cu

            consumed = await _handle_pending_task_continuation(
                channel="C1",
                text="go ahead without asin for now",
                session=session,
                session_service=svc,
                slack=slack,
                pending=pending,
            )

        assert consumed is True
        cu.create_task_in_list.assert_called_once()
        description = cu.create_task_in_list.call_args.kwargs["description_md"]
        assert "Unresolved" in description
        assert "ASIN" in description
        assert "go ahead without asin for now" not in description
        posted = [c.kwargs.get("text", "") for c in slack.post_message.await_args_list]
        assert not any("This looks like a product-level task" in t for t in posted)

    @pytest.mark.asyncio
    async def test_confirm_offtopic_falls_through(self):
        """Off-topic chat while awaiting confirm/details should not be consumed as task details."""
        svc, slack = _make_mocks()
        pending = {
            "awaiting": "confirm_or_details",
            "client_id": "client-1",
            "client_name": "Distex",
            "task_title": "Set up 20% coupon for Thorinox",
        }
        session = FakeSession(context={"pending_task_create": pending})

        consumed = await _handle_pending_task_continuation(
            channel="C1",
            text="what is plato all about?",
            session=session,
            session_service=svc,
            slack=slack,
            pending=pending,
        )

        assert consumed is False
        # Pending state should remain untouched so user can resume.
        assert svc.update_context.call_count == 0
        slack.post_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_asin_pending_creates_with_unresolved(self):
        """User says 'asin pending' → task created with unresolved section."""
        svc, slack = _make_mocks()
        pending = {
            "awaiting": "asin_or_pending",
            "client_id": "client-1",
            "client_name": "Distex",
            "task_title": "Create coupon",
            "draft": {
                "description": "Per SOP: Coupon Setup",
                "open_questions": ["ASIN(s) or SKU(s) required for this product-scoped task."],
            },
        }
        session = FakeSession(context={"pending_task_create": pending})
        fake_task = ClickUpTask(id="t1", url="https://clickup.com/t/t1")

        with _mock_reliability(), patch("app.api.routes.slack.get_clickup_service") as mock_cu:
            cu = AsyncMock()
            cu.create_task_in_list.return_value = fake_task
            mock_cu.return_value = cu

            consumed = await _handle_pending_task_continuation(
                channel="C1",
                text="create with asin pending",
                session=session,
                session_service=svc,
                slack=slack,
                pending=pending,
            )

        assert consumed is True
        call_kwargs = cu.create_task_in_list.call_args.kwargs
        assert "Unresolved" in call_kwargs["description_md"]
        assert "ASIN" in call_kwargs["description_md"]
        assert "First step" in call_kwargs["description_md"]

    @pytest.mark.asyncio
    async def test_user_provides_asin_creates_with_identifier(self):
        """User replies with ASIN → task created with identifier in body."""
        svc, slack = _make_mocks()
        pending = {
            "awaiting": "asin_or_pending",
            "client_id": "client-1",
            "client_name": "Distex",
            "task_title": "Create coupon",
            "draft": {
                "description": "Per SOP: Coupon Setup",
                "open_questions": ["ASIN(s) or SKU(s) required."],
            },
        }
        session = FakeSession(context={"pending_task_create": pending})
        fake_task = ClickUpTask(id="t1", url="https://clickup.com/t/t1")

        with _mock_reliability(), patch("app.api.routes.slack.get_clickup_service") as mock_cu:
            cu = AsyncMock()
            cu.create_task_in_list.return_value = fake_task
            mock_cu.return_value = cu

            consumed = await _handle_pending_task_continuation(
                channel="C1",
                text="B08XYZ1234",
                session=session,
                session_service=svc,
                slack=slack,
                pending=pending,
            )

        assert consumed is True
        call_kwargs = cu.create_task_in_list.call_args.kwargs
        assert "Product identifiers:" in call_kwargs["description_md"]
        assert "B08XYZ1234" in call_kwargs["description_md"]

    @pytest.mark.asyncio
    async def test_non_product_confirm_unchanged(self):
        """Non-product task confirm path works as before (regression)."""
        svc, slack = _make_mocks()
        pending = {
            "awaiting": "confirm_or_details",
            "client_id": "client-1",
            "client_name": "Distex",
            "task_title": "Fix landing page",
        }
        session = FakeSession(context={"pending_task_create": pending})
        fake_task = ClickUpTask(id="t1", url="https://clickup.com/t/t1")

        # Mock _enrich_task_draft to return a draft WITHOUT open_questions
        mock_draft = {
            "title": "Fix landing page",
            "description": "Per SOP: Copy Updates",
            "checklist": ["Review copy", "Update CTA"],
            "citations": [{"source_id": "copy", "title": "Copy SOP", "tier": "sop"}],
            "confidence": 0.9,
            "needs_clarification": False,
            "clarification_question": None,
            "open_questions": [],
            "source_tiers_used": ["sop"],
        }

        with (
            _mock_reliability(),
            patch("app.api.routes.slack._enrich_task_draft", new_callable=AsyncMock, return_value=mock_draft),
            patch("app.api.routes.slack.get_clickup_service") as mock_cu,
        ):
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
        # Task was created (not held for ASIN)
        cu.create_task_in_list.assert_called_once()
        call_kwargs = cu.create_task_in_list.call_args.kwargs
        assert "Per SOP" in call_kwargs["description_md"]

    @pytest.mark.asyncio
    async def test_asin_freetext_reasks_no_create(self):
        """User types non-identifier text in asin_or_pending → re-asks, no task created."""
        svc, slack = _make_mocks()
        pending = {
            "awaiting": "asin_or_pending",
            "client_id": "client-1",
            "client_name": "Distex",
            "task_title": "Create coupon",
            "draft": {
                "description": "",
                "open_questions": ["ASIN(s) or SKU(s) required."],
            },
        }
        session = FakeSession(context={"pending_task_create": pending})

        consumed = await _handle_pending_task_continuation(
            channel="C1",
            text="just go ahead with the summer promo ones",
            session=session,
            session_service=svc,
            slack=slack,
            pending=pending,
        )

        assert consumed is True
        # Should re-ask, not create
        msg = slack.post_message.call_args.kwargs["text"]
        assert "ASIN" in msg
        assert "pending" in msg.lower()

    @pytest.mark.asyncio
    async def test_asin_offtopic_message_falls_through(self):
        """Off-topic chat in asin_or_pending should not be trapped by ASIN re-asks."""
        svc, slack = _make_mocks()
        pending = {
            "awaiting": "asin_or_pending",
            "client_id": "client-1",
            "client_name": "Distex",
            "task_title": "Create coupon",
            "draft": {
                "description": "",
                "open_questions": ["ASIN(s) or SKU(s) required."],
            },
        }
        session = FakeSession(context={"pending_task_create": pending})

        consumed = await _handle_pending_task_continuation(
            channel="C1",
            text="you there?",
            session=session,
            session_service=svc,
            slack=slack,
            pending=pending,
        )

        assert consumed is False
        assert svc.update_context.call_count == 0
        slack.post_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_asin_known_intent_clears_state_and_falls_through(self):
        """Known intents should escape asin_or_pending and route normally."""
        svc, slack = _make_mocks()
        pending = {
            "awaiting": "asin_or_pending",
            "client_id": "client-1",
            "client_name": "Distex",
            "task_title": "Create coupon",
            "draft": {"description": "", "open_questions": ["ASIN required"]},
        }
        session = FakeSession(context={"pending_task_create": pending})

        consumed = await _handle_pending_task_continuation(
            channel="C1",
            text="what are the tasks for distex",
            session=session,
            session_service=svc,
            slack=slack,
            pending=pending,
        )

        assert consumed is False
        ctx = svc.update_context.call_args[0][1]
        assert ctx["pending_task_create"] is None
        slack.post_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_asin_cancel_clears_state(self):
        """Explicit cancel should end asin_or_pending immediately."""
        svc, slack = _make_mocks()
        pending = {
            "awaiting": "asin_or_pending",
            "client_id": "client-1",
            "client_name": "Distex",
            "task_title": "Create coupon",
            "draft": {"description": "", "open_questions": ["ASIN required"]},
        }
        session = FakeSession(context={"pending_task_create": pending})

        consumed = await _handle_pending_task_continuation(
            channel="C1",
            text="cancel",
            session=session,
            session_service=svc,
            slack=slack,
            pending=pending,
        )

        assert consumed is True
        ctx = svc.update_context.call_args[0][1]
        assert ctx["pending_task_create"] is None
        msg = slack.post_message.call_args.kwargs["text"]
        assert "canceled" in msg.lower()

    @pytest.mark.asyncio
    async def test_freetext_description_product_scoped_asks_asin(self):
        """Free-text description for product-scoped task → asks ASIN, doesn't create."""
        svc, slack = _make_mocks()
        pending = {
            "awaiting": "confirm_or_details",
            "client_id": "client-1",
            "client_name": "Distex",
            "task_title": "Create coupon for summer sale",
        }
        session = FakeSession(context={"pending_task_create": pending})

        consumed = await _handle_pending_task_continuation(
            channel="C1",
            text="Set up 20% off coupon for the summer promo",
            session=session,
            session_service=svc,
            slack=slack,
            pending=pending,
        )

        assert consumed is True
        # Should ask for ASIN, not create
        msg = slack.post_message.call_args.kwargs["text"]
        assert "ASIN" in msg
        # Should transition to asin_or_pending
        ctx = svc.update_context.call_args[0][1]
        assert ctx["pending_task_create"]["awaiting"] == "asin_or_pending"

    @pytest.mark.asyncio
    async def test_freetext_description_non_product_creates(self):
        """Free-text description for non-product task → creates normally (regression)."""
        svc, slack = _make_mocks()
        pending = {
            "awaiting": "confirm_or_details",
            "client_id": "client-1",
            "client_name": "Distex",
            "task_title": "Fix landing page",
        }
        session = FakeSession(context={"pending_task_create": pending})
        fake_task = ClickUpTask(id="t1", url="https://clickup.com/t/t1")

        with _mock_reliability(), patch("app.api.routes.slack.get_clickup_service") as mock_cu:
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
        cu.create_task_in_list.assert_called_once()
        call_kwargs = cu.create_task_in_list.call_args.kwargs
        assert "Q2 campaign" in call_kwargs["description_md"]

    @pytest.mark.asyncio
    async def test_freetext_description_with_asin_creates(self):
        """Free-text description with ASIN for product-scoped task → creates normally."""
        svc, slack = _make_mocks()
        pending = {
            "awaiting": "confirm_or_details",
            "client_id": "client-1",
            "client_name": "Distex",
            "task_title": "Create coupon",
        }
        session = FakeSession(context={"pending_task_create": pending})
        fake_task = ClickUpTask(id="t1", url="https://clickup.com/t/t1")

        with _mock_reliability(), patch("app.api.routes.slack.get_clickup_service") as mock_cu:
            cu = AsyncMock()
            cu.create_task_in_list.return_value = fake_task
            mock_cu.return_value = cu

            consumed = await _handle_pending_task_continuation(
                channel="C1",
                text="Set up coupon for B08XYZ1234",
                session=session,
                session_service=svc,
                slack=slack,
                pending=pending,
            )

        assert consumed is True
        cu.create_task_in_list.assert_called_once()


# ---------------------------------------------------------------------------
# C11D: Brand context resolution in task-create flow
# ---------------------------------------------------------------------------


class TestHandleCreateTaskBrandResolution:
    """Tests that brand resolver is wired into the task-create flow."""

    def _find_brand_picker(self, slack_mock) -> bool:
        """Check if any posted message contains select_brand_ action buttons."""
        for call in slack_mock.post_message.call_args_list:
            blocks = call.kwargs.get("blocks") or []
            for block in blocks:
                if isinstance(block, dict):
                    for el in block.get("elements", []):
                        if isinstance(el, dict) and str(el.get("action_id", "")).startswith("select_brand_"):
                            return True
        return False

    @pytest.mark.asyncio
    async def test_single_brand_no_picker(self):
        """Single mapped brand → client_level, no brand picker shown."""
        svc, slack = _make_mocks()
        # Single brand (default from _make_mocks)

        with _mock_reliability():
            await _handle_create_task(
                slack_user_id="U123",
                channel="C1",
                client_name_hint="Distex",
                task_title="Fix homepage banner",
                session_service=svc,
                slack=slack,
            )

        assert not self._find_brand_picker(slack)

    @pytest.mark.asyncio
    async def test_multi_brand_diff_dest_shows_picker(self):
        """Multiple brands with different destinations → brand picker posted."""
        svc, slack = _make_mocks()
        svc.get_brands_with_context_for_client.return_value = [
            {"id": "b1", "name": "Brand Alpha", "clickup_space_id": "sp1", "clickup_list_id": "l1"},
            {"id": "b2", "name": "Brand Beta", "clickup_space_id": "sp2", "clickup_list_id": "l2"},
        ]

        with _mock_reliability():
            await _handle_create_task(
                slack_user_id="U123",
                channel="C1",
                client_name_hint="Distex",
                task_title="Fix homepage",
                session_service=svc,
                slack=slack,
            )

        assert self._find_brand_picker(slack), "Expected brand picker with select_brand_ buttons"
        # Pending state should be awaiting brand
        ctx = svc.update_context.call_args[0][1]
        assert ctx["pending_task_create"]["awaiting"] == "brand"

    @pytest.mark.asyncio
    async def test_shared_dest_non_product_proceeds(self):
        """Multiple brands, shared destination, non-product request → client_level, no picker."""
        svc, slack = _make_mocks()
        svc.get_brands_with_context_for_client.return_value = [
            {"id": "b1", "name": "Brand Alpha", "clickup_space_id": "sp1", "clickup_list_id": "l1"},
            {"id": "b2", "name": "Brand Beta", "clickup_space_id": "sp1", "clickup_list_id": "l1"},
        ]

        with _mock_reliability():
            await _handle_create_task(
                slack_user_id="U123",
                channel="C1",
                client_name_hint="Distex",
                task_title="Update ad copy",
                session_service=svc,
                slack=slack,
            )

        assert not self._find_brand_picker(slack)
        # Should proceed to confirm (client_level)
        ctx = svc.update_context.call_args[0][1]
        assert ctx["pending_task_create"]["awaiting"] == "confirm_or_details"

    @pytest.mark.asyncio
    async def test_shared_dest_product_scoped_asks_brand(self):
        """Multiple brands, shared destination, product-scoped request → brand picker."""
        svc, slack = _make_mocks()
        svc.get_brands_with_context_for_client.return_value = [
            {"id": "b1", "name": "Brand Alpha", "clickup_space_id": "sp1", "clickup_list_id": "l1"},
            {"id": "b2", "name": "Brand Beta", "clickup_space_id": "sp1", "clickup_list_id": "l1"},
        ]

        with _mock_reliability():
            await _handle_create_task(
                slack_user_id="U123",
                channel="C1",
                client_name_hint="Distex",
                task_title="Create coupon for listing",
                session_service=svc,
                slack=slack,
            )

        assert self._find_brand_picker(slack), "Expected brand picker for product-scoped request"
        ctx = svc.update_context.call_args[0][1]
        assert ctx["pending_task_create"]["awaiting"] == "brand"

    @pytest.mark.asyncio
    async def test_no_destination_error(self):
        """No brands with ClickUp mappings → error message."""
        svc, slack = _make_mocks()
        svc.get_brands_with_context_for_client.return_value = [
            {"id": "b1", "name": "Orphan", "clickup_space_id": None, "clickup_list_id": None},
        ]

        with _mock_reliability():
            await _handle_create_task(
                slack_user_id="U123",
                channel="C1",
                client_name_hint="Distex",
                task_title="Fix homepage",
                session_service=svc,
                slack=slack,
            )

        messages = [call.kwargs.get("text", "") for call in slack.post_message.call_args_list]
        error_posted = any("no brand with clickup mapping" in (m or "").lower() for m in messages)
        assert error_posted, f"Expected no-destination error message, got: {messages}"

    @pytest.mark.asyncio
    async def test_brand_persisted_in_pending(self):
        """Resolved brand_id/brand_name appear in pending state."""
        svc, slack = _make_mocks()
        # Single brand → client_level with brand_context

        with _mock_reliability():
            await _handle_create_task(
                slack_user_id="U123",
                channel="C1",
                client_name_hint="Distex",
                task_title="Fix homepage banner",
                session_service=svc,
                slack=slack,
            )

        ctx = svc.update_context.call_args[0][1]
        pending = ctx.get("pending_task_create", {})
        assert pending.get("brand_id") == "brand-1"
        assert pending.get("brand_name") == "Brand A"
        assert pending.get("brand_resolution_mode") == "client_level"

    @pytest.mark.asyncio
    async def test_brand_passed_to_execute(self):
        """When brand resolved, _execute_task_create receives brand_id from pending."""
        svc, slack = _make_mocks()
        pending = {
            "awaiting": "confirm_or_details",
            "client_id": "client-1",
            "client_name": "Distex",
            "task_title": "Fix homepage",
            "brand_id": "brand-1",
            "brand_name": "Brand A",
            "brand_resolution_mode": "client_level",
        }
        session = FakeSession(context={"pending_task_create": pending})
        fake_task = ClickUpTask(id="t1", url="https://clickup.com/t/t1")

        # Mock the brand-by-ID query path in _execute_task_create
        brand_row = {"id": "brand-1", "name": "Brand A", "clickup_space_id": "sp1", "clickup_list_id": "list1"}
        mock_brand_response = MagicMock()
        mock_brand_response.data = [brand_row]
        svc.db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = mock_brand_response

        with _mock_reliability(), patch("app.api.routes.slack.get_clickup_service") as mock_cu:
            cu = AsyncMock()
            cu.create_task_in_list.return_value = fake_task
            mock_cu.return_value = cu

            consumed = await _handle_pending_task_continuation(
                channel="C1",
                text="yes",
                session=session,
                session_service=svc,
                slack=slack,
                pending=pending,
            )

        assert consumed is True
        cu.create_task_in_list.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_title_then_product_title_prompts_brand_picker(self):
        """If title is provided later and is product-scoped, resolver must re-ask brand."""
        svc, slack = _make_mocks()
        svc.get_brands_with_context_for_client.return_value = [
            {"id": "b1", "name": "Brand Alpha", "clickup_space_id": "sp1", "clickup_list_id": "l1"},
            {"id": "b2", "name": "Brand Beta", "clickup_space_id": "sp1", "clickup_list_id": "l1"},
        ]

        # Initial create with no title -> pending title
        with _mock_reliability():
            await _handle_create_task(
                slack_user_id="U123",
                channel="C1",
                client_name_hint="Distex",
                task_title="",
                session_service=svc,
                slack=slack,
            )

        initial_pending = svc.update_context.call_args[0][1]["pending_task_create"]
        assert initial_pending["awaiting"] == "title"
        assert initial_pending.get("brand_id") is None

        # User later provides product-scoped title -> should switch to brand picker.
        session = FakeSession(context={"pending_task_create": initial_pending})
        with _mock_reliability():
            consumed = await _handle_pending_task_continuation(
                channel="C1",
                text="Create coupon for Thorinox listing?",
                session=session,
                session_service=svc,
                slack=slack,
                pending=initial_pending,
            )

        assert consumed is True
        latest_pending = svc.update_context.call_args[0][1]["pending_task_create"]
        assert latest_pending["awaiting"] == "brand"
        assert latest_pending["task_title"] == "Create coupon for Thorinox listing?"
