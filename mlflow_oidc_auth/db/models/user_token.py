"""Named API access tokens, many per user (issue #189).

A user authenticates to the API with HTTP basic auth: their username and one of their tokens.
Each token has a name the user chose, a mandatory expiry and a ``last_used_at`` an operator can
read to tell a live credential from a forgotten one.

Only a hash is stored. ``token_prefix`` is the random, non-secret handle embedded in the token
(``mlf_<prefix>_<secret>``): it lets authentication fetch the one candidate row by index and
verify a single hash, instead of hashing the presented value against every token the user holds.
It is NULL only for a secret carried over from ``users.password_hash`` by the migration that
introduced this table; such a secret has no prefix, and a user holds at most one.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mlflow_oidc_auth.db.models._base import Base


class SqlUserToken(Base):
    """One access token of one user. Deleted, not revoked: a deleted token is gone."""

    __tablename__ = "user_tokens"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    token_prefix: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(), nullable=True)
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_tokens_user_id_name"),
        Index("ix_user_tokens_token_prefix", "token_prefix", unique=True),
    )
