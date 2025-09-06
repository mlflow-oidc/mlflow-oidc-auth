"""
Test the FastAPI-Flask Integration

This test verifies that the Flask hooks bridge works correctly
with FastAPI authentication middleware.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from flask import Flask
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mlflow_oidc_auth.bridge.user import FlaskContextBridge, FlaskHooksBridge, get_fastapi_username, get_fastapi_admin_status
from mlflow_oidc_auth.utils.fastapi_flask_bridge import get_current_user_from_fastapi, is_authenticated_via_fastapi, FastAPIFlaskAuthBridge


class TestFlaskContextBridge:
    """Test the Flask context bridge functionality."""

    def test_set_and_get_user_context(self):
        """Test setting and getting user context."""
        # Clear any existing context
        FlaskContextBridge.clear_context()

        # Set user context
        FlaskContextBridge.set_user_context("test_user", True, {"path": "/test"})

        # Get context
        username, is_admin, request_data = FlaskContextBridge.get_user_context()

        assert username == "test_user"
        assert is_admin is True
        assert request_data == {"path": "/test"}

        # Clear context
        FlaskContextBridge.clear_context()
        username, is_admin, request_data = FlaskContextBridge.get_user_context()

        assert username is None
        assert is_admin is False
        assert request_data == {}

    def test_utility_functions(self):
        """Test utility functions for accessing FastAPI context."""
        # Clear context
        FlaskContextBridge.clear_context()

        # Test when no context is set
        assert get_fastapi_username() is None
        assert get_fastapi_admin_status() is False

        # Set context
        FlaskContextBridge.set_user_context("admin_user", True)

        # Test utility functions
        assert get_fastapi_username() == "admin_user"
        assert get_fastapi_admin_status() is True

        # Clean up
        FlaskContextBridge.clear_context()


class TestFlaskHooksBridge:
    """Test the Flask hooks bridge WSGI middleware."""

    def test_flask_hooks_bridge_init(self):
        """Test FlaskHooksBridge initialization."""
        mock_app = Mock()
        mock_wsgi_app = Mock()
        mock_app.wsgi_app = mock_wsgi_app

        bridge = FlaskHooksBridge(mock_app)

        assert bridge.app == mock_app
        assert bridge.wsgi_app == mock_wsgi_app
        assert mock_app.wsgi_app == bridge

    @patch("mlflow_oidc_auth.middleware.flask_hooks_bridge.before_request_hook")
    @patch("mlflow_oidc_auth.middleware.flask_hooks_bridge.after_request_hook")
    def test_wsgi_call_with_user_context(self, mock_after_hook, mock_before_hook):
        """Test WSGI call with user context in environ."""
        # Setup mocks
        mock_app = Mock()
        mock_wsgi_app = Mock()
        mock_app.wsgi_app = mock_wsgi_app

        # Mock before_request hook returns None (continue processing)
        mock_before_hook.return_value = None

        # Mock after_request hook returns the response unchanged
        mock_after_hook.side_effect = lambda x: x

        # Mock WSGI app response
        mock_wsgi_app.return_value = [b'{"test": "response"}']

        # Create bridge
        bridge = FlaskHooksBridge(mock_app)

        # Create test environ with user context
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/test",
            "mlflow_oidc_auth.username": "test_user",
            "mlflow_oidc_auth.is_admin": False,
            "HTTP_HOST": "localhost",
            "wsgi.url_scheme": "http",
        }

        start_response = Mock()

        # Call the bridge
        with patch("mlflow_oidc_auth.middleware.flask_hooks_bridge.Request") as mock_request_class:
            mock_request = Mock()
            mock_request.path = "/test"
            mock_request.method = "GET"
            mock_request.args = {}
            mock_request.headers = {}
            mock_request_class.return_value = mock_request

            result = bridge(environ, start_response)

            # Verify the result
            assert result == [b'{"test": "response"}']

            # Verify hooks were called
            mock_before_hook.assert_called_once()
            mock_after_hook.assert_called_once()


class TestFastAPIFlaskBridge:
    """Test the FastAPI-Flask bridge utilities."""

    def test_get_current_user_from_fastapi(self):
        """Test getting current user from FastAPI context."""
        # Clear context
        FlaskContextBridge.clear_context()

        # Test when no user is authenticated
        username, is_admin = get_current_user_from_fastapi()
        assert username is None
        assert is_admin is False
        assert not is_authenticated_via_fastapi()

        # Set user context
        FlaskContextBridge.set_user_context("test_user", True)

        # Test with authenticated user
        username, is_admin = get_current_user_from_fastapi()
        assert username == "test_user"
        assert is_admin is True
        assert is_authenticated_via_fastapi()

        # Clean up
        FlaskContextBridge.clear_context()

    def test_fastapi_flask_auth_bridge_methods(self):
        """Test FastAPIFlaskAuthBridge static methods."""
        # Clear context
        FlaskContextBridge.clear_context()

        # Test with no authentication
        assert FastAPIFlaskAuthBridge.get_authenticated_user() is None
        assert not FastAPIFlaskAuthBridge.is_admin_user()

        session_data = FastAPIFlaskAuthBridge.get_user_session_data()
        assert session_data == {}

        # Set user context
        FlaskContextBridge.set_user_context("admin_user", True, {"path": "/admin"})

        # Test with authentication
        assert FastAPIFlaskAuthBridge.get_authenticated_user() == "admin_user"
        assert FastAPIFlaskAuthBridge.is_admin_user() is True

        session_data = FastAPIFlaskAuthBridge.get_user_session_data()
        assert session_data["username"] == "admin_user"
        assert session_data["is_admin"] is True

        request_info = FastAPIFlaskAuthBridge.get_request_info()
        assert request_info == {"path": "/admin"}

        # Clean up
        FlaskContextBridge.clear_context()

    @patch("mlflow_oidc_auth.utils.fastapi_flask_bridge.utils")
    def test_patch_flask_utils(self, mock_utils):
        """Test patching Flask utility functions."""
        # Setup mocks
        mock_original_get_username = Mock(return_value="flask_user")
        mock_original_get_is_admin = Mock(return_value=False)

        mock_utils.get_username = mock_original_get_username
        mock_utils.get_is_admin = mock_original_get_is_admin

        # Apply patches
        FastAPIFlaskAuthBridge.patch_flask_utils()

        # Test that functions are patched
        assert mock_utils.get_username != mock_original_get_username
        assert mock_utils.get_is_admin != mock_original_get_is_admin

        # Clear FastAPI context
        FlaskContextBridge.clear_context()

        # Test fallback to original functions
        result = mock_utils.get_username()
        assert result == "flask_user"  # Should fall back to original

        result = mock_utils.get_is_admin()
        assert result is False  # Should fall back to original

        # Set FastAPI context
        FlaskContextBridge.set_user_context("fastapi_user", True)

        # Test FastAPI context takes precedence
        result = mock_utils.get_username()
        assert result == "fastapi_user"  # Should use FastAPI context

        result = mock_utils.get_is_admin()
        assert result is True  # Should use FastAPI context

        # Clean up
        FlaskContextBridge.clear_context()


def test_integration_example():
    """
    Integration test showing how the system works end-to-end.
    """
    # Clear any existing context
    FlaskContextBridge.clear_context()

    # Simulate FastAPI middleware setting user context
    def simulate_fastapi_auth_middleware():
        """Simulate FastAPI auth middleware setting context."""
        FlaskContextBridge.set_user_context("integration_user", False, {"path": "/api/test", "method": "GET", "headers": {"Authorization": "Bearer token123"}})

    # Simulate Flask hook using FastAPI context
    def simulate_flask_hook():
        """Simulate Flask hook accessing FastAPI context."""
        username, is_admin = get_current_user_from_fastapi()

        assert username == "integration_user"
        assert is_admin is False
        assert is_authenticated_via_fastapi()

        request_data = FlaskContextBridge.get_user_context()[2]
        assert request_data["path"] == "/api/test"
        assert request_data["method"] == "GET"

        return f"Hook processed request for {username}"

    # Run the integration test
    simulate_fastapi_auth_middleware()
    result = simulate_flask_hook()

    assert result == "Hook processed request for integration_user"

    # Clean up
    FlaskContextBridge.clear_context()


if __name__ == "__main__":
    # Run basic tests
    print("Running FastAPI-Flask integration tests...")

    # Test context bridge
    test_context = TestFlaskContextBridge()
    test_context.test_set_and_get_user_context()
    test_context.test_utility_functions()
    print("✓ Context bridge tests passed")

    # Test bridge utilities
    test_bridge = TestFastAPIFlaskBridge()
    test_bridge.test_get_current_user_from_fastapi()
    test_bridge.test_fastapi_flask_auth_bridge_methods()
    print("✓ Bridge utilities tests passed")

    # Test integration
    test_integration_example()
    print("✓ Integration test passed")

    print("All tests passed! FastAPI-Flask integration is working correctly.")
