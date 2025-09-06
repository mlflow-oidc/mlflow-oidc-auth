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
    LIST_USERS,
    CREATE_USER,
    CREATE_ACCESS_TOKEN,
    DELETE_USER,
)
from mlflow_oidc_auth.models import CreateUserRequest, CreateAccessTokenRequest


class TestUsersRouter:
    """Test class for users router configuration."""

    def test_router_configuration(self):
        """Test that the users router is properly configured."""
        assert users_router.prefix == "/api/2.0/mlflow/users"
        assert "permissions" in users_router.tags
        assert "users" in users_router.tags
        assert 403 in users_router.responses
        assert 404 in users_router.responses

    def test_route_constants(self):
        """Test that route constants are properly defined."""
        assert LIST_USERS == ""
        assert CREATE_USER == "/create"
        assert CREATE_ACCESS_TOKEN == "/access-token"
        assert DELETE_USER == "/delete"


class TestListUsersEndpoint:
    """Test the list users endpoint functionality."""

    @pytest.mark.asyncio
    async def test_list_users_default(self, mock_store):
        """Test listing users with default parameters."""
        result = await list_users(username="test@example.com")

        assert isinstance(result.body, bytes)
        # Verify store was called with correct parameters
        mock_store.list_users.assert_called_once_with(is_service_account=False)

    @pytest.mark.asyncio
    async def test_list_users_service_accounts(self, mock_store):
        """Test listing service accounts only."""
        result = await list_users(service=True, username="test@example.com")

        # Verify store was called with service account filter
        mock_store.list_users.assert_called_once_with(is_service_account=True)

    @pytest.mark.asyncio
    async def test_list_users_exception_handling(self, mock_store):
        """Test list users exception handling."""
        mock_store.list_users.side_effect = Exception("Database error")

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
        response = client.get("/api/2.0/mlflow/users")

        # Should fail due to authentication requirement
        assert response.status_code in [401, 403]


class TestCreateAccessTokenEndpoint:
    """Test the create access token endpoint functionality."""

    @pytest.mark.asyncio
    async def test_create_access_token_for_self(self, mock_store, mock_user_management):
        """Test creating access token for authenticated user."""
        result = await create_access_token(token_request=None, current_username="test@example.com")

        assert result.status_code == 200

        # Verify token generation was called
        mock_user_management["generate_token"].assert_called_once()
        mock_store.update_user.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_access_token_for_other_user(self, mock_store, mock_user_management):
        """Test creating access token for another user."""
        token_request = CreateAccessTokenRequest(username="other@example.com")

        result = await create_access_token(token_request=token_request, current_username="test@example.com")

        assert result.status_code == 200

        # Verify token was created for the specified user
        mock_store.update_user.assert_called_once()
        call_args = mock_store.update_user.call_args
        assert call_args[1]["username"] == "other@example.com"

    @pytest.mark.asyncio
    async def test_create_access_token_with_expiration(self, mock_store, mock_user_management):
        """Test creating access token with expiration date."""
        future_date = datetime.now(timezone.utc) + timedelta(days=30)
        token_request = CreateAccessTokenRequest(expiration=future_date.isoformat())

        result = await create_access_token(token_request=token_request, current_username="test@example.com")

        assert result.status_code == 200

        # Verify expiration was set
        mock_store.update_user.assert_called_once()
        call_args = mock_store.update_user.call_args
        assert call_args[1]["password_expiration"] is not None

    @pytest.mark.asyncio
    async def test_create_access_token_past_expiration(self, mock_store):
        """Test creating access token with past expiration date."""
        past_date = datetime.now(timezone.utc) - timedelta(days=1)
        token_request = CreateAccessTokenRequest(expiration=past_date.isoformat())

        with pytest.raises(HTTPException) as exc_info:
            await create_access_token(token_request=token_request, current_username="test@example.com")

        assert exc_info.value.status_code == 400
        assert "must be in the future" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_access_token_far_future_expiration(self, mock_store):
        """Test creating access token with expiration too far in future."""
        far_future_date = datetime.now(timezone.utc) + timedelta(days=400)
        token_request = CreateAccessTokenRequest(expiration=far_future_date.isoformat())

        with pytest.raises(HTTPException) as exc_info:
            await create_access_token(token_request=token_request, current_username="test@example.com")

        assert exc_info.value.status_code == 400
        assert "less than 1 year" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_access_token_invalid_expiration_format(self, mock_store):
        """Test creating access token with invalid expiration format."""
        token_request = CreateAccessTokenRequest(expiration="invalid-date-format")

        with pytest.raises(HTTPException) as exc_info:
            await create_access_token(token_request=token_request, current_username="test@example.com")

        assert exc_info.value.status_code == 400
        assert "Invalid expiration date format" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_access_token_user_not_found(self, mock_store):
        """Test creating access token for non-existent user."""
        mock_store.get_user.return_value = None
        token_request = CreateAccessTokenRequest(username="nonexistent@example.com")

        with pytest.raises(HTTPException) as exc_info:
            await create_access_token(token_request=token_request, current_username="test@example.com")

        assert exc_info.value.status_code == 404
        assert "User nonexistent@example.com not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_access_token_exception_handling(self, mock_store, mock_user_management):
        """Test create access token exception handling."""
        mock_user_management["generate_token"].side_effect = Exception("Token generation failed")

        with pytest.raises(HTTPException) as exc_info:
            await create_access_token(token_request=None, current_username="test@example.com")

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
        request_data = {"username": "test@example.com", "expiration": future_date.isoformat()}

        response = authenticated_client.patch("/api/2.0/mlflow/users/access-token", json=request_data)

        assert response.status_code == 200
        assert "token" in response.json()


class TestCreateUserEndpoint:
    """Test the create user endpoint functionality."""

    @pytest.mark.asyncio
    async def test_create_user_success(self, mock_user_management):
        """Test successful user creation."""
        user_request = CreateUserRequest(username="newuser@example.com", display_name="New User", is_admin=False, is_service_account=False)

        result = await create_new_user(user_request=user_request, admin_username="admin@example.com")

        assert result.status_code == 201

        # Verify user creation was called with correct parameters
        mock_user_management["create_user"].assert_called_once_with(
            username="newuser@example.com", display_name="New User", is_admin=False, is_service_account=False
        )

    @pytest.mark.asyncio
    async def test_create_admin_user(self, mock_user_management):
        """Test creating admin user."""
        user_request = CreateUserRequest(username="admin2@example.com", display_name="Admin User 2", is_admin=True, is_service_account=False)

        result = await create_new_user(user_request=user_request, admin_username="admin@example.com")

        assert result.status_code == 201

        # Verify admin flag was passed correctly
        call_args = mock_user_management["create_user"].call_args
        assert call_args[1]["is_admin"] is True

    @pytest.mark.asyncio
    async def test_create_service_account(self, mock_user_management):
        """Test creating service account."""
        user_request = CreateUserRequest(username="service2@example.com", display_name="Service Account 2", is_admin=False, is_service_account=True)

        result = await create_new_user(user_request=user_request, admin_username="admin@example.com")

        assert result.status_code == 201

        # Verify service account flag was passed correctly
        call_args = mock_user_management["create_user"].call_args
        assert call_args[1]["is_service_account"] is True

    @pytest.mark.asyncio
    async def test_create_user_already_exists(self, mock_user_management):
        """Test creating user that already exists."""
        mock_user_management["create_user"].return_value = (False, "User already exists")

        user_request = CreateUserRequest(username="existing@example.com", display_name="Existing User", is_admin=False, is_service_account=False)

        result = await create_new_user(user_request=user_request, admin_username="admin@example.com")

        assert result.status_code == 200  # Updated, not created

    @pytest.mark.asyncio
    async def test_create_user_exception_handling(self, mock_user_management):
        """Test create user exception handling."""
        mock_user_management["create_user"].side_effect = Exception("Database error")

        user_request = CreateUserRequest(username="newuser@example.com", display_name="New User", is_admin=False, is_service_account=False)

        with pytest.raises(HTTPException) as exc_info:
            await create_new_user(user_request=user_request, admin_username="admin@example.com")

        assert exc_info.value.status_code == 500
        assert "Failed to create user" in str(exc_info.value.detail)

    def test_create_user_integration_admin(self, admin_client):
        """Test create user endpoint through FastAPI test client as admin."""
        user_data = {"username": "newuser@example.com", "display_name": "New User", "is_admin": False, "is_service_account": False}

        response = admin_client.post("/api/2.0/mlflow/users/create", json=user_data)

        assert response.status_code in [200, 201]
        assert "message" in response.json()

    def test_create_user_integration_non_admin(self, authenticated_client):
        """Test create user endpoint as non-admin user."""
        user_data = {"username": "newuser@example.com", "display_name": "New User", "is_admin": False, "is_service_account": False}

        response = authenticated_client.post("/api/2.0/mlflow/users/create", json=user_data)

        # Should fail due to insufficient permissions
        assert response.status_code == 403


class TestDeleteUserEndpoint:
    """Test the delete user endpoint functionality."""

    @pytest.mark.asyncio
    async def test_delete_user_success(self, mock_store):
        """Test successful user deletion."""
        result = await delete_user(username="user@example.com", admin_username="admin@example.com")

        assert result.status_code == 200

        # Verify user deletion was called
        mock_store.delete_user.assert_called_once_with("user@example.com")

    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, mock_store):
        """Test deleting non-existent user."""
        mock_store.get_user.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await delete_user(username="nonexistent@example.com", admin_username="admin@example.com")

        assert exc_info.value.status_code == 404
        assert "User nonexistent@example.com not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_delete_user_exception_handling(self, mock_store):
        """Test delete user exception handling."""
        mock_store.delete_user.side_effect = Exception("Database error")

        with pytest.raises(HTTPException) as exc_info:
            await delete_user(username="user@example.com", admin_username="admin@example.com")

        assert exc_info.value.status_code == 500
        assert "Failed to delete user" in str(exc_info.value.detail)

    def test_delete_user_integration_admin(self, admin_client):
        """Test delete user endpoint through FastAPI test client as admin."""
        response = admin_client.delete("/api/2.0/mlflow/users/delete", json={"username": "user@example.com"})

        assert response.status_code == 200
        assert "message" in response.json()

    def test_delete_user_integration_non_admin(self, authenticated_client):
        """Test delete user endpoint as non-admin user."""
        response = authenticated_client.delete("/api/2.0/mlflow/users/delete", json={"username": "user@example.com"})

        # Should fail due to insufficient permissions
        assert response.status_code == 403

    def test_delete_user_invalid_request_body(self, admin_client):
        """Test delete user with invalid request body."""
        response = admin_client.delete("/api/2.0/mlflow/users/delete", json={"invalid_field": "value"})

        # Should fail due to missing username field
        assert response.status_code == 422


class TestUsersRouterIntegration:
    """Test class for users router integration scenarios."""

    def test_all_endpoints_require_authentication(self, client):
        """Test that all user endpoints require authentication."""
        endpoints = [
            ("GET", "/api/2.0/mlflow/users"),
            ("PATCH", "/api/2.0/mlflow/users/access-token"),
            ("POST", "/api/2.0/mlflow/users/create"),
            ("DELETE", "/api/2.0/mlflow/users/delete"),
        ]

        for method, endpoint in endpoints:
            if method == "GET":
                response = client.get(endpoint)
            elif method == "PATCH":
                response = client.patch(endpoint)
            elif method == "POST":
                response = client.post(endpoint, json={})
            elif method == "DELETE":
                response = client.delete(endpoint, json={})

            # Should require authentication
            assert response.status_code in [401, 403]

    def test_admin_endpoints_require_admin_privileges(self, authenticated_client):
        """Test that admin endpoints require admin privileges."""
        admin_endpoints = [
            ("POST", "/api/2.0/mlflow/users/create", {"username": "test", "display_name": "Test"}),
            ("DELETE", "/api/2.0/mlflow/users/delete", {"username": "test"}),
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
        endpoints_with_body = [("POST", "/api/2.0/mlflow/users/create"), ("DELETE", "/api/2.0/mlflow/users/delete")]

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
        response = admin_client.post("/api/2.0/mlflow/users/create", json=user_data)
        assert "application/json" in response.headers.get("content-type", "")
