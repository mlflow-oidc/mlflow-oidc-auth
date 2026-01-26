"""
Comprehensive tests for AuthMiddleware.

This module tests authentication middleware behavior including:
- Authentication method handling (basic, bearer, session)
- Route protection and unprotected route handling
- User context setting and admin status checking
- Error handling and authentication failures
- ASGI scope injection for WSGI compatibility
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import Response
from fastapi.responses import RedirectResponse

from mlflow_oidc_auth.middleware.auth_middleware import AuthMiddleware


class TestAuthMiddleware:
    """Test suite for AuthMiddleware functionality."""

    @pytest.fixture
    def auth_middleware(self, test_fastapi_app):
        """Create AuthMiddleware instance for testing."""
        return AuthMiddleware(test_fastapi_app)

    def test_init(self, test_fastapi_app):
        """Test AuthMiddleware initialization."""
        middleware = AuthMiddleware(test_fastapi_app)
        assert middleware.app == test_fastapi_app

    def test_is_unprotected_route_health(self, auth_middleware):
        """Test that health endpoint is unprotected."""
        assert auth_middleware._is_unprotected_route("/health") is True
        assert auth_middleware._is_unprotected_route("/health/check") is True

    def test_is_unprotected_route_login(self, auth_middleware):
        """Test that login endpoints are unprotected."""
        assert auth_middleware._is_unprotected_route("/login") is True
        assert auth_middleware._is_unprotected_route("/login/oauth") is True

    def test_is_unprotected_route_callback(self, auth_middleware):
        """Test that callback endpoint is unprotected."""
        assert auth_middleware._is_unprotected_route("/callback") is True
        assert auth_middleware._is_unprotected_route("/callback/oauth") is True

    def test_is_unprotected_route_oidc_static(self, auth_middleware):
        """Test that OIDC static endpoints are unprotected."""
        assert auth_middleware._is_unprotected_route("/oidc/static/css/style.css") is True
        assert auth_middleware._is_unprotected_route("/oidc/static/js/app.js") is True

    def test_is_unprotected_route_metrics(self, auth_middleware):
        """Test that metrics endpoint is unprotected."""
        assert auth_middleware._is_unprotected_route("/metrics") is True
        assert auth_middleware._is_unprotected_route("/metrics/health") is True

    def test_is_unprotected_route_docs(self, auth_middleware):
        """Test that documentation endpoints are unprotected."""
        assert auth_middleware._is_unprotected_route("/docs") is True
        assert auth_middleware._is_unprotected_route("/redoc") is True
        assert auth_middleware._is_unprotected_route("/openapi.json") is True

    def test_is_unprotected_route_oidc_ui(self, auth_middleware):
        """Test that OIDC UI endpoints are unprotected."""
        assert auth_middleware._is_unprotected_route("/oidc/ui") is True
        assert auth_middleware._is_unprotected_route("/oidc/ui/admin") is True

    def test_is_unprotected_route_protected(self, auth_middleware):
        """Test that other routes are protected."""
        assert auth_middleware._is_unprotected_route("/api/users") is False
        assert auth_middleware._is_unprotected_route("/api/experiments") is False
        assert auth_middleware._is_unprotected_route("/protected") is False

    @pytest.mark.asyncio
    async def test_authenticate_basic_auth_success(self, auth_middleware, mock_store):
        """Test successful basic authentication."""
        with patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store):
            auth_header = "Basic YWRtaW5AZXhhbXBsZS5jb206YWRtaW5fcGFzcw=="  # admin@example.com:admin_pass

            success, username, error = await auth_middleware._authenticate_basic_auth(auth_header)

            assert success is True
            assert username == "admin@example.com"
            assert error == ""
            mock_store.authenticate_user.assert_called_once_with("admin@example.com", "admin_pass")

    @pytest.mark.asyncio
    async def test_authenticate_basic_auth_failure(self, auth_middleware, mock_store):
        """Test failed basic authentication with invalid credentials."""
        with patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store):
            auth_header = "Basic aW52YWxpZDppbnZhbGlk"  # invalid:invalid

            success, username, error = await auth_middleware._authenticate_basic_auth(auth_header)

            assert success is False
            assert username is None
            assert error == "Invalid basic auth credentials"
            mock_store.authenticate_user.assert_called_once_with("invalid", "invalid")

    @pytest.mark.asyncio
    async def test_authenticate_basic_auth_malformed_header(self, auth_middleware, mock_store):
        """Test basic authentication with malformed header."""
        with patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store):
            auth_header = "Basic invalid_base64"

            success, username, error = await auth_middleware._authenticate_basic_auth(auth_header)

            assert success is False
            assert username is None
            assert error == "Invalid basic auth format"

    @pytest.mark.asyncio
    async def test_authenticate_basic_auth_missing_colon(self, auth_middleware, mock_store):
        """Test basic authentication with credentials missing colon separator."""
        with patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store):
            # Base64 encode "usernamenocolon" (missing colon)
            import base64

            encoded = base64.b64encode("usernamenocolon".encode()).decode()
            auth_header = f"Basic {encoded}"

            success, username, error = await auth_middleware._authenticate_basic_auth(auth_header)

            assert success is False
            assert username is None
            assert error == "Invalid basic auth format"

    @pytest.mark.asyncio
    async def test_authenticate_basic_auth_store_exception(self, auth_middleware, mock_store):
        """Test basic authentication when store raises exception."""
        mock_store.authenticate_user.side_effect = Exception("Database error")

        with patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store):
            auth_header = "Basic YWRtaW5AZXhhbXBsZS5jb206YWRtaW5fcGFzcw=="

            success, username, error = await auth_middleware._authenticate_basic_auth(auth_header)

            assert success is False
            assert username is None
            assert error == "Invalid basic auth format"

    @pytest.mark.asyncio
    async def test_authenticate_bearer_token_success(self, auth_middleware, mock_validate_token):
        """Test successful bearer token authentication."""
        mock_validate_token_func = MagicMock(side_effect=mock_validate_token)

        with patch("mlflow_oidc_auth.middleware.auth_middleware.validate_token", mock_validate_token_func):
            auth_header = "Bearer valid_token"

            success, username, error = await auth_middleware._authenticate_bearer_token(auth_header)

            assert success is True
            assert username == "user@example.com"
            assert error == ""
            mock_validate_token_func.assert_called_once_with("valid_token")

    @pytest.mark.asyncio
    async def test_authenticate_bearer_token_with_preferred_username(self, auth_middleware):
        """Test bearer token authentication using preferred_username field."""

        def mock_validate_token(token):
            return {"preferred_username": "preferred@example.com", "exp": 9999999999}

        with patch("mlflow_oidc_auth.middleware.auth_middleware.validate_token", mock_validate_token):
            auth_header = "Bearer valid_token"

            success, username, error = await auth_middleware._authenticate_bearer_token(auth_header)

            assert success is True
            assert username == "preferred@example.com"
            assert error == ""

    @pytest.mark.asyncio
    async def test_authenticate_bearer_token_invalid_payload(self, auth_middleware, mock_validate_token):
        """Test bearer token authentication with invalid payload (no email/username)."""
        with patch("mlflow_oidc_auth.middleware.auth_middleware.validate_token", mock_validate_token):
            auth_header = "Bearer invalid_payload_token"

            success, username, error = await auth_middleware._authenticate_bearer_token(auth_header)

            assert success is False
            assert username is None
            assert error == "Invalid token payload"

    @pytest.mark.asyncio
    async def test_authenticate_bearer_token_invalid_token(self, auth_middleware, mock_validate_token):
        """Test bearer token authentication with invalid token."""
        with patch("mlflow_oidc_auth.middleware.auth_middleware.validate_token", mock_validate_token):
            auth_header = "Bearer invalid_token"

            success, username, error = await auth_middleware._authenticate_bearer_token(auth_header)

            assert success is False
            assert username is None
            assert error == "Invalid token"

    @pytest.mark.asyncio
    async def test_authenticate_bearer_token_validation_exception(self, auth_middleware):
        """Test bearer token authentication when validation raises exception."""

        def mock_validate_token(token):
            raise ValueError("Token validation failed")

        with patch("mlflow_oidc_auth.middleware.auth_middleware.validate_token", mock_validate_token):
            auth_header = "Bearer some_token"

            success, username, error = await auth_middleware._authenticate_bearer_token(auth_header)

            assert success is False
            assert username is None
            assert error == "Invalid token"

    @pytest.mark.asyncio
    async def test_authenticate_session_success(self, auth_middleware, create_mock_request):
        """Test successful session authentication."""
        request = create_mock_request(session={"username": "user@example.com"})

        success, username, error = await auth_middleware._authenticate_session(request)

        assert success is True
        assert username == "user@example.com"
        assert error == ""

    @pytest.mark.asyncio
    async def test_authenticate_session_no_username(self, auth_middleware, create_mock_request):
        """Test session authentication with no username in session."""
        request = create_mock_request(session={})

        success, username, error = await auth_middleware._authenticate_session(request)

        assert success is False
        assert username is None
        assert error == "No session authentication"

    @pytest.mark.asyncio
    async def test_authenticate_session_no_session_middleware(self, auth_middleware, create_mock_request):
        """Test session authentication when session middleware is not available."""
        request = create_mock_request(has_session_middleware=False)

        success, username, error = await auth_middleware._authenticate_session(request)

        assert success is False
        assert username is None
        assert "SessionMiddleware must be installed to access request.session" in error

    @pytest.mark.asyncio
    async def test_authenticate_session_access_error(self, auth_middleware, create_mock_request):
        """Test session authentication when session access raises exception."""
        request = create_mock_request()

        # Mock session property to raise exception
        def mock_session_property(self):
            raise RuntimeError("Session access failed")

        # Replace the session property with one that raises an exception
        # Save original so we can restore it after the test to avoid
        # impacting other tests which rely on the normal MockRequest.session
        original_session_prop = getattr(request.__class__, "session", None)
        try:
            request.__class__.session = property(mock_session_property)

            success, username, error = await auth_middleware._authenticate_session(request)

            assert success is False
            assert username is None
            assert "Session access failed" in error
        finally:
            # Restore original session descriptor/property
            if original_session_prop is not None:
                request.__class__.session = original_session_prop
            else:
                delattr(request.__class__, "session")

    @pytest.mark.asyncio
    async def test_authenticate_user_basic_auth_priority(self, auth_middleware, create_mock_request, mock_store):
        """Test that basic auth takes priority over other methods."""
        with patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store):
            request = create_mock_request(
                headers={"authorization": "Basic YWRtaW5AZXhhbXBsZS5jb206YWRtaW5fcGFzcw=="}, session={"username": "session_user@example.com"}
            )

            success, username, error = await auth_middleware._authenticate_user(request)

            assert success is True
            assert username == "admin@example.com"  # From basic auth, not session

    @pytest.mark.asyncio
    async def test_authenticate_user_bearer_auth_priority(self, auth_middleware, create_mock_request, mock_validate_token):
        """Test that bearer auth takes priority over session."""
        with patch("mlflow_oidc_auth.middleware.auth_middleware.validate_token", mock_validate_token):
            request = create_mock_request(headers={"authorization": "Bearer valid_token"}, session={"username": "session_user@example.com"})

            success, username, error = await auth_middleware._authenticate_user(request)

            assert success is True
            assert username == "user@example.com"  # From bearer token, not session

    @pytest.mark.asyncio
    async def test_authenticate_user_session_fallback(self, auth_middleware, create_mock_request):
        """Test that session auth is used when no header auth is present."""
        request = create_mock_request(session={"username": "session_user@example.com"})

        success, username, error = await auth_middleware._authenticate_user(request)

        assert success is True
        assert username == "session_user@example.com"
        assert error == ""

    @pytest.mark.asyncio
    async def test_authenticate_user_all_methods_fail(self, auth_middleware, create_mock_request):
        """Test authentication when all methods fail."""
        request = create_mock_request(session={})

        success, username, error = await auth_middleware._authenticate_user(request)

        assert success is False
        assert username is None
        assert error == "No session authentication"

    def test_get_user_admin_status_admin_user(self, auth_middleware, mock_store):
        """Test admin status check for admin user."""
        with patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store):
            is_admin = auth_middleware._get_user_admin_status("admin@example.com")

            assert is_admin is True
            mock_store.get_user.assert_called_once_with("admin@example.com")

    def test_get_user_admin_status_regular_user(self, auth_middleware, mock_store):
        """Test admin status check for regular user."""
        with patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store):
            is_admin = auth_middleware._get_user_admin_status("user@example.com")

            assert is_admin is False
            mock_store.get_user.assert_called_once_with("user@example.com")

    def test_get_user_admin_status_nonexistent_user(self, auth_middleware, mock_store):
        """Test admin status check for nonexistent user."""
        with patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store):
            is_admin = auth_middleware._get_user_admin_status("nonexistent@example.com")

            assert is_admin is False
            mock_store.get_user.assert_called_once_with("nonexistent@example.com")

    def test_get_user_admin_status_store_exception(self, auth_middleware, mock_store):
        """Test admin status check when store raises exception."""
        mock_store.get_user.side_effect = Exception("Database error")

        with patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store):
            is_admin = auth_middleware._get_user_admin_status("user@example.com")

            assert is_admin is False

    @pytest.mark.asyncio
    async def test_handle_auth_redirect_automatic_login(self, auth_middleware, create_mock_request, mock_config):
        """Test authentication redirect with automatic login enabled."""
        mock_config.AUTOMATIC_LOGIN_REDIRECT = True

        with patch("mlflow_oidc_auth.middleware.auth_middleware.config", mock_config):
            request = create_mock_request()

            response = await auth_middleware._handle_auth_redirect(request)

            assert isinstance(response, RedirectResponse)
            assert response.status_code == 302
            assert response.headers["location"] == "/login"

    @pytest.mark.asyncio
    async def test_handle_auth_redirect_no_automatic_login(self, auth_middleware, create_mock_request, mock_config):
        """Test authentication redirect with automatic login disabled."""
        mock_config.AUTOMATIC_LOGIN_REDIRECT = False

        with patch("mlflow_oidc_auth.middleware.auth_middleware.config", mock_config):
            request = create_mock_request()

            response = await auth_middleware._handle_auth_redirect(request)

            assert isinstance(response, RedirectResponse)
            assert response.status_code == 302
            assert response.headers["location"] == "/oidc/ui"

    @pytest.mark.asyncio
    async def test_dispatch_unprotected_route(self, auth_middleware, create_mock_request):
        """Test dispatch for unprotected routes bypasses authentication."""
        request = create_mock_request(path="/health")

        # Mock call_next
        async def mock_call_next(req):
            return Response(content="OK", status_code=200)

        response = await auth_middleware.dispatch(request, mock_call_next)

        assert response.status_code == 200
        assert response.body == b"OK"
        # Verify no authentication state was set
        assert not hasattr(request.state, "username")
        assert not hasattr(request.state, "is_admin")

    @pytest.mark.asyncio
    async def test_dispatch_authenticated_user(self, auth_middleware, create_mock_request, mock_store):
        """Test dispatch for authenticated user sets request state correctly."""
        with patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store):
            request = create_mock_request(path="/protected", session={"username": "user@example.com"})

            # Mock call_next
            async def mock_call_next(req):
                return Response(content="Protected content", status_code=200)

            response = await auth_middleware.dispatch(request, mock_call_next)

            assert response.status_code == 200
            assert response.body == b"Protected content"

            # Verify authentication state was set
            assert request.state.username == "user@example.com"
            assert request.state.is_admin is False

            # Verify ASGI scope was updated for WSGI compatibility
            assert "mlflow_oidc_auth" in request.scope
            assert request.scope["mlflow_oidc_auth"]["username"] == "user@example.com"
            assert request.scope["mlflow_oidc_auth"]["is_admin"] is False

    @pytest.mark.asyncio
    async def test_dispatch_authenticated_admin(self, auth_middleware, create_mock_request, mock_store):
        """Test dispatch for authenticated admin user sets admin status correctly."""
        with patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store):
            request = create_mock_request(path="/protected", session={"username": "admin@example.com"})

            # Mock call_next
            async def mock_call_next(req):
                return Response(content="Admin content", status_code=200)

            response = await auth_middleware.dispatch(request, mock_call_next)

            assert response.status_code == 200
            assert response.body == b"Admin content"

            # Verify authentication state was set
            assert request.state.username == "admin@example.com"
            assert request.state.is_admin is True

            # Verify ASGI scope was updated for WSGI compatibility
            assert "mlflow_oidc_auth" in request.scope
            assert request.scope["mlflow_oidc_auth"]["username"] == "admin@example.com"
            assert request.scope["mlflow_oidc_auth"]["is_admin"] is True

    @pytest.mark.asyncio
    async def test_dispatch_unauthenticated_user_automatic_redirect(self, auth_middleware, create_mock_request, mock_config):
        """Test dispatch for unauthenticated user with automatic login redirect."""
        mock_config.AUTOMATIC_LOGIN_REDIRECT = True

        with patch("mlflow_oidc_auth.middleware.auth_middleware.config", mock_config):
            request = create_mock_request(path="/protected", session={})

            # Mock call_next (should not be called)
            async def mock_call_next(req):
                pytest.fail("call_next should not be called for unauthenticated user")

            response = await auth_middleware.dispatch(request, mock_call_next)

            assert isinstance(response, RedirectResponse)
            assert response.status_code == 302
            assert response.headers["location"] == "/login"

    @pytest.mark.asyncio
    async def test_dispatch_unauthenticated_user_oidc_ui_redirect(self, auth_middleware, create_mock_request, mock_config):
        """Test dispatch for unauthenticated user with OIDC UI redirect."""
        mock_config.AUTOMATIC_LOGIN_REDIRECT = False

        with patch("mlflow_oidc_auth.middleware.auth_middleware.config", mock_config):
            request = create_mock_request(path="/protected", session={})

            # Mock call_next (should not be called)
            async def mock_call_next(req):
                pytest.fail("call_next should not be called for unauthenticated user")

            response = await auth_middleware.dispatch(request, mock_call_next)

            assert isinstance(response, RedirectResponse)
            assert response.status_code == 302
            assert response.headers["location"] == "/oidc/ui"

    @pytest.mark.asyncio
    async def test_dispatch_basic_auth_header(self, auth_middleware, create_mock_request, mock_store):
        """Test dispatch with basic authentication header."""
        with patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store):
            request = create_mock_request(path="/protected", headers={"authorization": "Basic YWRtaW5AZXhhbXBsZS5jb206YWRtaW5fcGFzcw=="})

            # Mock call_next
            async def mock_call_next(req):
                return Response(content="Authenticated via basic auth", status_code=200)

            response = await auth_middleware.dispatch(request, mock_call_next)

            assert response.status_code == 200
            assert request.state.username == "admin@example.com"
            assert request.state.is_admin is True

    @pytest.mark.asyncio
    async def test_dispatch_bearer_token_header(self, auth_middleware, create_mock_request, mock_validate_token):
        """Test dispatch with bearer token authentication header."""
        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.validate_token", mock_validate_token),
            patch("mlflow_oidc_auth.middleware.auth_middleware.store") as mock_store,
        ):
            # Mock store for admin status check
            mock_user = MagicMock()
            mock_user.is_admin = False
            mock_store.get_user.return_value = mock_user
            mock_store.get_user_profile.return_value = mock_user

            request = create_mock_request(path="/protected", headers={"authorization": "Bearer valid_token"})

            # Mock call_next
            async def mock_call_next(req):
                return Response(content="Authenticated via bearer token", status_code=200)

            response = await auth_middleware.dispatch(request, mock_call_next)

            assert response.status_code == 200
            assert request.state.username == "user@example.com"
            assert request.state.is_admin is False

    @pytest.mark.asyncio
    async def test_dispatch_authentication_failure_logging(self, auth_middleware, create_mock_request, mock_logger):
        """Test that authentication failures are properly logged."""
        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.logger", mock_logger),
            patch("mlflow_oidc_auth.middleware.auth_middleware.config") as mock_config,
        ):
            mock_config.AUTOMATIC_LOGIN_REDIRECT = True

            request = create_mock_request(path="/protected", session={})

            # Mock call_next (should not be called)
            async def mock_call_next(req):
                pytest.fail("call_next should not be called for unauthenticated user")

            await auth_middleware.dispatch(request, mock_call_next)

            # Verify logging was called
            mock_logger.info.assert_called_once()
            log_call_args = mock_logger.info.call_args[0][0]
            assert "Authentication failed for /protected" in log_call_args
            assert "No session authentication" in log_call_args

    @pytest.mark.asyncio
    async def test_dispatch_successful_authentication_logging(self, auth_middleware, create_mock_request, mock_store, mock_logger):
        """Test that successful authentication is properly logged."""
        with patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store), patch("mlflow_oidc_auth.middleware.auth_middleware.logger", mock_logger):
            request = create_mock_request(path="/protected", session={"username": "user@example.com"})

            # Mock call_next
            async def mock_call_next(req):
                return Response(content="OK", status_code=200)

            await auth_middleware.dispatch(request, mock_call_next)

            # Verify debug logging was called at least once and contains the expected message
            assert mock_logger.debug.call_count >= 1
            # Collect all debug log messages and ensure one contains the expected substring
            debug_messages = [c.args[0] for c in mock_logger.debug.call_args_list]
            assert any("User user@example.com (admin: False) accessing /protected" in msg for msg in debug_messages)

    @pytest.mark.asyncio
    async def test_dispatch_multiple_unprotected_routes(self, auth_middleware, create_mock_request):
        """Test dispatch handles multiple unprotected route patterns correctly."""
        unprotected_paths = [
            "/health",
            "/health/check",
            "/login",
            "/login/oauth",
            "/callback",
            "/callback/oauth",
            "/oidc/static/css/style.css",
            "/oidc/static/js/app.js",
            "/metrics",
            "/metrics/prometheus",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/oidc/ui",
            "/oidc/ui/admin",
        ]

        for path in unprotected_paths:
            request = create_mock_request(path=path)

            # Mock call_next
            async def mock_call_next(req):
                return Response(content=f"OK for {path}", status_code=200)

            response = await auth_middleware.dispatch(request, mock_call_next)

            assert response.status_code == 200
            # Verify no authentication state was set
            assert not hasattr(request.state, "username")
            assert not hasattr(request.state, "is_admin")

    @pytest.mark.asyncio
    async def test_dispatch_case_sensitivity(self, auth_middleware, create_mock_request):
        """Test that route protection is case sensitive."""
        # Uppercase paths should be protected (case sensitive)
        request = create_mock_request(path="/HEALTH")

        # Mock call_next (should not be called for protected route without auth)
        async def mock_call_next(req):
            pytest.fail("call_next should not be called for protected route without auth")

        with patch("mlflow_oidc_auth.middleware.auth_middleware.config") as mock_config:
            mock_config.AUTOMATIC_LOGIN_REDIRECT = True

            response = await auth_middleware.dispatch(request, mock_call_next)

            assert isinstance(response, RedirectResponse)
            assert response.status_code == 302

    @pytest.mark.asyncio
    async def test_dispatch_request_state_isolation(self, auth_middleware, create_mock_request, mock_store):
        """Test that request state is properly isolated between requests."""
        with patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store):
            # First request
            request1 = create_mock_request(path="/protected", session={"username": "user@example.com"})

            # Mock call_next
            async def mock_call_next(req):
                return Response(content="OK", status_code=200)

            await auth_middleware.dispatch(request1, mock_call_next)

            # Second request with different user
            request2 = create_mock_request(path="/protected", session={"username": "admin@example.com"})

            await auth_middleware.dispatch(request2, mock_call_next)

            # Verify each request has correct isolated state
            assert request1.state.username == "user@example.com"
            assert request1.state.is_admin is False

            assert request2.state.username == "admin@example.com"
            assert request2.state.is_admin is True

    @pytest.mark.asyncio
    async def test_dispatch_asgi_scope_injection(self, auth_middleware, create_mock_request, mock_store):
        """Test that ASGI scope is properly injected for WSGI compatibility."""
        with patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store):
            request = create_mock_request(path="/protected", session={"username": "admin@example.com"})

            # Verify scope doesn't have auth info initially
            assert "mlflow_oidc_auth" not in request.scope

            # Mock call_next
            async def mock_call_next(req):
                # Verify scope has auth info during request processing
                assert "mlflow_oidc_auth" in req.scope
                assert req.scope["mlflow_oidc_auth"]["username"] == "admin@example.com"
                assert req.scope["mlflow_oidc_auth"]["is_admin"] is True
                return Response(content="OK", status_code=200)

            await auth_middleware.dispatch(request, mock_call_next)

            # Verify scope still has auth info after processing
            assert "mlflow_oidc_auth" in request.scope
            assert request.scope["mlflow_oidc_auth"]["username"] == "admin@example.com"
            assert request.scope["mlflow_oidc_auth"]["is_admin"] is True

    @pytest.mark.asyncio
    async def test_authenticate_session_no_session_attribute(self, auth_middleware):
        """Test session authentication when request has no session attribute."""

        # Create a request without session attribute
        class RequestWithoutSession:
            pass

        request = RequestWithoutSession()

        success, username, error = await auth_middleware._authenticate_session(request)

        assert success is False
        assert username is None
        assert error == "Session middleware not available"

    @pytest.mark.asyncio
    async def test_authenticate_session_outer_exception(self, auth_middleware):
        """Test session authentication when outer try block raises exception."""

        # Create a request that raises exception when accessing hasattr
        class BadRequest:
            def __getattribute__(self, name):
                if name == "session":
                    raise RuntimeError("Outer exception")
                return super().__getattribute__(name)

        request = BadRequest()

        success, username, error = await auth_middleware._authenticate_session(request)

        assert success is False
        assert username is None
        assert "Session error: Outer exception" in error

    @pytest.mark.asyncio
    async def test_authenticate_session_inner_exception(self, auth_middleware):
        """Test session authentication when session access raises exception inside try block."""

        # Create a request that has session attribute but raises exception when accessed
        class RequestWithBadSession:
            @property
            def session(self):
                raise RuntimeError("Session access failed")

        request = RequestWithBadSession()

        success, username, error = await auth_middleware._authenticate_session(request)

        assert success is False
        assert username is None
        assert "Session error: Session access failed" in error

    @pytest.mark.asyncio
    async def test_authenticate_session_session_get_exception(self, auth_middleware):
        """Test session authentication when session.get() raises exception."""

        # Create a request with session that raises exception on get()
        class RequestWithBadSessionGet:
            @property
            def session(self):
                class BadSession:
                    def get(self, key):
                        raise RuntimeError("Session get failed")

                return BadSession()

        request = RequestWithBadSessionGet()

        success, username, error = await auth_middleware._authenticate_session(request)

        assert success is False
        assert username is None
        assert "Session access failed: Session get failed" in error
