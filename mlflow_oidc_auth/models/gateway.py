"""Pydantic models for gateway permission APIs."""

from pydantic import BaseModel, Field

from mlflow_oidc_auth.models._base import ResponseModel


class GatewayPermission(BaseModel):
    """Model for creating or updating a gateway permission (endpoint, model definition, or secret)."""

    permission: str = Field(..., description="Permission level for the gateway resource")


class GatewayRegexCreate(BaseModel):
    """Model for creating or updating a regex-based gateway permission."""

    regex: str = Field(..., description="Regex pattern to match gateway resource names")
    priority: int = Field(..., description="Priority of the permission rule")
    permission: str = Field(..., description="Permission level for matching resources")


class GatewayEndpointListItem(ResponseModel):
    """A gateway endpoint the caller may manage (``GET /permissions/gateways/endpoints``)."""

    name: str = Field(..., description="Endpoint name")
    type: str = Field(
        ...,
        deprecated=True,
        description="Endpoint type. Deprecated: MLflow's GatewayEndpoint has no such attribute, so this is always an empty string",
    )
    description: str = Field(
        ...,
        deprecated=True,
        description="Endpoint description. Deprecated: MLflow's GatewayEndpoint has no such attribute, so this is always an empty string",
    )
    route_type: str = Field(
        ...,
        deprecated=True,
        description="Route type. Deprecated: MLflow's GatewayEndpoint has no such attribute, so this is always an empty string",
    )
    auth_type: str = Field(
        ...,
        deprecated=True,
        description="Auth type. Deprecated: MLflow's GatewayEndpoint has no such attribute, so this is always an empty string",
    )


class GatewayModelDefinitionListItem(ResponseModel):
    """A gateway model definition the caller may manage (``GET /permissions/gateways/model-definitions``)."""

    name: str = Field(..., description="Model definition name")
    source: str = Field(..., description="Model provider: MLflow's GatewayModelDefinition has no source field, so this is its provider (empty for none)")


class GatewaySecretListItem(ResponseModel):
    """A gateway secret the caller may manage (``GET /permissions/gateways/secrets``). Never carries the secret value."""

    key: str = Field(..., description="Secret name")
