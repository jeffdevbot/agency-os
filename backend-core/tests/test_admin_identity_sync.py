import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app
from app.auth import require_admin_user
@pytest.fixture(autouse=True)
def override_admin_auth():
    app.dependency_overrides[require_admin_user] = lambda: {"id": "admin_user", "is_admin": True}
    yield
    app.dependency_overrides = {}

client = TestClient(app)

@pytest.fixture(autouse=True)
def mock_supabase():
    with patch("app.routers.admin.create_client") as mock:
        mock.return_value = MagicMock()
        yield mock

@pytest.fixture(autouse=True)
def mock_settings():
    with patch("app.routers.admin.settings") as mock:
        mock.supabase_url = "http://localhost:54321"
        mock.supabase_service_role = "service_role_token"
        yield mock

@pytest.fixture
def mock_run_sync():
    with patch("app.routers.admin.run_identity_sync") as mock:
        yield mock

def test_identity_sync_happy_path(mock_run_sync):
    mock_run_sync.return_value = {
        "summary": {"auto_match": 1},
        "actions_taken": [],
        "proposals": [],
        "needs_review_items": []
    }
    
    # Ensure TypedDicts are serializable lists
    payload = {
        "dry_run": True,
        "slack_users": [{"slack_user_id": "U1", "email": "test@example.com"}],
        "clickup_users": []
    }
    
    response = client.post("/admin/identity-sync/run", json=payload)
    
    assert response.status_code == 200
    assert response.json()["summary"]["auto_match"] == 1
    
    # Verify mock call
    args, kwargs = mock_run_sync.call_args
    assert kwargs["dry_run"] is True
    assert len(kwargs["slack_users"]) == 1
    assert kwargs["slack_users"][0]["slack_user_id"] == "U1"

def test_identity_sync_runtime_error(mock_run_sync):
    mock_run_sync.side_effect = Exception("Runtime boom")
    
    payload = {
        "dry_run": True,
        "slack_users": [],
        "clickup_users": []
    }
    
    response = client.post("/admin/identity-sync/run", json=payload)
    
    assert response.status_code == 500
    assert "Runtime boom" in response.json()["detail"]

def test_dry_run_default(mock_run_sync):
    mock_run_sync.return_value = {}
    # Omit dry_run, explicit users
    payload = {
        "slack_users": [],
        "clickup_users": []
    }
    
    response = client.post("/admin/identity-sync/run", json=payload)
    assert response.status_code == 200
    
    # Check default True
    args, kwargs = mock_run_sync.call_args
    assert kwargs["dry_run"] is True
