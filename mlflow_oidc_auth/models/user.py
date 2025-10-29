from typing import Optional

from pydantic import BaseModel


class CreateAccessTokenRequest(BaseModel):
    """Request model for creating access tokens."""

    username: Optional[str] = None  # Optional, will use authenticated user if not provided
    expiration: Optional[str] = None  # ISO 8601 format string


class CreateUserRequest(BaseModel):
    """Request model for creating users."""

    username: str
    display_name: str
    is_admin: bool = False
    is_service_account: bool = False
