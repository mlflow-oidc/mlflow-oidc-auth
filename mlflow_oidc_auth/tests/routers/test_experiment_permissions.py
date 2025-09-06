"""
Comprehensive tests for the experiment permissions router.

This module tests all experiment permission endpoints including listing experiments,
getting experiment user permissions with various scenarios including authentication,
authorization, and error handling.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from mlflow_oidc_auth.routers.experiment_permissions import (
    experiment_permissions_router,
    get_experiment_users,
    list_experiments,
    LIST_EXPERIMENTS,
    EXPERIMENT_USER_PERMISSIONS,
)
from mlflow_oidc_auth.models import ExperimentSummary, ExperimentUserPermission
from mlflow_oidc_auth.entities import User, ExperimentPermission as ExperimentPermissionEntity
from mlflow_oidc_auth.permissions import Permission


class TestExperimentPermissionsRouter:
    """Test class for experiment permissions router configuration."""

    def test_router_configuration(self):
        """Test that the experiment permissions router is properly configured."""
        assert experiment_permissions_router.prefix == "/api/2.0/mlflow/permissions/experiments"
        assert "permissions" in experiment_permissions_router.tags
        assert 403 in experiment_permissions_router.responses
        assert 404 in experiment_permissions_router.responses

    def test_route_constants(self):
        """Test that route constants are properly defined."""
        assert LIST_EXPERIMENTS == ""
        assert EXPERIMENT_USER_PERMISSIONS == "/{experiment_id}/users"


class TestGetExperimentUsersEndpoint:
    """Test the get experiment users endpoint functionality."""

    @pytest.mark.asyncio
    async def test_get_experiment_users_success(self, mock_store):
        """Test successful retrieval of experiment users."""
        # Mock users with experiment permissions
        user1 = User(
            username="user1@example.com",
            display_name="User 1",
            is_admin=False,
            is_service_account=False,
            experiment_permissions=[ExperimentPermissionEntity(experiment_id="123", permission=Permission.MANAGE)],
        )

        user2 = User(
            username="service@example.com",
            display_name="Service Account",
            is_admin=False,
            is_service_account=True,
            experiment_permissions=[ExperimentPermissionEntity(experiment_id="123", permission=Permission.READ)],
        )

        user3 = User(
            username="user3@example.com",
            display_name="User 3",
            is_admin=False,
            is_service_account=False,
            experiment_permissions=[],  # No permissions for this experiment
        )

        mock_store.list_users.return_value = [user1, user2, user3]

        result = await get_experiment_users(experiment_id="123", _="admin@example.com")

        assert len(result) == 2  # Only users with permissions for experiment 123

        # Check first user
        assert result[0].username == "user1@example.com"
        assert result[0].permission == Permission.MANAGE
        assert result[0].kind == "user"

        # Check service account
        assert result[1].username == "service@example.com"
        assert result[1].permission == Permission.READ
        assert result[1].kind == "service-account"

    @pytest.mark.asyncio
    async def test_get_experiment_users_no_permissions(self, mock_store):
        """Test getting experiment users when no users have permissions."""
        user1 = User(username="user1@example.com", display_name="User 1", is_admin=False, is_service_account=False, experiment_permissions=[])

        mock_store.list_users.return_value = [user1]

        result = await get_experiment_users(experiment_id="123", _="admin@example.com")

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_experiment_users_multiple_experiments(self, mock_store):
        """Test getting users for specific experiment when users have multiple experiment permissions."""
        user1 = User(
            username="user1@example.com",
            display_name="User 1",
            is_admin=False,
            is_service_account=False,
            experiment_permissions=[
                ExperimentPermissionEntity(experiment_id="123", permission=Permission.MANAGE),
                ExperimentPermissionEntity(experiment_id="456", permission=Permission.READ),
            ],
        )

        mock_store.list_users.return_value = [user1]

        result = await get_experiment_users(experiment_id="123", _="admin@example.com")

        assert len(result) == 1
        assert result[0].username == "user1@example.com"
        assert result[0].permission == Permission.MANAGE  # Should get permission for experiment 123

    def test_get_experiment_users_integration(self, authenticated_client):
        """Test get experiment users endpoint through FastAPI test client."""
        response = authenticated_client.get("/api/2.0/mlflow/permissions/experiments/123/users")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_experiment_users_unauthenticated(self, client):
        """Test get experiment users without authentication."""
        response = client.get("/api/2.0/mlflow/permissions/experiments/123/users")

        # Should fail due to authentication requirement
        assert response.status_code in [401, 403]

    def test_get_experiment_users_insufficient_permissions(self, authenticated_client):
        """Test get experiment users with insufficient permissions."""
        # Mock permission check to return False
        with patch("mlflow_oidc_auth.utils.can_manage_experiment", return_value=False):
            response = authenticated_client.get("/api/2.0/mlflow/permissions/experiments/123/users")

            assert response.status_code == 403


class TestListExperimentsEndpoint:
    """Test the list experiments endpoint functionality."""

    @pytest.mark.asyncio
    async def test_list_experiments_admin(self, mock_tracking_store):
        """Test listing experiments as admin user."""
        result = await list_experiments(username="admin@example.com", is_admin=True)

        assert len(result) == 1
        assert isinstance(result[0], ExperimentSummary)
        assert result[0].name == "Test Experiment"
        assert result[0].id == "123"
        assert result[0].tags == {"env": "test"}

    @pytest.mark.asyncio
    async def test_list_experiments_regular_user(self, mock_tracking_store, mock_permissions):
        """Test listing experiments as regular user."""
        # Mock can_manage_experiment to return True for specific experiments
        mock_permissions["can_manage_experiment"].return_value = True

        with patch("mlflow_oidc_auth.routers.experiment_permissions.can_manage_experiment", mock_permissions["can_manage_experiment"]):
            result = await list_experiments(username="user@example.com", is_admin=False)

            assert len(result) == 1
            assert result[0].name == "Test Experiment"
            assert result[0].id == "123"

    @pytest.mark.asyncio
    async def test_list_experiments_regular_user_no_permissions(self, mock_tracking_store, mock_permissions):
        """Test listing experiments as regular user with no permissions."""
        # Mock can_manage_experiment to return False
        mock_permissions["can_manage_experiment"].return_value = False

        with patch("mlflow_oidc_auth.routers.experiment_permissions.can_manage_experiment", mock_permissions["can_manage_experiment"]):
            result = await list_experiments(username="user@example.com", is_admin=False)

            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_experiments_multiple_experiments(self, mock_permissions):
        """Test listing multiple experiments with mixed permissions."""
        # Mock multiple experiments
        mock_experiment1 = MagicMock()
        mock_experiment1.experiment_id = "123"
        mock_experiment1.name = "Experiment 1"
        mock_experiment1.tags = {"env": "test"}

        mock_experiment2 = MagicMock()
        mock_experiment2.experiment_id = "456"
        mock_experiment2.name = "Experiment 2"
        mock_experiment2.tags = {"env": "prod"}

        mock_experiment3 = MagicMock()
        mock_experiment3.experiment_id = "789"
        mock_experiment3.name = "Experiment 3"
        mock_experiment3.tags = {}

        mock_tracking_store = MagicMock()
        mock_tracking_store.search_experiments.return_value = [mock_experiment1, mock_experiment2, mock_experiment3]

        # Mock permissions - user can manage experiments 123 and 789 but not 456
        def mock_can_manage(exp_id, username):
            return exp_id in ["123", "789"]

        with patch("mlflow.server.handlers._get_tracking_store", return_value=mock_tracking_store), patch(
            "mlflow_oidc_auth.routers.experiment_permissions.can_manage_experiment", side_effect=mock_can_manage
        ):
            result = await list_experiments(username="user@example.com", is_admin=False)

            assert len(result) == 2
            assert result[0].id == "123"
            assert result[1].id == "789"

    @pytest.mark.asyncio
    async def test_list_experiments_empty_tags(self, mock_permissions):
        """Test listing experiments with empty tags."""
        mock_experiment = MagicMock()
        mock_experiment.experiment_id = "123"
        mock_experiment.name = "Test Experiment"
        mock_experiment.tags = {}

        mock_tracking_store = MagicMock()
        mock_tracking_store.search_experiments.return_value = [mock_experiment]

        with patch("mlflow.server.handlers._get_tracking_store", return_value=mock_tracking_store):
            result = await list_experiments(username="admin@example.com", is_admin=True)

            assert len(result) == 1
            assert result[0].tags == {}

    @pytest.mark.asyncio
    async def test_list_experiments_none_tags(self, mock_permissions):
        """Test listing experiments with None tags."""
        mock_experiment = MagicMock()
        mock_experiment.experiment_id = "123"
        mock_experiment.name = "Test Experiment"
        mock_experiment.tags = None

        mock_tracking_store = MagicMock()
        mock_tracking_store.search_experiments.return_value = [mock_experiment]

        with patch("mlflow.server.handlers._get_tracking_store", return_value=mock_tracking_store):
            result = await list_experiments(username="admin@example.com", is_admin=True)

            assert len(result) == 1
            assert result[0].tags is None

    def test_list_experiments_integration_admin(self, admin_client):
        """Test list experiments endpoint through FastAPI test client as admin."""
        response = admin_client.get("/api/2.0/mlflow/permissions/experiments")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_experiments_integration_regular_user(self, authenticated_client):
        """Test list experiments endpoint through FastAPI test client as regular user."""
        response = authenticated_client.get("/api/2.0/mlflow/permissions/experiments")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_experiments_unauthenticated(self, client):
        """Test list experiments without authentication."""
        response = client.get("/api/2.0/mlflow/permissions/experiments")

        # Should fail due to authentication requirement
        assert response.status_code in [401, 403]


class TestExperimentPermissionsRouterIntegration:
    """Test class for experiment permissions router integration scenarios."""

    def test_all_endpoints_require_authentication(self, client):
        """Test that all experiment permission endpoints require authentication."""
        endpoints = [("GET", "/api/2.0/mlflow/permissions/experiments"), ("GET", "/api/2.0/mlflow/permissions/experiments/123/users")]

        for method, endpoint in endpoints:
            response = client.get(endpoint)

            # Should require authentication
            assert response.status_code in [401, 403]

    def test_experiment_user_permissions_requires_manage_permission(self, authenticated_client):
        """Test that experiment user permissions endpoint requires manage permission."""
        # Mock permission check to return False
        with patch("mlflow_oidc_auth.utils.can_manage_experiment", return_value=False):
            response = authenticated_client.get("/api/2.0/mlflow/permissions/experiments/123/users")

            assert response.status_code == 403

    def test_endpoints_response_content_type(self, authenticated_client):
        """Test that endpoints return proper content type."""
        endpoints = ["/api/2.0/mlflow/permissions/experiments", "/api/2.0/mlflow/permissions/experiments/123/users"]

        for endpoint in endpoints:
            response = authenticated_client.get(endpoint)
            assert "application/json" in response.headers.get("content-type", "")

    def test_experiment_id_parameter_validation(self, authenticated_client):
        """Test experiment ID parameter validation."""
        # Test with various experiment ID formats
        experiment_ids = ["123", "experiment-name", "exp_123", "0"]

        for exp_id in experiment_ids:
            response = authenticated_client.get(f"/api/2.0/mlflow/permissions/experiments/{exp_id}/users")

            # Should not fail due to parameter format (may fail due to permissions)
            assert response.status_code in [200, 403]

    def test_experiment_permissions_response_structure(self, authenticated_client):
        """Test that experiment permissions endpoints return proper response structure."""
        # Test list experiments response structure
        response = authenticated_client.get("/api/2.0/mlflow/permissions/experiments")

        assert response.status_code == 200
        experiments = response.json()
        assert isinstance(experiments, list)

        if experiments:  # If there are experiments
            experiment = experiments[0]
            assert "name" in experiment
            assert "id" in experiment
            assert "tags" in experiment

    def test_experiment_users_response_structure(self, authenticated_client):
        """Test that experiment users endpoint returns proper response structure."""
        response = authenticated_client.get("/api/2.0/mlflow/permissions/experiments/123/users")

        if response.status_code == 200:  # If user has permissions
            users = response.json()
            assert isinstance(users, list)

            if users:  # If there are users with permissions
                user = users[0]
                assert "username" in user
                assert "permission" in user
                assert "kind" in user
                assert user["kind"] in ["user", "service-account"]

    def test_experiment_permissions_error_handling(self, authenticated_client):
        """Test error handling in experiment permissions endpoints."""
        # Test with invalid experiment ID format (if any validation exists)
        response = authenticated_client.get("/api/2.0/mlflow/permissions/experiments//users")

        # Should handle invalid paths gracefully
        assert response.status_code in [404, 422]

    def test_experiment_permissions_concurrent_requests(self, authenticated_client):
        """Test that experiment permissions endpoints handle concurrent requests."""
        import concurrent.futures

        def make_request():
            return authenticated_client.get("/api/2.0/mlflow/permissions/experiments")

        # Make concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(5)]

            for future in concurrent.futures.as_completed(futures):
                response = future.result()
                assert response.status_code in [200, 403]  # Should not crash

    def test_experiment_permissions_with_special_characters(self, authenticated_client):
        """Test experiment permissions with special characters in experiment ID."""
        # Test with URL-encoded special characters
        special_ids = ["exp%20123", "exp-with-dashes", "exp_with_underscores"]

        for exp_id in special_ids:
            response = authenticated_client.get(f"/api/2.0/mlflow/permissions/experiments/{exp_id}/users")

            # Should handle special characters (may fail due to permissions, not parsing)
            assert response.status_code in [200, 403, 404]

    def test_experiment_permissions_performance(self, authenticated_client):
        """Test that experiment permissions endpoints respond in reasonable time."""
        import time

        endpoints = ["/api/2.0/mlflow/permissions/experiments", "/api/2.0/mlflow/permissions/experiments/123/users"]

        for endpoint in endpoints:
            start_time = time.time()
            response = authenticated_client.get(endpoint)
            end_time = time.time()

            # Should respond within reasonable time (5 seconds)
            assert (end_time - start_time) < 5.0
            assert response.status_code in [200, 403]
