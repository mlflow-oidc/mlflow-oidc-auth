from typing import List, Callable
from sqlalchemy.orm import Session
from mlflow_oidc_auth.entities import ExperimentGroupRegexPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository.utils import get_one_optional, get_one_or_raise, get_group, validate_regex
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

    def grant_group_permission(self, group_name: str, regex: str, permission: str) -> ExperimentGroupRegexPermission:
        _validate_permission(permission)
        validate_regex(regex)
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = SqlExperimentGroupRegexPermission(regex=regex, group_id=group.id, permission=permission)
            session.add(perm)
            session.flush()
            return perm.to_mlflow_entity()

    # def list_permissions_for_group(self, group_name: str) -> List[ExperimentPermission]:
    # def list_permissions_for_group_id(self, group_id: int) -> List[ExperimentPermission]:
    # def list_permissions_for_user_groups(self, username: str) -> List[ExperimentPermission]:
    # def get_group_permission_for_user_experiment(self, experiment_id: str, username: str) -> ExperimentPermission:

    def update_group_permission(self, group_name: str, regex: str, permission: str) -> ExperimentGroupRegexPermission:
        _validate_permission(permission)
        validate_regex(regex)
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = self._get_experiment_group_regex_permission(session, regex, int(group.id))
            if perm is None:
                raise ValueError(f"No permission found for group {group_name} and regex {regex}")
            perm.permission = permission
            session.commit()
            return perm.to_mlflow_entity()


# def revoke_group_permission(self, group_name: str, experiment_id: str) -> None:
