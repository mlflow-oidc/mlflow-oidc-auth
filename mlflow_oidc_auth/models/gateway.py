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
    type: str = Field(..., description="Endpoint type. MLflow's GatewayEndpoint has no such field, so this is always empty today")
    description: str = Field(..., description="Endpoint description. MLflow's GatewayEndpoint has no such field, so this is always empty today")
    route_type: str = Field(..., description="Route type. MLflow's GatewayEndpoint has no such field, so this is always empty today")
    auth_type: str = Field(..., description="Auth type. MLflow's GatewayEndpoint has no such field, so this is always empty today")


class GatewayModelDefinitionListItem(ResponseModel):
    """A gateway model definition the caller may manage (``GET /permissions/gateways/model-definitions``)."""

    name: str = Field(..., description="Model definition name")
    source: str = Field(..., description="Model provider: MLflow's GatewayModelDefinition has no source field, so this is its provider (empty for none)")


class GatewaySecretListItem(ResponseModel):
    """A gateway secret the caller may manage (``GET /permissions/gateways/secrets``). Never carries the secret value."""

    key: str = Field(..., description="Secret name")
