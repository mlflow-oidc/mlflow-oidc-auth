"""
Comprehensive tests for the prompt permissions router.

This module tests all prompt permission endpoints including listing prompts,
getting prompt user permissions with various scenarios including authentication,
authorization, and error handling.
"""

import pytest
from unittest.mock import MagicMock, patch

from mlflow_oidc_auth.routers.prompt_permissions import (
    LIST_PROMPTS,
    PROMPT_GROUP_PERMISSIONS,
    PROMPT_USER_PERMISSIONS,
    get_prompt_groups,
    get_prompt_users,
    list_prompts,
    prompt_permissions_router,
)
from mlflow_oidc_auth.entities import User, RegisteredModelPermission as RegisteredModelPermissionEntity


class TestPromptPermissionsRouter:
    """Test class for prompt permissions router configuration."""

    def test_router_configuration(self):
        """Test that the prompt permissions router is properly configured."""
        assert prompt_permissions_router.prefix == "/api/2.0/mlflow/permissions/prompts"
        assert "prompt permissions" in prompt_permissions_router.tags
        assert 403 in prompt_permissions_router.responses
        assert 404 in prompt_permissions_router.responses

    def test_route_constants(self):
        """Test that route constants are properly defined."""
        assert LIST_PROMPTS == ""
        assert PROMPT_USER_PERMISSIONS == "/{prompt_name}/users"
        assert PROMPT_GROUP_PERMISSIONS == "/{prompt_name}/groups"


class TestGetPromptGroupsEndpoint:
    """Test the get prompt groups endpoint functionality."""

    @pytest.mark.asyncio
    async def test_get_prompt_groups_success(self, mock_store):
        mock_store.prompt_group_repo.list_groups_for_prompt.return_value = [("team-a", "READ"), ("team-b", "MANAGE")]

        with patch("mlflow_oidc_auth.routers.prompt_permissions.store", mock_store):
            result = await get_prompt_groups(prompt_name="test-prompt", _="admin@example.com")

        assert len(result) == 2
        assert result[0].name == "team-a"
        assert result[0].permission == "READ"
        assert result[0].kind == "group"
        assert result[1].name == "team-b"
        assert result[1].permission == "MANAGE"
        assert result[1].kind == "group"

    def test_get_prompt_groups_integration(self, admin_client, mock_store):
        mock_store.prompt_group_repo.list_groups_for_prompt.return_value = []
        response = admin_client.get("/api/2.0/mlflow/permissions/prompts/test-prompt/groups")
        assert response.status_code == 200


class TestGetPromptUsersEndpoint:
    """Test the get prompt users endpoint functionality."""

    @pytest.mark.asyncio
    async def test_get_prompt_users_success(self, mock_store):
        """Test successful retrieval of prompt users."""
        # Mock users with prompt permissions (stored as registered model permissions)
        user1 = User(
            id_=1,
            username="user1@example.com",
            password_hash="hash1",
            password_expiration=None,
            display_name="User 1",
            is_admin=False,
            is_service_account=False,
            registered_model_permissions=[RegisteredModelPermissionEntity(name="test-prompt", permission="MANAGE")],
        )

        user2 = User(
            id_=2,
            username="service@example.com",
            password_hash="hash2",
            password_expiration=None,
            display_name="Service Account",
            is_admin=False,
            is_service_account=True,
            registered_model_permissions=[RegisteredModelPermissionEntity(name="test-prompt", permission="READ")],
        )

        user3 = User(
            id_=3,
            username="user3@example.com",
            password_hash="hash3",
            password_expiration=None,
            display_name="User 3",
            is_admin=False,
            is_service_account=False,
            registered_model_permissions=[],  # No permissions for this prompt
        )

        mock_store.list_users.return_value = [user1, user2, user3]

        with patch("mlflow_oidc_auth.routers.prompt_permissions.store", mock_store):
            result = await get_prompt_users(prompt_name="test-prompt", admin_username="admin@example.com")

        assert len(result) == 2  # Only users with permissions for test-prompt

        # Check first user
        assert result[0].name == "user1@example.com"
        assert result[0].permission == "MANAGE"
        assert result[0].kind == "user"

        # Check service account
        assert result[1].name == "service@example.com"
        assert result[1].permission == "READ"
        assert result[1].kind == "service-account"

    @pytest.mark.asyncio
    async def test_get_prompt_users_no_permissions(self, mock_store):
        """Test getting prompt users when no users have permissions."""
        user1 = User(
            id_=1,
            username="user1@example.com",
            password_hash="hash1",
            password_expiration=None,
            display_name="User 1",
            is_admin=False,
            is_service_account=False,
            registered_model_permissions=[],
        )

        mock_store.list_users.return_value = [user1]

        result = await get_prompt_users(prompt_name="test-prompt", admin_username="admin@example.com")

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_prompt_users_multiple_prompts(self, mock_store):
        """Test getting users for specific prompt when users have multiple prompt permissions."""
        user1 = User(
            id_=1,
            username="user1@example.com",
            password_hash="hash1",
            password_expiration=None,
            display_name="User 1",
            is_admin=False,
            is_service_account=False,
            registered_model_permissions=[
                RegisteredModelPermissionEntity(name="prompt-1", permission="MANAGE"),
                RegisteredModelPermissionEntity(name="prompt-2", permission="READ"),
            ],
        )

        with patch("mlflow_oidc_auth.routers.prompt_permissions.store.list_users", return_value=[user1]):
            result = await get_prompt_users(prompt_name="prompt-1", admin_username="admin@example.com")

        assert len(result) == 1
        assert result[0].name == "user1@example.com"
        assert result[0].permission == "MANAGE"  # Should get permission for prompt-1

    @pytest.mark.asyncio
    async def test_get_prompt_users_no_registered_model_permissions_attr(self, mock_store):
        """Test getting users when user object doesn't have registered_model_permissions attribute."""
        user1 = User(
            id_=1,
            username="user1@example.com",
            password_hash="hash1",
            password_expiration=None,
            display_name="User 1",
            is_admin=False,
            is_service_account=False,
        )
        # Set registered_model_permissions to None to simulate missing attribute
        user1._registered_model_permissions = None

        mock_store.list_users.return_value = [user1]

        result = await get_prompt_users(prompt_name="test-prompt", admin_username="admin@example.com")

        assert len(result) == 0

    def test_get_prompt_users_integration(self, admin_client):
        """Test get prompt users endpoint through FastAPI test client."""
        response = admin_client.get("/api/2.0/mlflow/permissions/prompts/test-prompt/users")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_prompt_users_non_admin(self, authenticated_client):
        """Test get prompt users as non-admin user."""
        response = authenticated_client.get("/api/2.0/mlflow/permissions/prompts/test-prompt/users")

        # Should fail due to admin requirement
        assert response.status_code == 403

    def test_get_prompt_users_unauthenticated(self, client):
        """Test get prompt users without authentication."""
        response = client.get("/api/2.0/mlflow/permissions/prompts/test-prompt/users")

        # Should fail due to authentication requirement
        assert response.status_code in [401, 403]


class TestListPromptsEndpoint:
    """Test the list prompts endpoint functionality."""

    @pytest.mark.asyncio
    async def test_list_prompts_admin(self):
        """Test listing prompts as admin user."""
        # Mock prompts
        mock_prompt1 = MagicMock()
        mock_prompt1.name = "prompt-1"
        mock_prompt1.tags = {"type": "classification"}
        mock_prompt1.description = "Test Prompt 1"
        mock_prompt1.aliases = ["alias1"]

        mock_prompt2 = MagicMock()
        mock_prompt2.name = "prompt-2"
        mock_prompt2.tags = {"type": "generation"}
        mock_prompt2.description = "Test Prompt 2"
        mock_prompt2.aliases = []

        with patch("mlflow_oidc_auth.routers.prompt_permissions.fetch_all_prompts") as mock_fetch:
            mock_fetch.return_value = [mock_prompt1, mock_prompt2]

            result = await list_prompts(username="admin@example.com", is_admin=True)

            assert result.status_code == 200

            import json

            content = json.loads(bytes(result.body).decode())

            assert len(content) == 2
            assert content[0]["name"] == "prompt-1"
            assert content[0]["tags"] == {"type": "classification"}
            assert content[0]["description"] == "Test Prompt 1"
            assert content[0]["aliases"] == ["alias1"]

    @pytest.mark.asyncio
    async def test_list_prompts_regular_user_with_permissions(self):
        """Test listing prompts as regular user with manage permissions."""
        mock_prompt1 = MagicMock()
        mock_prompt1.name = "prompt-1"
        mock_prompt1.tags = {"type": "classification"}
        mock_prompt1.description = "Test Prompt 1"
        mock_prompt1.aliases = []

        mock_prompt2 = MagicMock()
        mock_prompt2.name = "prompt-2"
        mock_prompt2.tags = {"type": "generation"}
        mock_prompt2.description = "Test Prompt 2"
        mock_prompt2.aliases = []

        # Mock can_manage_registered_model to return True for prompt-1 only
        def mock_can_manage(prompt_name, username):
            return prompt_name == "prompt-1"

        with patch("mlflow_oidc_auth.routers.prompt_permissions.fetch_all_prompts") as mock_fetch, patch(
            "mlflow_oidc_auth.routers.prompt_permissions.can_manage_registered_model", side_effect=mock_can_manage
        ):
            mock_fetch.return_value = [mock_prompt1, mock_prompt2]

            result = await list_prompts(username="user@example.com", is_admin=False)

            assert result.status_code == 200

            import json

            content = json.loads(bytes(result.body).decode())

            assert len(content) == 1  # Only prompt-1 should be returned
            assert content[0]["name"] == "prompt-1"

    @pytest.mark.asyncio
    async def test_list_prompts_regular_user_no_permissions(self):
        """Test listing prompts as regular user with no permissions."""
        mock_prompt1 = MagicMock()
        mock_prompt1.name = "prompt-1"
        mock_prompt1.tags = {}
        mock_prompt1.description = "Test Prompt 1"
        mock_prompt1.aliases = []

        with patch("mlflow_oidc_auth.routers.prompt_permissions.fetch_all_prompts") as mock_fetch, patch(
            "mlflow_oidc_auth.routers.prompt_permissions.can_manage_registered_model", return_value=False
        ):
            mock_fetch.return_value = [mock_prompt1]

            result = await list_prompts(username="user@example.com", is_admin=False)

            assert result.status_code == 200

            import json

            content = json.loads(bytes(result.body).decode())

            assert len(content) == 0

    @pytest.mark.asyncio
    async def test_list_prompts_empty_list(self):
        """Test listing prompts when no prompts exist."""
        with patch("mlflow_oidc_auth.routers.prompt_permissions.fetch_all_prompts") as mock_fetch:
            mock_fetch.return_value = []

            result = await list_prompts(username="admin@example.com", is_admin=True)

            assert result.status_code == 200

            import json

            content = json.loads(bytes(result.body).decode())

            assert len(content) == 0

    @pytest.mark.asyncio
    async def test_list_prompts_with_none_values(self):
        """Test listing prompts with None values in prompt attributes."""
        mock_prompt = MagicMock()
        mock_prompt.name = "prompt-1"
        mock_prompt.tags = None
        mock_prompt.description = None
        mock_prompt.aliases = None

        with patch("mlflow_oidc_auth.routers.prompt_permissions.fetch_all_prompts") as mock_fetch:
            mock_fetch.return_value = [mock_prompt]

            result = await list_prompts(username="admin@example.com", is_admin=True)

            assert result.status_code == 200

            import json

            content = json.loads(bytes(result.body).decode())

            assert len(content) == 1
            assert content[0]["name"] == "prompt-1"
            assert content[0]["tags"] is None
            assert content[0]["description"] is None
            assert content[0]["aliases"] is None

    def test_list_prompts_integration_admin(self, admin_client):
        """Test list prompts endpoint through FastAPI test client as admin."""
        response = admin_client.get("/api/2.0/mlflow/permissions/prompts")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_prompts_integration_regular_user(self, authenticated_client):
        """Test list prompts endpoint through FastAPI test client as regular user."""
        response = authenticated_client.get("/api/2.0/mlflow/permissions/prompts")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_prompts_unauthenticated(self, client):
        """Test list prompts without authentication."""
        response = client.get("/api/2.0/mlflow/permissions/prompts")

        # Should fail due to authentication requirement
        assert response.status_code in [401, 403]


class TestPromptPermissionsRouterIntegration:
    """Test class for prompt permissions router integration scenarios."""

    def test_all_endpoints_require_authentication(self, client):
        """Test that all prompt permission endpoints require authentication."""
        endpoints = [("GET", "/api/2.0/mlflow/permissions/prompts"), ("GET", "/api/2.0/mlflow/permissions/prompts/test-prompt/users")]

        for method, endpoint in endpoints:
            response = client.get(endpoint)

            # Should require authentication
            assert response.status_code in [401, 403]

    def test_prompt_user_permissions_requires_admin(self, authenticated_client):
        """Test that prompt user permissions endpoint requires admin privileges."""
        response = authenticated_client.get("/api/2.0/mlflow/permissions/prompts/test-prompt/users")

        # Should fail due to admin requirement
        assert response.status_code == 403

    def test_endpoints_response_content_type(self, authenticated_client, admin_client):
        """Test that endpoints return proper content type."""
        # Test list prompts
        response = authenticated_client.get("/api/2.0/mlflow/permissions/prompts")
        assert "application/json" in response.headers.get("content-type", "")

        # Test prompt users (admin only)
        response = admin_client.get("/api/2.0/mlflow/permissions/prompts/test-prompt/users")
        assert "application/json" in response.headers.get("content-type", "")

    def test_prompt_name_parameter_validation(self, admin_client):
        """Test prompt name parameter validation."""
        # Test with various prompt name formats
        prompt_names = ["test-prompt", "prompt_with_underscores", "prompt123", "Prompt-Name"]

        for prompt_name in prompt_names:
            response = admin_client.get(f"/api/2.0/mlflow/permissions/prompts/{prompt_name}/users")

            # Should not fail due to parameter format
            assert response.status_code == 200

    def test_prompt_permissions_response_structure(self, authenticated_client):
        """Test that prompt permissions endpoints return proper response structure."""
        # Test list prompts response structure
        response = authenticated_client.get("/api/2.0/mlflow/permissions/prompts")

        assert response.status_code == 200
        prompts = response.json()
        assert isinstance(prompts, list)

        if prompts:  # If there are prompts
            prompt = prompts[0]
            assert "name" in prompt
            assert "tags" in prompt
            assert "description" in prompt
            assert "aliases" in prompt

    def test_prompt_users_response_structure(self, admin_client):
        """Test that prompt users endpoint returns proper response structure."""
        response = admin_client.get("/api/2.0/mlflow/permissions/prompts/test-prompt/users")

        assert response.status_code == 200
        users = response.json()
        assert isinstance(users, list)

        if users:  # If there are users with permissions
            user = users[0]
            assert "name" in user
            assert "permission" in user
            assert "kind" in user
            assert user["kind"] in ["user", "service-account"]

    def test_prompt_permissions_error_handling(self, admin_client):
        """Test error handling in prompt permissions endpoints."""
        # Test with empty prompt name
        response = admin_client.get("/api/2.0/mlflow/permissions/prompts//users")

        # Should handle invalid paths gracefully
        assert response.status_code in [404, 422]

    def test_prompt_permissions_concurrent_requests(self, authenticated_client):
        """Test that prompt permissions endpoints handle concurrent requests."""
        import concurrent.futures

        def make_request():
            return authenticated_client.get("/api/2.0/mlflow/permissions/prompts")

        # Make concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(5)]

            for future in concurrent.futures.as_completed(futures):
                response = future.result()
                assert response.status_code == 200  # Should not crash

    def test_prompt_permissions_with_special_characters(self, admin_client):
        """Test prompt permissions with special characters in prompt name."""
        # Test with URL-encoded special characters
        special_names = ["prompt%20name", "prompt-with-dashes", "prompt_with_underscores"]

        for prompt_name in special_names:
            response = admin_client.get(f"/api/2.0/mlflow/permissions/prompts/{prompt_name}/users")

            # Should handle special characters (may return empty list, but shouldn't crash)
            assert response.status_code == 200

    def test_prompt_permissions_performance(self, authenticated_client):
        """Test that prompt permissions endpoints respond in reasonable time."""
        import time

        endpoints = ["/api/2.0/mlflow/permissions/prompts"]

        for endpoint in endpoints:
            start_time = time.time()
            response = authenticated_client.get(endpoint)
            end_time = time.time()

            # Should respond within reasonable time (5 seconds)
            assert (end_time - start_time) < 5.0
            assert response.status_code == 200

    def test_prompt_permissions_with_long_prompt_names(self, admin_client):
        """Test prompt permissions with very long prompt names."""
        # Test with a very long prompt name
        long_prompt_name = "a" * 1000  # 1000 character prompt name

        response = admin_client.get(f"/api/2.0/mlflow/permissions/prompts/{long_prompt_name}/users")

        # Should handle long names gracefully (may return 404 or empty list)
        assert response.status_code in [200, 404]

    def test_prompt_permissions_case_sensitivity(self, admin_client):
        """Test prompt permissions case sensitivity."""
        # Test with different cases
        prompt_names = ["TestPrompt", "testprompt", "TESTPROMPT"]

        for prompt_name in prompt_names:
            response = admin_client.get(f"/api/2.0/mlflow/permissions/prompts/{prompt_name}/users")

            # Should handle different cases (behavior may vary based on implementation)
            assert response.status_code == 200

    def test_prompt_permissions_with_numeric_names(self, admin_client):
        """Test prompt permissions with numeric prompt names."""
        # Test with numeric names
        numeric_names = ["123", "456789", "0"]

        for prompt_name in numeric_names:
            response = admin_client.get(f"/api/2.0/mlflow/permissions/prompts/{prompt_name}/users")

            # Should handle numeric names
            assert response.status_code == 200

    def test_prompt_permissions_with_unicode_names(self, admin_client):
        """Test prompt permissions with unicode characters in prompt names."""
        # Test with unicode characters (URL encoded)
        unicode_names = ["prompt%E2%9C%93", "test%C3%A9"]  # ✓ and é encoded

        for prompt_name in unicode_names:
            response = admin_client.get(f"/api/2.0/mlflow/permissions/prompts/{prompt_name}/users")

            # Should handle unicode characters
            assert response.status_code == 200
