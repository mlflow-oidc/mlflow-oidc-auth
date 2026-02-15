from typing import Callable, List

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_STATE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlGatewayEndpointGroupPermission, SqlGroup
from mlflow_oidc_auth.entities import GatewayEndpointPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository.utils import get_group


class GatewayEndpointGroupPermissionRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def _get_group_permission(self, session: Session, endpoint_id: str, group_name: str) -> SqlGatewayEndpointGroupPermission:
        try:
            return (
                session.query(SqlGatewayEndpointGroupPermission)
                .join(SqlGroup, SqlGatewayEndpointGroupPermission.group_id == SqlGroup.id)
                .filter(
                    SqlGatewayEndpointGroupPermission.endpoint_id == endpoint_id,
                    SqlGroup.group_name == group_name,
                )
                .one()
            )
        except NoResultFound as e:
            raise MlflowException(
                f"No gateway endpoint group permission for endpoint={endpoint_id}, group={group_name}",
                RESOURCE_DOES_NOT_EXIST,
            ) from e
        except MultipleResultsFound as e:
            raise MlflowException(
                f"Multiple gateway endpoint group perms for endpoint={endpoint_id}, group={group_name}",
                INVALID_STATE,
            ) from e

    def grant_group_permission(self, group_name: str, endpoint_id: str, permission: str) -> GatewayEndpointPermission:
        _validate_permission(permission)
        with self._Session() as session:
            try:
                group = get_group(session, group_name)
                perm = SqlGatewayEndpointGroupPermission(
                    endpoint_id=endpoint_id,
                    group_id=group.id,
                    permission=permission,
                )
                session.add(perm)
                session.flush()
                return perm.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(
                    f"Gateway endpoint group permission already exists ({endpoint_id}, {group_name}): {e}",
                    RESOURCE_ALREADY_EXISTS,
                ) from e

    def get_group_permission_for_user(self, endpoint_id: str, group_name: str) -> GatewayEndpointPermission:
        with self._Session() as session:
            perm = self._get_group_permission(session, endpoint_id, group_name)
            return perm.to_mlflow_entity()

    def list_permissions_for_group(self, group_name: str) -> List[GatewayEndpointPermission]:
        with self._Session() as session:
            group = get_group(session, group_name)
            rows = session.query(SqlGatewayEndpointGroupPermission).filter(SqlGatewayEndpointGroupPermission.group_id == group.id).all()
            return [r.to_mlflow_entity() for r in rows]

    def revoke_group_permission(self, group_name: str, endpoint_id: str) -> None:
        with self._Session() as session:
            perm = self._get_group_permission(session, endpoint_id, group_name)
            session.delete(perm)
            session.flush()

    def update_group_permission(self, group_name: str, endpoint_id: str, permission: str) -> GatewayEndpointPermission:
        _validate_permission(permission)
        with self._Session() as session:
            perm = self._get_group_permission(session, endpoint_id, group_name)
            perm.permission = permission
            session.flush()
            return perm.to_mlflow_entity()

    def rename(self, old_name: str, new_name: str) -> None:
        """Update all group-level permissions from *old_name* to *new_name*."""
        with self._Session() as session:
            perms = session.query(SqlGatewayEndpointGroupPermission).filter(SqlGatewayEndpointGroupPermission.endpoint_id == old_name).all()
            for perm in perms:
                perm.endpoint_id = new_name
            session.flush()

    def list_groups_for_endpoint(self, endpoint_id: str):
        with self._Session() as session:
            rows = (
                session.query(SqlGatewayEndpointGroupPermission, SqlGroup.group_name)
                .join(SqlGroup, SqlGatewayEndpointGroupPermission.group_id == SqlGroup.id)
                .filter(SqlGatewayEndpointGroupPermission.endpoint_id == endpoint_id)
                .all()
            )
            return [(group_name, perm.permission) for perm, group_name in rows]

    def wipe(self, endpoint_id: str) -> None:
        """Delete all group-level permissions for a gateway endpoint."""
        with self._Session() as session:
            perms = session.query(SqlGatewayEndpointGroupPermission).filter(SqlGatewayEndpointGroupPermission.endpoint_id == endpoint_id).all()
            for p in perms:
                session.delete(p)
            session.flush()
