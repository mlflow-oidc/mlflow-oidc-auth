from typing import List, Callable

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_ALREADY_EXISTS
from sqlalchemy.exc import IntegrityError

from mlflow_oidc_auth.db.models import SqlExperimentRegexPermission, SqlUser
from mlflow_oidc_auth.entities import ExperimentRegexPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository.utils import get_one_or_raise, get_user, validate_regex
from sqlalchemy.orm import Session


class ExperimentPermissionRegexRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

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

    def get(self, regex: str, username: str) -> ExperimentRegexPermission:
        with self._Session() as session:
            row: SqlExperimentRegexPermission = get_one_or_raise(
                session,
                SqlExperimentRegexPermission,
                SqlExperimentRegexPermission.regex == regex,
                SqlExperimentRegexPermission.user_id == session.query(SqlUser.id).filter(SqlUser.username == username),
                not_found_msg=f"No experiment perm for regex={regex}, user={username}",
                multiple_msg=f"Multiple experiment perms for regex={regex}, user={username}",
            )
            return row.to_mlflow_entity()

    def list(self) -> List[ExperimentRegexPermission]:
        with self._Session() as session:
            rows = session.query(SqlExperimentRegexPermission).all()
            return [r.to_mlflow_entity() for r in rows]

    def list_permissions_for_user(self, username: str) -> List[ExperimentRegexPermission]:
        with self._Session() as session:
            user = get_user(session, username)
            rows = session.query(SqlExperimentRegexPermission).filter(SqlExperimentRegexPermission.user_id == user.id).all()
            return [r.to_mlflow_entity() for r in rows]

    def update(self, regex: str, priority: int, permission: str, username: str) -> ExperimentRegexPermission:
        validate_regex(regex)
        _validate_permission(permission)
        with self._Session() as session:
            perm: SqlExperimentRegexPermission = get_one_or_raise(
                session,
                SqlExperimentRegexPermission,
                SqlExperimentRegexPermission.regex == regex,
                SqlExperimentRegexPermission.user_id == session.query(SqlUser.id).filter(SqlUser.username == username),
                not_found_msg=f"No perm to update for regex={regex}, user={username}",
                multiple_msg=f"Multiple perms for regex={regex}, user={username}",
            )
            perm.priority = priority
            perm.permission = permission
            session.flush()
            return perm.to_mlflow_entity()

    def revoke(self, regex: str, username: str) -> None:
        validate_regex(regex)
        with self._Session() as session:
            perm: SqlExperimentRegexPermission = get_one_or_raise(
                session,
                SqlExperimentRegexPermission,
                SqlExperimentRegexPermission.regex == regex,
                SqlExperimentRegexPermission.user_id == session.query(SqlUser.id).filter(SqlUser.username == username),
                not_found_msg=f"No perm to delete for regex={regex}, user={username}",
                multiple_msg=f"Multiple perms for regex={regex}, user={username}",
            )
            session.delete(perm)
            session.commit()
            return None
