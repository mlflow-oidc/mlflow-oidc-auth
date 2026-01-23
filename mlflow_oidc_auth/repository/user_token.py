from datetime import datetime, timezone
from typing import Callable, List, Optional

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from mlflow_oidc_auth.db.models import SqlUser, SqlUserToken
from mlflow_oidc_auth.entities import UserToken
from mlflow_oidc_auth.repository.utils import get_user


class UserTokenRepository:
    def __init__(self, session_maker: Callable[[], Session]):
        self._Session = session_maker

    def create(
        self,
        username: str,
        name: str,
        token: str,
        expires_at: datetime,
    ) -> UserToken:
        """Create a new token for a user.

        Args:
            username: The username of the token owner.
            name: A descriptive name for the token.
            token: The plaintext token (will be hashed before storage).
            expires_at: Required expiration datetime (max 1 year from now).

        Returns:
            The created UserToken entity.

        Raises:
            MlflowException: If a token with the same name already exists for this user.
        """
        token_hash = generate_password_hash(token)
        with self._Session() as session:
            user = get_user(session, username)
            try:
                sql_token = SqlUserToken(
                    user_id=user.id,
                    name=name,
                    token_hash=token_hash,
                    created_at=datetime.now(timezone.utc),
                    expires_at=expires_at,
                    last_used_at=None,
                )
                session.add(sql_token)
                session.flush()
                return sql_token.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(
                    f"Token with name '{name}' already exists for user '{username}'",
                    RESOURCE_ALREADY_EXISTS,
                ) from e

    def list_for_user(self, username: str) -> List[UserToken]:
        """List all tokens for a user.

        Args:
            username: The username to list tokens for.

        Returns:
            List of UserToken entities (without exposing token hashes).
        """
        with self._Session() as session:
            user = get_user(session, username)
            tokens = session.query(SqlUserToken).filter(SqlUserToken.user_id == user.id).all()
            return [t.to_mlflow_entity() for t in tokens]

    def get(self, token_id: int, username: str) -> UserToken:
        """Get a specific token by ID.

        Args:
            token_id: The token ID.
            username: The username (for authorization check).

        Returns:
            The UserToken entity.

        Raises:
            MlflowException: If the token doesn't exist or doesn't belong to the user.
        """
        with self._Session() as session:
            user = get_user(session, username)
            token = session.query(SqlUserToken).filter(SqlUserToken.id == token_id, SqlUserToken.user_id == user.id).one_or_none()
            if token is None:
                raise MlflowException(
                    f"Token with id={token_id} not found for user '{username}'",
                    RESOURCE_DOES_NOT_EXIST,
                )
            return token.to_mlflow_entity()

    def delete(self, token_id: int, username: str) -> None:
        """Delete a specific token.

        Args:
            token_id: The token ID to delete.
            username: The username (for authorization check).

        Raises:
            MlflowException: If the token doesn't exist or doesn't belong to the user.
        """
        with self._Session() as session:
            user = get_user(session, username)
            token = session.query(SqlUserToken).filter(SqlUserToken.id == token_id, SqlUserToken.user_id == user.id).one_or_none()
            if token is None:
                raise MlflowException(
                    f"Token with id={token_id} not found for user '{username}'",
                    RESOURCE_DOES_NOT_EXIST,
                )
            session.delete(token)
            session.flush()

    def delete_all_for_user(self, username: str) -> int:
        """Delete all tokens for a user.

        Args:
            username: The username whose tokens should be deleted.

        Returns:
            The number of tokens deleted.
        """
        with self._Session() as session:
            user = get_user(session, username)
            count = session.query(SqlUserToken).filter(SqlUserToken.user_id == user.id).delete(synchronize_session=False)
            session.flush()
            return count

    def authenticate(self, username: str, password: str) -> bool:
        """Authenticate a user using any of their tokens.

        Checks the provided password against all non-expired tokens for the user.

        Args:
            username: The username to authenticate.
            password: The plaintext token to verify.

        Returns:
            True if authentication succeeds, False otherwise.
        """
        with self._Session() as session:
            user = session.query(SqlUser).filter(SqlUser.username == username).one_or_none()
            if user is None:
                return False

            tokens = session.query(SqlUserToken).filter(SqlUserToken.user_id == user.id).all()
            now = datetime.now(timezone.utc)

            for token in tokens:
                # Skip expired tokens
                # NOTE: We check for None to support legacy tokens migrated from password_hash
                # that may not have had an expiration set. New tokens always require expiration.
                if token.expires_at is not None:
                    expires_at = token.expires_at
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)
                    if expires_at < now:
                        continue

                # Check password hash
                if check_password_hash(token.token_hash, password):
                    # Update last_used_at
                    token.last_used_at = now
                    session.flush()
                    return True

            return False

    def update_last_used(self, token_id: int) -> None:
        """Update the last_used_at timestamp for a token.

        Args:
            token_id: The token ID to update.
        """
        with self._Session() as session:
            token = session.query(SqlUserToken).filter(SqlUserToken.id == token_id).one_or_none()
            if token is not None:
                token.last_used_at = datetime.now(timezone.utc)
                session.flush()

    def get_user_id_from_token(self, username: str, password: str) -> Optional[int]:
        """Get the user ID if the token authenticates successfully.

        This is useful for getting user context after token authentication.

        Args:
            username: The username to authenticate.
            password: The plaintext token to verify.

        Returns:
            The user ID if authentication succeeds, None otherwise.
        """
        with self._Session() as session:
            user = session.query(SqlUser).filter(SqlUser.username == username).one_or_none()
            if user is None:
                return None

            tokens = session.query(SqlUserToken).filter(SqlUserToken.user_id == user.id).all()
            now = datetime.now(timezone.utc)

            for token in tokens:
                # Skip expired tokens
                # NOTE: We check for None to support legacy tokens migrated from password_hash
                # that may not have had an expiration set. New tokens always require expiration.
                if token.expires_at is not None:
                    expires_at = token.expires_at
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)
                    if expires_at < now:
                        continue

                # Check password hash
                if check_password_hash(token.token_hash, password):
                    # Update last_used_at
                    token.last_used_at = now
                    session.flush()
                    return user.id

            return None
