"""MCP server permission repositories (user and group grants).

MLflow keeps MCP servers unique per ``(workspace, name)``, so both repositories are
``workspace_scoped``: every lookup matches only the request's grant workspace and every new grant
records it (see ``_GrantWorkspaceScope``).
"""

from typing import List, Tuple

from mlflow_oidc_auth.db.models import SqlMCPServerGroupPermission, SqlMCPServerPermission, SqlUser
from mlflow_oidc_auth.entities import MCPServerPermission
from mlflow_oidc_auth.repository._base import BaseGroupPermissionRepository, BaseUserPermissionRepository


class MCPServerPermissionRepository(BaseUserPermissionRepository[SqlMCPServerPermission, MCPServerPermission]):
    model_class = SqlMCPServerPermission
    resource_id_attr = "name"
    workspace_scoped = True  # MLflow keeps MCP servers unique per (workspace, name)

    def list_users_for_resource(self, name: str) -> List[Tuple[str, str, bool]]:
        """Users with a grant on ``name`` in the request's grant workspace.

        Parameters:
            name: The MCP server name.

        Returns:
            ``(username, permission, is_service_account)`` per grant, ordered by username.
        """
        with self._Session() as session:
            rows = (
                session.query(SqlUser.username, self.model_class.permission, SqlUser.is_service_account)
                .join(self.model_class, self.model_class.user_id == SqlUser.id)
                .filter(self._resource_is(name))
                .order_by(SqlUser.username)
                .all()
            )
            return [(str(username), str(permission), bool(is_sa)) for username, permission, is_sa in rows]


class MCPServerGroupPermissionRepository(BaseGroupPermissionRepository[SqlMCPServerGroupPermission, MCPServerPermission]):
    model_class = SqlMCPServerGroupPermission
    resource_id_attr = "name"
    workspace_scoped = True  # MLflow keeps MCP servers unique per (workspace, name)

    def get_group_permission_for_group(self, name: str, group_name: str) -> MCPServerPermission:
        """The grant ``group_name`` holds on ``name`` in the request's grant workspace.

        Raises:
            MlflowException: ``RESOURCE_DOES_NOT_EXIST`` when there is none.
        """
        with self._Session() as session:
            return self._get_group_permission(session, name, group_name).to_mlflow_entity()
