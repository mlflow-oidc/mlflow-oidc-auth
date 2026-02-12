"""Tests for gateway secret permissions router."""

from unittest.mock import patch

import pytest

from mlflow_oidc_auth.dependencies import check_gateway_secret_manage_permission
from mlflow_oidc_auth.utils import get_is_admin, get_username


@pytest.fixture
def mock_secret_permissions():
    """Create mock gateway secret permissions for users."""

    class MockSecretPermission:
        def __init__(self, secret_id: str, permission: str) -> None:
            self.secret_id = secret_id
            self.permission = permission

    return MockSecretPermission


@pytest.fixture
def override_secret_manage_permission(test_app):
    """Override the gateway secret manage permission check."""

    async def always_allow():
        return None

    test_app.dependency_overrides[check_gateway_secret_manage_permission] = always_allow
    yield
    test_app.dependency_overrides.pop(check_gateway_secret_manage_permission, None)


GATEWAY_SECRET_BASE = "/api/2.0/mlflow/permissions/gateways/secrets"


@pytest.mark.usefixtures("authenticated_session", "override_secret_manage_permission")
class TestGatewaySecretPermissionRoutes:
    """Tests for gateway secret permission routes."""

    def test_list_users(self, test_app, authenticated_client, mock_store, mock_secret_permissions):
        """Test listing users with permissions for a gateway secret."""
        admin_user, regular_user, service_user = mock_store.list_users.return_value

        admin_user.gateway_secret_permissions = [mock_secret_permissions("my-secret", "MANAGE")]
        regular_user.gateway_secret_permissions = [mock_secret_permissions("my-secret", "READ")]
        service_user.gateway_secret_permissions = []

        with patch("mlflow_oidc_auth.routers.gateway_secret_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GATEWAY_SECRET_BASE}/my-secret/users")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert {"name": "admin@example.com", "permission": "MANAGE", "kind": "user"} in body
        assert {"name": "user@example.com", "permission": "READ", "kind": "user"} in body

    def test_list_users_filters_by_secret(self, test_app, authenticated_client, mock_store, mock_secret_permissions):
        """Test that only users with permissions for the specific secret are returned."""
        admin_user, regular_user, service_user = mock_store.list_users.return_value

        admin_user.gateway_secret_permissions = [mock_secret_permissions("other-secret", "MANAGE")]
        regular_user.gateway_secret_permissions = [mock_secret_permissions("my-secret", "READ")]
        service_user.gateway_secret_permissions = [mock_secret_permissions("my-secret", "EDIT")]

        with patch("mlflow_oidc_auth.routers.gateway_secret_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GATEWAY_SECRET_BASE}/my-secret/users")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert {"name": "user@example.com", "permission": "READ", "kind": "user"} in body
        assert {"name": "service@example.com", "permission": "EDIT", "kind": "service-account"} in body

    def test_list_users_empty(self, test_app, authenticated_client, mock_store, mock_secret_permissions):
        """Test listing users when no one has permissions."""
        admin_user, regular_user, service_user = mock_store.list_users.return_value

        admin_user.gateway_secret_permissions = []
        regular_user.gateway_secret_permissions = []
        service_user.gateway_secret_permissions = []

        with patch("mlflow_oidc_auth.routers.gateway_secret_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GATEWAY_SECRET_BASE}/unknown/users")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_users_no_attr(self, test_app, authenticated_client, mock_store):
        """Test when users don't have gateway_secret_permissions attribute."""
        admin_user, regular_user, service_user = mock_store.list_users.return_value

        for user in [admin_user, regular_user, service_user]:
            if hasattr(user, "gateway_secret_permissions"):
                delattr(user, "gateway_secret_permissions")

        with patch("mlflow_oidc_auth.routers.gateway_secret_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GATEWAY_SECRET_BASE}/my-secret/users")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_groups(self, test_app, authenticated_client, mock_store, mock_secret_permissions):
        """Test listing groups with permissions for a gateway secret."""
        mock_store.gateway_secret_group_repo.list_groups_for_secret.return_value = [
            ("developers", "READ"),
            ("admins", "MANAGE"),
        ]

        with patch("mlflow_oidc_auth.routers.gateway_secret_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GATEWAY_SECRET_BASE}/my-secret/groups")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert {"kind": "group", "name": "developers", "permission": "READ"} in body
        assert {"kind": "group", "name": "admins", "permission": "MANAGE"} in body

    def test_list_groups_empty(self, test_app, authenticated_client, mock_store, mock_secret_permissions):
        """Test listing groups when none have permissions."""
        mock_store.gateway_secret_group_repo.list_groups_for_secret.return_value = []

        with patch("mlflow_oidc_auth.routers.gateway_secret_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GATEWAY_SECRET_BASE}/my-secret/groups")

        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.usefixtures("authenticated_session")
class TestListGatewaySecrets:
    """Tests for listing all gateway secrets."""

    def test_admin_sees_all(self, test_app, authenticated_client, mock_store):
        """Test that admin sees all secrets."""

        async def is_admin():
            return True

        async def get_user():
            return "admin@example.com"

        test_app.dependency_overrides[get_is_admin] = is_admin
        test_app.dependency_overrides[get_username] = get_user

        try:
            mock_secrets = [
                {"name": "api-key-1"},
                {"name": "api-key-2"},
            ]

            with patch("mlflow_oidc_auth.routers.gateway_secret_permissions.fetch_all_gateway_secrets", return_value=mock_secrets):
                with patch("mlflow_oidc_auth.routers.gateway_secret_permissions.store", mock_store):
                    resp = authenticated_client.get(GATEWAY_SECRET_BASE)

            assert resp.status_code == 200
            body = resp.json()
            assert len(body) == 2
            keys = [s["key"] for s in body]
            assert "api-key-1" in keys
            assert "api-key-2" in keys
        finally:
            test_app.dependency_overrides.pop(get_is_admin, None)
            test_app.dependency_overrides.pop(get_username, None)

    def test_non_admin_filtered(self, test_app, authenticated_client, mock_store):
        """Test that non-admin users see filtered secrets."""

        async def is_admin():
            return False

        async def get_user():
            return "user@example.com"

        test_app.dependency_overrides[get_is_admin] = is_admin
        test_app.dependency_overrides[get_username] = get_user

        try:
            mock_secrets = [{"name": "api-key-1"}, {"name": "api-key-2"}, {"name": "api-key-3"}]

            def filter_mock(username, secrets):
                return [s for s in secrets if s["name"] == "api-key-2"]

            with patch("mlflow_oidc_auth.routers.gateway_secret_permissions.fetch_all_gateway_secrets", return_value=mock_secrets):
                with patch("mlflow_oidc_auth.routers.gateway_secret_permissions.filter_manageable_gateway_secrets", filter_mock):
                    with patch("mlflow_oidc_auth.routers.gateway_secret_permissions.store", mock_store):
                        resp = authenticated_client.get(GATEWAY_SECRET_BASE)

            assert resp.status_code == 200
            body = resp.json()
            assert len(body) == 1
            assert body[0]["key"] == "api-key-2"
        finally:
            test_app.dependency_overrides.pop(get_is_admin, None)
            test_app.dependency_overrides.pop(get_username, None)

    def test_secret_with_key_field(self, test_app, authenticated_client, mock_store):
        """Test secrets that use 'key' field instead of 'name'."""

        async def is_admin():
            return True

        async def get_user():
            return "admin@example.com"

        test_app.dependency_overrides[get_is_admin] = is_admin
        test_app.dependency_overrides[get_username] = get_user

        try:
            mock_secrets = [{"key": "secret-key-1"}]

            with patch("mlflow_oidc_auth.routers.gateway_secret_permissions.fetch_all_gateway_secrets", return_value=mock_secrets):
                with patch("mlflow_oidc_auth.routers.gateway_secret_permissions.store", mock_store):
                    resp = authenticated_client.get(GATEWAY_SECRET_BASE)

            assert resp.status_code == 200
            body = resp.json()
            assert len(body) == 1
            assert body[0]["key"] == "secret-key-1"
        finally:
            test_app.dependency_overrides.pop(get_is_admin, None)
            test_app.dependency_overrides.pop(get_username, None)

    def test_empty_list(self, test_app, authenticated_client, mock_store):
        """Test empty secrets list."""

        async def is_admin():
            return True

        async def get_user():
            return "admin@example.com"

        test_app.dependency_overrides[get_is_admin] = is_admin
        test_app.dependency_overrides[get_username] = get_user

        try:
            with patch("mlflow_oidc_auth.routers.gateway_secret_permissions.fetch_all_gateway_secrets", return_value=[]):
                with patch("mlflow_oidc_auth.routers.gateway_secret_permissions.store", mock_store):
                    resp = authenticated_client.get(GATEWAY_SECRET_BASE)

            assert resp.status_code == 200
            assert resp.json() == []
        finally:
            test_app.dependency_overrides.pop(get_is_admin, None)
            test_app.dependency_overrides.pop(get_username, None)
