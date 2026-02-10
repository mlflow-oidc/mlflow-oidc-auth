from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mlflow_oidc_auth.db.models._base import Base
from mlflow_oidc_auth.entities import GatewayModelDefinitionGroupRegexPermission, GatewayModelDefinitionPermission, GatewayModelDefinitionRegexPermission


class SqlGatewayModelDefinitionPermission(Base):
    __tablename__ = "gateway_model_definition_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    model_definition_id: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    __table_args__ = (UniqueConstraint("model_definition_id", "user_id", name="unique_model_def_user"),)

    def to_mlflow_entity(self):
        return GatewayModelDefinitionPermission(
            model_definition_id=self.model_definition_id,
            user_id=self.user_id,
            permission=self.permission,
        )


class SqlGatewayModelDefinitionGroupPermission(Base):
    __tablename__ = "gateway_model_definition_group_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    model_definition_id: Mapped[str] = mapped_column(String(255), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    __table_args__ = (UniqueConstraint("model_definition_id", "group_id", name="unique_model_def_group"),)

    def to_mlflow_entity(self):
        return GatewayModelDefinitionPermission(
            model_definition_id=self.model_definition_id,
            group_id=self.group_id,
            permission=self.permission,
        )


class SqlGatewayModelDefinitionRegexPermission(Base):
    __tablename__ = "gateway_model_definition_regex_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    regex: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer(), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    __table_args__ = (UniqueConstraint("regex", "user_id", name="unique_model_def_user_regex"),)

    def to_mlflow_entity(self):
        return GatewayModelDefinitionRegexPermission(
            id_=self.id,
            regex=self.regex,
            priority=self.priority,
            user_id=self.user_id,
            permission=self.permission,
        )


class SqlGatewayModelDefinitionGroupRegexPermission(Base):
    __tablename__ = "gateway_model_definition_group_regex_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    regex: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer(), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    __table_args__ = (UniqueConstraint("regex", "group_id", name="unique_model_def_group_regex"),)

    def to_mlflow_entity(self):
        return GatewayModelDefinitionGroupRegexPermission(
            id_=self.id,
            regex=self.regex,
            priority=self.priority,
            group_id=self.group_id,
            permission=self.permission,
        )
