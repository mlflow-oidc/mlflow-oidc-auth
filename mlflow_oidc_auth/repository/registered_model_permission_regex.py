from typing import List, Callable

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_ALREADY_EXISTS
from sqlalchemy.exc import IntegrityError

from mlflow_oidc_auth.db.models import SqlRegisteredModelRegexPermission
from mlflow_oidc_auth.entities import RegisteredModelRegexPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository.utils import get_one_or_raise, get_user, validate_regex
from sqlalchemy.orm import Session


class RegisteredModelPermissionRegexRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

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

    def get(self, regex: str, username: str, prompt: bool = False) -> RegisteredModelRegexPermission:
        with self._Session() as session:
            user = get_user(session, username)
            perm: SqlRegisteredModelRegexPermission = get_one_or_raise(
                session,
                SqlRegisteredModelRegexPermission,
                SqlRegisteredModelRegexPermission.regex == regex,
                SqlRegisteredModelRegexPermission.user_id == user.id,
                SqlRegisteredModelRegexPermission.prompt == prompt,
                not_found_msg=f"No registered model perm for regex={regex}, user={username}",
                multiple_msg=f"Multiple registered model perms for regex={regex}, user={username}",
            )
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

    def update(
        self, regex: str, priority: int, permission: str, username: str, prompt: bool = False
    ) -> RegisteredModelRegexPermission:
        validate_regex(regex)
        _validate_permission(permission)
        with self._Session() as session:
            user = get_user(session, username)
            perm: SqlRegisteredModelRegexPermission = get_one_or_raise(
                session,
                SqlRegisteredModelRegexPermission,
                SqlRegisteredModelRegexPermission.regex == regex,
                SqlRegisteredModelRegexPermission.user_id == user.id,
                SqlRegisteredModelRegexPermission.prompt == prompt,
                not_found_msg=f"No registered model perm to update for regex={regex}, user={username}",
                multiple_msg=f"Multiple registered model perms for regex={regex}, user={username}",
            )
            perm.priority = priority
            perm.permission = permission
            session.commit()
            return perm.to_mlflow_entity()

    def revoke(self, regex: str, username: str, prompt: bool = False) -> None:
        with self._Session() as session:
            user = get_user(session, username)
            perm = get_one_or_raise(
                session,
                SqlRegisteredModelRegexPermission,
                SqlRegisteredModelRegexPermission.regex == regex,
                SqlRegisteredModelRegexPermission.user_id == user.id,
                SqlRegisteredModelRegexPermission.prompt == prompt,
                not_found_msg=f"No registered model perm to delete for regex={regex}, user={username}",
                multiple_msg=f"Multiple registered model perms for regex={regex}, user={username}",
            )
            session.delete(perm)
            session.commit()
            return None
