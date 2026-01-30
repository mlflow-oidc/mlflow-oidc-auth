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
    __table_args__ = (UniqueConstraint("secret_id", "user_id", name="unique_secret_user"),)

    def to_mlflow_entity(self):
        return GatewaySecretPermission(
            secret_id=self.secret_id,
            user_id=self.user_id,
            permission=self.permission,
        )


class SqlGatewaySecretGroupPermission(Base):
    __tablename__ = "gateway_secret_group_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    secret_id: Mapped[str] = mapped_column(String(255), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    __table_args__ = (UniqueConstraint("secret_id", "group_id", name="unique_secret_group"),)

    def to_mlflow_entity(self):
        return GatewaySecretPermission(
            secret_id=self.secret_id,
            group_id=self.group_id,
            permission=self.permission,
        )


class SqlGatewaySecretRegexPermission(Base):
    __tablename__ = "gateway_secret_regex_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    regex: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer(), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    __table_args__ = (UniqueConstraint("regex", "user_id", name="unique_secret_user_regex"),)

    def to_mlflow_entity(self):
        return GatewaySecretRegexPermission(
            id_=self.id,
            regex=self.regex,
            priority=self.priority,
            user_id=self.user_id,
            permission=self.permission,
        )


class SqlGatewaySecretGroupRegexPermission(Base):
    __tablename__ = "gateway_secret_group_regex_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    regex: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer(), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    __table_args__ = (UniqueConstraint("regex", "group_id", name="unique_secret_group_regex"),)

    def to_mlflow_entity(self):
        return GatewaySecretGroupRegexPermission(
            id_=self.id,
            regex=self.regex,
            priority=self.priority,
            group_id=self.group_id,
            permission=self.permission,
        )
