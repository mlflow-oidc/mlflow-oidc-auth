"""Tests for gateway model definition permissions router."""

from unittest.mock import patch

import pytest

from mlflow_oidc_auth.dependencies import check_gateway_model_definition_manage_permission
from mlflow_oidc_auth.utils import get_is_admin, get_username


@pytest.fixture
def mock_model_def_permissions():
    """Create mock gateway model definition permissions for users."""

    class MockModelDefPermission:
        def __init__(self, model_definition_id: str, permission: str) -> None:
            self.model_definition_id = model_definition_id
            self.permission = permission

    return MockModelDefPermission


@pytest.fixture
def override_model_def_manage_permission(test_app):
    """Override the gateway model definition manage permission check."""

    async def always_allow():
        return None

    test_app.dependency_overrides[check_gateway_model_definition_manage_permission] = always_allow
    yield
    test_app.dependency_overrides.pop(check_gateway_model_definition_manage_permission, None)


GATEWAY_MODEL_DEF_BASE = "/api/2.0/mlflow/permissions/gateways/model-definitions"


@pytest.mark.usefixtures("authenticated_session", "override_model_def_manage_permission")
class TestGatewayModelDefinitionPermissionRoutes:
    """Tests for gateway model definition permission routes."""

    def test_list_users(self, test_app, authenticated_client, mock_store, mock_model_def_permissions):
        """Test listing users with permissions for a gateway model definition."""
        admin_user, regular_user, service_user = mock_store.list_users.return_value

        admin_user.gateway_model_definition_permissions = [mock_model_def_permissions("my-model", "MANAGE")]
        regular_user.gateway_model_definition_permissions = [mock_model_def_permissions("my-model", "READ")]
        service_user.gateway_model_definition_permissions = []

        with patch("mlflow_oidc_auth.routers.gateway_model_definition_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GATEWAY_MODEL_DEF_BASE}/my-model/users")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert {"name": "admin@example.com", "permission": "MANAGE", "kind": "user"} in body
        assert {"name": "user@example.com", "permission": "READ", "kind": "user"} in body

    def test_list_users_filters_by_model(self, test_app, authenticated_client, mock_store, mock_model_def_permissions):
        """Test that only users with permissions for the specific model are returned."""
        admin_user, regular_user, service_user = mock_store.list_users.return_value

        admin_user.gateway_model_definition_permissions = [mock_model_def_permissions("other-model", "MANAGE")]
        regular_user.gateway_model_definition_permissions = [mock_model_def_permissions("my-model", "READ")]
        service_user.gateway_model_definition_permissions = [mock_model_def_permissions("my-model", "EDIT")]

        with patch("mlflow_oidc_auth.routers.gateway_model_definition_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GATEWAY_MODEL_DEF_BASE}/my-model/users")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert {"name": "user@example.com", "permission": "READ", "kind": "user"} in body
        assert {"name": "service@example.com", "permission": "EDIT", "kind": "service-account"} in body

    def test_list_users_empty(self, test_app, authenticated_client, mock_store, mock_model_def_permissions):
        """Test listing users when no one has permissions."""
        admin_user, regular_user, service_user = mock_store.list_users.return_value

        admin_user.gateway_model_definition_permissions = []
        regular_user.gateway_model_definition_permissions = []
        service_user.gateway_model_definition_permissions = []

        with patch("mlflow_oidc_auth.routers.gateway_model_definition_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GATEWAY_MODEL_DEF_BASE}/unknown/users")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_users_no_attr(self, test_app, authenticated_client, mock_store):
        """Test when users don't have gateway_model_definition_permissions attribute."""
        admin_user, regular_user, service_user = mock_store.list_users.return_value

        for user in [admin_user, regular_user, service_user]:
            if hasattr(user, "gateway_model_definition_permissions"):
                delattr(user, "gateway_model_definition_permissions")

        with patch("mlflow_oidc_auth.routers.gateway_model_definition_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GATEWAY_MODEL_DEF_BASE}/my-model/users")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_groups(self, test_app, authenticated_client, mock_store, mock_model_def_permissions):
        """Test listing groups with permissions for a gateway model definition."""
        mock_store.gateway_model_definition_group_repo.list_groups_for_model_definition.return_value = [
            ("developers", "READ"),
            ("admins", "MANAGE"),
        ]

        with patch("mlflow_oidc_auth.routers.gateway_model_definition_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GATEWAY_MODEL_DEF_BASE}/my-model/groups")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert {"kind": "group", "name": "developers", "permission": "READ"} in body
        assert {"kind": "group", "name": "admins", "permission": "MANAGE"} in body

    def test_list_groups_empty(self, test_app, authenticated_client, mock_store, mock_model_def_permissions):
        """Test listing groups when none have permissions."""
        mock_store.gateway_model_definition_group_repo.list_groups_for_model_definition.return_value = []

        with patch("mlflow_oidc_auth.routers.gateway_model_definition_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GATEWAY_MODEL_DEF_BASE}/my-model/groups")

        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.usefixtures("authenticated_session")
class TestListGatewayModelDefinitions:
    """Tests for listing all gateway model definitions."""

    def test_admin_sees_all(self, test_app, authenticated_client, mock_store):
        """Test that admin sees all model definitions from MLflow."""

        async def is_admin():
            return True

        async def get_user():
            return "admin@example.com"

        test_app.dependency_overrides[get_is_admin] = is_admin
        test_app.dependency_overrides[get_username] = get_user

        try:
            mock_models = [
                {"name": "gpt-4", "source": "openai"},
                {"name": "claude", "provider": "anthropic"},
            ]

            with patch("mlflow_oidc_auth.routers.gateway_model_definition_permissions.fetch_all_gateway_model_definitions", return_value=mock_models):
                with patch("mlflow_oidc_auth.routers.gateway_model_definition_permissions.store", mock_store):
                    resp = authenticated_client.get(GATEWAY_MODEL_DEF_BASE)

            assert resp.status_code == 200
            body = resp.json()
            assert len(body) == 2
            names = [m["name"] for m in body]
            assert "gpt-4" in names
            assert "claude" in names
        finally:
            test_app.dependency_overrides.pop(get_is_admin, None)
            test_app.dependency_overrides.pop(get_username, None)

    def test_non_admin_filtered(self, test_app, authenticated_client, mock_store):
        """Test that non-admin users see filtered model definitions."""

        async def is_admin():
            return False

        async def get_user():
            return "user@example.com"

        test_app.dependency_overrides[get_is_admin] = is_admin
        test_app.dependency_overrides[get_username] = get_user

        try:
            mock_models = [{"name": "gpt-4"}, {"name": "claude"}, {"name": "llama"}]

            def filter_mock(username, models):
                return [m for m in models if m["name"] == "claude"]

            with patch("mlflow_oidc_auth.routers.gateway_model_definition_permissions.fetch_all_gateway_model_definitions", return_value=mock_models):
                with patch("mlflow_oidc_auth.routers.gateway_model_definition_permissions.filter_manageable_gateway_model_definitions", filter_mock):
                    with patch("mlflow_oidc_auth.routers.gateway_model_definition_permissions.store", mock_store):
                        resp = authenticated_client.get(GATEWAY_MODEL_DEF_BASE)

            assert resp.status_code == 200
            body = resp.json()
            assert len(body) == 1
            assert body[0]["name"] == "claude"
        finally:
            test_app.dependency_overrides.pop(get_is_admin, None)
            test_app.dependency_overrides.pop(get_username, None)

    def test_empty_list(self, test_app, authenticated_client, mock_store):
        """Test empty model definition list."""

        async def is_admin():
            return True

        async def get_user():
            return "admin@example.com"

        test_app.dependency_overrides[get_is_admin] = is_admin
        test_app.dependency_overrides[get_username] = get_user

        try:
            with patch("mlflow_oidc_auth.routers.gateway_model_definition_permissions.fetch_all_gateway_model_definitions", return_value=[]):
                with patch("mlflow_oidc_auth.routers.gateway_model_definition_permissions.store", mock_store):
                    resp = authenticated_client.get(GATEWAY_MODEL_DEF_BASE)

            assert resp.status_code == 200
            assert resp.json() == []
        finally:
            test_app.dependency_overrides.pop(get_is_admin, None)
            test_app.dependency_overrides.pop(get_username, None)
