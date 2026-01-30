from typing import Callable, List

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_STATE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlGatewaySecretGroupRegexPermission, SqlGroup
from mlflow_oidc_auth.entities import GatewaySecretGroupRegexPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository.utils import get_group


class GatewaySecretPermissionGroupRegexRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def _get_group_regex_permission(self, session: Session, id: int, group_id: int) -> SqlGatewaySecretGroupRegexPermission:
        try:
            return (
                session.query(SqlGatewaySecretGroupRegexPermission)
                .filter(
                    SqlGatewaySecretGroupRegexPermission.id == id,
                    SqlGatewaySecretGroupRegexPermission.group_id == group_id,
                )
                .one()
            )
        except NoResultFound:
            raise MlflowException(f"Permission not found for group_id: {group_id} and id: {id}", RESOURCE_DOES_NOT_EXIST)
        except MultipleResultsFound:
            raise MlflowException(f"Multiple Permissions found for group_id: {group_id} and id: {id}", INVALID_STATE)

    def grant(self, group_name: str, regex: str, priority: int, permission: str) -> GatewaySecretGroupRegexPermission:
        _validate_permission(permission)
        with self._Session() as session:
            try:
                group = get_group(session, group_name)
                perm = SqlGatewaySecretGroupRegexPermission(
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
                    f"Gateway secret group regex perm exists ({regex},{group_name}): {e}",
                    RESOURCE_ALREADY_EXISTS,
                )

    def get(self, id: int, group_name: str) -> GatewaySecretGroupRegexPermission:
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = self._get_group_regex_permission(session, id, group.id)
            return perm.to_mlflow_entity()

    def list_permissions_for_group(self, group_name: str) -> List[GatewaySecretGroupRegexPermission]:
        with self._Session() as session:
            group = get_group(session, group_name)
            perms = (
                session.query(SqlGatewaySecretGroupRegexPermission)
                .filter(SqlGatewaySecretGroupRegexPermission.group_id == group.id)
                .order_by(SqlGatewaySecretGroupRegexPermission.priority)
                .all()
            )
            return [p.to_mlflow_entity() for p in perms]

    def list_permissions_for_groups(self, group_names: List[str]) -> List[GatewaySecretGroupRegexPermission]:
        with self._Session() as session:
            groups = [get_group(session, name) for name in group_names]
            perms = (
                session.query(SqlGatewaySecretGroupRegexPermission)
                .filter(SqlGatewaySecretGroupRegexPermission.group_id.in_([g.id for g in groups]))
                .order_by(SqlGatewaySecretGroupRegexPermission.priority)
                .all()
            )
            return [p.to_mlflow_entity() for p in perms]

    def list_permissions_for_groups_ids(self, group_ids: List[int]) -> List[GatewaySecretGroupRegexPermission]:
        with self._Session() as session:
            perms = (
                session.query(SqlGatewaySecretGroupRegexPermission)
                .filter(SqlGatewaySecretGroupRegexPermission.group_id.in_(group_ids))
                .order_by(SqlGatewaySecretGroupRegexPermission.priority)
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
