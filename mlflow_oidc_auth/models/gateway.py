"""Pydantic models for gateway permission APIs."""

from pydantic import BaseModel, Field


class GatewayPermission(BaseModel):
    """Model for creating or updating a gateway permission (endpoint, model definition, or secret)."""

    permission: str = Field(..., description="Permission level for the gateway resource")


class GatewayRegexCreate(BaseModel):
    """Model for creating or updating a regex-based gateway permission."""

    regex: str = Field(..., description="Regex pattern to match gateway resource names")
    priority: int = Field(..., description="Priority of the permission rule")
    permission: str = Field(..., description="Permission level for matching resources")
