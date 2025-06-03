from typing import Callable, List

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_STATE, RESOURCE_DOES_NOT_EXIST
from sqlalchemy.exc import MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlExperimentGroupRegexPermission
from mlflow_oidc_auth.entities import ExperimentGroupRegexPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository.utils import get_group, get_user, list_user_groups, validate_regex


class ExperimentPermissionGroupRegexRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def _get_experiment_group_regex_permission(
        self, session: Session, id: int, group_id: int
    ) -> SqlExperimentGroupRegexPermission:
        """
        Get the experiment group regex permission for a given ID and group ID.
        :param session: SQLAlchemy session
        :param id: The ID of the permission.
        :param group_id: The ID of the group.
        :return: The experiment group regex permission if it exists, otherwise raises an exception.
        """
        try:
            return (
                session.query(SqlExperimentGroupRegexPermission)
                .filter(
                    SqlExperimentGroupRegexPermission.id == id,
                    SqlExperimentGroupRegexPermission.group_id == group_id,
                )
                .one()
            )
        except NoResultFound:
            raise MlflowException(f"Permission not found for group_id: {group_id} and id: {id}", RESOURCE_DOES_NOT_EXIST)
        except MultipleResultsFound:
            raise MlflowException(f"Multiple Permissions found for group_id: {group_id} and id: {id}", INVALID_STATE)

    def _list_group_permissions(self, session: Session, groups: List[int]) -> List[SqlExperimentGroupRegexPermission]:
        return (
            session.query(SqlExperimentGroupRegexPermission)
            .filter(SqlExperimentGroupRegexPermission.group_id.in_(groups))
            .order_by(SqlExperimentGroupRegexPermission.priority)
            .all()
        )

    def grant(self, group_name: str, regex: str, priority: int, permission: str) -> ExperimentGroupRegexPermission:
        _validate_permission(permission)
        validate_regex(regex)
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = SqlExperimentGroupRegexPermission(regex=regex, group_id=group.id, permission=permission, priority=priority)
            session.add(perm)
            session.flush()
            return perm.to_mlflow_entity()

    def get(self, group_name: str, id: int) -> ExperimentGroupRegexPermission:
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = self._get_experiment_group_regex_permission(session, id, group.id)
            return perm.to_mlflow_entity()

    def update(self, id: int, group_name: str, regex: str, priority: int, permission: str) -> ExperimentGroupRegexPermission:
        _validate_permission(permission)
        validate_regex(regex)
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = self._get_experiment_group_regex_permission(session, id, group.id)
            perm.permission = permission
            perm.regex = regex
            perm.priority = priority
            session.commit()
            return perm.to_mlflow_entity()

    def revoke(self, group_name: str, id: int) -> None:
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = self._get_experiment_group_regex_permission(session, id, group.id)
            session.delete(perm)
            session.commit()
            return None

    def list_permissions_for_group(self, group_name: str) -> List[ExperimentGroupRegexPermission]:
        with self._Session() as session:
            group = get_group(session, group_name)
            permissions = self._list_group_permissions(session, [group.id])
            return [p.to_mlflow_entity() for p in permissions]

    def list_permissions_for_groups(self, group_names: List[str]) -> List[ExperimentGroupRegexPermission]:
        with self._Session() as session:
            group_ids = [get_group(session, group_name).id for group_name in group_names]
            permissions = self._list_group_permissions(session, group_ids)
            return [p.to_mlflow_entity() for p in permissions]

    def list_permissions_for_group_id(self, group_id: int) -> List[ExperimentGroupRegexPermission]:
        with self._Session() as session:
            permissions = self._list_group_permissions(session, [group_id])
            return [p.to_mlflow_entity() for p in permissions]

    def list_permissions_for_groups_ids(self, group_ids: List[int]) -> List[ExperimentGroupRegexPermission]:
        with self._Session() as session:
            permissions = self._list_group_permissions(session, group_ids)
            return [p.to_mlflow_entity() for p in permissions]

    def list_permissions_for_user_groups(self, username: str) -> List[ExperimentGroupRegexPermission]:
        with self._Session() as session:
            user = get_user(session, username)
            user_groups = list_user_groups(session, user)
            group_ids = [group.id for group in user_groups]
            permissions = self._list_group_permissions(session, group_ids)
            return [p.to_mlflow_entity() for p in permissions]
