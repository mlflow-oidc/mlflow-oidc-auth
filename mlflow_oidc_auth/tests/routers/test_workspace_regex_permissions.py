"""Tests for the workspace regex permissions router.

Verifies all 8 CRUD endpoints for workspace user-regex and group-regex
permission management, including full cache flush behavior (D-09).
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock


class TestRouterConfiguration:
    """Test workspace regex permissions router setup."""

    def test_router_prefix(self):
        """Test that the router has the correct v3 prefix."""
        from mlflow_oidc_auth.routers.workspace_regex_permissions import (
            workspace_regex_permissions_router,
        )

        assert workspace_regex_permissions_router.prefix == "/api/3.0/mlflow/permissions/workspaces/regex"

    def test_router_tags(self):
        """Test that the router has expected tags."""
        from mlflow_oidc_auth.routers.workspace_regex_permissions import (
            workspace_regex_permissions_router,
        )

        assert "workspace regex permissions" in workspace_regex_permissions_router.tags

    def test_router_responses(self):
        """Test that the router has expected response codes."""
        from mlflow_oidc_auth.routers.workspace_regex_permissions import (
            workspace_regex_permissions_router,
        )

        assert 403 in workspace_regex_permissions_router.responses
        assert 404 in workspace_regex_permissions_router.responses

    def test_route_count(self):
        """Test that the router has exactly 8 routes."""
        from mlflow_oidc_auth.routers.workspace_regex_permissions import (
            workspace_regex_permissions_router,
        )

        assert len(workspace_regex_permissions_router.routes) == 8


class TestCreateUserRegexPermission:
    """Test create user regex workspace permission endpoint."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.flush_workspace_cache")
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions._validate_permission")
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.store")
    async def test_create_calls_store_and_flushes_cache(self, mock_store, mock_validate, mock_flush):
        """Test that POST /user calls store.create_workspace_regex_permission and flushes cache."""
        from mlflow_oidc_auth.routers.workspace_regex_permissions import (
            create_user_regex_permission,
        )
        from mlflow_oidc_auth.models.workspace import WorkspaceRegexPermissionRequest

        mock_perm = MagicMock()
        mock_perm.id = 1
        mock_perm.regex = "^prod-.*"
        mock_perm.priority = 10
        mock_perm.permission = "MANAGE"
        mock_store.create_workspace_regex_permission.return_value = mock_perm

        body = WorkspaceRegexPermissionRequest(
            regex="^prod-.*",
            priority=10,
            permission="MANAGE",
            username="user1@example.com",
        )
        result = await create_user_regex_permission(body=body, admin_username="admin@example.com")

        mock_validate.assert_called_once_with("MANAGE")
        mock_store.create_workspace_regex_permission.assert_called_once_with("^prod-.*", 10, "MANAGE", "user1@example.com")
        mock_flush.assert_called_once()
        assert result.id == 1
        assert result.regex == "^prod-.*"
        assert result.priority == 10
        assert result.permission == "MANAGE"
        assert result.username == "user1@example.com"


class TestListUserRegexPermissions:
    """Test list user regex workspace permissions endpoint."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.store")
    async def test_list_calls_store(self, mock_store):
        """Test that GET /user calls store.list_all_workspace_regex_permissions."""
        from mlflow_oidc_auth.routers.workspace_regex_permissions import (
            list_user_regex_permissions,
        )

        mock_perm = MagicMock()
        mock_perm.id = 1
        mock_perm.regex = "^prod-.*"
        mock_perm.priority = 10
        mock_perm.permission = "MANAGE"
        mock_perm.user_id = 42
        mock_store.list_all_workspace_regex_permissions.return_value = [mock_perm]

        result = await list_user_regex_permissions(_="admin@example.com")

        mock_store.list_all_workspace_regex_permissions.assert_called_once()
        assert len(result) == 1


class TestUpdateUserRegexPermission:
    """Test update user regex workspace permission endpoint."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.flush_workspace_cache")
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions._validate_permission")
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.store")
    async def test_update_calls_store_and_flushes_cache(self, mock_store, mock_validate, mock_flush):
        """Test that PATCH /user/{id} calls store.update_workspace_regex_permission and flushes cache."""
        from mlflow_oidc_auth.routers.workspace_regex_permissions import (
            update_user_regex_permission,
        )
        from mlflow_oidc_auth.models.workspace import WorkspaceRegexPermissionRequest

        mock_perm = MagicMock()
        mock_perm.id = 5
        mock_perm.regex = "^staging-.*"
        mock_perm.priority = 20
        mock_perm.permission = "READ"
        mock_store.update_workspace_regex_permission.return_value = mock_perm

        body = WorkspaceRegexPermissionRequest(
            regex="^staging-.*",
            priority=20,
            permission="READ",
            username="user1@example.com",
        )
        result = await update_user_regex_permission(body=body, permission_id=5, admin_username="admin@example.com")

        mock_validate.assert_called_once_with("READ")
        mock_store.update_workspace_regex_permission.assert_called_once_with("^staging-.*", 20, "READ", "user1@example.com", 5)
        mock_flush.assert_called_once()
        assert result.id == 5


class TestDeleteUserRegexPermission:
    """Test delete user regex workspace permission endpoint."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.flush_workspace_cache")
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.store")
    async def test_delete_calls_store_and_flushes_cache(self, mock_store, mock_flush):
        """Test that DELETE /user/{id} calls store.delete_workspace_regex_permission and flushes cache."""
        from mlflow_oidc_auth.routers.workspace_regex_permissions import (
            delete_user_regex_permission,
        )

        await delete_user_regex_permission(
            permission_id=5,
            username="user1@example.com",
            admin_username="admin@example.com",
        )

        mock_store.delete_workspace_regex_permission.assert_called_once_with("user1@example.com", 5)
        mock_flush.assert_called_once()


class TestCreateGroupRegexPermission:
    """Test create group regex workspace permission endpoint."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.flush_workspace_cache")
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions._validate_permission")
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.store")
    async def test_create_calls_store_and_flushes_cache(self, mock_store, mock_validate, mock_flush):
        """Test that POST /group calls store.create_workspace_group_regex_permission and flushes cache."""
        from mlflow_oidc_auth.routers.workspace_regex_permissions import (
            create_group_regex_permission,
        )
        from mlflow_oidc_auth.models.workspace import (
            WorkspaceGroupRegexPermissionRequest,
        )

        mock_perm = MagicMock()
        mock_perm.id = 2
        mock_perm.regex = "^team-.*"
        mock_perm.priority = 5
        mock_perm.permission = "EDIT"
        mock_store.create_workspace_group_regex_permission.return_value = mock_perm

        body = WorkspaceGroupRegexPermissionRequest(regex="^team-.*", priority=5, permission="EDIT", group_name="devs")
        result = await create_group_regex_permission(body=body, admin_username="admin@example.com")

        mock_validate.assert_called_once_with("EDIT")
        mock_store.create_workspace_group_regex_permission.assert_called_once_with("devs", "^team-.*", 5, "EDIT")
        mock_flush.assert_called_once()
        assert result.id == 2
        assert result.group_name == "devs"


class TestListGroupRegexPermissions:
    """Test list group regex workspace permissions endpoint."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.store")
    async def test_list_calls_store(self, mock_store):
        """Test that GET /group calls store.list_all_workspace_group_regex_permissions."""
        from mlflow_oidc_auth.routers.workspace_regex_permissions import (
            list_group_regex_permissions,
        )

        mock_perm = MagicMock()
        mock_perm.id = 2
        mock_perm.regex = "^team-.*"
        mock_perm.priority = 5
        mock_perm.permission = "EDIT"
        mock_perm.group_id = 10
        mock_store.list_all_workspace_group_regex_permissions.return_value = [mock_perm]

        result = await list_group_regex_permissions(_="admin@example.com")

        mock_store.list_all_workspace_group_regex_permissions.assert_called_once()
        assert len(result) == 1


class TestUpdateGroupRegexPermission:
    """Test update group regex workspace permission endpoint."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.flush_workspace_cache")
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions._validate_permission")
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.store")
    async def test_update_calls_store_and_flushes_cache(self, mock_store, mock_validate, mock_flush):
        """Test that PATCH /group/{id} calls store.update_workspace_group_regex_permission and flushes cache."""
        from mlflow_oidc_auth.routers.workspace_regex_permissions import (
            update_group_regex_permission,
        )
        from mlflow_oidc_auth.models.workspace import (
            WorkspaceGroupRegexPermissionRequest,
        )

        mock_perm = MagicMock()
        mock_perm.id = 3
        mock_perm.regex = "^staging-.*"
        mock_perm.priority = 15
        mock_perm.permission = "READ"
        mock_store.update_workspace_group_regex_permission.return_value = mock_perm

        body = WorkspaceGroupRegexPermissionRequest(regex="^staging-.*", priority=15, permission="READ", group_name="viewers")
        result = await update_group_regex_permission(body=body, permission_id=3, admin_username="admin@example.com")

        mock_validate.assert_called_once_with("READ")
        mock_store.update_workspace_group_regex_permission.assert_called_once_with(3, "viewers", "^staging-.*", 15, "READ")
        mock_flush.assert_called_once()
        assert result.id == 3


class TestDeleteGroupRegexPermission:
    """Test delete group regex workspace permission endpoint."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.flush_workspace_cache")
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.store")
    async def test_delete_calls_store_and_flushes_cache(self, mock_store, mock_flush):
        """Test that DELETE /group/{id} calls store.delete_workspace_group_regex_permission and flushes cache."""
        from mlflow_oidc_auth.routers.workspace_regex_permissions import (
            delete_group_regex_permission,
        )

        await delete_group_regex_permission(permission_id=3, group_name="viewers", admin_username="admin@example.com")

        mock_store.delete_workspace_group_regex_permission.assert_called_once_with("viewers", 3)
        mock_flush.assert_called_once()


class TestCacheFlushBehavior:
    """Verify all 6 CUD ops flush cache and list ops do not."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.flush_workspace_cache")
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions._validate_permission")
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.store")
    async def test_user_create_flushes_cache(self, mock_store, mock_validate, mock_flush):
        """User regex create must flush cache."""
        from mlflow_oidc_auth.routers.workspace_regex_permissions import (
            create_user_regex_permission,
        )
        from mlflow_oidc_auth.models.workspace import WorkspaceRegexPermissionRequest

        mock_perm = MagicMock()
        mock_perm.id = 1
        mock_perm.regex = ".*"
        mock_perm.priority = 1
        mock_perm.permission = "READ"
        mock_store.create_workspace_regex_permission.return_value = mock_perm

        body = WorkspaceRegexPermissionRequest(regex=".*", priority=1, permission="READ", username="u")
        await create_user_regex_permission(body=body, admin_username="admin")
        mock_flush.assert_called_once()

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.flush_workspace_cache")
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions._validate_permission")
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.store")
    async def test_user_update_flushes_cache(self, mock_store, mock_validate, mock_flush):
        """User regex update must flush cache."""
        from mlflow_oidc_auth.routers.workspace_regex_permissions import (
            update_user_regex_permission,
        )
        from mlflow_oidc_auth.models.workspace import WorkspaceRegexPermissionRequest

        mock_perm = MagicMock()
        mock_perm.id = 1
        mock_perm.regex = ".*"
        mock_perm.priority = 1
        mock_perm.permission = "READ"
        mock_store.update_workspace_regex_permission.return_value = mock_perm

        body = WorkspaceRegexPermissionRequest(regex=".*", priority=1, permission="READ", username="u")
        await update_user_regex_permission(body=body, permission_id=1, admin_username="admin")
        mock_flush.assert_called_once()

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.flush_workspace_cache")
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.store")
    async def test_user_delete_flushes_cache(self, mock_store, mock_flush):
        """User regex delete must flush cache."""
        from mlflow_oidc_auth.routers.workspace_regex_permissions import (
            delete_user_regex_permission,
        )

        await delete_user_regex_permission(permission_id=1, username="u", admin_username="admin")
        mock_flush.assert_called_once()

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.flush_workspace_cache")
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions._validate_permission")
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.store")
    async def test_group_create_flushes_cache(self, mock_store, mock_validate, mock_flush):
        """Group regex create must flush cache."""
        from mlflow_oidc_auth.routers.workspace_regex_permissions import (
            create_group_regex_permission,
        )
        from mlflow_oidc_auth.models.workspace import (
            WorkspaceGroupRegexPermissionRequest,
        )

        mock_perm = MagicMock()
        mock_perm.id = 1
        mock_perm.regex = ".*"
        mock_perm.priority = 1
        mock_perm.permission = "READ"
        mock_store.create_workspace_group_regex_permission.return_value = mock_perm

        body = WorkspaceGroupRegexPermissionRequest(regex=".*", priority=1, permission="READ", group_name="g")
        await create_group_regex_permission(body=body, admin_username="admin")
        mock_flush.assert_called_once()

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.flush_workspace_cache")
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions._validate_permission")
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.store")
    async def test_group_update_flushes_cache(self, mock_store, mock_validate, mock_flush):
        """Group regex update must flush cache."""
        from mlflow_oidc_auth.routers.workspace_regex_permissions import (
            update_group_regex_permission,
        )
        from mlflow_oidc_auth.models.workspace import (
            WorkspaceGroupRegexPermissionRequest,
        )

        mock_perm = MagicMock()
        mock_perm.id = 1
        mock_perm.regex = ".*"
        mock_perm.priority = 1
        mock_perm.permission = "READ"
        mock_store.update_workspace_group_regex_permission.return_value = mock_perm

        body = WorkspaceGroupRegexPermissionRequest(regex=".*", priority=1, permission="READ", group_name="g")
        await update_group_regex_permission(body=body, permission_id=1, admin_username="admin")
        mock_flush.assert_called_once()

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.flush_workspace_cache")
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.store")
    async def test_group_delete_flushes_cache(self, mock_store, mock_flush):
        """Group regex delete must flush cache."""
        from mlflow_oidc_auth.routers.workspace_regex_permissions import (
            delete_group_regex_permission,
        )

        await delete_group_regex_permission(permission_id=1, group_name="g", admin_username="admin")
        mock_flush.assert_called_once()

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.flush_workspace_cache")
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.store")
    async def test_list_user_does_not_flush(self, mock_store, mock_flush):
        """List user regex must NOT flush cache."""
        from mlflow_oidc_auth.routers.workspace_regex_permissions import (
            list_user_regex_permissions,
        )

        mock_store.list_all_workspace_regex_permissions.return_value = []
        await list_user_regex_permissions(_="admin")
        mock_flush.assert_not_called()

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.flush_workspace_cache")
    @patch("mlflow_oidc_auth.routers.workspace_regex_permissions.store")
    async def test_list_group_does_not_flush(self, mock_store, mock_flush):
        """List group regex must NOT flush cache."""
        from mlflow_oidc_auth.routers.workspace_regex_permissions import (
            list_group_regex_permissions,
        )

        mock_store.list_all_workspace_group_regex_permissions.return_value = []
        await list_group_regex_permissions(_="admin")
        mock_flush.assert_not_called()
