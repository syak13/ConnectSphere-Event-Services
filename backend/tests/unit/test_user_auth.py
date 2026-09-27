import pytest
from unittest.mock import patch, MagicMock
from flask import Flask
from app.auth.routes import auth_bp

@pytest.fixture
def client():
    # Create a Flask app and register the auth blueprint
    app = Flask(__name__)
    app.register_blueprint(auth_bp)
    return app.test_client()

@patch("app.auth.routes.authenticate")
def test_login_missing_email_or_password(mock_authenticate, client):
    # Test when email or password is missing
    response = client.post("/login", json={"email": "test@example.com"})
    assert response.status_code == 400
    assert response.json == {"error": "email and password are required"}

    response = client.post("/login", json={"password": "password123"})
    assert response.status_code == 400
    assert response.json == {"error": "email and password are required"}

@patch("app.auth.routes.authenticate")
def test_login_invalid_credentials(mock_authenticate, client):
    # Test when credentials are invalid
    mock_authenticate.return_value = None  # Simulate invalid credentials
    response = client.post("/login", json={"email": "test@example.com", "password": "wrongpassword"})
    assert response.status_code == 401
    assert response.json == {"error": "Invalid credentials"}

@patch("app.auth.routes.issue_tokens")
@patch("app.auth.routes.authenticate")
def test_login_successful(mock_authenticate, mock_issue_tokens, client):
    # Test successful login
    mock_user = MagicMock()
    mock_user.to_dict.return_value = {"id": 1, "email": "test@example.com"}
    mock_authenticate.return_value = mock_user
    mock_issue_tokens.return_value = ("access_token_mock", "refresh_token_mock")

    response = client.post(
        "/login",
        json={"email": "test@example.com", "password": "password123"}
    )

    assert response.status_code == 200
    assert response.json == {
        "accessToken": "access_token_mock",
        "refreshToken": "refresh_token_mock",
        "user": {"id": 1, "email": "test@example.com"},
    }
    mock_authenticate.assert_called_once_with("test@example.com", "password123")
    mock_issue_tokens.assert_called_once_with(mock_user)