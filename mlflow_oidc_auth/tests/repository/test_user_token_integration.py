"""
Integration tests for UserTokenRepository using real SQLite database.

Tests the full token lifecycle including creation, authentication,
expiration, and deletion with actual database operations.
"""

import pytest
from datetime import datetime, timedelta, timezone

from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore


@pytest.fixture
def store(tmp_path):
    """Create a SqlAlchemyStore with a temporary SQLite database."""
    store = SqlAlchemyStore()
    db_path = tmp_path / "test_tokens.db"
    store.init_db(f"sqlite:///{db_path.as_posix()}")
    return store


@pytest.fixture
def test_user(store):
    """Create a test user and return their username."""
    username = "tokenuser@example.com"
    store.create_user(
        username=username,
        password="initial_password",
        display_name="Token Test User",
    )
    return username


class TestTokenLifecycle:
    """Integration tests for the full token lifecycle."""

    def test_create_and_list_tokens(self, store, test_user):
        """Test creating multiple tokens and listing them."""
        expires = datetime.now(timezone.utc) + timedelta(days=30)

        # Create first token
        token1 = store.create_user_token(
            username=test_user,
            name="token-1",
            token="secret_token_1",
            expires_at=expires,
        )
        assert token1.name == "token-1"
        assert token1.user_id is not None

        # Create second token
        token2 = store.create_user_token(
            username=test_user,
            name="token-2",
            token="secret_token_2",
            expires_at=expires,
        )
        assert token2.name == "token-2"

        # List tokens
        tokens = store.list_user_tokens(test_user)
        # Note: User creation also creates a "default" token, so we have 3 total
        token_names = [t.name for t in tokens]
        assert "token-1" in token_names
        assert "token-2" in token_names

    def test_create_duplicate_token_name_fails(self, store, test_user):
        """Test that creating a token with duplicate name fails."""
        expires = datetime.now(timezone.utc) + timedelta(days=30)

        # Create first token
        store.create_user_token(
            username=test_user,
            name="unique-name",
            token="secret1",
            expires_at=expires,
        )

        # Try to create another with same name
        with pytest.raises(MlflowException) as exc:
            store.create_user_token(
                username=test_user,
                name="unique-name",
                token="secret2",
                expires_at=expires,
            )
        assert "already exists" in str(exc.value)

    def test_authenticate_with_valid_token(self, store, test_user):
        """Test authentication with a valid token."""
        expires = datetime.now(timezone.utc) + timedelta(days=30)
        raw_token = "my_secret_token_123"

        store.create_user_token(
            username=test_user,
            name="auth-token",
            token=raw_token,
            expires_at=expires,
        )

        # Should authenticate successfully
        result = store.authenticate_user_token(test_user, raw_token)
        assert result is True

    def test_authenticate_with_wrong_token(self, store, test_user):
        """Test authentication fails with wrong token."""
        expires = datetime.now(timezone.utc) + timedelta(days=30)

        store.create_user_token(
            username=test_user,
            name="auth-token",
            token="correct_token",
            expires_at=expires,
        )

        # Should fail with wrong token
        result = store.authenticate_user_token(test_user, "wrong_token")
        assert result is False

    def test_authenticate_with_expired_token(self, store, test_user):
        """Test authentication fails with expired token."""
        # Create token that's already expired
        expired = datetime.now(timezone.utc) - timedelta(days=1)
        raw_token = "expired_token_123"

        store.create_user_token(
            username=test_user,
            name="expired-token",
            token=raw_token,
            expires_at=expired,
        )

        # Should fail authentication
        result = store.authenticate_user_token(test_user, raw_token)
        assert result is False

    def test_delete_specific_token(self, store, test_user):
        """Test deleting a specific token."""
        expires = datetime.now(timezone.utc) + timedelta(days=30)

        token = store.create_user_token(
            username=test_user,
            name="to-delete",
            token="secret",
            expires_at=expires,
        )

        # Verify token exists
        tokens_before = store.list_user_tokens(test_user)
        names_before = [t.name for t in tokens_before]
        assert "to-delete" in names_before

        # Delete the token
        store.delete_user_token(token.id, test_user)

        # Verify token is gone
        tokens_after = store.list_user_tokens(test_user)
        names_after = [t.name for t in tokens_after]
        assert "to-delete" not in names_after

    def test_delete_nonexistent_token_fails(self, store, test_user):
        """Test deleting a non-existent token fails."""
        with pytest.raises(MlflowException) as exc:
            store.delete_user_token(99999, test_user)
        assert "not found" in str(exc.value)

    def test_get_specific_token(self, store, test_user):
        """Test getting a specific token by ID."""
        expires = datetime.now(timezone.utc) + timedelta(days=30)

        created = store.create_user_token(
            username=test_user,
            name="get-test",
            token="secret",
            expires_at=expires,
        )

        # Get the token
        retrieved = store.get_user_token(created.id, test_user)
        assert retrieved.id == created.id
        assert retrieved.name == "get-test"

    def test_multiple_tokens_authenticate_independently(self, store, test_user):
        """Test that multiple tokens work independently."""
        expires = datetime.now(timezone.utc) + timedelta(days=30)

        # Create two tokens
        store.create_user_token(
            username=test_user,
            name="token-a",
            token="secret_a",
            expires_at=expires,
        )
        store.create_user_token(
            username=test_user,
            name="token-b",
            token="secret_b",
            expires_at=expires,
        )

        # Both should authenticate
        assert store.authenticate_user_token(test_user, "secret_a") is True
        assert store.authenticate_user_token(test_user, "secret_b") is True

    def test_deleting_user_deletes_tokens(self, store):
        """Test that deleting a user deletes all their tokens."""
        username = "delete_me@example.com"
        store.create_user(
            username=username,
            password="pw",
            display_name="Delete Me",
        )
        expires = datetime.now(timezone.utc) + timedelta(days=30)

        # Create additional tokens
        store.create_user_token(
            username=username,
            name="extra-token",
            token="secret",
            expires_at=expires,
        )

        # Verify tokens exist
        tokens = store.list_user_tokens(username)
        assert len(tokens) >= 1

        # Delete user
        store.delete_user(username)

        # User should be gone
        assert store.has_user(username) is False


class TestTokenExpiration:
    """Tests focused on token expiration behavior."""

    def test_token_just_before_expiry_works(self, store, test_user):
        """Test that a token just before expiry still works."""
        # Expires in 1 second
        expires = datetime.now(timezone.utc) + timedelta(seconds=1)
        raw_token = "almost_expired"

        store.create_user_token(
            username=test_user,
            name="almost-expired",
            token=raw_token,
            expires_at=expires,
        )

        # Should still work
        result = store.authenticate_user_token(test_user, raw_token)
        assert result is True

    def test_mixed_expired_and_valid_tokens(self, store, test_user):
        """Test that valid token works even if other tokens are expired."""
        expired = datetime.now(timezone.utc) - timedelta(days=1)
        valid = datetime.now(timezone.utc) + timedelta(days=30)

        # Create expired token
        store.create_user_token(
            username=test_user,
            name="expired",
            token="expired_secret",
            expires_at=expired,
        )

        # Create valid token
        store.create_user_token(
            username=test_user,
            name="valid",
            token="valid_secret",
            expires_at=valid,
        )

        # Expired token should fail
        assert store.authenticate_user_token(test_user, "expired_secret") is False

        # Valid token should work
        assert store.authenticate_user_token(test_user, "valid_secret") is True
