"""Validators for AI Gateway resources (endpoints, secrets, model definitions).

These validators enforce permission checks for gateway CRUD operations
in the Flask before-request hook.
"""

from __future__ import annotations

from flask import request

from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.utils import all_source_values, get_request_param
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

    ``GetGatewayEndpoint`` accepts both ``name`` and ``endpoint_id``, and MLflow
    passes both to the store, so a request may reference two different resources
    (issue #270 cross-field bypass). We require READ on *every* resource named.
    """
    names = _all_gateway_endpoint_names()
    if not names:
        return False
    return all(can_read_gateway_endpoint(name, username) for name in names)


def validate_can_update_gateway_endpoint(username: str) -> bool:
    """Validate UPDATE permission on a gateway endpoint.

    The old name is already stashed in ``flask.g`` by
    ``_stash_gateway_context`` (which runs for all users).
    For the permission check we resolve the current endpoint name
    via ``endpoint_id`` since the request ``name`` is the *new* name.
    """
    names = _get_gateway_endpoint_name_for_update()
    if not names:
        return False
    return all(can_update_gateway_endpoint(name, username) for name in names)


def validate_can_delete_gateway_endpoint(username: str) -> bool:
    """Validate MANAGE permission for deleting a gateway endpoint.

    ``DeleteGatewayEndpoint`` identifies the resource by ``endpoint_id`` only, so
    any ``name`` in the body is ignored by MLflow. We still require MANAGE on every
    resource the request references (issue #270 cross-field bypass).
    """
    names = _all_gateway_endpoint_names()
    if not names:
        return False
    return all(can_manage_gateway_endpoint(name, username) for name in names)


def validate_can_manage_gateway_endpoint_validator(username: str) -> bool:
    """Validate MANAGE permission on a gateway endpoint."""
    names = _all_gateway_endpoint_names()
    if not names:
        return False
    return all(can_manage_gateway_endpoint(name, username) for name in names)


# ---------------------------------------------------------------------------
# Gateway Secret validators
# ---------------------------------------------------------------------------


def validate_can_read_gateway_secret(username: str) -> bool:
    """Validate READ permission on a gateway secret.

    ``GetGatewaySecretInfo`` accepts both ``secret_name`` and ``secret_id``; we
    require READ on every resource referenced (issue #270 cross-field bypass).
    """
    names = _all_gateway_secret_names()
    if not names:
        return False
    return all(can_read_gateway_secret(name, username) for name in names)


def validate_can_update_gateway_secret(username: str) -> bool:
    """Validate UPDATE permission on a gateway secret.

    ``UpdateGatewaySecret`` identifies the resource by ``secret_id`` only, so we
    resolve the current name from the id rather than trusting a request ``secret_name``
    (issue #270 cross-field bypass).
    """
    names = _get_gateway_secret_name_for_update()
    if not names:
        return False
    return all(can_update_gateway_secret(name, username) for name in names)


def validate_can_delete_gateway_secret(username: str) -> bool:
    """Validate MANAGE permission for deleting a gateway secret.

    ``DeleteGatewaySecret`` identifies the resource by ``secret_id`` only; we still
    require MANAGE on every resource the request references (issue #270).
    """
    names = _all_gateway_secret_names()
    if not names:
        return False
    return all(can_manage_gateway_secret(name, username) for name in names)


# ---------------------------------------------------------------------------
# Gateway Model Definition validators
# ---------------------------------------------------------------------------


def validate_can_read_gateway_model_definition(username: str) -> bool:
    """Validate READ permission on a gateway model definition.

    ``GetGatewayModelDefinition`` identifies the resource by ``model_definition_id``,
    so any request ``name`` is ignored by MLflow. We require READ on every resource
    the request references (issue #270 cross-field bypass). Fail-closed on no match.
    """
    names = _all_gateway_model_definition_names()
    if not names:
        _logger.warning("Cannot resolve gateway model definition name — denying access (fail-closed)")
        return False
    return all(can_read_gateway_model_definition(name, username) for name in names)


def validate_can_update_gateway_model_definition(username: str) -> bool:
    """Validate UPDATE permission on a gateway model definition.

    ``UpdateGatewayModelDefinition`` identifies the resource by ``model_definition_id``
    (the ``name`` field carries the *new* name on a rename), so we resolve the current
    name from the id rather than trusting a request ``name`` (issue #270).
    """
    names = _get_gateway_model_definition_name_for_update()
    if not names:
        _logger.warning("Cannot resolve gateway model definition name — denying access (fail-closed)")
        return False
    return all(can_update_gateway_model_definition(name, username) for name in names)


def validate_can_delete_gateway_model_definition(username: str) -> bool:
    """Validate MANAGE permission for deleting a gateway model definition.

    ``DeleteGatewayModelDefinition`` identifies the resource by ``model_definition_id``;
    we require MANAGE on every resource the request references (issue #270).
    """
    names = _all_gateway_model_definition_names()
    if not names:
        _logger.warning("Cannot resolve gateway model definition name — denying access (fail-closed)")
        return False
    return all(can_manage_gateway_model_definition(name, username) for name in names)


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


def _safe_param(name: str) -> str | None:
    """Read a request parameter without raising when it is absent."""
    try:
        value = get_request_param(name)
    except Exception:
        return None
    return value or None


def _safe_params(name: str) -> list:
    """Every distinct value of ``name`` the request carries, MLflow's own first.

    The value from the source MLflow reads comes first; then every other value in any
    request source (issues #285, #288), so a request cannot hide a second resource in
    the query string or the body the check would otherwise skip.
    """
    primary = _safe_param(name)
    values = [primary] if primary else []
    for value in all_source_values(name):
        if str(value) not in {str(v) for v in values}:
            values.append(value)
    return values


def _resolve_all(ids: list, resolve) -> list[str] | None:
    """Resolve every id to a name; ``None`` if any of them cannot be resolved (fail closed)."""
    names: list[str] = []
    for resource_id in ids:
        name = resolve(resource_id)
        if not name:
            return None
        names.append(name)
    return list(dict.fromkeys(names))


def _all_gateway_endpoint_names() -> list[str]:
    """Every endpoint name a read/delete request references.

    ``GetGatewayEndpoint``/``DeleteGatewayEndpoint`` may carry ``name`` and/or
    ``endpoint_id``, and MLflow resolves whichever the store prefers.  To close the
    cross-field bypass (issue #270) we return *all* distinct resources referenced —
    the ``name`` as given and the name resolved from ``endpoint_id`` — so the caller
    must be authorized on every one.
    """
    names: list[str] = list(_safe_params("name"))
    ids = _safe_params("endpoint_id")
    if ids:
        resolved = _resolve_all(ids, _resolve_endpoint_name_from_id)
        if resolved is None:
            # An id we cannot resolve is a resource we cannot authorize: deny rather
            # than decide on the rest of the request alone.
            return []
        names.extend(resolved)
    # De-duplicate while preserving order (a legit request naming one resource two ways).
    return list(dict.fromkeys(names))


def _get_gateway_endpoint_name_for_update() -> list[str] | None:
    """Resolve the *current* endpoint name(s) for update requests, or None (deny).

    ``UpdateGatewayEndpoint`` identifies the resource by ``endpoint_id`` (the ``name``
    field holds the *new* name on a rename), so we resolve the current name via the id.
    """
    ids = _safe_params("endpoint_id")
    if not ids:
        return None
    return _resolve_all(ids, _resolve_endpoint_name_from_id)


def _all_gateway_secret_names() -> list[str]:
    """Every secret name a read/delete request references (see ``_all_gateway_endpoint_names``)."""
    names: list[str] = list(_safe_params("secret_name"))
    ids = _safe_params("secret_id")
    if ids:
        resolved = _resolve_all(ids, _resolve_secret_name_from_id)
        if resolved is None:
            # An id we cannot resolve is a resource we cannot authorize: deny rather
            # than decide on the rest of the request alone.
            return []
        names.extend(resolved)
    return list(dict.fromkeys(names))


def _get_gateway_secret_name_for_update() -> list[str] | None:
    """Resolve the current secret name(s) for update requests, or None (deny).

    ``UpdateGatewaySecret`` identifies the resource by ``secret_id`` only, so we resolve
    the current name via the id rather than trusting a request ``secret_name``.
    """
    ids = _safe_params("secret_id")
    if not ids:
        return None
    return _resolve_all(ids, _resolve_secret_name_from_id)


def _all_gateway_model_definition_names() -> list[str]:
    """Every model-definition name a read/delete request references (see ``_all_gateway_endpoint_names``)."""
    names: list[str] = list(_safe_params("name"))
    ids = _safe_params("model_definition_id")
    if ids:
        resolved = _resolve_all(ids, _resolve_model_definition_name_from_id)
        if resolved is None:
            # An id we cannot resolve is a resource we cannot authorize: deny rather
            # than decide on the rest of the request alone.
            return []
        names.extend(resolved)
    return list(dict.fromkeys(names))


def _get_gateway_model_definition_name_for_update() -> list[str] | None:
    """Resolve the current model-definition name(s) for update requests, or None (deny).

    ``UpdateGatewayModelDefinition`` identifies the resource by ``model_definition_id``
    (the ``name`` field holds the *new* name on a rename), so we resolve the current
    name via the id rather than trusting a request ``name``.
    """
    ids = _safe_params("model_definition_id")
    if not ids:
        return None
    return _resolve_all(ids, _resolve_model_definition_name_from_id)
