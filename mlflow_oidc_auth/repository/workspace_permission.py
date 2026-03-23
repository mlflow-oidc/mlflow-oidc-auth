"""Standalone repository for user-level workspace permissions.

Per decision WSAUTH-B: This is a standalone repository — NOT extending base classes.
Workspace is a tenant boundary, not a resource.
"""

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import (
    RESOURCE_ALREADY_EXISTS,
    RESOURCE_DOES_NOT_EXIST,
)
from sqlalchemy.exc import IntegrityError, NoResultFound

from mlflow_oidc_auth.db.models.workspace import SqlWorkspacePermission
from mlflow_oidc_auth.entities.workspace import WorkspacePermission


class WorkspacePermissionRepository:
    """CRUD operations for user-level workspace permissions."""

    def __init__(self, session_maker):
        self.ManagedSessionMaker = session_maker

    def get(self, workspace: str, user_id: int) -> WorkspacePermission:
        """Get a user's workspace permission.

        Parameters:
            workspace: The workspace name.
            user_id: The user's ID.

        Returns:
            WorkspacePermission entity.

        Raises:
            MlflowException: If the permission does not exist.
        """
        with self.ManagedSessionMaker() as session:
            try:
                perm = (
                    session.query(SqlWorkspacePermission)
                    .filter(
                        SqlWorkspacePermission.workspace == workspace,
                        SqlWorkspacePermission.user_id == user_id,
                    )
                    .one()
                )
                return perm.to_mlflow_entity()
            except NoResultFound:
                raise MlflowException(
                    f"Workspace permission not found for workspace={workspace}, user_id={user_id}",
                    RESOURCE_DOES_NOT_EXIST,
                )

    def create(
        self, workspace: str, user_id: int, permission: str
    ) -> WorkspacePermission:
        """Create a workspace permission for a user.

        Parameters:
            workspace: The workspace name.
            user_id: The user's ID.
            permission: The permission level (e.g., READ, EDIT, MANAGE).

        Returns:
            WorkspacePermission entity.

        Raises:
            MlflowException: If a permission already exists for this workspace+user.
        """
        with self.ManagedSessionMaker() as session:
            try:
                perm = SqlWorkspacePermission(
                    workspace=workspace, user_id=user_id, permission=permission
                )
                session.add(perm)
                session.flush()
                return perm.to_mlflow_entity()
            except IntegrityError:
                raise MlflowException(
                    f"Workspace permission already exists for workspace={workspace}, user_id={user_id}",
                    RESOURCE_ALREADY_EXISTS,
                )

    def update(
        self, workspace: str, user_id: int, permission: str
    ) -> WorkspacePermission:
        """Update a user's workspace permission.

        Parameters:
            workspace: The workspace name.
            user_id: The user's ID.
            permission: The new permission level.

        Returns:
            Updated WorkspacePermission entity.

        Raises:
            MlflowException: If the permission does not exist.
        """
        with self.ManagedSessionMaker() as session:
            try:
                perm = (
                    session.query(SqlWorkspacePermission)
                    .filter(
                        SqlWorkspacePermission.workspace == workspace,
                        SqlWorkspacePermission.user_id == user_id,
                    )
                    .one()
                )
                perm.permission = permission
                session.flush()
                return perm.to_mlflow_entity()
            except NoResultFound:
                raise MlflowException(
                    f"Workspace permission not found for workspace={workspace}, user_id={user_id}",
                    RESOURCE_DOES_NOT_EXIST,
                )

    def delete(self, workspace: str, user_id: int) -> None:
        """Delete a user's workspace permission.

        Parameters:
            workspace: The workspace name.
            user_id: The user's ID.

        Raises:
            MlflowException: If the permission does not exist.
        """
        with self.ManagedSessionMaker() as session:
            try:
                perm = (
                    session.query(SqlWorkspacePermission)
                    .filter(
                        SqlWorkspacePermission.workspace == workspace,
                        SqlWorkspacePermission.user_id == user_id,
                    )
                    .one()
                )
                session.delete(perm)
                session.flush()
            except NoResultFound:
                raise MlflowException(
                    f"Workspace permission not found for workspace={workspace}, user_id={user_id}",
                    RESOURCE_DOES_NOT_EXIST,
                )

    def list_for_user(self, user_id: int) -> list[WorkspacePermission]:
        """List all workspace permissions for a user.

        Parameters:
            user_id: The user's ID.

        Returns:
            List of WorkspacePermission entities.
        """
        with self.ManagedSessionMaker() as session:
            perms = (
                session.query(SqlWorkspacePermission)
                .filter(SqlWorkspacePermission.user_id == user_id)
                .all()
            )
            return [p.to_mlflow_entity() for p in perms]

    def list_for_workspace(self, workspace: str) -> list[WorkspacePermission]:
        """List all user permissions in a workspace.

        Parameters:
            workspace: The workspace name.

        Returns:
            List of WorkspacePermission entities.
        """
        with self.ManagedSessionMaker() as session:
            perms = (
                session.query(SqlWorkspacePermission)
                .filter(SqlWorkspacePermission.workspace == workspace)
                .all()
            )
            return [p.to_mlflow_entity() for p in perms]
