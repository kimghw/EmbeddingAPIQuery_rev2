"""Test main FastAPI application."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from main import create_app


@pytest.fixture
def client():
    """Create test client."""
    with patch('main.get_config') as mock_config:
        mock_config.return_value = MagicMock(
            ENVIRONMENT="test",
            DATABASE_URL="sqlite:///test.db",
            GRAPH_API_ENDPOINT="https://graph.microsoft.com/v1.0",
            EXTERNAL_API_URL="https://api.example.com"
        )
        
        app = create_app()
        with TestClient(app) as test_client:
            yield test_client


def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    
    data = response.json()
    assert data["message"] == "GraphAPI Query System"
    assert data["version"] == "1.0.0"
    assert data["status"] == "running"
    assert data["environment"] == "test"


def test_basic_health_check(client):
    """Test basic health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "1.0.0"


def test_api_health_check(client):
    """Test API health check endpoint."""
    with patch('adapters.api.dependencies.get_db_adapter_dependency') as mock_db, \
         patch('adapters.api.dependencies.get_graph_api_dependency') as mock_graph, \
         patch('adapters.api.dependencies.get_external_api_dependency') as mock_external:
        
        # Mock health checks
        mock_db.return_value.health_check.return_value = True
        mock_graph.return_value.health_check.return_value = True
        mock_external.return_value.health_check.return_value = True
        
        response = client.get("/api/v1/health/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"


def test_configuration_endpoint(client):
    """Test configuration endpoint."""
    with patch('adapters.api.dependencies.get_config_dependency') as mock_config:
        mock_config.return_value.get_environment.return_value = "test"
        mock_config.return_value.get_database_url.return_value = "sqlite:///test.db"
        mock_config.return_value.get_graph_api_endpoint.return_value = "https://graph.microsoft.com/v1.0"
        mock_config.return_value.get_external_api_url.return_value = "https://api.example.com"
        mock_config.return_value.get_client_id.return_value = "test_client_id"
        mock_config.return_value.get_client_secret.return_value = "test_secret"
        mock_config.return_value.get_external_api_key.return_value = "test_key"
        
        response = client.get("/api/v1/config/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["environment"] == "test"
        assert data["client_secret_configured"] is True
        assert data["external_api_key_configured"] is True


def test_accounts_list_endpoint(client):
    """Test accounts list endpoint."""
    with patch('adapters.api.dependencies.get_account_usecase') as mock_usecase:
        mock_usecase.return_value.get_active_accounts.return_value = MagicMock(
            accounts=[]
        )
        
        response = client.get("/api/v1/accounts/?active_only=true")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "accounts" in data
        assert data["total"] == 0


def test_emails_list_endpoint(client):
    """Test emails list endpoint."""
    with patch('adapters.api.dependencies.get_email_usecase') as mock_usecase:
        mock_usecase.return_value.get_emails_by_status.return_value = MagicMock(
            emails=[]
        )
        
        response = client.get("/api/v1/emails/?status=pending")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "emails" in data
        assert data["total"] == 0


def test_transmissions_summary_endpoint(client):
    """Test transmissions summary endpoint."""
    with patch('adapters.api.dependencies.get_transmission_usecase') as mock_usecase:
        mock_usecase.return_value.get_transmission_summary.return_value = MagicMock(
            success=True,
            summary={"pending": 0, "sent": 0, "failed": 0}
        )
        
        response = client.get("/api/v1/transmissions/summary")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "summary" in data


def test_error_handling(client):
    """Test error handling."""
    # Test 404
    response = client.get("/nonexistent")
    assert response.status_code == 404
    
    # Test invalid account ID
    response = client.get("/api/v1/accounts/invalid-uuid")
    assert response.status_code == 422  # Validation error


if __name__ == "__main__":
    pytest.main([__file__])
