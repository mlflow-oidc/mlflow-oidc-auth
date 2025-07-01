from typing import Callable, List

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_STATE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlRegisteredModelPermission
from mlflow_oidc_auth.entities import RegisteredModelPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository.utils import get_user


class RegisteredModelPermissionRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def _get_registered_model_permission(self, session: Session, name: str, user_id: int) -> SqlRegisteredModelPermission:
        """
        Get the registered model permission for a given name and user ID.
        :param session: SQLAlchemy session
        :param name: The name of the registered model.
        :param user_id: The ID of the user.
        :return: The registered model permission if it exists, otherwise raises an exception.
        """
        try:
            return (
                session.query(SqlRegisteredModelPermission)
                .filter(
                    SqlRegisteredModelPermission.name == name,
                    SqlRegisteredModelPermission.user_id == user_id,
                )
                .one()
            )
        except NoResultFound:
            raise MlflowException(
                f"No model perm for name={name}, user_id={user_id}",
                RESOURCE_DOES_NOT_EXIST,
            )
        except MultipleResultsFound:
            raise MlflowException(
                f"Multiple model perms for name={name}, user_id={user_id}",
                INVALID_STATE,
            )

    def create(self, name: str, username: str, permission: str) -> RegisteredModelPermission:
        _validate_permission(permission)
        with self._Session() as session:
            try:
                user = get_user(session, username)
                perm = SqlRegisteredModelPermission(name=name, user_id=user.id, permission=permission)
                session.add(perm)
                session.flush()
                return perm.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(
                    f"Registered‑model perm exists ({name},{username}): {e}",
                    RESOURCE_ALREADY_EXISTS,
                )

    def get(self, name: str, username: str) -> RegisteredModelPermission:
        with self._Session() as session:
            user = get_user(session, username)
            perm = self._get_registered_model_permission(session, name, user.id)
            return perm.to_mlflow_entity()

    def list_for_user(self, username: str) -> List[RegisteredModelPermission]:
        with self._Session() as session:
            user = get_user(session, username)
            rows = session.query(SqlRegisteredModelPermission).filter(SqlRegisteredModelPermission.user_id == user.id).all()
            return [r.to_mlflow_entity() for r in rows]

    def update(self, name: str, username: str, permission: str) -> RegisteredModelPermission:
        _validate_permission(permission)
        with self._Session() as session:
            user = get_user(session, username)
            perm = self._get_registered_model_permission(session, name, user.id)
            perm.permission = permission
            session.flush()
            return perm.to_mlflow_entity()

    def rename(self, old_name: str, new_name: str) -> None:
        with self._Session() as session:
            perms = session.query(SqlRegisteredModelPermission).filter(SqlRegisteredModelPermission.name == old_name).all()
            if not perms:
                raise MlflowException(f"No registered model permissions found for name: {old_name}", RESOURCE_DOES_NOT_EXIST)
            for perm in perms:
                perm.name = new_name
            session.flush()

    def delete(self, name: str, username: str) -> None:
        with self._Session() as session:
            user = get_user(session, username)
            perm = self._get_registered_model_permission(session, name, user.id)
            session.delete(perm)
            session.flush()

    def wipe(self, name: str):
        with self._Session() as session:
            perms = session.query(SqlRegisteredModelPermission).filter(SqlRegisteredModelPermission.name == name).all()
            for p in perms:
                session.delete(p)
            session.flush()
