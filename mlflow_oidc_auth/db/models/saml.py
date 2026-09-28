"""Consumed SAML assertions (issue #328).

A SAML Response is a bearer credential for as long as its assertion is valid: whoever holds the
POST body can present it again. Recording each assertion ``ID`` as it is accepted, under a unique
constraint, is what makes the second presentation fail. Rows are needed only until the assertion
could no longer pass validation anyway (``not_on_or_after``), then swept.
"""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from mlflow_oidc_auth.db.models._base import Base


class SqlSamlAssertion(Base):
    """One accepted assertion, kept until it expires so it cannot be accepted twice."""

    __tablename__ = "saml_assertions"
    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    assertion_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(255), nullable=False)
    not_on_or_after: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, server_default=func.now())
    __table_args__ = (
        Index("ix_saml_assertions_assertion_id", "assertion_id", unique=True),
        Index("ix_saml_assertions_not_on_or_after", "not_on_or_after"),
    )
