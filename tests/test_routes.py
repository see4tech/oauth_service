import pytest
from fastapi.testclient import TestClient
from oauth_service.routes import oauth_router

client = TestClient(oauth_router)

def test_oauth_init_endpoint():
    """Test OAuth initialization endpoint."""
    response = client.post(
        "/oauth/twitter/init",
        json={
            "user_id": "test_user",
            "redirect_uri": "http://localhost/callback"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "authorization_url" in data
    assert "state" in data

def test_invalid_platform():
    """Test handling of invalid platform."""
    response = client.post(
        "/oauth/invalid_platform/init",
        json={
            "user_id": "test_user",
            "redirect_uri": "http://localhost/callback"
        }
    )
    assert response.status_code == 400

def test_oauth_callback():
    """Test OAuth callback handling."""
    response = client.post(
        "/oauth/twitter/callback",
        json={
            "code": "test_code",
            "state": "test_state",
            "redirect_uri": "http://localhost/callback"
        }
    )
    # Should fail without valid state
    assert response.status_code == 400
