from typing import Callable, List

from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlExperimentGroupRegexPermission
from mlflow_oidc_auth.entities import ExperimentGroupRegexPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository.utils import get_group, get_one_or_raise, get_user, list_user_groups, validate_regex


class ExperimentPermissionGroupRegexRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def _get_experiment_group_regex_permission(self, session, regex: str, group_id: int) -> SqlExperimentGroupRegexPermission:
        """
        Get the experiment group regex permission for a given regex and group ID.
        :param session: SQLAlchemy session
        :param regex: The regex pattern.
        :param group_id: The ID of the group.
        :return: The experiment group regex permission if it exists, otherwise None.
        """
        return get_one_or_raise(
            session,
            SqlExperimentGroupRegexPermission,
            SqlExperimentGroupRegexPermission.regex == regex,
            SqlExperimentGroupRegexPermission.group_id == group_id,
            not_found_msg="Permission not found for group_id: {} and regex: {}".format(group_id, regex),
            multiple_msg="Multiple Permissions found for group_id: {} and regex: {}".format(group_id, regex),
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

    def get(self, group_name: str, regex: str) -> ExperimentGroupRegexPermission:
        with self._Session() as session:
            group = get_group(session, group_name)
            row: SqlExperimentGroupRegexPermission = get_one_or_raise(
                session,
                SqlExperimentGroupRegexPermission,
                SqlExperimentGroupRegexPermission.regex == regex,
                SqlExperimentGroupRegexPermission.group_id == group.id,
                not_found_msg=f"No experiment perm for regex={regex}, group={group_name}",
                multiple_msg=f"Multiple experiment perms for regex={regex}, group={group_name}",
            )
            return row.to_mlflow_entity()

    def update(self, group_name: str, regex: str, priority: int, permission: str) -> ExperimentGroupRegexPermission:
        _validate_permission(permission)
        validate_regex(regex)
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = self._get_experiment_group_regex_permission(session, regex, int(group.id))
            if perm is None:
                raise ValueError(f"No permission found for group {group_name} and regex {regex}")
            perm.permission = permission
            perm.priority = priority
            session.commit()
            return perm.to_mlflow_entity()

    def revoke(self, group_name: str, regex: str) -> None:
        validate_regex(regex)
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = self._get_experiment_group_regex_permission(session, regex, int(group.id))
            if perm is None:
                raise ValueError(f"No permission found for group {group_name} and regex {regex}")
            session.delete(perm)
            session.commit()
            return None

    def list_permissions_for_group(self, group_name: str) -> List[ExperimentGroupRegexPermission]:
        with self._Session() as session:
            group = get_group(session, group_name)
            permissions = (
                session.query(SqlExperimentGroupRegexPermission)
                .filter(SqlExperimentGroupRegexPermission.group_id == group.id)
                .order_by(SqlExperimentGroupRegexPermission.priority)
                .all()
            )
            return [p.to_mlflow_entity() for p in permissions]

    def list_permissions_for_groups(self, group_names: List[str]) -> List[ExperimentGroupRegexPermission]:
        with self._Session() as session:
            group_ids = [get_group(session, group_name).id for group_name in group_names]
            permissions = (
                session.query(SqlExperimentGroupRegexPermission)
                .filter(SqlExperimentGroupRegexPermission.group_id.in_(group_ids))
                .order_by(SqlExperimentGroupRegexPermission.priority)
                .all()
            )
            return [p.to_mlflow_entity() for p in permissions]

    def list_permissions_for_group_id(self, group_id: int) -> List[ExperimentGroupRegexPermission]:
        with self._Session() as session:
            permissions = (
                session.query(SqlExperimentGroupRegexPermission)
                .filter(SqlExperimentGroupRegexPermission.group_id == group_id)
                .order_by(SqlExperimentGroupRegexPermission.priority)
                .all()
            )
            return [p.to_mlflow_entity() for p in permissions]

    def list_permissions_for_groups_ids(self, group_ids: List[int]) -> List[ExperimentGroupRegexPermission]:
        print(f"list_permissions_for_groups_ids: {group_ids}")
        with self._Session() as session:
            permissions = (
                session.query(SqlExperimentGroupRegexPermission)
                .filter(SqlExperimentGroupRegexPermission.group_id.in_(group_ids))
                .order_by(SqlExperimentGroupRegexPermission.priority)
                .all()
            )
            return [p.to_mlflow_entity() for p in permissions]

    def list_permissions_for_user_groups(self, username: str) -> List[ExperimentGroupRegexPermission]:
        with self._Session() as session:
            user = get_user(session, username)
            user_groups = list_user_groups(session, user)
            group_ids = [group.id for group in user_groups]
            permissions = (
                session.query(SqlExperimentGroupRegexPermission)
                .filter(SqlExperimentGroupRegexPermission.group_id.in_(group_ids))
                .all()
            )
            return [p.to_mlflow_entity() for p in permissions]
