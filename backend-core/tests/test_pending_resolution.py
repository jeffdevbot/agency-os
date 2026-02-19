"""Tests for C10F semantic pending-state resolver."""

from __future__ import annotations

import pytest

from app.services.agencyclaw.pending_resolution import resolve_pending_action


class TestConfirmOrDetailsResolution:
    def test_interrupt_on_known_intent(self):
        result = resolve_pending_action(
            awaiting="confirm_or_details",
            text="what are the distex tasks?",
            known_intent="weekly_tasks",
            has_identifier=False,
        )
        assert result["action"] == "interrupt"

    def test_cancel(self):
        result = resolve_pending_action(
            awaiting="confirm_or_details",
            text="never mind",
            known_intent="help",
            has_identifier=False,
        )
        assert result["action"] == "cancel"

    def test_proceed_draft_paraphrase(self):
        result = resolve_pending_action(
            awaiting="confirm_or_details",
            text="go ahead and create it",
            known_intent="help",
            has_identifier=False,
        )
        assert result["action"] == "proceed_draft"

    def test_proceed_with_asin_pending_paraphrase(self):
        result = resolve_pending_action(
            awaiting="confirm_or_details",
            text="create it without asin for now",
            known_intent="help",
            has_identifier=False,
        )
        assert result["action"] == "proceed_with_asin_pending"

    def test_off_topic_smalltalk(self):
        result = resolve_pending_action(
            awaiting="confirm_or_details",
            text="what is plato all about?",
            known_intent="help",
            has_identifier=False,
        )
        assert result["action"] == "off_topic"

    def test_default_to_details(self):
        result = resolve_pending_action(
            awaiting="confirm_or_details",
            text="Set this up at 20% discount for next week.",
            known_intent="help",
            has_identifier=False,
        )
        assert result["action"] == "provide_details"


class TestAsinOrPendingResolution:
    def test_interrupt_on_known_intent(self):
        result = resolve_pending_action(
            awaiting="asin_or_pending",
            text="switch to Acme",
            known_intent="switch_client",
            has_identifier=False,
        )
        assert result["action"] == "interrupt"

    def test_cancel(self):
        result = resolve_pending_action(
            awaiting="asin_or_pending",
            text="cancel task",
            known_intent="help",
            has_identifier=False,
        )
        assert result["action"] == "cancel"

    def test_identifier_wins(self):
        result = resolve_pending_action(
            awaiting="asin_or_pending",
            text="B08XYZ1234",
            known_intent="help",
            has_identifier=True,
        )
        assert result["action"] == "provide_identifier"

    def test_proceed_with_asin_pending_paraphrase(self):
        result = resolve_pending_action(
            awaiting="asin_or_pending",
            text="create now and i will send asin later",
            known_intent="help",
            has_identifier=False,
        )
        assert result["action"] == "proceed_with_asin_pending"

    def test_reask_for_asin_related_no_identifier(self):
        result = resolve_pending_action(
            awaiting="asin_or_pending",
            text="set up coupon for summer promo products",
            known_intent="help",
            has_identifier=False,
        )
        assert result["action"] == "reask"

    def test_off_topic_smalltalk(self):
        result = resolve_pending_action(
            awaiting="asin_or_pending",
            text="you there?",
            known_intent="help",
            has_identifier=False,
        )
        assert result["action"] == "off_topic"


@pytest.mark.parametrize(
    "text",
    [
        "create with asin pending",
        "create with sku pending",
        "proceed without asin",
        "create with no identifiers for now",
    ],
)
def test_asin_deferral_variants(text: str):
    result = resolve_pending_action(
        awaiting="asin_or_pending",
        text=text,
        known_intent="help",
        has_identifier=False,
    )
    assert result["action"] == "proceed_with_asin_pending"

