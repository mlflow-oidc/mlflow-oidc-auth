"""
Unit tests for UserTokenRepository.

Tests cover token creation, listing, deletion, authentication,
and expiration validation.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from mlflow.exceptions import MlflowException
from sqlalchemy.exc import IntegrityError

from mlflow_oidc_auth.repository.user_token import UserTokenRepository


@pytest.fixture
def session():
    """Create a mock SQLAlchemy session."""
    s = MagicMock()
    s.__enter__.return_value = s
    s.__exit__.return_value = None
    return s


@pytest.fixture
def session_maker(session):
    """Create a mock session maker."""
    return MagicMock(return_value=session)


@pytest.fixture
def repo(session_maker):
    """Create a UserTokenRepository with mock session maker."""
    return UserTokenRepository(session_maker)


class TestCreateToken:
    """Tests for UserTokenRepository.create()"""

    def test_create_success(self, repo, session):
        """Test successful token creation."""
        mock_user = MagicMock()
        mock_user.id = 1

        mock_token = MagicMock()
        mock_token.to_mlflow_entity.return_value = "token_entity"

        expires_at = datetime.now(timezone.utc) + timedelta(days=30)

        with (
            patch("mlflow_oidc_auth.repository.user_token.get_user", return_value=mock_user),
            patch("mlflow_oidc_auth.repository.user_token.generate_password_hash", return_value="hashed_token"),
            patch("mlflow_oidc_auth.repository.user_token.SqlUserToken", return_value=mock_token),
        ):
            result = repo.create("testuser", "my-token", "raw_token_value", expires_at)

            assert result == "token_entity"
            session.add.assert_called_once_with(mock_token)
            session.flush.assert_called_once()

    def test_create_duplicate_name_raises_error(self, repo, session):
        """Test that creating a token with duplicate name raises MlflowException."""
        mock_user = MagicMock()
        mock_user.id = 1

        session.flush.side_effect = IntegrityError("statement", "params", "orig")
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)

        with (
            patch("mlflow_oidc_auth.repository.user_token.get_user", return_value=mock_user),
            patch("mlflow_oidc_auth.repository.user_token.generate_password_hash", return_value="hashed"),
            patch("mlflow_oidc_auth.repository.user_token.SqlUserToken", return_value=MagicMock()),
        ):
            with pytest.raises(MlflowException) as exc:
                repo.create("testuser", "duplicate-name", "token", expires_at)

            assert "already exists" in str(exc.value)
            assert exc.value.error_code == "RESOURCE_ALREADY_EXISTS"


class TestListForUser:
    """Tests for UserTokenRepository.list_for_user()"""

    def test_list_for_user_returns_tokens(self, repo, session):
        """Test listing all tokens for a user."""
        mock_user = MagicMock()
        mock_user.id = 1

        mock_token1 = MagicMock()
        mock_token1.to_mlflow_entity.return_value = "token1"
        mock_token2 = MagicMock()
        mock_token2.to_mlflow_entity.return_value = "token2"

        session.query().filter().all.return_value = [mock_token1, mock_token2]

        with patch("mlflow_oidc_auth.repository.user_token.get_user", return_value=mock_user):
            result = repo.list_for_user("testuser")

            assert result == ["token1", "token2"]

    def test_list_for_user_empty(self, repo, session):
        """Test listing tokens when user has none."""
        mock_user = MagicMock()
        mock_user.id = 1

        session.query().filter().all.return_value = []

        with patch("mlflow_oidc_auth.repository.user_token.get_user", return_value=mock_user):
            result = repo.list_for_user("testuser")

            assert result == []


class TestGetToken:
    """Tests for UserTokenRepository.get()"""

    def test_get_token_found(self, repo, session):
        """Test getting a specific token by ID."""
        mock_user = MagicMock()
        mock_user.id = 1

        mock_token = MagicMock()
        mock_token.to_mlflow_entity.return_value = "token_entity"

        session.query().filter().one_or_none.return_value = mock_token

        with patch("mlflow_oidc_auth.repository.user_token.get_user", return_value=mock_user):
            result = repo.get(token_id=123, username="testuser")

            assert result == "token_entity"

    def test_get_token_not_found(self, repo, session):
        """Test getting a non-existent token raises MlflowException."""
        mock_user = MagicMock()
        mock_user.id = 1

        session.query().filter().one_or_none.return_value = None

        with patch("mlflow_oidc_auth.repository.user_token.get_user", return_value=mock_user):
            with pytest.raises(MlflowException) as exc:
                repo.get(token_id=999, username="testuser")

            assert "not found" in str(exc.value)
            assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"


class TestDeleteToken:
    """Tests for UserTokenRepository.delete()"""

    def test_delete_token_success(self, repo, session):
        """Test successful token deletion."""
        mock_user = MagicMock()
        mock_user.id = 1

        mock_token = MagicMock()
        session.query().filter().one_or_none.return_value = mock_token

        with patch("mlflow_oidc_auth.repository.user_token.get_user", return_value=mock_user):
            repo.delete(token_id=123, username="testuser")

            session.delete.assert_called_once_with(mock_token)
            session.flush.assert_called_once()

    def test_delete_token_not_found(self, repo, session):
        """Test deleting non-existent token raises MlflowException."""
        mock_user = MagicMock()
        mock_user.id = 1

        session.query().filter().one_or_none.return_value = None

        with patch("mlflow_oidc_auth.repository.user_token.get_user", return_value=mock_user):
            with pytest.raises(MlflowException) as exc:
                repo.delete(token_id=999, username="testuser")

            assert "not found" in str(exc.value)
            session.delete.assert_not_called()


class TestDeleteAllForUser:
    """Tests for UserTokenRepository.delete_all_for_user()"""

    def test_delete_all_for_user(self, repo, session):
        """Test deleting all tokens for a user."""
        mock_user = MagicMock()
        mock_user.id = 1

        session.query().filter().delete.return_value = 3

        with patch("mlflow_oidc_auth.repository.user_token.get_user", return_value=mock_user):
            count = repo.delete_all_for_user("testuser")

            assert count == 3
            session.flush.assert_called_once()


class TestAuthenticate:
    """Tests for UserTokenRepository.authenticate()"""

    def test_authenticate_success(self, repo, session):
        """Test successful authentication with valid token."""
        mock_user = MagicMock()
        mock_user.id = 1

        mock_token = MagicMock()
        mock_token.token_hash = "hashed_password"
        mock_token.expires_at = datetime.now(timezone.utc) + timedelta(days=30)

        session.query().filter().one_or_none.return_value = mock_user
        session.query().filter().all.return_value = [mock_token]

        with patch("mlflow_oidc_auth.repository.user_token.check_password_hash", return_value=True):
            result = repo.authenticate("testuser", "raw_token")

            assert result is True
            session.flush.assert_called_once()  # last_used_at updated

    def test_authenticate_user_not_found(self, repo, session):
        """Test authentication fails when user doesn't exist."""
        session.query().filter().one_or_none.return_value = None

        result = repo.authenticate("nonexistent", "token")

        assert result is False

    def test_authenticate_wrong_password(self, repo, session):
        """Test authentication fails with wrong password."""
        mock_user = MagicMock()
        mock_user.id = 1

        mock_token = MagicMock()
        mock_token.token_hash = "hashed_password"
        mock_token.expires_at = datetime.now(timezone.utc) + timedelta(days=30)

        session.query().filter().one_or_none.return_value = mock_user
        session.query().filter().all.return_value = [mock_token]

        with patch("mlflow_oidc_auth.repository.user_token.check_password_hash", return_value=False):
            result = repo.authenticate("testuser", "wrong_token")

            assert result is False

    def test_authenticate_expired_token(self, repo, session):
        """Test authentication fails with expired token."""
        mock_user = MagicMock()
        mock_user.id = 1

        mock_token = MagicMock()
        mock_token.token_hash = "hashed_password"
        # Token expired yesterday
        mock_token.expires_at = datetime.now(timezone.utc) - timedelta(days=1)

        session.query().filter().one_or_none.return_value = mock_user
        session.query().filter().all.return_value = [mock_token]

        # Even with correct password hash, should fail due to expiration
        with patch("mlflow_oidc_auth.repository.user_token.check_password_hash", return_value=True):
            result = repo.authenticate("testuser", "token")

            assert result is False

    def test_authenticate_no_tokens(self, repo, session):
        """Test authentication fails when user has no tokens."""
        mock_user = MagicMock()
        mock_user.id = 1

        session.query().filter().one_or_none.return_value = mock_user
        session.query().filter().all.return_value = []

        result = repo.authenticate("testuser", "token")

        assert result is False

    def test_authenticate_legacy_token_no_expiration(self, repo, session):
        """Test authentication succeeds for legacy tokens without expiration."""
        mock_user = MagicMock()
        mock_user.id = 1

        mock_token = MagicMock()
        mock_token.token_hash = "hashed_password"
        mock_token.expires_at = None  # Legacy token without expiration

        session.query().filter().one_or_none.return_value = mock_user
        session.query().filter().all.return_value = [mock_token]

        with patch("mlflow_oidc_auth.repository.user_token.check_password_hash", return_value=True):
            result = repo.authenticate("testuser", "token")

            assert result is True

    def test_authenticate_naive_datetime_handling(self, repo, session):
        """Test that naive datetime in expires_at is treated as UTC."""
        mock_user = MagicMock()
        mock_user.id = 1

        mock_token = MagicMock()
        mock_token.token_hash = "hashed_password"
        # Naive datetime (no timezone info) - should be treated as UTC
        # Use datetime.now() without timezone to create a naive datetime
        naive_future = datetime(2099, 1, 1, 12, 0, 0)  # Far future, no tzinfo
        mock_token.expires_at = naive_future

        session.query().filter().one_or_none.return_value = mock_user
        session.query().filter().all.return_value = [mock_token]

        with patch("mlflow_oidc_auth.repository.user_token.check_password_hash", return_value=True):
            result = repo.authenticate("testuser", "token")

            assert result is True

    def test_authenticate_multiple_tokens_first_valid(self, repo, session):
        """Test authentication succeeds when first token is valid."""
        mock_user = MagicMock()
        mock_user.id = 1

        mock_token1 = MagicMock()
        mock_token1.token_hash = "hash1"
        mock_token1.expires_at = datetime.now(timezone.utc) + timedelta(days=30)

        mock_token2 = MagicMock()
        mock_token2.token_hash = "hash2"
        mock_token2.expires_at = datetime.now(timezone.utc) + timedelta(days=30)

        session.query().filter().one_or_none.return_value = mock_user
        session.query().filter().all.return_value = [mock_token1, mock_token2]

        # First token matches
        with patch("mlflow_oidc_auth.repository.user_token.check_password_hash", side_effect=[True, False]):
            result = repo.authenticate("testuser", "token")

            assert result is True

    def test_authenticate_multiple_tokens_second_valid(self, repo, session):
        """Test authentication succeeds when second token is valid."""
        mock_user = MagicMock()
        mock_user.id = 1

        mock_token1 = MagicMock()
        mock_token1.token_hash = "hash1"
        mock_token1.expires_at = datetime.now(timezone.utc) + timedelta(days=30)

        mock_token2 = MagicMock()
        mock_token2.token_hash = "hash2"
        mock_token2.expires_at = datetime.now(timezone.utc) + timedelta(days=30)

        session.query().filter().one_or_none.return_value = mock_user
        session.query().filter().all.return_value = [mock_token1, mock_token2]

        # Second token matches
        with patch("mlflow_oidc_auth.repository.user_token.check_password_hash", side_effect=[False, True]):
            result = repo.authenticate("testuser", "token")

            assert result is True


class TestUpdateLastUsed:
    """Tests for UserTokenRepository.update_last_used()"""

    def test_update_last_used_success(self, repo, session):
        """Test updating last_used_at timestamp."""
        mock_token = MagicMock()
        session.query().filter().one_or_none.return_value = mock_token

        repo.update_last_used(token_id=123)

        assert mock_token.last_used_at is not None
        session.flush.assert_called_once()

    def test_update_last_used_token_not_found(self, repo, session):
        """Test update_last_used does nothing when token not found."""
        session.query().filter().one_or_none.return_value = None

        # Should not raise, just silently do nothing
        repo.update_last_used(token_id=999)

        session.flush.assert_not_called()


class TestGetUserIdFromToken:
    """Tests for UserTokenRepository.get_user_id_from_token()"""

    def test_get_user_id_success(self, repo, session):
        """Test getting user ID from valid token."""
        mock_user = MagicMock()
        mock_user.id = 42

        mock_token = MagicMock()
        mock_token.token_hash = "hashed"
        mock_token.expires_at = datetime.now(timezone.utc) + timedelta(days=30)

        session.query().filter().one_or_none.return_value = mock_user
        session.query().filter().all.return_value = [mock_token]

        with patch("mlflow_oidc_auth.repository.user_token.check_password_hash", return_value=True):
            result = repo.get_user_id_from_token("testuser", "token")

            assert result == 42

    def test_get_user_id_user_not_found(self, repo, session):
        """Test get_user_id_from_token returns None when user not found."""
        session.query().filter().one_or_none.return_value = None

        result = repo.get_user_id_from_token("nonexistent", "token")

        assert result is None

    def test_get_user_id_invalid_token(self, repo, session):
        """Test get_user_id_from_token returns None for invalid token."""
        mock_user = MagicMock()
        mock_user.id = 42

        mock_token = MagicMock()
        mock_token.token_hash = "hashed"
        mock_token.expires_at = datetime.now(timezone.utc) + timedelta(days=30)

        session.query().filter().one_or_none.return_value = mock_user
        session.query().filter().all.return_value = [mock_token]

        with patch("mlflow_oidc_auth.repository.user_token.check_password_hash", return_value=False):
            result = repo.get_user_id_from_token("testuser", "wrong_token")

            assert result is None

    def test_get_user_id_expired_token(self, repo, session):
        """Test get_user_id_from_token returns None for expired token."""
        mock_user = MagicMock()
        mock_user.id = 42

        mock_token = MagicMock()
        mock_token.token_hash = "hashed"
        mock_token.expires_at = datetime.now(timezone.utc) - timedelta(days=1)

        session.query().filter().one_or_none.return_value = mock_user
        session.query().filter().all.return_value = [mock_token]

        with patch("mlflow_oidc_auth.repository.user_token.check_password_hash", return_value=True):
            result = repo.get_user_id_from_token("testuser", "token")

            assert result is None
