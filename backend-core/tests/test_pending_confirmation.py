from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.agencyclaw.pending_confirmation import (
    build_pending_confirmation,
    compute_proposal_fingerprint,
    is_affirmative,
    is_expired,
    is_negative,
    payload_has_valid_fingerprint,
    validate_confirmation,
)


def test_build_pending_confirmation_has_required_fields_and_stable_fingerprint():
    payload1 = build_pending_confirmation(
        action_type="mutation",
        skill_id="clickup_task_create",
        args={"task_title": "Fix listing", "client_name": "Distex"},
        requested_by="U123",
        lane_key="U123",
        now=datetime(2026, 2, 24, 0, 0, 0, tzinfo=timezone.utc),
        ttl_seconds=600,
    )
    payload2 = build_pending_confirmation(
        action_type="mutation",
        skill_id="clickup_task_create",
        args={"client_name": "Distex", "task_title": "Fix listing"},
        requested_by="U123",
        lane_key="U123",
        now=datetime(2026, 2, 24, 0, 0, 0, tzinfo=timezone.utc),
        ttl_seconds=600,
    )
    assert payload1["skill_id"] == "clickup_task_create"
    assert payload1["action_type"] == "mutation"
    assert payload1["requested_by"] == "U123"
    assert payload1["proposal_fingerprint"] == payload2["proposal_fingerprint"]


def test_is_expired_behavior():
    now = datetime(2026, 2, 24, 0, 0, 0, tzinfo=timezone.utc)
    payload = {
        "expires_at": (now + timedelta(minutes=1)).isoformat(),
    }
    assert is_expired(payload, now=now) is False
    assert is_expired(payload, now=now + timedelta(minutes=2)) is True


def test_affirmative_negative_phrase_sets():
    assert is_affirmative("confirm")
    assert is_affirmative("go ahead")
    assert is_affirmative("Yes, create it.")
    assert is_affirmative("please create it")
    assert is_negative("cancel")
    assert is_negative("no")
    assert is_negative("No, don't")
    assert not is_affirmative("maybe")
    assert not is_negative("maybe")


def test_validate_confirmation_states():
    now = datetime(2026, 2, 24, 0, 0, 0, tzinfo=timezone.utc)
    payload = build_pending_confirmation(
        action_type="mutation",
        skill_id="clickup_task_create",
        args={"task_title": "Fix listing"},
        requested_by="U123",
        lane_key="U123",
        now=now,
        ttl_seconds=60,
    )
    assert validate_confirmation(payload, slack_user_id="U123", text="confirm", now=now)["state"] == "confirm"
    assert validate_confirmation(payload, slack_user_id="U123", text="cancel", now=now)["state"] == "cancel"
    assert validate_confirmation(payload, slack_user_id="U123", text="hello", now=now)["state"] == "ignore"
    assert (
        validate_confirmation(payload, slack_user_id="U999", text="confirm", now=now)["state"]
        == "wrong_actor"
    )
    assert (
        validate_confirmation(
            payload,
            slack_user_id="U123",
            text="confirm",
            now=now + timedelta(minutes=2),
        )["state"]
        == "expired"
    )


def test_fingerprint_helpers_and_mismatch_rejected():
    payload = build_pending_confirmation(
        action_type="mutation",
        skill_id="clickup_task_create",
        args={"task_title": "Fix listing"},
        requested_by="U123",
        lane_key="U123",
    )
    assert payload_has_valid_fingerprint(payload, lane_key="U123") is True
    expected = compute_proposal_fingerprint(
        skill_id="clickup_task_create",
        args_json='{"task_title":"Fix listing"}',
        requested_by="U123",
        lane_key="U123",
    )
    assert payload["proposal_fingerprint"] == expected

    tampered = dict(payload)
    tampered["args"] = {"task_title": "Tampered"}
    result = validate_confirmation(
        tampered,
        slack_user_id="U123",
        text="confirm",
    )
    assert result["state"] == "invalid"
