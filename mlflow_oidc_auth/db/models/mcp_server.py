from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mlflow_oidc_auth.db.models._base import Base
from mlflow_oidc_auth.entities import MCPServerPermission

# Grants on MLflow's MCP server registry (names are String(256), as in MLflow's mcp_servers table).
# MLflow keeps MCP servers unique per (workspace, name), so
# every grant records the workspace of the server it names (see utils/grant_workspace.py). There
# are no regex tables: MCP server grants are resolved from user and group grants only, then the
# workspace permission.


class SqlMCPServerPermission(Base):
    __tablename__ = "mcp_server_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    # Nullable like the other workspace-scoped grant tables, so the shared backfill and cleanup code
    # treats every table alike; this plugin always writes it.
    workspace: Mapped[Optional[str]] = mapped_column(String(63), nullable=True)
    __table_args__ = (UniqueConstraint("workspace", "name", "user_id", name="uq_mcp_server_perm_workspace_name_user"),)

    def to_mlflow_entity(self):
        return MCPServerPermission(name=self.name, user_id=self.user_id, permission=self.permission, workspace=self.workspace)


class SqlMCPServerGroupPermission(Base):
    __tablename__ = "mcp_server_group_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    workspace: Mapped[Optional[str]] = mapped_column(String(63), nullable=True)
    __table_args__ = (UniqueConstraint("workspace", "name", "group_id", name="uq_mcp_server_group_perm_workspace_name_group"),)

    def to_mlflow_entity(self):
        return MCPServerPermission(name=self.name, group_id=self.group_id, permission=self.permission, workspace=self.workspace)
