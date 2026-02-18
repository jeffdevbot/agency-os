import pytest
from app.services.agencyclaw.identity_reconciliation import (
    reconcile_identity,
    SlackExternalUser,
    ClickUpExternalUser,
    ExistingProfile,
)

def test_exact_email_match():
    slack_user = SlackExternalUser(slack_user_id="U1", email="jeff@example.com", real_name="Jeff")
    profiles = [
        ExistingProfile(id="p1", slack_user_id=None, clickup_user_id=None, email="jeff@example.com", is_admin=False)
    ]
    result = reconcile_identity(slack_user, None, profiles)
    assert result["outcome"] == "auto_match"
    assert result["candidate_profile_ids"] == ["p1"]
    assert "email_match" in result["reasons"]

def test_exact_slack_id_match():
    slack_user = SlackExternalUser(slack_user_id="U1", email="new@example.com", real_name="Jeff")
    profiles = [
        ExistingProfile(id="p1", slack_user_id="U1", clickup_user_id=None, email="old@example.com", is_admin=False)
    ]
    result = reconcile_identity(slack_user, None, profiles)
    assert result["outcome"] == "auto_match"
    assert result["candidate_profile_ids"] == ["p1"]
    assert "slack_id_match" in result["reasons"]

def test_exact_clickup_id_match():
    clickup_user = ClickUpExternalUser(clickup_user_id="C1", email="new@example.com", username="Jeff")
    profiles = [
        ExistingProfile(id="p1", slack_user_id=None, clickup_user_id="C1", email="old@example.com", is_admin=False)
    ]
    result = reconcile_identity(None, clickup_user, profiles)
    assert result["outcome"] == "auto_match"
    assert result["candidate_profile_ids"] == ["p1"]
    assert "clickup_id_match" in result["reasons"]

def test_multiple_candidates_ambiguous():
    slack_user = SlackExternalUser(slack_user_id="U1", email="ambiguous@example.com", real_name="Jeff")
    profiles = [
        ExistingProfile(id="p1", slack_user_id="U2", clickup_user_id=None, email="ambiguous@example.com", is_admin=False),
        ExistingProfile(id="p2", slack_user_id="U3", clickup_user_id=None, email="ambiguous@example.com", is_admin=False)
    ]
    result = reconcile_identity(slack_user, None, profiles)
    assert result["outcome"] == "needs_review"
    assert len(result["candidate_profile_ids"]) == 2

def test_conflicting_ids():
    # Profile has Slack ID U2, but incoming user has Slack ID U1. Even if email matches, this is a conflict.
    slack_user = SlackExternalUser(slack_user_id="U1", email="jeff@example.com", real_name="Jeff")
    profiles = [
        ExistingProfile(id="p1", slack_user_id="U2", clickup_user_id=None, email="jeff@example.com", is_admin=False)
    ]
    result = reconcile_identity(slack_user, None, profiles)
    assert result["outcome"] == "needs_review"
    assert "conflicting_slack_id" in result["reasons"]
    
def test_no_match_new_profile():
    slack_user = SlackExternalUser(slack_user_id="U1", email="new@example.com", real_name="Jeff")
    profiles = [
        ExistingProfile(id="p1", slack_user_id="U2", clickup_user_id="C2", email="other@example.com", is_admin=False)
    ]
    result = reconcile_identity(slack_user, None, profiles)
    assert result["outcome"] == "new_profile"
    assert result["candidate_profile_ids"] == []
    assert result["suggested_action"]["action"] == "create_profile"

def test_case_insensitive_email():
    slack_user = SlackExternalUser(slack_user_id="U1", email="JeFf@ExAmPlE.CoM", real_name="Jeff")
    profiles = [
        ExistingProfile(id="p1", slack_user_id=None, clickup_user_id=None, email="jeff@example.com", is_admin=False)
    ]
    result = reconcile_identity(slack_user, None, profiles)
    assert result["outcome"] == "auto_match"
    assert "email_match" in result["reasons"]

def test_mixed_match_signals():
    # Email matches one profile, ClickUp ID matches same profile. Should be auto_match.
    clickup_user = ClickUpExternalUser(clickup_user_id="C1", email="jeff@example.com", username="Jeff")
    profiles = [
        ExistingProfile(id="p1", slack_user_id=None, clickup_user_id="C1", email="jeff@example.com", is_admin=False)
    ]
    result = reconcile_identity(None, clickup_user, profiles)
    assert result["outcome"] == "auto_match"
    assert "email_match" in result["reasons"]
    assert "clickup_id_match" in result["reasons"]
