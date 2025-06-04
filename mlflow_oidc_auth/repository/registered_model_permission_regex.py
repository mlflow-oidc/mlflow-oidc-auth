from typing import Callable, List

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_STATE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlRegisteredModelRegexPermission
from mlflow_oidc_auth.entities import RegisteredModelRegexPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository.utils import get_user, validate_regex


class RegisteredModelPermissionRegexRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def _get_registered_model_regex_permission(self, session: Session, id: int, user_id: int, prompt: bool = False) -> SqlRegisteredModelRegexPermission:
        """
        Get the registered model regex permission for a given regex and user ID.
        :param session: SQLAlchemy session
        :param regex: The regex pattern.
        :param user_id: The ID of the user.
        :param prompt: Whether to include prompt in the filter.
        :return: The registered model regex permission if it exists, otherwise raises an exception.
        """
        try:
            return (
                session.query(SqlRegisteredModelRegexPermission)
                .filter(
                    SqlRegisteredModelRegexPermission.id == id,
                    SqlRegisteredModelRegexPermission.user_id == user_id,
                    SqlRegisteredModelRegexPermission.prompt == prompt,
                )
                .one()
            )
        except NoResultFound:
            raise MlflowException(f"Permission not found for user_id: {user_id} and id: {id}", RESOURCE_DOES_NOT_EXIST)
        except MultipleResultsFound:
            raise MlflowException(f"Multiple Permissions found for user_id: {user_id} and id: {id}", INVALID_STATE)

    def grant(
        self,
        regex: str,
        priority: int,
        permission: str,
        username: str,
        prompt: bool = False,
    ) -> RegisteredModelRegexPermission:
        validate_regex(regex)
        _validate_permission(permission)
        with self._Session() as session:
            try:
                user = get_user(session, username)
                perm = SqlRegisteredModelRegexPermission(
                    regex=regex,
                    priority=priority,
                    user_id=user.id,
                    permission=permission,
                    prompt=prompt,
                )
                session.add(perm)
                session.flush()
                return perm.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(
                    f"Registered model perm exists ({regex},{username}): {e}",
                    RESOURCE_ALREADY_EXISTS,
                )

    def get(self, id: int, username: str, prompt: bool = False) -> RegisteredModelRegexPermission:
        with self._Session() as session:
            user = get_user(session, username)
            perm = self._get_registered_model_regex_permission(session, id, user.id, prompt=prompt)
            return perm.to_mlflow_entity()

    def list_regex_for_user(self, username: str, prompt: bool = False) -> List[RegisteredModelRegexPermission]:
        with self._Session() as session:
            user = get_user(session, username)
            perms = (
                session.query(SqlRegisteredModelRegexPermission)
                .filter(
                    SqlRegisteredModelRegexPermission.user_id == user.id,
                    SqlRegisteredModelRegexPermission.prompt == prompt,
                )
                .order_by(SqlRegisteredModelRegexPermission.priority)
                .all()
            )
            return [p.to_mlflow_entity() for p in perms]

    def update(self, id: int, regex: str, priority: int, permission: str, username: str, prompt: bool = False) -> RegisteredModelRegexPermission:
        validate_regex(regex)
        _validate_permission(permission)
        with self._Session() as session:
            user = get_user(session, username)
            perm = self._get_registered_model_regex_permission(session, id, user.id, prompt=prompt)
            perm.priority = priority
            perm.permission = permission
            session.commit()
            return perm.to_mlflow_entity()

    def revoke(self, id: int, username: str, prompt: bool = False) -> None:
        with self._Session() as session:
            user = get_user(session, username)
            perm = self._get_registered_model_regex_permission(session, id, user.id, prompt=prompt)
            session.delete(perm)
            session.commit()
            return None
