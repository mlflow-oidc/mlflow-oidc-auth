from typing import Callable, List

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_STATE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlGatewaySecretRegexPermission
from mlflow_oidc_auth.entities import GatewaySecretRegexPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository.utils import get_user, validate_regex


class GatewaySecretPermissionRegexRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def _get_secret_regex_permission(self, session: Session, id: int, user_id: int) -> SqlGatewaySecretRegexPermission:
        try:
            return (
                session.query(SqlGatewaySecretRegexPermission)
                .filter(
                    SqlGatewaySecretRegexPermission.id == id,
                    SqlGatewaySecretRegexPermission.user_id == user_id,
                )
                .one()
            )
        except NoResultFound:
            raise MlflowException(f"Permission not found for user_id: {user_id} and id: {id}", RESOURCE_DOES_NOT_EXIST)
        except MultipleResultsFound:
            raise MlflowException(f"Multiple Permissions found for user_id: {user_id} and id: {id}", INVALID_STATE)

    def grant(self, regex: str, priority: int, permission: str, username: str) -> GatewaySecretRegexPermission:
        validate_regex(regex)
        _validate_permission(permission)
        with self._Session() as session:
            try:
                user = get_user(session, username)
                perm = SqlGatewaySecretRegexPermission(
                    regex=regex,
                    priority=priority,
                    user_id=user.id,
                    permission=permission,
                )
                session.add(perm)
                session.flush()
                return perm.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(
                    f"Gateway secret regex perm exists ({regex},{username}): {e}",
                    RESOURCE_ALREADY_EXISTS,
                )

    def get(self, id: int, username: str) -> GatewaySecretRegexPermission:
        with self._Session() as session:
            user = get_user(session, username)
            perm = self._get_secret_regex_permission(session, id, user.id)
            return perm.to_mlflow_entity()

    def list_regex_for_user(self, username: str) -> List[GatewaySecretRegexPermission]:
        with self._Session() as session:
            user = get_user(session, username)
            perms = (
                session.query(SqlGatewaySecretRegexPermission)
                .filter(
                    SqlGatewaySecretRegexPermission.user_id == user.id,
                )
                .order_by(SqlGatewaySecretRegexPermission.priority)
                .all()
            )
            return [p.to_mlflow_entity() for p in perms]

    def update(self, id: int, regex: str, priority: int, permission: str, username: str) -> GatewaySecretRegexPermission:
        validate_regex(regex)
        _validate_permission(permission)
        with self._Session() as session:
            user = get_user(session, username)
            perm = self._get_secret_regex_permission(session, id, user.id)
            perm.priority = priority
            perm.permission = permission
            session.commit()
            return perm.to_mlflow_entity()

    def revoke(self, id: int, username: str) -> None:
        with self._Session() as session:
            user = get_user(session, username)
            perm = self._get_secret_regex_permission(session, id, user.id)
            session.delete(perm)
            session.commit()
            return None
