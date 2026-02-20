
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
from app.api.routes.slack import _handle_interaction, _handle_create_task, _get_receipt_service
from app.services.playbook_session import PlaybookSession
from app.services.slack import SlackReceiptService

@pytest.fixture
def mock_receipt_service():
    service = MagicMock(spec=SlackReceiptService)
    service.attempt_insert_dedupe.return_value = True # Default to new
    return service

@pytest.fixture
def mock_session_service():
    service = MagicMock()
    service.get_or_create_session.return_value = PlaybookSession(
        id="sess123",
        slack_user_id="U123",
        profile_id="prof1",
        active_client_id="client1",
        context={},
        last_message_at="2023-01-01T00:00:00Z"
    )
    service.get_client_name.return_value = "TestClient"
    return service

@pytest.fixture
def mock_slack_service():
    service = AsyncMock()
    return service

@pytest.mark.asyncio
async def test_interaction_dedupe_success(mock_receipt_service, mock_session_service, mock_slack_service):
    """Verify new interaction is processed."""
    payload = {
        "type": "block_actions",
        "user": {"id": "U123"},
        "channel": {"id": "C123"},
        "message": {"ts": "123.456"},
        "actions": [{"action_id": "cancel_create_task"}]
    }
    
    with patch("app.api.routes.slack._get_receipt_service", return_value=mock_receipt_service), \
         patch("app.api.routes.slack.get_playbook_session_service", return_value=mock_session_service), \
         patch("app.api.routes.slack.get_slack_service", return_value=mock_slack_service):
        
        await _handle_interaction(payload)
        
        # Dedupe checked
        mock_receipt_service.attempt_insert_dedupe.assert_called_once()
        # Status updated to processed
        mock_receipt_service.update_status.assert_called_with(
            "interaction:U123:cancel_create_task:123.456", "processed"
        )
        # Session updated (cancel clears context)
        mock_session_service.update_context.assert_called_with("sess123", {"pending_task_create": None})

@pytest.mark.asyncio
async def test_interaction_dedupe_duplicate(mock_receipt_service, mock_session_service, mock_slack_service):
    """Verify duplicate interaction is ignored."""
    mock_receipt_service.attempt_insert_dedupe.return_value = False # Duplicate checking
    
    payload = {
        "type": "block_actions",
        "user": {"id": "U123"},
        "channel": {"id": "C123"},
        "message": {"ts": "123.456"},
        "actions": [{"action_id": "cancel_create_task"}]
    }
    
    with patch("app.api.routes.slack._get_receipt_service", return_value=mock_receipt_service), \
         patch("app.api.routes.slack.get_playbook_session_service", return_value=mock_session_service), \
         patch("app.api.routes.slack.get_slack_service", return_value=mock_slack_service):
        
        await _handle_interaction(payload)
        
        # Dedupe checked
        mock_receipt_service.attempt_insert_dedupe.assert_called_once()
        # No processing logic called
        mock_session_service.update_context.assert_not_called()
        mock_receipt_service.update_status.assert_not_called()

@pytest.mark.asyncio
async def test_confirmation_success(mock_receipt_service, mock_session_service, mock_slack_service):
    """Verify confirmation triggers creation."""
    # Setup pending state
    mock_session_service.get_or_create_session.return_value = PlaybookSession(
        id="sess123",
        slack_user_id="U123",
        profile_id="prof1",
        active_client_id="client1",
        context={"pending_task_create": {
            "awaiting": "confirm_or_details",
            "client_id": "c1",
            "task_title": "My Task",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }},
        last_message_at="2023-01-01T00:00:00Z"
    )
    
    payload = {
        "type": "block_actions",
        "user": {"id": "U123"},
        "channel": {"id": "C123"},
        "message": {"ts": "123.456"},
        "actions": [{"action_id": "confirm_create_task_draft"}]
    }

    with patch("app.api.routes.slack._get_receipt_service", return_value=mock_receipt_service), \
         patch("app.api.routes.slack.get_playbook_session_service", return_value=mock_session_service), \
         patch("app.api.routes.slack.get_slack_service", return_value=mock_slack_service), \
         patch("app.api.routes.slack._execute_task_create", new_callable=AsyncMock) as mock_exec:
        
        await _handle_interaction(payload)
        
        mock_exec.assert_called_once()
        mock_receipt_service.update_status.assert_called_with("interaction:U123:confirm_create_task_draft:123.456", "processed")
        # Ensure message updated to "Creating..."
        mock_slack_service.update_message.assert_called()

@pytest.mark.asyncio
async def test_confirmation_expired(mock_receipt_service, mock_session_service, mock_slack_service):
    """Verify expired confirmation is rejected."""
    old_time = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    mock_session_service.get_or_create_session.return_value = PlaybookSession(
        id="sess123",
        slack_user_id="U123",
        profile_id="prof1",
        active_client_id="client1",
        context={"pending_task_create": {
            "awaiting": "confirm_or_details",
            "timestamp": old_time
        }},
        last_message_at="2023-01-01T00:00:00Z"
    )
    
    payload = {
        "type": "block_actions",
        "user": {"id": "U123"},
        "channel": {"id": "C123"},
        "message": {"ts": "123.456"},
        "actions": [{"action_id": "confirm_create_task_draft"}]
    }

    with patch("app.api.routes.slack._get_receipt_service", return_value=mock_receipt_service), \
         patch("app.api.routes.slack.get_playbook_session_service", return_value=mock_session_service), \
         patch("app.api.routes.slack.get_slack_service", return_value=mock_slack_service), \
         patch("app.api.routes.slack._execute_task_create", new_callable=AsyncMock) as mock_exec:
        
        await _handle_interaction(payload)
        
        mock_exec.assert_not_called()
        mock_receipt_service.update_status.assert_called_with(
            "interaction:U123:confirm_create_task_draft:123.456",
            "ignored",
            {"reason": "expired"},
        )


@pytest.mark.asyncio
async def test_brand_selection_invalid_option_ignored(
    mock_receipt_service, mock_session_service, mock_slack_service,
):
    """C11D: selecting a brand not present in pending candidates should be ignored."""
    mock_session_service.get_or_create_session.return_value = PlaybookSession(
        id="sess123",
        slack_user_id="U123",
        profile_id="prof1",
        active_client_id="client1",
        context={"pending_task_create": {
            "awaiting": "brand",
            "client_id": "c1",
            "client_name": "Distex",
            "task_title": "Create coupon",
            "brand_candidates": [{"id": "b1", "name": "Brand A"}],
        }},
        last_message_at="2023-01-01T00:00:00Z",
    )

    payload = {
        "type": "block_actions",
        "user": {"id": "U123"},
        "channel": {"id": "C123"},
        "message": {"ts": "123.456"},
        "actions": [{"action_id": "select_brand_b999", "value": "b999"}],
    }

    with patch("app.api.routes.slack._get_receipt_service", return_value=mock_receipt_service), \
         patch("app.api.routes.slack.get_playbook_session_service", return_value=mock_session_service), \
         patch("app.api.routes.slack.get_slack_service", return_value=mock_slack_service):

        await _handle_interaction(payload)

    mock_receipt_service.update_status.assert_called_with(
        "interaction:U123:select_brand_b999:123.456",
        "ignored",
        {"reason": "invalid_brand_selection"},
    )
    # Pending state should be unchanged (no transition on invalid selection).
    mock_session_service.update_context.assert_not_called()
