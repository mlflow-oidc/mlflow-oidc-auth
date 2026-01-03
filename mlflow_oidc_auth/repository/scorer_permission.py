from typing import Callable, List

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_STATE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlScorerPermission, SqlUser
from mlflow_oidc_auth.entities import ScorerPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository.utils import get_user


class ScorerPermissionRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def _get_permission(self, session: Session, experiment_id: str, scorer_name: str, username: str) -> SqlScorerPermission:
        try:
            return (
                session.query(SqlScorerPermission)
                .join(SqlUser, SqlScorerPermission.user_id == SqlUser.id)
                .filter(
                    SqlScorerPermission.experiment_id == experiment_id,
                    SqlScorerPermission.scorer_name == scorer_name,
                    SqlUser.username == username,
                )
                .one()
            )
        except NoResultFound as e:
            raise MlflowException(
                f"No scorer permission for exp={experiment_id}, scorer={scorer_name}, user={username}",
                RESOURCE_DOES_NOT_EXIST,
            ) from e
        except MultipleResultsFound as e:
            raise MlflowException(
                f"Multiple scorer perms for exp={experiment_id}, scorer={scorer_name}, user={username}",
                INVALID_STATE,
            ) from e

    def grant_permission(self, experiment_id: str, scorer_name: str, username: str, permission: str) -> ScorerPermission:
        _validate_permission(permission)
        with self._Session() as session:
            try:
                user = get_user(session, username)
                perm = SqlScorerPermission(
                    experiment_id=experiment_id,
                    scorer_name=scorer_name,
                    user_id=user.id,
                    permission=permission,
                )
                session.add(perm)
                session.flush()
                return perm.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(
                    f"Scorer permission already exists ({experiment_id}, {scorer_name}, {username}): {e}",
                    RESOURCE_ALREADY_EXISTS,
                ) from e

    def get_permission(self, experiment_id: str, scorer_name: str, username: str) -> ScorerPermission:
        with self._Session() as session:
            perm = self._get_permission(session, experiment_id, scorer_name, username)
            return perm.to_mlflow_entity()

    def list_permissions_for_user(self, username: str) -> List[ScorerPermission]:
        with self._Session() as session:
            user = get_user(session, username)
            rows = session.query(SqlScorerPermission).filter(SqlScorerPermission.user_id == user.id).all()
            return [r.to_mlflow_entity() for r in rows]

    def update_permission(self, experiment_id: str, scorer_name: str, username: str, permission: str) -> ScorerPermission:
        _validate_permission(permission)
        with self._Session() as session:
            perm = self._get_permission(session, experiment_id, scorer_name, username)
            perm.permission = permission
            session.flush()
            return perm.to_mlflow_entity()

    def revoke_permission(self, experiment_id: str, scorer_name: str, username: str) -> None:
        with self._Session() as session:
            perm = self._get_permission(session, experiment_id, scorer_name, username)
            session.delete(perm)
            session.flush()
