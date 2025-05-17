from typing import List, Callable
from sqlalchemy.orm import Session

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_ALREADY_EXISTS
from sqlalchemy.exc import IntegrityError

from mlflow_oidc_auth.db.models import SqlRegisteredModelPermission, SqlUser
from mlflow_oidc_auth.entities import RegisteredModelPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository.utils import get_one_or_raise, get_user


class RegisteredModelPermissionRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

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
            row = get_one_or_raise(
                session,
                SqlRegisteredModelPermission,
                SqlRegisteredModelPermission.name == name,
                SqlRegisteredModelPermission.user_id
                == session.query(SqlUser.id).filter(SqlUser.username == username).scalar_subquery(),
                not_found_msg=f"No model perm for name={name}, user={username}",
                multiple_msg=f"Multiple model perms for name={name}, user={username}",
            )
            return row.to_mlflow_entity()

    def list_for_user(self, username: str) -> List[RegisteredModelPermission]:
        with self._Session() as session:
            user = get_user(session, username)
            rows = session.query(SqlRegisteredModelPermission).filter(SqlRegisteredModelPermission.user_id == user.id).all()
            return [r.to_mlflow_entity() for r in rows]

    def update(self, name: str, username: str, permission: str) -> RegisteredModelPermission:
        _validate_permission(permission)
        with self._Session() as session:
            perm = get_one_or_raise(
                session,
                SqlRegisteredModelPermission,
                SqlRegisteredModelPermission.name == name,
                SqlRegisteredModelPermission.user_id
                == session.query(SqlUser.id).filter(SqlUser.username == username).scalar_subquery(),
                not_found_msg=f"No perm to update for name={name}, user={username}",
                multiple_msg=f"Multiple perms for name={name}, user={username}",
            )
            perm.permission = permission
            session.flush()
            return perm.to_mlflow_entity()

    def delete(self, name: str, username: str) -> None:
        with self._Session() as session:
            perm = get_one_or_raise(
                session,
                SqlRegisteredModelPermission,
                SqlRegisteredModelPermission.name == name,
                SqlRegisteredModelPermission.user_id
                == session.query(SqlUser.id).filter(SqlUser.username == username).scalar_subquery(),
                not_found_msg=f"No perm to delete for name={name}, user={username}",
                multiple_msg=f"Multiple perms for name={name}, user={username}",
            )
            session.delete(perm)
            session.flush()

    def wipe(self, name: str):
        with self._Session() as session:
            perms = session.query(SqlRegisteredModelPermission).filter(SqlRegisteredModelPermission.name == name).all()
            for p in perms:
                session.delete(p)
            session.flush()
