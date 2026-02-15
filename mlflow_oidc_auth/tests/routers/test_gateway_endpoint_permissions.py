"""Tests for gateway endpoint permissions router."""

from unittest.mock import patch

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
        assert {
            "name": "admin@example.com",
            "permission": "MANAGE",
            "kind": "user",
        } in body
        assert {
            "name": "user@example.com",
            "permission": "READ",
            "kind": "user",
        } in body
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
        assert {
            "name": "user@example.com",
            "permission": "READ",
            "kind": "user",
        } in body
        assert {
            "name": "service@example.com",
            "permission": "EDIT",
            "kind": "service-account",
        } in body

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
        # Mock the repository method to return groups with permissions
        mock_store.gateway_endpoint_group_repo.list_groups_for_endpoint.return_value = [
            ("developers", "READ"),
            ("admins", "MANAGE"),
        ]

        with patch("mlflow_oidc_auth.routers.gateway_endpoint_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GATEWAY_ENDPOINT_BASE}/my-endpoint/groups")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert {"kind": "group", "name": "developers", "permission": "READ"} in body
        assert {"kind": "group", "name": "admins", "permission": "MANAGE"} in body
        mock_store.gateway_endpoint_group_repo.list_groups_for_endpoint.assert_called_with("my-endpoint")

    def test_list_gateway_endpoint_groups_filters_by_endpoint(self, test_app, authenticated_client, mock_store, mock_gateway_permissions):
        """Test that only groups with permissions for the specific endpoint are returned."""
        # Only one group has permission for this endpoint
        mock_store.gateway_endpoint_group_repo.list_groups_for_endpoint.return_value = [
            ("admins", "MANAGE"),
        ]

        with patch("mlflow_oidc_auth.routers.gateway_endpoint_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GATEWAY_ENDPOINT_BASE}/my-endpoint/groups")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert {"kind": "group", "name": "admins", "permission": "MANAGE"} in body

    def test_list_gateway_endpoint_groups_empty(self, test_app, authenticated_client, mock_store, mock_gateway_permissions):
        """Test listing groups when no group has permissions for the endpoint."""
        mock_store.gateway_endpoint_group_repo.list_groups_for_endpoint.return_value = []

        with patch("mlflow_oidc_auth.routers.gateway_endpoint_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GATEWAY_ENDPOINT_BASE}/unknown-endpoint/groups")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_gateway_endpoint_groups_no_gateway_permissions_attr(self, test_app, authenticated_client, mock_store):
        """Test listing groups when groups don't have gateway_endpoint_permissions attribute."""
        mock_store.gateway_endpoint_group_repo.list_groups_for_endpoint.return_value = []

        with patch("mlflow_oidc_auth.routers.gateway_endpoint_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GATEWAY_ENDPOINT_BASE}/my-endpoint/groups")

        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.usefixtures("authenticated_session")
class TestListGatewayEndpoints:
    """Tests for listing all gateway endpoints."""

    def test_list_endpoints_admin_sees_all(self, test_app, authenticated_client, mock_store, mock_gateway_permissions):
        """Test that admin sees all endpoints from MLflow."""

        # Override to make current user admin
        async def override_get_is_admin():
            return True

        async def override_get_username():
            return "admin@example.com"

        test_app.dependency_overrides[get_is_admin] = override_get_is_admin
        test_app.dependency_overrides[get_username] = override_get_username

        try:
            # Mock fetch_all_gateway_endpoints to return sample endpoints
            mock_endpoints = [
                {"name": "endpoint-a", "endpoint_type": "llm/v1/chat"},
                {"name": "endpoint-b", "endpoint_type": "llm/v1/completions"},
                {"name": "endpoint-c", "endpoint_type": "llm/v1/embeddings"},
            ]

            with patch(
                "mlflow_oidc_auth.routers.gateway_endpoint_permissions.fetch_all_gateway_endpoints",
                return_value=mock_endpoints,
            ):
                with patch(
                    "mlflow_oidc_auth.routers.gateway_endpoint_permissions.store",
                    mock_store,
                ):
                    resp = authenticated_client.get(GATEWAY_ENDPOINT_BASE)

            assert resp.status_code == 200
            body = resp.json()
            assert len(body) == 3
            endpoint_names = [e["name"] for e in body]
            assert sorted(endpoint_names) == ["endpoint-a", "endpoint-b", "endpoint-c"]
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
            # Mock endpoints - MLflow should already return unique endpoints
            mock_endpoints = [
                {"name": "shared-endpoint", "endpoint_type": "llm/v1/chat"},
                {"name": "unique-endpoint", "endpoint_type": "llm/v1/completions"},
            ]

            with patch(
                "mlflow_oidc_auth.routers.gateway_endpoint_permissions.fetch_all_gateway_endpoints",
                return_value=mock_endpoints,
            ):
                with patch(
                    "mlflow_oidc_auth.routers.gateway_endpoint_permissions.store",
                    mock_store,
                ):
                    resp = authenticated_client.get(GATEWAY_ENDPOINT_BASE)

            assert resp.status_code == 200
            body = resp.json()
            endpoint_names = [e["name"] for e in body]
            assert sorted(endpoint_names) == ["shared-endpoint", "unique-endpoint"]
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
            mock_endpoints = [
                {"name": "endpoint-a", "endpoint_type": "llm/v1/chat"},
                {"name": "endpoint-b", "endpoint_type": "llm/v1/completions"},
                {"name": "endpoint-c", "endpoint_type": "llm/v1/embeddings"},
                {"name": "endpoint-d", "endpoint_type": "llm/v1/chat"},
            ]

            def filter_mock(username, endpoints):
                # User can manage endpoint-b and endpoint-d
                return [e for e in endpoints if e["name"] in ["endpoint-b", "endpoint-d"]]

            with patch(
                "mlflow_oidc_auth.routers.gateway_endpoint_permissions.fetch_all_gateway_endpoints",
                return_value=mock_endpoints,
            ):
                with patch(
                    "mlflow_oidc_auth.routers.gateway_endpoint_permissions.filter_manageable_gateway_endpoints",
                    filter_mock,
                ):
                    with patch(
                        "mlflow_oidc_auth.routers.gateway_endpoint_permissions.store",
                        mock_store,
                    ):
                        resp = authenticated_client.get(GATEWAY_ENDPOINT_BASE)

            assert resp.status_code == 200
            body = resp.json()
            endpoint_names = [e["name"] for e in body]
            assert sorted(endpoint_names) == ["endpoint-b", "endpoint-d"]
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
            mock_endpoints = [
                {"name": "endpoint-a", "endpoint_type": "llm/v1/chat"},
                {"name": "endpoint-b", "endpoint_type": "llm/v1/completions"},
            ]

            def filter_mock(username, endpoints):
                # Return only endpoint-b (simulating endpoint-a being filtered due to error)
                return [e for e in endpoints if e["name"] == "endpoint-b"]

            with patch(
                "mlflow_oidc_auth.routers.gateway_endpoint_permissions.fetch_all_gateway_endpoints",
                return_value=mock_endpoints,
            ):
                with patch(
                    "mlflow_oidc_auth.routers.gateway_endpoint_permissions.filter_manageable_gateway_endpoints",
                    filter_mock,
                ):
                    with patch(
                        "mlflow_oidc_auth.routers.gateway_endpoint_permissions.store",
                        mock_store,
                    ):
                        resp = authenticated_client.get(GATEWAY_ENDPOINT_BASE)

            assert resp.status_code == 200
            body = resp.json()
            endpoint_names = [e["name"] for e in body]
            assert endpoint_names == ["endpoint-b"]
        finally:
            test_app.dependency_overrides.pop(get_is_admin, None)
            test_app.dependency_overrides.pop(get_username, None)

    def test_list_endpoints_empty_when_no_permissions(self, test_app, authenticated_client, mock_store, mock_gateway_permissions):
        """Test that empty list is returned when no gateway endpoints exist."""

        async def override_get_is_admin():
            return True

        async def override_get_username():
            return "admin@example.com"

        test_app.dependency_overrides[get_is_admin] = override_get_is_admin
        test_app.dependency_overrides[get_username] = override_get_username

        try:
            # No endpoints returned from MLflow
            with patch(
                "mlflow_oidc_auth.routers.gateway_endpoint_permissions.fetch_all_gateway_endpoints",
                return_value=[],
            ):
                with patch(
                    "mlflow_oidc_auth.routers.gateway_endpoint_permissions.store",
                    mock_store,
                ):
                    resp = authenticated_client.get(GATEWAY_ENDPOINT_BASE)

            assert resp.status_code == 200
            assert resp.json() == []
        finally:
            test_app.dependency_overrides.pop(get_is_admin, None)
            test_app.dependency_overrides.pop(get_username, None)

    def test_list_endpoints_handles_missing_gateway_permissions_attr(self, test_app, authenticated_client, mock_store):
        """Test handling endpoints without all expected attributes."""

        async def override_get_is_admin():
            return True

        async def override_get_username():
            return "admin@example.com"

        test_app.dependency_overrides[get_is_admin] = override_get_is_admin
        test_app.dependency_overrides[get_username] = override_get_username

        try:
            # Endpoints with minimal attributes
            mock_endpoints = [
                {"name": "endpoint-a"},  # Missing endpoint_type
            ]

            with patch(
                "mlflow_oidc_auth.routers.gateway_endpoint_permissions.fetch_all_gateway_endpoints",
                return_value=mock_endpoints,
            ):
                with patch(
                    "mlflow_oidc_auth.routers.gateway_endpoint_permissions.store",
                    mock_store,
                ):
                    resp = authenticated_client.get(GATEWAY_ENDPOINT_BASE)

            assert resp.status_code == 200
            body = resp.json()
            assert len(body) == 1
            assert body[0]["name"] == "endpoint-a"
            assert body[0]["type"] == ""  # Default when missing
        finally:
            test_app.dependency_overrides.pop(get_is_admin, None)
            test_app.dependency_overrides.pop(get_username, None)
