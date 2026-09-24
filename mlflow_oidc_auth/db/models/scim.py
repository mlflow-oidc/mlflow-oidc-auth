"""SCIM bearer tokens (issue #321).

A SCIM client — Entra, Okta, a script — authenticates with a long-lived bearer token that an
administrator issues and hands to the directory. It is not a user credential: it identifies a
*directory*, never resolves to a ``users`` row, and is accepted on ``/scim/v2`` only.

Only a hash is stored. ``token_prefix`` is the random, non-secret handle embedded in the token
(``scim_<prefix>_<secret>``); it is what lets ``authenticate`` find the one row to verify
instead of hashing against every token, and what an administrator sees to tell tokens apart.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from mlflow_oidc_auth.db.models._base import Base


class SqlScimToken(Base):
    """One issued SCIM token. Rows are revoked, never deleted, so the audit trail keeps a name."""

    __tablename__ = "scim_tokens"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, server_default=func.now())
    created_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(), nullable=True)
    __table_args__ = (
        UniqueConstraint("name", name="uq_scim_tokens_name"),
        Index("ix_scim_tokens_token_prefix", "token_prefix", unique=True),
    )


class SqlScimActivity(Base):
    """One request to ``/scim/v2``, as the admin UI's provisioning status sees it (issue #325).

    What is recorded is deliberately narrow: the route *template* (``/Users/{user_id}``), never
    the concrete path, with the SCIM ``id`` in ``resource_id``; the status, an outcome class and
    the short SCIM error ``detail``. Never a token, never a header, never a request or response
    body. ``token_id`` is not a foreign key: a token row is never deleted, but the activity must
    also outlive a table rebuild, and ``token_name`` keeps the row readable on its own.
    """

    __tablename__ = "scim_activity"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    token_id: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True)
    token_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[int] = mapped_column(Integer(), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True)
    __table_args__ = (
        Index("ix_scim_activity_at", "at"),
        Index("ix_scim_activity_token_id_at", "token_id", "at"),
    )
