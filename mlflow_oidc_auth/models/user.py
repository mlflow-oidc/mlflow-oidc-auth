from typing import List, Optional

from pydantic import BaseModel, Field

from mlflow_oidc_auth.models._base import ResponseModel


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


# ---------------------------------------------------------------------------------------------
# Response models (#458). The users router returns ``JSONResponse`` objects, so these document
# the bodies it already builds; they list exactly those fields and never anything more.
# ---------------------------------------------------------------------------------------------


class ServiceAccountSourceOption(ResponseModel):
    """A source a service account can sign in through: ``internal`` or an OIDC provider."""

    id: str = Field(..., description="'internal' or a provider id")
    display_name: str = Field(..., description="Label shown in the UI")
    type: str = Field(..., description="'internal' or the provider type")


class AccessTokenRotateResponse(ResponseModel):
    """``PATCH /users/access-token``. The plaintext token is returned only here, once."""

    token: str = Field(..., description="Plaintext access token, shown once")
    expires_at: str = Field(..., description="ISO 8601 expiry")
    message: str = Field(..., description="Human-readable message")


class UserTokenRecord(ResponseModel):
    """One of a user's named access tokens. Never carries the secret or its hash."""

    id: int
    name: str
    token_prefix: Optional[str] = Field(None, description="Non-secret lookup prefix; null for a token from before named tokens")
    created_at: str = Field(..., description="ISO 8601")
    created_by: Optional[str] = None
    expires_at: str = Field(..., description="ISO 8601; a token always expires")
    last_used_at: Optional[str] = Field(None, description="ISO 8601")
    active: bool = Field(..., description="False once the token has expired")


class UserTokenCreatedResponse(UserTokenRecord):
    """A newly issued named token. The plaintext ``token`` is returned only here, once."""

    token: str = Field(..., description="Plaintext access token, shown once")


class UserTokenListResponse(ResponseModel):
    """A user's access tokens."""

    tokens: List[UserTokenRecord]


class DeletedCountResponse(ResponseModel):
    """How many records a delete removed."""

    deleted: int


class RevokedCountResponse(ResponseModel):
    """How many sessions or tokens a revoke removed."""

    revoked: int


class UserDetail(ResponseModel):
    """A user with its lifecycle state (``GET /users/details``, ``PATCH /users/{username}/active``)."""

    username: str
    display_name: str
    is_admin: bool
    is_service_account: bool
    active: bool
    managed_by: str = Field(..., description="'manual', 'scim', 'oidc:<provider-id>' or 'saml:<provider-id>'")
    service_account_source: Optional[str] = Field(None, description="How a service account signs in; null for a person")


class MembershipHandover(ResponseModel):
    """One group membership handed to a new owner."""

    group: str
    from_: Optional[str] = Field(None, alias="from", description="The membership's previous owner")


class UserOwnershipResponse(ResponseModel):
    """``PATCH /users/ownership``: what changed."""

    __absent_fields__ = frozenset({"memberships"})

    username: str
    managed_by: str
    previous: Optional[str] = None
    memberships: Optional[List[MembershipHandover]] = Field(None, description="Present only when memberships were handed over")


class UserSessionRecord(ResponseModel):
    """A live server-side session. Never the full session id: that is a bearer credential."""

    pk: int
    session_id_prefix: str
    provider_id: Optional[str] = None
    created_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    expires_at: Optional[str] = None


class UserSessionListResponse(ResponseModel):
    """A user's live sessions."""

    sessions: List[UserSessionRecord]


class UserIdentity(ResponseModel):
    """A provider identity that resolves to a user."""

    provider_id: str
    subject: str


class ServiceAccountSourceResponse(ResponseModel):
    """``PUT /users/{username}/service-account-source``."""

    username: str
    service_account_source: str
