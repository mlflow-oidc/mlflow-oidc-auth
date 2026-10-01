from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mlflow_oidc_auth.db.models._base import Base
from mlflow_oidc_auth.entities import ExperimentGroupRegexPermission, ExperimentPermission, ExperimentRegexPermission


class SqlExperimentPermission(Base):
    __tablename__ = "experiment_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    __table_args__ = (UniqueConstraint("experiment_id", "user_id", name="unique_experiment_user"),)

    def to_mlflow_entity(self):
        return ExperimentPermission(
            experiment_id=self.experiment_id,
            user_id=self.user_id,
            permission=self.permission,
        )


class SqlExperimentGroupPermission(Base):
    __tablename__ = "experiment_group_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(String(255), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    __table_args__ = (UniqueConstraint("experiment_id", "group_id", name="unique_experiment_group"),)

    def to_mlflow_entity(self):
        return ExperimentPermission(
            experiment_id=self.experiment_id,
            group_id=self.group_id,
            permission=self.permission,
        )


class SqlExperimentRegexPermission(Base):
    __tablename__ = "experiment_regex_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    regex: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer(), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    # The workspace the pattern applies in, or "*" for every workspace (utils/grant_workspace.py).
    workspace: Mapped[str] = mapped_column(String(63), nullable=False, default="*", server_default="*")
    __table_args__ = (UniqueConstraint("regex", "user_id", "workspace", name="uq_experiment_user_regex_ws"),)

    def to_mlflow_entity(self):
        entity = ExperimentRegexPermission(
            id_=self.id,
            regex=self.regex,
            priority=self.priority,
            user_id=self.user_id,
            permission=self.permission,
        )
        entity.workspace = self.workspace
        return entity


class SqlExperimentGroupRegexPermission(Base):
    __tablename__ = "experiment_group_regex_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    regex: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer(), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    # The workspace the pattern applies in, or "*" for every workspace (utils/grant_workspace.py).
    workspace: Mapped[str] = mapped_column(String(63), nullable=False, default="*", server_default="*")
    __table_args__ = (UniqueConstraint("regex", "group_id", "workspace", name="uq_experiment_group_regex_ws"),)

    def to_mlflow_entity(self):
        entity = ExperimentGroupRegexPermission(
            id_=self.id,
            regex=self.regex,
            priority=self.priority,
            group_id=self.group_id,
            permission=self.permission,
        )
        entity.workspace = self.workspace
        return entity
