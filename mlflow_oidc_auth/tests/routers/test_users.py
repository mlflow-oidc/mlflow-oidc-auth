"""
Comprehensive tests for the users router.

This module tests all user management endpoints including listing users,
creating users, creating access tokens, and deleting users with various
scenarios including authentication, authorization, and error handling.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException

from mlflow_oidc_auth.routers.users import (
    users_router,
    list_users,
    create_new_user,
    create_access_token,
    delete_user,
    get_user_information,
    CREATE_ACCESS_TOKEN,
)
from mlflow_oidc_auth.models import CreateUserRequest, CreateAccessTokenRequest


class TestUsersRouter:
    """Test class for users router configuration."""

    def test_router_configuration(self):
        """Test that the users router is properly configured."""
        assert users_router.prefix == "/api/2.0/mlflow/users"
        assert "users" in users_router.tags
        assert 403 in users_router.responses
        assert 404 in users_router.responses

    def test_route_constants(self):
        """Test that route constants are properly defined."""
        assert CREATE_ACCESS_TOKEN == "/access-token"


class TestListUsersEndpoint:
    """Test the list users endpoint functionality."""

    @pytest.mark.asyncio
    async def test_list_users_default(self, mock_store):
        """Test listing users with default parameters."""
        with patch("mlflow_oidc_auth.store.store", mock_store):
            result = await list_users(username="test@example.com")

        assert isinstance(result.body, bytes)
        # Verify store was called with correct parameters
        mock_store.list_users.assert_called_once_with(is_service_account=False)

    @pytest.mark.asyncio
    async def test_list_users_service_accounts(self, mock_store):
        """Test listing service accounts only."""
        with patch("mlflow_oidc_auth.store.store", mock_store):
            result = await list_users(service=True, username="test@example.com")

        # Verify store was called with service account filter
        mock_store.list_users.assert_called_once_with(is_service_account=True)

    @pytest.mark.asyncio
    async def test_list_users_exception_handling(self, mock_store):
        """Test list users exception handling."""
        mock_store.list_users.side_effect = Exception("Database error")

        with patch("mlflow_oidc_auth.store.store", mock_store):
            with pytest.raises(HTTPException) as exc_info:
                await list_users(username="test@example.com")

        assert exc_info.value.status_code == 500
        assert "Failed to retrieve users" in str(exc_info.value.detail)

    def test_list_users_integration(self, authenticated_client):
        """Test list users endpoint through FastAPI test client."""
        response = authenticated_client.get("/api/2.0/mlflow/users")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_users_service_filter_integration(self, authenticated_client):
        """Test list users with service account filter."""
        response = authenticated_client.get("/api/2.0/mlflow/users?service=true")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_users_unauthenticated(self, client):
        """Test list users without authentication."""
        with pytest.raises(Exception) as exc_info:
            client.get("/api/2.0/mlflow/users")

        # Should fail due to authentication requirement
        assert "Authentication required" in str(exc_info.value)


class TestCreateAccessTokenEndpoint:
    """Test the create access token endpoint functionality."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.users.generate_token")
    async def test_create_access_token_for_self(self, mock_generate_token, mock_store):
        """Test creating access token for authenticated user."""
        mock_user = MagicMock()
        mock_store.get_user.side_effect = None
        mock_store.get_user.return_value = mock_user
        mock_generate_token.return_value = "generated_token_123"

        with patch("mlflow_oidc_auth.routers.users.store", mock_store):
            result = await create_access_token(token_request=None, current_username="test@example.com", is_admin=False)

        assert result.status_code == 200
        mock_generate_token.assert_called_once()
        mock_store.update_user.assert_called_once()

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.users.generate_token")
    async def test_create_access_token_for_other_user_requires_admin(self, mock_generate_token, mock_store):
        """Test creating access token for another user requires admin."""
        mock_user = MagicMock()
        mock_store.get_user.side_effect = None
        mock_store.get_user.return_value = mock_user
        mock_generate_token.return_value = "generated_token_123"

        token_request = CreateAccessTokenRequest(username="other@example.com")

        with patch("mlflow_oidc_auth.routers.users.store", mock_store):
            with pytest.raises(HTTPException) as exc_info:
                await create_access_token(token_request=token_request, current_username="test@example.com", is_admin=False)

        assert exc_info.value.status_code == 403
        assert "Administrator privileges required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.users.generate_token")
    async def test_create_access_token_for_other_user_as_admin(self, mock_generate_token, mock_store):
        """Test admin creating access token for another user."""
        mock_user = MagicMock()
        mock_store.get_user.side_effect = None
        mock_store.get_user.return_value = mock_user
        mock_generate_token.return_value = "generated_token_123"

        token_request = CreateAccessTokenRequest(username="other@example.com")

        with patch("mlflow_oidc_auth.routers.users.store", mock_store):
            result = await create_access_token(token_request=token_request, current_username="admin@example.com", is_admin=True)

        assert result.status_code == 200
        mock_generate_token.assert_called_once()
        mock_store.update_user.assert_called_once()
        call_args = mock_store.update_user.call_args
        assert call_args[1]["username"] == "other@example.com"

    @pytest.mark.asyncio
    async def test_create_access_token_with_expiration(self, mock_user_management, mock_store):
        """Test creating access token with expiration date."""
        mock_user = MagicMock()
        mock_store.get_user.side_effect = None
        mock_store.get_user.return_value = mock_user

        future_date = datetime.now(timezone.utc) + timedelta(days=30)
        token_request = CreateAccessTokenRequest(expiration=future_date.isoformat())

        with patch("mlflow_oidc_auth.routers.users.store", mock_store):
            result = await create_access_token(token_request=token_request, current_username="test@example.com", is_admin=False)

        assert result.status_code == 200
        mock_store.update_user.assert_called_once()
        call_args = mock_store.update_user.call_args
        assert call_args[1]["password_expiration"] is not None

    @pytest.mark.asyncio
    async def test_create_access_token_past_expiration(self, mock_store):
        """Test creating access token with past expiration date."""
        mock_user = MagicMock()
        mock_store.get_user.side_effect = None
        mock_store.get_user.return_value = mock_user

        past_date = datetime.now(timezone.utc) - timedelta(days=1)
        token_request = CreateAccessTokenRequest(expiration=past_date.isoformat())

        with patch("mlflow_oidc_auth.routers.users.store", mock_store):
            with pytest.raises(HTTPException) as exc_info:
                await create_access_token(token_request=token_request, current_username="test@example.com", is_admin=False)

        assert exc_info.value.status_code == 400
        assert "must be in the future" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_access_token_far_future_expiration(self, mock_store):
        """Test creating access token with expiration too far in future."""
        mock_user = MagicMock()
        mock_store.get_user.side_effect = None
        mock_store.get_user.return_value = mock_user

        far_future_date = datetime.now(timezone.utc) + timedelta(days=400)
        token_request = CreateAccessTokenRequest(expiration=far_future_date.isoformat())

        with patch("mlflow_oidc_auth.routers.users.store", mock_store):
            with pytest.raises(HTTPException) as exc_info:
                await create_access_token(token_request=token_request, current_username="test@example.com", is_admin=False)

        assert exc_info.value.status_code == 400
        assert "less than 1 year" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_access_token_invalid_expiration_format(self, mock_store):
        """Test creating access token with invalid expiration format."""
        mock_user = MagicMock()
        mock_store.get_user.side_effect = None
        mock_store.get_user.return_value = mock_user

        token_request = CreateAccessTokenRequest(expiration="invalid-date-format")

        with patch("mlflow_oidc_auth.routers.users.store", mock_store):
            with pytest.raises(HTTPException) as exc_info:
                await create_access_token(token_request=token_request, current_username="test@example.com", is_admin=False)

        assert exc_info.value.status_code == 400
        assert "Invalid expiration date format" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_access_token_user_not_found(self, mock_store):
        """Test admin creating access token for non-existent user returns 404."""
        mock_store.get_user.side_effect = None
        mock_store.get_user.return_value = None
        token_request = CreateAccessTokenRequest(username="nonexistent@example.com")

        with patch("mlflow_oidc_auth.routers.users.store", mock_store):
            with pytest.raises(HTTPException) as exc_info:
                await create_access_token(token_request=token_request, current_username="admin@example.com", is_admin=True)

        assert exc_info.value.status_code == 404
        assert "User nonexistent@example.com not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_access_token_user_not_found_non_admin_forbidden(self, mock_store):
        """Test non-admin cannot probe other usernames even if missing."""
        mock_store.get_user.side_effect = None
        mock_store.get_user.return_value = None
        token_request = CreateAccessTokenRequest(username="nonexistent@example.com")

        with patch("mlflow_oidc_auth.routers.users.store", mock_store):
            with pytest.raises(HTTPException) as exc_info:
                await create_access_token(token_request=token_request, current_username="user@example.com", is_admin=False)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.users.generate_token")
    async def test_create_access_token_exception_handling(self, mock_generate_token, mock_store):
        """Test create access token exception handling."""
        mock_user = MagicMock()
        mock_store.get_user.side_effect = None
        mock_store.get_user.return_value = mock_user
        mock_generate_token.side_effect = Exception("Token generation failed")

        with patch("mlflow_oidc_auth.routers.users.store", mock_store):
            with pytest.raises(HTTPException) as exc_info:
                await create_access_token(token_request=None, current_username="test@example.com", is_admin=False)

        assert exc_info.value.status_code == 500
        assert "Failed to create access token" in str(exc_info.value.detail)

    def test_create_access_token_integration(self, authenticated_client):
        """Test create access token endpoint through FastAPI test client."""
        response = authenticated_client.patch("/api/2.0/mlflow/users/access-token")

        assert response.status_code == 200
        assert "token" in response.json()

    def test_create_access_token_with_body_integration(self, authenticated_client):
        """Test create access token with request body."""
        future_date = datetime.now(timezone.utc) + timedelta(days=30)
        request_data = {"username": "user@example.com", "expiration": future_date.isoformat()}

        response = authenticated_client.patch("/api/2.0/mlflow/users/access-token", json=request_data)

        assert response.status_code == 200
        assert "token" in response.json()

    def test_create_access_token_for_other_user_forbidden_integration(self, authenticated_client):
        """Test non-admin cannot create token for another user."""
        request_data = {"username": "admin@example.com"}

        response = authenticated_client.patch("/api/2.0/mlflow/users/access-token", json=request_data)

        assert response.status_code == 403

    def test_create_access_token_for_other_user_admin_integration(self, admin_client):
        """Test admin can create token for another user."""
        request_data = {"username": "user@example.com"}

        response = admin_client.patch("/api/2.0/mlflow/users/access-token", json=request_data)

        assert response.status_code == 200
        assert "token" in response.json()


class TestGetUserInformationEndpoint:
    """Test the get user information endpoint functionality."""

    @pytest.mark.asyncio
    async def test_get_user_information_unit(self, mock_store):
        """Test get_user_information returns user data when called by admin."""
        mock_user = MagicMock()
        mock_user.to_json.return_value = {"username": "user@example.com"}
        mock_store.get_user.return_value = mock_user

        with patch("mlflow_oidc_auth.routers.users.store", mock_store):
            result = await get_user_information(username="user@example.com", admin_username="admin@example.com")

        assert result.status_code == 200
        mock_store.get_user.assert_called_once_with("user@example.com")

    def test_get_user_information_admin_integration(self, admin_client):
        """Test admin can retrieve arbitrary user information."""
        response = admin_client.get("/api/2.0/mlflow/users/user@example.com")

        assert response.status_code == 200

    def test_get_user_information_non_admin_forbidden_integration(self, authenticated_client):
        """Test non-admin cannot retrieve user information for arbitrary user."""
        response = authenticated_client.get("/api/2.0/mlflow/users/user@example.com")

        assert response.status_code == 403


class TestCreateUserEndpoint:
    """Test the create user endpoint functionality."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.users.create_user")
    async def test_create_user_success(self, mock_create_user, mock_store):
        """Test successful user creation."""
        mock_create_user.return_value = (True, "User created successfully")

        user_request = CreateUserRequest(username="newuser@example.com", display_name="New User", is_admin=False, is_service_account=False)

        result = await create_new_user(user_request=user_request, admin_username="admin@example.com")

        assert result.status_code == 201

        # Verify user creation was called with correct parameters
        mock_create_user.assert_called_once_with(username="newuser@example.com", display_name="New User", is_admin=False, is_service_account=False)

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.users.create_user")
    async def test_create_admin_user(self, mock_create_user, mock_store):
        """Test creating admin user."""
        mock_create_user.return_value = (True, "User created successfully")

        user_request = CreateUserRequest(username="admin2@example.com", display_name="Admin User 2", is_admin=True, is_service_account=False)

        result = await create_new_user(user_request=user_request, admin_username="admin@example.com")

        assert result.status_code == 201

        # Verify admin flag was passed correctly
        call_args = mock_create_user.call_args
        assert call_args[1]["is_admin"] is True

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.users.create_user")
    async def test_create_service_account(self, mock_create_user, mock_store):
        """Test creating service account."""
        mock_create_user.return_value = (True, "User created successfully")

        user_request = CreateUserRequest(username="service2@example.com", display_name="Service Account 2", is_admin=False, is_service_account=True)

        result = await create_new_user(user_request=user_request, admin_username="admin@example.com")

        assert result.status_code == 201

        # Verify service account flag was passed correctly
        call_args = mock_create_user.call_args
        assert call_args[1]["is_service_account"] is True

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.users.create_user")
    async def test_create_user_already_exists(self, mock_create_user, mock_store):
        """Test creating user that already exists."""
        mock_create_user.return_value = (False, "User already exists")

        user_request = CreateUserRequest(username="existing@example.com", display_name="Existing User", is_admin=False, is_service_account=False)

        result = await create_new_user(user_request=user_request, admin_username="admin@example.com")

        assert result.status_code == 200  # Updated, not created

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.users.create_user")
    async def test_create_user_exception_handling(self, mock_create_user, mock_store):
        """Test create user exception handling."""
        mock_create_user.side_effect = Exception("Database error")

        user_request = CreateUserRequest(username="newuser@example.com", display_name="New User", is_admin=False, is_service_account=False)

        with pytest.raises(HTTPException) as exc_info:
            await create_new_user(user_request=user_request, admin_username="admin@example.com")

        assert exc_info.value.status_code == 500
        assert "Failed to create user" in str(exc_info.value.detail)

    def test_create_user_integration_admin(self, admin_client):
        """Test create user endpoint through FastAPI test client as admin."""
        user_data = {"username": "newuser@example.com", "display_name": "New User", "is_admin": False, "is_service_account": False}

        response = admin_client.post("/api/2.0/mlflow/users", json=user_data)

        assert response.status_code in [200, 201]
        assert "message" in response.json()

    def test_create_user_integration_non_admin(self, authenticated_client):
        """Test create user endpoint as non-admin user."""
        user_data = {"username": "newuser@example.com", "display_name": "New User", "is_admin": False, "is_service_account": False}

        response = authenticated_client.post("/api/2.0/mlflow/users", json=user_data)

        # Should fail due to insufficient permissions
        assert response.status_code == 403


class TestDeleteUserEndpoint:
    """Test the delete user endpoint functionality."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.users.store")
    async def test_delete_user_success(self, mock_store_patch):
        """Test successful user deletion."""
        # Mock the user object
        mock_user = MagicMock()
        mock_store_patch.get_user.return_value = mock_user
        mock_store_patch.delete_user.return_value = None

        result = await delete_user(username="user@example.com", admin_username="admin@example.com")

        assert result.status_code == 200

        # Verify user deletion was called
        mock_store_patch.delete_user.assert_called_once_with("user@example.com")

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.users.store")
    async def test_delete_user_not_found(self, mock_store_patch):
        """Test deleting non-existent user."""
        mock_store_patch.get_user.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await delete_user(username="nonexistent@example.com", admin_username="admin@example.com")

        assert exc_info.value.status_code == 404
        assert "User nonexistent@example.com not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.users.store")
    async def test_delete_user_exception_handling(self, mock_store_patch):
        """Test delete user exception handling."""
        # Mock the user object
        mock_user = MagicMock()
        mock_store_patch.get_user.return_value = mock_user
        mock_store_patch.delete_user.side_effect = Exception("Database error")

        with pytest.raises(HTTPException) as exc_info:
            await delete_user(username="user@example.com", admin_username="admin@example.com")

        assert exc_info.value.status_code == 500
        assert "Failed to delete user" in str(exc_info.value.detail)

    def test_delete_user_integration_admin(self, admin_client):
        """Test delete user endpoint through FastAPI test client as admin."""
        response = admin_client.delete("/api/2.0/mlflow/users", json={"username": "user@example.com"})

        assert response.status_code == 200
        assert "message" in response.json()

    def test_delete_user_integration_non_admin(self, authenticated_client):
        """Test delete user endpoint as non-admin user."""
        response = authenticated_client.delete("/api/2.0/mlflow/users", json={"username": "user@example.com"})

        # Should fail due to insufficient permissions
        assert response.status_code == 403

    def test_delete_user_invalid_request_body(self, admin_client):
        """Test delete user with invalid request body."""
        response = admin_client.delete("/api/2.0/mlflow/users", json={"invalid_field": "value"})

        # Should fail due to missing username field
        assert response.status_code == 422


class TestUsersRouterIntegration:
    """Test class for users router integration scenarios."""

    def test_all_endpoints_require_authentication(self, client):
        """Test that all user endpoints require authentication."""
        endpoints = [
            ("GET", "/api/2.0/mlflow/users"),
            ("PATCH", "/api/2.0/mlflow/users/access-token"),
            ("POST", "/api/2.0/mlflow/users"),
            ("DELETE", "/api/2.0/mlflow/users"),
        ]

        for method, endpoint in endpoints:
            try:
                if method == "GET":
                    response = client.get(endpoint)
                elif method == "PATCH":
                    response = client.patch(endpoint)
                elif method == "POST":
                    response = client.post(endpoint, json={})
                elif method == "DELETE":
                    response = client.delete(endpoint)
            except Exception as exc:
                # TestClientWrapper.get historically raises on unauthenticated GETs
                assert "Authentication required" in str(exc)
                continue

            # If no exception was raised, the endpoint should return 401 or 403
            assert response.status_code in [401, 403]

    def test_admin_endpoints_require_admin_privileges(self, authenticated_client):
        """Test that admin endpoints require admin privileges."""
        admin_endpoints = [
            ("POST", "/api/2.0/mlflow/users", {"username": "test", "display_name": "Test"}),
            ("DELETE", "/api/2.0/mlflow/users", {"username": "test"}),
        ]

        for method, endpoint, data in admin_endpoints:
            if method == "POST":
                response = authenticated_client.post(endpoint, json=data)
            elif method == "DELETE":
                response = authenticated_client.delete(endpoint, json=data)

            # Should require admin privileges
            assert response.status_code == 403

    def test_endpoints_with_invalid_json(self, authenticated_client):
        """Test endpoints with invalid JSON data."""
        endpoints_with_body = [("POST", "/api/2.0/mlflow/users"), ("DELETE", "/api/2.0/mlflow/users")]

        for method, endpoint in endpoints_with_body:
            if method == "POST":
                response = authenticated_client.post(endpoint, data="invalid json")
            elif method == "DELETE":
                response = authenticated_client.delete(endpoint, data="invalid json")

            # Should return 422 for invalid JSON
            assert response.status_code == 422

    def test_endpoints_response_content_type(self, authenticated_client, admin_client):
        """Test that endpoints return proper content type."""
        # Test list users
        response = authenticated_client.get("/api/2.0/mlflow/users")
        assert "application/json" in response.headers.get("content-type", "")

        # Test create access token
        response = authenticated_client.patch("/api/2.0/mlflow/users/access-token")
        assert "application/json" in response.headers.get("content-type", "")

        # Test create user (admin only)
        user_data = {"username": "test@example.com", "display_name": "Test User", "is_admin": False, "is_service_account": False}
        response = admin_client.post("/api/2.0/mlflow/users", json=user_data)
        assert "application/json" in response.headers.get("content-type", "")
