from typing import Callable, List

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_STATE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlGatewayEndpointPermission, SqlUser
from mlflow_oidc_auth.entities import GatewayEndpointPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository.utils import get_user


class GatewayEndpointPermissionRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def _get_permission(self, session: Session, endpoint_id: str, username: str) -> SqlGatewayEndpointPermission:
        try:
            return (
                session.query(SqlGatewayEndpointPermission)
                .join(SqlUser, SqlGatewayEndpointPermission.user_id == SqlUser.id)
                .filter(
                    SqlGatewayEndpointPermission.endpoint_id == endpoint_id,
                    SqlUser.username == username,
                )
                .one()
            )
        except NoResultFound as e:
            raise MlflowException(
                f"No gateway endpoint permission for endpoint={endpoint_id}, user={username}",
                RESOURCE_DOES_NOT_EXIST,
            ) from e
        except MultipleResultsFound as e:
            raise MlflowException(
                f"Multiple gateway endpoint perms for endpoint={endpoint_id}, user={username}",
                INVALID_STATE,
            ) from e

    def grant_permission(self, endpoint_id: str, username: str, permission: str) -> GatewayEndpointPermission:
        _validate_permission(permission)
        with self._Session() as session:
            try:
                user = get_user(session, username)
                perm = SqlGatewayEndpointPermission(
                    endpoint_id=endpoint_id,
                    user_id=user.id,
                    permission=permission,
                )
                session.add(perm)
                session.flush()
                return perm.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(
                    f"Gateway endpoint permission already exists ({endpoint_id}, {username}): {e}",
                    RESOURCE_ALREADY_EXISTS,
                ) from e

    def get_permission(self, endpoint_id: str, username: str) -> GatewayEndpointPermission:
        with self._Session() as session:
            perm = self._get_permission(session, endpoint_id, username)
            return perm.to_mlflow_entity()

    def list_permissions_for_user(self, username: str) -> List[GatewayEndpointPermission]:
        with self._Session() as session:
            user = get_user(session, username)
            rows = session.query(SqlGatewayEndpointPermission).filter(SqlGatewayEndpointPermission.user_id == user.id).all()
            return [r.to_mlflow_entity() for r in rows]

    def update_permission(self, endpoint_id: str, username: str, permission: str) -> GatewayEndpointPermission:
        _validate_permission(permission)
        with self._Session() as session:
            perm = self._get_permission(session, endpoint_id, username)
            perm.permission = permission
            session.flush()
            return perm.to_mlflow_entity()

    def revoke_permission(self, endpoint_id: str, username: str) -> None:
        with self._Session() as session:
            perm = self._get_permission(session, endpoint_id, username)
            session.delete(perm)
            session.flush()

    def rename(self, old_name: str, new_name: str) -> None:
        """Update all user-level permissions from *old_name* to *new_name*."""
        with self._Session() as session:
            perms = session.query(SqlGatewayEndpointPermission).filter(SqlGatewayEndpointPermission.endpoint_id == old_name).all()
            for perm in perms:
                perm.endpoint_id = new_name
            session.flush()

    def wipe(self, endpoint_id: str) -> None:
        """Delete all user-level permissions for a gateway endpoint."""
        with self._Session() as session:
            perms = session.query(SqlGatewayEndpointPermission).filter(SqlGatewayEndpointPermission.endpoint_id == endpoint_id).all()
            for p in perms:
                session.delete(p)
            session.flush()
