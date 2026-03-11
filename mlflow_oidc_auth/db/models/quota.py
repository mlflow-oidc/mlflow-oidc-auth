from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from mlflow_oidc_auth.db.models._base import Base


class SqlUserQuota(Base):
    __tablename__ = "user_quotas"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    quota_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    used_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    soft_cap_fraction: Mapped[float] = mapped_column(Float, nullable=False, default=0.9)
    last_reconciled_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    soft_notified_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    hard_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
