"""
Comprehensive tests for the authentication router.

This module tests all authentication endpoints including login, logout, callback,
and auth status with various scenarios including success, failure, and edge cases.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from authlib.jose.errors import BadSignatureError
from fastapi import HTTPException
from fastapi.responses import JSONResponse, RedirectResponse

from mlflow_oidc_auth.routers.auth import (
    AUTH_STATUS,
    CALLBACK,
    LOGIN,
    LOGOUT,
    _build_ui_url,
    _extract_session_expiry,
    _persist_session_auth,
    _process_oidc_callback_fastapi,
    auth_router,
    auth_status,
    callback,
    login,
    logout,
    refresh_session_with_idp,
)


class TestAuthRouter:
    """Test class for authentication router endpoints."""

    def test_router_configuration(self):
        """Test that the auth router is properly configured."""
        assert auth_router.tags == ["auth"]
        assert 404 in auth_router.responses
        assert auth_router.responses[404]["description"] == "Not found"

    def test_route_constants(self):
        """Test that route constants are properly defined."""
        assert LOGIN == "/login"
        assert LOGOUT == "/logout"
        assert CALLBACK == "/callback"
        assert AUTH_STATUS == "/auth/status"


class TestBuildUIUrl:
    """Test the _build_ui_url helper function."""

    def test_build_ui_url_basic(self, mock_request_with_session):
        """Test building basic UI URL without query parameters."""
        request = mock_request_with_session()
        request.base_url = "http://localhost:8000"

        result = _build_ui_url(request, "/auth")

        assert result == "http://localhost:8000/oidc/ui/auth"

    def test_build_ui_url_with_query_params(self, mock_request_with_session):
        """Test building UI URL with query parameters."""
        request = mock_request_with_session()
        request.base_url = "http://localhost:8000/"

        result = _build_ui_url(request, "/auth", {"error": "test_error", "code": "123"})

        assert "http://localhost:8000/oidc/ui/auth?" in result
        assert "error=test_error" in result
        assert "code=123" in result

    def test_build_ui_url_trailing_slash_handling(self, mock_request_with_session):
        """Test that trailing slashes are handled correctly."""
        request = mock_request_with_session()
        request.base_url = "http://localhost:8000/"

        result = _build_ui_url(request, "/home")

        assert result == "http://localhost:8000/oidc/ui/home"


class TestLoginEndpoint:
    """Test the login endpoint functionality."""

    @pytest.mark.asyncio
    async def test_login_success(self, mock_request_with_session, mock_oauth, mock_config):
        """Test successful login initiation."""
        request = mock_request_with_session({"oauth_state": None})

        with (
            patch("mlflow_oidc_auth.routers.auth.oauth", mock_oauth),
            patch("mlflow_oidc_auth.routers.auth.config", mock_config),
            patch("mlflow_oidc_auth.routers.auth.get_configured_or_dynamic_redirect_uri") as mock_redirect,
            patch("secrets.token_urlsafe") as mock_token,
            patch("mlflow_oidc_auth.routers.auth.is_oidc_configured", return_value=True),
        ):
            mock_redirect.return_value = "http://localhost:8000/callback"
            mock_token.return_value = "test_state_token"

            await login(request)

            # Verify state was set in session
            assert request.session["oauth_state"] == "test_state_token"

            # Verify OAuth redirect was called
            mock_oauth.oidc.authorize_redirect.assert_called_once_with(
                request,
                redirect_uri="http://localhost:8000/callback",
                state="test_state_token",
            )

    @pytest.mark.asyncio
    async def test_login_captures_safe_next_param(self, mock_request_with_session, mock_oauth, mock_config):
        """``/login?next=<relative-path>`` is stored so the callback can return there."""
        request = mock_request_with_session({"oauth_state": None})
        request.query_params = {"next": "/oidc/ui/groups"}

        with (
            patch("mlflow_oidc_auth.routers.auth.oauth", mock_oauth),
            patch("mlflow_oidc_auth.routers.auth.config", mock_config),
            patch("mlflow_oidc_auth.routers.auth.get_configured_or_dynamic_redirect_uri") as mock_redirect,
            patch("mlflow_oidc_auth.routers.auth.is_oidc_configured", return_value=True),
        ):
            mock_redirect.return_value = "http://localhost:8000/callback"
            await login(request)

        assert request.session["redirect_after_login"] == "/oidc/ui/groups"

    @pytest.mark.asyncio
    async def test_login_drops_unsafe_next_param(self, mock_request_with_session, mock_oauth, mock_config):
        """Open-redirect targets must be ignored."""
        request = mock_request_with_session({"oauth_state": None})
        request.query_params = {"next": "https://attacker.example/steal"}

        with (
            patch("mlflow_oidc_auth.routers.auth.oauth", mock_oauth),
            patch("mlflow_oidc_auth.routers.auth.config", mock_config),
            patch("mlflow_oidc_auth.routers.auth.get_configured_or_dynamic_redirect_uri") as mock_redirect,
            patch("mlflow_oidc_auth.routers.auth.is_oidc_configured", return_value=True),
        ):
            mock_redirect.return_value = "http://localhost:8000/callback"
            await login(request)

        assert "redirect_after_login" not in request.session

    @pytest.mark.asyncio
    async def test_login_oauth_not_configured(self, mock_request_with_session):
        """Test login when OAuth client is not properly configured."""
        request = mock_request_with_session()

        mock_oauth = MagicMock()
        mock_oauth.oidc = MagicMock()
        # Remove authorize_redirect method to simulate misconfiguration
        del mock_oauth.oidc.authorize_redirect

        with (
            patch("mlflow_oidc_auth.routers.auth.oauth", mock_oauth),
            patch("mlflow_oidc_auth.routers.auth.is_oidc_configured", return_value=True),
            pytest.raises(HTTPException) as exc_info,
        ):
            await login(request)

        assert exc_info.value.status_code == 500
        assert "OIDC authentication not available" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_login_exception_handling(self, mock_request_with_session, mock_oauth):
        """Test login exception handling."""
        request = mock_request_with_session()

        mock_oauth.oidc.authorize_redirect.side_effect = Exception("OAuth error")

        with (
            patch("mlflow_oidc_auth.routers.auth.oauth", mock_oauth),
            patch("mlflow_oidc_auth.routers.auth.is_oidc_configured", return_value=True),
            pytest.raises(HTTPException) as exc_info,
        ):
            await login(request)

        assert exc_info.value.status_code == 500
        assert "Failed to initiate OIDC login" in str(exc_info.value.detail)


class TestLogoutEndpoint:
    """Test the logout endpoint functionality."""

    @pytest.mark.asyncio
    async def test_logout_with_oidc_provider_logout(self, mock_request_with_session, mock_oauth):
        """Test logout with OIDC provider logout support."""
        request = mock_request_with_session({"username": "test@example.com", "authenticated": True})

        with patch("mlflow_oidc_auth.routers.auth.oauth", mock_oauth):
            result = await logout(request)

            # Verify session was cleared
            assert len(request.session) == 0

            # Verify redirect to OIDC provider logout
            assert isinstance(result, RedirectResponse)
            assert result.status_code == 302
            assert "https://provider.com/logout" in result.headers["location"]
            # client_id must be sent so providers like Keycloak do not reject the
            # logout with "Missing parameters: id_token_hint".
            assert "client_id=" in result.headers["location"]

    @pytest.mark.asyncio
    async def test_logout_without_oidc_provider_logout(self, mock_request_with_session):
        """Test logout when OIDC provider doesn't support logout."""
        request = mock_request_with_session({"username": "test@example.com", "authenticated": True})

        mock_oauth = MagicMock()
        mock_oauth.oidc.server_metadata = {}  # No end_session_endpoint

        with patch("mlflow_oidc_auth.routers.auth.oauth", mock_oauth):
            result = await logout(request)

            # Verify session was cleared
            assert len(request.session) == 0

            # Verify redirect to auth page
            assert isinstance(result, RedirectResponse)
            assert result.status_code == 302
            assert "/oidc/ui/auth" in result.headers["location"]

    @pytest.mark.asyncio
    async def test_logout_exception_handling(self, mock_request_with_session):
        """Test logout exception handling."""
        request = mock_request_with_session({"username": "test@example.com", "authenticated": True})

        # Simulate exception during logout
        with patch("mlflow_oidc_auth.routers.auth.oauth") as mock_oauth:
            mock_oauth.oidc.server_metadata = None  # This will cause an exception

            result = await logout(request)

            # Should still redirect to auth page even with exception
            assert isinstance(result, RedirectResponse)
            assert "/oidc/ui/auth" in result.headers["location"]

    @pytest.mark.asyncio
    async def test_logout_unauthenticated_user(self, mock_request_with_session, mock_oauth):
        """Test logout for unauthenticated user."""
        request = mock_request_with_session({})

        with patch("mlflow_oidc_auth.routers.auth.oauth", mock_oauth):
            result = await logout(request)

            # Verify session was cleared (even if empty)
            assert len(request.session) == 0

            # Should still redirect properly
            assert isinstance(result, RedirectResponse)


class TestCallbackEndpoint:
    """Test the OIDC callback endpoint functionality."""

    @pytest.mark.asyncio
    async def test_callback_success(self, mock_request_with_session, mock_user_management):
        """Test successful OIDC callback processing."""
        request = mock_request_with_session({"oauth_state": "test_state"})

        with (
            patch("mlflow_oidc_auth.routers.auth.is_oidc_configured", return_value=True),
            patch("mlflow_oidc_auth.routers.auth._process_oidc_callback_fastapi") as mock_process,
        ):
            mock_process.return_value = ("test@example.com", [])

            result = await callback(request)

            # Verify session was updated
            assert request.session["username"] == "test@example.com"
            assert request.session["authenticated"] is True

            # Verify redirect to home page
            assert isinstance(result, RedirectResponse)
            assert result.status_code == 302
            assert "/oidc/ui/user" in result.headers["location"]

    @pytest.mark.asyncio
    async def test_callback_with_errors(self, mock_request_with_session):
        """Test callback with authentication errors."""
        request = mock_request_with_session({"oauth_state": "test_state"})

        with (
            patch("mlflow_oidc_auth.routers.auth.is_oidc_configured", return_value=True),
            patch("mlflow_oidc_auth.routers.auth._process_oidc_callback_fastapi") as mock_process,
        ):
            mock_process.return_value = (
                None,
                ["Authentication failed", "Invalid token"],
            )

            result = await callback(request)

            # Verify redirect to auth page with errors
            assert isinstance(result, RedirectResponse)
            assert result.status_code == 302
            assert "/oidc/ui/auth" in result.headers["location"]
            assert "error=" in result.headers["location"]

    @pytest.mark.asyncio
    async def test_callback_no_email_returned(self, mock_request_with_session):
        """Test callback when no email is returned but no errors."""
        request = mock_request_with_session({"oauth_state": "test_state"})

        with (
            patch("mlflow_oidc_auth.routers.auth.is_oidc_configured", return_value=True),
            patch("mlflow_oidc_auth.routers.auth._process_oidc_callback_fastapi") as mock_process,
        ):
            mock_process.return_value = (None, [])

            with pytest.raises(HTTPException) as exc_info:
                await callback(request)

            assert exc_info.value.status_code == 401
            assert "Authentication failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_callback_with_redirect_after_login(self, mock_request_with_session):
        """Test callback with custom redirect after login."""
        request = mock_request_with_session(
            {
                "oauth_state": "test_state",
                "redirect_after_login": "http://localhost:8000/custom",
            }
        )

        with (
            patch("mlflow_oidc_auth.routers.auth.is_oidc_configured", return_value=True),
            patch("mlflow_oidc_auth.routers.auth._process_oidc_callback_fastapi") as mock_process,
        ):
            mock_process.return_value = ("test@example.com", [])

            result = await callback(request)

            # Verify redirect to custom URL
            assert isinstance(result, RedirectResponse)
            assert result.headers["location"] == "http://localhost:8000/custom"

            # Verify redirect_after_login was removed from session
            assert "redirect_after_login" not in request.session

    @pytest.mark.asyncio
    async def test_callback_exception_handling(self, mock_request_with_session):
        """Test callback exception handling."""
        request = mock_request_with_session({"oauth_state": "test_state"})

        with (
            patch("mlflow_oidc_auth.routers.auth.is_oidc_configured", return_value=True),
            patch("mlflow_oidc_auth.routers.auth._process_oidc_callback_fastapi") as mock_process,
        ):
            mock_process.side_effect = Exception("Unexpected error")

            with pytest.raises(HTTPException) as exc_info:
                await callback(request)

            assert exc_info.value.status_code == 500
            assert "Internal server error during authentication" in str(exc_info.value.detail)

            with pytest.raises(HTTPException) as exc_info:
                await callback(request)

            assert exc_info.value.status_code == 500
            assert "Internal server error during authentication" in str(exc_info.value.detail)


class TestAuthStatusEndpoint:
    """Test the auth status endpoint functionality."""

    @pytest.mark.asyncio
    async def test_auth_status_authenticated(self, mock_request_with_session, mock_config):
        """Test auth status for authenticated user."""
        request = mock_request_with_session({"username": "test@example.com", "authenticated": True})

        with patch("mlflow_oidc_auth.routers.auth.config", mock_config):
            result = await auth_status(request)

            assert isinstance(result, JSONResponse)
            content = result.body.decode()
            assert '"authenticated":true' in content
            assert '"username":"test@example.com"' in content
            assert '"provider":"Test Provider"' in content

    @pytest.mark.asyncio
    async def test_auth_status_unauthenticated(self, mock_request_with_session, mock_config):
        """Test auth status for unauthenticated user."""
        request = mock_request_with_session({})

        with patch("mlflow_oidc_auth.routers.auth.config", mock_config):
            result = await auth_status(request)

            assert isinstance(result, JSONResponse)
            content = result.body.decode()
            assert '"authenticated":false' in content
            assert '"username":null' in content
            assert '"provider":null' in content

    @pytest.mark.asyncio
    async def test_auth_status_exception_handling(self, mock_request_with_session):
        """Test auth status exception handling."""
        request = mock_request_with_session({})
        request.session = None  # This will cause an exception

        with pytest.raises(HTTPException) as exc_info:
            await auth_status(request)

        assert exc_info.value.status_code == 500


class TestProcessOIDCCallbackFastAPI:
    """Test the OIDC callback processing function."""

    @pytest.mark.asyncio
    async def test_process_callback_success(self, mock_request_with_session, mock_oauth, mock_config, mock_user_management):
        """Test successful OIDC callback processing."""
        request = mock_request_with_session({"oauth_state": "test_state"})
        request.query_params = {"state": "test_state", "code": "auth_code_123"}

        with (
            patch("mlflow_oidc_auth.routers.auth.oauth", mock_oauth),
            patch("mlflow_oidc_auth.routers.auth.config", mock_config),
        ):
            email, errors = await _process_oidc_callback_fastapi(request, request.session)

            assert email == "test@example.com"
            assert errors == []

            # Verify user management functions were called
            mock_user_management["create_user"].assert_called_once()
            mock_user_management["populate_groups"].assert_called_once()
            mock_user_management["update_user"].assert_called_once()

    @pytest.mark.asyncio
    async def test_process_callback_refreshes_jwks_on_bad_signature(
        self,
        mock_request_with_session,
        mock_oauth,
        mock_config,
        mock_user_management,
        caplog,
    ):
        """Retry token exchange after JWKS refresh when the provider rotates signing keys."""

        caplog.set_level("DEBUG", logger="uvicorn")
        request = mock_request_with_session({"oauth_state": "test_state"})
        request.query_params = {"state": "test_state", "code": "auth_code_123"}

        mock_oauth.oidc.authorize_access_token.side_effect = [
            BadSignatureError("bad signature"),
            {
                "access_token": "token",
                "id_token": "id_token",
                "userinfo": {
                    "email": "test@example.com",
                    "name": "Test User",
                    "groups": ["test-group"],
                },
            },
        ]
        mock_oauth.oidc.fetch_jwk_set = AsyncMock()

        with (
            patch("mlflow_oidc_auth.routers.auth.oauth", mock_oauth),
            patch("mlflow_oidc_auth.routers.auth.config", mock_config),
        ):
            email, errors = await _process_oidc_callback_fastapi(request, request.session)

        assert errors == [], f"{caplog.text} call_count={mock_oauth.oidc.authorize_access_token.call_count}"
        assert email == "test@example.com"
        assert "OIDC token exchange error" not in caplog.text
        mock_oauth.oidc.fetch_jwk_set.assert_awaited_once_with(force=True)
        assert mock_oauth.oidc.authorize_access_token.call_count == 2

    @pytest.mark.asyncio
    async def test_process_callback_oidc_error(self, mock_request_with_session):
        """Test callback processing with OIDC provider error."""
        request = mock_request_with_session({"oauth_state": "test_state"})
        request.query_params = {
            "error": "access_denied",
            "error_description": "User denied access",
        }

        email, errors = await _process_oidc_callback_fastapi(request, request.session)

        assert email is None
        assert len(errors) == 2
        assert "OIDC provider error" in errors[0]
        assert "User denied access" in errors[1]

    @pytest.mark.asyncio
    async def test_process_callback_missing_state(self, mock_request_with_session):
        """Test callback processing with missing OAuth state."""
        request = mock_request_with_session({})  # No oauth_state in session
        request.query_params = {"state": "test_state", "code": "auth_code_123"}

        email, errors = await _process_oidc_callback_fastapi(request, request.session)

        assert email is None
        assert len(errors) == 1
        assert "Missing OAuth state in session" in errors[0]

    @pytest.mark.asyncio
    async def test_process_callback_invalid_state(self, mock_request_with_session):
        """Test callback processing with invalid OAuth state."""
        request = mock_request_with_session({"oauth_state": "correct_state"})
        request.query_params = {"state": "wrong_state", "code": "auth_code_123"}

        email, errors = await _process_oidc_callback_fastapi(request, request.session)

        assert email is None
        assert len(errors) == 1
        assert "Invalid state parameter" in errors[0]

    @pytest.mark.asyncio
    async def test_process_callback_missing_code(self, mock_request_with_session):
        """Test callback processing with missing authorization code."""
        request = mock_request_with_session({"oauth_state": "test_state"})
        request.query_params = {
            "state": "test_state"
            # Missing code parameter
        }

        email, errors = await _process_oidc_callback_fastapi(request, request.session)

        assert email is None
        assert len(errors) == 1
        assert "No authorization code received" in errors[0]

    @pytest.mark.asyncio
    async def test_process_callback_token_exchange_failure(self, mock_request_with_session, mock_oauth):
        """Test callback processing with token exchange failure."""
        request = mock_request_with_session({"oauth_state": "test_state"})
        request.query_params = {"state": "test_state", "code": "auth_code_123"}

        # Mock failed token exchange
        mock_oauth.oidc.authorize_access_token.return_value = None

        with patch("mlflow_oidc_auth.routers.auth.oauth", mock_oauth):
            email, errors = await _process_oidc_callback_fastapi(request, request.session)

            assert email is None
            assert len(errors) == 1
            assert "Failed to exchange authorization code" in errors[0]

    @pytest.mark.asyncio
    async def test_process_callback_missing_userinfo(self, mock_request_with_session, mock_oauth):
        """Test callback processing with missing user info."""
        request = mock_request_with_session({"oauth_state": "test_state"})
        request.query_params = {"state": "test_state", "code": "auth_code_123"}

        # Mock token response without userinfo
        mock_oauth.oidc.authorize_access_token.return_value = {
            "access_token": "token",
            "id_token": "id_token",
            # Missing userinfo
        }

        with patch("mlflow_oidc_auth.routers.auth.oauth", mock_oauth):
            email, errors = await _process_oidc_callback_fastapi(request, request.session)

            assert email is None
            assert len(errors) == 1
            assert "No user information received" in errors[0]

    @pytest.mark.asyncio
    async def test_process_callback_missing_email(self, mock_request_with_session, mock_oauth):
        """Test callback processing with missing email in userinfo."""
        request = mock_request_with_session({"oauth_state": "test_state"})
        request.query_params = {"state": "test_state", "code": "auth_code_123"}

        # Mock token response with userinfo but no email
        mock_oauth.oidc.authorize_access_token.return_value = {
            "access_token": "token",
            "id_token": "id_token",
            "userinfo": {
                "name": "Test User"
                # Missing email
            },
        }

        with patch("mlflow_oidc_auth.routers.auth.oauth", mock_oauth):
            email, errors = await _process_oidc_callback_fastapi(request, request.session)

            assert email is None
            assert len(errors) == 1
            assert "No email provided in OIDC userinfo" in errors[0]

    @pytest.mark.asyncio
    async def test_process_callback_unauthorized_user(self, mock_request_with_session, mock_oauth, mock_config):
        """Test callback processing for unauthorized user."""
        request = mock_request_with_session({"oauth_state": "test_state"})
        request.query_params = {"state": "test_state", "code": "auth_code_123"}

        # Mock token response with user not in allowed groups
        mock_oauth.oidc.authorize_access_token.return_value = {
            "access_token": "token",
            "id_token": "id_token",
            "userinfo": {
                "email": "unauthorized@example.com",
                "name": "Unauthorized User",
                "groups": ["unauthorized-group"],
            },  # Not in allowed groups
        }

        # Mock config with specific allowed groups
        mock_config.OIDC_ADMIN_GROUP_NAME = ["admin-group"]
        mock_config.OIDC_GROUP_NAME = ["user-group"]

        with (
            patch("mlflow_oidc_auth.routers.auth.oauth", mock_oauth),
            patch("mlflow_oidc_auth.routers.auth.config", mock_config),
        ):
            email, errors = await _process_oidc_callback_fastapi(request, request.session)

            assert email is None
            assert len(errors) == 1
            assert "User is not allowed to login" in errors[0]

    @pytest.mark.asyncio
    async def test_process_callback_user_management_error(self, mock_request_with_session, mock_oauth, mock_config):
        """Test callback processing with user management error."""
        request = mock_request_with_session({"oauth_state": "test_state"})
        request.query_params = {"state": "test_state", "code": "auth_code_123"}

        with (
            patch("mlflow_oidc_auth.routers.auth.oauth", mock_oauth),
            patch("mlflow_oidc_auth.routers.auth.config", mock_config),
            patch("mlflow_oidc_auth.user.create_user") as mock_create,
        ):
            # Mock user creation failure
            mock_create.side_effect = Exception("Database error")

            email, errors = await _process_oidc_callback_fastapi(request, request.session)

            assert email is None
            assert len(errors) == 1
            assert "Failed to update user/groups" in errors[0]


class TestExtractSessionExpiry:
    """Test ``_extract_session_expiry`` precedence rules."""

    def test_prefers_expires_at(self):
        token = {"expires_at": 12345, "expires_in": 3600, "userinfo": {"exp": 99999}}
        assert _extract_session_expiry(token) == 12345

    def test_falls_back_to_id_token_exp(self):
        token = {"userinfo": {"exp": 99999}, "expires_in": 3600}
        assert _extract_session_expiry(token) == 99999

    def test_computes_from_expires_in_when_no_expires_at(self):
        import time as _time

        token = {"expires_in": 3600}
        result = _extract_session_expiry(token)
        # Allow a few seconds of slack between time.time() inside and outside.
        assert result is not None
        assert abs(result - (int(_time.time()) + 3600)) < 5

    def test_returns_none_when_unavailable(self):
        assert _extract_session_expiry({}) is None
        assert _extract_session_expiry({"userinfo": {}}) is None

    def test_ignores_non_numeric_expiry(self):
        assert _extract_session_expiry({"expires_at": "soon"}) is None


class TestPersistSessionAuth:
    """Test that the callback persists exactly the session fields needed for re-auth."""

    def test_stores_expires_at_when_refresh_disabled(self, mock_config):
        mock_config.OIDC_USE_REFRESH_TOKEN = False
        session = {}
        token = {"expires_at": 9999999999, "refresh_token": "rt"}

        with patch("mlflow_oidc_auth.routers.auth.config", mock_config):
            _persist_session_auth(session, token)

        assert session["expires_at"] == 9999999999
        # Refresh token must NOT leak into the cookie when feature is disabled.
        assert "refresh_token" not in session

    def test_stores_refresh_token_when_enabled(self, mock_config):
        mock_config.OIDC_USE_REFRESH_TOKEN = True
        session = {}
        token = {"expires_at": 9999999999, "refresh_token": "rt-abc"}

        with patch("mlflow_oidc_auth.routers.auth.config", mock_config):
            _persist_session_auth(session, token)

        assert session["expires_at"] == 9999999999
        assert session["refresh_token"] == "rt-abc"

    def test_clears_stale_expires_at_when_no_new_expiry(self, mock_config):
        mock_config.OIDC_USE_REFRESH_TOKEN = False
        session = {"expires_at": 100}

        with patch("mlflow_oidc_auth.routers.auth.config", mock_config):
            _persist_session_auth(session, {})  # token response without expiry info

        assert "expires_at" not in session

    def test_drops_refresh_token_when_disabled_after_enabled(self, mock_config):
        # Simulates rotating from refresh-enabled deployment back to disabled.
        mock_config.OIDC_USE_REFRESH_TOKEN = False
        session = {"refresh_token": "stale"}
        token = {"expires_at": 9999999999, "refresh_token": "rt-new"}

        with patch("mlflow_oidc_auth.routers.auth.config", mock_config):
            _persist_session_auth(session, token)

        assert "refresh_token" not in session

    def test_keeps_existing_refresh_token_when_response_omits_one(self, mock_config):
        """Many IdPs (Entra, some Keycloak configs) emit refresh_token only on
        the initial token exchange and reuse the same one across refreshes.
        Removing the stored token would break the next refresh."""
        mock_config.OIDC_USE_REFRESH_TOKEN = True
        session = {"refresh_token": "rt-original"}
        token = {"expires_at": 9999999999}  # No refresh_token in the response

        with patch("mlflow_oidc_auth.routers.auth.config", mock_config):
            _persist_session_auth(session, token)

        assert session["refresh_token"] == "rt-original"
        assert session["expires_at"] == 9999999999


class TestRefreshSessionWithIdP:
    """Test ``refresh_session_with_idp`` against the OAuth client."""

    @pytest.mark.asyncio
    async def test_disabled_when_feature_off(self, mock_config):
        mock_config.OIDC_USE_REFRESH_TOKEN = False

        with patch("mlflow_oidc_auth.routers.auth.config", mock_config):
            assert await refresh_session_with_idp({"refresh_token": "rt"}) is False

    @pytest.mark.asyncio
    async def test_returns_false_without_refresh_token(self, mock_config):
        mock_config.OIDC_USE_REFRESH_TOKEN = True

        with patch("mlflow_oidc_auth.routers.auth.config", mock_config):
            assert await refresh_session_with_idp({}) is False

    @pytest.mark.asyncio
    async def test_success_updates_session(self, mock_config, mock_oauth):
        mock_config.OIDC_USE_REFRESH_TOKEN = True
        mock_oauth.oidc.fetch_access_token = AsyncMock(
            return_value={
                "access_token": "new",
                "expires_at": 9999999999,
                "refresh_token": "rt-new",
            }
        )
        session = {"refresh_token": "rt-old", "expires_at": 1, "username": "u@x"}

        with (
            patch("mlflow_oidc_auth.routers.auth.config", mock_config),
            patch("mlflow_oidc_auth.routers.auth.oauth", mock_oauth),
        ):
            ok = await refresh_session_with_idp(session)

        assert ok is True
        assert session["expires_at"] == 9999999999
        assert session["refresh_token"] == "rt-new"
        assert session["username"] == "u@x"  # untouched
        mock_oauth.oidc.fetch_access_token.assert_awaited_once_with(grant_type="refresh_token", refresh_token="rt-old")

    @pytest.mark.asyncio
    async def test_failure_returns_false_without_mutating(self, mock_config, mock_oauth):
        mock_config.OIDC_USE_REFRESH_TOKEN = True
        mock_oauth.oidc.fetch_access_token = AsyncMock(side_effect=RuntimeError("idp down"))
        session = {"refresh_token": "rt-old", "expires_at": 1}

        with (
            patch("mlflow_oidc_auth.routers.auth.config", mock_config),
            patch("mlflow_oidc_auth.routers.auth.oauth", mock_oauth),
        ):
            ok = await refresh_session_with_idp(session)

        assert ok is False
        # Session retains its (still-stale) values; middleware is responsible for clearing it.
        assert session["refresh_token"] == "rt-old"
        assert session["expires_at"] == 1


class TestProcessCallbackPersistsExpiry:
    """End-to-end: the callback path persists the IdP expiry into the session."""

    @pytest.mark.asyncio
    async def test_callback_writes_expires_at(self, mock_request_with_session, mock_oauth, mock_config, mock_user_management):
        mock_config.OIDC_USE_REFRESH_TOKEN = False
        mock_oauth.oidc.authorize_access_token = AsyncMock(
            return_value={
                "access_token": "at",
                "id_token": "idt",
                "expires_at": 9999999999,
                "userinfo": {
                    "email": "test@example.com",
                    "name": "Test User",
                    "groups": ["test-group"],
                },
            }
        )
        request = mock_request_with_session({"oauth_state": "test_state"})
        request.query_params = {"state": "test_state", "code": "auth_code_123"}

        with (
            patch("mlflow_oidc_auth.routers.auth.oauth", mock_oauth),
            patch("mlflow_oidc_auth.routers.auth.config", mock_config),
        ):
            email, errors = await _process_oidc_callback_fastapi(request, request.session)

        assert errors == []
        assert email == "test@example.com"
        assert request.session["expires_at"] == 9999999999
        assert "refresh_token" not in request.session

    @pytest.mark.asyncio
    async def test_callback_writes_refresh_token_when_enabled(self, mock_request_with_session, mock_oauth, mock_config, mock_user_management):
        mock_config.OIDC_USE_REFRESH_TOKEN = True
        mock_oauth.oidc.authorize_access_token = AsyncMock(
            return_value={
                "access_token": "at",
                "id_token": "idt",
                "expires_at": 9999999999,
                "refresh_token": "rt-xyz",
                "userinfo": {
                    "email": "test@example.com",
                    "name": "Test User",
                    "groups": ["test-group"],
                },
            }
        )
        request = mock_request_with_session({"oauth_state": "test_state"})
        request.query_params = {"state": "test_state", "code": "auth_code_123"}

        with (
            patch("mlflow_oidc_auth.routers.auth.oauth", mock_oauth),
            patch("mlflow_oidc_auth.routers.auth.config", mock_config),
        ):
            email, errors = await _process_oidc_callback_fastapi(request, request.session)

        assert errors == []
        assert email == "test@example.com"
        assert request.session["expires_at"] == 9999999999
        assert request.session["refresh_token"] == "rt-xyz"


class TestSanitizeNext:
    """Validate the open-redirect guard on the ?next= query param."""

    def test_accepts_relative_path(self):
        from mlflow_oidc_auth.routers.auth import _sanitize_next

        assert _sanitize_next("/oidc/ui/groups") == "/oidc/ui/groups"

    def test_accepts_path_with_search_and_hash(self):
        from mlflow_oidc_auth.routers.auth import _sanitize_next

        assert _sanitize_next("/?tab=runs#/experiments/0") == "/?tab=runs#/experiments/0"

    def test_rejects_absolute_url(self):
        from mlflow_oidc_auth.routers.auth import _sanitize_next

        assert _sanitize_next("https://attacker.example/steal") is None
        assert _sanitize_next("http://attacker.example/") is None

    def test_rejects_protocol_relative(self):
        from mlflow_oidc_auth.routers.auth import _sanitize_next

        # //evil.example escapes origin in browsers — must reject.
        assert _sanitize_next("//evil.example/path") is None

    def test_rejects_javascript_scheme(self):
        from mlflow_oidc_auth.routers.auth import _sanitize_next

        assert _sanitize_next("javascript:alert(1)") is None

    def test_rejects_header_injection_chars(self):
        from mlflow_oidc_auth.routers.auth import _sanitize_next

        assert _sanitize_next("/path\nLocation: http://evil") is None
        assert _sanitize_next("/path\rfoo") is None

    def test_rejects_empty_and_none(self):
        from mlflow_oidc_auth.routers.auth import _sanitize_next

        assert _sanitize_next(None) is None
        assert _sanitize_next("") is None
        assert _sanitize_next("no-leading-slash") is None
