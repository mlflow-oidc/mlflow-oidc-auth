from typing import Callable, List

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_STATE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlGatewayModelDefinitionGroupRegexPermission, SqlGroup
from mlflow_oidc_auth.entities import GatewayModelDefinitionGroupRegexPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository.utils import get_group


class GatewayModelDefinitionPermissionGroupRegexRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def _get_group_regex_permission(self, session: Session, id: int, group_id: int) -> SqlGatewayModelDefinitionGroupRegexPermission:
        try:
            return (
                session.query(SqlGatewayModelDefinitionGroupRegexPermission)
                .filter(
                    SqlGatewayModelDefinitionGroupRegexPermission.id == id,
                    SqlGatewayModelDefinitionGroupRegexPermission.group_id == group_id,
                )
                .one()
            )
        except NoResultFound:
            raise MlflowException(f"Permission not found for group_id: {group_id} and id: {id}", RESOURCE_DOES_NOT_EXIST)
        except MultipleResultsFound:
            raise MlflowException(f"Multiple Permissions found for group_id: {group_id} and id: {id}", INVALID_STATE)

    def grant(self, group_name: str, regex: str, priority: int, permission: str) -> GatewayModelDefinitionGroupRegexPermission:
        _validate_permission(permission)
        with self._Session() as session:
            try:
                group = get_group(session, group_name)
                perm = SqlGatewayModelDefinitionGroupRegexPermission(
                    regex=regex,
                    priority=priority,
                    group_id=group.id,
                    permission=permission,
                )
                session.add(perm)
                session.flush()
                return perm.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(
                    f"Gateway model definition group regex perm exists ({regex},{group_name}): {e}",
                    RESOURCE_ALREADY_EXISTS,
                )

    def get(self, id: int, group_name: str) -> GatewayModelDefinitionGroupRegexPermission:
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = self._get_group_regex_permission(session, id, group.id)
            return perm.to_mlflow_entity()

    def list_permissions_for_group(self, group_name: str) -> List[GatewayModelDefinitionGroupRegexPermission]:
        with self._Session() as session:
            group = get_group(session, group_name)
            perms = (
                session.query(SqlGatewayModelDefinitionGroupRegexPermission)
                .filter(SqlGatewayModelDefinitionGroupRegexPermission.group_id == group.id)
                .order_by(SqlGatewayModelDefinitionGroupRegexPermission.priority)
                .all()
            )
            return [p.to_mlflow_entity() for p in perms]

    def list_permissions_for_groups(self, group_names: List[str]) -> List[GatewayModelDefinitionGroupRegexPermission]:
        with self._Session() as session:
            groups = [get_group(session, name) for name in group_names]
            perms = (
                session.query(SqlGatewayModelDefinitionGroupRegexPermission)
                .filter(SqlGatewayModelDefinitionGroupRegexPermission.group_id.in_([g.id for g in groups]))
                .order_by(SqlGatewayModelDefinitionGroupRegexPermission.priority)
                .all()
            )
            return [p.to_mlflow_entity() for p in perms]

    def list_permissions_for_groups_ids(self, group_ids: List[int]) -> List[GatewayModelDefinitionGroupRegexPermission]:
        with self._Session() as session:
            perms = (
                session.query(SqlGatewayModelDefinitionGroupRegexPermission)
                .filter(SqlGatewayModelDefinitionGroupRegexPermission.group_id.in_(group_ids))
                .order_by(SqlGatewayModelDefinitionGroupRegexPermission.priority)
                .all()
            )
            return [p.to_mlflow_entity() for p in perms]

    def revoke(self, id: int, group_name: str) -> None:
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = self._get_group_regex_permission(session, id, group.id)
            session.delete(perm)
            session.commit()
            return None
