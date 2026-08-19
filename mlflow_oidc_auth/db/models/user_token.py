from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mlflow_oidc_auth.db.models._base import Base
from mlflow_oidc_auth.entities.user_token import UserToken

if TYPE_CHECKING:
    from mlflow_oidc_auth.db.models.user import SqlUser


class SqlUserToken(Base):
    __tablename__ = "user_tokens"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(nullable=True)
    user: Mapped["SqlUser"] = relationship("SqlUser", back_populates="tokens")
    __table_args__ = (UniqueConstraint("user_id", "name", name="unique_user_token_name"),)

    def to_mlflow_entity(self):
        return UserToken(
            id_=self.id,
            user_id=self.user_id,
            name=self.name,
            token_hash=self.token_hash,
            created_at=self.created_at,
            expires_at=self.expires_at,
            last_used_at=self.last_used_at,
        )
