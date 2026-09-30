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
    get_current_user_information,
    get_user_information,
    CREATE_ACCESS_TOKEN,
    CURRENT_USER,
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


class TestCurrentUserProfileEndpoint:
    """Tests for the lightweight current-user profile endpoint."""

    @pytest.mark.asyncio
    async def test_get_current_user_profile_direct(self, mock_store):
        """Direct call returns a lightweight model (no permissions collections)."""

        # Ensure the mock supports the lightweight method.
        mock_store.get_user_profile.side_effect = mock_store.get_user.side_effect

        with patch("mlflow_oidc_auth.routers.users.store", mock_store):
            result = await get_current_user_information(current_username="user@example.com")

        assert result.username == "user@example.com"
        assert result.is_admin is False
        assert isinstance(result.groups, list)

    def test_get_current_user_profile_integration(self, authenticated_client):
        """Endpoint returns only basic profile fields."""

        resp = authenticated_client.get(f"/api/2.0/mlflow/users{CURRENT_USER}")

        assert resp.status_code == 200
        payload = resp.json()
        assert set(payload.keys()) == {
            "display_name",
            "groups",
            "id",
            "is_admin",
            "is_service_account",
            "username",
        }


class TestListUsersEndpoint:
    """Test the list users endpoint functionality."""

    @pytest.mark.asyncio
    async def test_list_users_default(self, mock_store):
        """Test listing users with default parameters."""
        mock_store.list_usernames.return_value = [
            "alice@example.com",
            "bob@example.com",
        ]
        with patch("mlflow_oidc_auth.store.store", mock_store):
            result = await list_users(username="test@example.com")

        assert isinstance(result.body, bytes)
        # Verify store was called with correct parameters
        mock_store.list_usernames.assert_called_once_with(is_service_account=False)

    @pytest.mark.asyncio
    async def test_list_users_service_accounts(self, mock_store):
        """Test listing service accounts only."""
        mock_store.list_usernames.return_value = ["svc@example.com"]
        with patch("mlflow_oidc_auth.store.store", mock_store):
            await list_users(service=True, username="test@example.com")

        # Verify store was called with service account filter
        mock_store.list_usernames.assert_called_once_with(is_service_account=True)

    @pytest.mark.asyncio
    async def test_list_users_exception_handling(self, mock_store):
        """Test list users exception handling."""
        mock_store.list_usernames.side_effect = Exception("Database error")

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


def _token_record(name="default", token_id=7):
    from mlflow_oidc_auth.repository.user_token import UserTokenRecord

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return UserTokenRecord(
        id=token_id, name=name, token_prefix="ab12cd34", created_at=now, created_by="x", expires_at=now + timedelta(days=30), last_used_at=None
    )


class TestCreateAccessTokenEndpoint:
    """``PATCH /users/access-token``: replaces the caller's ``default`` token (issue #189)."""

    @pytest.fixture
    def store(self, mock_store):
        mock_store.replace_user_token.return_value = (_token_record(), "mlf_ab12cd34_secret", True)
        with patch("mlflow_oidc_auth.routers.users.store", mock_store):
            yield mock_store

    @pytest.mark.asyncio
    async def test_create_access_token_for_self(self, store):
        result = await create_access_token(token_request=None, current_username="user@example.com", is_admin=False)

        assert result.status_code == 200
        body = result.body.decode()
        assert "mlf_ab12cd34_secret" in body and "expires_at" in body
        username, name, expires_at = store.replace_user_token.call_args.args
        assert (username, name) == ("user@example.com", "default")
        assert result.headers["cache-control"] == "no-store"

    @pytest.mark.asyncio
    async def test_omitted_expiration_is_one_year_never_unlimited(self, store):
        """Tokens must expire: an omitted expiration is a year, not 'does not expire'."""
        await create_access_token(token_request=None, current_username="user@example.com", is_admin=False)

        expires_at = store.replace_user_token.call_args.args[2]
        assert expires_at is not None
        assert timedelta(days=364) < expires_at - datetime.now(timezone.utc) <= timedelta(days=365)

    @pytest.mark.asyncio
    async def test_the_requested_expiration_is_passed_as_utc(self, store):
        when = (datetime.now(timezone.utc) + timedelta(days=30)).replace(microsecond=0)
        await create_access_token(
            token_request=CreateAccessTokenRequest(expiration=when.astimezone(timezone(timedelta(hours=14))).isoformat()),
            current_username="user@example.com",
            is_admin=False,
        )

        expires_at = store.replace_user_token.call_args.args[2]
        assert expires_at == when and expires_at.utcoffset() == timedelta(0)

    @pytest.mark.asyncio
    async def test_non_admin_cannot_rotate_another_users_token(self, store):
        with pytest.raises(HTTPException) as exc_info:
            await create_access_token(token_request=CreateAccessTokenRequest(username="admin@example.com"), current_username="user@example.com", is_admin=False)

        assert exc_info.value.status_code == 403
        store.replace_user_token.assert_not_called()

    @pytest.mark.asyncio
    async def test_admin_can_rotate_another_users_token(self, store):
        result = await create_access_token(
            token_request=CreateAccessTokenRequest(username="user@example.com"), current_username="admin@example.com", is_admin=True
        )

        assert result.status_code == 200
        assert store.replace_user_token.call_args.args[0] == "user@example.com"
        assert store.replace_user_token.call_args.kwargs["created_by"] == "admin@example.com"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "expiration, detail",
        [
            ((datetime.now(timezone.utc) - timedelta(days=1)).isoformat(), "future"),
            ((datetime.now(timezone.utc) + timedelta(days=400)).isoformat(), "1 year"),
            ("invalid-date-format", "Invalid expiration"),
        ],
    )
    async def test_bad_expiration_is_400(self, store, expiration, detail):
        with pytest.raises(HTTPException) as exc_info:
            await create_access_token(token_request=CreateAccessTokenRequest(expiration=expiration), current_username="user@example.com", is_admin=False)

        assert exc_info.value.status_code == 400
        assert detail in exc_info.value.detail
        store.replace_user_token.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_user_is_404(self, store):
        with pytest.raises(HTTPException) as exc_info:
            await create_access_token(token_request=CreateAccessTokenRequest(username="ghost@example.com"), current_username="admin@example.com", is_admin=True)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_token_cap_is_409(self, store):
        from mlflow.exceptions import MlflowException
        from mlflow.protos.databricks_pb2 import INVALID_STATE

        store.replace_user_token.side_effect = MlflowException("already holds 20 unexpired tokens", INVALID_STATE)

        with pytest.raises(HTTPException) as exc_info:
            await create_access_token(token_request=None, current_username="user@example.com", is_admin=False)

        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_unexpected_store_error_is_a_generic_500(self, store):
        from mlflow.exceptions import MlflowException

        store.replace_user_token.side_effect = MlflowException("boom with internals")

        with pytest.raises(HTTPException) as exc_info:
            await create_access_token(token_request=None, current_username="user@example.com", is_admin=False)

        assert exc_info.value.status_code == 500
        assert "internals" not in exc_info.value.detail

    def test_basic_authenticated_caller_is_refused(self, authenticated_client):
        """A request authenticated with an access token must not mint another one."""
        response = authenticated_client.patch("/api/2.0/mlflow/users/access-token")

        assert response.status_code == 403
        assert "signed-in session" in response.json()["detail"]

    def test_basic_authenticated_admin_is_refused_too(self, admin_client):
        response = admin_client.patch("/api/2.0/mlflow/users/access-token", json={"username": "user@example.com"})

        assert response.status_code == 403


class TestGetUserInformationEndpoint:
    """Test the get user information endpoint functionality."""

    @pytest.mark.asyncio
    async def test_get_user_information_unit(self, mock_store):
        """Test get_user_information returns lightweight user data when called by admin."""

        mock_user = MagicMock()
        mock_user.id = 2
        mock_user.username = "user@example.com"
        mock_user.display_name = "Regular User"
        mock_user.is_admin = False
        mock_user.is_service_account = False
        mock_user.groups = []

        mock_store.get_user_profile.return_value = mock_user

        with patch("mlflow_oidc_auth.routers.users.store", mock_store):
            result = await get_user_information(username="user@example.com", admin_username="admin@example.com")

        assert result.username == "user@example.com"
        assert result.is_admin is False
        mock_store.get_user_profile.assert_called_once_with("user@example.com")

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

        user_request = CreateUserRequest(
            username="newuser@example.com",
            display_name="New User",
            is_admin=False,
            is_service_account=False,
        )

        result = await create_new_user(user_request=user_request, admin_username="admin@example.com")

        assert result.status_code == 201

        # Verify user creation was called with correct parameters
        mock_create_user.assert_called_once_with(
            username="newuser@example.com",
            display_name="New User",
            is_admin=False,
            is_service_account=False,
            written_by="manual",
        )

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.users.create_user")
    async def test_create_admin_user(self, mock_create_user, mock_store):
        """Test creating admin user."""
        mock_create_user.return_value = (True, "User created successfully")

        user_request = CreateUserRequest(
            username="admin2@example.com",
            display_name="Admin User 2",
            is_admin=True,
            is_service_account=False,
        )

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

        user_request = CreateUserRequest(
            username="service2@example.com",
            display_name="Service Account 2",
            is_admin=False,
            is_service_account=True,
        )

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

        user_request = CreateUserRequest(
            username="existing@example.com",
            display_name="Existing User",
            is_admin=False,
            is_service_account=False,
        )

        result = await create_new_user(user_request=user_request, admin_username="admin@example.com")

        assert result.status_code == 200  # Updated, not created

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.users.create_user")
    async def test_create_user_exception_handling(self, mock_create_user, mock_store):
        """Test create user exception handling."""
        mock_create_user.side_effect = Exception("Database error")

        user_request = CreateUserRequest(
            username="newuser@example.com",
            display_name="New User",
            is_admin=False,
            is_service_account=False,
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_new_user(user_request=user_request, admin_username="admin@example.com")

        assert exc_info.value.status_code == 500
        assert "Failed to create user" in str(exc_info.value.detail)

    def test_create_user_integration_admin(self, admin_client):
        """Test create user endpoint through FastAPI test client as admin."""
        user_data = {
            "username": "newuser@example.com",
            "display_name": "New User",
            "is_admin": False,
            "is_service_account": False,
        }

        response = admin_client.post("/api/2.0/mlflow/users", json=user_data)

        assert response.status_code in [200, 201]
        assert "message" in response.json()

    def test_create_user_integration_non_admin(self, authenticated_client):
        """Test create user endpoint as non-admin user."""
        user_data = {
            "username": "newuser@example.com",
            "display_name": "New User",
            "is_admin": False,
            "is_service_account": False,
        }

        response = authenticated_client.post("/api/2.0/mlflow/users", json=user_data)

        # Should fail due to insufficient permissions
        assert response.status_code == 403


class TestDeleteUserEndpoint:
    """Test the delete user endpoint functionality."""

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.users.store")
    async def test_delete_user_success(self, mock_store_patch):
        """Test successful user deletion."""
        mock_store_patch.get_user_detail.return_value = {"username": "user@example.com", "managed_by": "manual", "is_admin": False}
        mock_store_patch.delete_user.return_value = None

        result = await delete_user(username="user@example.com", admin_username="admin@example.com")

        assert result.status_code == 200

        # Verify user deletion was called
        # The delete runs with the orphan hand-over hook in the same transaction (#324).
        mock_store_patch.delete_user_with_hook.assert_called_once()
        assert mock_store_patch.delete_user_with_hook.call_args.args[0] == "user@example.com"
        assert callable(mock_store_patch.delete_user_with_hook.call_args.args[1])

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.users.store")
    async def test_delete_user_not_found(self, mock_store_patch):
        """Test deleting non-existent user."""
        mock_store_patch.get_user_detail.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await delete_user(username="nonexistent@example.com", admin_username="admin@example.com")

        assert exc_info.value.status_code == 404
        assert "User nonexistent@example.com not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    @patch("mlflow_oidc_auth.routers.users.store")
    async def test_delete_user_exception_handling(self, mock_store_patch):
        """Test delete user exception handling."""
        mock_store_patch.get_user_detail.return_value = {"username": "user@example.com", "managed_by": "manual", "is_admin": False}
        mock_store_patch.delete_user_with_hook.side_effect = Exception("Database error")

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
            (
                "POST",
                "/api/2.0/mlflow/users",
                {"username": "test", "display_name": "Test"},
            ),
            ("DELETE", "/api/2.0/mlflow/users", {"username": "test"}),
        ]

        for method, endpoint, data in admin_endpoints:
            if method == "POST":
                response = authenticated_client.post(endpoint, json=data)
            elif method == "DELETE":
                response = authenticated_client.delete(endpoint, json=data)

            # Should require admin privileges
            assert response.status_code == 403

    def test_endpoints_with_invalid_json(self, authenticated_client, admin_client):
        """Test endpoints with invalid JSON data.

        The user-creation and deletion APIs are admin-only, so a non-admin client may
        be short-circuited with a 403 before the request body is ever parsed.  FastAPI
        versions differ in whether validation or dependencies run first, so CI and local
        environments could see different status codes.  To make the test robust we
        exercise both admin and non-admin clients.
        """
        endpoints_with_body = [
            ("POST", "/api/2.0/mlflow/users"),
            ("DELETE", "/api/2.0/mlflow/users"),
        ]

        # Admins should always hit the JSON validation step and therefore receive 422
        for method, endpoint in endpoints_with_body:
            if method == "POST":
                response = admin_client.post(endpoint, data="invalid json")
            else:
                response = admin_client.delete(endpoint, data="invalid json")

            assert response.status_code == 422, "admin client should reach body validation even with invalid JSON"

        # Non-admin clients may be rejected with 403 before validation; both outcomes
        # are acceptable as long as they don't succeed.
        for method, endpoint in endpoints_with_body:
            if method == "POST":
                response = authenticated_client.post(endpoint, data="invalid json")
            else:
                response = authenticated_client.delete(endpoint, data="invalid json")

            assert response.status_code in (403, 422)

    def test_endpoints_response_content_type(self, authenticated_client, admin_client):
        """Test that endpoints return proper content type."""
        # Test list users
        response = authenticated_client.get("/api/2.0/mlflow/users")
        assert "application/json" in response.headers.get("content-type", "")

        # Test create access token
        response = authenticated_client.patch("/api/2.0/mlflow/users/access-token")
        assert "application/json" in response.headers.get("content-type", "")

        # Test create user (admin only)
        user_data = {
            "username": "test@example.com",
            "display_name": "Test User",
            "is_admin": False,
            "is_service_account": False,
        }
        response = admin_client.post("/api/2.0/mlflow/users", json=user_data)
        assert "application/json" in response.headers.get("content-type", "")
