"""
Test cases for mlflow_oidc_auth.utils.request_helpers_fastapi module.

This module contains comprehensive tests for FastAPI request handling functionality
including parameter extraction, authentication, and user information retrieval.
"""

import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio

from fastapi import HTTPException, Request
from fastapi.security import HTTPBasicCredentials, HTTPAuthorizationCredentials
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_PARAMETER_VALUE

from mlflow_oidc_auth.utils.request_helpers_fastapi import (
    get_username_from_session,
    get_username_from_basic_auth,
    get_username_from_bearer_token,
    get_authenticated_username,
    get_username,
    get_is_admin,
    get_base_path,
)


class TestRequestHelpersFastAPI(unittest.TestCase):
    """Test cases for FastAPI request helper utility functions."""

    def setUp(self) -> None:
        """Set up test environment."""
        pass

    def tearDown(self) -> None:
        """Clean up test environment."""
        pass

    def test_get_username_from_session_with_state(self):
        """Test username extraction from request state."""

        async def test_async():
            mock_request = MagicMock(spec=Request)
            mock_request.state = MagicMock()
            mock_request.state.username = "state_user"

            result = await get_username_from_session(mock_request)
            self.assertEqual(result, "state_user")

        asyncio.run(test_async())

    def test_get_username_from_session_with_session_fallback(self):
        """Test username extraction from session fallback."""

        async def test_async():
            mock_request = MagicMock(spec=Request)
            mock_request.state = MagicMock()
            mock_request.state.username = None
            mock_request.session = {"username": "session_user"}

            result = await get_username_from_session(mock_request)
            self.assertEqual(result, "session_user")

        asyncio.run(test_async())

    def test_get_username_from_session_no_username(self):
        """Test username extraction when no username is found."""

        async def test_async():
            mock_request = MagicMock(spec=Request)
            mock_request.state = MagicMock()
            mock_request.state.username = None
            mock_request.session = {}

            result = await get_username_from_session(mock_request)
            self.assertIsNone(result)

        asyncio.run(test_async())

    def test_get_username_from_session_no_state_attr(self):
        """Test username extraction when state has no username attribute."""

        async def test_async():
            mock_request = MagicMock(spec=Request)
            mock_request.state = MagicMock()
            # Remove username attribute
            if hasattr(mock_request.state, "username"):
                delattr(mock_request.state, "username")
            mock_request.session = {"username": "session_user"}

            result = await get_username_from_session(mock_request)
            self.assertEqual(result, "session_user")

        asyncio.run(test_async())

    def test_get_username_from_session_session_error(self):
        """Test username extraction when session access fails."""

        async def test_async():
            mock_request = MagicMock(spec=Request)
            mock_request.state = MagicMock()
            mock_request.state.username = None
            # Make session access raise an exception
            mock_request.session = MagicMock()
            mock_request.session.get.side_effect = Exception("Session error")

            result = await get_username_from_session(mock_request)
            self.assertIsNone(result)

        asyncio.run(test_async())

    @patch("mlflow_oidc_auth.utils.request_helpers_fastapi.store")
    def test_get_username_from_basic_auth_success(self, mock_store):
        """Test username extraction from basic auth credentials."""

        async def test_async():
            mock_credentials = HTTPBasicCredentials(username="test_user", password="test_pass")
            mock_user = MagicMock()
            mock_user.username = "test_user"
            mock_store.get_user.return_value = mock_user

            result = await get_username_from_basic_auth(mock_credentials)
            self.assertEqual(result, "test_user")
            mock_store.get_user.assert_called_once_with("test_user")

        asyncio.run(test_async())

    @patch("mlflow_oidc_auth.utils.request_helpers_fastapi.store")
    def test_get_username_from_basic_auth_no_credentials(self, mock_store):
        """Test username extraction when no basic auth credentials provided."""

        async def test_async():
            result = await get_username_from_basic_auth(None)
            self.assertIsNone(result)
            mock_store.get_user.assert_not_called()

        asyncio.run(test_async())

    @patch("mlflow_oidc_auth.utils.request_helpers_fastapi.store")
    def test_get_username_from_basic_auth_user_not_found(self, mock_store):
        """Test username extraction when user is not found."""

        async def test_async():
            mock_credentials = HTTPBasicCredentials(username="nonexistent", password="test_pass")
            mock_store.get_user.side_effect = Exception("User not found")

            result = await get_username_from_basic_auth(mock_credentials)
            self.assertIsNone(result)

        asyncio.run(test_async())

    @patch("mlflow_oidc_auth.utils.request_helpers_fastapi.store")
    def test_get_username_from_basic_auth_no_username(self, mock_store):
        """Test username extraction when user has no username."""

        async def test_async():
            mock_credentials = HTTPBasicCredentials(username="test_user", password="test_pass")
            mock_user = MagicMock()
            mock_user.username = None
            mock_store.get_user.return_value = mock_user

            result = await get_username_from_basic_auth(mock_credentials)
            self.assertIsNone(result)

        asyncio.run(test_async())

    @patch("mlflow_oidc_auth.utils.request_helpers_fastapi.validate_token")
    def test_get_username_from_bearer_token_success(self, mock_validate_token):
        """Test username extraction from bearer token."""

        async def test_async():
            mock_credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test_token")
            mock_validate_token.return_value = {"email": "user@example.com"}

            result = await get_username_from_bearer_token(mock_credentials)
            self.assertEqual(result, "user@example.com")
            mock_validate_token.assert_called_once_with("test_token")

        asyncio.run(test_async())

    @patch("mlflow_oidc_auth.utils.request_helpers_fastapi.validate_token")
    def test_get_username_from_bearer_token_no_credentials(self, mock_validate_token):
        """Test username extraction when no bearer token provided."""

        async def test_async():
            result = await get_username_from_bearer_token(None)
            self.assertIsNone(result)
            mock_validate_token.assert_not_called()

        asyncio.run(test_async())

    @patch("mlflow_oidc_auth.utils.request_helpers_fastapi.validate_token")
    def test_get_username_from_bearer_token_no_email(self, mock_validate_token):
        """Test username extraction when token has no email."""

        async def test_async():
            mock_credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test_token")
            mock_validate_token.return_value = {"sub": "user123"}  # No email field

            result = await get_username_from_bearer_token(mock_credentials)
            self.assertIsNone(result)

        asyncio.run(test_async())

    @patch("mlflow_oidc_auth.utils.request_helpers_fastapi.validate_token")
    def test_get_username_from_bearer_token_validation_error(self, mock_validate_token):
        """Test username extraction when token validation fails."""

        async def test_async():
            mock_credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid_token")
            mock_validate_token.side_effect = Exception("Invalid token")

            result = await get_username_from_bearer_token(mock_credentials)
            self.assertIsNone(result)

        asyncio.run(test_async())

    def test_get_authenticated_username_session_auth(self):
        """Test authenticated username retrieval using session auth."""

        async def test_async():
            mock_request = MagicMock(spec=Request)
            mock_request.state = MagicMock()
            mock_request.state.username = "session_user"

            result = await get_authenticated_username(mock_request, None, None)
            self.assertEqual(result, "session_user")

        asyncio.run(test_async())

    def test_get_authenticated_username_basic_auth(self):
        """Test authenticated username retrieval using basic auth."""

        async def test_async():
            mock_request = MagicMock(spec=Request)
            mock_request.state = MagicMock()
            mock_request.state.username = None
            mock_request.session = {}

            result = await get_authenticated_username(mock_request, "basic_user", None)
            self.assertEqual(result, "basic_user")

        asyncio.run(test_async())

    def test_get_authenticated_username_bearer_auth(self):
        """Test authenticated username retrieval using bearer token."""

        async def test_async():
            mock_request = MagicMock(spec=Request)
            mock_request.state = MagicMock()
            mock_request.state.username = None
            mock_request.session = {}

            result = await get_authenticated_username(mock_request, None, "bearer_user")
            self.assertEqual(result, "bearer_user")

        asyncio.run(test_async())

    def test_get_authenticated_username_no_auth(self):
        """Test authenticated username retrieval when no auth is provided."""

        async def test_async():
            mock_request = MagicMock(spec=Request)
            mock_request.state = MagicMock()
            mock_request.state.username = None
            mock_request.session = {}

            with self.assertRaises(HTTPException) as cm:
                await get_authenticated_username(mock_request, None, None)
            self.assertEqual(cm.exception.status_code, 401)
            self.assertIn("Authentication required", cm.exception.detail)

        asyncio.run(test_async())

    @patch("mlflow_oidc_auth.utils.request_helpers_fastapi.get_authenticated_username")
    @patch("mlflow_oidc_auth.utils.request_helpers_fastapi.get_username_from_basic_auth")
    @patch("mlflow_oidc_auth.utils.request_helpers_fastapi.get_username_from_bearer_token")
    def test_get_username_success(self, mock_bearer, mock_basic, mock_authenticated):
        """Test legacy get_username function success."""

        async def test_async():
            mock_request = MagicMock(spec=Request)
            mock_bearer.return_value = None
            mock_basic.return_value = None
            mock_authenticated.return_value = "test_user"

            result = await get_username(mock_request)
            self.assertEqual(result, "test_user")

        asyncio.run(test_async())

    @patch("mlflow_oidc_auth.utils.request_helpers_fastapi.get_authenticated_username")
    @patch("mlflow_oidc_auth.utils.request_helpers_fastapi.get_username_from_basic_auth")
    @patch("mlflow_oidc_auth.utils.request_helpers_fastapi.get_username_from_bearer_token")
    def test_get_username_http_exception(self, mock_bearer, mock_basic, mock_authenticated):
        """Test legacy get_username function with HTTP exception."""

        async def test_async():
            mock_request = MagicMock(spec=Request)
            mock_bearer.return_value = None
            mock_basic.return_value = None
            mock_authenticated.side_effect = HTTPException(status_code=401, detail="Auth required")

            with self.assertRaises(MlflowException) as cm:
                await get_username(mock_request)
            self.assertEqual(cm.exception.error_code, "INVALID_PARAMETER_VALUE")
            self.assertIn("Auth required", str(cm.exception))

        asyncio.run(test_async())

    @patch("mlflow_oidc_auth.utils.request_helpers_fastapi.store")
    @patch("mlflow_oidc_auth.utils.request_helpers_fastapi.get_username")
    def test_get_is_admin_true(self, mock_get_username, mock_store):
        """Test admin status retrieval when user is admin."""

        async def test_async():
            mock_request = MagicMock(spec=Request)
            mock_get_username.return_value = "admin_user"
            mock_user = MagicMock()
            mock_user.is_admin = True
            mock_store.get_user.return_value = mock_user

            result = await get_is_admin(mock_request)
            self.assertTrue(result)
            mock_store.get_user.assert_called_once_with("admin_user")

        asyncio.run(test_async())

    @patch("mlflow_oidc_auth.utils.request_helpers_fastapi.store")
    @patch("mlflow_oidc_auth.utils.request_helpers_fastapi.get_username")
    def test_get_is_admin_false(self, mock_get_username, mock_store):
        """Test admin status retrieval when user is not admin."""

        async def test_async():
            mock_request = MagicMock(spec=Request)
            mock_get_username.return_value = "regular_user"
            mock_user = MagicMock()
            mock_user.is_admin = False
            mock_store.get_user.return_value = mock_user

            result = await get_is_admin(mock_request)
            self.assertFalse(result)

        asyncio.run(test_async())

    def test_get_base_path_with_forwarded_prefix(self):
        """Test base path extraction with X-Forwarded-Prefix header."""

        async def test_async():
            mock_request = MagicMock(spec=Request)
            mock_request.headers = {"x-forwarded-prefix": "/my-app/"}
            mock_request.base_url = MagicMock()
            mock_request.base_url.path = ""

            result = await get_base_path(mock_request)
            self.assertEqual(result, "/my-app")

        asyncio.run(test_async())

    def test_get_base_path_with_base_url_path(self):
        """Test base path extraction with base URL path."""

        async def test_async():
            mock_request = MagicMock(spec=Request)
            mock_request.headers = {}
            mock_request.base_url = MagicMock()
            mock_request.base_url.path = "/api/v1/"

            result = await get_base_path(mock_request)
            self.assertEqual(result, "/api/v1")

        asyncio.run(test_async())

    def test_get_base_path_empty(self):
        """Test base path extraction when no path is available."""

        async def test_async():
            mock_request = MagicMock(spec=Request)
            mock_request.headers = {}
            mock_request.base_url = MagicMock()
            mock_request.base_url.path = ""

            result = await get_base_path(mock_request)
            self.assertEqual(result, "")

        asyncio.run(test_async())


if __name__ == "__main__":
    unittest.main()
