from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mlflow_oidc_auth.db.models._base import Base
from mlflow_oidc_auth.entities import SkillPermission

# Grants on MLflow's skill registry. ``name`` holds the grant key: the bare skill name, or
# ``@<organization>/<name>`` (MLflow's organization is String(64) and its name String(128), so the
# key fits String(256)). MLflow keeps skills unique per (workspace, organization, name), so every
# grant records the workspace of the skill it names (see utils/grant_workspace.py). There are no
# regex tables: skill grants are resolved from user and group grants only, then the workspace
# permission.


class SqlSkillPermission(Base):
    __tablename__ = "skill_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    # Nullable like the other workspace-scoped grant tables, so the shared backfill and cleanup code
    # treats every table alike; this plugin always writes it.
    workspace: Mapped[Optional[str]] = mapped_column(String(63), nullable=True)
    __table_args__ = (UniqueConstraint("workspace", "name", "user_id", name="uq_skill_perm_workspace_name_user"),)

    def to_mlflow_entity(self):
        return SkillPermission(name=self.name, user_id=self.user_id, permission=self.permission, workspace=self.workspace)


class SqlSkillGroupPermission(Base):
    __tablename__ = "skill_group_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    workspace: Mapped[Optional[str]] = mapped_column(String(63), nullable=True)
    __table_args__ = (UniqueConstraint("workspace", "name", "group_id", name="uq_skill_group_perm_workspace_name_group"),)

    def to_mlflow_entity(self):
        return SkillPermission(name=self.name, group_id=self.group_id, permission=self.permission, workspace=self.workspace)
