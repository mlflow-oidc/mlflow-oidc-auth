"""Tests for gateway CRUD endpoints in group_permissions router.

This module tests all 30 gateway-related endpoints in the group_permissions router:
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

GROUP_BASE = "/api/2.0/mlflow/permissions/groups"


@pytest.fixture
def override_admin(test_app):
    """Override admin permission check to always pass."""

    async def always_admin():
        return "admin@example.com"

    test_app.dependency_overrides[check_admin_permission] = always_admin
    yield
    test_app.dependency_overrides.pop(check_admin_permission, None)


def _make_direct_perm(attr_name: str, value: str, permission: str = "READ") -> MagicMock:
    """Create a mock direct permission entity."""
    perm = MagicMock()
    setattr(perm, attr_name, value)
    perm.permission = permission
    return perm


def _make_regex_perm(perm_id: int = 1, regex: str = ".*", priority: int = 1, group_id: int = 10, permission: str = "READ") -> MagicMock:
    """Create a mock regex permission entity."""
    perm = MagicMock()
    perm.id = perm_id
    perm.regex = regex
    perm.priority = priority
    perm.group_id = group_id
    perm.permission = permission
    return perm


# ========================================================================================
# GATEWAY ENDPOINT PERMISSIONS
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session", "override_admin")
class TestGroupGatewayEndpointPermissions:
    """Tests for group gateway endpoint CRUD endpoints."""

    def test_list(self, authenticated_client, mock_store):
        """Test listing group gateway endpoint permissions."""
        mock_store.list_group_gateway_endpoint_permissions.return_value = [
            _make_direct_perm("endpoint_id", "ep-1", "MANAGE"),
            _make_direct_perm("endpoint_id", "ep-2", "READ"),
        ]
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GROUP_BASE}/devs/gateways/endpoints")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert {"kind": "group", "name": "ep-1", "permission": "MANAGE"} in body

    def test_create(self, authenticated_client, mock_store):
        """Test creating a group gateway endpoint permission."""
        mock_store.create_group_gateway_endpoint_permission.return_value = _make_direct_perm("endpoint_id", "ep-1", "MANAGE")
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.post(f"{GROUP_BASE}/devs/gateways/endpoints/ep-1", json={"permission": "MANAGE"})
        assert resp.status_code == 201
        assert resp.json() == {"kind": "group", "name": "ep-1", "permission": "MANAGE"}

    def test_get(self, authenticated_client, mock_store):
        """Test getting a specific group gateway endpoint permission."""
        mock_store.get_user_groups_gateway_endpoint_permission.return_value = _make_direct_perm("endpoint_id", "ep-1", "READ")
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GROUP_BASE}/devs/gateways/endpoints/ep-1")
        assert resp.status_code == 200
        assert resp.json() == {"kind": "group", "name": "ep-1", "permission": "READ"}

    def test_update(self, authenticated_client, mock_store):
        """Test updating a group gateway endpoint permission."""
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.patch(f"{GROUP_BASE}/devs/gateways/endpoints/ep-1", json={"permission": "EDIT"})
        assert resp.status_code == 200
        assert "updated" in resp.json()["message"].lower()
        mock_store.update_group_gateway_endpoint_permission.assert_called_once()

    def test_delete(self, authenticated_client, mock_store):
        """Test deleting a group gateway endpoint permission."""
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.delete(f"{GROUP_BASE}/devs/gateways/endpoints/ep-1")
        assert resp.status_code == 200
        assert "deleted" in resp.json()["message"].lower()
        mock_store.delete_group_gateway_endpoint_permission.assert_called_once()

    def test_list_error(self, authenticated_client, mock_store):
        """Test error handling for list endpoint."""
        mock_store.list_group_gateway_endpoint_permissions.side_effect = Exception("DB error")
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GROUP_BASE}/devs/gateways/endpoints")
        assert resp.status_code == 500

    def test_get_not_found(self, authenticated_client, mock_store):
        """Test 404 for missing permission."""
        mock_store.get_user_groups_gateway_endpoint_permission.side_effect = Exception("Not found")
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GROUP_BASE}/devs/gateways/endpoints/missing")
        assert resp.status_code == 404


# ========================================================================================
# GATEWAY ENDPOINT PATTERN PERMISSIONS
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session", "override_admin")
class TestGroupGatewayEndpointPatternPermissions:
    """Tests for group gateway endpoint pattern CRUD endpoints."""

    def test_list(self, authenticated_client, mock_store):
        """Test listing group gateway endpoint regex permissions."""
        mock_store.list_group_gateway_endpoint_regex_permissions.return_value = [
            _make_regex_perm(1, "ep-.*", 1, 10, "READ"),
        ]
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GROUP_BASE}/devs/gateways/endpoints-patterns")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["regex"] == "ep-.*"

    def test_create(self, authenticated_client, mock_store):
        """Test creating a group gateway endpoint regex permission."""
        mock_store.create_group_gateway_endpoint_regex_permission.return_value = _make_regex_perm(1, "ep-.*", 1, 10, "READ")
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.post(
                f"{GROUP_BASE}/devs/gateways/endpoints-patterns",
                json={"regex": "ep-.*", "priority": 1, "permission": "READ"},
            )
        assert resp.status_code == 201
        assert resp.json()["regex"] == "ep-.*"

    def test_get(self, authenticated_client, mock_store):
        """Test getting a specific group gateway endpoint regex permission."""
        mock_store.get_group_gateway_endpoint_regex_permission.return_value = _make_regex_perm(1, "ep-.*", 1, 10, "READ")
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GROUP_BASE}/devs/gateways/endpoints-patterns/1")
        assert resp.status_code == 200

    def test_update(self, authenticated_client, mock_store):
        """Test updating a group gateway endpoint regex permission."""
        mock_store.update_group_gateway_endpoint_regex_permission.return_value = _make_regex_perm(1, "new-.*", 2, 10, "MANAGE")
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.patch(
                f"{GROUP_BASE}/devs/gateways/endpoints-patterns/1",
                json={"regex": "new-.*", "priority": 2, "permission": "MANAGE"},
            )
        assert resp.status_code == 200
        assert resp.json()["regex"] == "new-.*"

    def test_delete(self, authenticated_client, mock_store):
        """Test deleting a group gateway endpoint regex permission."""
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.delete(f"{GROUP_BASE}/devs/gateways/endpoints-patterns/1")
        assert resp.status_code == 200
        mock_store.delete_group_gateway_endpoint_regex_permission.assert_called_once()

    def test_get_not_found(self, authenticated_client, mock_store):
        """Test 404 for missing regex permission."""
        mock_store.get_group_gateway_endpoint_regex_permission.side_effect = Exception("Not found")
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GROUP_BASE}/devs/gateways/endpoints-patterns/999")
        assert resp.status_code == 404


# ========================================================================================
# GATEWAY MODEL DEFINITION PERMISSIONS
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session", "override_admin")
class TestGroupGatewayModelDefinitionPermissions:
    """Tests for group gateway model definition CRUD endpoints."""

    def test_list(self, authenticated_client, mock_store):
        """Test listing group gateway model definition permissions."""
        mock_store.list_group_gateway_model_definition_permissions.return_value = [
            _make_direct_perm("model_definition_id", "gpt-4", "MANAGE"),
        ]
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GROUP_BASE}/devs/gateways/model-definitions")
        assert resp.status_code == 200
        assert resp.json()[0]["name"] == "gpt-4"

    def test_create(self, authenticated_client, mock_store):
        """Test creating a group gateway model definition permission."""
        mock_store.create_group_gateway_model_definition_permission.return_value = _make_direct_perm("model_definition_id", "gpt-4", "MANAGE")
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.post(f"{GROUP_BASE}/devs/gateways/model-definitions/gpt-4", json={"permission": "MANAGE"})
        assert resp.status_code == 201
        assert resp.json() == {"kind": "group", "name": "gpt-4", "permission": "MANAGE"}

    def test_get(self, authenticated_client, mock_store):
        """Test getting a specific group gateway model definition permission."""
        mock_store.get_user_groups_gateway_model_definition_permission.return_value = _make_direct_perm("model_definition_id", "gpt-4", "READ")
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GROUP_BASE}/devs/gateways/model-definitions/gpt-4")
        assert resp.status_code == 200
        assert resp.json() == {"kind": "group", "name": "gpt-4", "permission": "READ"}

    def test_update(self, authenticated_client, mock_store):
        """Test updating a group gateway model definition permission."""
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.patch(f"{GROUP_BASE}/devs/gateways/model-definitions/gpt-4", json={"permission": "EDIT"})
        assert resp.status_code == 200
        mock_store.update_group_gateway_model_definition_permission.assert_called_once()

    def test_delete(self, authenticated_client, mock_store):
        """Test deleting a group gateway model definition permission."""
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.delete(f"{GROUP_BASE}/devs/gateways/model-definitions/gpt-4")
        assert resp.status_code == 200
        mock_store.delete_group_gateway_model_definition_permission.assert_called_once()

    def test_get_not_found(self, authenticated_client, mock_store):
        """Test 404 for missing model definition permission."""
        mock_store.get_user_groups_gateway_model_definition_permission.side_effect = Exception("Not found")
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GROUP_BASE}/devs/gateways/model-definitions/missing")
        assert resp.status_code == 404


# ========================================================================================
# GATEWAY MODEL DEFINITION PATTERN PERMISSIONS
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session", "override_admin")
class TestGroupGatewayModelDefinitionPatternPermissions:
    """Tests for group gateway model definition pattern CRUD endpoints."""

    def test_list(self, authenticated_client, mock_store):
        """Test listing group gateway model definition regex permissions."""
        mock_store.list_group_gateway_model_definition_regex_permissions.return_value = [
            _make_regex_perm(1, "gpt-.*", 1, 10, "READ"),
        ]
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GROUP_BASE}/devs/gateways/model-definitions-patterns")
        assert resp.status_code == 200
        assert resp.json()[0]["regex"] == "gpt-.*"

    def test_create(self, authenticated_client, mock_store):
        """Test creating a group gateway model definition regex permission."""
        mock_store.create_group_gateway_model_definition_regex_permission.return_value = _make_regex_perm(2, "gpt-.*", 1, 10, "READ")
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.post(
                f"{GROUP_BASE}/devs/gateways/model-definitions-patterns",
                json={"regex": "gpt-.*", "priority": 1, "permission": "READ"},
            )
        assert resp.status_code == 201

    def test_get(self, authenticated_client, mock_store):
        """Test getting a specific group gateway model definition regex permission."""
        mock_store.get_group_gateway_model_definition_regex_permission.return_value = _make_regex_perm(1, "gpt-.*", 1, 10, "READ")
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GROUP_BASE}/devs/gateways/model-definitions-patterns/1")
        assert resp.status_code == 200

    def test_update(self, authenticated_client, mock_store):
        """Test updating a group gateway model definition regex permission."""
        mock_store.update_group_gateway_model_definition_regex_permission.return_value = _make_regex_perm(1, "claude-.*", 2, 10, "MANAGE")
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.patch(
                f"{GROUP_BASE}/devs/gateways/model-definitions-patterns/1",
                json={"regex": "claude-.*", "priority": 2, "permission": "MANAGE"},
            )
        assert resp.status_code == 200

    def test_delete(self, authenticated_client, mock_store):
        """Test deleting a group gateway model definition regex permission."""
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.delete(f"{GROUP_BASE}/devs/gateways/model-definitions-patterns/1")
        assert resp.status_code == 200
        mock_store.delete_group_gateway_model_definition_regex_permission.assert_called_once()

    def test_get_not_found(self, authenticated_client, mock_store):
        """Test 404 for missing model definition regex permission."""
        mock_store.get_group_gateway_model_definition_regex_permission.side_effect = Exception("Not found")
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GROUP_BASE}/devs/gateways/model-definitions-patterns/999")
        assert resp.status_code == 404


# ========================================================================================
# GATEWAY SECRET PERMISSIONS
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session", "override_admin")
class TestGroupGatewaySecretPermissions:
    """Tests for group gateway secret CRUD endpoints."""

    def test_list(self, authenticated_client, mock_store):
        """Test listing group gateway secret permissions."""
        mock_store.list_group_gateway_secret_permissions.return_value = [
            _make_direct_perm("secret_id", "api-key", "MANAGE"),
        ]
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GROUP_BASE}/devs/gateways/secrets")
        assert resp.status_code == 200
        assert resp.json()[0]["name"] == "api-key"

    def test_create(self, authenticated_client, mock_store):
        """Test creating a group gateway secret permission."""
        mock_store.create_group_gateway_secret_permission.return_value = _make_direct_perm("secret_id", "api-key", "MANAGE")
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.post(f"{GROUP_BASE}/devs/gateways/secrets/api-key", json={"permission": "MANAGE"})
        assert resp.status_code == 201
        assert resp.json() == {"kind": "group", "name": "api-key", "permission": "MANAGE"}

    def test_get(self, authenticated_client, mock_store):
        """Test getting a specific group gateway secret permission."""
        mock_store.get_user_groups_gateway_secret_permission.return_value = _make_direct_perm("secret_id", "api-key", "READ")
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GROUP_BASE}/devs/gateways/secrets/api-key")
        assert resp.status_code == 200
        assert resp.json() == {"kind": "group", "name": "api-key", "permission": "READ"}

    def test_update(self, authenticated_client, mock_store):
        """Test updating a group gateway secret permission."""
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.patch(f"{GROUP_BASE}/devs/gateways/secrets/api-key", json={"permission": "EDIT"})
        assert resp.status_code == 200
        mock_store.update_group_gateway_secret_permission.assert_called_once()

    def test_delete(self, authenticated_client, mock_store):
        """Test deleting a group gateway secret permission."""
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.delete(f"{GROUP_BASE}/devs/gateways/secrets/api-key")
        assert resp.status_code == 200
        mock_store.delete_group_gateway_secret_permission.assert_called_once()

    def test_get_not_found(self, authenticated_client, mock_store):
        """Test 404 for missing secret permission."""
        mock_store.get_user_groups_gateway_secret_permission.side_effect = Exception("Not found")
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GROUP_BASE}/devs/gateways/secrets/missing")
        assert resp.status_code == 404


# ========================================================================================
# GATEWAY SECRET PATTERN PERMISSIONS
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session", "override_admin")
class TestGroupGatewaySecretPatternPermissions:
    """Tests for group gateway secret pattern CRUD endpoints."""

    def test_list(self, authenticated_client, mock_store):
        """Test listing group gateway secret regex permissions."""
        mock_store.list_group_gateway_secret_regex_permissions.return_value = [
            _make_regex_perm(1, "api-.*", 1, 10, "READ"),
        ]
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GROUP_BASE}/devs/gateways/secrets-patterns")
        assert resp.status_code == 200
        assert resp.json()[0]["regex"] == "api-.*"

    def test_create(self, authenticated_client, mock_store):
        """Test creating a group gateway secret regex permission."""
        mock_store.create_group_gateway_secret_regex_permission.return_value = _make_regex_perm(2, "api-.*", 1, 10, "READ")
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.post(
                f"{GROUP_BASE}/devs/gateways/secrets-patterns",
                json={"regex": "api-.*", "priority": 1, "permission": "READ"},
            )
        assert resp.status_code == 201

    def test_get(self, authenticated_client, mock_store):
        """Test getting a specific group gateway secret regex permission."""
        mock_store.get_group_gateway_secret_regex_permission.return_value = _make_regex_perm(1, "api-.*", 1, 10, "READ")
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GROUP_BASE}/devs/gateways/secrets-patterns/1")
        assert resp.status_code == 200

    def test_update(self, authenticated_client, mock_store):
        """Test updating a group gateway secret regex permission."""
        mock_store.update_group_gateway_secret_regex_permission.return_value = _make_regex_perm(1, "key-.*", 2, 10, "MANAGE")
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.patch(
                f"{GROUP_BASE}/devs/gateways/secrets-patterns/1",
                json={"regex": "key-.*", "priority": 2, "permission": "MANAGE"},
            )
        assert resp.status_code == 200

    def test_delete(self, authenticated_client, mock_store):
        """Test deleting a group gateway secret regex permission."""
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.delete(f"{GROUP_BASE}/devs/gateways/secrets-patterns/1")
        assert resp.status_code == 200
        mock_store.delete_group_gateway_secret_regex_permission.assert_called_once()

    def test_get_not_found(self, authenticated_client, mock_store):
        """Test 404 for missing secret regex permission."""
        mock_store.get_group_gateway_secret_regex_permission.side_effect = Exception("Not found")
        with patch("mlflow_oidc_auth.routers.group_permissions.store", mock_store):
            resp = authenticated_client.get(f"{GROUP_BASE}/devs/gateways/secrets-patterns/999")
        assert resp.status_code == 404
