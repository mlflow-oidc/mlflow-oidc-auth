from typing import List, Optional

from pydantic import BaseModel, Field


class CreateAccessTokenRequest(BaseModel):
    """Request model for creating access tokens (legacy single-token API)."""

    username: Optional[str] = None  # Optional, will use authenticated user if not provided
    expiration: Optional[str] = None  # ISO 8601 format string


class CreateUserRequest(BaseModel):
    """Request model for creating users."""

    username: str
    display_name: str
    is_admin: bool = False
    is_service_account: bool = False


class CreateUserTokenRequest(BaseModel):
    """Request model for creating a named user token."""

    name: str = Field(..., min_length=1, max_length=255, description="Descriptive name for the token")
    expiration: str = Field(..., description="Expiration date in ISO 8601 format (required, max 1 year)")


class UserTokenResponse(BaseModel):
    """Response model for a user token (without the actual token value)."""

    id: int
    name: str
    created_at: str  # ISO 8601
    expires_at: Optional[str] = None  # ISO 8601
    last_used_at: Optional[str] = None  # ISO 8601


class UserTokenCreatedResponse(BaseModel):
    """Response model when a new token is created (includes the token value once)."""

    id: int
    name: str
    token: str  # The actual token value - only shown once at creation time
    created_at: str  # ISO 8601
    expires_at: Optional[str] = None  # ISO 8601
    message: str


class UserTokenListResponse(BaseModel):
    """Response model for listing user tokens."""

    tokens: List[UserTokenResponse]
