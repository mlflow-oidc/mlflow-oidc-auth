"""Phase 0 identity and session tables (issue #333).

Schema only. Nothing reads or writes these yet: identity resolution is #309 and session
handling is #310. They land together so the Alembic chain keeps a single head while those two
proceed in parallel.

Deliberately no ``to_mlflow_entity`` on any of them — an entity is part of a public surface, and
these have no consumer to shape one for. The issues that give them behaviour will add what they
need.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from mlflow_oidc_auth.db.models._base import Base


class SqlUserIdentity(Base):
    """One external identity — a ``(provider, subject)`` pair — bound to a local user.

    A user may hold several: the same person arriving through two providers resolves to one
    ``users`` row. ``(provider_id, subject)`` is unique, so an identity can never be claimed by
    two accounts.
    """

    __tablename__ = "user_identities"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, server_default=func.now())
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(), nullable=True)
    __table_args__ = (
        UniqueConstraint("provider_id", "subject", name="uq_user_identities_provider_subject"),
        Index("ix_user_identities_user_id", "user_id"),
    )


class SqlAuthSession(Base):
    """A server-side session, so that revocation can be real rather than advisory.

    ``session_id`` is an opaque 256-bit value chosen by the application; the column is sized for
    either common encoding. ``encrypted_tokens`` holds provider token material that the
    application encrypts before it ever reaches this column.
    """

    __tablename__ = "auth_sessions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    provider_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, server_default=func.now())
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(), nullable=True)
    encrypted_tokens: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    __table_args__ = (
        Index("ix_auth_sessions_session_id", "session_id", unique=True),
        Index("ix_auth_sessions_user_id", "user_id"),
        Index("ix_auth_sessions_expires_at", "expires_at"),
    )


class SqlAuthState(Base):
    """In-flight authorization state: the CSRF ``state``, its ``nonce`` and the PKCE verifier.

    Rows are short-lived and swept by ``expires_at``, which is indexed for that reason. Holding
    the verifier server-side is what lets PKCE and the RFC 9207 mix-up defence be enforced
    rather than trusted (#312, #316).
    """

    __tablename__ = "auth_state"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    state: Mapped[str] = mapped_column(String(255), nullable=False)
    nonce: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    code_verifier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    provider_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    relay_state: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    __table_args__ = (
        Index("ix_auth_state_state", "state", unique=True),
        Index("ix_auth_state_expires_at", "expires_at"),
    )
