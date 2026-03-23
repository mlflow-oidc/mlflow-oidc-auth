"""
Tests for workspace header extraction in AuthMiddleware.

Tests that X-MLFLOW-WORKSPACE header is only extracted when
MLFLOW_ENABLE_WORKSPACES is True, and ignored otherwise.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import Response

from mlflow_oidc_auth.entities.auth_context import AuthContext
from mlflow_oidc_auth.middleware.auth_middleware import AuthMiddleware


class TestWorkspaceHeaderExtraction:
    """Test workspace header handling in AuthMiddleware."""

    @pytest.fixture
    def auth_middleware(self, test_fastapi_app):
        """Create AuthMiddleware instance for testing."""
        return AuthMiddleware(test_fastapi_app)

    @pytest.mark.asyncio
    async def test_workspace_header_ignored_when_disabled(
        self, auth_middleware, create_mock_request, mock_store
    ):
        """When MLFLOW_ENABLE_WORKSPACES=False, workspace header is ignored even if present."""
        mock_config = MagicMock()
        mock_config.MLFLOW_ENABLE_WORKSPACES = False

        request = create_mock_request(
            path="/api/2.0/mlflow/experiments/list",
            headers={
                "x-mlflow-workspace": "my-workspace",
                "authorization": "Bearer valid_token",
            },
        )

        async def mock_call_next(req):
            return Response(content="OK", status_code=200)

        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.config", mock_config),
            patch(
                "mlflow_oidc_auth.middleware.auth_middleware.validate_token"
            ) as mock_validate,
            patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store),
        ):
            mock_validate.return_value = {
                "email": "user@example.com",
                "preferred_username": "user@example.com",
            }

            await auth_middleware.dispatch(request, mock_call_next)

            auth_context = request.scope.get("mlflow_oidc_auth")
            assert isinstance(auth_context, AuthContext)
            assert auth_context.username == "user@example.com"
            assert auth_context.workspace is None

    @pytest.mark.asyncio
    async def test_workspace_header_extracted_when_enabled(
        self, auth_middleware, create_mock_request, mock_store
    ):
        """When MLFLOW_ENABLE_WORKSPACES=True, X-MLFLOW-WORKSPACE header is extracted."""
        mock_config = MagicMock()
        mock_config.MLFLOW_ENABLE_WORKSPACES = True

        request = create_mock_request(
            path="/api/2.0/mlflow/experiments/list",
            headers={
                "x-mlflow-workspace": "my-workspace",
                "authorization": "Bearer valid_token",
            },
        )

        async def mock_call_next(req):
            return Response(content="OK", status_code=200)

        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.config", mock_config),
            patch(
                "mlflow_oidc_auth.middleware.auth_middleware.validate_token"
            ) as mock_validate,
            patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store),
        ):
            mock_validate.return_value = {
                "email": "user@example.com",
                "preferred_username": "user@example.com",
            }

            await auth_middleware.dispatch(request, mock_call_next)

            auth_context = request.scope.get("mlflow_oidc_auth")
            assert isinstance(auth_context, AuthContext)
            assert auth_context.workspace == "my-workspace"

    @pytest.mark.asyncio
    async def test_workspace_header_none_when_enabled_no_header(
        self, auth_middleware, create_mock_request, mock_store
    ):
        """When MLFLOW_ENABLE_WORKSPACES=True but no header, workspace is None."""
        mock_config = MagicMock()
        mock_config.MLFLOW_ENABLE_WORKSPACES = True

        request = create_mock_request(
            path="/api/2.0/mlflow/experiments/list",
            headers={"authorization": "Bearer valid_token"},
        )

        async def mock_call_next(req):
            return Response(content="OK", status_code=200)

        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.config", mock_config),
            patch(
                "mlflow_oidc_auth.middleware.auth_middleware.validate_token"
            ) as mock_validate,
            patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store),
        ):
            mock_validate.return_value = {
                "email": "user@example.com",
                "preferred_username": "user@example.com",
            }

            await auth_middleware.dispatch(request, mock_call_next)

            auth_context = request.scope.get("mlflow_oidc_auth")
            assert isinstance(auth_context, AuthContext)
            assert auth_context.workspace is None

    @pytest.mark.asyncio
    async def test_auth_context_always_has_username_and_admin(
        self, auth_middleware, create_mock_request, mock_store
    ):
        """Regardless of workspace flag, AuthContext always has username and is_admin."""
        mock_config = MagicMock()
        mock_config.MLFLOW_ENABLE_WORKSPACES = False

        request = create_mock_request(
            path="/api/2.0/mlflow/experiments/list",
            headers={"authorization": "Bearer admin_token"},
        )

        async def mock_call_next(req):
            return Response(content="OK", status_code=200)

        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.config", mock_config),
            patch(
                "mlflow_oidc_auth.middleware.auth_middleware.validate_token"
            ) as mock_validate,
            patch("mlflow_oidc_auth.middleware.auth_middleware.store", mock_store),
        ):
            mock_validate.return_value = {
                "email": "admin@example.com",
                "preferred_username": "admin@example.com",
            }

            await auth_middleware.dispatch(request, mock_call_next)

            auth_context = request.scope.get("mlflow_oidc_auth")
            assert isinstance(auth_context, AuthContext)
            assert auth_context.username == "admin@example.com"
            assert auth_context.is_admin is True
