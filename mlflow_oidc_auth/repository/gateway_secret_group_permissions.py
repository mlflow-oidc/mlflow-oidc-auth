from typing import Callable, List

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_STATE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlGatewaySecretGroupPermission, SqlGroup
from mlflow_oidc_auth.entities import GatewaySecretPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository.utils import get_group


class GatewaySecretGroupPermissionRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def _get_group_permission(self, session: Session, secret_id: str, group_name: str) -> SqlGatewaySecretGroupPermission:
        try:
            return (
                session.query(SqlGatewaySecretGroupPermission)
                .join(SqlGroup, SqlGatewaySecretGroupPermission.group_id == SqlGroup.id)
                .filter(
                    SqlGatewaySecretGroupPermission.secret_id == secret_id,
                    SqlGroup.group_name == group_name,
                )
                .one()
            )
        except NoResultFound as e:
            raise MlflowException(
                f"No gateway secret group permission for secret={secret_id}, group={group_name}",
                RESOURCE_DOES_NOT_EXIST,
            ) from e
        except MultipleResultsFound as e:
            raise MlflowException(
                f"Multiple gateway secret group perms for secret={secret_id}, group={group_name}",
                INVALID_STATE,
            ) from e

    def grant_group_permission(self, group_name: str, secret_id: str, permission: str) -> GatewaySecretPermission:
        _validate_permission(permission)
        with self._Session() as session:
            try:
                group = get_group(session, group_name)
                perm = SqlGatewaySecretGroupPermission(
                    secret_id=secret_id,
                    group_id=group.id,
                    permission=permission,
                )
                session.add(perm)
                session.flush()
                return perm.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(
                    f"Gateway secret group permission already exists ({secret_id}, {group_name}): {e}",
                    RESOURCE_ALREADY_EXISTS,
                ) from e

    def get_group_permission_for_user(self, secret_id: str, group_name: str) -> GatewaySecretPermission:
        with self._Session() as session:
            perm = self._get_group_permission(session, secret_id, group_name)
            return perm.to_mlflow_entity()

    def list_permissions_for_group(self, group_name: str) -> List[GatewaySecretPermission]:
        with self._Session() as session:
            group = get_group(session, group_name)
            rows = session.query(SqlGatewaySecretGroupPermission).filter(SqlGatewaySecretGroupPermission.group_id == group.id).all()
            return [r.to_mlflow_entity() for r in rows]

    def revoke_group_permission(self, group_name: str, secret_id: str) -> None:
        with self._Session() as session:
            perm = self._get_group_permission(session, secret_id, group_name)
            session.delete(perm)
            session.flush()

    def update_group_permission(self, group_name: str, secret_id: str, permission: str) -> GatewaySecretPermission:
        _validate_permission(permission)
        with self._Session() as session:
            perm = self._get_group_permission(session, secret_id, group_name)
            perm.permission = permission
            session.flush()
            return perm.to_mlflow_entity()

    def list_groups_for_secret(self, secret_id: str):
        with self._Session() as session:
            rows = (
                session.query(SqlGatewaySecretGroupPermission, SqlGroup.group_name)
                .join(SqlGroup, SqlGatewaySecretGroupPermission.group_id == SqlGroup.id)
                .filter(SqlGatewaySecretGroupPermission.secret_id == secret_id)
                .all()
            )
            return [(group_name, perm.permission) for perm, group_name in rows]

    def wipe(self, secret_id: str) -> None:
        """Delete all group-level permissions for a gateway secret."""
        with self._Session() as session:
            perms = session.query(SqlGatewaySecretGroupPermission).filter(SqlGatewaySecretGroupPermission.secret_id == secret_id).all()
            for p in perms:
                session.delete(p)
            session.flush()
