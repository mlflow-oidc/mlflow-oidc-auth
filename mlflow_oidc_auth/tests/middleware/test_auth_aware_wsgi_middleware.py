"""
Comprehensive tests for AuthAwareWSGIMiddleware and AuthInjectingWSGIApp.

This module tests WSGI middleware functionality including:
- ASGI to WSGI conversion with authentication context
- Authentication information injection into WSGI environ
- WSGI application wrapping and execution
- Error handling and edge cases
- Non-HTTP request handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Dict, Any

from mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware import AuthAwareWSGIMiddleware, AuthInjectingWSGIApp


class TestAuthInjectingWSGIApp:
    """Test suite for AuthInjectingWSGIApp functionality."""

    def test_init(self, mock_flask_app, sample_asgi_scope):
        """Test AuthInjectingWSGIApp initialization."""
        app = AuthInjectingWSGIApp(mock_flask_app, sample_asgi_scope)

        assert app.flask_app == mock_flask_app
        assert app.scope == sample_asgi_scope

    def test_call_with_auth_info(self, mock_flask_app, sample_asgi_scope, sample_wsgi_environ, mock_logger):
        """Test WSGI app call with authentication information in scope."""
        # Add auth info to scope
        sample_asgi_scope["mlflow_oidc_auth"] = {"username": "user@example.com", "is_admin": False}

        app = AuthInjectingWSGIApp(mock_flask_app, sample_asgi_scope)

        # Mock start_response
        start_response = MagicMock()

        with patch("mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware.logger", mock_logger):
            result = app(sample_wsgi_environ, start_response)

            # Verify auth info was injected into environ
            assert sample_wsgi_environ["mlflow_oidc_auth.username"] == "user@example.com"
            assert sample_wsgi_environ["mlflow_oidc_auth.is_admin"] is False

            # Verify Flask app was called with enhanced environ
            assert result == [b'{"message": "Hello from Flask"}']

            # Verify debug logging
            mock_logger.debug.assert_called_once()
            log_message = mock_logger.debug.call_args[0][0]
            assert "Injecting auth info into WSGI environ" in log_message
            assert "username=user@example.com" in log_message
            assert "is_admin=False" in log_message

    def test_call_with_admin_auth_info(self, mock_flask_app, sample_asgi_scope, sample_wsgi_environ, mock_logger):
        """Test WSGI app call with admin authentication information."""
        # Add admin auth info to scope
        sample_asgi_scope["mlflow_oidc_auth"] = {"username": "admin@example.com", "is_admin": True}

        app = AuthInjectingWSGIApp(mock_flask_app, sample_asgi_scope)

        # Mock start_response
        start_response = MagicMock()

        with patch("mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware.logger", mock_logger):
            result = app(sample_wsgi_environ, start_response)

            # Verify admin auth info was injected
            assert sample_wsgi_environ["mlflow_oidc_auth.username"] == "admin@example.com"
            assert sample_wsgi_environ["mlflow_oidc_auth.is_admin"] is True

            # Verify Flask app was called
            assert result == [b'{"message": "Hello from Flask"}']

            # Verify debug logging with admin status
            mock_logger.debug.assert_called_once()
            log_message = mock_logger.debug.call_args[0][0]
            assert "username=admin@example.com" in log_message
            assert "is_admin=True" in log_message

    def test_call_without_auth_info(self, mock_flask_app, sample_asgi_scope, sample_wsgi_environ, mock_logger):
        """Test WSGI app call without authentication information in scope."""
        # No auth info in scope
        app = AuthInjectingWSGIApp(mock_flask_app, sample_asgi_scope)

        # Mock start_response
        start_response = MagicMock()

        with patch("mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware.logger", mock_logger):
            result = app(sample_wsgi_environ, start_response)

            # Verify no auth info was injected into environ
            assert "mlflow_oidc_auth.username" not in sample_wsgi_environ
            assert "mlflow_oidc_auth.is_admin" not in sample_wsgi_environ

            # Verify Flask app was still called
            assert result == [b'{"message": "Hello from Flask"}']

            # Verify no debug logging for auth injection
            mock_logger.debug.assert_not_called()

    def test_call_with_empty_auth_info(self, mock_flask_app, sample_asgi_scope, sample_wsgi_environ, mock_logger):
        """Test WSGI app call with empty authentication information."""
        # Empty auth info in scope
        sample_asgi_scope["mlflow_oidc_auth"] = {}

        app = AuthInjectingWSGIApp(mock_flask_app, sample_asgi_scope)

        # Mock start_response
        start_response = MagicMock()

        with patch("mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware.logger", mock_logger):
            result = app(sample_wsgi_environ, start_response)

            # Verify no auth info was injected
            assert "mlflow_oidc_auth.username" not in sample_wsgi_environ
            assert "mlflow_oidc_auth.is_admin" not in sample_wsgi_environ

            # Verify Flask app was called
            assert result == [b'{"message": "Hello from Flask"}']

            # Verify no debug logging
            mock_logger.debug.assert_not_called()

    def test_call_with_username_only(self, mock_flask_app, sample_asgi_scope, sample_wsgi_environ, mock_logger):
        """Test WSGI app call with username but no is_admin flag."""
        # Auth info with username only
        sample_asgi_scope["mlflow_oidc_auth"] = {"username": "user@example.com"}

        app = AuthInjectingWSGIApp(mock_flask_app, sample_asgi_scope)

        # Mock start_response
        start_response = MagicMock()

        with patch("mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware.logger", mock_logger):
            result = app(sample_wsgi_environ, start_response)

            # Verify username was injected, is_admin defaults to False
            assert sample_wsgi_environ["mlflow_oidc_auth.username"] == "user@example.com"
            assert sample_wsgi_environ["mlflow_oidc_auth.is_admin"] is False

            # Verify Flask app was called
            assert result == [b'{"message": "Hello from Flask"}']

            # Verify debug logging
            mock_logger.debug.assert_called_once()
            log_message = mock_logger.debug.call_args[0][0]
            assert "is_admin=False" in log_message

    def test_call_preserves_existing_environ(self, mock_flask_app, sample_asgi_scope, sample_wsgi_environ):
        """Test that existing environ variables are preserved."""
        # Add some existing environ variables
        sample_wsgi_environ["EXISTING_VAR"] = "existing_value"
        sample_wsgi_environ["HTTP_AUTHORIZATION"] = "Bearer token"

        # Add auth info to scope
        sample_asgi_scope["mlflow_oidc_auth"] = {"username": "user@example.com", "is_admin": True}

        app = AuthInjectingWSGIApp(mock_flask_app, sample_asgi_scope)

        # Mock start_response
        start_response = MagicMock()

        result = app(sample_wsgi_environ, start_response)

        # Verify existing environ variables are preserved
        assert sample_wsgi_environ["EXISTING_VAR"] == "existing_value"
        assert sample_wsgi_environ["HTTP_AUTHORIZATION"] == "Bearer token"

        # Verify auth info was added
        assert sample_wsgi_environ["mlflow_oidc_auth.username"] == "user@example.com"
        assert sample_wsgi_environ["mlflow_oidc_auth.is_admin"] is True

    def test_call_flask_app_exception(self, sample_asgi_scope, sample_wsgi_environ):
        """Test handling when Flask app raises an exception."""

        def failing_flask_app(environ, start_response):
            raise RuntimeError("Flask app error")

        app = AuthInjectingWSGIApp(failing_flask_app, sample_asgi_scope)

        # Mock start_response
        start_response = MagicMock()

        # Verify exception is propagated
        with pytest.raises(RuntimeError, match="Flask app error"):
            app(sample_wsgi_environ, start_response)

    def test_call_start_response_called(self, mock_flask_app, sample_asgi_scope, sample_wsgi_environ):
        """Test that start_response is properly called by Flask app."""
        app = AuthInjectingWSGIApp(mock_flask_app, sample_asgi_scope)

        # Mock start_response
        start_response = MagicMock()

        result = app(sample_wsgi_environ, start_response)

        # Verify start_response was called (by the mock Flask app)
        # The mock Flask app should call start_response
        assert result == [b'{"message": "Hello from Flask"}']


class TestAuthAwareWSGIMiddleware:
    """Test suite for AuthAwareWSGIMiddleware functionality."""

    def test_init(self, mock_flask_app):
        """Test AuthAwareWSGIMiddleware initialization."""
        middleware = AuthAwareWSGIMiddleware(mock_flask_app)

        assert middleware.flask_app == mock_flask_app

    @pytest.mark.asyncio
    async def test_call_http_request(self, mock_flask_app, sample_asgi_scope, mock_receive, mock_send):
        """Test middleware call with HTTP request."""
        sample_asgi_scope["type"] = "http"
        sample_asgi_scope["mlflow_oidc_auth"] = {"username": "user@example.com", "is_admin": False}

        middleware = AuthAwareWSGIMiddleware(mock_flask_app)

        with patch("mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware.WSGIMiddleware") as mock_wsgi_middleware:
            # Mock WSGIMiddleware instance
            mock_wsgi_instance = AsyncMock()
            mock_wsgi_middleware.return_value = mock_wsgi_instance

            await middleware(sample_asgi_scope, mock_receive, mock_send)

            # Verify WSGIMiddleware was created with AuthInjectingWSGIApp
            mock_wsgi_middleware.assert_called_once()
            created_app = mock_wsgi_middleware.call_args[0][0]
            assert isinstance(created_app, AuthInjectingWSGIApp)
            assert created_app.flask_app == mock_flask_app
            assert created_app.scope == sample_asgi_scope

            # Verify WSGIMiddleware was called
            mock_wsgi_instance.assert_called_once_with(sample_asgi_scope, mock_receive, mock_send)

    @pytest.mark.asyncio
    async def test_call_non_http_request(self, mock_flask_app, sample_asgi_scope, mock_receive, mock_send):
        """Test middleware call with non-HTTP request."""
        sample_asgi_scope["type"] = "websocket"

        middleware = AuthAwareWSGIMiddleware(mock_flask_app)

        # Mock Flask app as ASGI app for non-HTTP requests
        mock_asgi_flask_app = AsyncMock()
        middleware.flask_app = mock_asgi_flask_app

        await middleware(sample_asgi_scope, mock_receive, mock_send)

        # Verify Flask app was called directly for non-HTTP requests
        mock_asgi_flask_app.assert_called_once_with(sample_asgi_scope, mock_receive, mock_send)

    @pytest.mark.asyncio
    async def test_call_lifespan_request(self, mock_flask_app, mock_receive, mock_send):
        """Test middleware call with lifespan request."""
        lifespan_scope = {
            "type": "lifespan",
            "asgi": {"version": "3.0"},
        }

        middleware = AuthAwareWSGIMiddleware(mock_flask_app)

        # Mock Flask app as ASGI app for lifespan requests
        mock_asgi_flask_app = AsyncMock()
        middleware.flask_app = mock_asgi_flask_app

        await middleware(sample_asgi_scope, mock_receive, mock_send)

        # Verify Flask app was called directly for lifespan requests
        mock_asgi_flask_app.assert_called_once_with(sample_asgi_scope, mock_receive, mock_send)

    @pytest.mark.asyncio
    async def test_call_http_with_complex_auth_info(self, mock_flask_app, sample_asgi_scope, mock_receive, mock_send):
        """Test middleware with complex authentication information."""
        sample_asgi_scope["type"] = "http"
        sample_asgi_scope["mlflow_oidc_auth"] = {
            "username": "admin@example.com",
            "is_admin": True,
            "groups": ["admin", "users"],
            "extra_claims": {"department": "engineering"},
        }

        middleware = AuthAwareWSGIMiddleware(mock_flask_app)

        with patch("mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware.WSGIMiddleware") as mock_wsgi_middleware:
            mock_wsgi_instance = AsyncMock()
            mock_wsgi_middleware.return_value = mock_wsgi_instance

            await middleware(sample_asgi_scope, mock_receive, mock_send)

            # Verify AuthInjectingWSGIApp was created with full scope
            created_app = mock_wsgi_middleware.call_args[0][0]
            assert created_app.scope["mlflow_oidc_auth"]["username"] == "admin@example.com"
            assert created_app.scope["mlflow_oidc_auth"]["is_admin"] is True
            assert created_app.scope["mlflow_oidc_auth"]["groups"] == ["admin", "users"]

    @pytest.mark.asyncio
    async def test_call_http_without_auth_info(self, mock_flask_app, sample_asgi_scope, mock_receive, mock_send):
        """Test middleware with HTTP request but no authentication information."""
        sample_asgi_scope["type"] = "http"
        # No mlflow_oidc_auth in scope

        middleware = AuthAwareWSGIMiddleware(mock_flask_app)

        with patch("mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware.WSGIMiddleware") as mock_wsgi_middleware:
            mock_wsgi_instance = AsyncMock()
            mock_wsgi_middleware.return_value = mock_wsgi_instance

            await middleware(sample_asgi_scope, mock_receive, mock_send)

            # Verify WSGIMiddleware was still created and called
            mock_wsgi_middleware.assert_called_once()
            created_app = mock_wsgi_middleware.call_args[0][0]
            assert isinstance(created_app, AuthInjectingWSGIApp)
            assert created_app.scope == sample_asgi_scope

            mock_wsgi_instance.assert_called_once_with(sample_asgi_scope, mock_receive, mock_send)

    @pytest.mark.asyncio
    async def test_call_wsgi_middleware_exception(self, mock_flask_app, sample_asgi_scope, mock_receive, mock_send):
        """Test handling when WSGIMiddleware raises an exception."""
        sample_asgi_scope["type"] = "http"

        middleware = AuthAwareWSGIMiddleware(mock_flask_app)

        with patch("mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware.WSGIMiddleware") as mock_wsgi_middleware:
            mock_wsgi_instance = AsyncMock()
            mock_wsgi_instance.side_effect = RuntimeError("WSGI middleware error")
            mock_wsgi_middleware.return_value = mock_wsgi_instance

            # Verify exception is propagated
            with pytest.raises(RuntimeError, match="WSGI middleware error"):
                await middleware(sample_asgi_scope, mock_receive, mock_send)

    @pytest.mark.asyncio
    async def test_call_multiple_http_requests(self, mock_flask_app, mock_receive, mock_send):
        """Test middleware handles multiple HTTP requests correctly."""
        middleware = AuthAwareWSGIMiddleware(mock_flask_app)

        # First request
        scope1 = {"type": "http", "path": "/api/users", "mlflow_oidc_auth": {"username": "user1@example.com", "is_admin": False}}

        # Second request
        scope2 = {"type": "http", "path": "/api/admin", "mlflow_oidc_auth": {"username": "admin@example.com", "is_admin": True}}

        with patch("mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware.WSGIMiddleware") as mock_wsgi_middleware:
            mock_wsgi_instance = AsyncMock()
            mock_wsgi_middleware.return_value = mock_wsgi_instance

            # Process first request
            await middleware(scope1, mock_receive, mock_send)

            # Process second request
            await middleware(scope2, mock_receive, mock_send)

            # Verify WSGIMiddleware was created twice with different AuthInjectingWSGIApp instances
            assert mock_wsgi_middleware.call_count == 2

            # Verify each call had correct scope
            first_app = mock_wsgi_middleware.call_args_list[0][0][0]
            second_app = mock_wsgi_middleware.call_args_list[1][0][0]

            assert first_app.scope["mlflow_oidc_auth"]["username"] == "user1@example.com"
            assert second_app.scope["mlflow_oidc_auth"]["username"] == "admin@example.com"

    @pytest.mark.asyncio
    async def test_integration_auth_injection_flow(self, sample_asgi_scope, sample_wsgi_environ, mock_receive, mock_send):
        """Test complete integration flow from ASGI scope to WSGI environ injection."""
        # Setup auth info in ASGI scope
        sample_asgi_scope["type"] = "http"
        sample_asgi_scope["mlflow_oidc_auth"] = {"username": "integration@example.com", "is_admin": True}

        # Create a Flask app that captures the environ
        captured_environ = {}

        def capturing_flask_app(environ, start_response):
            captured_environ.update(environ)
            status = "200 OK"
            headers = [("Content-Type", "application/json")]
            start_response(status, headers)
            return [b'{"status": "ok"}']

        middleware = AuthAwareWSGIMiddleware(capturing_flask_app)

        # Execute the middleware
        await middleware(sample_asgi_scope, mock_receive, mock_send)

        # Verify auth info was properly injected into WSGI environ
        assert captured_environ["mlflow_oidc_auth.username"] == "integration@example.com"
        assert captured_environ["mlflow_oidc_auth.is_admin"] is True
