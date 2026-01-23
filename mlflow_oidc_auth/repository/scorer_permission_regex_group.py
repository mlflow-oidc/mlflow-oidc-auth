from typing import Callable, List

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_STATE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlScorerGroupRegexPermission
from mlflow_oidc_auth.entities import ScorerGroupRegexPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository.utils import get_group, validate_regex


class ScorerPermissionGroupRegexRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def _get(self, session: Session, group_id: int, id: int) -> SqlScorerGroupRegexPermission:
        try:
            return (
                session.query(SqlScorerGroupRegexPermission)
                .filter(
                    SqlScorerGroupRegexPermission.group_id == group_id,
                    SqlScorerGroupRegexPermission.id == id,
                )
                .one()
            )
        except NoResultFound as e:
            raise MlflowException(
                f"Scorer group regex permission not found for group_id={group_id}, id={id}",
                RESOURCE_DOES_NOT_EXIST,
            ) from e
        except MultipleResultsFound as e:
            raise MlflowException(
                f"Multiple scorer group regex permissions for group_id={group_id}, id={id}",
                INVALID_STATE,
            ) from e

    def grant(self, group_name: str, regex: str, priority: int, permission: str) -> ScorerGroupRegexPermission:
        validate_regex(regex)
        _validate_permission(permission)
        with self._Session() as session:
            try:
                group = get_group(session, group_name)
                perm = SqlScorerGroupRegexPermission(regex=regex, priority=priority, group_id=group.id, permission=permission)
                session.add(perm)
                session.flush()
                return perm.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(
                    f"Scorer group regex perm exists ({regex},{group_name}): {e}",
                    RESOURCE_ALREADY_EXISTS,
                ) from e

    def get(self, group_name: str, id: int) -> ScorerGroupRegexPermission:
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = self._get(session, group.id, id)
            return perm.to_mlflow_entity()

    def list_permissions_for_groups_ids(self, group_ids: List[int]) -> List[ScorerGroupRegexPermission]:
        with self._Session() as session:
            rows = (
                session.query(SqlScorerGroupRegexPermission)
                .filter(SqlScorerGroupRegexPermission.group_id.in_(group_ids))
                .order_by(SqlScorerGroupRegexPermission.priority)
                .all()
            )
            return [r.to_mlflow_entity() for r in rows]

    def update(self, id: int, group_name: str, regex: str, priority: int, permission: str) -> ScorerGroupRegexPermission:
        validate_regex(regex)
        _validate_permission(permission)
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = self._get(session, group.id, id)
            perm.regex = regex
            perm.priority = priority
            perm.permission = permission
            session.commit()
            return perm.to_mlflow_entity()

    def revoke(self, id: int, group_name: str) -> None:
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = self._get(session, group.id, id)
            session.delete(perm)
            session.commit()
