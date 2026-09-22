"""
Comprehensive tests for the authentication router.

This module tests all authentication endpoints including login, logout, callback,
and auth status with various scenarios including success, failure, and edge cases.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from types import SimpleNamespace

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
    _session_tokens_from_response,
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
    async def test_login_success(self, mock_request_with_session, mock_oauth, mock_config, created_states):
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
            # The attempt is a row now, not a cookie key: what login must do is start one and
            # send its state to the provider (#316).
            assert created_states, "login must record an attempt"

            # Verify OAuth redirect was called
            mock_oauth.oidc.authorize_redirect.assert_called_once_with(
                request,
                redirect_uri="http://localhost:8000/callback",
                state="test_state_token",
            )

    @pytest.mark.asyncio
    async def test_login_captures_safe_next_param(self, mock_request_with_session, mock_oauth, mock_config, created_states):
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

        # The return target travels with the attempt, not in the cookie: a second tab starting
        # its own login would otherwise overwrite where the first one meant to come back to.
        assert created_states[-1]["redirect_after_login"] == "/oidc/ui/groups"

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
            # The cookie carries an opaque session id, not the username: authenticating from a
            # cookie-carried username is exactly what could not be revoked (#310).
            assert "username" not in request.session
            assert request.session["session_id"]
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
        # Since #310 the cookie carries only an opaque session id; the username comes from the row.
        request = mock_request_with_session({"session_id": "sid-test"})

        with patch("mlflow_oidc_auth.routers.auth.config", mock_config), patch("mlflow_oidc_auth.routers.auth.store") as mock_store:
            mock_store.resolve_auth_session.return_value = SimpleNamespace(username="test@example.com", is_admin=False, is_active=True)
            result = await auth_status(request)

            assert isinstance(result, JSONResponse)
            content = result.body.decode()
            assert '"authenticated":true' in content
            assert '"username":"test@example.com"' in content
            assert '"provider":"Test Provider"' in content

    @pytest.mark.asyncio
    async def test_auth_status_deactivated_user_is_not_authenticated(self, mock_request_with_session, mock_config):
        """``resolve`` reports the active flag rather than filtering on it, so the endpoint has
        to apply the check — otherwise the SPA renders a logged-in shell for an account every
        API call will 401."""
        request = mock_request_with_session({"session_id": "sid-inactive"})

        with patch("mlflow_oidc_auth.routers.auth.config", mock_config), patch("mlflow_oidc_auth.routers.auth.store") as mock_store:
            mock_store.resolve_auth_session.return_value = SimpleNamespace(username="gone@example.com", is_admin=False, is_active=False)
            result = await auth_status(request)

            content = result.body.decode()
            assert '"authenticated":false' in content
            assert '"username":null' in content

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
        """A rotated signing key refreshes the JWKS, so the *next* login works.

        This login does not: it used to assert that a second exchange succeeded, which authlib
        can never do. It removes the per-attempt state — the PKCE verifier, the nonce, the
        redirect URI — from the session before sending the token request, so a second call
        raises ``MismatchingStateError``, and the authorization code is single-use anyway. The
        retry only ever replaced the real error with a misleading one.
        """

        caplog.set_level("DEBUG", logger="uvicorn")
        request = mock_request_with_session({"oauth_state": "test_state"})
        request.query_params = {"state": "test_state", "code": "auth_code_123"}

        mock_oauth.oidc.authorize_access_token.side_effect = BadSignatureError("bad signature")
        mock_oauth.oidc.fetch_jwk_set = AsyncMock()

        with (
            patch("mlflow_oidc_auth.routers.auth.oauth", mock_oauth),
            patch("mlflow_oidc_auth.routers.auth.config", mock_config),
        ):
            email, errors = await _process_oidc_callback_fastapi(request, request.session)

        assert email is None
        assert errors, "the login fails; what recovers is the one after it"
        mock_oauth.oidc.fetch_jwk_set.assert_awaited_once_with(force=True)
        assert mock_oauth.oidc.authorize_access_token.call_count == 1, "a second attempt cannot succeed and must not be made"

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
    async def test_process_callback_missing_state(self, mock_request_with_session, no_attempt):
        """Test callback processing with missing OAuth state."""
        request = mock_request_with_session({})  # No oauth_state in session
        request.query_params = {"state": "test_state", "code": "auth_code_123"}

        email, errors = await _process_oidc_callback_fastapi(request, request.session)

        assert email is None
        assert len(errors) == 1
        # "Missing" and "wrong" give the same answer now — the row is the check, and telling
        # them apart would tell an attacker which of the two they had.
        assert "Invalid state parameter" in errors[0]

    @pytest.mark.asyncio
    async def test_process_callback_invalid_state(self, mock_request_with_session, no_attempt):
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
            assert "No username provided in OIDC userinfo" in errors[0]

    @pytest.mark.asyncio
    async def test_process_callback_missing_display_name_falls_back_to_username(self, mock_request_with_session, mock_oauth, mock_config, mock_user_management):
        """A missing display name must not block login — it falls back to the username."""
        request = mock_request_with_session({"oauth_state": "test_state"})
        request.query_params = {"state": "test_state", "code": "auth_code_123"}

        mock_oauth.oidc.authorize_access_token.return_value = {
            "access_token": "token",
            "id_token": "id_token",
            "userinfo": {
                "email": "test@example.com",
                "groups": ["test-group"],
                # Missing "name", so display-name extraction fails.
            },
        }

        with (
            patch("mlflow_oidc_auth.routers.auth.oauth", mock_oauth),
            patch("mlflow_oidc_auth.routers.auth.config", mock_config),
        ):
            username, errors = await _process_oidc_callback_fastapi(request, request.session)

            assert username == "test@example.com"
            assert errors == []
            mock_user_management["create_user"].assert_called_once_with(
                username="test@example.com", display_name="test@example.com", is_admin=False, written_by="oidc:default"
            )

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


class _FakeSessionRow:
    """A single session row with the refresh-guard surface of the real store (#367).

    Enough to drive ``refresh_session_with_idp`` without a database: the guard yields the blob
    as it is *now*, records writes, and can be told the session was revoked.
    """

    def __init__(self, tokens=None, live=True):
        from mlflow_oidc_auth.session.token_vault import get_token_vault

        self.vault = get_token_vault()
        self.blob = self.vault.encrypt(tokens) if tokens is not None else None
        self.live = live
        self.writes = []
        self.guard_entries = 0

    @property
    def tokens(self):
        return self.vault.decrypt(self.blob)

    def resolved(self):
        return SimpleNamespace(username="u@x", is_admin=False, is_active=True, provider_id=None, encrypted_tokens=self.blob, session_id="sid")

    def auth_session_refresh_guard(self, session_id):
        from contextlib import contextmanager

        from mlflow_oidc_auth.repository.auth_session import RefreshGuard

        @contextmanager
        def _guard():
            self.guard_entries += 1

            def _write(new_blob):
                if not self.live:
                    return False
                self.blob = new_blob
                self.writes.append(new_blob)
                return True

            yield RefreshGuard(self.blob, self.live, reread=lambda: self.blob, write=_write)

        return _guard()

    def store_auth_session_tokens(self, session_id, blob):
        self.blob = blob
        self.writes.append(blob)
        return True

    def resolve_auth_session(self, session_id):
        return self.resolved()


class TestSessionTokensFromResponse:
    """What a token response leaves on the session row (#367). Nothing here touches the cookie."""

    def _build(self, mock_config, token, **kwargs):
        with patch("mlflow_oidc_auth.routers.auth.config", mock_config):
            return _session_tokens_from_response(token, **kwargs)

    def test_refresh_token_is_not_retained_when_refresh_disabled(self, mock_config):
        mock_config.OIDC_USE_REFRESH_TOKEN = False
        tokens = self._build(mock_config, {"expires_at": 9999999999, "refresh_token": "rt"}, provider_id="default")

        assert tokens.expires_at == 9999999999
        assert tokens.refresh_token is None
        assert tokens.provider_id == "default"

    def test_refresh_token_is_retained_when_enabled(self, mock_config):
        mock_config.OIDC_USE_REFRESH_TOKEN = True
        tokens = self._build(mock_config, {"expires_at": 9999999999, "refresh_token": "rt-abc", "id_token": "idt"})

        assert tokens.refresh_token == "rt-abc"
        assert tokens.id_token == "idt"

    def test_no_expiry_in_response_is_none(self, mock_config):
        mock_config.OIDC_USE_REFRESH_TOKEN = False
        assert self._build(mock_config, {}).expires_at is None

    def test_keeps_previous_refresh_token_when_response_omits_one(self, mock_config):
        """Many IdPs (Entra, some Keycloak configs) emit refresh_token only on
        the initial token exchange and reuse the same one across refreshes."""
        from mlflow_oidc_auth.session.token_vault import SessionTokens

        mock_config.OIDC_USE_REFRESH_TOKEN = True
        previous = SessionTokens(provider_id="corp", expires_at=1, refresh_token="rt-original", id_token="idt-old")

        tokens = self._build(mock_config, {"expires_at": 9999999999}, previous=previous)

        assert tokens.refresh_token == "rt-original"
        assert tokens.id_token == "idt-old"
        assert tokens.provider_id == "corp", "a refresh keeps the issuing provider"
        assert tokens.expires_at == 9999999999

    def test_previous_refresh_token_is_dropped_when_refresh_disabled(self, mock_config):
        from mlflow_oidc_auth.session.token_vault import SessionTokens

        mock_config.OIDC_USE_REFRESH_TOKEN = False
        tokens = self._build(mock_config, {"expires_at": 9999999999}, previous=SessionTokens(refresh_token="stale"))

        assert tokens.refresh_token is None


class TestRefreshSessionWithIdP:
    """``refresh_session_with_idp`` against the OAuth client, through the refresh guard (#367)."""

    @pytest.fixture
    def cfg(self, mock_config):
        mock_config.OIDC_USE_REFRESH_TOKEN = True
        mock_config.OIDC_SESSION_EXPIRY_LEEWAY_SECONDS = 30
        return mock_config

    async def _refresh(self, cfg, mock_oauth, row, resolved=True):
        with (
            patch("mlflow_oidc_auth.routers.auth.config", cfg),
            patch("mlflow_oidc_auth.routers.auth.oauth", mock_oauth),
            patch("mlflow_oidc_auth.routers.auth.store", row),
        ):
            return await refresh_session_with_idp("sid", row.resolved() if resolved else None)

    @pytest.mark.asyncio
    async def test_disabled_when_feature_off(self, cfg, mock_oauth):
        from mlflow_oidc_auth.session.token_vault import SessionTokens

        cfg.OIDC_USE_REFRESH_TOKEN = False
        row = _FakeSessionRow(SessionTokens(expires_at=1, refresh_token="rt"))

        assert await self._refresh(cfg, mock_oauth, row) is False
        assert row.guard_entries == 0

    @pytest.mark.asyncio
    async def test_returns_false_without_refresh_token(self, cfg, mock_oauth):
        from mlflow_oidc_auth.session.token_vault import SessionTokens

        row = _FakeSessionRow(SessionTokens(expires_at=1))

        assert await self._refresh(cfg, mock_oauth, row) is False
        assert row.guard_entries == 0, "nothing to refresh with: the guard is not even taken"

    @pytest.mark.asyncio
    async def test_returns_false_without_session_id(self, cfg, mock_oauth):
        with patch("mlflow_oidc_auth.routers.auth.config", cfg):
            assert await refresh_session_with_idp(None) is False

    @pytest.mark.asyncio
    async def test_success_stores_rotated_token_on_the_row(self, cfg, mock_oauth):
        from mlflow_oidc_auth.session.token_vault import SessionTokens

        mock_oauth.oidc.fetch_access_token = AsyncMock(return_value={"access_token": "new", "expires_at": 9999999999, "refresh_token": "rt-new"})
        row = _FakeSessionRow(SessionTokens(expires_at=1, refresh_token="rt-old", id_token="idt"))

        assert await self._refresh(cfg, mock_oauth, row) is True

        assert row.tokens.expires_at == 9999999999
        assert row.tokens.refresh_token == "rt-new"
        assert row.tokens.id_token == "idt", "the ID token survives a refresh that returns none"
        mock_oauth.oidc.fetch_access_token.assert_awaited_once_with(grant_type="refresh_token", refresh_token="rt-old")

    @pytest.mark.asyncio
    async def test_loser_adopts_winner_without_calling_the_idp(self, cfg, mock_oauth):
        """The middleware saw an expired row, but by the time this request holds the guard a
        concurrent one has refreshed it. Exchanging again would replay a rotated token."""
        from mlflow_oidc_auth.session.token_vault import SessionTokens

        mock_oauth.oidc.fetch_access_token = AsyncMock()
        row = _FakeSessionRow(SessionTokens(expires_at=1, refresh_token="rt-old"))
        stale = row.resolved()
        row.blob = row.vault.encrypt(SessionTokens(expires_at=9999999999, refresh_token="rt-rotated"))

        with (
            patch("mlflow_oidc_auth.routers.auth.config", cfg),
            patch("mlflow_oidc_auth.routers.auth.oauth", mock_oauth),
            patch("mlflow_oidc_auth.routers.auth.store", row),
        ):
            assert await refresh_session_with_idp("sid", stale) is True

        mock_oauth.oidc.fetch_access_token.assert_not_called()
        assert row.tokens.refresh_token == "rt-rotated"

    @pytest.mark.asyncio
    async def test_failure_returns_false_without_mutating(self, cfg, mock_oauth):
        from mlflow_oidc_auth.session.token_vault import SessionTokens

        mock_oauth.oidc.fetch_access_token = AsyncMock(side_effect=RuntimeError("idp down"))
        row = _FakeSessionRow(SessionTokens(expires_at=1, refresh_token="rt-old"))

        assert await self._refresh(cfg, mock_oauth, row) is False
        assert row.writes == []
        assert row.tokens.refresh_token == "rt-old"

    @pytest.mark.asyncio
    async def test_a_waiter_adopts_without_entering_the_guard(self, cfg, mock_oauth, monkeypatch):
        """Queued on the event loop, a waiter re-reads the row and adopts; it never takes a thread."""
        from mlflow_oidc_auth.routers import auth as auth_module
        from mlflow_oidc_auth.session.token_vault import SessionTokens

        blocking_calls = []
        monkeypatch.setattr(auth_module, "_run_blocking", lambda *a, **k: blocking_calls.append(a) or (_ for _ in ()).throw(AssertionError))
        mock_oauth.oidc.fetch_access_token = AsyncMock()
        row = _FakeSessionRow(SessionTokens(expires_at=1, refresh_token="rt-old"))
        stale = row.resolved()
        row.blob = row.vault.encrypt(SessionTokens(expires_at=9999999999, refresh_token="rt-rotated"))

        with (
            patch("mlflow_oidc_auth.routers.auth.config", cfg),
            patch("mlflow_oidc_auth.routers.auth.oauth", mock_oauth),
            patch("mlflow_oidc_auth.routers.auth.store", row),
        ):
            assert await refresh_session_with_idp("sid", stale) is True

        assert blocking_calls == []
        assert row.guard_entries == 0

    @pytest.mark.asyncio
    async def test_failure_after_a_concurrent_winner_is_success(self, cfg, mock_oauth):
        """The IdP refused (the token was just rotated by a winner elsewhere); the re-read finds
        the winner's fresh tokens, so this request is not logged out."""
        from mlflow_oidc_auth.session.token_vault import SessionTokens

        row = _FakeSessionRow(SessionTokens(expires_at=1, refresh_token="rt-old"))

        async def _refuse_after_winner(**kwargs):
            row.blob = row.vault.encrypt(SessionTokens(expires_at=9999999999, refresh_token="rt-winner"))
            raise RuntimeError("invalid_grant")

        mock_oauth.oidc.fetch_access_token = _refuse_after_winner

        assert await self._refresh(cfg, mock_oauth, row) is True
        assert row.writes == []

    @pytest.mark.asyncio
    async def test_revoked_session_is_not_refreshed(self, cfg, mock_oauth):
        from mlflow_oidc_auth.session.token_vault import SessionTokens

        mock_oauth.oidc.fetch_access_token = AsyncMock()
        row = _FakeSessionRow(SessionTokens(expires_at=1, refresh_token="rt-old"))
        resolved = row.resolved()
        row.live = False

        with (
            patch("mlflow_oidc_auth.routers.auth.config", cfg),
            patch("mlflow_oidc_auth.routers.auth.oauth", mock_oauth),
            patch("mlflow_oidc_auth.routers.auth.store", row),
        ):
            assert await refresh_session_with_idp("sid", resolved) is False
        mock_oauth.oidc.fetch_access_token.assert_not_called()

    @pytest.mark.asyncio
    async def test_named_provider_is_refreshed_at_that_provider_only(self, cfg, mock_oauth):
        """A refresh token is never sent to a different issuer's token endpoint."""
        from mlflow_oidc_auth.session.token_vault import SessionTokens

        mock_oauth.oidc.fetch_access_token = AsyncMock()
        row = _FakeSessionRow(SessionTokens(provider_id="other", expires_at=1, refresh_token="rt-old"))

        with patch("mlflow_oidc_auth.routers.auth.get_client", return_value=None):
            assert await self._refresh(cfg, mock_oauth, row) is False
        mock_oauth.oidc.fetch_access_token.assert_not_called()

    @pytest.mark.asyncio
    async def test_undecryptable_tokens_are_not_used(self, cfg, mock_oauth):
        mock_oauth.oidc.fetch_access_token = AsyncMock()
        row = _FakeSessionRow()
        row.blob = "not-a-fernet-token"

        assert await self._refresh(cfg, mock_oauth, row) is False
        mock_oauth.oidc.fetch_access_token.assert_not_called()


class TestProcessCallbackPersistsExpiry:
    """The callback leaves tokens for the session row, and none in the cookie (#367)."""

    @pytest.mark.asyncio
    async def test_callback_holds_expiry_for_the_row(self, mock_request_with_session, mock_oauth, mock_config, mock_user_management):
        mock_config.OIDC_USE_REFRESH_TOKEN = False
        mock_oauth.oidc.authorize_access_token = AsyncMock(
            return_value={
                "access_token": "at",
                "id_token": "idt",
                "expires_at": 9999999999,
                "refresh_token": "rt-ignored",
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
        tokens = request.state.pending_session_tokens
        assert tokens.expires_at == 9999999999
        assert tokens.refresh_token is None
        assert tokens.id_token == "idt"
        assert tokens.provider_id == "default"
        assert "expires_at" not in request.session
        assert "refresh_token" not in request.session

    @pytest.mark.asyncio
    async def test_callback_holds_refresh_token_when_enabled(self, mock_request_with_session, mock_oauth, mock_config, mock_user_management):
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
        assert request.state.pending_session_tokens.refresh_token == "rt-xyz"
        assert "refresh_token" not in request.session
        assert "expires_at" not in request.session


class TestOpenServerSession:
    def test_tokens_are_encrypted_onto_the_row_at_creation(self, mock_config):
        from mlflow_oidc_auth.routers.auth import _open_server_session
        from mlflow_oidc_auth.session.token_vault import SessionTokens, get_token_vault

        mock_config.SESSION_COOKIE_MAX_AGE_SECONDS = 3600
        store_mock = MagicMock()
        store_mock.create_auth_session.return_value = "sid-new"
        tokens = SessionTokens(provider_id="default", expires_at=9999999999, refresh_token="rt-long-enough-not-to-appear-in-ciphertext-by-chance")

        with patch("mlflow_oidc_auth.routers.auth.config", mock_config), patch("mlflow_oidc_auth.routers.auth.store", store_mock):
            assert _open_server_session("u@x", provider_id="default", tokens=tokens) == "sid-new"

        kwargs = store_mock.create_auth_session.call_args.kwargs
        assert kwargs["provider_id"] == "default"
        assert tokens.refresh_token not in kwargs["encrypted_tokens"]
        assert get_token_vault().decrypt(kwargs["encrypted_tokens"]) == tokens

    def test_without_tokens_no_blob_is_stored(self, mock_config):
        from mlflow_oidc_auth.routers.auth import _open_server_session

        mock_config.SESSION_COOKIE_MAX_AGE_SECONDS = 3600
        store_mock = MagicMock()

        with patch("mlflow_oidc_auth.routers.auth.config", mock_config), patch("mlflow_oidc_auth.routers.auth.store", store_mock):
            _open_server_session("u@x")

        assert store_mock.create_auth_session.call_args.kwargs["encrypted_tokens"] is None


class TestLogoutIdTokenHint:
    """RP-initiated logout offers the session's ID token when it came from the default provider."""

    async def _logout(self, mock_request_with_session, mock_oauth, tokens):
        from urllib.parse import parse_qs, urlparse

        row = _FakeSessionRow(tokens)
        row.revoke_auth_session = MagicMock(return_value=True)
        request = mock_request_with_session({"session_id": "sid", "authenticated": True})
        request.state = SimpleNamespace(username="u@x", resolved_session=None)
        with patch("mlflow_oidc_auth.routers.auth.oauth", mock_oauth), patch("mlflow_oidc_auth.routers.auth.store", row):
            result = await logout(request)
        row.revoke_auth_session.assert_called_once_with("sid")
        return parse_qs(urlparse(result.headers["location"]).query)

    @pytest.mark.asyncio
    async def test_default_provider_id_token_is_offered(self, mock_request_with_session, mock_oauth):
        from mlflow_oidc_auth.session.token_vault import SessionTokens

        query = await self._logout(mock_request_with_session, mock_oauth, SessionTokens(provider_id="default", id_token="idt-default"))

        assert query["id_token_hint"] == ["idt-default"]
        assert "client_id" in query

    @pytest.mark.asyncio
    async def test_another_providers_id_token_is_never_sent_to_the_default_one(self, mock_request_with_session, mock_oauth):
        from mlflow_oidc_auth.session.token_vault import SessionTokens

        query = await self._logout(mock_request_with_session, mock_oauth, SessionTokens(provider_id="other", id_token="idt-other"))

        assert "id_token_hint" not in query

    @pytest.mark.asyncio
    async def test_no_tokens_means_no_hint(self, mock_request_with_session, mock_oauth):
        query = await self._logout(mock_request_with_session, mock_oauth, None)

        assert "id_token_hint" not in query


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


@pytest.fixture(autouse=True)
def in_flight_login_attempt(monkeypatch):
    """Answer the callback's state lookup with a live attempt (#316).

    The CSRF state moved out of the cookie and into an ``auth_state`` row, so a callback test
    that seeds ``session["oauth_state"]`` no longer describes anything. This stands in for the
    row: any non-empty ``state`` resolves to an attempt at the ``default`` provider, which is
    what these cases were always about — the user-management half of the callback.

    The state machinery itself is tested directly in ``test_auth_state.py`` and
    ``test_provider_login.py``.
    """
    from mlflow_oidc_auth.routers import auth as auth_router_mod
    from mlflow_oidc_auth.provider_registry import ProviderConfig, RegistryLoadResult
    from mlflow_oidc_auth.repository.auth_state import AuthAttempt

    monkeypatch.setattr(
        auth_router_mod.store,
        "consume_auth_state",
        lambda state: AuthAttempt(state=state, provider_id="default") if state else None,
        raising=False,
    )
    monkeypatch.setattr(
        auth_router_mod.config,
        "AUTH_PROVIDERS",
        RegistryLoadResult(providers=[ProviderConfig(id="default", type="oidc", audience="mlflow")], errors=[], source="legacy"),
        raising=False,
    )

    # Identity resolution and provisioning policy (#318) run inside the callback now, so the
    # store has to answer two questions: is this username taken, and is this identity bound.
    # A fresh principal at a jit provider — which is what these cases describe.
    class _Identities:
        def __init__(self):
            self.bound = {}

        def get_username_by_identity(self, provider_id, subject):
            return self.bound.get((provider_id, subject))

        def link(self, provider_id, subject, username, **kwargs):
            self.bound[(provider_id, subject)] = username
            return True

    monkeypatch.setattr(auth_router_mod.store, "user_identity_repo", _Identities(), raising=False)
    monkeypatch.setattr(auth_router_mod.store, "has_user", lambda username: False, raising=False)
    monkeypatch.setattr(auth_router_mod.store, "get_groups_for_user", lambda username: [], raising=False)


@pytest.fixture
def created_states(monkeypatch):
    """Record the login attempts ``login`` starts, in place of the old cookie key."""
    from mlflow_oidc_auth.routers import auth as auth_router_mod

    recorded = []

    def create(provider_id, **kwargs):
        recorded.append({"provider_id": provider_id, **kwargs})
        return "test_state_token"

    monkeypatch.setattr(auth_router_mod.store, "create_auth_state", create, raising=False)
    return recorded


@pytest.fixture
def no_attempt(monkeypatch):
    """No in-flight attempt matches — an unknown, replayed or expired state."""
    from mlflow_oidc_auth.routers import auth as auth_router_mod

    monkeypatch.setattr(auth_router_mod.store, "consume_auth_state", lambda state: None, raising=False)
