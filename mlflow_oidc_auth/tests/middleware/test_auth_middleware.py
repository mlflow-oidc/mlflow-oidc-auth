"""
Comprehensive tests for AuthMiddleware.

This module tests authentication middleware behavior including:
- Authentication method handling (basic, bearer, session)
- Route protection and unprotected route handling
- User context setting and admin status checking
- Error handling and authentication failures
- ASGI scope injection for WSGI compatibility
"""

import threading

import pytest
from unittest.mock import MagicMock, patch
from fastapi import Response
from fastapi.responses import RedirectResponse

from mlflow_oidc_auth.middleware import auth_middleware as middleware_module
from mlflow_oidc_auth.middleware.auth_middleware import AuthMiddleware


class TestAuthMiddleware:
    """Test suite for AuthMiddleware functionality."""

    @pytest.fixture(autouse=True)
    def _default_store(self, mock_store, monkeypatch):
        """Point the middleware at the mock store by default.

        Session authentication resolves the cookie's opaque id through the store (#310), so a
        test that does not patch it would otherwise reach the real lazy singleton and try to
        open a database. Tests that patch the store explicitly still win inside their own
        ``with`` block.
        """
        monkeypatch.setattr("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store)

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

    def test_is_unprotected_route_mlflow_static_files(self, auth_middleware):
        """MLflow's hashed bundle assets must load even without a valid session."""
        assert auth_middleware._is_unprotected_route("/static-files/static/js/9605.46a42772.chunk.js") is True
        assert auth_middleware._is_unprotected_route("/static-files/static/css/main.css") is True
        assert auth_middleware._is_unprotected_route("/static-files/static/media/default-error.svg") is True

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
    async def test_authenticate_basic_auth_offloads_store_lookup(self, auth_middleware, mock_store):
        """The synchronous database/hash path must run on the worker thread, not the event loop."""
        verifying_threads = []

        def record_thread(username, password):
            verifying_threads.append(threading.current_thread())
            return True

        mock_store.authenticate_user.side_effect = record_thread
        with patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store):
            auth_header = "Basic YWRtaW5AZXhhbXBsZS5jb206YWRtaW5fcGFzcw=="

            success, username, error = await auth_middleware._authenticate_basic_auth(auth_header)

        assert success is True
        assert username == "admin@example.com"
        assert error == ""
        mock_store.authenticate_user.assert_called_once_with("admin@example.com", "admin_pass")
        assert len(verifying_threads) == 1
        assert verifying_threads[0] is not threading.current_thread()
        assert verifying_threads[0].name.startswith("mlflow-oidc-basic-auth")
        # max_workers=1 is the security bound: one credential verification per process at a time.
        assert middleware_module._BASIC_AUTH_EXECUTOR._max_workers == 1

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

        with patch(
            "mlflow_oidc_auth.middleware.auth_middleware.validate_token",
            mock_validate_token_func,
        ):
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

        with patch(
            "mlflow_oidc_auth.middleware.auth_middleware.validate_token",
            mock_validate_token,
        ):
            auth_header = "Bearer valid_token"

            success, username, error = await auth_middleware._authenticate_bearer_token(auth_header)

            assert success is True
            assert username == "preferred@example.com"
            assert error == ""

    @pytest.mark.asyncio
    async def test_authenticate_bearer_token_invalid_payload(self, auth_middleware, mock_validate_token):
        """Test bearer token authentication with invalid payload (no email/username)."""
        with patch(
            "mlflow_oidc_auth.middleware.auth_middleware.validate_token",
            mock_validate_token,
        ):
            auth_header = "Bearer invalid_payload_token"

            success, username, error = await auth_middleware._authenticate_bearer_token(auth_header)

            assert success is False
            assert username is None
            assert error == "No username provided in bearer token payload"

    @pytest.mark.asyncio
    async def test_authenticate_bearer_token_invalid_token(self, auth_middleware, mock_validate_token):
        """Test bearer token authentication with invalid token."""
        with patch(
            "mlflow_oidc_auth.middleware.auth_middleware.validate_token",
            mock_validate_token,
        ):
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

        with patch(
            "mlflow_oidc_auth.middleware.auth_middleware.validate_token",
            mock_validate_token,
        ):
            auth_header = "Bearer some_token"

            success, username, error = await auth_middleware._authenticate_bearer_token(auth_header)

            assert success is False
            assert username is None
            assert error == "Invalid token"

    @pytest.mark.asyncio
    async def test_authenticate_session_success(self, auth_middleware, create_mock_request):
        """Test successful session authentication."""
        request = create_mock_request(session={"session_id": "sid-user"})

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
        assert error == "Session error"

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
            assert error == "Session error"
        finally:
            # Restore original session descriptor/property
            if original_session_prop is not None:
                request.__class__.session = original_session_prop
            else:
                delattr(request.__class__, "session")

    @staticmethod
    def _resolved_with(tokens=None, blob=None):
        """A resolved session whose row carries ``tokens`` (encrypted) or a raw ``blob`` (#367)."""
        from mlflow_oidc_auth.repository.auth_session import ResolvedSession
        from mlflow_oidc_auth.session.token_vault import get_token_vault

        if tokens is not None:
            blob = get_token_vault().encrypt(tokens)
        return ResolvedSession(username="user@example.com", is_admin=False, is_active=True, session_id="sid-user", encrypted_tokens=blob)

    async def _authenticate(self, auth_middleware, create_mock_request, session, resolved, refresh=None):
        from unittest.mock import AsyncMock, patch as _patch

        from mlflow_oidc_auth.middleware import auth_middleware as middleware_mod

        refresh = refresh if refresh is not None else AsyncMock(return_value=False)
        with (
            _patch.object(middleware_mod, "store") as store_mock,
            _patch("mlflow_oidc_auth.routers.auth.refresh_session_with_idp", new=refresh),
            _patch.object(middleware_mod.config, "OIDC_SESSION_EXPIRY_LEEWAY_SECONDS", 0, create=True),
        ):
            store_mock.resolve_auth_session.return_value = resolved
            request = create_mock_request(session=session)
            result = await auth_middleware._authenticate_session(request)
        return result, refresh

    @pytest.mark.asyncio
    async def test_authenticate_session_unexpired_passes_through(self, auth_middleware, create_mock_request):
        """A session whose row holds a future IdP expiry is allowed without touching the IdP."""
        from mlflow_oidc_auth.session.token_vault import SessionTokens

        (success, username, error), refresh = await self._authenticate(
            auth_middleware, create_mock_request, {"session_id": "sid-user"}, self._resolved_with(SessionTokens(expires_at=9999999999))
        )

        assert (success, username, error) == (True, "user@example.com", "")
        refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_authenticate_session_expired_no_refresh_token_clears(self, auth_middleware, create_mock_request):
        """Expired sessions that cannot be refreshed are cleared and rejected."""
        from mlflow_oidc_auth.session.token_vault import SessionTokens

        session = {"session_id": "sid-user", "authenticated": True}
        resolved = self._resolved_with(SessionTokens(expires_at=100))
        (success, username, error), refresh = await self._authenticate(auth_middleware, create_mock_request, session, resolved)

        assert (success, username, error) == (False, None, "Session expired")
        assert session == {}  # session.clear() was called
        refresh.assert_awaited_once_with("sid-user", resolved)

    @pytest.mark.asyncio
    async def test_authenticate_session_expired_refresh_succeeds(self, auth_middleware, create_mock_request):
        """When refresh succeeds the session is accepted, and nothing token-shaped enters the cookie."""
        from unittest.mock import AsyncMock

        from mlflow_oidc_auth.session.token_vault import SessionTokens

        session = {"session_id": "sid-user"}
        resolved = self._resolved_with(SessionTokens(expires_at=100, refresh_token="rt-123"))
        (success, username, error), refresh = await self._authenticate(
            auth_middleware, create_mock_request, session, resolved, refresh=AsyncMock(return_value=True)
        )

        assert (success, username, error) == (True, "user@example.com", "")
        refresh.assert_awaited_once_with("sid-user", resolved)
        assert session == {"session_id": "sid-user"}

    @pytest.mark.asyncio
    async def test_authenticate_session_no_expires_at_unchanged(self, auth_middleware, create_mock_request):
        """A row with no IdP expiry (or no tokens at all) keeps working."""
        from mlflow_oidc_auth.session.token_vault import SessionTokens

        for resolved in (self._resolved_with(), self._resolved_with(SessionTokens(refresh_token="rt"))):
            (success, username, _), refresh = await self._authenticate(auth_middleware, create_mock_request, {"session_id": "sid-user"}, resolved)
            assert success is True
            assert username == "user@example.com"
            refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_authenticate_session_ignores_and_cleans_legacy_cookie_expiry(self, auth_middleware, create_mock_request):
        """A pre-#367 cookie's ``expires_at``/``refresh_token`` is neither trusted nor kept.

        Here the cookie claims a far-future expiry while the row says expired: the row wins.
        """
        from mlflow_oidc_auth.session.token_vault import SessionTokens

        session = {"session_id": "sid-user", "expires_at": 9999999999, "refresh_token": "rt-from-cookie"}
        resolved = self._resolved_with(SessionTokens(expires_at=100))
        (success, _, error), refresh = await self._authenticate(auth_middleware, create_mock_request, session, resolved)

        assert (success, error) == (False, "Session expired")
        refresh.assert_awaited_once_with("sid-user", resolved)
        assert "refresh_token" not in session and "expires_at" not in session

    @pytest.mark.asyncio
    async def test_legacy_cookie_expiry_bounds_a_tokenless_row_when_past(self, auth_middleware, create_mock_request):
        """A row opened before #367 has no tokens; the signed cookie's expiry is its only IdP bound.
        Once past, the session ends — there is nothing on the row to refresh with."""
        session = {"session_id": "sid-user", "expires_at": 100, "refresh_token": "rt-from-cookie"}
        (success, _, error), refresh = await self._authenticate(auth_middleware, create_mock_request, session, self._resolved_with())

        assert (success, error) == (False, "Session expired")
        assert session == {}
        refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_legacy_cookie_expiry_is_kept_while_in_the_future(self, auth_middleware, create_mock_request):
        """Still in the future: accepted, the refresh token dropped, the bound kept for next time."""
        session = {"session_id": "sid-user", "expires_at": 9999999999, "refresh_token": "rt-from-cookie"}
        (success, _, _), refresh = await self._authenticate(auth_middleware, create_mock_request, session, self._resolved_with())

        assert success is True
        refresh.assert_not_called()
        assert session == {"session_id": "sid-user", "expires_at": 9999999999}

    @pytest.mark.asyncio
    async def test_non_numeric_legacy_expiry_is_dropped(self, auth_middleware, create_mock_request):
        session = {"session_id": "sid-user", "expires_at": "never"}
        (success, _, _), _ = await self._authenticate(auth_middleware, create_mock_request, session, self._resolved_with())

        assert success is True
        assert session == {"session_id": "sid-user"}

    @pytest.mark.asyncio
    async def test_authenticate_session_undecryptable_tokens_fail_closed(self, auth_middleware, create_mock_request):
        """Tokens that exist but cannot be read (key rotated, tampering) do not keep a session alive."""
        session = {"session_id": "sid-user"}
        (success, _, error), _ = await self._authenticate(auth_middleware, create_mock_request, session, self._resolved_with(blob="gAAAA-tampered"))

        assert (success, error) == (False, "Session expired")
        assert session == {}

    def test_is_session_expired_reads_session_tokens(self):
        from mlflow_oidc_auth.middleware.auth_middleware import AuthMiddleware
        from mlflow_oidc_auth.session.token_vault import SessionTokens

        assert AuthMiddleware._is_session_expired(None) is False
        assert AuthMiddleware._is_session_expired(SessionTokens()) is False
        assert AuthMiddleware._is_session_expired(SessionTokens(expires_at=100)) is True
        assert AuthMiddleware._is_session_expired(SessionTokens(expires_at=9999999999)) is False

    @pytest.mark.asyncio
    async def test_authenticate_user_basic_auth_priority(self, auth_middleware, create_mock_request, mock_store):
        """Test that basic auth takes priority over other methods."""
        with patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store):
            request = create_mock_request(
                headers={"authorization": "Basic YWRtaW5AZXhhbXBsZS5jb206YWRtaW5fcGFzcw=="},
                session={"username": "session_user@example.com"},
            )

            success, username, error = await auth_middleware._authenticate_user(request)

            assert success is True
            assert username == "admin@example.com"  # From basic auth, not session

    @pytest.mark.asyncio
    async def test_authenticate_user_bearer_auth_priority(self, auth_middleware, create_mock_request, mock_validate_token):
        """Test that bearer auth takes priority over session."""
        with patch(
            "mlflow_oidc_auth.middleware.auth_middleware.validate_token",
            mock_validate_token,
        ):
            request = create_mock_request(
                headers={"authorization": "Bearer valid_token"},
                session={"username": "session_user@example.com"},
            )

            success, username, error = await auth_middleware._authenticate_user(request)

            assert success is True
            assert username == "user@example.com"  # From bearer token, not session

    @pytest.mark.asyncio
    async def test_authenticate_user_session_fallback(self, auth_middleware, create_mock_request):
        """Test that session auth is used when no header auth is present."""
        request = create_mock_request(session={"session_id": "sid-user"})

        success, username, error = await auth_middleware._authenticate_user(request)

        assert success is True
        assert username == "user@example.com"
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
        """Test authentication redirect with automatic login enabled.

        Includes the ``?next=<original-path>`` round-trip so the user lands
        back on the page they tried to load instead of the root.
        """
        mock_config.AUTOMATIC_LOGIN_REDIRECT = True

        with patch("mlflow_oidc_auth.middleware.auth_middleware.config", mock_config):
            request = create_mock_request(path="/protected")

            response = await auth_middleware._handle_auth_redirect(request)

            assert isinstance(response, RedirectResponse)
            assert response.status_code == 302
            assert response.headers["location"] == "/login?next=%2Fprotected"

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
            request = create_mock_request(path="/protected", session={"session_id": "sid-user"})

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
            assert request.scope["mlflow_oidc_auth"].username == "user@example.com"
            assert request.scope["mlflow_oidc_auth"].is_admin is False

    @pytest.mark.asyncio
    async def test_dispatch_authenticated_admin(self, auth_middleware, create_mock_request, mock_store):
        """Test dispatch for authenticated admin user sets admin status correctly."""
        with patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store):
            request = create_mock_request(path="/protected", session={"session_id": "sid-admin"})

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
            assert request.scope["mlflow_oidc_auth"].username == "admin@example.com"
            assert request.scope["mlflow_oidc_auth"].is_admin is True

    @pytest.mark.asyncio
    async def test_dispatch_unauthenticated_user_automatic_redirect(self, auth_middleware, create_mock_request, mock_config):
        """Document navigation requests redirect to login when auto-redirect is enabled."""
        mock_config.AUTOMATIC_LOGIN_REDIRECT = True

        with patch("mlflow_oidc_auth.middleware.auth_middleware.config", mock_config):
            request = create_mock_request(
                path="/protected",
                session={},
                headers={"sec-fetch-dest": "document"},
            )

            async def mock_call_next(req):
                pytest.fail("call_next should not be called for unauthenticated user")

            response = await auth_middleware.dispatch(request, mock_call_next)

            assert isinstance(response, RedirectResponse)
            assert response.status_code == 302
            assert response.headers["location"] == "/login?next=%2Fprotected"

    @pytest.mark.asyncio
    async def test_dispatch_unauthenticated_user_oidc_ui_redirect(self, auth_middleware, create_mock_request, mock_config):
        """Document navigation requests redirect to the UI when auto-redirect is disabled."""
        mock_config.AUTOMATIC_LOGIN_REDIRECT = False

        with patch("mlflow_oidc_auth.middleware.auth_middleware.config", mock_config):
            request = create_mock_request(
                path="/protected",
                session={},
                headers={"sec-fetch-dest": "document"},
            )

            async def mock_call_next(req):
                pytest.fail("call_next should not be called for unauthenticated user")

            response = await auth_middleware.dispatch(request, mock_call_next)

            assert isinstance(response, RedirectResponse)
            assert response.status_code == 302
            assert response.headers["location"] == "/oidc/ui"

    @pytest.mark.asyncio
    async def test_dispatch_unauthenticated_user_preserves_query_string_in_next(self, auth_middleware, create_mock_request, mock_config):
        """Query string is forwarded as part of ?next= so deep links survive re-auth."""
        mock_config.AUTOMATIC_LOGIN_REDIRECT = True

        with patch("mlflow_oidc_auth.middleware.auth_middleware.config", mock_config):
            request = create_mock_request(
                path="/protected",
                session={},
                headers={"sec-fetch-dest": "document"},
            )
            request.url.query = "tab=runs&id=42"

            response = await auth_middleware.dispatch(request, lambda r: pytest.fail("nope"))

            assert isinstance(response, RedirectResponse)
            assert response.headers["location"] == "/login?next=%2Fprotected%3Ftab%3Druns%26id%3D42"

    @pytest.mark.asyncio
    async def test_dispatch_unauthenticated_subresource_returns_401(self, auth_middleware, create_mock_request, mock_config):
        """Subresource fetches (chunks, fetch/XHR) get 401 instead of a 302 → HTML.

        Otherwise the browser silently follows the redirect and the JS chunk
        loader / JSON.parse receives HTML and throws — that's the regression
        that broke the SPA mid-session once IdP-issued expiry kicked in.
        """
        mock_config.AUTOMATIC_LOGIN_REDIRECT = True

        with patch("mlflow_oidc_auth.middleware.auth_middleware.config", mock_config):
            # Browser script fetch — Sec-Fetch-Dest is the modern signal.
            # Use a protected path; /static-files/* is unprotected by design.
            request = create_mock_request(
                path="/some-app-route/data.js",
                session={},
                headers={"sec-fetch-dest": "script"},
            )

            response = await auth_middleware.dispatch(request, lambda r: pytest.fail("should not be called"))

            assert response.status_code == 401
            assert b"Authentication required" in response.body

    @pytest.mark.asyncio
    @pytest.mark.parametrize("prefix", ["/api", "/ajax-api"])
    async def test_dispatch_unauthenticated_rest_path_returns_401(self, prefix, auth_middleware, create_mock_request, mock_config):
        """Both REST prefixes are API surfaces and must 401 rather than redirect.

        The plugin serves its endpoints under "/ajax-api" too (that's the prefix
        MLflow's UI calls), so an unauthenticated call there must not be handed
        a 302 to the login page.
        """
        mock_config.AUTOMATIC_LOGIN_REDIRECT = True

        with patch("mlflow_oidc_auth.middleware.auth_middleware.config", mock_config):
            request = create_mock_request(
                path=f"{prefix}/2.0/mlflow/users/current",
                session={},
                headers={"sec-fetch-dest": "document"},
            )

            response = await auth_middleware.dispatch(request, lambda r: pytest.fail("should not be called"))

            assert response.status_code == 401
            assert b"Authentication required" in response.body

    @pytest.mark.asyncio
    async def test_dispatch_unauthenticated_xhr_returns_401_via_accept_fallback(self, auth_middleware, create_mock_request, mock_config):
        """Older clients without Sec-Fetch-Dest fall back to the Accept header."""
        mock_config.AUTOMATIC_LOGIN_REDIRECT = True

        with patch("mlflow_oidc_auth.middleware.auth_middleware.config", mock_config):
            request = create_mock_request(
                path="/some-endpoint",
                session={},
                headers={"accept": "application/json"},
            )

            response = await auth_middleware.dispatch(request, lambda r: pytest.fail("should not be called"))

            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_dispatch_unauthenticated_html_accept_redirects(self, auth_middleware, create_mock_request, mock_config):
        """Without Sec-Fetch-Dest, an Accept: text/html header still redirects."""
        mock_config.AUTOMATIC_LOGIN_REDIRECT = True

        with patch("mlflow_oidc_auth.middleware.auth_middleware.config", mock_config):
            request = create_mock_request(
                path="/some-endpoint",
                session={},
                headers={"accept": "text/html,application/xhtml+xml"},
            )

            response = await auth_middleware.dispatch(request, lambda r: pytest.fail("should not be called"))

            assert isinstance(response, RedirectResponse)
            assert response.status_code == 302

    @pytest.mark.asyncio
    async def test_dispatch_basic_auth_header(self, auth_middleware, create_mock_request, mock_store):
        """Test dispatch with basic authentication header."""
        with patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store):
            request = create_mock_request(
                path="/protected",
                headers={"authorization": "Basic YWRtaW5AZXhhbXBsZS5jb206YWRtaW5fcGFzcw=="},
            )

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
            patch(
                "mlflow_oidc_auth.middleware.auth_middleware.validate_token",
                mock_validate_token,
            ),
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
        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store),
            patch("mlflow_oidc_auth.middleware.auth_middleware.logger", mock_logger),
        ):
            request = create_mock_request(path="/protected", session={"session_id": "sid-user"})

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
        request = create_mock_request(path="/HEALTH", headers={"sec-fetch-dest": "document"})

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
            request1 = create_mock_request(path="/protected", session={"session_id": "sid-user"})

            # Mock call_next
            async def mock_call_next(req):
                return Response(content="OK", status_code=200)

            await auth_middleware.dispatch(request1, mock_call_next)

            # Second request with different user
            request2 = create_mock_request(path="/protected", session={"session_id": "sid-admin"})

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
            request = create_mock_request(path="/protected", session={"session_id": "sid-admin"})

            # Verify scope doesn't have auth info initially
            assert "mlflow_oidc_auth" not in request.scope

            # Mock call_next
            async def mock_call_next(req):
                # Verify scope has auth info during request processing
                assert "mlflow_oidc_auth" in req.scope
                assert req.scope["mlflow_oidc_auth"].username == "admin@example.com"
                assert req.scope["mlflow_oidc_auth"].is_admin is True
                return Response(content="OK", status_code=200)

            await auth_middleware.dispatch(request, mock_call_next)

            # Verify scope still has auth info after processing
            assert "mlflow_oidc_auth" in request.scope
            assert request.scope["mlflow_oidc_auth"].username == "admin@example.com"
            assert request.scope["mlflow_oidc_auth"].is_admin is True

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
        assert error == "Session error"

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
        assert error == "Session error"

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
        assert error == "Session access failed"


class TestLoginRedirectSchemeRelative:
    """The login redirect must be scheme-relative so it can't downgrade https->http (#128).

    Behind a TLS-terminating proxy (e.g. Azure Application Gateway) the server sees the
    request as http. If the redirect Location were an absolute http:// URL the browser
    would be sent to http and the proxy would 404. Emitting a path-only Location makes the
    browser resolve it against the current (https) origin, so the scheme is preserved.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("automatic_login_redirect", [True, False])
    async def test_redirect_location_has_no_scheme(self, automatic_login_redirect):
        from unittest.mock import AsyncMock

        middleware = AuthMiddleware.__new__(AuthMiddleware)  # bypass __init__ (no app needed)

        fake_url = MagicMock(scheme="http", path="/some/page", query="a=1")
        request = MagicMock(url=fake_url, headers={}, scope={})

        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.config") as cfg,
            patch("mlflow_oidc_auth.utils.get_base_path", new=AsyncMock(return_value="")),
        ):
            cfg.AUTOMATIC_LOGIN_REDIRECT = automatic_login_redirect
            response = await middleware._handle_auth_redirect(request)

        location = response.headers["location"]
        assert not location.startswith("http://"), f"redirect downgraded to http: {location}"
        assert not location.startswith("https://"), f"redirect hardcoded a scheme: {location}"
        assert location.startswith("/"), f"redirect is not path-relative: {location}"

    @pytest.mark.asyncio
    async def test_redirect_honors_forwarded_prefix_without_scheme(self):
        """With a proxy path prefix the Location stays path-only (prefix + /login), still no scheme."""
        from unittest.mock import AsyncMock

        middleware = AuthMiddleware.__new__(AuthMiddleware)
        fake_url = MagicMock(scheme="http", path="/page", query="")
        request = MagicMock(url=fake_url, headers={}, scope={})

        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.config") as cfg,
            patch("mlflow_oidc_auth.utils.get_base_path", new=AsyncMock(return_value="/mlflow")),
        ):
            cfg.AUTOMATIC_LOGIN_REDIRECT = True
            response = await middleware._handle_auth_redirect(request)

        location = response.headers["location"]
        assert location.startswith("/mlflow/login")
        assert "http://" not in location and "https://" not in location
