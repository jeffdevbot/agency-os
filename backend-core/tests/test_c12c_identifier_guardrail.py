"""C12C Path-1 identifier guardrail tests (no catalog lookup integration)."""

from app.services.agencyclaw.pending_resolution import resolve_pending_action


def test_confirm_state_accepts_explicit_identifier_pending_phrase() -> None:
    result = resolve_pending_action(
        awaiting="confirm_or_details",
        text="create with identifier pending",
        known_intent="help",
        has_identifier=False,
    )
    assert result["action"] == "proceed_with_asin_pending"


def test_asin_state_without_identifier_reasks() -> None:
    result = resolve_pending_action(
        awaiting="asin_or_pending",
        text="coupon for thorinox",
        known_intent="help",
        has_identifier=False,
    )
    assert result["action"] == "reask"


def test_asin_state_with_identifier_proceeds() -> None:
    result = resolve_pending_action(
        awaiting="asin_or_pending",
        text="B08XYZ1234",
        known_intent="help",
        has_identifier=True,
    )
    assert result["action"] == "provide_identifier"
