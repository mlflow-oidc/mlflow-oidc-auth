from typing import Callable, List, Optional

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST
from sqlalchemy.orm import Session

from mlflow_oidc_auth.db.models import SqlGroup, SqlScorerGroupPermission
from mlflow_oidc_auth.entities import ScorerPermission
from mlflow_oidc_auth.permissions import _validate_permission, compare_permissions
from mlflow_oidc_auth.repository.utils import get_group, get_user, list_user_groups


class ScorerPermissionGroupRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def _get_group_permission(self, session: Session, experiment_id: str, scorer_name: str, group_name: str) -> Optional[SqlScorerGroupPermission]:
        group = session.query(SqlGroup).filter(SqlGroup.group_name == group_name).one_or_none()
        if group is None:
            return None
        return (
            session.query(SqlScorerGroupPermission)
            .filter(
                SqlScorerGroupPermission.experiment_id == experiment_id,
                SqlScorerGroupPermission.scorer_name == scorer_name,
                SqlScorerGroupPermission.group_id == group.id,
            )
            .one_or_none()
        )

    def _list_user_groups(self, username: str) -> List[str]:
        with self._Session() as session:
            user = get_user(session, username)
            user_groups_ids = list_user_groups(session, user)
            user_groups = session.query(SqlGroup).filter(SqlGroup.id.in_([ug.group_id for ug in user_groups_ids])).all()
            return [ug.group_name for ug in user_groups]

    def grant_group_permission(self, group_name: str, experiment_id: str, scorer_name: str, permission: str) -> ScorerPermission:
        _validate_permission(permission)
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = SqlScorerGroupPermission(
                experiment_id=experiment_id,
                scorer_name=scorer_name,
                group_id=group.id,
                permission=permission,
            )
            session.add(perm)
            session.flush()
            return perm.to_mlflow_entity()

    def list_permissions_for_group(self, group_name: str) -> List[ScorerPermission]:
        with self._Session() as session:
            group = get_group(session, group_name)
            rows = session.query(SqlScorerGroupPermission).filter(SqlScorerGroupPermission.group_id == group.id).all()
            return [r.to_mlflow_entity() for r in rows]

    def list_permissions_for_group_id(self, group_id: int) -> List[ScorerPermission]:
        with self._Session() as session:
            rows = session.query(SqlScorerGroupPermission).filter(SqlScorerGroupPermission.group_id == group_id).all()
            return [r.to_mlflow_entity() for r in rows]

    def list_groups_for_scorer(self, experiment_id: str, scorer_name: str) -> List[tuple[str, str]]:
        """List groups that have explicit permissions for a scorer.

        Returns pairs of (group_name, permission).
        """

        with self._Session() as session:
            rows = (
                session.query(SqlGroup.group_name, SqlScorerGroupPermission.permission)
                .join(SqlScorerGroupPermission, SqlScorerGroupPermission.group_id == SqlGroup.id)
                .filter(SqlScorerGroupPermission.experiment_id == experiment_id)
                .filter(SqlScorerGroupPermission.scorer_name == scorer_name)
                .all()
            )
            return [(str(group_name), str(permission)) for group_name, permission in rows]

    def get_group_permission_for_user_scorer(self, experiment_id: str, scorer_name: str, username: str) -> ScorerPermission:
        with self._Session() as session:
            user_groups = self._list_user_groups(username)
            best: Optional[SqlScorerGroupPermission] = None
            for group_name in user_groups:
                perm = self._get_group_permission(session, experiment_id, scorer_name, group_name)
                if perm is None:
                    continue
                if best is None:
                    best = perm
                    continue
                try:
                    if compare_permissions(str(best.permission), str(perm.permission)):
                        best = perm
                except AttributeError:
                    best = perm

            if best is not None:
                return best.to_mlflow_entity()

            raise MlflowException(
                f"Scorer group permission not found for exp={experiment_id}, scorer={scorer_name}, user={username}",
                RESOURCE_DOES_NOT_EXIST,
            )

    def update_group_permission(self, group_name: str, experiment_id: str, scorer_name: str, permission: str) -> ScorerPermission:
        _validate_permission(permission)
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = (
                session.query(SqlScorerGroupPermission)
                .filter(
                    SqlScorerGroupPermission.experiment_id == experiment_id,
                    SqlScorerGroupPermission.scorer_name == scorer_name,
                    SqlScorerGroupPermission.group_id == group.id,
                )
                .one()
            )
            perm.permission = permission
            session.flush()
            return perm.to_mlflow_entity()

    def revoke_group_permission(self, group_name: str, experiment_id: str, scorer_name: str) -> None:
        with self._Session() as session:
            group = get_group(session, group_name)
            perm = (
                session.query(SqlScorerGroupPermission)
                .filter(
                    SqlScorerGroupPermission.experiment_id == experiment_id,
                    SqlScorerGroupPermission.scorer_name == scorer_name,
                    SqlScorerGroupPermission.group_id == group.id,
                )
                .one()
            )
            session.delete(perm)
            session.flush()
