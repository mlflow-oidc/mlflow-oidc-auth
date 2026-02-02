"""Tests for gateway endpoint permissions router."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mlflow_oidc_auth.dependencies import check_gateway_endpoint_manage_permission
from mlflow_oidc_auth.utils import get_is_admin, get_username


@pytest.fixture
def mock_gateway_permissions():
    """Create mock gateway endpoint permissions for users and groups."""

    class MockGatewayPermission:
        def __init__(self, endpoint_id, permission):
            self.endpoint_id = endpoint_id
            self.permission = permission

    return MockGatewayPermission


@pytest.fixture
def override_gateway_manage_permission(test_app):
    """Override the gateway manage permission check to always pass."""
    async def always_allow():
        return None

    test_app.dependency_overrides[check_gateway_endpoint_manage_permission] = always_allow
    yield
    test_app.dependency_overrides.pop(check_gateway_endpoint_manage_permission, None)


# Base URL for gateway endpoint permissions
GATEWAY_ENDPOINT_BASE = "/api/2.0/mlflow/permissions/gateways/endpoints"


@pytest.mark.usefixtures("authenticated_session", "override_gateway_manage_permission")
class TestGatewayEndpointPermissionRoutes:
    """Tests for gateway endpoint permission routes."""

    def test_list_gateway_endpoint_users(self, test_app, authenticated_client, mock_store, mock_gateway_permissions):
        """Test listing users with permissions for a gateway endpoint."""
        # Setup users with gateway endpoint permissions
        admin_user, regular_user, service_user = mock_store.list_users.return_value

        admin_user.gateway_endpoint_permissions = [mock_gateway_permissions("my-endpoint", "MANAGE")]
        regular_user.gateway_endpoint_permissions = [mock_gateway_permissions("my-endpoint", "READ")]
        service_user.gateway_endpoint_permissions = []

        with patch("mlflow_oidc_auth.routers.gateway_endpoint_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GATEWAY_ENDPOINT_BASE}/my-endpoint/users")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert {"name": "admin@example.com", "permission": "MANAGE", "kind": "user"} in body
        assert {"name": "user@example.com", "permission": "READ", "kind": "user"} in body
        mock_store.list_users.assert_called_with(all=True)

    def test_list_gateway_endpoint_users_filters_by_endpoint(self, test_app, authenticated_client, mock_store, mock_gateway_permissions):
        """Test that only users with permissions for the specific endpoint are returned."""
        admin_user, regular_user, service_user = mock_store.list_users.return_value

        admin_user.gateway_endpoint_permissions = [mock_gateway_permissions("other-endpoint", "MANAGE")]
        regular_user.gateway_endpoint_permissions = [mock_gateway_permissions("my-endpoint", "READ")]
        service_user.gateway_endpoint_permissions = [mock_gateway_permissions("my-endpoint", "EDIT")]

        with patch("mlflow_oidc_auth.routers.gateway_endpoint_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GATEWAY_ENDPOINT_BASE}/my-endpoint/users")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        # admin should not be included since they have permissions for a different endpoint
        assert {"name": "user@example.com", "permission": "READ", "kind": "user"} in body
        assert {"name": "service@example.com", "permission": "EDIT", "kind": "service-account"} in body

    def test_list_gateway_endpoint_users_empty(self, test_app, authenticated_client, mock_store, mock_gateway_permissions):
        """Test listing users when no one has permissions for the endpoint."""
        admin_user, regular_user, service_user = mock_store.list_users.return_value

        admin_user.gateway_endpoint_permissions = []
        regular_user.gateway_endpoint_permissions = []
        service_user.gateway_endpoint_permissions = []

        with patch("mlflow_oidc_auth.routers.gateway_endpoint_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GATEWAY_ENDPOINT_BASE}/unknown-endpoint/users")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_gateway_endpoint_users_no_gateway_permissions_attr(self, test_app, authenticated_client, mock_store):
        """Test listing users when users don't have gateway_endpoint_permissions attribute."""
        admin_user, regular_user, service_user = mock_store.list_users.return_value

        # Remove the attribute entirely
        if hasattr(admin_user, "gateway_endpoint_permissions"):
            delattr(admin_user, "gateway_endpoint_permissions")
        if hasattr(regular_user, "gateway_endpoint_permissions"):
            delattr(regular_user, "gateway_endpoint_permissions")
        if hasattr(service_user, "gateway_endpoint_permissions"):
            delattr(service_user, "gateway_endpoint_permissions")

        with patch("mlflow_oidc_auth.routers.gateway_endpoint_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GATEWAY_ENDPOINT_BASE}/my-endpoint/users")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_gateway_endpoint_groups(self, test_app, authenticated_client, mock_store, mock_gateway_permissions):
        """Test listing groups with permissions for a gateway endpoint."""
        mock_group1 = MagicMock()
        mock_group1.group_name = "developers"
        mock_group1.gateway_endpoint_permissions = [mock_gateway_permissions("my-endpoint", "READ")]

        mock_group2 = MagicMock()
        mock_group2.group_name = "admins"
        mock_group2.gateway_endpoint_permissions = [mock_gateway_permissions("my-endpoint", "MANAGE")]

        mock_group3 = MagicMock()
        mock_group3.group_name = "viewers"
        mock_group3.gateway_endpoint_permissions = []

        mock_store.list_groups.return_value = [mock_group1, mock_group2, mock_group3]

        with patch("mlflow_oidc_auth.routers.gateway_endpoint_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GATEWAY_ENDPOINT_BASE}/my-endpoint/groups")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert {"name": "developers", "permission": "READ", "kind": "group"} in body
        assert {"name": "admins", "permission": "MANAGE", "kind": "group"} in body
        mock_store.list_groups.assert_called_with(all=True)

    def test_list_gateway_endpoint_groups_filters_by_endpoint(self, test_app, authenticated_client, mock_store, mock_gateway_permissions):
        """Test that only groups with permissions for the specific endpoint are returned."""
        mock_group1 = MagicMock()
        mock_group1.group_name = "developers"
        mock_group1.gateway_endpoint_permissions = [mock_gateway_permissions("other-endpoint", "READ")]

        mock_group2 = MagicMock()
        mock_group2.group_name = "admins"
        mock_group2.gateway_endpoint_permissions = [mock_gateway_permissions("my-endpoint", "MANAGE")]

        mock_store.list_groups.return_value = [mock_group1, mock_group2]

        with patch("mlflow_oidc_auth.routers.gateway_endpoint_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GATEWAY_ENDPOINT_BASE}/my-endpoint/groups")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert {"name": "admins", "permission": "MANAGE", "kind": "group"} in body

    def test_list_gateway_endpoint_groups_empty(self, test_app, authenticated_client, mock_store, mock_gateway_permissions):
        """Test listing groups when no group has permissions for the endpoint."""
        mock_group = MagicMock()
        mock_group.group_name = "developers"
        mock_group.gateway_endpoint_permissions = []

        mock_store.list_groups.return_value = [mock_group]

        with patch("mlflow_oidc_auth.routers.gateway_endpoint_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GATEWAY_ENDPOINT_BASE}/unknown-endpoint/groups")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_gateway_endpoint_groups_no_gateway_permissions_attr(self, test_app, authenticated_client, mock_store):
        """Test listing groups when groups don't have gateway_endpoint_permissions attribute."""
        mock_group = MagicMock(spec=[])  # Empty spec means no attributes
        mock_group.group_name = "developers"

        mock_store.list_groups.return_value = [mock_group]

        with patch("mlflow_oidc_auth.routers.gateway_endpoint_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GATEWAY_ENDPOINT_BASE}/my-endpoint/groups")

        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.usefixtures("authenticated_session")
class TestListGatewayEndpoints:
    """Tests for listing all gateway endpoints with permissions."""

    def test_list_endpoints_admin_sees_all(self, test_app, authenticated_client, mock_store, mock_gateway_permissions):
        """Test that admin sees all endpoints from all users."""
        # Override to make current user admin
        async def override_get_is_admin():
            return True

        async def override_get_username():
            return "admin@example.com"

        test_app.dependency_overrides[get_is_admin] = override_get_is_admin
        test_app.dependency_overrides[get_username] = override_get_username

        try:
            admin_user, regular_user, service_user = mock_store.list_users.return_value

            admin_user.gateway_endpoint_permissions = [mock_gateway_permissions("endpoint-a", "MANAGE")]
            regular_user.gateway_endpoint_permissions = [mock_gateway_permissions("endpoint-b", "READ")]
            service_user.gateway_endpoint_permissions = [mock_gateway_permissions("endpoint-c", "EDIT")]

            with patch("mlflow_oidc_auth.routers.gateway_endpoint_permissions.store", mock_store):
                resp = authenticated_client.get(GATEWAY_ENDPOINT_BASE)

            assert resp.status_code == 200
            body = resp.json()
            assert sorted(body) == ["endpoint-a", "endpoint-b", "endpoint-c"]
            mock_store.list_users.assert_called_with(all=True)
        finally:
            test_app.dependency_overrides.pop(get_is_admin, None)
            test_app.dependency_overrides.pop(get_username, None)

    def test_list_endpoints_admin_deduplicates(self, test_app, authenticated_client, mock_store, mock_gateway_permissions):
        """Test that admin sees deduplicated endpoint list."""
        async def override_get_is_admin():
            return True

        async def override_get_username():
            return "admin@example.com"

        test_app.dependency_overrides[get_is_admin] = override_get_is_admin
        test_app.dependency_overrides[get_username] = override_get_username

        try:
            admin_user, regular_user, service_user = mock_store.list_users.return_value

            # Multiple users have the same endpoint
            admin_user.gateway_endpoint_permissions = [mock_gateway_permissions("shared-endpoint", "MANAGE")]
            regular_user.gateway_endpoint_permissions = [mock_gateway_permissions("shared-endpoint", "READ")]
            service_user.gateway_endpoint_permissions = [mock_gateway_permissions("unique-endpoint", "EDIT")]

            with patch("mlflow_oidc_auth.routers.gateway_endpoint_permissions.store", mock_store):
                resp = authenticated_client.get(GATEWAY_ENDPOINT_BASE)

            assert resp.status_code == 200
            body = resp.json()
            assert sorted(body) == ["shared-endpoint", "unique-endpoint"]
        finally:
            test_app.dependency_overrides.pop(get_is_admin, None)
            test_app.dependency_overrides.pop(get_username, None)

    def test_list_endpoints_non_admin_filters_by_manage_permission(self, test_app, authenticated_client, mock_store, mock_gateway_permissions):
        """Test that non-admin users only see endpoints they can manage."""
        async def override_get_is_admin():
            return False

        async def override_get_username():
            return "user@example.com"

        test_app.dependency_overrides[get_is_admin] = override_get_is_admin
        test_app.dependency_overrides[get_username] = override_get_username

        try:
            admin_user, regular_user, service_user = mock_store.list_users.return_value

            admin_user.gateway_endpoint_permissions = [mock_gateway_permissions("endpoint-a", "MANAGE")]
            regular_user.gateway_endpoint_permissions = [mock_gateway_permissions("endpoint-b", "READ")]
            service_user.gateway_endpoint_permissions = [mock_gateway_permissions("endpoint-c", "EDIT")]

            mock_group = MagicMock()
            mock_group.group_name = "developers"
            mock_group.gateway_endpoint_permissions = [mock_gateway_permissions("endpoint-d", "MANAGE")]
            mock_store.list_groups.return_value = [mock_group]

            def can_manage_mock(endpoint, username):
                # User can manage endpoint-b and endpoint-d
                return endpoint in ["endpoint-b", "endpoint-d"]

            with patch("mlflow_oidc_auth.routers.gateway_endpoint_permissions.store", mock_store):
                with patch("mlflow_oidc_auth.utils.permissions.can_manage_gateway_endpoint", can_manage_mock):
                    resp = authenticated_client.get(GATEWAY_ENDPOINT_BASE)

            assert resp.status_code == 200
            body = resp.json()
            assert sorted(body) == ["endpoint-b", "endpoint-d"]
        finally:
            test_app.dependency_overrides.pop(get_is_admin, None)
            test_app.dependency_overrides.pop(get_username, None)

    def test_list_endpoints_non_admin_handles_permission_errors(self, test_app, authenticated_client, mock_store, mock_gateway_permissions):
        """Test that permission errors are handled gracefully for non-admin users."""
        async def override_get_is_admin():
            return False

        async def override_get_username():
            return "user@example.com"

        test_app.dependency_overrides[get_is_admin] = override_get_is_admin
        test_app.dependency_overrides[get_username] = override_get_username

        try:
            admin_user, regular_user, service_user = mock_store.list_users.return_value

            admin_user.gateway_endpoint_permissions = [mock_gateway_permissions("endpoint-a", "MANAGE")]
            regular_user.gateway_endpoint_permissions = [mock_gateway_permissions("endpoint-b", "READ")]
            service_user.gateway_endpoint_permissions = []

            mock_store.list_groups.return_value = []

            def can_manage_mock(endpoint, username):
                if endpoint == "endpoint-a":
                    raise Exception("Permission check failed")
                return endpoint == "endpoint-b"

            with patch("mlflow_oidc_auth.routers.gateway_endpoint_permissions.store", mock_store):
                with patch("mlflow_oidc_auth.utils.permissions.can_manage_gateway_endpoint", can_manage_mock):
                    resp = authenticated_client.get(GATEWAY_ENDPOINT_BASE)

            assert resp.status_code == 200
            body = resp.json()
            # endpoint-a should be excluded due to error, endpoint-b should be included
            assert body == ["endpoint-b"]
        finally:
            test_app.dependency_overrides.pop(get_is_admin, None)
            test_app.dependency_overrides.pop(get_username, None)

    def test_list_endpoints_empty_when_no_permissions(self, test_app, authenticated_client, mock_store, mock_gateway_permissions):
        """Test that empty list is returned when no gateway permissions exist."""
        async def override_get_is_admin():
            return True

        async def override_get_username():
            return "admin@example.com"

        test_app.dependency_overrides[get_is_admin] = override_get_is_admin
        test_app.dependency_overrides[get_username] = override_get_username

        try:
            admin_user, regular_user, service_user = mock_store.list_users.return_value

            admin_user.gateway_endpoint_permissions = []
            regular_user.gateway_endpoint_permissions = []
            service_user.gateway_endpoint_permissions = []

            with patch("mlflow_oidc_auth.routers.gateway_endpoint_permissions.store", mock_store):
                resp = authenticated_client.get(GATEWAY_ENDPOINT_BASE)

            assert resp.status_code == 200
            assert resp.json() == []
        finally:
            test_app.dependency_overrides.pop(get_is_admin, None)
            test_app.dependency_overrides.pop(get_username, None)

    def test_list_endpoints_handles_missing_gateway_permissions_attr(self, test_app, authenticated_client, mock_store):
        """Test handling users without gateway_endpoint_permissions attribute."""
        async def override_get_is_admin():
            return True

        async def override_get_username():
            return "admin@example.com"

        test_app.dependency_overrides[get_is_admin] = override_get_is_admin
        test_app.dependency_overrides[get_username] = override_get_username

        try:
            admin_user, regular_user, service_user = mock_store.list_users.return_value

            # Remove the attribute entirely
            if hasattr(admin_user, "gateway_endpoint_permissions"):
                delattr(admin_user, "gateway_endpoint_permissions")
            if hasattr(regular_user, "gateway_endpoint_permissions"):
                delattr(regular_user, "gateway_endpoint_permissions")
            if hasattr(service_user, "gateway_endpoint_permissions"):
                delattr(service_user, "gateway_endpoint_permissions")

            with patch("mlflow_oidc_auth.routers.gateway_endpoint_permissions.store", mock_store):
                resp = authenticated_client.get(GATEWAY_ENDPOINT_BASE)

            assert resp.status_code == 200
            assert resp.json() == []
        finally:
            test_app.dependency_overrides.pop(get_is_admin, None)
            test_app.dependency_overrides.pop(get_username, None)
