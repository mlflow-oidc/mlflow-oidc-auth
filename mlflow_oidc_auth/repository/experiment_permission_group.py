from typing import List, Optional, Callable
from sqlalchemy.orm import Session
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST

from mlflow_oidc_auth.db.models import SqlExperimentGroupPermission, SqlGroup, SqlUserGroup
from mlflow_oidc_auth.entities import ExperimentPermission
from mlflow_oidc_auth.permissions import _validate_permission, compare_permissions
from mlflow_oidc_auth.repository.utils import get_user, get_group, list_user_groups


class ExperimentPermissionGroupRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def _get_experiment_group_permission(
        self, session: Session, experiment_id: str, group_name: str
    ) -> Optional[SqlExperimentGroupPermission]:
        """
        Get the experiment group permission for a given experiment and group name.
        :param session: SQLAlchemy session
        :param experiment_id: The ID of the experiment.
        :param group_name: The name of the group.
        :return: The experiment group permission if it exists, otherwise None.
        """
        group = session.query(SqlGroup).filter(SqlGroup.group_name == group_name).one_or_none()
        if group is None:
            return None
        return (
            session.query(SqlExperimentGroupPermission)
            .filter(
                SqlExperimentGroupPermission.experiment_id == experiment_id,
                SqlExperimentGroupPermission.group_id == group.id,
            )
            .one_or_none()
        )

    def _list_user_groups(self, username: str) -> List[str]:
        """
        List all groups for a given user.
        :param username: The username of the user.
        :return: A list of group names the user belongs to.
        """
        with self._Session() as session:
            user = get_user(session, username)
            user_groups_ids = list_user_groups(session, user)
            user_groups = session.query(SqlGroup).filter(SqlGroup.id.in_([ug.group_id for ug in user_groups_ids])).all()
            return [ug.group_name for ug in user_groups]

    def grant_group_permission(self, group_name: str, experiment_id: str, permission: str) -> ExperimentPermission:
        """
        Create a new experiment group permission.
        :param group_name: The name of the group.
        :param experiment_id: The ID of the experiment.
        :param permission: The permission to be granted to the group.
        :return: The created experiment group permission.
        """
        _validate_permission(permission)
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = SqlExperimentGroupPermission(experiment_id=experiment_id, group_id=group.id, permission=permission)
            session.add(perm)
            session.flush()
            return perm.to_mlflow_entity()

    def list_permissions_for_group(self, group_name: str) -> List[ExperimentPermission]:
        """
        List all experiment permissions for a given group.
        :param group_name: The name of the group.
        :return: A list of experiment permissions for the group.
        """
        with self._Session() as session:
            group = get_group(session, group_name)
            perms = session.query(SqlExperimentGroupPermission).filter(SqlExperimentGroupPermission.group_id == group.id).all()
            return [p.to_mlflow_entity() for p in perms]

    def list_permissions_for_group_id(self, group_id: int) -> List[ExperimentPermission]:
        """
        List all experiment permissions for a given group ID.
        :param group_id: The ID of the group.
        :return: A list of experiment permissions for the group.
        """
        with self._Session() as session:
            perms = session.query(SqlExperimentGroupPermission).filter(SqlExperimentGroupPermission.group_id == group_id).all()
            return [p.to_mlflow_entity() for p in perms]

    def list_permissions_for_user_groups(self, username: str) -> List[ExperimentPermission]:
        """
        List all experiment permissions for a given user.
        :param username: The username of the user.
        :return: A list of experiment permissions for the user.
        """
        with self._Session() as session:
            user = get_user(session, username=username)
            user_groups = list_user_groups(session, user)
            perms = (
                session.query(SqlExperimentGroupPermission)
                .filter(SqlExperimentGroupPermission.group_id.in_([ug.group_id for ug in user_groups]))
                .all()
            )
            return [p.to_mlflow_entity() for p in perms]

    def get_group_permission_for_user_experiment(self, experiment_id: str, username: str) -> ExperimentPermission:
        """
        Get the experiment permission for a given user and experiment.
        :param experiment_id: The ID of the experiment.
        :param username: The username of the user.
        :return: The experiment permission for the user.
        """
        with self._Session() as session:
            user_groups = self._list_user_groups(username)
            user_perms: Optional[SqlExperimentGroupPermission] = None
            for ug in user_groups:
                perms = self._get_experiment_group_permission(session, experiment_id, ug)
                if perms is None:
                    continue
                if user_perms is None:
                    user_perms = perms
                    continue
                try:
                    if compare_permissions(str(user_perms.permission), str(perms.permission)):
                        user_perms = perms
                except AttributeError:
                    user_perms = perms
            try:
                if user_perms is not None:
                    return user_perms.to_mlflow_entity()
                else:
                    raise MlflowException(
                        f"Experiment with experiment_id={experiment_id} and username={username} not found",
                        RESOURCE_DOES_NOT_EXIST,
                    )
            except AttributeError:
                raise MlflowException(
                    f"Experiment permission with experiment_id={experiment_id} and username={username} not found",
                    RESOURCE_DOES_NOT_EXIST,
                )

    def update_group_permission(self, group_name: str, experiment_id: str, permission: str) -> ExperimentPermission:
        """
        Update the experiment group permission for a given experiment and group name.
        :param group_name: The name of the group.
        :param experiment_id: The ID of the experiment.
        :param permission: The new permission to be granted to the group.
        :return: The updated experiment group permission.
        """
        _validate_permission(permission)
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = (
                session.query(SqlExperimentGroupPermission)
                .filter(
                    SqlExperimentGroupPermission.experiment_id == experiment_id,
                    SqlExperimentGroupPermission.group_id == group.id,
                )
                .one()
            )
            perm.permission = permission
            session.flush()
            return perm.to_mlflow_entity()

    def revoke_group_permission(self, group_name: str, experiment_id: str) -> None:
        """
        Delete the experiment group permission for a given experiment and group name.
        :param group_name: The name of the group.
        :param experiment_id: The ID of the experiment.
        """
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = (
                session.query(SqlExperimentGroupPermission)
                .filter(
                    SqlExperimentGroupPermission.experiment_id == experiment_id,
                    SqlExperimentGroupPermission.group_id == group.id,
                )
                .one()
            )
            session.delete(perm)
            session.flush()
