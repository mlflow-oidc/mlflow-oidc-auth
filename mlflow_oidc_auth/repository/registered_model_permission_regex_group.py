"""Registered model group regex permission repository.

Adds extra ``prompt`` parameter to all methods (filters on
``SqlRegisteredModelGroupRegexPermission.prompt``), so every method
is overridden. Also uses ``GroupRepository`` for user-group listing.
"""

from typing import List

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_STATE, RESOURCE_DOES_NOT_EXIST
from sqlalchemy.exc import MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlRegisteredModelGroupRegexPermission
from mlflow_oidc_auth.entities import RegisteredModelGroupRegexPermission
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository._base import BaseGroupRegexPermissionRepository
from mlflow_oidc_auth.repository import GroupRepository
from mlflow_oidc_auth.repository.utils import get_group


class RegisteredModelGroupRegexPermissionRepository(
    BaseGroupRegexPermissionRepository[SqlRegisteredModelGroupRegexPermission, RegisteredModelGroupRegexPermission]
):
    model_class = SqlRegisteredModelGroupRegexPermission

    def __init__(self, session_maker):
        super().__init__(session_maker)
        self._group_repo = GroupRepository(session_maker)

    # -- private helper with prompt filter ------------------------------------

    def _get_registered_model_group_regex_permission(
        self, session: Session, id: int, group_id: int, prompt: bool = False
    ) -> SqlRegisteredModelGroupRegexPermission:
        try:
            return (
                session.query(SqlRegisteredModelGroupRegexPermission)
                .filter(
                    SqlRegisteredModelGroupRegexPermission.id == id,
                    SqlRegisteredModelGroupRegexPermission.group_id == group_id,
                    SqlRegisteredModelGroupRegexPermission.prompt == prompt,
                )
                .one()
            )
        except NoResultFound:
            raise MlflowException(
                f"No model perm for id={id}, group_id={group_id}, prompt={prompt}",
                RESOURCE_DOES_NOT_EXIST,
            )
        except MultipleResultsFound:
            raise MlflowException(
                f"Multiple model perms for id={id}, group_id={group_id}, prompt={prompt}",
                INVALID_STATE,
            )

    # -- All overridden because of extra prompt parameter ---------------------

    def grant(
        self,
        group_name: str,
        regex: str,
        permission: str,
        priority: int = 0,
        prompt: bool = False,
    ) -> RegisteredModelGroupRegexPermission:  # type: ignore[override]
        _validate_permission(permission)
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = SqlRegisteredModelGroupRegexPermission(
                regex=regex,
                priority=priority,
                group_id=group.id,
                permission=permission,
                prompt=prompt,
            )
            session.add(perm)
            session.flush()
            return perm.to_mlflow_entity()

    def get(self, id: int, group_name: str, prompt: bool = False) -> RegisteredModelGroupRegexPermission:  # type: ignore[override]
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = self._get_registered_model_group_regex_permission(session, id, group.id, prompt=prompt)
            return perm.to_mlflow_entity()

    def list_permissions_for_group(self, group_name: str, prompt: bool = False) -> List[RegisteredModelGroupRegexPermission]:  # type: ignore[override]
        with self._Session() as session:
            group = get_group(session, group_name)
            permissions = (
                session.query(SqlRegisteredModelGroupRegexPermission)
                .filter(
                    SqlRegisteredModelGroupRegexPermission.group_id == group.id,
                    SqlRegisteredModelGroupRegexPermission.prompt == prompt,
                )
                .order_by(SqlRegisteredModelGroupRegexPermission.priority)
                .all()
            )
            return [p.to_mlflow_entity() for p in permissions]

    def list_permissions_for_groups(self, group_names: List[str], prompt: bool = False) -> List[RegisteredModelGroupRegexPermission]:
        with self._Session() as session:
            groups = [get_group(session, name) for name in group_names]
            permissions = (
                session.query(SqlRegisteredModelGroupRegexPermission)
                .filter(
                    SqlRegisteredModelGroupRegexPermission.group_id.in_([g.id for g in groups]),
                    SqlRegisteredModelGroupRegexPermission.prompt == prompt,
                )
                .order_by(SqlRegisteredModelGroupRegexPermission.priority)
                .all()
            )
            return [p.to_mlflow_entity() for p in permissions]

    def list_permissions_for_groups_ids(
        self, group_ids: List[int], prompt: bool = False
    ) -> List[RegisteredModelGroupRegexPermission]:  # type: ignore[override]
        with self._Session() as session:
            permissions = (
                session.query(SqlRegisteredModelGroupRegexPermission)
                .filter(
                    SqlRegisteredModelGroupRegexPermission.group_id.in_(group_ids),
                    SqlRegisteredModelGroupRegexPermission.prompt == prompt,
                )
                .order_by(SqlRegisteredModelGroupRegexPermission.priority)
                .all()
            )
            return [p.to_mlflow_entity() for p in permissions]

    def update(  # type: ignore[override]
        self,
        id: int,
        regex: str,
        group_name: str,
        permission: str,
        priority: int = 0,
        prompt: bool = False,
    ) -> RegisteredModelGroupRegexPermission:
        _validate_permission(permission)
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = self._get_registered_model_group_regex_permission(session, id, group.id, prompt=prompt)
            perm.permission = permission
            perm.priority = priority
            perm.prompt = prompt
            perm.regex = regex
            session.flush()
            return perm.to_mlflow_entity()

    def revoke(self, id: int, group_name: str, prompt: bool = False) -> None:  # type: ignore[override]
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = self._get_registered_model_group_regex_permission(session, id, group.id, prompt=prompt)
            session.delete(perm)
            session.flush()
