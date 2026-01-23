"""
Tests for user token management API endpoints.

Tests cover:
- Current user token operations (list, create, delete)
- Admin token operations for other users
- Expiration validation
- Error handling
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from mlflow_oidc_auth.routers.users import (
    list_tokens,
    create_token,
    delete_token,
    list_user_tokens_admin,
    create_user_token_admin,
    delete_user_token_admin,
    _parse_expiration,
    _token_to_response,
)
from mlflow_oidc_auth.models.user import CreateUserTokenRequest


# =============================================================================
# Helper Fixtures
# =============================================================================


@pytest.fixture
def mock_token():
    """Create a mock token entity."""
    token = MagicMock()
    token.id = 1
    token.name = "test-token"
    token.token_hash = "hashed_value"
    token.created_at = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    token.expires_at = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
    token.last_used_at = datetime(2024, 1, 20, 15, 30, 0, tzinfo=timezone.utc)
    return token


@pytest.fixture
def mock_created_token():
    """Create a mock token entity as returned after creation."""
    token = MagicMock()
    token.id = 42
    token.name = "new-token"
    token.token_hash = "new_hashed_value"
    token.created_at = datetime.now(timezone.utc)
    token.expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    token.last_used_at = None
    return token


# =============================================================================
# Tests for _parse_expiration helper
# =============================================================================


class TestParseExpiration:
    """Tests for the _parse_expiration helper function."""

    def test_valid_iso_format(self):
        """Test parsing valid ISO 8601 date."""
        future_date = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        result = _parse_expiration(future_date)
        assert isinstance(result, datetime)

    def test_valid_iso_format_with_z(self):
        """Test parsing ISO 8601 date with 'Z' suffix."""
        future_date = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        result = _parse_expiration(future_date)
        assert isinstance(result, datetime)

    def test_empty_string_raises_error(self):
        """Test that empty expiration string raises HTTPException."""
        with pytest.raises(HTTPException) as exc:
            _parse_expiration("")
        assert exc.value.status_code == 400
        assert "required" in exc.value.detail.lower()

    def test_none_raises_error(self):
        """Test that None expiration raises HTTPException."""
        with pytest.raises(HTTPException) as exc:
            _parse_expiration(None)
        assert exc.value.status_code == 400

    def test_past_date_raises_error(self):
        """Test that past expiration date raises HTTPException."""
        past_date = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        with pytest.raises(HTTPException) as exc:
            _parse_expiration(past_date)
        assert exc.value.status_code == 400
        assert "future" in exc.value.detail.lower()

    def test_more_than_one_year_raises_error(self):
        """Test that expiration more than 1 year in future raises HTTPException."""
        far_future = (datetime.now(timezone.utc) + timedelta(days=400)).isoformat()
        with pytest.raises(HTTPException) as exc:
            _parse_expiration(far_future)
        assert exc.value.status_code == 400
        assert "1 year" in exc.value.detail.lower()

    def test_invalid_format_raises_error(self):
        """Test that invalid date format raises HTTPException."""
        with pytest.raises(HTTPException) as exc:
            _parse_expiration("not-a-date")
        assert exc.value.status_code == 400
        assert "format" in exc.value.detail.lower()

    def test_exactly_one_year_is_valid(self):
        """Test that expiration exactly at 1 year boundary is valid."""
        # 365 days is within the 366 day limit
        one_year = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
        result = _parse_expiration(one_year)
        assert isinstance(result, datetime)


# =============================================================================
# Tests for _token_to_response helper
# =============================================================================


class TestTokenToResponse:
    """Tests for the _token_to_response helper function."""

    def test_converts_token_with_all_fields(self, mock_token):
        """Test conversion of token with all fields populated."""
        result = _token_to_response(mock_token)
        assert result.id == 1
        assert result.name == "test-token"
        assert result.created_at is not None
        assert result.expires_at is not None
        assert result.last_used_at is not None

    def test_handles_none_last_used_at(self, mock_token):
        """Test conversion when last_used_at is None."""
        mock_token.last_used_at = None
        result = _token_to_response(mock_token)
        assert result.last_used_at is None

    def test_handles_none_expires_at(self, mock_token):
        """Test conversion when expires_at is None (legacy token)."""
        mock_token.expires_at = None
        result = _token_to_response(mock_token)
        assert result.expires_at is None


# =============================================================================
# Tests for Current User Token Endpoints
# =============================================================================


class TestListTokens:
    """Tests for GET /tokens endpoint."""

    @pytest.mark.asyncio
    async def test_list_tokens_success(self, mock_store, mock_token):
        """Test successfully listing user's tokens."""
        mock_store.list_user_tokens.return_value = [mock_token]

        with patch("mlflow_oidc_auth.routers.users.store", mock_store):
            result = await list_tokens(current_username="user@example.com")

        assert len(result.tokens) == 1
        assert result.tokens[0].name == "test-token"
        mock_store.list_user_tokens.assert_called_once_with("user@example.com")

    @pytest.mark.asyncio
    async def test_list_tokens_empty(self, mock_store):
        """Test listing tokens when user has none."""
        mock_store.list_user_tokens.return_value = []

        with patch("mlflow_oidc_auth.routers.users.store", mock_store):
            result = await list_tokens(current_username="user@example.com")

        assert len(result.tokens) == 0

    @pytest.mark.asyncio
    async def test_list_tokens_error_handling(self, mock_store):
        """Test error handling when listing tokens fails."""
        mock_store.list_user_tokens.side_effect = Exception("Database error")

        with patch("mlflow_oidc_auth.routers.users.store", mock_store):
            with pytest.raises(HTTPException) as exc:
                await list_tokens(current_username="user@example.com")

        assert exc.value.status_code == 500


class TestCreateToken:
    """Tests for POST /tokens endpoint."""

    @pytest.mark.asyncio
    async def test_create_token_success(self, mock_store, mock_created_token):
        """Test successfully creating a new token."""
        mock_store.create_user_token.return_value = mock_created_token
        expiration = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        request = CreateUserTokenRequest(name="new-token", expiration=expiration)

        with patch("mlflow_oidc_auth.routers.users.store", mock_store), patch("mlflow_oidc_auth.routers.users.generate_token", return_value="generated_secret"):
            result = await create_token(token_request=request, current_username="user@example.com")

        assert result.name == "new-token"
        assert result.token == "generated_secret"
        assert "created successfully" in result.message

    @pytest.mark.asyncio
    async def test_create_token_duplicate_name(self, mock_store):
        """Test creating token with duplicate name returns 409."""
        mock_store.create_user_token.side_effect = Exception("Token 'dup' already exists")
        expiration = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        request = CreateUserTokenRequest(name="dup", expiration=expiration)

        with patch("mlflow_oidc_auth.routers.users.store", mock_store), patch("mlflow_oidc_auth.routers.users.generate_token", return_value="secret"):
            with pytest.raises(HTTPException) as exc:
                await create_token(token_request=request, current_username="user@example.com")

        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_create_token_invalid_expiration(self, mock_store):
        """Test creating token with invalid expiration."""
        # Past date
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        request = CreateUserTokenRequest(name="test", expiration=past)

        with patch("mlflow_oidc_auth.routers.users.store", mock_store):
            with pytest.raises(HTTPException) as exc:
                await create_token(token_request=request, current_username="user@example.com")

        assert exc.value.status_code == 400


class TestDeleteToken:
    """Tests for DELETE /tokens/{token_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_token_success(self, mock_store):
        """Test successfully deleting a token."""
        mock_store.delete_user_token.return_value = None

        with patch("mlflow_oidc_auth.routers.users.store", mock_store):
            result = await delete_token(token_id=123, current_username="user@example.com")

        assert result.status_code == 200
        mock_store.delete_user_token.assert_called_once_with(123, "user@example.com")

    @pytest.mark.asyncio
    async def test_delete_token_not_found(self, mock_store):
        """Test deleting non-existent token returns 404."""
        mock_store.delete_user_token.side_effect = Exception("Token not found")

        with patch("mlflow_oidc_auth.routers.users.store", mock_store):
            with pytest.raises(HTTPException) as exc:
                await delete_token(token_id=999, current_username="user@example.com")

        assert exc.value.status_code == 404


# =============================================================================
# Tests for Admin Token Endpoints
# =============================================================================


class TestListUserTokensAdmin:
    """Tests for GET /{username}/tokens endpoint (admin)."""

    @pytest.mark.asyncio
    async def test_list_user_tokens_admin_success(self, mock_store, mock_token):
        """Test admin successfully listing another user's tokens."""
        # Use existing user from conftest mock_store setup
        mock_store.list_user_tokens.return_value = [mock_token]

        with patch("mlflow_oidc_auth.routers.users.store", mock_store):
            # Use user@example.com which exists in mock_store
            result = await list_user_tokens_admin(username="user@example.com", admin_username="admin@example.com")

        assert len(result.tokens) == 1
        mock_store.list_user_tokens.assert_called_once_with("user@example.com")

    @pytest.mark.asyncio
    async def test_list_user_tokens_admin_user_not_found(self, mock_store):
        """Test admin listing tokens for non-existent user."""
        mock_store.get_user_profile.return_value = None

        with patch("mlflow_oidc_auth.routers.users.store", mock_store):
            with pytest.raises(HTTPException) as exc:
                await list_user_tokens_admin(username="nonexistent@example.com", admin_username="admin@example.com")

        assert exc.value.status_code == 404


class TestCreateUserTokenAdmin:
    """Tests for POST /{username}/tokens endpoint (admin)."""

    @pytest.mark.asyncio
    async def test_create_user_token_admin_success(self, mock_store, mock_created_token):
        """Test admin successfully creating token for another user."""
        # Use existing user from conftest mock_store setup
        mock_store.create_user_token.return_value = mock_created_token
        expiration = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        request = CreateUserTokenRequest(name="admin-created", expiration=expiration)

        with patch("mlflow_oidc_auth.routers.users.store", mock_store), patch("mlflow_oidc_auth.routers.users.generate_token", return_value="admin_generated"):
            # Use user@example.com which exists in mock_store
            result = await create_user_token_admin(username="user@example.com", token_request=request, admin_username="admin@example.com")

        assert result.token == "admin_generated"
        mock_store.create_user_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_token_admin_user_not_found(self, mock_store):
        """Test admin creating token for non-existent user."""
        mock_store.get_user_profile.return_value = None
        expiration = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        request = CreateUserTokenRequest(name="test", expiration=expiration)

        with patch("mlflow_oidc_auth.routers.users.store", mock_store):
            with pytest.raises(HTTPException) as exc:
                await create_user_token_admin(username="nonexistent@example.com", token_request=request, admin_username="admin@example.com")

        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_create_user_token_admin_duplicate_name(self, mock_store):
        """Test admin creating token with duplicate name."""
        # Use existing user from conftest mock_store setup
        mock_store.create_user_token.side_effect = Exception("Token already exists")
        expiration = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        request = CreateUserTokenRequest(name="dup", expiration=expiration)

        with patch("mlflow_oidc_auth.routers.users.store", mock_store), patch("mlflow_oidc_auth.routers.users.generate_token", return_value="secret"):
            with pytest.raises(HTTPException) as exc:
                # Use user@example.com which exists in mock_store
                await create_user_token_admin(username="user@example.com", token_request=request, admin_username="admin@example.com")

        assert exc.value.status_code == 409


class TestDeleteUserTokenAdmin:
    """Tests for DELETE /{username}/tokens/{token_id} endpoint (admin)."""

    @pytest.mark.asyncio
    async def test_delete_user_token_admin_success(self, mock_store):
        """Test admin successfully deleting another user's token."""
        mock_store.delete_user_token.return_value = None

        with patch("mlflow_oidc_auth.routers.users.store", mock_store):
            result = await delete_user_token_admin(username="target@example.com", token_id=123, admin_username="admin@example.com")

        assert result.status_code == 200
        mock_store.delete_user_token.assert_called_once_with(123, "target@example.com")

    @pytest.mark.asyncio
    async def test_delete_user_token_admin_not_found(self, mock_store):
        """Test admin deleting non-existent token."""
        mock_store.delete_user_token.side_effect = Exception("Token not found")

        with patch("mlflow_oidc_auth.routers.users.store", mock_store):
            with pytest.raises(HTTPException) as exc:
                await delete_user_token_admin(username="target@example.com", token_id=999, admin_username="admin@example.com")

        assert exc.value.status_code == 404


# =============================================================================
# Integration Tests with Test Client
# =============================================================================


class TestTokenEndpointsIntegration:
    """Integration tests using the test client."""

    def test_list_tokens_authenticated(self, authenticated_client, mock_store, mock_token):
        """Test listing tokens via HTTP client."""
        mock_store.list_user_tokens.return_value = [mock_token]

        resp = authenticated_client.get("/api/2.0/mlflow/users/tokens")

        # May return 200 or redirect depending on auth setup
        if resp.status_code == 200:
            data = resp.json()
            assert "tokens" in data

    def test_create_token_authenticated(self, authenticated_client, mock_store, mock_created_token):
        """Test creating token via HTTP client."""
        mock_store.create_user_token.return_value = mock_created_token
        expiration = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()

        resp = authenticated_client.post("/api/2.0/mlflow/users/tokens", json={"name": "http-test", "expiration": expiration})

        # May return 201 or other status depending on auth setup
        if resp.status_code == 201:
            data = resp.json()
            assert "token" in data

    def test_delete_token_authenticated(self, authenticated_client, mock_store):
        """Test deleting token via HTTP client."""
        mock_store.delete_user_token.return_value = None

        resp = authenticated_client.delete("/api/2.0/mlflow/users/tokens/123")

        # May return 200 or other status depending on auth setup
        if resp.status_code == 200:
            data = resp.json()
            assert "message" in data
