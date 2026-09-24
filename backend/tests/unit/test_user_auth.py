import unittest
from unittest.mock import patch, MagicMock
from flask import Flask, jsonify
from app.auth.routes import auth_bp

class TestUserAuth(unittest.TestCase):
    def setUp(self):
        # Create a Flask app and register the auth blueprint
        self.app = Flask(__name__)
        self.app.register_blueprint(auth_bp)
        self.client = self.app.test_client()

    @patch("app.auth.routes.authenticate")
    def test_login_missing_email_or_password(self, mock_authenticate):
        # Test when email or password is missing
        response = self.client.post("/login", json={"email": "test@example.com"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {"error": "email and password are required"})

        response = self.client.post("/login", json={"password": "password123"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {"error": "email and password are required"})

    @patch("app.auth.routes.authenticate")
    def test_login_invalid_credentials(self, mock_authenticate):
        # Test when credentials are invalid
        mock_authenticate.return_value = None  # Simulate invalid credentials
        response = self.client.post("/login", json={"email": "test@example.com", "password": "wrongpassword"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json, {"error": "Invalid credentials"})

    @patch("app.auth.routes.issue_tokens")
    @patch("app.auth.routes.authenticate")
    def test_login_successful(self, mock_authenticate, mock_issue_tokens):
        # Test successful login
        mock_user = MagicMock()
        mock_user.to_dict.return_value = {"id": 1, "email": "test@example.com"}
        mock_authenticate.return_value = mock_user
        mock_issue_tokens.return_value = ("access_token_mock", "refresh_token_mock")

        response = self.client.post(
            "/login",
            json={"email": "test@example.com", "password": "password123"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json,
            {
                "accessToken": "access_token_mock",
                "refreshToken": "refresh_token_mock",
                "user": {"id": 1, "email": "test@example.com"},
            },
        )
        mock_authenticate.assert_called_once_with("test@example.com", "password123")
        mock_issue_tokens.assert_called_once_with(mock_user)

if __name__ == "__main__":
    unittest.main()