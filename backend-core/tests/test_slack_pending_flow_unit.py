"""C14X: Unit tests for slack_pending_flow.py extracted module.

Covers:
- compose_asin_pending_description: various draft shapes (empty, with description,
  with checklist, with citations, with open_questions)
- handle_pending_task_continuation: all awaiting states with mocked callbacks
  (brand, title, confirm_or_details, asin_or_pending)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.agencyclaw.slack_pending_flow import (
    compose_asin_pending_description,
    handle_pending_task_continuation,
)


# ---------------------------------------------------------------------------
# compose_asin_pending_description
# ---------------------------------------------------------------------------


class TestComposeAsinPendingDescription:
    def test_none_draft(self) -> None:
        result = compose_asin_pending_description(None)
        assert "Unresolved" in result
        assert "First step" in result

    def test_empty_draft(self) -> None:
        result = compose_asin_pending_description({})
        assert "Unresolved" in result

    def test_with_description(self) -> None:
        draft = {"description": "Set up 20% coupon for Thorinox"}
        result = compose_asin_pending_description(draft)
        assert "Set up 20% coupon" in result
        assert "Unresolved" in result

    def test_with_checklist(self) -> None:
        draft = {"checklist": ["Step 1", "Step 2"]}
        result = compose_asin_pending_description(draft)
        assert "Checklist" in result
        assert "Step 1" in result
        assert "Step 2" in result

    def test_with_citations(self) -> None:
        draft = {"citations": [{"title": "SOP: Coupon Setup"}]}
        result = compose_asin_pending_description(draft)
        assert "Sources" in result
        assert "SOP: Coupon Setup" in result

    def test_with_custom_open_questions(self) -> None:
        draft = {"open_questions": ["What ASIN?", "Which marketplace?"]}
        result = compose_asin_pending_description(draft)
        assert "What ASIN?" in result
        assert "Which marketplace?" in result

    def test_full_draft(self) -> None:
        draft = {
            "description": "Some desc",
            "checklist": ["A", "B"],
            "citations": [{"title": "Ref1"}],
            "open_questions": ["Q1"],
        }
        result = compose_asin_pending_description(draft)
        assert "Some desc" in result
        assert "Checklist" in result
        assert "Sources" in result
        assert "Q1" in result


# ---------------------------------------------------------------------------
# handle_pending_task_continuation helpers
# ---------------------------------------------------------------------------


def _make_session(profile_id: str = "prof1", active_client_id: str | None = None) -> MagicMock:
    s = MagicMock()
    s.id = "sess1"
    s.profile_id = profile_id
    s.active_client_id = active_client_id
    return s


def _make_session_service() -> MagicMock:
    ss = MagicMock()
    ss.update_context = MagicMock()
    return ss


def _make_slack() -> AsyncMock:
    return AsyncMock()


def _classify_help(text: str) -> tuple[str, dict]:
    """Default: classify everything as 'help' (not an interrupting intent)."""
    return ("help", {})


def _classify_switch(text: str) -> tuple[str, dict]:
    """Simulate a 'switch_client' intent — triggers interrupt."""
    return ("switch_client", {"client_name": "acme"})


# ---------------------------------------------------------------------------
# awaiting == "brand"
# ---------------------------------------------------------------------------


class TestPendingBrand:
    @pytest.mark.asyncio
    async def test_brand_resolved_single_match_with_title(self) -> None:
        """Brand hint resolves to single match, title already present -> confirm."""
        session = _make_session()
        session_service = _make_session_service()
        slack = _make_slack()

        resolve_brand = AsyncMock(return_value={
            "mode": "single_match",
            "brand_context": {"id": "b1", "name": "Alpha"},
            "candidates": [],
        })

        pending = {
            "awaiting": "brand",
            "client_id": "c1",
            "client_name": "Acme",
            "task_title": "Set up coupon",
        }

        result = await handle_pending_task_continuation(
            channel="C01",
            text="Alpha",
            session=session,
            session_service=session_service,
            slack=slack,
            pending=pending,
            classify_message=_classify_help,
            resolve_brand_for_task=resolve_brand,
            enrich_task_draft=AsyncMock(),
            execute_task_create=AsyncMock(),
            extract_product_identifiers=MagicMock(return_value=[]),
        )

        assert result is True
        slack.post_message.assert_called_once()
        call_kwargs = slack.post_message.call_args[1]
        assert "Set up coupon" in call_kwargs.get("text", "")

    @pytest.mark.asyncio
    async def test_brand_resolved_no_title_asks_for_title(self) -> None:
        """Brand resolves but no task_title -> awaiting 'title'."""
        session = _make_session()
        session_service = _make_session_service()
        slack = _make_slack()

        resolve_brand = AsyncMock(return_value={
            "mode": "single_match",
            "brand_context": {"id": "b1", "name": "Alpha"},
            "candidates": [],
        })

        pending = {
            "awaiting": "brand",
            "client_id": "c1",
            "client_name": "Acme",
            "task_title": "",
        }

        result = await handle_pending_task_continuation(
            channel="C01",
            text="Alpha",
            session=session,
            session_service=session_service,
            slack=slack,
            pending=pending,
            classify_message=_classify_help,
            resolve_brand_for_task=resolve_brand,
            enrich_task_draft=AsyncMock(),
            execute_task_create=AsyncMock(),
            extract_product_identifiers=MagicMock(return_value=[]),
        )

        assert result is True
        slack.post_message.assert_called_once()
        msg = slack.post_message.call_args[1].get("text", "")
        assert "task" in msg.lower() or "called" in msg.lower()

    @pytest.mark.asyncio
    async def test_brand_ambiguous_returns_true(self) -> None:
        """Ambiguous brand -> returns True (prompt shown by resolve_brand_for_task)."""
        session = _make_session()
        session_service = _make_session_service()
        slack = _make_slack()

        resolve_brand = AsyncMock(return_value={
            "mode": "ambiguous_brand",
            "brand_context": None,
            "candidates": [{"id": "b1", "name": "A"}, {"id": "b2", "name": "B"}],
        })

        pending = {
            "awaiting": "brand",
            "client_id": "c1",
            "client_name": "Acme",
            "task_title": "Title",
        }

        result = await handle_pending_task_continuation(
            channel="C01",
            text="Alpha",
            session=session,
            session_service=session_service,
            slack=slack,
            pending=pending,
            classify_message=_classify_help,
            resolve_brand_for_task=resolve_brand,
            enrich_task_draft=AsyncMock(),
            execute_task_create=AsyncMock(),
            extract_product_identifiers=MagicMock(return_value=[]),
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_brand_no_destination(self) -> None:
        """No destination -> message posted, returns True."""
        session = _make_session()
        session_service = _make_session_service()
        slack = _make_slack()

        resolve_brand = AsyncMock(return_value={
            "mode": "no_destination",
            "brand_context": None,
            "candidates": [],
        })

        pending = {
            "awaiting": "brand",
            "client_id": "c1",
            "client_name": "Acme",
            "task_title": "Title",
        }

        result = await handle_pending_task_continuation(
            channel="C01",
            text="Nonexistent",
            session=session,
            session_service=session_service,
            slack=slack,
            pending=pending,
            classify_message=_classify_help,
            resolve_brand_for_task=resolve_brand,
            enrich_task_draft=AsyncMock(),
            execute_task_create=AsyncMock(),
            extract_product_identifiers=MagicMock(return_value=[]),
        )

        assert result is True
        assert "No matching brand" in slack.post_message.call_args[1].get("text", "")

    @pytest.mark.asyncio
    async def test_brand_interrupt_on_new_intent(self) -> None:
        """Non-help intent during brand awaiting -> clears pending, returns False."""
        session = _make_session()
        session_service = _make_session_service()
        slack = _make_slack()

        pending = {
            "awaiting": "brand",
            "client_id": "c1",
            "client_name": "Acme",
            "task_title": "Title",
        }

        result = await handle_pending_task_continuation(
            channel="C01",
            text="switch to Revant",
            session=session,
            session_service=session_service,
            slack=slack,
            pending=pending,
            classify_message=_classify_switch,
            resolve_brand_for_task=AsyncMock(),
            enrich_task_draft=AsyncMock(),
            execute_task_create=AsyncMock(),
            extract_product_identifiers=MagicMock(return_value=[]),
        )

        assert result is False
        session_service.update_context.assert_called_once()

    @pytest.mark.asyncio
    async def test_brand_empty_text_returns_false(self) -> None:
        """Empty text in brand awaiting -> returns False."""
        pending = {"awaiting": "brand", "client_id": "c1"}

        result = await handle_pending_task_continuation(
            channel="C01",
            text="   ",
            session=_make_session(),
            session_service=_make_session_service(),
            slack=_make_slack(),
            pending=pending,
            classify_message=_classify_help,
            resolve_brand_for_task=AsyncMock(),
            enrich_task_draft=AsyncMock(),
            execute_task_create=AsyncMock(),
            extract_product_identifiers=MagicMock(return_value=[]),
        )

        assert result is False


# ---------------------------------------------------------------------------
# awaiting == "title"
# ---------------------------------------------------------------------------


class TestPendingTitle:
    @pytest.mark.asyncio
    async def test_title_provided_with_brand_shows_confirm(self) -> None:
        session = _make_session()
        session_service = _make_session_service()
        slack = _make_slack()

        pending = {
            "awaiting": "title",
            "client_id": "c1",
            "client_name": "Acme",
            "brand_id": "b1",
            "brand_name": "Alpha",
            "brand_resolution_mode": "single_match",
        }

        result = await handle_pending_task_continuation(
            channel="C01",
            text="Set up coupon for Thorinox",
            session=session,
            session_service=session_service,
            slack=slack,
            pending=pending,
            classify_message=_classify_help,
            resolve_brand_for_task=AsyncMock(),
            enrich_task_draft=AsyncMock(),
            execute_task_create=AsyncMock(),
            extract_product_identifiers=MagicMock(return_value=[]),
        )

        assert result is True
        slack.post_message.assert_called_once()
        msg = slack.post_message.call_args[1].get("text", "")
        assert "Set up coupon" in msg

    @pytest.mark.asyncio
    async def test_title_interrupt_clears_pending(self) -> None:
        session = _make_session()
        session_service = _make_session_service()
        slack = _make_slack()

        pending = {
            "awaiting": "title",
            "client_id": "c1",
            "client_name": "Acme",
            "brand_id": "b1",
            "brand_name": "Alpha",
        }

        result = await handle_pending_task_continuation(
            channel="C01",
            text="switch to Revant",
            session=session,
            session_service=session_service,
            slack=slack,
            pending=pending,
            classify_message=_classify_switch,
            resolve_brand_for_task=AsyncMock(),
            enrich_task_draft=AsyncMock(),
            execute_task_create=AsyncMock(),
            extract_product_identifiers=MagicMock(return_value=[]),
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_title_no_brand_resolves_then_confirms(self) -> None:
        """No brand_id in pending -> resolve_brand called, then confirm shown."""
        session = _make_session()
        session_service = _make_session_service()
        slack = _make_slack()

        resolve_brand = AsyncMock(return_value={
            "mode": "single_match",
            "brand_context": {"id": "b1", "name": "Alpha"},
            "candidates": [],
        })

        pending = {
            "awaiting": "title",
            "client_id": "c1",
            "client_name": "Acme",
            "brand_id": None,
            "brand_name": None,
        }

        result = await handle_pending_task_continuation(
            channel="C01",
            text="Create listing optimization",
            session=session,
            session_service=session_service,
            slack=slack,
            pending=pending,
            classify_message=_classify_help,
            resolve_brand_for_task=resolve_brand,
            enrich_task_draft=AsyncMock(),
            execute_task_create=AsyncMock(),
            extract_product_identifiers=MagicMock(return_value=[]),
        )

        assert result is True
        resolve_brand.assert_called_once()


# ---------------------------------------------------------------------------
# awaiting == "confirm_or_details"
# ---------------------------------------------------------------------------


class TestPendingConfirmOrDetails:
    @pytest.mark.asyncio
    async def test_cancel(self) -> None:
        session = _make_session()
        session_service = _make_session_service()
        slack = _make_slack()

        pending = {
            "awaiting": "confirm_or_details",
            "client_id": "c1",
            "client_name": "Acme",
            "task_title": "Title",
        }

        result = await handle_pending_task_continuation(
            channel="C01",
            text="cancel",
            session=session,
            session_service=session_service,
            slack=slack,
            pending=pending,
            classify_message=_classify_help,
            resolve_brand_for_task=AsyncMock(),
            enrich_task_draft=AsyncMock(),
            execute_task_create=AsyncMock(),
            extract_product_identifiers=MagicMock(return_value=[]),
        )

        assert result is True
        assert "canceled" in slack.post_message.call_args[1].get("text", "").lower()

    @pytest.mark.asyncio
    async def test_interrupt_on_new_intent(self) -> None:
        session = _make_session()
        session_service = _make_session_service()
        slack = _make_slack()

        pending = {
            "awaiting": "confirm_or_details",
            "client_id": "c1",
            "client_name": "Acme",
            "task_title": "Title",
        }

        result = await handle_pending_task_continuation(
            channel="C01",
            text="switch to Revant",
            session=session,
            session_service=session_service,
            slack=slack,
            pending=pending,
            classify_message=_classify_switch,
            resolve_brand_for_task=AsyncMock(),
            enrich_task_draft=AsyncMock(),
            execute_task_create=AsyncMock(),
            extract_product_identifiers=MagicMock(return_value=[]),
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_proceed_draft_calls_execute(self) -> None:
        session = _make_session()
        session_service = _make_session_service()
        slack = _make_slack()
        execute = AsyncMock()
        enrich = AsyncMock(return_value={"needs_clarification": False, "description": "Enriched", "checklist": [], "citations": []})

        pending = {
            "awaiting": "confirm_or_details",
            "client_id": "c1",
            "client_name": "Acme",
            "task_title": "Title",
        }

        result = await handle_pending_task_continuation(
            channel="C01",
            text="yes please",
            session=session,
            session_service=session_service,
            slack=slack,
            pending=pending,
            classify_message=_classify_help,
            resolve_brand_for_task=AsyncMock(),
            enrich_task_draft=enrich,
            execute_task_create=execute,
            extract_product_identifiers=MagicMock(return_value=[]),
        )

        assert result is True
        execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_description_provided_creates_task(self) -> None:
        """User sends a description (not a confirm command) -> create with description."""
        session = _make_session()
        session_service = _make_session_service()
        slack = _make_slack()
        execute = AsyncMock()

        pending = {
            "awaiting": "confirm_or_details",
            "client_id": "c1",
            "client_name": "Acme",
            "task_title": "Title",
        }

        # Plain text that doesn't match cancel/proceed/interrupt
        result = await handle_pending_task_continuation(
            channel="C01",
            text="Set up 20% coupon for Thorinox B08N5WRWNW",
            session=session,
            session_service=session_service,
            slack=slack,
            pending=pending,
            classify_message=_classify_help,
            resolve_brand_for_task=AsyncMock(),
            enrich_task_draft=AsyncMock(),
            execute_task_create=execute,
            extract_product_identifiers=MagicMock(return_value=["B08N5WRWNW"]),
        )

        assert result is True
        execute.assert_called_once()


# ---------------------------------------------------------------------------
# awaiting == "asin_or_pending"
# ---------------------------------------------------------------------------


class TestPendingAsinOrPending:
    @pytest.mark.asyncio
    async def test_cancel(self) -> None:
        session = _make_session()
        session_service = _make_session_service()
        slack = _make_slack()

        pending = {
            "awaiting": "asin_or_pending",
            "client_id": "c1",
            "client_name": "Acme",
            "task_title": "Title",
        }

        result = await handle_pending_task_continuation(
            channel="C01",
            text="cancel",
            session=session,
            session_service=session_service,
            slack=slack,
            pending=pending,
            classify_message=_classify_help,
            resolve_brand_for_task=AsyncMock(),
            enrich_task_draft=AsyncMock(),
            execute_task_create=AsyncMock(),
            extract_product_identifiers=MagicMock(return_value=[]),
        )

        assert result is True
        assert "canceled" in slack.post_message.call_args[1]["text"].lower()

    @pytest.mark.asyncio
    async def test_proceed_asin_pending(self) -> None:
        session = _make_session()
        session_service = _make_session_service()
        slack = _make_slack()
        execute = AsyncMock()

        pending = {
            "awaiting": "asin_or_pending",
            "client_id": "c1",
            "client_name": "Acme",
            "task_title": "Title",
            "draft": {"description": "D", "open_questions": ["Q1"]},
        }

        result = await handle_pending_task_continuation(
            channel="C01",
            text="create with asin pending",
            session=session,
            session_service=session_service,
            slack=slack,
            pending=pending,
            classify_message=_classify_help,
            resolve_brand_for_task=AsyncMock(),
            enrich_task_draft=AsyncMock(),
            execute_task_create=execute,
            extract_product_identifiers=MagicMock(return_value=[]),
        )

        assert result is True
        execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_provide_identifier(self) -> None:
        """User provides an ASIN -> execute_task_create called with identifier in description."""
        session = _make_session()
        session_service = _make_session_service()
        slack = _make_slack()
        execute = AsyncMock()

        pending = {
            "awaiting": "asin_or_pending",
            "client_id": "c1",
            "client_name": "Acme",
            "task_title": "Title",
            "draft": {"description": "Original desc"},
        }

        # Mock _has_product_identifier to return True for this text
        with patch(
            "app.services.agencyclaw.slack_pending_flow.resolve_pending_action",
            return_value={"action": "provide_identifier", "reason": "identifier_present"},
        ):
            result = await handle_pending_task_continuation(
                channel="C01",
                text="B08N5WRWNW",
                session=session,
                session_service=session_service,
                slack=slack,
                pending=pending,
                classify_message=_classify_help,
                resolve_brand_for_task=AsyncMock(),
                enrich_task_draft=AsyncMock(),
                execute_task_create=execute,
                extract_product_identifiers=MagicMock(return_value=["B08N5WRWNW"]),
            )

        assert result is True
        execute.assert_called_once()
        desc = execute.call_args[1].get("task_description", "")
        assert "B08N5WRWNW" in desc

    @pytest.mark.asyncio
    async def test_interrupt(self) -> None:
        session = _make_session()
        session_service = _make_session_service()
        slack = _make_slack()

        pending = {
            "awaiting": "asin_or_pending",
            "client_id": "c1",
            "client_name": "Acme",
            "task_title": "Title",
        }

        result = await handle_pending_task_continuation(
            channel="C01",
            text="switch to Revant",
            session=session,
            session_service=session_service,
            slack=slack,
            pending=pending,
            classify_message=_classify_switch,
            resolve_brand_for_task=AsyncMock(),
            enrich_task_draft=AsyncMock(),
            execute_task_create=AsyncMock(),
            extract_product_identifiers=MagicMock(return_value=[]),
        )

        assert result is False


# ---------------------------------------------------------------------------
# Unknown awaiting state
# ---------------------------------------------------------------------------


class TestPendingUnknownState:
    @pytest.mark.asyncio
    async def test_unknown_clears_pending(self) -> None:
        session = _make_session()
        session_service = _make_session_service()
        slack = _make_slack()

        pending = {"awaiting": "something_unknown"}

        result = await handle_pending_task_continuation(
            channel="C01",
            text="hello",
            session=session,
            session_service=session_service,
            slack=slack,
            pending=pending,
            classify_message=_classify_help,
            resolve_brand_for_task=AsyncMock(),
            enrich_task_draft=AsyncMock(),
            execute_task_create=AsyncMock(),
            extract_product_identifiers=MagicMock(return_value=[]),
        )

        assert result is False
        session_service.update_context.assert_called_once()
