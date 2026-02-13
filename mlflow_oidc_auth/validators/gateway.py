"""Validators for AI Gateway resources (endpoints, secrets, model definitions).

These validators enforce permission checks for gateway CRUD operations
in the Flask before-request hook.
"""

from __future__ import annotations

from flask import request

from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.utils import get_request_param
from mlflow_oidc_auth.utils.permissions import (
    can_manage_gateway_endpoint,
    can_manage_gateway_model_definition,
    can_manage_gateway_secret,
    can_read_gateway_endpoint,
    can_read_gateway_model_definition,
    can_read_gateway_secret,
    can_update_gateway_endpoint,
    can_update_gateway_model_definition,
    can_update_gateway_secret,
)

_logger = get_logger()


# ---------------------------------------------------------------------------
# Gateway Endpoint validators
# ---------------------------------------------------------------------------


def validate_can_read_gateway_endpoint(username: str) -> bool:
    """Validate READ permission on a gateway endpoint.

    ``GetGatewayEndpoint`` provides ``name`` (or ``endpoint_id``).
    We check by name when available, falling back to ID resolution.
    """
    name = _get_gateway_endpoint_name()
    if not name:
        return False
    return can_read_gateway_endpoint(name, username)


def validate_can_update_gateway_endpoint(username: str) -> bool:
    """Validate UPDATE permission on a gateway endpoint.

    The old name is already stashed in ``flask.g`` by
    ``_stash_gateway_context`` (which runs for all users).
    For the permission check we resolve the current endpoint name
    via ``endpoint_id`` since the request ``name`` is the *new* name.
    """
    name = _get_gateway_endpoint_name_for_update()
    if not name:
        return False
    return can_update_gateway_endpoint(name, username)


def validate_can_delete_gateway_endpoint(username: str) -> bool:
    """Validate MANAGE permission for deleting a gateway endpoint.

    The name is already stashed in ``flask.g`` by
    ``_stash_gateway_context`` (which runs for all users).
    """
    name = _get_gateway_endpoint_name()
    if not name:
        return False
    return can_manage_gateway_endpoint(name, username)


def validate_can_manage_gateway_endpoint_validator(username: str) -> bool:
    """Validate MANAGE permission on a gateway endpoint."""
    name = _get_gateway_endpoint_name()
    if not name:
        return False
    return can_manage_gateway_endpoint(name, username)


# ---------------------------------------------------------------------------
# Gateway Secret validators
# ---------------------------------------------------------------------------


def validate_can_read_gateway_secret(username: str) -> bool:
    """Validate READ permission on a gateway secret.

    ``GetGatewaySecretInfo`` provides ``secret_name`` (or ``secret_id``).
    """
    name = _get_gateway_secret_name()
    if not name:
        return False
    return can_read_gateway_secret(name, username)


def validate_can_update_gateway_secret(username: str) -> bool:
    """Validate UPDATE permission on a gateway secret."""
    name = _get_gateway_secret_name()
    if not name:
        return False
    return can_update_gateway_secret(name, username)


def validate_can_delete_gateway_secret(username: str) -> bool:
    """Validate MANAGE permission for deleting a gateway secret.

    The name is already stashed in ``flask.g`` by
    ``_stash_gateway_context`` (which runs for all users).
    """
    name = _get_gateway_secret_name()
    if not name:
        return False
    return can_manage_gateway_secret(name, username)


# ---------------------------------------------------------------------------
# Gateway Model Definition validators
# ---------------------------------------------------------------------------


def validate_can_read_gateway_model_definition(username: str) -> bool:
    """Validate READ permission on a gateway model definition.

    ``GetGatewayModelDefinition`` only provides ``model_definition_id``,
    so we fall back to ID resolution via the tracking store. If
    resolution fails, we allow through and rely on list filtering.
    """
    name = _get_gateway_model_definition_name()
    if not name:
        # ID-only request — cannot resolve name; allow and rely on list filtering
        return True
    return can_read_gateway_model_definition(name, username)


def validate_can_update_gateway_model_definition(username: str) -> bool:
    """Validate UPDATE permission on a gateway model definition."""
    name = _get_gateway_model_definition_name()
    if not name:
        return True
    return can_update_gateway_model_definition(name, username)


def validate_can_delete_gateway_model_definition(username: str) -> bool:
    """Validate MANAGE permission for deleting a gateway model definition.

    The name is already stashed in ``flask.g`` by
    ``_stash_gateway_context`` (which runs for all users).
    """
    name = _get_gateway_model_definition_name()
    if not name:
        return True
    return can_manage_gateway_model_definition(name, username)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_endpoint_name_from_id(endpoint_id: str) -> str | None:
    """Look up a gateway endpoint's name from its ID via the tracking store."""
    try:
        from mlflow.server.handlers import _get_tracking_store

        endpoint = _get_tracking_store().get_gateway_endpoint(endpoint_id=endpoint_id)
        return endpoint.name
    except Exception:
        _logger.debug(f"Could not resolve gateway endpoint name from id '{endpoint_id}'")
        return None


def _resolve_secret_name_from_id(secret_id: str) -> str | None:
    """Look up a gateway secret's name from its ID via the tracking store."""
    try:
        from mlflow.server.handlers import _get_tracking_store

        secret = _get_tracking_store().get_secret_info(secret_id=secret_id)
        return secret.secret_name
    except Exception:
        _logger.debug(f"Could not resolve gateway secret name from id '{secret_id}'")
        return None


def _resolve_model_definition_name_from_id(model_definition_id: str) -> str | None:
    """Look up a gateway model definition's name from its ID via the tracking store."""
    try:
        from mlflow.server.handlers import _get_tracking_store

        model_def = _get_tracking_store().get_gateway_model_definition(model_definition_id=model_definition_id)
        return model_def.name
    except Exception:
        _logger.debug(f"Could not resolve gateway model definition name from id '{model_definition_id}'")
        return None


def _get_gateway_endpoint_name() -> str | None:
    """Extract gateway endpoint name from the request.

    Tries ``name`` first, then falls back to resolving ``endpoint_id``
    via the tracking store.
    """
    try:
        return get_request_param("name")
    except Exception:
        pass
    try:
        endpoint_id = get_request_param("endpoint_id")
        return _resolve_endpoint_name_from_id(endpoint_id)
    except Exception:
        return None


def _get_gateway_endpoint_name_for_update() -> str | None:
    """Extract the *current* gateway endpoint name for update requests.

    Unlike ``_get_gateway_endpoint_name``, this deliberately skips the
    ``name`` request parameter because in ``UpdateGatewayEndpoint`` the
    ``name`` field holds the *new* name.  We resolve the current name
    via ``endpoint_id`` instead.
    """
    try:
        endpoint_id = get_request_param("endpoint_id")
        return _resolve_endpoint_name_from_id(endpoint_id)
    except Exception:
        return None


def _get_gateway_secret_name() -> str | None:
    """Extract gateway secret name from the request.

    Tries ``secret_name`` first, then falls back to resolving ``secret_id``
    via the tracking store.
    """
    try:
        return get_request_param("secret_name")
    except Exception:
        pass
    try:
        secret_id = get_request_param("secret_id")
        return _resolve_secret_name_from_id(secret_id)
    except Exception:
        return None


def _get_gateway_model_definition_name() -> str | None:
    """Extract gateway model definition name from the request.

    Tries ``name`` first, then falls back to resolving ``model_definition_id``
    via the tracking store.
    """
    try:
        return get_request_param("name")
    except Exception:
        pass
    try:
        model_definition_id = get_request_param("model_definition_id")
        return _resolve_model_definition_name_from_id(model_definition_id)
    except Exception:
        return None
