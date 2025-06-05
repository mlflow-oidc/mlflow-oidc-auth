from typing import Callable, List

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_STATE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlExperimentRegexPermission
from mlflow_oidc_auth.entities import ExperimentRegexPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository.utils import get_user, validate_regex


class ExperimentPermissionRegexRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def _get_experiment_regex_permission(self, session: Session, user_id: int, id: int) -> SqlExperimentRegexPermission:
        """
        Get the experiment regex permission for a given regex and user ID.
        :param session: SQLAlchemy session
        :param regex: The regex pattern.
        :param user_id: The ID of the user.
        :return: The experiment regex permission if it exists, otherwise raises an exception.
        """
        try:
            return (
                session.query(SqlExperimentRegexPermission)
                .filter(
                    SqlExperimentRegexPermission.user_id == user_id,
                    SqlExperimentRegexPermission.id == id,
                )
                .one()
            )
        except NoResultFound:
            raise MlflowException(f"Permission not found for user_id: {user_id}, and id: {id}", RESOURCE_DOES_NOT_EXIST)
        except MultipleResultsFound:
            raise MlflowException(f"Multiple Permissions found for user_id: {user_id}, and id: {id}", INVALID_STATE)

    def grant(
        self,
        regex: str,
        priority: int,
        permission: str,
        username: str,
    ) -> ExperimentRegexPermission:
        validate_regex(regex)
        _validate_permission(permission)
        with self._Session() as session:
            try:
                user = get_user(session, username)
                perm = SqlExperimentRegexPermission(
                    regex=regex,
                    priority=priority,
                    user_id=user.id,
                    permission=permission,
                )
                session.add(perm)
                session.flush()
                return perm.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(
                    f"Experiment perm exists ({regex},{username}): {e}",
                    RESOURCE_ALREADY_EXISTS,
                )

    def get(self, username: str, id: int) -> ExperimentRegexPermission:
        with self._Session() as session:
            user = get_user(session, username)
            perm = self._get_experiment_regex_permission(session=session, user_id=user.id, id=id)
            return perm.to_mlflow_entity()

    def list(self) -> List[ExperimentRegexPermission]:
        with self._Session() as session:
            rows = session.query(SqlExperimentRegexPermission).all()
            return [r.to_mlflow_entity() for r in rows]

    def list_regex_for_user(self, username: str) -> List[ExperimentRegexPermission]:
        with self._Session() as session:
            user = get_user(session, username)
            rows = (
                session.query(SqlExperimentRegexPermission)
                .filter(SqlExperimentRegexPermission.user_id == user.id)
                .order_by(SqlExperimentRegexPermission.priority)
                .all()
            )
            return [r.to_mlflow_entity() for r in rows]

    def update(self, regex: str, priority: int, permission: str, username: str, id: int) -> ExperimentRegexPermission:
        validate_regex(regex)
        _validate_permission(permission)
        with self._Session() as session:
            user = get_user(session, username)
            perm = self._get_experiment_regex_permission(session, user.id, id)
            perm.priority = priority
            perm.permission = permission
            perm.regex = regex
            session.flush()
            return perm.to_mlflow_entity()

    def revoke(self, username: str, id: int) -> None:
        with self._Session() as session:
            user = get_user(session, username)
            perm = self._get_experiment_regex_permission(session=session, user_id=user.id, id=id)
            session.delete(perm)
            session.commit()
            return None
