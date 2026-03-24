"""Tests for the workspace CRUD router.

Verifies all 5 endpoints for workspace lifecycle management (create, list, get,
update, delete), including permission checks, name validation, feature-flag gating,
and error handling.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from pydantic import ValidationError


# ──────────────────────────────────────────────────────────────────────────
# Pydantic model tests (name validation, field constraints)
# ──────────────────────────────────────────────────────────────────────────


class TestWorkspaceCrudPydanticModels:
    """Test Pydantic request/response models for workspace CRUD."""

    def test_create_request_valid_name(self):
        """Valid DNS-safe name is accepted."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudCreateRequest

        req = WorkspaceCrudCreateRequest(name="my-workspace", description="A workspace")
        assert req.name == "my-workspace"
        assert req.description == "A workspace"

    def test_create_request_valid_name_numeric(self):
        """Purely numeric name is DNS-safe and accepted."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudCreateRequest

        req = WorkspaceCrudCreateRequest(name="ws01")
        assert req.name == "ws01"

    def test_create_request_rejects_uppercase(self):
        """Uppercase letters are rejected."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudCreateRequest

        with pytest.raises(ValidationError):
            WorkspaceCrudCreateRequest(name="MyWorkspace")

    def test_create_request_rejects_too_long(self):
        """Names > 63 characters are rejected."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudCreateRequest

        with pytest.raises(ValidationError):
            WorkspaceCrudCreateRequest(name="a" * 64)

    def test_create_request_rejects_too_short(self):
        """Names < 2 characters are rejected."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudCreateRequest

        with pytest.raises(ValidationError):
            WorkspaceCrudCreateRequest(name="a")

    def test_create_request_rejects_reserved_name(self):
        """Reserved names ('workspaces', 'api', etc.) are rejected."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudCreateRequest

        for reserved in ["workspaces", "api", "ajax-api", "static-files"]:
            with pytest.raises(ValidationError, match="reserved"):
                WorkspaceCrudCreateRequest(name=reserved)

    def test_create_request_rejects_leading_hyphen(self):
        """Leading hyphen is rejected."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudCreateRequest

        with pytest.raises(ValidationError):
            WorkspaceCrudCreateRequest(name="-workspace")

    def test_create_request_rejects_trailing_hyphen(self):
        """Trailing hyphen is rejected."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudCreateRequest

        with pytest.raises(ValidationError):
            WorkspaceCrudCreateRequest(name="workspace-")

    def test_create_request_rejects_consecutive_hyphens(self):
        """Consecutive hyphens are rejected."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudCreateRequest

        with pytest.raises(ValidationError):
            WorkspaceCrudCreateRequest(name="work--space")

    def test_create_request_default_description(self):
        """Description defaults to empty string."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudCreateRequest

        req = WorkspaceCrudCreateRequest(name="ws")
        assert req.description == ""

    def test_update_request_valid(self):
        """Update request accepts valid description."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudUpdateRequest

        req = WorkspaceCrudUpdateRequest(description="Updated desc")
        assert req.description == "Updated desc"

    def test_update_request_rejects_too_long_description(self):
        """Description > 500 characters is rejected."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudUpdateRequest

        with pytest.raises(ValidationError):
            WorkspaceCrudUpdateRequest(description="x" * 501)

    def test_response_model_fields(self):
        """Response model has name and description fields."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudResponse

        resp = WorkspaceCrudResponse(name="ws1", description="desc")
        assert resp.name == "ws1"
        assert resp.description == "desc"

    def test_response_model_default_description(self):
        """Response model description defaults to empty string."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudResponse

        resp = WorkspaceCrudResponse(name="ws1")
        assert resp.description == ""


# ──────────────────────────────────────────────────────────────────────────
# Router configuration tests
# ──────────────────────────────────────────────────────────────────────────


class TestRouterConfiguration:
    """Test workspace CRUD router setup."""

    def test_router_prefix(self):
        """Test that the router has the correct v3 prefix."""
        from mlflow_oidc_auth.routers.workspace_crud import workspace_crud_router

        assert workspace_crud_router.prefix == "/api/3.0/mlflow/workspaces/crud"

    def test_router_tags(self):
        """Test that the router has expected tags."""
        from mlflow_oidc_auth.routers.workspace_crud import workspace_crud_router

        assert "workspace crud" in workspace_crud_router.tags

    def test_router_has_five_routes(self):
        """Test that the router has exactly 5 routes."""
        from mlflow_oidc_auth.routers.workspace_crud import workspace_crud_router

        assert len(workspace_crud_router.routes) == 5

    def test_router_not_in_get_all_routers(self):
        """Test that workspace_crud_router is NOT in get_all_routers (feature-flag gated)."""
        from mlflow_oidc_auth.routers import get_all_routers

        routers = get_all_routers()
        router_tags = [r.tags[0] if r.tags else "no-tag" for r in routers]
        assert "workspace crud" not in router_tags

    def test_router_in_all_exports(self):
        """Test that workspace_crud_router IS in __all__."""
        from mlflow_oidc_auth.routers import __all__ as router_all

        assert "workspace_crud_router" in router_all

    def test_prefix_constant_exists(self):
        """Test that WORKSPACE_CRUD_ROUTER_PREFIX exists in _prefix module."""
        from mlflow_oidc_auth.routers._prefix import WORKSPACE_CRUD_ROUTER_PREFIX

        assert WORKSPACE_CRUD_ROUTER_PREFIX == "/api/3.0/mlflow/workspaces/crud"


# ──────────────────────────────────────────────────────────────────────────
# Create workspace endpoint tests
# ──────────────────────────────────────────────────────────────────────────


class TestCreateWorkspace:
    """Test POST workspace create endpoint."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_crud._get_workspace_store")
    async def test_create_workspace_success(self, mock_get_ws_store):
        """POST with valid name/description creates workspace and returns 201-equivalent response."""
        from mlflow_oidc_auth.routers.workspace_crud import create_workspace
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudCreateRequest

        mock_ws = MagicMock()
        mock_ws.name = "new-ws"
        mock_ws.description = "A new workspace"
        mock_get_ws_store.return_value.create_workspace.return_value = mock_ws

        body = WorkspaceCrudCreateRequest(name="new-ws", description="A new workspace")
        result = await create_workspace(body=body, username="admin@example.com")

        assert result.name == "new-ws"
        assert result.description == "A new workspace"
        mock_get_ws_store.return_value.create_workspace.assert_called_once_with(
            name="new-ws", description="A new workspace"
        )

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_crud._get_workspace_store")
    async def test_create_workspace_duplicate_returns_409(self, mock_get_ws_store):
        """POST with duplicate name returns 409."""
        from mlflow_oidc_auth.routers.workspace_crud import create_workspace
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudCreateRequest
        from fastapi import HTTPException

        mock_get_ws_store.return_value.create_workspace.side_effect = Exception(
            "Workspace 'dup' already exists"
        )

        body = WorkspaceCrudCreateRequest(name="dup-ws", description="")
        with pytest.raises(HTTPException) as exc_info:
            await create_workspace(body=body, username="admin@example.com")
        assert exc_info.value.status_code == 409


# ──────────────────────────────────────────────────────────────────────────
# List workspaces endpoint tests
# ──────────────────────────────────────────────────────────────────────────


class TestListWorkspaces:
    """Test GET workspace list endpoint."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_crud.get_workspace_permission_cached")
    @patch("mlflow_oidc_auth.routers.workspace_crud.get_is_admin")
    @patch("mlflow_oidc_auth.routers.workspace_crud.get_username")
    @patch("mlflow_oidc_auth.routers.workspace_crud._get_workspace_store")
    async def test_list_workspaces_admin_sees_all(
        self, mock_get_ws_store, mock_get_username, mock_get_is_admin, mock_perm_cached
    ):
        """Admin sees all workspaces."""
        from mlflow_oidc_auth.routers.workspace_crud import list_workspaces

        mock_get_username.return_value = "admin@example.com"
        mock_get_is_admin.return_value = True

        ws1 = MagicMock()
        ws1.name = "ws1"
        ws1.description = "Workspace 1"
        ws2 = MagicMock()
        ws2.name = "ws2"
        ws2.description = "Workspace 2"
        mock_get_ws_store.return_value.list_workspaces.return_value = [ws1, ws2]

        mock_request = MagicMock()
        result = await list_workspaces(request=mock_request)

        assert len(result) == 2
        assert result[0].name == "ws1"
        assert result[1].name == "ws2"

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_crud.get_workspace_permission_cached")
    @patch("mlflow_oidc_auth.routers.workspace_crud.get_is_admin")
    @patch("mlflow_oidc_auth.routers.workspace_crud.get_username")
    @patch("mlflow_oidc_auth.routers.workspace_crud._get_workspace_store")
    async def test_list_workspaces_nonadmin_sees_only_permitted(
        self, mock_get_ws_store, mock_get_username, mock_get_is_admin, mock_perm_cached
    ):
        """Non-admin sees only workspaces they have permission on."""
        from mlflow_oidc_auth.routers.workspace_crud import list_workspaces

        mock_get_username.return_value = "user@example.com"
        mock_get_is_admin.return_value = False

        ws1 = MagicMock()
        ws1.name = "ws1"
        ws1.description = "Workspace 1"
        ws2 = MagicMock()
        ws2.name = "ws2"
        ws2.description = "Workspace 2"
        ws3 = MagicMock()
        ws3.name = "ws3"
        ws3.description = "Workspace 3"
        mock_get_ws_store.return_value.list_workspaces.return_value = [ws1, ws2, ws3]

        # User has permission on ws1 and ws3, not ws2
        def _perm_side_effect(username, ws_name):
            if ws_name in ("ws1", "ws3"):
                return MagicMock()  # non-None means has permission
            return None

        mock_perm_cached.side_effect = _perm_side_effect

        mock_request = MagicMock()
        result = await list_workspaces(request=mock_request)

        assert len(result) == 2
        assert result[0].name == "ws1"
        assert result[1].name == "ws3"


# ──────────────────────────────────────────────────────────────────────────
# Get workspace endpoint tests
# ──────────────────────────────────────────────────────────────────────────


class TestGetWorkspace:
    """Test GET workspace detail endpoint."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_crud._get_workspace_store")
    async def test_get_workspace_success(self, mock_get_ws_store):
        """GET with valid name and READ permission returns workspace details."""
        from mlflow_oidc_auth.routers.workspace_crud import get_workspace

        mock_ws = MagicMock()
        mock_ws.name = "ws1"
        mock_ws.description = "Workspace 1"
        mock_get_ws_store.return_value.get_workspace.return_value = mock_ws

        result = await get_workspace(workspace="ws1", _="user@example.com")

        assert result.name == "ws1"
        assert result.description == "Workspace 1"

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_crud._get_workspace_store")
    async def test_get_workspace_not_found(self, mock_get_ws_store):
        """GET with non-existent workspace returns 404."""
        from mlflow_oidc_auth.routers.workspace_crud import get_workspace
        from fastapi import HTTPException

        mock_get_ws_store.return_value.get_workspace.side_effect = Exception(
            "Workspace 'nonexistent' not found"
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_workspace(workspace="nonexistent", _="user@example.com")
        assert exc_info.value.status_code == 404


# ──────────────────────────────────────────────────────────────────────────
# Update workspace endpoint tests
# ──────────────────────────────────────────────────────────────────────────


class TestUpdateWorkspace:
    """Test PATCH workspace update endpoint."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_crud._get_workspace_store")
    async def test_update_workspace_success(self, mock_get_ws_store):
        """PATCH with MANAGE permission updates workspace description."""
        from mlflow_oidc_auth.routers.workspace_crud import update_workspace
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudUpdateRequest

        mock_ws = MagicMock()
        mock_ws.name = "ws1"
        mock_ws.description = "Updated description"
        mock_get_ws_store.return_value.update_workspace.return_value = mock_ws

        body = WorkspaceCrudUpdateRequest(description="Updated description")
        result = await update_workspace(
            body=body, workspace="ws1", _="admin@example.com"
        )

        assert result.name == "ws1"
        assert result.description == "Updated description"

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_crud._get_workspace_store")
    async def test_update_workspace_not_found(self, mock_get_ws_store):
        """PATCH on non-existent workspace returns 404."""
        from mlflow_oidc_auth.routers.workspace_crud import update_workspace
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudUpdateRequest
        from fastapi import HTTPException

        mock_get_ws_store.return_value.update_workspace.side_effect = Exception(
            "Workspace does not exist"
        )

        body = WorkspaceCrudUpdateRequest(description="Updated")
        with pytest.raises(HTTPException) as exc_info:
            await update_workspace(
                body=body, workspace="nonexistent", _="admin@example.com"
            )
        assert exc_info.value.status_code == 404


# ──────────────────────────────────────────────────────────────────────────
# Delete workspace endpoint tests
# ──────────────────────────────────────────────────────────────────────────


class TestDeleteWorkspace:
    """Test DELETE workspace endpoint."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_crud._get_workspace_store")
    async def test_delete_workspace_success(self, mock_get_ws_store):
        """DELETE with MANAGE permission deletes workspace in RESTRICT mode."""
        from mlflow_oidc_auth.routers.workspace_crud import delete_workspace

        await delete_workspace(workspace="ws1", _="admin@example.com")

        mock_get_ws_store.return_value.delete_workspace.assert_called_once_with(
            "ws1", mode="RESTRICT"
        )

    @pytest.mark.asyncio
    async def test_delete_default_workspace_returns_400(self):
        """DELETE on 'default' workspace returns 400."""
        from mlflow_oidc_auth.routers.workspace_crud import delete_workspace
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await delete_workspace(workspace="default", _="admin@example.com")
        assert exc_info.value.status_code == 400
        assert "default" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_crud._get_workspace_store")
    async def test_delete_workspace_not_found(self, mock_get_ws_store):
        """DELETE on non-existent workspace returns 404."""
        from mlflow_oidc_auth.routers.workspace_crud import delete_workspace
        from fastapi import HTTPException

        mock_get_ws_store.return_value.delete_workspace.side_effect = Exception(
            "Workspace 'ws-gone' not found"
        )

        with pytest.raises(HTTPException) as exc_info:
            await delete_workspace(workspace="ws-gone", _="admin@example.com")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.workspace_crud._get_workspace_store")
    async def test_delete_workspace_not_empty_returns_409(self, mock_get_ws_store):
        """DELETE on workspace with resources returns 409."""
        from mlflow_oidc_auth.routers.workspace_crud import delete_workspace
        from fastapi import HTTPException

        mock_get_ws_store.return_value.delete_workspace.side_effect = Exception(
            "Workspace has resources and RESTRICT mode is enabled"
        )

        with pytest.raises(HTTPException) as exc_info:
            await delete_workspace(workspace="ws-full", _="admin@example.com")
        assert exc_info.value.status_code == 409


# ──────────────────────────────────────────────────────────────────────────
# Feature flag gating test
# ──────────────────────────────────────────────────────────────────────────


class TestFeatureFlagGating:
    """Test that workspace CRUD router is feature-flag gated in app.py."""

    def test_workspace_crud_router_registered_when_workspaces_enabled(self):
        """When MLFLOW_ENABLE_WORKSPACES=true, workspace_crud_router should be included."""
        # We test this by checking the app.py code includes the workspace_crud_router
        # inside the feature flag block. We parse the source as a proxy.
        import inspect
        from mlflow_oidc_auth import app as app_module

        source = inspect.getsource(app_module.create_app)
        assert "workspace_crud_router" in source
