from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mlflow_oidc_auth.db.models._base import Base
from mlflow_oidc_auth.entities import ScorerGroupRegexPermission, ScorerPermission, ScorerRegexPermission


class SqlScorerPermission(Base):
    __tablename__ = "scorer_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(String(255), nullable=False)
    scorer_name: Mapped[str] = mapped_column(String(256), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    __table_args__ = (UniqueConstraint("experiment_id", "scorer_name", "user_id", name="unique_scorer_user"),)

    def to_mlflow_entity(self):
        return ScorerPermission(
            experiment_id=self.experiment_id,
            scorer_name=self.scorer_name,
            user_id=self.user_id,
            permission=self.permission,
        )


class SqlScorerGroupPermission(Base):
    __tablename__ = "scorer_group_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(String(255), nullable=False)
    scorer_name: Mapped[str] = mapped_column(String(256), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    __table_args__ = (UniqueConstraint("experiment_id", "scorer_name", "group_id", name="unique_scorer_group"),)

    def to_mlflow_entity(self):
        return ScorerPermission(
            experiment_id=self.experiment_id,
            scorer_name=self.scorer_name,
            group_id=self.group_id,
            permission=self.permission,
        )


class SqlScorerRegexPermission(Base):
    __tablename__ = "scorer_regex_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    regex: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer(), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    __table_args__ = (UniqueConstraint("regex", "user_id", name="unique_scorer_user_regex"),)

    def to_mlflow_entity(self):
        return ScorerRegexPermission(
            id_=self.id,
            regex=self.regex,
            priority=self.priority,
            user_id=self.user_id,
            permission=self.permission,
        )


class SqlScorerGroupRegexPermission(Base):
    __tablename__ = "scorer_group_regex_permissions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    regex: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer(), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(255))
    __table_args__ = (UniqueConstraint("regex", "group_id", name="unique_scorer_group_regex"),)

    def to_mlflow_entity(self):
        return ScorerGroupRegexPermission(
            id_=self.id,
            regex=self.regex,
            priority=self.priority,
            group_id=self.group_id,
            permission=self.permission,
        )
