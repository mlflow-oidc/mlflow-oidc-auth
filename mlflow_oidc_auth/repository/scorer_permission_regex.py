from typing import Callable, List

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_STATE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlScorerRegexPermission
from mlflow_oidc_auth.entities import ScorerRegexPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository.utils import get_user, validate_regex


class ScorerPermissionRegexRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def _get(self, session: Session, user_id: int, id: int) -> SqlScorerRegexPermission:
        try:
            return (
                session.query(SqlScorerRegexPermission)
                .filter(
                    SqlScorerRegexPermission.user_id == user_id,
                    SqlScorerRegexPermission.id == id,
                )
                .one()
            )
        except NoResultFound as e:
            raise MlflowException(
                f"Scorer regex permission not found for user_id={user_id}, id={id}",
                RESOURCE_DOES_NOT_EXIST,
            ) from e
        except MultipleResultsFound as e:
            raise MlflowException(
                f"Multiple scorer regex permissions for user_id={user_id}, id={id}",
                INVALID_STATE,
            ) from e

    def grant(self, regex: str, priority: int, permission: str, username: str) -> ScorerRegexPermission:
        validate_regex(regex)
        _validate_permission(permission)
        with self._Session() as session:
            try:
                user = get_user(session, username)
                perm = SqlScorerRegexPermission(regex=regex, priority=priority, user_id=user.id, permission=permission)
                session.add(perm)
                session.flush()
                return perm.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(
                    f"Scorer regex perm exists ({regex},{username}): {e}",
                    RESOURCE_ALREADY_EXISTS,
                ) from e

    def get(self, username: str, id: int) -> ScorerRegexPermission:
        with self._Session() as session:
            user = get_user(session, username)
            perm = self._get(session, user.id, id)
            return perm.to_mlflow_entity()

    def list_regex_for_user(self, username: str) -> List[ScorerRegexPermission]:
        with self._Session() as session:
            user = get_user(session, username)
            rows = session.query(SqlScorerRegexPermission).filter(SqlScorerRegexPermission.user_id == user.id).order_by(SqlScorerRegexPermission.priority).all()
            return [r.to_mlflow_entity() for r in rows]

    def update(self, id: int, regex: str, priority: int, permission: str, username: str) -> ScorerRegexPermission:
        validate_regex(regex)
        _validate_permission(permission)
        with self._Session() as session:
            user = get_user(session, username)
            perm = self._get(session, user.id, id)
            perm.regex = regex
            perm.priority = priority
            perm.permission = permission
            session.flush()
            return perm.to_mlflow_entity()

    def revoke(self, id: int, username: str) -> None:
        with self._Session() as session:
            user = get_user(session, username)
            perm = self._get(session, user.id, id)
            session.delete(perm)
            session.commit()
