"""
Comprehensive tests for the registered model permissions router.

This module tests all registered model permission endpoints including listing models,
getting model user permissions with various scenarios including authentication,
authorization, and error handling.
"""

import pytest
from unittest.mock import MagicMock, patch

from mlflow_oidc_auth.routers.registered_model_permissions import (
    registered_model_permissions_router,
    get_registered_model_groups,
    get_registered_model_users,
    list_models,
    LIST_MODELS,
    REGISTERED_MODEL_GROUP_PERMISSIONS,
    REGISTERED_MODEL_USER_PERMISSIONS,
)
from mlflow_oidc_auth.entities import User, RegisteredModelPermission as RegisteredModelPermissionEntity


class TestRegisteredModelPermissionsRouter:
    """Test class for registered model permissions router configuration."""

    def test_router_configuration(self):
        """Test that the registered model permissions router is properly configured."""
        assert registered_model_permissions_router.prefix == "/api/2.0/mlflow/permissions/registered-models"
        assert "registered model permissions" in registered_model_permissions_router.tags
        assert 403 in registered_model_permissions_router.responses
        assert 404 in registered_model_permissions_router.responses

    def test_route_constants(self):
        """Test that route constants are properly defined."""
        assert LIST_MODELS == ""
        assert REGISTERED_MODEL_USER_PERMISSIONS == "/{name}/users"
        assert REGISTERED_MODEL_GROUP_PERMISSIONS == "/{name}/groups"


class TestGetRegisteredModelGroupsEndpoint:
    """Test the get registered model groups endpoint functionality."""

    @pytest.mark.asyncio
    async def test_get_registered_model_groups_success(self, mock_store):
        mock_store.registered_model_group_repo.list_groups_for_model.return_value = [("team-a", "READ"), ("team-b", "MANAGE")]

        with patch("mlflow_oidc_auth.routers.registered_model_permissions.store", mock_store):
            result = await get_registered_model_groups(name="test-model", _="admin@example.com")

        assert len(result) == 2
        assert result[0].name == "team-a"
        assert result[0].permission == "READ"
        assert result[0].kind == "group"
        assert result[1].name == "team-b"
        assert result[1].permission == "MANAGE"
        assert result[1].kind == "group"

    def test_get_registered_model_groups_integration(self, admin_client, mock_store):
        mock_store.registered_model_group_repo.list_groups_for_model.return_value = []
        response = admin_client.get("/api/2.0/mlflow/permissions/registered-models/test-model/groups")
        assert response.status_code == 200


class TestGetRegisteredModelUsersEndpoint:
    """Test the get registered model users endpoint functionality."""

    @pytest.mark.asyncio
    async def test_get_registered_model_users_success(self, mock_store):
        """Test successful retrieval of registered model users."""
        # Mock users with registered model permissions
        user1 = User(
            id_=1,
            username="user1@example.com",
            password_hash="hash1",
            password_expiration=None,
            display_name="User 1",
            is_admin=False,
            is_service_account=False,
            registered_model_permissions=[RegisteredModelPermissionEntity(name="test-model", permission="MANAGE")],
        )

        user2 = User(
            id_=2,
            username="service@example.com",
            password_hash="hash2",
            password_expiration=None,
            display_name="Service Account",
            is_admin=False,
            is_service_account=True,
            registered_model_permissions=[RegisteredModelPermissionEntity(name="test-model", permission="READ")],
        )

        user3 = User(
            id_=3,
            username="user3@example.com",
            password_hash="hash3",
            password_expiration=None,
            display_name="User 3",
            is_admin=False,
            is_service_account=False,
            registered_model_permissions=[],  # No permissions for this model
        )

        mock_store.list_users.return_value = [user1, user2, user3]

        with patch("mlflow_oidc_auth.routers.registered_model_permissions.store", mock_store):
            result = await get_registered_model_users(name="test-model", _=None)

        assert len(result) == 2  # Only users with permissions for test-model

        # Check first user
        assert result[0].name == "user1@example.com"
        assert result[0].permission == "MANAGE"
        assert result[0].kind == "user"

        # Check service account
        assert result[1].name == "service@example.com"
        assert result[1].permission == "READ"
        assert result[1].kind == "service-account"

    @pytest.mark.asyncio
    async def test_get_registered_model_users_no_permissions(self, mock_store):
        """Test getting registered model users when no users have permissions."""
        user1 = User(username="user1@example.com", display_name="User 1", is_admin=False, is_service_account=False, registered_model_permissions=[])

        mock_store.list_users.return_value = [user1]

        result = await get_registered_model_users(name="test-model", _=None)

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_registered_model_users_multiple_models(self, mock_store):
        """Test getting users for specific model when users have multiple model permissions."""
        user1 = User(
            username="user1@example.com",
            display_name="User 1",
            is_admin=False,
            is_service_account=False,
            registered_model_permissions=[
                RegisteredModelPermissionEntity(name="model-1", permission="MANAGE"),
                RegisteredModelPermissionEntity(name="model-2", permission="READ"),
            ],
        )

        mock_store.list_users.return_value = [user1]

        result = await get_registered_model_users(name="model-1", _=None)

        assert len(result) == 1
        assert result[0].name == "user1@example.com"
        assert result[0].permission == "MANAGE"  # Should get permission for model-1

    @pytest.mark.asyncio
    async def test_get_registered_model_users_no_registered_model_permissions_attr(self, mock_store):
        """Test getting users when user object doesn't have registered_model_permissions attribute."""
        user1 = User(username="user1@example.com", display_name="User 1", is_admin=False, is_service_account=False)
        # Remove the registered_model_permissions attribute
        delattr(user1, "registered_model_permissions")

        mock_store.list_users.return_value = [user1]

        result = await get_registered_model_users(name="test-model", _=None)

        assert len(result) == 0

    def test_get_registered_model_users_integration(self, admin_client):
        """Test get registered model users endpoint through FastAPI test client."""
        response = admin_client.get("/api/2.0/mlflow/permissions/registered-models/test-model/users")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_registered_model_users_non_admin(self, authenticated_client):
        """Test get registered model users as non-admin user."""
        response = authenticated_client.get("/api/2.0/mlflow/permissions/registered-models/test-model/users")

        # Allowed because mocks grant manage permission
        assert response.status_code == 200

    def test_get_registered_model_users_non_admin_without_manage_permission(self, authenticated_client):
        """Non-admin lacking manage rights should be forbidden."""
        with patch("mlflow_oidc_auth.dependencies.can_manage_registered_model", return_value=False):
            response = authenticated_client.get("/api/2.0/mlflow/permissions/registered-models/test-model/users")

        assert response.status_code == 403

    def test_get_registered_model_users_unauthenticated(self, client):
        """Test get registered model users without authentication."""
        response = client.get("/api/2.0/mlflow/permissions/registered-models/test-model/users")

        # Should fail due to authentication requirement
        assert response.status_code in [401, 403]


class TestListModelsEndpoint:
    """Test the list models endpoint functionality."""

    @pytest.mark.asyncio
    async def test_list_models_admin(self):
        """Test listing models as admin user."""
        # Mock registered models
        mock_model1 = MagicMock()
        mock_model1.name = "model-1"
        mock_model1.tags = {"env": "test"}
        mock_model1.description = "Test Model 1"
        mock_model1.aliases = ["alias1"]

        mock_model2 = MagicMock()
        mock_model2.name = "model-2"
        mock_model2.tags = {"env": "prod"}
        mock_model2.description = "Test Model 2"
        mock_model2.aliases = []

        with patch("mlflow_oidc_auth.routers.registered_model_permissions.fetch_all_registered_models") as mock_fetch:
            mock_fetch.return_value = [mock_model1, mock_model2]

            result = await list_models(username="admin@example.com", is_admin=True)

            assert result.status_code == 200

            import json

            content = json.loads(result.body.decode())

            assert len(content) == 2
            assert content[0]["name"] == "model-1"
            assert content[0]["tags"] == {"env": "test"}
            assert content[0]["description"] == "Test Model 1"
            assert content[0]["aliases"] == ["alias1"]

    @pytest.mark.asyncio
    async def test_list_models_regular_user_with_permissions(self):
        """Test listing models as regular user with manage permissions."""
        mock_model1 = MagicMock()
        mock_model1.name = "model-1"
        mock_model1.tags = {"env": "test"}
        mock_model1.description = "Test Model 1"
        mock_model1.aliases = []

        mock_model2 = MagicMock()
        mock_model2.name = "model-2"
        mock_model2.tags = {"env": "prod"}
        mock_model2.description = "Test Model 2"
        mock_model2.aliases = []

        # Mock filter_manageable_models to return only model-1
        with patch("mlflow_oidc_auth.routers.registered_model_permissions.fetch_all_registered_models") as mock_fetch, patch(
            "mlflow_oidc_auth.routers.registered_model_permissions.filter_manageable_models"
        ) as mock_filter:
            mock_fetch.return_value = [mock_model1, mock_model2]
            mock_filter.return_value = [mock_model1]  # Only model-1 is manageable

            result = await list_models(username="user@example.com", is_admin=False)

            assert result.status_code == 200

            import json

            content = json.loads(result.body.decode())

            assert len(content) == 1  # Only model-1 should be returned
            assert content[0]["name"] == "model-1"

            # Verify filter_manageable_models was called with correct args
            mock_filter.assert_called_once_with("user@example.com", [mock_model1, mock_model2])

    @pytest.mark.asyncio
    async def test_list_models_regular_user_no_permissions(self):
        """Test listing models as regular user with no permissions."""
        mock_model1 = MagicMock()
        mock_model1.name = "model-1"
        mock_model1.tags = {}
        mock_model1.description = "Test Model 1"
        mock_model1.aliases = []

        with patch("mlflow_oidc_auth.routers.registered_model_permissions.fetch_all_registered_models") as mock_fetch, patch(
            "mlflow_oidc_auth.routers.registered_model_permissions.filter_manageable_models", return_value=[]
        ):
            mock_fetch.return_value = [mock_model1]

            result = await list_models(username="user@example.com", is_admin=False)

            assert result.status_code == 200

            import json

            content = json.loads(result.body.decode())

            assert len(content) == 0

    @pytest.mark.asyncio
    async def test_list_models_empty_list(self):
        """Test listing models when no models exist."""
        with patch("mlflow_oidc_auth.routers.registered_model_permissions.fetch_all_registered_models") as mock_fetch:
            mock_fetch.return_value = []

            result = await list_models(username="admin@example.com", is_admin=True)

            assert result.status_code == 200

            import json

            content = json.loads(result.body.decode())

            assert len(content) == 0

    @pytest.mark.asyncio
    async def test_list_models_with_none_values(self):
        """Test listing models with None values in model attributes."""
        mock_model = MagicMock()
        mock_model.name = "model-1"
        mock_model.tags = None
        mock_model.description = None
        mock_model.aliases = None

        with patch("mlflow_oidc_auth.routers.registered_model_permissions.fetch_all_registered_models") as mock_fetch:
            mock_fetch.return_value = [mock_model]

            result = await list_models(username="admin@example.com", is_admin=True)

            assert result.status_code == 200

            import json

            content = json.loads(result.body.decode())

            assert len(content) == 1
            assert content[0]["name"] == "model-1"
            assert content[0]["tags"] is None
            assert content[0]["description"] is None
            assert content[0]["aliases"] is None

    def test_list_models_integration_admin(self, admin_client):
        """Test list models endpoint through FastAPI test client as admin."""
        response = admin_client.get("/api/2.0/mlflow/permissions/registered-models")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_models_integration_regular_user(self, authenticated_client):
        """Test list models endpoint through FastAPI test client as regular user."""
        response = authenticated_client.get("/api/2.0/mlflow/permissions/registered-models")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_models_unauthenticated(self, client):
        """Test list models without authentication."""
        response = client.get("/api/2.0/mlflow/permissions/registered-models")

        # Should fail due to authentication requirement
        assert response.status_code in [401, 403]


class TestRegisteredModelPermissionsRouterIntegration:
    """Test class for registered model permissions router integration scenarios."""

    def test_all_endpoints_require_authentication(self, client):
        """Test that all registered model permission endpoints require authentication."""
        endpoints = [("GET", "/api/2.0/mlflow/permissions/registered-models"), ("GET", "/api/2.0/mlflow/permissions/registered-models/test-model/users")]

        for method, endpoint in endpoints:
            response = client.get(endpoint)

            # Should require authentication
            assert response.status_code in [401, 403]

    def test_model_user_permissions_requires_admin(self, authenticated_client):
        """Test that model user permissions endpoint requires admin privileges."""
        with patch("mlflow_oidc_auth.dependencies.can_manage_registered_model", return_value=False):
            response = authenticated_client.get("/api/2.0/mlflow/permissions/registered-models/test-model/users")

        # Without manage permission a non-admin is forbidden
        assert response.status_code == 403

    def test_endpoints_response_content_type(self, authenticated_client, admin_client):
        """Test that endpoints return proper content type."""
        # Test list models
        response = authenticated_client.get("/api/2.0/mlflow/permissions/registered-models")
        assert "application/json" in response.headers.get("content-type", "")

        # Test model users (admin only)
        response = admin_client.get("/api/2.0/mlflow/permissions/registered-models/test-model/users")
        assert "application/json" in response.headers.get("content-type", "")

    def test_model_name_parameter_validation(self, admin_client):
        """Test model name parameter validation."""
        # Test with various model name formats
        model_names = ["test-model", "model_with_underscores", "model123", "Model-Name"]

        for model_name in model_names:
            response = admin_client.get(f"/api/2.0/mlflow/permissions/registered-models/{model_name}/users")

            # Should not fail due to parameter format
            assert response.status_code == 200

    def test_registered_model_permissions_response_structure(self, authenticated_client):
        """Test that registered model permissions endpoints return proper response structure."""
        # Test list models response structure
        response = authenticated_client.get("/api/2.0/mlflow/permissions/registered-models")

        assert response.status_code == 200
        models = response.json()
        assert isinstance(models, list)

        if models:  # If there are models
            model = models[0]
            assert "name" in model
            assert "tags" in model
            assert "description" in model
            assert "aliases" in model

    def test_model_users_response_structure(self, admin_client):
        """Test that model users endpoint returns proper response structure."""
        response = admin_client.get("/api/2.0/mlflow/permissions/registered-models/test-model/users")

        assert response.status_code == 200
        users = response.json()
        assert isinstance(users, list)

        if users:  # If there are users with permissions
            user = users[0]
            assert "name" in user
            assert "permission" in user
            assert "kind" in user
            assert user["kind"] in ["user", "service-account"]

    def test_registered_model_permissions_error_handling(self, admin_client):
        """Test error handling in registered model permissions endpoints."""
        # Test with empty model name
        response = admin_client.get("/api/2.0/mlflow/permissions/registered-models//users")

        # Should handle invalid paths gracefully
        assert response.status_code in [404, 422]

    def test_registered_model_permissions_concurrent_requests(self, authenticated_client):
        """Test that registered model permissions endpoints handle concurrent requests."""
        import concurrent.futures

        def make_request():
            return authenticated_client.get("/api/2.0/mlflow/permissions/registered-models")

        # Make concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(5)]

            for future in concurrent.futures.as_completed(futures):
                response = future.result()
                assert response.status_code == 200  # Should not crash

    def test_registered_model_permissions_with_special_characters(self, admin_client):
        """Test registered model permissions with special characters in model name."""
        # Test with URL-encoded special characters
        special_names = ["model%20name", "model-with-dashes", "model_with_underscores"]

        for model_name in special_names:
            response = admin_client.get(f"/api/2.0/mlflow/permissions/registered-models/{model_name}/users")

            # Should handle special characters (may return empty list, but shouldn't crash)
            assert response.status_code == 200

    def test_registered_model_permissions_performance(self, authenticated_client):
        """Test that registered model permissions endpoints respond in reasonable time."""
        import time

        endpoints = ["/api/2.0/mlflow/permissions/registered-models"]

        for endpoint in endpoints:
            start_time = time.time()
            response = authenticated_client.get(endpoint)
            end_time = time.time()

            # Should respond within reasonable time (5 seconds)
            assert (end_time - start_time) < 5.0
            assert response.status_code == 200

    def test_registered_model_permissions_with_long_model_names(self, admin_client):
        """Test registered model permissions with very long model names."""
        # Test with a very long model name
        long_model_name = "a" * 1000  # 1000 character model name

        response = admin_client.get(f"/api/2.0/mlflow/permissions/registered-models/{long_model_name}/users")

        # Should handle long names gracefully (may return 404 or empty list)
        assert response.status_code in [200, 404]

    def test_registered_model_permissions_case_sensitivity(self, admin_client):
        """Test registered model permissions case sensitivity."""
        # Test with different cases
        model_names = ["TestModel", "testmodel", "TESTMODEL"]

        for model_name in model_names:
            response = admin_client.get(f"/api/2.0/mlflow/permissions/registered-models/{model_name}/users")

            # Should handle different cases (behavior may vary based on implementation)
            assert response.status_code == 200
