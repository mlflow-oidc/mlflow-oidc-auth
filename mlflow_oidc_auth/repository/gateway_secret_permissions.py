from typing import Callable, List

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_STATE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlGatewaySecretPermission, SqlUser
from mlflow_oidc_auth.entities import GatewaySecretPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository.utils import get_user


class GatewaySecretPermissionRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def _get_permission(self, session: Session, secret_id: str, username: str) -> SqlGatewaySecretPermission:
        try:
            return (
                session.query(SqlGatewaySecretPermission)
                .join(SqlUser, SqlGatewaySecretPermission.user_id == SqlUser.id)
                .filter(
                    SqlGatewaySecretPermission.secret_id == secret_id,
                    SqlUser.username == username,
                )
                .one()
            )
        except NoResultFound as e:
            raise MlflowException(
                f"No gateway secret permission for secret={secret_id}, user={username}",
                RESOURCE_DOES_NOT_EXIST,
            ) from e
        except MultipleResultsFound as e:
            raise MlflowException(
                f"Multiple gateway secret perms for secret={secret_id}, user={username}",
                INVALID_STATE,
            ) from e

    def grant_permission(self, secret_id: str, username: str, permission: str) -> GatewaySecretPermission:
        _validate_permission(permission)
        with self._Session() as session:
            try:
                user = get_user(session, username)
                perm = SqlGatewaySecretPermission(
                    secret_id=secret_id,
                    user_id=user.id,
                    permission=permission,
                )
                session.add(perm)
                session.flush()
                return perm.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(
                    f"Gateway secret permission already exists ({secret_id}, {username}): {e}",
                    RESOURCE_ALREADY_EXISTS,
                ) from e

    def get_permission(self, secret_id: str, username: str) -> GatewaySecretPermission:
        with self._Session() as session:
            perm = self._get_permission(session, secret_id, username)
            return perm.to_mlflow_entity()

    def list_permissions_for_user(self, username: str) -> List[GatewaySecretPermission]:
        with self._Session() as session:
            user = get_user(session, username)
            rows = session.query(SqlGatewaySecretPermission).filter(SqlGatewaySecretPermission.user_id == user.id).all()
            return [r.to_mlflow_entity() for r in rows]

    def update_permission(self, secret_id: str, username: str, permission: str) -> GatewaySecretPermission:
        _validate_permission(permission)
        with self._Session() as session:
            perm = self._get_permission(session, secret_id, username)
            perm.permission = permission
            session.flush()
            return perm.to_mlflow_entity()

    def revoke_permission(self, secret_id: str, username: str) -> None:
        with self._Session() as session:
            perm = self._get_permission(session, secret_id, username)
            session.delete(perm)
            session.flush()

    def wipe(self, secret_id: str) -> None:
        """Delete all user-level permissions for a gateway secret."""
        with self._Session() as session:
            perms = session.query(SqlGatewaySecretPermission).filter(SqlGatewaySecretPermission.secret_id == secret_id).all()
            for p in perms:
                session.delete(p)
            session.flush()
