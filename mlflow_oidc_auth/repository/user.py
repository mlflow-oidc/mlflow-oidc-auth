from datetime import datetime, timezone
from typing import Callable, List, Optional

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST
from mlflow.utils.validation import _validate_username
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from mlflow_oidc_auth.db.models import SqlUser
from mlflow_oidc_auth.entities import User
from mlflow_oidc_auth.repository.utils import get_user


class UserRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def create(self, username: str, password: str, display_name: str, is_admin: bool = False, is_service_account: bool = False) -> User:
        _validate_username(username)
        pwhash = generate_password_hash(password)
        with self._Session() as session:
            try:
                u = SqlUser(
                    username=username,
                    password_hash=pwhash,
                    display_name=display_name,
                    is_admin=is_admin,
                    is_service_account=is_service_account,
                )
                session.add(u)
                session.flush()
                return u.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(f"User '{username}' already exists: {e}", RESOURCE_ALREADY_EXISTS) from e

    def get(self, username: str) -> User:
        with self._Session() as session:
            u = session.query(SqlUser).filter(SqlUser.username == username).one_or_none()
            if u is None:
                raise MlflowException(f"User '{username}' not found", RESOURCE_DOES_NOT_EXIST)
            return u.to_mlflow_entity()

    def exist(self, username: str) -> bool:
        with self._Session() as session:
            return session.query(SqlUser).filter(SqlUser.username == username).first() is not None

    def list(self, is_service_account: bool = False, all: bool = False) -> List[User]:
        with self._Session() as session:
            q = session.query(SqlUser)
            if not all:
                q = q.filter(SqlUser.is_service_account == is_service_account)
            return [u.to_mlflow_entity() for u in q.all()]

    def update(
        self,
        username: str,
        password: Optional[str] = None,
        password_expiration: Optional[datetime] = None,
        is_admin: Optional[bool] = False,
        is_service_account: Optional[bool] = False,
    ) -> User:
        from werkzeug.security import generate_password_hash

        with self._Session() as session:
            user = get_user(session, username)
            if password is not None:
                user.password_hash = generate_password_hash(password)
            if password_expiration is not None:
                user.password_expiration = password_expiration
            if is_admin is not None:
                user.is_admin = is_admin
            if is_service_account is not None:
                user.is_service_account = is_service_account
            session.flush()
            return user.to_mlflow_entity()

    def delete(self, username: str) -> None:
        with self._Session() as session:
            user = get_user(session, username)
            if user is None:
                raise MlflowException(f"User '{username}' not found.")

            # Delete dependent rows first.
            # Without this, SQLAlchemy may try to NULL-out non-nullable FKs
            # (e.g. experiment_permissions.user_id), causing IntegrityError.
            from mlflow_oidc_auth.db.models import (
                SqlExperimentPermission,
                SqlExperimentRegexPermission,
                SqlRegisteredModelPermission,
                SqlRegisteredModelRegexPermission,
                SqlScorerPermission,
                SqlScorerRegexPermission,
                SqlUserGroup,
            )

            user_id = user.id
            session.query(SqlExperimentPermission).filter(SqlExperimentPermission.user_id == user_id).delete(synchronize_session=False)
            session.query(SqlExperimentRegexPermission).filter(SqlExperimentRegexPermission.user_id == user_id).delete(synchronize_session=False)
            session.query(SqlRegisteredModelPermission).filter(SqlRegisteredModelPermission.user_id == user_id).delete(synchronize_session=False)
            session.query(SqlRegisteredModelRegexPermission).filter(SqlRegisteredModelRegexPermission.user_id == user_id).delete(
                synchronize_session=False
            )
            session.query(SqlScorerPermission).filter(SqlScorerPermission.user_id == user_id).delete(synchronize_session=False)
            session.query(SqlScorerRegexPermission).filter(SqlScorerRegexPermission.user_id == user_id).delete(synchronize_session=False)
            session.query(SqlUserGroup).filter(SqlUserGroup.user_id == user_id).delete(synchronize_session=False)

            session.delete(user)
            session.flush()

    def authenticate(self, username: str, password: str) -> bool:
        with self._Session() as session:
            try:
                user = get_user(session, username)
                if user.password_expiration is not None:
                    if user.password_expiration.tzinfo is None:
                        user.password_expiration = user.password_expiration.replace(tzinfo=timezone.utc)
                    if user.password_expiration < datetime.now(timezone.utc):
                        return False
                return check_password_hash(getattr(user, "password_hash"), password)
            except MlflowException:
                return False
