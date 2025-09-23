from pydantic import BaseModel, Field
from typing import List, Optional
from pydantic import Field, field_validator

# Valid webhook statuses
VALID_WEBHOOK_STATUSES = ["ACTIVE", "DISABLED"]

# Valid webhook event types based on MLflow documentation
VALID_WEBHOOK_EVENTS = [
    "registered_model.created",
    "model_version.created",
    "model_version_tag.set",
    "model_version_tag.deleted",
    "model_version_alias.created",
    "model_version_alias.deleted",
]


# Pydantic models for request/response bodies
class WebhookCreateRequest(BaseModel):
    """Request model for creating a webhook."""

    name: str = Field(..., description="Name of the webhook", min_length=1, max_length=256)
    url: str = Field(..., description="URL endpoint for the webhook")
    events: List[str] = Field(..., description="List of event types to trigger the webhook")
    description: Optional[str] = Field(None, description="Description of the webhook", max_length=500)
    secret: Optional[str] = Field(None, description="Secret token for HMAC signature verification")
    status: Optional[str] = Field("ACTIVE", description="Initial status of the webhook")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator("events")
    @classmethod
    def validate_events(cls, v):
        if not v:
            raise ValueError("At least one event must be specified")
        invalid_events = [event for event in v if event not in VALID_WEBHOOK_EVENTS]
        if invalid_events:
            raise ValueError(f"Invalid event types: {invalid_events}. Valid events: {VALID_WEBHOOK_EVENTS}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v is not None and v not in VALID_WEBHOOK_STATUSES:
            raise ValueError(f"Invalid status: {v}. Valid statuses: {VALID_WEBHOOK_STATUSES}")
        return v


class WebhookUpdateRequest(BaseModel):
    """Request model for updating a webhook."""

    name: Optional[str] = Field(None, description="New name for the webhook", min_length=1, max_length=256)
    url: Optional[str] = Field(None, description="New URL endpoint for the webhook")
    events: Optional[List[str]] = Field(None, description="New list of event types")
    description: Optional[str] = Field(None, description="New description", max_length=500)
    secret: Optional[str] = Field(None, description="New secret token for HMAC signature verification")
    status: Optional[str] = Field(None, description="New status")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        if v is not None and not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator("events")
    @classmethod
    def validate_events(cls, v):
        if v is not None:
            if not v:
                raise ValueError("At least one event must be specified")
            invalid_events = [event for event in v if event not in VALID_WEBHOOK_EVENTS]
            if invalid_events:
                raise ValueError(f"Invalid event types: {invalid_events}. Valid events: {VALID_WEBHOOK_EVENTS}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v is not None and v not in VALID_WEBHOOK_STATUSES:
            raise ValueError(f"Invalid status: {v}. Valid statuses: {VALID_WEBHOOK_STATUSES}")
        return v


class WebhookTestRequest(BaseModel):
    """Request model for testing a webhook."""

    event_type: Optional[str] = Field(None, description="Specific event type to test with")

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v):
        if v is not None and v not in VALID_WEBHOOK_EVENTS:
            raise ValueError(f"Invalid event type: {v}. Valid events: {VALID_WEBHOOK_EVENTS}")
        return v


class WebhookResponse(BaseModel):
    """Response model for webhook operations."""

    webhook_id: str = Field(..., description="Webhook ID")
    name: str = Field(..., description="Webhook name")
    url: str = Field(..., description="Webhook URL")
    events: List[str] = Field(..., description="List of event types")
    description: Optional[str] = Field(None, description="Webhook description")
    status: str = Field(..., description="Webhook status")
    creation_timestamp: int = Field(..., description="Creation timestamp in milliseconds")
    last_updated_timestamp: int = Field(..., description="Last updated timestamp in milliseconds")


class WebhookListResponse(BaseModel):
    """Response model for listing webhooks."""

    webhooks: List[WebhookResponse] = Field(..., description="List of webhooks")
    next_page_token: Optional[str] = Field(None, description="Token for next page")


class WebhookTestResponse(BaseModel):
    """Response model for webhook test results."""

    success: bool = Field(..., description="Whether the test succeeded")
    response_status: Optional[int] = Field(None, description="HTTP response status code")
    response_body: Optional[str] = Field(None, description="Response body")
    error_message: Optional[str] = Field(None, description="Error message if test failed")
