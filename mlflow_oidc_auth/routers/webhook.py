"""
FastAPI webhook router implementation.

This module provides CRUD operations for MLflow webhooks with admin-only access control.
All webhook operations require admin permissions for security purposes.

Based on MLflow webhook documentation: https://mlflow.org/docs/latest/ml/webhooks/

Supported webhook events:
- registered_model.created: Triggered when a new registered model is created
- model_version.created: Triggered when a new model version is created
- model_version_tag.set: Triggered when a tag is set on a model version
- model_version_tag.deleted: Triggered when a tag is deleted from a model version
- model_version_alias.created: Triggered when an alias is created for a model version
- model_version_alias.deleted: Triggered when an alias is deleted from a model version
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from mlflow.entities.webhook import Webhook, WebhookEvent, WebhookStatus
from mlflow.store.db.db_types import DATABASE_ENGINES
from mlflow.tracking._model_registry.registry import ModelRegistryStoreRegistry
from mlflow.webhooks.delivery import test_webhook

from mlflow_oidc_auth.dependencies import check_admin_permission
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import WebhookCreateRequest, WebhookListResponse, WebhookResponse, WebhookTestRequest, WebhookTestResponse, WebhookUpdateRequest

from ._prefix import WEBHOOK_ROUTER_PREFIX

logger = get_logger()


class ModelRegistryStoreRegistryWrapper(ModelRegistryStoreRegistry):
    """
    Wrapper for ModelRegistryStoreRegistry that properly registers database schemes.

    This is needed because the default ModelRegistryStoreRegistry doesn't register
    any database schemes, leading to UnsupportedModelRegistryStoreURIException.
    """

    def __init__(self):
        super().__init__()
        # Register file stores
        self.register("", self._get_file_store)
        self.register("file", self._get_file_store)
        # Register database stores for all supported engines
        for scheme in DATABASE_ENGINES:
            self.register(scheme, self._get_sqlalchemy_store)
        # Register any plugins
        self.register_entrypoints()

    @classmethod
    def _get_file_store(cls, store_uri):
        """Get file-based model registry store."""
        from mlflow.store.model_registry.file_store import FileStore

        return FileStore(store_uri)

    @classmethod
    def _get_sqlalchemy_store(cls, store_uri):
        """Get SQLAlchemy-based model registry store."""
        from mlflow.store.model_registry.sqlalchemy_store import SqlAlchemyStore

        return SqlAlchemyStore(store_uri)


# Initialize model registry store registry with proper database scheme registration
_model_registry_store_registry = ModelRegistryStoreRegistryWrapper()


def _get_model_registry_store():
    """
    Get the model registry store for webhook operations.

    This function retrieves the MLflow model registry store configured for the current
    tracking URI. The store is used for webhook operations that interact with registered
    models and model versions.

    Returns:
        The configured model registry store instance.

    Raises:
        HTTPException: If the model registry store cannot be initialized, typically
            due to database configuration issues or unsupported URI schemes.
    """
    try:
        return _model_registry_store_registry.get_store()
    except Exception as e:
        logger.error(f"Failed to get model registry store: {e}")
        raise HTTPException(status_code=503, detail="Webhook service temporarily unavailable. Ensure MLflow is properly configured with SQL backend.")


# Create the router
webhook_router = APIRouter(
    prefix=WEBHOOK_ROUTER_PREFIX,
    tags=["webhook"],
    responses={
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Resource not found"},
        500: {"description": "Internal server error"},
        503: {"description": "Service unavailable"},
    },
)


def _webhook_to_response(webhook: Webhook) -> WebhookResponse:
    """Convert MLflow Webhook entity to WebhookResponse."""
    return WebhookResponse(
        webhook_id=webhook.webhook_id,
        name=webhook.name,
        url=webhook.url,
        events=[str(event) for event in webhook.events],
        description=webhook.description,
        status=str(webhook.status),
        creation_timestamp=webhook.creation_timestamp,
        last_updated_timestamp=webhook.last_updated_timestamp,
    )


@webhook_router.post(
    "/",
    response_model=WebhookResponse,
    summary="Create a webhook",
    description="Create a new webhook. Only admin users can create webhooks.",
)
def create_webhook(
    webhook_data: WebhookCreateRequest,
    admin_username: str = Depends(check_admin_permission),
) -> WebhookResponse:
    """
    Create a new webhook.

    This endpoint allows administrators to create new webhooks that will be triggered
    on specific MLflow events such as model registration, version creation, etc.

    Args:
        webhook_data: The webhook configuration data including name, URL, events, etc.
        admin_username: The username of the authenticated admin (injected by dependency).

    Returns:
        The created webhook data.

    Raises:
        HTTPException: If creation fails or user lacks admin permissions.
    """
    logger.info(f"Admin {admin_username} creating webhook: {webhook_data.name}")

    store = _get_model_registry_store()

    # Convert event strings to WebhookEvent objects
    webhook_events = []
    for event in webhook_data.events:
        try:
            webhook_events.append(WebhookEvent.from_str(event))  # type: ignore
        except Exception as e:
            logger.error(f"Invalid event type: {event}, error: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid event type: {event}")

    # Convert status string to WebhookStatus enum
    status = WebhookStatus(webhook_data.status) if webhook_data.status else WebhookStatus.ACTIVE

    # Create webhook using MLflow store
    webhook = store.create_webhook(
        name=webhook_data.name,
        url=webhook_data.url,
        events=webhook_events,
        description=webhook_data.description,
        secret=webhook_data.secret,
        status=status,
    )

    logger.info(f"Webhook {webhook.webhook_id} created successfully by {admin_username}")
    return _webhook_to_response(webhook)


@webhook_router.get(
    "/",
    response_model=WebhookListResponse,
    summary="List webhooks",
    description="List all webhooks with pagination support. Only admin users can view webhooks.",
)
def list_webhooks(
    max_results: Optional[int] = Query(None, description="Maximum number of webhooks to return", ge=1, le=1000),
    page_token: Optional[str] = Query(None, description="Token for pagination"),
    admin_username: str = Depends(check_admin_permission),
) -> WebhookListResponse:
    """
    List all webhooks with pagination support.

    This endpoint allows administrators to retrieve a paginated list of all webhooks
    in the system.

    Args:
        max_results: Maximum number of webhooks to return per page.
        page_token: Token for pagination to get the next page of results.
        admin_username: The username of the authenticated admin (injected by dependency).

    Returns:
        A paginated list of webhooks.

    Raises:
        HTTPException: If listing fails or user lacks admin permissions.
    """
    logger.info(f"Admin {admin_username} listing webhooks")

    store = _get_model_registry_store()
    logger.debug(f"Store obtained: {store}")

    # Get webhooks from MLflow store
    webhooks_page = store.list_webhooks(
        max_results=max_results,
        page_token=page_token,
    )

    # Convert to response format
    webhook_responses = [_webhook_to_response(webhook) for webhook in webhooks_page]

    logger.info(f"Retrieved {len(webhook_responses)} webhooks for {admin_username}")
    return WebhookListResponse(
        webhooks=webhook_responses,
        next_page_token=webhooks_page.token,
    )


@webhook_router.get(
    "/{webhook_id}",
    response_model=WebhookResponse,
    summary="Get webhook details",
    description="Get details of a specific webhook by ID. Only admin users can view webhooks.",
)
def get_webhook(
    webhook_id: str = Path(..., description="The webhook ID"),
    admin_username: str = Depends(check_admin_permission),
) -> WebhookResponse:
    """
    Get webhook details by ID.

    This endpoint allows administrators to retrieve details of a specific webhook
    using its unique identifier.

    Args:
        webhook_id: The unique identifier of the webhook.
        admin_username: The username of the authenticated admin (injected by dependency).

    Returns:
        The webhook data.

    Raises:
        HTTPException: If webhook not found or user lacks admin permissions.
    """
    logger.info(f"Admin {admin_username} retrieving webhook: {webhook_id}")

    store = _get_model_registry_store()

    # Get webhook from MLflow store
    webhook = store.get_webhook(webhook_id=webhook_id)

    logger.info(f"Retrieved webhook {webhook_id} for {admin_username}")
    return _webhook_to_response(webhook)


@webhook_router.put(
    "/{webhook_id}",
    response_model=WebhookResponse,
    summary="Update webhook",
    description="Update a webhook's configuration. Only admin users can update webhooks.",
)
def update_webhook(
    webhook_id: str = Path(..., description="The webhook ID"),
    *,
    webhook_data: WebhookUpdateRequest,
    admin_username: str = Depends(check_admin_permission),
) -> WebhookResponse:
    """
    Update a webhook's configuration.

    This endpoint allows administrators to update webhook configuration including
    name, URL, events, description, secret, and status.

    Args:
        webhook_id: The unique identifier of the webhook to update.
        webhook_data: The updated webhook data.
        admin_username: The username of the authenticated admin (injected by dependency).

    Returns:
        The updated webhook data.

    Raises:
        HTTPException: If webhook not found, update fails, or user lacks admin permissions.
    """
    logger.info(f"Admin {admin_username} updating webhook: {webhook_id}")

    store = _get_model_registry_store()

    # Convert event strings to WebhookEvent objects if provided
    webhook_events = None
    if webhook_data.events is not None:
        webhook_events = []
        for event in webhook_data.events:
            try:
                webhook_events.append(WebhookEvent.from_str(event))  # type: ignore
            except Exception as e:
                logger.error(f"Invalid event type: {event}, error: {e}")
                raise HTTPException(status_code=400, detail=f"Invalid event type: {event}")

    # Convert status string to WebhookStatus enum if provided
    status = None
    if webhook_data.status is not None:
        status = WebhookStatus(webhook_data.status)

    # Update webhook using MLflow store
    webhook = store.update_webhook(
        webhook_id=webhook_id,
        name=webhook_data.name,
        description=webhook_data.description,
        url=webhook_data.url,
        events=webhook_events,
        secret=webhook_data.secret,
        status=status,
    )

    logger.info(f"Webhook {webhook_id} updated successfully by {admin_username}")
    return _webhook_to_response(webhook)


@webhook_router.delete(
    "/{webhook_id}",
    summary="Delete webhook",
    description="Delete a webhook. Only admin users can delete webhooks.",
)
def delete_webhook(
    webhook_id: str = Path(..., description="The webhook ID"),
    admin_username: str = Depends(check_admin_permission),
) -> dict:
    """
    Delete a webhook.

    This endpoint allows administrators to delete a webhook permanently.
    Once deleted, the webhook will no longer trigger on events.

    Args:
        webhook_id: The unique identifier of the webhook to delete.
        admin_username: The username of the authenticated admin (injected by dependency).

    Returns:
        Success message confirming deletion.

    Raises:
        HTTPException: If webhook not found, deletion fails, or user lacks admin permissions.
    """
    logger.info(f"Admin {admin_username} deleting webhook: {webhook_id}")

    store = _get_model_registry_store()

    # Delete webhook using MLflow store
    store.delete_webhook(webhook_id=webhook_id)

    logger.info(f"Webhook {webhook_id} deleted successfully by {admin_username}")
    return {"message": f"Webhook {webhook_id} deleted successfully"}


@webhook_router.post(
    "/{webhook_id}/test",
    response_model=WebhookTestResponse,
    summary="Test webhook",
    description="Test a webhook by sending a sample payload. Only admin users can test webhooks.",
)
def test_webhook_endpoint(
    webhook_id: str = Path(..., description="The webhook ID"),
    test_data: Optional[WebhookTestRequest] = None,
    admin_username: str = Depends(check_admin_permission),
) -> WebhookTestResponse:
    """
    Test a webhook by sending a sample payload.

    This endpoint allows administrators to test a webhook by sending sample payloads
    to verify connectivity and response handling. If no event type is specified,
    the first event from the webhook's event list will be used.

    Args:
        webhook_id: The unique identifier of the webhook to test.
        test_data: Optional test configuration (e.g., specific event type).
        admin_username: The username of the authenticated admin (injected by dependency).

    Returns:
        Test result including success status and response details.

    Raises:
        HTTPException: If webhook not found, test fails, or user lacks admin permissions.
    """
    logger.info(f"Admin {admin_username} testing webhook: {webhook_id}")

    store = _get_model_registry_store()

    # Get webhook from store
    webhook = store.get_webhook(webhook_id=webhook_id)

    # Determine event to test with
    event = None
    if test_data and test_data.event_type:
        try:
            event = WebhookEvent.from_str(test_data.event_type)  # type: ignore
        except Exception as e:
            logger.error(f"Invalid event type: {test_data.event_type}, error: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid event type: {test_data.event_type}")

    # Test webhook using MLflow's test function
    test_result = test_webhook(webhook=webhook, event=event)

    logger.info(f"Webhook {webhook_id} test completed for {admin_username}: success={test_result.success}")

    return WebhookTestResponse(
        success=test_result.success,
        response_status=test_result.response_status,
        response_body=test_result.response_body,
        error_message=test_result.error_message,
    )
