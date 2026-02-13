from typing import Callable, List

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_STATE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlGatewayModelDefinitionPermission, SqlUser
from mlflow_oidc_auth.entities import GatewayModelDefinitionPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository.utils import get_user


class GatewayModelDefinitionPermissionRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def _get_permission(self, session: Session, model_definition_id: str, username: str) -> SqlGatewayModelDefinitionPermission:
        try:
            return (
                session.query(SqlGatewayModelDefinitionPermission)
                .join(SqlUser, SqlGatewayModelDefinitionPermission.user_id == SqlUser.id)
                .filter(
                    SqlGatewayModelDefinitionPermission.model_definition_id == model_definition_id,
                    SqlUser.username == username,
                )
                .one()
            )
        except NoResultFound as e:
            raise MlflowException(
                f"No gateway model definition permission for model_definition={model_definition_id}, user={username}",
                RESOURCE_DOES_NOT_EXIST,
            ) from e
        except MultipleResultsFound as e:
            raise MlflowException(
                f"Multiple gateway model definition perms for model_definition={model_definition_id}, user={username}",
                INVALID_STATE,
            ) from e

    def grant_permission(self, model_definition_id: str, username: str, permission: str) -> GatewayModelDefinitionPermission:
        _validate_permission(permission)
        with self._Session() as session:
            try:
                user = get_user(session, username)
                perm = SqlGatewayModelDefinitionPermission(
                    model_definition_id=model_definition_id,
                    user_id=user.id,
                    permission=permission,
                )
                session.add(perm)
                session.flush()
                return perm.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(
                    f"Gateway model definition permission already exists ({model_definition_id}, {username}): {e}",
                    RESOURCE_ALREADY_EXISTS,
                ) from e

    def get_permission(self, model_definition_id: str, username: str) -> GatewayModelDefinitionPermission:
        with self._Session() as session:
            perm = self._get_permission(session, model_definition_id, username)
            return perm.to_mlflow_entity()

    def list_permissions_for_user(self, username: str) -> List[GatewayModelDefinitionPermission]:
        with self._Session() as session:
            user = get_user(session, username)
            rows = session.query(SqlGatewayModelDefinitionPermission).filter(SqlGatewayModelDefinitionPermission.user_id == user.id).all()
            return [r.to_mlflow_entity() for r in rows]

    def update_permission(self, model_definition_id: str, username: str, permission: str) -> GatewayModelDefinitionPermission:
        _validate_permission(permission)
        with self._Session() as session:
            perm = self._get_permission(session, model_definition_id, username)
            perm.permission = permission
            session.flush()
            return perm.to_mlflow_entity()

    def revoke_permission(self, model_definition_id: str, username: str) -> None:
        with self._Session() as session:
            perm = self._get_permission(session, model_definition_id, username)
            session.delete(perm)
            session.flush()

    def wipe(self, model_definition_id: str) -> None:
        """Delete all user-level permissions for a gateway model definition."""
        with self._Session() as session:
            perms = session.query(SqlGatewayModelDefinitionPermission).filter(SqlGatewayModelDefinitionPermission.model_definition_id == model_definition_id).all()
            for p in perms:
                session.delete(p)
            session.flush()
