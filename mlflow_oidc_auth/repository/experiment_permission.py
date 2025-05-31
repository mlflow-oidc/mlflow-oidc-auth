from typing import Callable, List

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_STATE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlExperimentPermission, SqlUser
from mlflow_oidc_auth.entities import ExperimentPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository.utils import get_user


class ExperimentPermissionRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def _get_experiment_permission(self, session, experiment_id: str, username: str) -> SqlExperimentPermission:
        """
        Get the experiment permission for a given experiment and user.
        :param session: SQLAlchemy session
        :param experiment_id: The ID of the experiment.
        :param username: The username of the user.
        :return: The experiment permission if it exists, otherwise raises an exception.
        """
        try:
            return (
                session.query(SqlExperimentPermission)
                .join(SqlUser, SqlExperimentPermission.user_id == SqlUser.id)
                .filter(
                    SqlExperimentPermission.experiment_id == experiment_id,
                    SqlUser.username == username,
                )
                .one()
            )
        except NoResultFound:
            raise MlflowException(
                f"No permission for exp={experiment_id}, user={username}",
                RESOURCE_DOES_NOT_EXIST,
            )
        except MultipleResultsFound:
            raise MlflowException(
                f"Multiple perms for exp={experiment_id}, user={username}",
                INVALID_STATE,
            )

    def grant_permission(self, experiment_id: str, username: str, permission: str) -> ExperimentPermission:
        """
        Create a new experiment permission.
        :param experiment_id: The ID of the experiment.
        :param username: The username of the user.
        :param permission: The permission to be granted to the user.
        :return: The created experiment permission.
        """
        _validate_permission(permission)
        with self._Session() as session:
            try:
                user = get_user(session, username)
                perm = SqlExperimentPermission(experiment_id=experiment_id, user_id=user.id, permission=permission)
                session.add(perm)
                session.flush()
                return perm.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(
                    f"Experiment permission already exists ({experiment_id}, {username}): {e}",
                    RESOURCE_ALREADY_EXISTS,
                )

    def get_permission(self, experiment_id: str, username: str) -> ExperimentPermission:
        """
        Get the experiment permission for a given experiment and user.
        :param experiment_id: The ID of the experiment.
        :param username: The username of the user.
        :return: The experiment permission if it exists.
        """
        with self._Session() as session:
            perm = self._get_experiment_permission(session, experiment_id, username)
            return perm.to_mlflow_entity()

    def list_permissions_for_user(self, username: str) -> List[ExperimentPermission]:
        """
        List all experiment permissions for a given user.
        :param username: The username of the user.
        :return: A list of experiment permissions for the user.
        """
        with self._Session() as session:
            user = get_user(session, username)
            rows: List[SqlExperimentPermission] = (
                session.query(SqlExperimentPermission).filter(SqlExperimentPermission.user_id == user.id).all()
            )
            return [r.to_mlflow_entity() for r in rows]

    def list_permissions_for_experiment(self, experiment_id: str) -> List[ExperimentPermission]:
        """
        List all experiment permissions for a given experiment.
        :param experiment_id: The ID of the experiment.
        :return: A list of experiment permissions for the experiment.
        """
        with self._Session() as session:
            rows: List[SqlExperimentPermission] = (
                session.query(SqlExperimentPermission).filter(SqlExperimentPermission.experiment_id == experiment_id).all()
            )
            return [r.to_mlflow_entity() for r in rows]

    def update_permission(self, experiment_id: str, username: str, permission: str) -> ExperimentPermission:
        """
        Update the experiment permission for a given experiment and user.
        :param experiment_id: The ID of the experiment.
        :param username: The username of the user.
        :param permission: The new permission to be granted to the user.
        :return: The updated experiment permission.
        """
        _validate_permission(permission)
        with self._Session() as session:
            perm = self._get_experiment_permission(session, experiment_id, username)
            perm.permission = permission
            session.flush()
            return perm.to_mlflow_entity()

    def revoke_permission(self, experiment_id: str, username: str) -> None:
        """
        Delete the experiment permission for a given experiment and user.
        :param experiment_id: The ID of the experiment.
        :param username: The username of the user.
        """
        with self._Session() as session:
            perm = self._get_experiment_permission(session, experiment_id, username)
            session.delete(perm)
            session.flush()
