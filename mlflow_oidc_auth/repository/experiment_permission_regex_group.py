from typing import List, Callable
from sqlalchemy.orm import Session
from mlflow_oidc_auth.entities import ExperimentGroupRegexPermission, ExperimentPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository.utils import (
    get_one_optional,
    get_one_or_raise,
    get_group,
    validate_regex,
    get_user,
    list_user_groups,
)
from mlflow_oidc_auth.db.models import SqlExperimentGroupRegexPermission, SqlGroup


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

    def _experiment_id_to_name(self, session, experiment_id: str) -> str:
        """
        Convert experiment ID to name.
        :param session: SQLAlchemy session
        :param experiment_id: The ID of the experiment.
        :return: The name of the experiment.
        """
        # need to fetch experiments until experiment_id we have a match
        # import mlflow
        # mlflow.get_experiment_by_name("aaa")
        # get_experiment_by_name
        # return _get_tracking_store().get_experiment_by_name(args["experiment_name"]).experiment_id
        return experiment_id

    def _is_experiment_in_regex(self, session, experiment_id: str, regex: str) -> bool:
        """
        Check if the experiment ID matches the regex pattern.
        :param session: SQLAlchemy session
        :param experiment_id: The ID of the experiment.
        :param regex: The regex pattern.
        :return: True if the experiment ID matches the regex, otherwise False.
        """

        # return session.query(SqlExperimentGroupRegexPermission).filter(
        #     SqlExperimentGroupRegexPermission.regex == regex,
        #     SqlExperimentGroupRegexPermission.experiment_id == experiment_id
        # ).count() > 0
        return False

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
                .all()
            )
            return [p.to_mlflow_entity() for p in permissions]

    def list_permissions_for_group_id(self, group_id: int) -> List[ExperimentGroupRegexPermission]:
        with self._Session() as session:
            permissions = (
                session.query(SqlExperimentGroupRegexPermission)
                .filter(SqlExperimentGroupRegexPermission.group_id == group_id)
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

    # def get_group_permission_for_user_experiment(self, experiment_id: str, username: str) -> ExperimentPermission:
