from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mlflow_oidc_auth.db.models._base import Base
from mlflow_oidc_auth.entities import GatewaySecretPermission, GatewaySecretGroupRegexPermission, GatewaySecretRegexPermission


# Secret permissions
class SqlGatewaySecretPermission(Base):
    __tablename__ = "gateway_secret_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    secret_id: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    # The workspace of the resource this grant names (see utils/grant_workspace.py). NULL only for
    # a grant from before the column existed, until the startup backfill assigns one.
    workspace: Mapped[Optional[str]] = mapped_column(String(63), nullable=True)
    __table_args__ = (UniqueConstraint("workspace", "secret_id", "user_id", name="uq_gw_secret_perm_workspace_user"),)

    def to_mlflow_entity(self):
        return GatewaySecretPermission(
            secret_id=self.secret_id,
            user_id=self.user_id,
            permission=self.permission,
            workspace=self.workspace,
        )


class SqlGatewaySecretGroupPermission(Base):
    __tablename__ = "gateway_secret_group_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    secret_id: Mapped[str] = mapped_column(String(255), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    # The workspace of the resource this grant names (see utils/grant_workspace.py). NULL only for
    # a grant from before the column existed, until the startup backfill assigns one.
    workspace: Mapped[Optional[str]] = mapped_column(String(63), nullable=True)
    __table_args__ = (UniqueConstraint("workspace", "secret_id", "group_id", name="uq_gw_secret_group_perm_workspace_group"),)

    def to_mlflow_entity(self):
        return GatewaySecretPermission(
            secret_id=self.secret_id,
            group_id=self.group_id,
            permission=self.permission,
            workspace=self.workspace,
        )


class SqlGatewaySecretRegexPermission(Base):
    __tablename__ = "gateway_secret_regex_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    regex: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer(), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    # The workspace the pattern applies in, or "*" for every workspace (utils/grant_workspace.py).
    workspace: Mapped[str] = mapped_column(String(63), nullable=False, default="*", server_default="*")
    __table_args__ = (UniqueConstraint("regex", "user_id", "workspace", name="uq_secret_user_regex_ws"),)

    def to_mlflow_entity(self):
        entity = GatewaySecretRegexPermission(
            id_=self.id,
            regex=self.regex,
            priority=self.priority,
            user_id=self.user_id,
            permission=self.permission,
        )
        entity.workspace = self.workspace
        return entity


class SqlGatewaySecretGroupRegexPermission(Base):
    __tablename__ = "gateway_secret_group_regex_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    regex: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer(), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    # The workspace the pattern applies in, or "*" for every workspace (utils/grant_workspace.py).
    workspace: Mapped[str] = mapped_column(String(63), nullable=False, default="*", server_default="*")
    __table_args__ = (UniqueConstraint("regex", "group_id", "workspace", name="uq_secret_group_regex_ws"),)

    def to_mlflow_entity(self):
        entity = GatewaySecretGroupRegexPermission(
            id_=self.id,
            regex=self.regex,
            priority=self.priority,
            group_id=self.group_id,
            permission=self.permission,
        )
        entity.workspace = self.workspace
        return entity
