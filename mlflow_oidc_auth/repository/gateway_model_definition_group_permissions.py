from typing import Callable, List

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_STATE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlGatewayModelDefinitionGroupPermission, SqlGroup
from mlflow_oidc_auth.entities import GatewayModelDefinitionPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository.utils import get_group


class GatewayModelDefinitionGroupPermissionRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def _get_group_permission(self, session: Session, model_definition_id: str, group_name: str) -> SqlGatewayModelDefinitionGroupPermission:
        try:
            return (
                session.query(SqlGatewayModelDefinitionGroupPermission)
                .join(SqlGroup, SqlGatewayModelDefinitionGroupPermission.group_id == SqlGroup.id)
                .filter(
                    SqlGatewayModelDefinitionGroupPermission.model_definition_id == model_definition_id,
                    SqlGroup.group_name == group_name,
                )
                .one()
            )
        except NoResultFound as e:
            raise MlflowException(
                f"No gateway model definition group permission for model_definition={model_definition_id}, group={group_name}",
                RESOURCE_DOES_NOT_EXIST,
            ) from e
        except MultipleResultsFound as e:
            raise MlflowException(
                f"Multiple gateway model definition group perms for model_definition={model_definition_id}, group={group_name}",
                INVALID_STATE,
            ) from e

    def grant_group_permission(self, group_name: str, model_definition_id: str, permission: str) -> GatewayModelDefinitionPermission:
        _validate_permission(permission)
        with self._Session() as session:
            try:
                group = get_group(session, group_name)
                perm = SqlGatewayModelDefinitionGroupPermission(
                    model_definition_id=model_definition_id,
                    group_id=group.id,
                    permission=permission,
                )
                session.add(perm)
                session.flush()
                return perm.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(
                    f"Gateway model definition group permission already exists ({model_definition_id}, {group_name}): {e}",
                    RESOURCE_ALREADY_EXISTS,
                ) from e

    def get_group_permission_for_user(self, model_definition_id: str, group_name: str) -> GatewayModelDefinitionPermission:
        with self._Session() as session:
            perm = self._get_group_permission(session, model_definition_id, group_name)
            return perm.to_mlflow_entity()

    def list_permissions_for_group(self, group_name: str) -> List[GatewayModelDefinitionPermission]:
        with self._Session() as session:
            group = get_group(session, group_name)
            rows = session.query(SqlGatewayModelDefinitionGroupPermission).filter(SqlGatewayModelDefinitionGroupPermission.group_id == group.id).all()
            return [r.to_mlflow_entity() for r in rows]

    def revoke_group_permission(self, group_name: str, model_definition_id: str) -> None:
        with self._Session() as session:
            perm = self._get_group_permission(session, model_definition_id, group_name)
            session.delete(perm)
            session.flush()

    def update_group_permission(self, group_name: str, model_definition_id: str, permission: str) -> GatewayModelDefinitionPermission:
        _validate_permission(permission)
        with self._Session() as session:
            perm = self._get_group_permission(session, model_definition_id, group_name)
            perm.permission = permission
            session.flush()
            return perm.to_mlflow_entity()

    def list_groups_for_model_definition(self, model_definition_id: str):
        with self._Session() as session:
            rows = (
                session.query(SqlGatewayModelDefinitionGroupPermission, SqlGroup.group_name)
                .join(SqlGroup, SqlGatewayModelDefinitionGroupPermission.group_id == SqlGroup.id)
                .filter(SqlGatewayModelDefinitionGroupPermission.model_definition_id == model_definition_id)
                .all()
            )
            return [(group_name, perm.permission) for perm, group_name in rows]
