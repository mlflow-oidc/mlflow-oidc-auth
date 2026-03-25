"""Tests for OIDC workspace auto-create on login (WSOIDC-04).

Verifies that the OIDC callback auto-creates workspaces that don't exist
before assigning membership, handles failures gracefully, and respects
the feature flag.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestOidcWorkspaceAutoCreate:
    """Test workspace auto-creation during OIDC callback."""

    def _make_request_and_session(self, state="test-state"):
        """Create mock request and session for _process_oidc_callback_fastapi."""
        request = MagicMock()
        request.query_params = {
            "state": state,
            "code": "auth-code",
        }
        session = {
            "oauth_state": state,
        }
        return request, session

    def _make_config_mock(self, enable_workspaces=True, plugin=None, claim="workspace"):
        """Create mock config for workspace tests."""
        config_mock = MagicMock()
        config_mock.MLFLOW_ENABLE_WORKSPACES = enable_workspaces
        config_mock.OIDC_WORKSPACE_DETECTION_PLUGIN = plugin
        config_mock.OIDC_WORKSPACE_CLAIM_NAME = claim
        config_mock.OIDC_WORKSPACE_DEFAULT_PERMISSION = "READ"
        config_mock.OIDC_GROUP_DETECTION_PLUGIN = None
        config_mock.OIDC_GROUPS_ATTRIBUTE = "groups"
        config_mock.OIDC_ADMIN_GROUP_NAME = ["admin-group"]
        config_mock.OIDC_GROUP_NAME = ["user-group"]
        config_mock.OIDC_REDIRECT_URI = "http://localhost:8000/callback"
        config_mock.OIDC_DISCOVERY_URL = (
            "https://provider.com/.well-known/openid_configuration"
        )
        return config_mock

    @pytest.mark.asyncio
    @patch("mlflow.server.handlers._get_workspace_store")
    @patch("mlflow_oidc_auth.routers.auth.oauth")
    @patch("mlflow_oidc_auth.routers.auth.config")
    async def test_auto_creates_nonexistent_workspace(
        self, mock_config_obj, mock_oauth, mock_get_ws_store
    ):
        """When OIDC callback detects a workspace that doesn't exist, it auto-creates it."""
        from mlflow_oidc_auth.routers.auth import _process_oidc_callback_fastapi

        config_mock = self._make_config_mock(enable_workspaces=True)
        mock_config_obj.__dict__.update(config_mock.__dict__)
        # Proxy attribute access to config_mock
        for attr in dir(config_mock):
            if not attr.startswith("_"):
                setattr(mock_config_obj, attr, getattr(config_mock, attr))

        # Mock OAuth token response with workspace claim
        mock_oauth.oidc.authorize_access_token = AsyncMock(
            return_value={
                "access_token": "token",
                "id_token": "id-token",
                "userinfo": {
                    "email": "user@example.com",
                    "name": "Test User",
                    "groups": ["user-group"],
                    "workspace": "new-ws",
                },
            }
        )

        # Mock MLflow workspace store — workspace doesn't exist
        mlflow_ws_store = MagicMock()
        mlflow_ws_store.get_workspace.side_effect = Exception(
            "Workspace 'new-ws' not found"
        )
        mlflow_ws_store.create_workspace.return_value = MagicMock(name="new-ws")
        mock_get_ws_store.return_value = mlflow_ws_store

        request, session = self._make_request_and_session()

        with (
            patch("mlflow_oidc_auth.store.store") as mock_plugin_store,
            patch("mlflow_oidc_auth.user.create_user"),
            patch("mlflow_oidc_auth.user.populate_groups"),
            patch("mlflow_oidc_auth.user.update_user"),
        ):
            email, errors = await _process_oidc_callback_fastapi(request, session)

        # Workspace was auto-created with a Workspace object
        mlflow_ws_store.create_workspace.assert_called_once()
        ws_arg = mlflow_ws_store.create_workspace.call_args[0][0]
        assert ws_arg.name == "new-ws"
        assert ws_arg.description == ""
        assert email == "user@example.com"
        assert errors == []

    @pytest.mark.asyncio
    @patch("mlflow.server.handlers._get_workspace_store")
    @patch("mlflow_oidc_auth.routers.auth.oauth")
    @patch("mlflow_oidc_auth.routers.auth.config")
    async def test_does_not_create_existing_workspace(
        self, mock_config_obj, mock_oauth, mock_get_ws_store
    ):
        """When OIDC callback detects a workspace that already exists, no creation is attempted."""
        from mlflow_oidc_auth.routers.auth import _process_oidc_callback_fastapi

        config_mock = self._make_config_mock(enable_workspaces=True)
        for attr in dir(config_mock):
            if not attr.startswith("_"):
                setattr(mock_config_obj, attr, getattr(config_mock, attr))

        mock_oauth.oidc.authorize_access_token = AsyncMock(
            return_value={
                "access_token": "token",
                "id_token": "id-token",
                "userinfo": {
                    "email": "user@example.com",
                    "name": "Test User",
                    "groups": ["user-group"],
                    "workspace": "existing-ws",
                },
            }
        )

        # Mock MLflow workspace store — workspace exists
        mlflow_ws_store = MagicMock()
        mlflow_ws_store.get_workspace.return_value = MagicMock(name="existing-ws")
        mock_get_ws_store.return_value = mlflow_ws_store

        request, session = self._make_request_and_session()

        with (
            patch("mlflow_oidc_auth.store.store") as mock_plugin_store,
            patch("mlflow_oidc_auth.user.create_user"),
            patch("mlflow_oidc_auth.user.populate_groups"),
            patch("mlflow_oidc_auth.user.update_user"),
        ):
            email, errors = await _process_oidc_callback_fastapi(request, session)

        # Workspace was NOT created (it already exists)
        mlflow_ws_store.create_workspace.assert_not_called()
        assert email == "user@example.com"
        assert errors == []

    @pytest.mark.asyncio
    @patch("mlflow.server.handlers._get_workspace_store")
    @patch("mlflow_oidc_auth.routers.auth.oauth")
    @patch("mlflow_oidc_auth.routers.auth.config")
    async def test_auto_create_failure_does_not_block_login(
        self, mock_config_obj, mock_oauth, mock_get_ws_store
    ):
        """When workspace auto-creation fails, login continues successfully."""
        from mlflow_oidc_auth.routers.auth import _process_oidc_callback_fastapi

        config_mock = self._make_config_mock(enable_workspaces=True)
        for attr in dir(config_mock):
            if not attr.startswith("_"):
                setattr(mock_config_obj, attr, getattr(config_mock, attr))

        mock_oauth.oidc.authorize_access_token = AsyncMock(
            return_value={
                "access_token": "token",
                "id_token": "id-token",
                "userinfo": {
                    "email": "user@example.com",
                    "name": "Test User",
                    "groups": ["user-group"],
                    "workspace": "bad--name",
                },
            }
        )

        # Mock MLflow workspace store — workspace doesn't exist and creation fails
        mlflow_ws_store = MagicMock()
        mlflow_ws_store.get_workspace.side_effect = Exception("not found")
        mlflow_ws_store.create_workspace.side_effect = Exception(
            "Invalid workspace name"
        )
        mock_get_ws_store.return_value = mlflow_ws_store

        request, session = self._make_request_and_session()

        with (
            patch("mlflow_oidc_auth.store.store") as mock_plugin_store,
            patch("mlflow_oidc_auth.user.create_user"),
            patch("mlflow_oidc_auth.user.populate_groups"),
            patch("mlflow_oidc_auth.user.update_user"),
        ):
            email, errors = await _process_oidc_callback_fastapi(request, session)

        # Login succeeds even though workspace auto-create failed
        assert email == "user@example.com"
        assert errors == []

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.auth.oauth")
    @patch("mlflow_oidc_auth.routers.auth.config")
    async def test_no_auto_create_when_workspaces_disabled(
        self, mock_config_obj, mock_oauth
    ):
        """When MLFLOW_ENABLE_WORKSPACES is false, no workspace auto-creation happens."""
        from mlflow_oidc_auth.routers.auth import _process_oidc_callback_fastapi

        config_mock = self._make_config_mock(enable_workspaces=False)
        for attr in dir(config_mock):
            if not attr.startswith("_"):
                setattr(mock_config_obj, attr, getattr(config_mock, attr))

        mock_oauth.oidc.authorize_access_token = AsyncMock(
            return_value={
                "access_token": "token",
                "id_token": "id-token",
                "userinfo": {
                    "email": "user@example.com",
                    "name": "Test User",
                    "groups": ["user-group"],
                    "workspace": "some-ws",
                },
            }
        )

        request, session = self._make_request_and_session()

        with (
            patch("mlflow_oidc_auth.store.store") as mock_plugin_store,
            patch("mlflow_oidc_auth.user.create_user"),
            patch("mlflow_oidc_auth.user.populate_groups"),
            patch("mlflow_oidc_auth.user.update_user"),
        ):
            # _get_workspace_store should never be called since workspaces are disabled
            with patch("mlflow.server.handlers._get_workspace_store") as mock_get_ws:
                email, errors = await _process_oidc_callback_fastapi(request, session)
                mock_get_ws.assert_not_called()

        assert email == "user@example.com"
        assert errors == []
