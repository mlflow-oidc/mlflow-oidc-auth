from typing import Optional

from pydantic import BaseModel


class CreateAccessTokenRequest(BaseModel):
    """Request model for creating access tokens."""

    username: Optional[str] = None  # Optional, will use authenticated user if not provided
    expiration: Optional[str] = None  # ISO 8601 format string


class CreateUserTokenRequest(BaseModel):
    """Request model for issuing a named access token (issue #189)."""

    name: str  # Unique among the user's tokens
    expiration: str  # ISO 8601; required, at most one year away


class CreateUserRequest(BaseModel):
    """Request model for creating users."""

    username: str
    display_name: str
    is_admin: bool = False
    is_service_account: bool = False
    #: For a service account: ``internal`` (default) — it signs in with access tokens issued for it
    #: only — or the id of the one provider whose tokens it signs in with.
    service_account_source: Optional[str] = None
    #: For an external service account: the provider subject to bind it to now. Without it, the
    #: first token from its provider binds that token's subject.
    subject: Optional[str] = None


class ServiceAccountSourceRequest(BaseModel):
    """How a service account signs in: ``internal`` or a provider id, with an optional subject for a provider."""

    source: str
    subject: Optional[str] = None
