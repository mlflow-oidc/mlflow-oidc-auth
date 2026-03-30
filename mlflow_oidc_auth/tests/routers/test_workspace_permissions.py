"""Tests for the workspace permissions router.

Verifies all 8 CRUD endpoints for workspace user and group permission management,
including cache invalidation behavior (user CUD invalidates, group CUD does not).
"""

import pytest
from unittest.mock import MagicMock, patch

from mlflow_oidc_auth.routers.workspace_permissions import (
    workspace_permissions_router,
    list_workspace_users,
    list_workspace_groups,
    create_workspace_user_permission,
    create_workspace_group_permission,
    update_workspace_user_permission,
    update_workspace_group_permission,
    delete_workspace_user_permission,
    delete_workspace_group_permission,
    WORKSPACE_USERS,
    WORKSPACE_GROUPS,
    WORKSPACE_USER,
    WORKSPACE_GROUP,
)
from mlflow_oidc_auth.models.workspace import (
    WorkspaceUserPermissionRequest,
    WorkspaceGroupPermissionRequest,
    WorkspaceUserPermissionResponse,
    WorkspaceGroupPermissionResponse,
)
from mlflow_oidc_auth.entities.workspace import (
    WorkspacePermission,
    WorkspaceGroupPermission,
)


class TestRouterConfiguration:
    """Test workspace permissions router setup."""

    def test_router_prefix(self):
        """Test that the router has the correct v3 prefix."""
        assert workspace_permissions_router.prefix == "/api/3.0/mlflow/permissions/workspaces"

    def test_router_tags(self):
        """Test that the router has expected tags."""
        assert "workspace permissions" in workspace_permissions_router.tags

    def test_router_responses(self):
        """Test that the router has expected response codes."""
        assert 403 in workspace_permissions_router.responses
        assert 404 in workspace_permissions_router.responses

    def test_route_count(self):
        """Test that the router has exactly 8 routes."""
        assert len(workspace_permissions_router.routes) == 8

    def test_route_constants(self):
        """Test that route path constants are defined correctly."""
        assert WORKSPACE_USERS == "/{workspace}/users"
        assert WORKSPACE_GROUPS == "/{workspace}/groups"
        assert WORKSPACE_USER == "/{workspace}/users/{username}"
        assert WORKSPACE_GROUP == "/{workspace}/groups/{group_name}"


class TestListWorkspaceUsers:
    """Test list workspace users endpoint."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_permissions.store")
    async def test_list_workspace_users_returns_all_user_permissions(self, mock_store):
        """Test that list returns all user permissions for a workspace."""
        mock_store.list_workspace_permissions.return_value = [
            WorkspacePermission(
                workspace="ws1",
                user_id=1,
                permission="MANAGE",
                username="user1@example.com",
            ),
            WorkspacePermission(
                workspace="ws1",
                user_id=2,
                permission="READ",
                username="user2@example.com",
            ),
        ]

        result = await list_workspace_users(workspace="ws1", _="admin@example.com")

        assert len(result) == 2
        assert result[0].workspace == "ws1"
        assert result[0].username == "user1@example.com"
        assert result[0].permission == "MANAGE"
        assert result[1].username == "user2@example.com"
        assert result[1].permission == "READ"
        mock_store.list_workspace_permissions.assert_called_once_with("ws1")

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_permissions.store")
    async def test_list_workspace_users_empty(self, mock_store):
        """Test that list returns empty list when no permissions exist."""
        mock_store.list_workspace_permissions.return_value = []

        result = await list_workspace_users(workspace="ws1", _="admin@example.com")

        assert len(result) == 0

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_permissions.store")
    async def test_list_workspace_users_fallback_to_user_id(self, mock_store):
        """Test that username falls back to user_id string when username is None."""
        mock_store.list_workspace_permissions.return_value = [
            WorkspacePermission(workspace="ws1", user_id=99, permission="READ", username=None),
        ]

        result = await list_workspace_users(workspace="ws1", _="admin@example.com")

        assert result[0].username == "99"


class TestListWorkspaceGroups:
    """Test list workspace groups endpoint."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_permissions.store")
    async def test_list_workspace_groups_returns_all_group_permissions(self, mock_store):
        """Test that list returns all group permissions for a workspace."""
        mock_store.list_workspace_group_permissions.return_value = [
            WorkspaceGroupPermission(workspace="ws1", group_id=10, permission="MANAGE", group_name="admins"),
            WorkspaceGroupPermission(workspace="ws1", group_id=20, permission="READ", group_name="viewers"),
        ]

        result = await list_workspace_groups(workspace="ws1", _="admin@example.com")

        assert len(result) == 2
        assert result[0].group_name == "admins"
        assert result[0].permission == "MANAGE"
        assert result[1].group_name == "viewers"
        assert result[1].permission == "READ"
        mock_store.list_workspace_group_permissions.assert_called_once_with("ws1")

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_permissions.store")
    async def test_list_workspace_groups_fallback_to_group_id(self, mock_store):
        """Test that group_name falls back to group_id string when group_name is None."""
        mock_store.list_workspace_group_permissions.return_value = [
            WorkspaceGroupPermission(workspace="ws1", group_id=42, permission="EDIT", group_name=None),
        ]

        result = await list_workspace_groups(workspace="ws1", _="admin@example.com")

        assert result[0].group_name == "42"


class TestCreateWorkspaceUserPermission:
    """Test create workspace user permission endpoint."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_permissions.invalidate_workspace_permission")
    @patch("mlflow_oidc_auth.routers.workspace_permissions._validate_permission")
    @patch("mlflow_oidc_auth.routers.workspace_permissions.store")
    async def test_create_user_permission_success(self, mock_store, mock_validate, mock_invalidate):
        """Test successful creation of a user workspace permission."""
        mock_store.create_workspace_permission.return_value = WorkspacePermission(
            workspace="ws1",
            user_id=1,
            permission="MANAGE",
            username="user1@example.com",
        )

        body = WorkspaceUserPermissionRequest(username="user1@example.com", permission="MANAGE")
        result = await create_workspace_user_permission(body=body, workspace="ws1", current_username="admin@example.com")

        assert result.workspace == "ws1"
        assert result.username == "user1@example.com"
        assert result.permission == "MANAGE"
        mock_validate.assert_called_once_with("MANAGE")
        mock_store.create_workspace_permission.assert_called_once_with("ws1", "user1@example.com", "MANAGE")
        mock_invalidate.assert_called_once_with("user1@example.com", "ws1")

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_permissions.invalidate_workspace_permission")
    @patch("mlflow_oidc_auth.routers.workspace_permissions._validate_permission")
    @patch("mlflow_oidc_auth.routers.workspace_permissions.store")
    async def test_create_user_permission_calls_invalidate(self, mock_store, mock_validate, mock_invalidate):
        """Verify that cache invalidation is called after user permission creation."""
        mock_store.create_workspace_permission.return_value = WorkspacePermission(workspace="ws1", user_id=1, permission="READ", username="test@example.com")

        body = WorkspaceUserPermissionRequest(username="test@example.com", permission="READ")
        await create_workspace_user_permission(body=body, workspace="ws1", current_username="admin@example.com")

        mock_invalidate.assert_called_once_with("test@example.com", "ws1")


class TestCreateWorkspaceGroupPermission:
    """Test create workspace group permission endpoint."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_permissions.invalidate_workspace_permission")
    @patch("mlflow_oidc_auth.routers.workspace_permissions._validate_permission")
    @patch("mlflow_oidc_auth.routers.workspace_permissions.store")
    async def test_create_group_permission_success(self, mock_store, mock_validate, mock_invalidate):
        """Test successful creation of a group workspace permission."""
        mock_store.create_workspace_group_permission.return_value = WorkspaceGroupPermission(workspace="ws1", group_id=10, permission="EDIT", group_name="devs")

        body = WorkspaceGroupPermissionRequest(group_name="devs", permission="EDIT")
        result = await create_workspace_group_permission(body=body, workspace="ws1", current_username="admin@example.com")

        assert result.workspace == "ws1"
        assert result.group_name == "devs"
        assert result.permission == "EDIT"
        mock_validate.assert_called_once_with("EDIT")
        mock_store.create_workspace_group_permission.assert_called_once_with("ws1", "devs", "EDIT")

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_permissions.invalidate_workspace_permission")
    @patch("mlflow_oidc_auth.routers.workspace_permissions._validate_permission")
    @patch("mlflow_oidc_auth.routers.workspace_permissions.store")
    async def test_create_group_permission_does_not_invalidate_cache(self, mock_store, mock_validate, mock_invalidate):
        """Verify that group permission creation does NOT call invalidate_workspace_permission (per D-15)."""
        mock_store.create_workspace_group_permission.return_value = WorkspaceGroupPermission(
            workspace="ws1", group_id=10, permission="READ", group_name="viewers"
        )

        body = WorkspaceGroupPermissionRequest(group_name="viewers", permission="READ")
        await create_workspace_group_permission(body=body, workspace="ws1", current_username="admin@example.com")

        mock_invalidate.assert_not_called()


class TestUpdateWorkspaceUserPermission:
    """Test update workspace user permission endpoint."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_permissions.invalidate_workspace_permission")
    @patch("mlflow_oidc_auth.routers.workspace_permissions._validate_permission")
    @patch("mlflow_oidc_auth.routers.workspace_permissions.store")
    async def test_update_user_permission_success(self, mock_store, mock_validate, mock_invalidate):
        """Test successful update of a user workspace permission."""
        mock_store.update_workspace_permission.return_value = WorkspacePermission(workspace="ws1", user_id=1, permission="EDIT", username="user1@example.com")

        body = WorkspaceUserPermissionRequest(username="user1@example.com", permission="EDIT")
        result = await update_workspace_user_permission(
            body=body,
            workspace="ws1",
            username="user1@example.com",
            current_username="admin@example.com",
        )

        assert result.permission == "EDIT"
        mock_validate.assert_called_once_with("EDIT")
        mock_store.update_workspace_permission.assert_called_once_with("ws1", "user1@example.com", "EDIT")
        mock_invalidate.assert_called_once_with("user1@example.com", "ws1")


class TestUpdateWorkspaceGroupPermission:
    """Test update workspace group permission endpoint."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_permissions.invalidate_workspace_permission")
    @patch("mlflow_oidc_auth.routers.workspace_permissions._validate_permission")
    @patch("mlflow_oidc_auth.routers.workspace_permissions.store")
    async def test_update_group_permission_success(self, mock_store, mock_validate, mock_invalidate):
        """Test successful update of a group workspace permission."""
        mock_store.update_workspace_group_permission.return_value = WorkspaceGroupPermission(
            workspace="ws1", group_id=10, permission="MANAGE", group_name="devs"
        )

        body = WorkspaceGroupPermissionRequest(group_name="devs", permission="MANAGE")
        result = await update_workspace_group_permission(
            body=body,
            workspace="ws1",
            group_name="devs",
            current_username="admin@example.com",
        )

        assert result.permission == "MANAGE"
        mock_validate.assert_called_once_with("MANAGE")
        mock_store.update_workspace_group_permission.assert_called_once_with("ws1", "devs", "MANAGE")
        # Group updates do NOT invalidate cache per D-15
        mock_invalidate.assert_not_called()


class TestDeleteWorkspaceUserPermission:
    """Test delete workspace user permission endpoint."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_permissions.invalidate_workspace_permission")
    @patch("mlflow_oidc_auth.routers.workspace_permissions.store")
    async def test_delete_user_permission_success(self, mock_store, mock_invalidate):
        """Test successful deletion of a user workspace permission."""
        await delete_workspace_user_permission(
            workspace="ws1",
            username="user1@example.com",
            current_username="admin@example.com",
        )

        mock_store.delete_workspace_permission.assert_called_once_with("ws1", "user1@example.com")
        mock_invalidate.assert_called_once_with("user1@example.com", "ws1")


class TestDeleteWorkspaceGroupPermission:
    """Test delete workspace group permission endpoint."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_permissions.invalidate_workspace_permission")
    @patch("mlflow_oidc_auth.routers.workspace_permissions.store")
    async def test_delete_group_permission_success(self, mock_store, mock_invalidate):
        """Test successful deletion of a group workspace permission."""
        await delete_workspace_group_permission(workspace="ws1", group_name="devs", current_username="admin@example.com")

        mock_store.delete_workspace_group_permission.assert_called_once_with("ws1", "devs")
        # Group deletes do NOT invalidate cache per D-15
        mock_invalidate.assert_not_called()


class TestCacheInvalidationBehavior:
    """Verify cache invalidation patterns across all endpoints (D-13/D-14/D-15)."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_permissions.invalidate_workspace_permission")
    @patch("mlflow_oidc_auth.routers.workspace_permissions._validate_permission")
    @patch("mlflow_oidc_auth.routers.workspace_permissions.store")
    async def test_user_create_invalidates(self, mock_store, mock_validate, mock_invalidate):
        """User create must invalidate cache."""
        mock_store.create_workspace_permission.return_value = WorkspacePermission(workspace="ws", user_id=1, permission="READ", username="u")
        body = WorkspaceUserPermissionRequest(username="u", permission="READ")
        await create_workspace_user_permission(body=body, workspace="ws", current_username="admin")
        mock_invalidate.assert_called_once()

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_permissions.invalidate_workspace_permission")
    @patch("mlflow_oidc_auth.routers.workspace_permissions._validate_permission")
    @patch("mlflow_oidc_auth.routers.workspace_permissions.store")
    async def test_user_update_invalidates(self, mock_store, mock_validate, mock_invalidate):
        """User update must invalidate cache."""
        mock_store.update_workspace_permission.return_value = WorkspacePermission(workspace="ws", user_id=1, permission="EDIT", username="u")
        body = WorkspaceUserPermissionRequest(username="u", permission="EDIT")
        await update_workspace_user_permission(body=body, workspace="ws", username="u", current_username="admin")
        mock_invalidate.assert_called_once()

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_permissions.invalidate_workspace_permission")
    @patch("mlflow_oidc_auth.routers.workspace_permissions.store")
    async def test_user_delete_invalidates(self, mock_store, mock_invalidate):
        """User delete must invalidate cache."""
        await delete_workspace_user_permission(workspace="ws", username="u", current_username="admin")
        mock_invalidate.assert_called_once()

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_permissions.invalidate_workspace_permission")
    @patch("mlflow_oidc_auth.routers.workspace_permissions._validate_permission")
    @patch("mlflow_oidc_auth.routers.workspace_permissions.store")
    async def test_group_create_does_not_invalidate(self, mock_store, mock_validate, mock_invalidate):
        """Group create must NOT invalidate cache (per D-15)."""
        mock_store.create_workspace_group_permission.return_value = WorkspaceGroupPermission(workspace="ws", group_id=1, permission="READ", group_name="g")
        body = WorkspaceGroupPermissionRequest(group_name="g", permission="READ")
        await create_workspace_group_permission(body=body, workspace="ws", current_username="admin")
        mock_invalidate.assert_not_called()

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_permissions.invalidate_workspace_permission")
    @patch("mlflow_oidc_auth.routers.workspace_permissions._validate_permission")
    @patch("mlflow_oidc_auth.routers.workspace_permissions.store")
    async def test_group_update_does_not_invalidate(self, mock_store, mock_validate, mock_invalidate):
        """Group update must NOT invalidate cache (per D-15)."""
        mock_store.update_workspace_group_permission.return_value = WorkspaceGroupPermission(workspace="ws", group_id=1, permission="EDIT", group_name="g")
        body = WorkspaceGroupPermissionRequest(group_name="g", permission="EDIT")
        await update_workspace_group_permission(body=body, workspace="ws", group_name="g", current_username="admin")
        mock_invalidate.assert_not_called()

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_permissions.invalidate_workspace_permission")
    @patch("mlflow_oidc_auth.routers.workspace_permissions.store")
    async def test_group_delete_does_not_invalidate(self, mock_store, mock_invalidate):
        """Group delete must NOT invalidate cache (per D-15)."""
        await delete_workspace_group_permission(workspace="ws", group_name="g", current_username="admin")
        mock_invalidate.assert_not_called()


class TestResponseModels:
    """Test that response models match expected structure."""

    def test_user_permission_response_fields(self):
        """Test WorkspaceUserPermissionResponse has required fields."""
        resp = WorkspaceUserPermissionResponse(workspace="ws1", username="user@test.com", permission="READ")
        assert resp.workspace == "ws1"
        assert resp.username == "user@test.com"
        assert resp.permission == "READ"

    def test_group_permission_response_fields(self):
        """Test WorkspaceGroupPermissionResponse has required fields."""
        resp = WorkspaceGroupPermissionResponse(workspace="ws1", group_name="admins", permission="MANAGE")
        assert resp.workspace == "ws1"
        assert resp.group_name == "admins"
        assert resp.permission == "MANAGE"

    def test_user_permission_request_fields(self):
        """Test WorkspaceUserPermissionRequest has required fields."""
        req = WorkspaceUserPermissionRequest(username="user@test.com", permission="READ")
        assert req.username == "user@test.com"
        assert req.permission == "READ"

    def test_group_permission_request_fields(self):
        """Test WorkspaceGroupPermissionRequest has required fields."""
        req = WorkspaceGroupPermissionRequest(group_name="devs", permission="EDIT")
        assert req.group_name == "devs"
        assert req.permission == "EDIT"
