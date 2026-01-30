from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mlflow_oidc_auth.db.models._base import Base
from mlflow_oidc_auth.entities import GatewayEndpointGroupRegexPermission, GatewayEndpointPermission, GatewayEndpointRegexPermission


class SqlGatewayEndpointPermission(Base):
    __tablename__ = "gateway_endpoint_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    endpoint_id: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    __table_args__ = (UniqueConstraint("endpoint_id", "user_id", name="unique_endpoint_user"),)

    def to_mlflow_entity(self):
        return GatewayEndpointPermission(
            endpoint_id=self.endpoint_id,
            user_id=self.user_id,
            permission=self.permission,
        )


class SqlGatewayEndpointGroupPermission(Base):
    __tablename__ = "gateway_endpoint_group_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    endpoint_id: Mapped[str] = mapped_column(String(255), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    __table_args__ = (UniqueConstraint("endpoint_id", "group_id", name="unique_endpoint_group"),)

    def to_mlflow_entity(self):
        return GatewayEndpointGroupRegexPermission(
            endpoint_id=self.endpoint_id,
            group_id=self.group_id,
            permission=self.permission,
        )


class SqlGatewayEndpointRegexPermission(Base):
    __tablename__ = "gateway_endpoint_regex_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    regex: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer(), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    __table_args__ = (UniqueConstraint("regex", "user_id", name="unique_endpoint_user_regex"),)

    def to_mlflow_entity(self):
        return GatewayEndpointRegexPermission(
            id_=self.id,
            regex=self.regex,
            priority=self.priority,
            user_id=self.user_id,
            permission=self.permission,
        )


class SqlGatewayEndpointGroupRegexPermission(Base):
    __tablename__ = "gateway_endpoint_group_regex_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    regex: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer(), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    __table_args__ = (UniqueConstraint("regex", "group_id", name="unique_endpoint_group_regex"),)

    def to_mlflow_entity(self):
        return GatewayEndpointGroupRegexPermission(
            id_=self.id,
            regex=self.regex,
            priority=self.priority,
            group_id=self.group_id,
            permission=self.permission,
        )
