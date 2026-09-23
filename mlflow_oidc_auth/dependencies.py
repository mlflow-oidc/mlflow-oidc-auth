"""
FastAPI dependency functions for the MLflow OIDC Auth Plugin.

This module provides dependency functions that can be used with FastAPI's
dependency injection system for common authorization and validation tasks.
"""

from fastapi import Depends, Request, HTTPException, Path

from mlflow_oidc_auth.utils import (
    can_manage_experiment,
    can_manage_registered_model,
    can_manage_scorer,
    get_is_admin,
    get_username,
)
from mlflow_oidc_auth.utils.workspace_cache import get_workspace_permission_cached


async def check_admin_permission(
    request: Request,
) -> str:
    """
    Verify that the current user has administrator privileges.

    This dependency checks if the authenticated user has admin permissions
    and raises an HTTPException if they don't.

    Parameters:
    -----------
    request : Request
        The FastAPI request object containing session information.

    Returns:
    --------
    str
        The username of the authenticated admin user.

    Raises:
    -------
    HTTPException
        If the user is not authenticated or doesn't have admin permissions.
    """
    try:
        username = await get_username(request=request)
        is_admin = await get_is_admin(request=request)
    except Exception:
        # Keep behavior simple for callers: admin-only endpoints always respond
        # with 403 when the user cannot be identified or checked.
        raise HTTPException(
            status_code=403,
            detail="Administrator privileges required for this operation",
        )

    if not is_admin:
        raise HTTPException(
            status_code=403,
            detail="Administrator privileges required for this operation",
        )

    return username


async def check_experiment_manage_permission(
    experiment_id: str = Path(..., description="The experiment ID"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> None:
    """
    Check if the current user can manage the specified experiment.

    This dependency checks if the authenticated user is an admin or has
    manage permissions for the specified experiment.

    Parameters:
    -----------
    experiment_id : str
        The ID of the experiment to check permissions for.
    request : Request
        The FastAPI request object.

    Returns:
    --------
    str
        The username of the authenticated user.

    Raises:
    -------
    HTTPException
        If the user doesn't have management permission for the experiment.
    """
    if not is_admin and not can_manage_experiment(experiment_id, current_username):
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient permissions to manage experiment {experiment_id}",
        )

    return None


async def check_registered_model_manage_permission(
    name: str = Path(..., description="Registered model or prompt name"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> None:
    """
    Check if the current user can manage the specified registered model.

    This dependency checks if the authenticated user is an admin or has
    manage permissions for the specified registered model.

    Parameters:
    -----------
    model_name : str
        The name of the registered model to check permissions for.
    request : Request
        The FastAPI request object.

    Returns:
    --------
    None
    """
    if not is_admin and not can_manage_registered_model(name, current_username):
        raise HTTPException(status_code=403, detail=f"Insufficient permissions to manage {name}")

    return None


async def check_prompt_manage_permission(
    prompt_name: str = Path(..., description="Prompt name"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> None:
    """Check if the current user can manage the specified prompt.

    This mirrors registered model checks because prompts are stored as registered models
    in the system. Users with admin rights or explicit manage permission can proceed.
    """

    if not is_admin and not can_manage_registered_model(prompt_name, current_username):
        raise HTTPException(status_code=403, detail=f"Insufficient permissions to manage {prompt_name}")

    return None


async def check_gateway_endpoint_manage_permission(
    name: str = Path(..., description="Gateway endpoint name"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> None:
    """Check if the current user can manage the specified gateway endpoint.

    This mirrors gateway checks but targets endpoint-scoped permissions.
    """
    from mlflow_oidc_auth.utils.permissions import can_manage_gateway_endpoint

    if not is_admin and not can_manage_gateway_endpoint(name, current_username):
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient permissions to manage endpoint {name}",
        )

    return None


async def check_gateway_secret_manage_permission(
    name: str = Path(..., description="Gateway secret name"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> None:
    """Check if the current user can manage the specified gateway secret.

    This mirrors gateway checks but targets secret-scoped permissions.
    """
    from mlflow_oidc_auth.utils.permissions import can_manage_gateway_secret

    if not is_admin and not can_manage_gateway_secret(name, current_username):
        raise HTTPException(status_code=403, detail=f"Insufficient permissions to manage secret {name}")

    return None


async def check_gateway_model_definition_manage_permission(
    name: str = Path(..., description="Gateway model definition name"),
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> None:
    """Check if the current user can manage the specified gateway model definition.

    This mirrors gateway checks but targets model definition-scoped permissions.
    """
    from mlflow_oidc_auth.utils.permissions import can_manage_gateway_model_definition

    if not is_admin and not can_manage_gateway_model_definition(name, current_username):
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient permissions to manage model definition {name}",
        )

    return None


async def check_scorer_manage_permission(
    request: Request,
    current_username: str = Depends(get_username),
    is_admin: bool = Depends(get_is_admin),
) -> None:
    """Check if the current user can manage the scorer from the incoming request.

    This dependency supports MLflow v3 scorer permission routes:
    - GET: parameters in query string
    - POST/PATCH/DELETE: parameters in JSON body (with query fallback)
    """

    experiment_id = request.query_params.get("experiment_id") or request.path_params.get("experiment_id")
    scorer_name = request.query_params.get("scorer_name") or request.path_params.get("scorer_name")

    if request.method in {"POST", "PATCH", "DELETE"}:
        try:
            body = await request.json()
        except Exception:
            body = None

        if isinstance(body, dict):
            experiment_id = experiment_id or body.get("experiment_id")
            scorer_name = scorer_name or body.get("scorer_name")

    if not experiment_id or not scorer_name:
        raise HTTPException(
            status_code=400,
            detail="Missing required parameters: experiment_id and scorer_name",
        )

    if not is_admin and not can_manage_scorer(str(experiment_id), str(scorer_name), str(current_username)):
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient permissions to manage scorer {scorer_name}",
        )

    return None


async def check_workspace_manage_permission(
    workspace: str = Path(..., description="The workspace name"),
    request: Request = None,
) -> str:
    """Verify global admin OR workspace MANAGE permission (per D-03).

    Used on create/update/delete workspace permission endpoints.

    Returns:
        The username of the authenticated user.
    """
    try:
        username = await get_username(request=request)
        is_admin = await get_is_admin(request=request)
    except Exception:
        raise HTTPException(status_code=403, detail="Authentication required")

    if is_admin:
        return username

    from mlflow_oidc_auth.config import config

    if not config.MLFLOW_ENABLE_WORKSPACES:
        raise HTTPException(status_code=403, detail="Workspaces are not enabled")

    perm = get_workspace_permission_cached(username, workspace)
    if perm is None or not perm.can_manage:
        raise HTTPException(
            status_code=403,
            detail=f"MANAGE permission required on workspace '{workspace}'",
        )

    return username


async def check_workspace_read_permission(
    workspace: str = Path(..., description="The workspace name"),
    request: Request = None,
) -> str:
    """Verify global admin OR at least workspace READ permission.

    Used on list workspace permission endpoints.

    Returns:
        The username of the authenticated user.
    """
    try:
        username = await get_username(request=request)
        is_admin = await get_is_admin(request=request)
    except Exception:
        raise HTTPException(status_code=403, detail="Authentication required")

    if is_admin:
        return username

    from mlflow_oidc_auth.config import config

    if not config.MLFLOW_ENABLE_WORKSPACES:
        raise HTTPException(status_code=403, detail="Workspaces are not enabled")

    perm = get_workspace_permission_cached(username, workspace)
    if perm is None or not perm.can_read:
        raise HTTPException(
            status_code=403,
            detail=f"READ permission required on workspace '{workspace}'",
        )

    return username


# ---------------------------------------------------------------------------------------------
# SCIM (#321)
# ---------------------------------------------------------------------------------------------


class ScimRateLimiter:
    """Token bucket per SCIM token, in process.

    **Multi-replica caveat:** each replica keeps its own buckets, so with N replicas behind a load
    balancer a token may make up to N times the configured rate. That is acceptable for its
    purpose — stopping a runaway directory sync from saturating one process — and is not a
    security boundary. A shared limit belongs at the ingress.
    """

    def __init__(self) -> None:
        import threading

        self._lock = threading.Lock()
        self._buckets: dict = {}

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()

    def allow(self, key, per_minute: int) -> bool:
        """Take one request from ``key``'s bucket. ``per_minute <= 0`` disables the limit."""
        import time

        if per_minute <= 0:
            return True
        now = time.monotonic()
        rate = per_minute / 60.0
        with self._lock:
            tokens, last = self._buckets.get(key, (float(per_minute), now))
            tokens = min(float(per_minute), tokens + (now - last) * rate)
            if tokens < 1.0:
                self._buckets[key] = (tokens, now)
                return False
            self._buckets[key] = (tokens - 1.0, now)
            return True


scim_rate_limiter = ScimRateLimiter()

#: Failed authentications, keyed by client address. Same multi-replica caveat as above; and the
#: address is whatever ``ProxyHeadersMiddleware`` resolved, so with an untrusted
#: ``X-Forwarded-For`` a client can rotate it. It bounds noise and CPU, it is not a lockout.
scim_auth_failure_limiter = ScimRateLimiter()


class _AuthFailureAudit:
    """At most one ``scim.auth_failed`` audit event per client per minute.

    The event carries how many failures the client had in the window that just closed, so the
    count is not lost — only the repetition is.
    """

    WINDOW_SECONDS = 60.0

    def __init__(self) -> None:
        import threading

        self._lock = threading.Lock()
        self._windows: dict = {}

    def reset(self) -> None:
        with self._lock:
            self._windows.clear()

    def record(self, client: str, method: str, path: str) -> None:
        import time

        from mlflow_oidc_auth.audit import emit_audit_event

        now = time.monotonic()
        with self._lock:
            if len(self._windows) > 10_000:
                # Bounded: an attacker rotating addresses costs at most a duplicate line each.
                self._windows.clear()
            started, count = self._windows.get(client, (None, 0))
            if started is not None and now - started < self.WINDOW_SECONDS:
                self._windows[client] = (started, count + 1)
                return
            self._windows[client] = (now, 1)
        emit_audit_event(
            "scim.auth_failed",
            actor="anonymous",
            resource_type="scim",
            resource_id=path,
            detail={"client": client, "method": method, "path": path, "failures_in_previous_window": count},
            status="denied",
        )


scim_auth_failure_audit = _AuthFailureAudit()


async def require_scim_token(request: Request):
    """Authenticate a SCIM request by its dedicated bearer token, and nothing else.

    ``/scim/v2`` is carved out of :class:`~mlflow_oidc_auth.middleware.AuthMiddleware`, so this is
    the *only* authentication those routes see: a browser session, a basic-auth user token or an
    OIDC bearer token does not authenticate here, whoever it belongs to — admins included. A SCIM
    token in turn authenticates nowhere else: it names no user, so the middleware rejects it.

    Returns:
        ScimTokenRecord: The authenticated token, also placed on ``request.state.scim_token``.

    Raises:
        HTTPException: 401 with ``WWW-Authenticate: Bearer`` when the token is missing, unknown,
            revoked or expired; 429 when the token has exhausted its rate budget.
    """
    import asyncio

    from mlflow_oidc_auth.config import config
    from mlflow_oidc_auth.store import store

    header = request.headers.get("authorization", "")
    scheme, _, presented = header.partition(" ")
    record = None
    if scheme.lower() == "bearer" and presented.strip():
        try:
            # Hash verification and a database round trip: off the event loop.
            record = await asyncio.get_running_loop().run_in_executor(None, store.authenticate_scim_token, presented.strip())
        except Exception:
            # Fail closed. Nothing about the failure is returned to the caller.
            record = None
    if record is None:
        client = request.client.host if request.client else "unknown"
        scim_auth_failure_audit.record(client, request.method, request.url.path)
        if not scim_auth_failure_limiter.allow(("auth-failed", client), int(getattr(config, "SCIM_AUTH_FAILURE_LIMIT_PER_MINUTE", 60) or 0)):
            raise HTTPException(status_code=429, detail="Too many failed SCIM authentications", headers={"Retry-After": "60"})
        raise HTTPException(status_code=401, detail="A valid SCIM bearer token is required", headers={"WWW-Authenticate": 'Bearer realm="scim"'})

    request.state.scim_token = record
    if not scim_rate_limiter.allow(record.id, int(getattr(config, "SCIM_RATE_LIMIT_PER_MINUTE", 600) or 0)):
        raise HTTPException(status_code=429, detail="SCIM rate limit exceeded", headers={"Retry-After": "60"})
    return record
