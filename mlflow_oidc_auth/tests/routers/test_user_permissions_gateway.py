"""Tests for gateway CRUD endpoints in user_permissions router.

This module tests all 30 gateway-related endpoints in the user_permissions router:
- 5 for gateway endpoint permissions (list, create, get, update, delete)
- 5 for gateway endpoint pattern permissions
- 5 for gateway model definition permissions
- 5 for gateway model definition pattern permissions
- 5 for gateway secret permissions
- 5 for gateway secret pattern permissions
"""

from unittest.mock import MagicMock, patch

import pytest

from mlflow_oidc_auth.dependencies import check_admin_permission
from mlflow_oidc_auth.utils import get_is_admin, get_username

USER_BASE = "/api/2.0/mlflow/permissions/users"
_UP = "mlflow_oidc_auth.routers.user_permissions"


def _make_perm_result(permission_name: str, kind: str = "user") -> MagicMock:
    """Create a mock PermissionResult for effective_gateway_*_permission."""
    result = MagicMock()
    result.permission.name = permission_name
    result.permission.can_manage = permission_name == "MANAGE"
    result.kind = kind
    return result


@pytest.fixture
def override_admin(test_app):
    """Override admin permission check to always pass."""

    async def always_admin():
        return "admin@example.com"

    test_app.dependency_overrides[check_admin_permission] = always_admin
    yield
    test_app.dependency_overrides.pop(check_admin_permission, None)


@pytest.fixture
def override_user_non_admin(test_app):
    """Override get_username and get_is_admin for non-admin user tests."""

    async def _username():
        return "test@example.com"

    async def _is_admin():
        return False

    test_app.dependency_overrides[get_username] = _username
    test_app.dependency_overrides[get_is_admin] = _is_admin
    yield
    test_app.dependency_overrides.pop(get_username, None)
    test_app.dependency_overrides.pop(get_is_admin, None)


def _make_direct_perm(attr_name: str, value: str, permission: str = "READ") -> MagicMock:
    """Create a mock direct permission entity."""
    perm = MagicMock()
    setattr(perm, attr_name, value)
    perm.permission = permission
    return perm


def _make_regex_perm(
    perm_id: int = 1,
    regex: str = ".*",
    priority: int = 1,
    user_id: int = 5,
    permission: str = "READ",
) -> MagicMock:
    """Create a mock regex permission entity."""
    perm = MagicMock()
    perm.id = perm_id
    perm.regex = regex
    perm.priority = priority
    perm.user_id = user_id
    perm.permission = permission
    return perm


# ========================================================================================
# GATEWAY ENDPOINT PERMISSIONS
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session", "override_admin")
class TestUserGatewayEndpointPermissions:
    """Tests for user gateway endpoint CRUD endpoints (create/get/update/delete)."""

    def test_create(self, authenticated_client, mock_store):
        """Test creating a user gateway endpoint permission."""
        mock_store.create_gateway_endpoint_permission.return_value = _make_direct_perm("endpoint_id", "ep-1", "MANAGE")
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.post(
                f"{USER_BASE}/user@example.com/gateways/endpoints/ep-1",
                json={"permission": "MANAGE"},
            )
        assert resp.status_code == 201
        assert resp.json()["name"] == "ep-1"
        assert resp.json()["kind"] == "user"

    def test_get(self, authenticated_client, mock_store):
        """Test getting a specific user gateway endpoint permission."""
        mock_store.get_gateway_endpoint_permission.return_value = _make_direct_perm("endpoint_id", "ep-1", "READ")
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.get(f"{USER_BASE}/user@example.com/gateways/endpoints/ep-1")
        assert resp.status_code == 200
        assert resp.json()["name"] == "ep-1"

    def test_update(self, authenticated_client, mock_store):
        """Test updating a user gateway endpoint permission."""
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.patch(
                f"{USER_BASE}/user@example.com/gateways/endpoints/ep-1",
                json={"permission": "EDIT"},
            )
        assert resp.status_code == 200
        assert "updated" in resp.json()["message"].lower()
        mock_store.update_gateway_endpoint_permission.assert_called_once()

    def test_delete(self, authenticated_client, mock_store):
        """Test deleting a user gateway endpoint permission."""
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.delete(f"{USER_BASE}/user@example.com/gateways/endpoints/ep-1")
        assert resp.status_code == 200
        assert "deleted" in resp.json()["message"].lower()
        mock_store.delete_gateway_endpoint_permission.assert_called_once()

    def test_get_not_found(self, authenticated_client, mock_store):
        """Test 404 for missing permission."""
        mock_store.get_gateway_endpoint_permission.side_effect = Exception("Not found")
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.get(f"{USER_BASE}/user@example.com/gateways/endpoints/missing")
        assert resp.status_code == 404


# ========================================================================================
# GATEWAY ENDPOINT PATTERN PERMISSIONS
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session", "override_admin")
class TestUserGatewayEndpointPatternPermissions:
    """Tests for user gateway endpoint pattern CRUD endpoints."""

    def test_list(self, authenticated_client, mock_store):
        """Test listing user gateway endpoint regex permissions."""
        mock_store.list_gateway_endpoint_regex_permissions.return_value = [
            _make_regex_perm(1, "ep-.*", 1, 5, "READ"),
        ]
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.get(f"{USER_BASE}/user@example.com/gateways/endpoints-patterns")
        assert resp.status_code == 200
        assert resp.json()[0]["regex"] == "ep-.*"

    def test_create(self, authenticated_client, mock_store):
        """Test creating a user gateway endpoint regex permission."""
        mock_store.create_gateway_endpoint_regex_permission.return_value = _make_regex_perm(1, "ep-.*", 1, 5, "READ")
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.post(
                f"{USER_BASE}/user@example.com/gateways/endpoints-patterns",
                json={"regex": "ep-.*", "priority": 1, "permission": "READ"},
            )
        assert resp.status_code == 201

    def test_get(self, authenticated_client, mock_store):
        """Test getting a specific user gateway endpoint regex permission."""
        mock_store.get_gateway_endpoint_regex_permission.return_value = _make_regex_perm(1, "ep-.*", 1, 5, "READ")
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.get(f"{USER_BASE}/user@example.com/gateways/endpoints-patterns/1")
        assert resp.status_code == 200

    def test_update(self, authenticated_client, mock_store):
        """Test updating a user gateway endpoint regex permission."""
        mock_store.update_gateway_endpoint_regex_permission.return_value = _make_regex_perm(1, "new-.*", 2, 5, "MANAGE")
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.patch(
                f"{USER_BASE}/user@example.com/gateways/endpoints-patterns/1",
                json={"regex": "new-.*", "priority": 2, "permission": "MANAGE"},
            )
        assert resp.status_code == 200

    def test_delete(self, authenticated_client, mock_store):
        """Test deleting a user gateway endpoint regex permission."""
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.delete(f"{USER_BASE}/user@example.com/gateways/endpoints-patterns/1")
        assert resp.status_code == 200
        mock_store.delete_gateway_endpoint_regex_permission.assert_called_once()

    def test_get_not_found(self, authenticated_client, mock_store):
        """Test 404 for missing regex permission."""
        mock_store.get_gateway_endpoint_regex_permission.side_effect = Exception("Not found")
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.get(f"{USER_BASE}/user@example.com/gateways/endpoints-patterns/999")
        assert resp.status_code == 404


# ========================================================================================
# GATEWAY MODEL DEFINITION PERMISSIONS
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session", "override_admin")
class TestUserGatewayModelDefinitionPermissions:
    """Tests for user gateway model definition CRUD endpoints (create/get/update/delete)."""

    def test_create(self, authenticated_client, mock_store):
        """Test creating a user gateway model definition permission."""
        mock_store.create_gateway_model_definition_permission.return_value = _make_direct_perm("model_definition_id", "gpt-4", "MANAGE")
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.post(
                f"{USER_BASE}/user@example.com/gateways/model-definitions/gpt-4",
                json={"permission": "MANAGE"},
            )
        assert resp.status_code == 201
        assert resp.json()["name"] == "gpt-4"

    def test_get(self, authenticated_client, mock_store):
        """Test getting a specific user gateway model definition permission."""
        mock_store.get_gateway_model_definition_permission.return_value = _make_direct_perm("model_definition_id", "gpt-4", "READ")
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.get(f"{USER_BASE}/user@example.com/gateways/model-definitions/gpt-4")
        assert resp.status_code == 200

    def test_update(self, authenticated_client, mock_store):
        """Test updating a user gateway model definition permission."""
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.patch(
                f"{USER_BASE}/user@example.com/gateways/model-definitions/gpt-4",
                json={"permission": "EDIT"},
            )
        assert resp.status_code == 200
        mock_store.update_gateway_model_definition_permission.assert_called_once()

    def test_delete(self, authenticated_client, mock_store):
        """Test deleting a user gateway model definition permission."""
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.delete(f"{USER_BASE}/user@example.com/gateways/model-definitions/gpt-4")
        assert resp.status_code == 200
        mock_store.delete_gateway_model_definition_permission.assert_called_once()

    def test_get_not_found(self, authenticated_client, mock_store):
        """Test 404 for missing permission."""
        mock_store.get_gateway_model_definition_permission.side_effect = Exception("Not found")
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.get(f"{USER_BASE}/user@example.com/gateways/model-definitions/missing")
        assert resp.status_code == 404


# ========================================================================================
# GATEWAY MODEL DEFINITION PATTERN PERMISSIONS
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session", "override_admin")
class TestUserGatewayModelDefinitionPatternPermissions:
    """Tests for user gateway model definition pattern CRUD endpoints."""

    def test_list(self, authenticated_client, mock_store):
        """Test listing user gateway model definition regex permissions."""
        mock_store.list_gateway_model_definition_regex_permissions.return_value = [
            _make_regex_perm(1, "gpt-.*", 1, 5, "READ"),
        ]
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.get(f"{USER_BASE}/user@example.com/gateways/model-definitions-patterns")
        assert resp.status_code == 200
        assert resp.json()[0]["regex"] == "gpt-.*"

    def test_create(self, authenticated_client, mock_store):
        """Test creating a user gateway model definition regex permission."""
        mock_store.create_gateway_model_definition_regex_permission.return_value = _make_regex_perm(2, "gpt-.*", 1, 5, "READ")
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.post(
                f"{USER_BASE}/user@example.com/gateways/model-definitions-patterns",
                json={"regex": "gpt-.*", "priority": 1, "permission": "READ"},
            )
        assert resp.status_code == 201

    def test_get(self, authenticated_client, mock_store):
        """Test getting a specific user gateway model definition regex permission."""
        mock_store.get_gateway_model_definition_regex_permission.return_value = _make_regex_perm(1, "gpt-.*", 1, 5, "READ")
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.get(f"{USER_BASE}/user@example.com/gateways/model-definitions-patterns/1")
        assert resp.status_code == 200

    def test_update(self, authenticated_client, mock_store):
        """Test updating a user gateway model definition regex permission."""
        mock_store.update_gateway_model_definition_regex_permission.return_value = _make_regex_perm(1, "claude-.*", 2, 5, "MANAGE")
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.patch(
                f"{USER_BASE}/user@example.com/gateways/model-definitions-patterns/1",
                json={"regex": "claude-.*", "priority": 2, "permission": "MANAGE"},
            )
        assert resp.status_code == 200

    def test_delete(self, authenticated_client, mock_store):
        """Test deleting a user gateway model definition regex permission."""
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.delete(f"{USER_BASE}/user@example.com/gateways/model-definitions-patterns/1")
        assert resp.status_code == 200
        mock_store.delete_gateway_model_definition_regex_permission.assert_called_once()

    def test_get_not_found(self, authenticated_client, mock_store):
        """Test 404 for missing regex permission."""
        mock_store.get_gateway_model_definition_regex_permission.side_effect = Exception("Not found")
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.get(f"{USER_BASE}/user@example.com/gateways/model-definitions-patterns/999")
        assert resp.status_code == 404


# ========================================================================================
# GATEWAY SECRET PERMISSIONS
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session", "override_admin")
class TestUserGatewaySecretPermissions:
    """Tests for user gateway secret CRUD endpoints (create/get/update/delete)."""

    def test_create(self, authenticated_client, mock_store):
        """Test creating a user gateway secret permission."""
        mock_store.create_gateway_secret_permission.return_value = _make_direct_perm("secret_id", "api-key", "MANAGE")
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.post(
                f"{USER_BASE}/user@example.com/gateways/secrets/api-key",
                json={"permission": "MANAGE"},
            )
        assert resp.status_code == 201
        assert resp.json()["name"] == "api-key"

    def test_get(self, authenticated_client, mock_store):
        """Test getting a specific user gateway secret permission."""
        mock_store.get_gateway_secret_permission.return_value = _make_direct_perm("secret_id", "api-key", "READ")
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.get(f"{USER_BASE}/user@example.com/gateways/secrets/api-key")
        assert resp.status_code == 200

    def test_update(self, authenticated_client, mock_store):
        """Test updating a user gateway secret permission."""
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.patch(
                f"{USER_BASE}/user@example.com/gateways/secrets/api-key",
                json={"permission": "EDIT"},
            )
        assert resp.status_code == 200
        mock_store.update_gateway_secret_permission.assert_called_once()

    def test_delete(self, authenticated_client, mock_store):
        """Test deleting a user gateway secret permission."""
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.delete(f"{USER_BASE}/user@example.com/gateways/secrets/api-key")
        assert resp.status_code == 200
        mock_store.delete_gateway_secret_permission.assert_called_once()

    def test_get_not_found(self, authenticated_client, mock_store):
        """Test 404 for missing permission."""
        mock_store.get_gateway_secret_permission.side_effect = Exception("Not found")
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.get(f"{USER_BASE}/user@example.com/gateways/secrets/missing")
        assert resp.status_code == 404


# ========================================================================================
# GATEWAY SECRET PATTERN PERMISSIONS
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session", "override_admin")
class TestUserGatewaySecretPatternPermissions:
    """Tests for user gateway secret pattern CRUD endpoints."""

    def test_list(self, authenticated_client, mock_store):
        """Test listing user gateway secret regex permissions."""
        mock_store.list_gateway_secret_regex_permissions.return_value = [
            _make_regex_perm(1, "api-.*", 1, 5, "READ"),
        ]
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.get(f"{USER_BASE}/user@example.com/gateways/secrets-patterns")
        assert resp.status_code == 200
        assert resp.json()[0]["regex"] == "api-.*"

    def test_create(self, authenticated_client, mock_store):
        """Test creating a user gateway secret regex permission."""
        mock_store.create_gateway_secret_regex_permission.return_value = _make_regex_perm(2, "api-.*", 1, 5, "READ")
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.post(
                f"{USER_BASE}/user@example.com/gateways/secrets-patterns",
                json={"regex": "api-.*", "priority": 1, "permission": "READ"},
            )
        assert resp.status_code == 201

    def test_get(self, authenticated_client, mock_store):
        """Test getting a specific user gateway secret regex permission."""
        mock_store.get_gateway_secret_regex_permission.return_value = _make_regex_perm(1, "api-.*", 1, 5, "READ")
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.get(f"{USER_BASE}/user@example.com/gateways/secrets-patterns/1")
        assert resp.status_code == 200

    def test_update(self, authenticated_client, mock_store):
        """Test updating a user gateway secret regex permission."""
        mock_store.update_gateway_secret_regex_permission.return_value = _make_regex_perm(1, "key-.*", 2, 5, "MANAGE")
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.patch(
                f"{USER_BASE}/user@example.com/gateways/secrets-patterns/1",
                json={"regex": "key-.*", "priority": 2, "permission": "MANAGE"},
            )
        assert resp.status_code == 200

    def test_delete(self, authenticated_client, mock_store):
        """Test deleting a user gateway secret regex permission."""
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.delete(f"{USER_BASE}/user@example.com/gateways/secrets-patterns/1")
        assert resp.status_code == 200
        mock_store.delete_gateway_secret_regex_permission.assert_called_once()

    def test_get_not_found(self, authenticated_client, mock_store):
        """Test 404 for missing regex permission."""
        mock_store.get_gateway_secret_regex_permission.side_effect = Exception("Not found")
        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.get(f"{USER_BASE}/user@example.com/gateways/secrets-patterns/999")
        assert resp.status_code == 404


# ========================================================================================
# GATEWAY LIST ENDPOINTS (non-admin access)
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session")
class TestUserGatewayEndpointPermissionsList:
    """Tests for listing gateway endpoint permissions with role-based filtering."""

    def test_list_as_admin(self, admin_client):
        """Admin sees all gateway endpoints with target user's effective permissions."""
        endpoints = [{"name": "ep-1"}, {"name": "ep-2"}]
        with (
            patch(f"{_UP}.fetch_all_gateway_endpoints", return_value=endpoints),
            patch(
                f"{_UP}.effective_gateway_endpoint_permission",
                side_effect=[
                    _make_perm_result("MANAGE", "user"),
                    _make_perm_result("READ", "regex"),
                ],
            ),
        ):
            resp = admin_client.get(f"{USER_BASE}/user@example.com/gateways/endpoints")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert {"name": "ep-1", "permission": "MANAGE", "kind": "user"} in body
        assert {"name": "ep-2", "permission": "READ", "kind": "regex"} in body

    @pytest.mark.usefixtures("override_user_non_admin")
    def test_list_same_user_filters_no_permissions(self, authenticated_client):
        """Same user sees endpoints where permission != NO_PERMISSIONS."""
        endpoints = [{"name": "ep-visible"}, {"name": "ep-hidden"}]
        with (
            patch(f"{_UP}.fetch_all_gateway_endpoints", return_value=endpoints),
            patch(
                f"{_UP}.effective_gateway_endpoint_permission",
                side_effect=[
                    _make_perm_result("READ", "user"),
                    _make_perm_result("NO_PERMISSIONS", "default"),
                ],
            ),
        ):
            resp = authenticated_client.get(f"{USER_BASE}/test@example.com/gateways/endpoints")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["name"] == "ep-visible"

    @pytest.mark.usefixtures("override_user_non_admin")
    def test_list_other_user_shows_only_manageable(self, authenticated_client):
        """Non-admin querying another user sees only endpoints they can manage."""
        endpoints = [{"name": "ep-manage"}, {"name": "ep-readonly"}]
        with (
            patch(f"{_UP}.fetch_all_gateway_endpoints", return_value=endpoints),
            patch(
                f"{_UP}.effective_gateway_endpoint_permission",
                side_effect=[
                    # target user's permission for ep-manage
                    _make_perm_result("READ", "user"),
                    # caller's permission for ep-manage (can_manage=True)
                    _make_perm_result("MANAGE", "user"),
                    # target user's permission for ep-readonly
                    _make_perm_result("READ", "user"),
                    # caller's permission for ep-readonly (can_manage=False)
                    _make_perm_result("READ", "regex"),
                ],
            ),
        ):
            resp = authenticated_client.get(f"{USER_BASE}/other@example.com/gateways/endpoints")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["name"] == "ep-manage"

    def test_list_error(self, admin_client):
        """Test error handling for list endpoint."""
        with patch(f"{_UP}.fetch_all_gateway_endpoints", side_effect=Exception("DB error")):
            resp = admin_client.get(f"{USER_BASE}/user@example.com/gateways/endpoints")
        assert resp.status_code == 500


@pytest.mark.usefixtures("authenticated_session")
class TestUserGatewayModelDefinitionPermissionsList:
    """Tests for listing gateway model definition permissions with role-based filtering."""

    def test_list_as_admin(self, admin_client):
        """Admin sees all gateway model definitions with target user's effective permissions."""
        models = [{"name": "gpt-4"}, {"name": "claude-3"}]
        with (
            patch(f"{_UP}.fetch_all_gateway_model_definitions", return_value=models),
            patch(
                f"{_UP}.effective_gateway_model_definition_permission",
                side_effect=[
                    _make_perm_result("MANAGE", "user"),
                    _make_perm_result("READ", "regex"),
                ],
            ),
        ):
            resp = admin_client.get(f"{USER_BASE}/user@example.com/gateways/model-definitions")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert {"name": "gpt-4", "permission": "MANAGE", "kind": "user"} in body

    @pytest.mark.usefixtures("override_user_non_admin")
    def test_list_same_user_filters_no_permissions(self, authenticated_client):
        """Same user sees model definitions where permission != NO_PERMISSIONS."""
        models = [{"name": "gpt-4"}, {"name": "hidden-model"}]
        with (
            patch(f"{_UP}.fetch_all_gateway_model_definitions", return_value=models),
            patch(
                f"{_UP}.effective_gateway_model_definition_permission",
                side_effect=[
                    _make_perm_result("READ", "user"),
                    _make_perm_result("NO_PERMISSIONS", "default"),
                ],
            ),
        ):
            resp = authenticated_client.get(f"{USER_BASE}/test@example.com/gateways/model-definitions")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["name"] == "gpt-4"

    @pytest.mark.usefixtures("override_user_non_admin")
    def test_list_other_user_shows_only_manageable(self, authenticated_client):
        """Non-admin querying another user sees only model definitions they can manage."""
        models = [{"name": "gpt-4"}, {"name": "claude-3"}]
        with (
            patch(f"{_UP}.fetch_all_gateway_model_definitions", return_value=models),
            patch(
                f"{_UP}.effective_gateway_model_definition_permission",
                side_effect=[
                    _make_perm_result("READ", "user"),
                    _make_perm_result("MANAGE", "user"),
                    _make_perm_result("READ", "user"),
                    _make_perm_result("READ", "regex"),
                ],
            ),
        ):
            resp = authenticated_client.get(f"{USER_BASE}/other@example.com/gateways/model-definitions")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["name"] == "gpt-4"

    def test_list_error(self, admin_client):
        """Test error handling for list endpoint."""
        with patch(f"{_UP}.fetch_all_gateway_model_definitions", side_effect=Exception("DB error")):
            resp = admin_client.get(f"{USER_BASE}/user@example.com/gateways/model-definitions")
        assert resp.status_code == 500


@pytest.mark.usefixtures("authenticated_session")
class TestUserGatewaySecretPermissionsList:
    """Tests for listing gateway secret permissions with role-based filtering."""

    def test_list_as_admin(self, admin_client):
        """Admin sees all gateway secrets with target user's effective permissions."""
        secrets = [{"secret_name": "api-key"}, {"secret_name": "db-pass"}]
        with (
            patch(f"{_UP}.fetch_all_gateway_secrets", return_value=secrets),
            patch(
                f"{_UP}.effective_gateway_secret_permission",
                side_effect=[
                    _make_perm_result("MANAGE", "user"),
                    _make_perm_result("READ", "regex"),
                ],
            ),
        ):
            resp = admin_client.get(f"{USER_BASE}/user@example.com/gateways/secrets")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert {"name": "api-key", "permission": "MANAGE", "kind": "user"} in body
        assert {"name": "db-pass", "permission": "READ", "kind": "regex"} in body

    @pytest.mark.usefixtures("override_user_non_admin")
    def test_list_same_user_filters_no_permissions(self, authenticated_client):
        """Same user sees secrets where permission != NO_PERMISSIONS."""
        secrets = [{"secret_name": "visible-key"}, {"secret_name": "hidden-key"}]
        with (
            patch(f"{_UP}.fetch_all_gateway_secrets", return_value=secrets),
            patch(
                f"{_UP}.effective_gateway_secret_permission",
                side_effect=[
                    _make_perm_result("READ", "user"),
                    _make_perm_result("NO_PERMISSIONS", "default"),
                ],
            ),
        ):
            resp = authenticated_client.get(f"{USER_BASE}/test@example.com/gateways/secrets")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["name"] == "visible-key"

    @pytest.mark.usefixtures("override_user_non_admin")
    def test_list_other_user_shows_only_manageable(self, authenticated_client):
        """Non-admin querying another user sees only secrets they can manage."""
        secrets = [{"secret_name": "manageable"}, {"secret_name": "readonly"}]
        with (
            patch(f"{_UP}.fetch_all_gateway_secrets", return_value=secrets),
            patch(
                f"{_UP}.effective_gateway_secret_permission",
                side_effect=[
                    _make_perm_result("READ", "user"),
                    _make_perm_result("MANAGE", "user"),
                    _make_perm_result("READ", "user"),
                    _make_perm_result("READ", "regex"),
                ],
            ),
        ):
            resp = authenticated_client.get(f"{USER_BASE}/other@example.com/gateways/secrets")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["name"] == "manageable"

    def test_list_error(self, admin_client):
        """Test error handling for list endpoint."""
        with patch(f"{_UP}.fetch_all_gateway_secrets", side_effect=Exception("DB error")):
            resp = admin_client.get(f"{USER_BASE}/user@example.com/gateways/secrets")
        assert resp.status_code == 500
