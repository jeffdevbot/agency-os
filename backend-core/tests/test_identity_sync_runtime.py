import pytest
from unittest.mock import MagicMock
from app.services.agencyclaw.identity_sync_runtime import run_identity_sync
from app.services.agencyclaw.identity_reconciliation import SlackExternalUser, ClickUpExternalUser

@pytest.fixture
def mock_db():
    db = MagicMock()
    # default empty profiles
    db.table.return_value.select.return_value.execute.return_value.data = []
    return db

def test_dry_run_no_writes(mock_db):
    slack_users = [SlackExternalUser(slack_user_id="U1", email="jeff@example.com", real_name="Jeff")]
    # Existing profile matches
    mock_db.table.return_value.select.return_value.execute.return_value.data = [{
        "id": "p1", "email": "jeff@example.com", "slack_user_id": None, "clickup_user_id": None, "is_admin": False
    }]
    
    result = run_identity_sync(mock_db, slack_users=slack_users, clickup_users=[], dry_run=True)
    
    assert result["summary"]["auto_match"] == 1
    assert len(result["actions_taken"]) == 1
    assert "[DRY RUN]" in result["actions_taken"][0]
    
    # Verify no update call
    mock_db.table.return_value.update.assert_not_called()

def test_auto_match_updates_db(mock_db):
    slack_users = [SlackExternalUser(slack_user_id="U1", email="jeff@example.com", real_name="Jeff")]
    mock_db.table.return_value.select.return_value.execute.return_value.data = [{
        "id": "p1", "email": "jeff@example.com", "slack_user_id": None, "clickup_user_id": None, "is_admin": False
    }]
    
    result = run_identity_sync(mock_db, slack_users=slack_users, clickup_users=[], dry_run=False)
    
    assert result["summary"]["auto_match"] == 1
    # Verify update call
    mock_db.table.return_value.update.assert_called_with({"slack_user_id": "U1"})
    mock_db.table.return_value.update.return_value.eq.assert_called_with("id", "p1")

def test_auto_match_does_not_clear_existing_other_id(mock_db):
    slack_users = [SlackExternalUser(slack_user_id="U1", email="jeff@example.com", real_name="Jeff")]
    mock_db.table.return_value.select.return_value.execute.return_value.data = [{
        "id": "p1", "email": "jeff@example.com", "slack_user_id": None, "clickup_user_id": "C99", "is_admin": False
    }]

    run_identity_sync(mock_db, slack_users=slack_users, clickup_users=[], dry_run=False)

    mock_db.table.return_value.update.assert_called_once_with({"slack_user_id": "U1"})

def test_new_profile_proposal(mock_db):
    slack_users = [SlackExternalUser(slack_user_id="U1", email="new@example.com", real_name="Jeff")]
    mock_db.table.return_value.select.return_value.execute.return_value.data = []
    
    result = run_identity_sync(mock_db, slack_users=slack_users, clickup_users=[], dry_run=False)
    
    assert result["summary"]["new_profile"] == 1
    assert len(result["proposals"]) == 1
    assert result["proposals"][0]["candidate_id"] == "U1"
    # Ensure no DB insert for profile
    mock_db.table.return_value.insert.assert_not_called()

def test_needs_review_events(mock_db):
    slack_users = [SlackExternalUser(slack_user_id="U1", email="conflict@example.com", real_name="Jeff")]
    # Conflict: Profile exists with same email but DIFFERENT Slack ID
    mock_db.table.return_value.select.return_value.execute.return_value.data = [{
        "id": "p1", "email": "conflict@example.com", "slack_user_id": "U99", "clickup_user_id": None, "is_admin": False
    }]
    
    result = run_identity_sync(mock_db, slack_users=slack_users, clickup_users=[], dry_run=False)
    
    assert result["summary"]["needs_review"] == 1
    # Verify event insert
    calls = mock_db.table.return_value.insert.call_args_list
    assert len(calls) > 0 # At least one insert
    args, _ = calls[0]
    payload = args[0]
    assert payload["event_type"] == "identity_needs_review"
    assert payload["payload"]["source"] == "slack"
    assert payload["payload"]["candidate_id"] == "U1"

def test_summary_counts_aggregated(mock_db):
    # 1 match, 1 new
    slack_users = [SlackExternalUser(slack_user_id="U1", email="match@example.com", real_name="Jeff")]
    clickup_users = [ClickUpExternalUser(clickup_user_id="C1", email="new@example.com", username="NewGuy")]
    
    mock_db.table.return_value.select.return_value.execute.return_value.data = [{
        "id": "p1", "email": "match@example.com", "slack_user_id": None, "clickup_user_id": None, "is_admin": False
    }]
    
    result = run_identity_sync(mock_db, slack_users=slack_users, clickup_users=clickup_users, dry_run=True)
    
    assert result["summary"]["auto_match"] == 1
    assert result["summary"]["new_profile"] == 1
    assert len(result["actions_taken"]) == 1 # only 1 match
    assert len(result["proposals"]) == 1 # only 1 new
