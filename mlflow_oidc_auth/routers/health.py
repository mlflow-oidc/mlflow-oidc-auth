"""Health check endpoints for Kubernetes probes and monitoring.

This module provides health check endpoints suitable for Kubernetes liveness,
readiness, and startup probes in multi-replica deployments.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from mlflow_oidc_auth.oauth import is_oidc_configured
from mlflow_oidc_auth.store import store

from ._prefix import HEALTH_CHECK_ROUTER_PREFIX

health_check_router = APIRouter(
    prefix=HEALTH_CHECK_ROUTER_PREFIX,
    tags=["health"],
    responses={404: {"description": "Not found"}},
)


@health_check_router.get("")
async def health_check_root() -> JSONResponse:
    """Health check endpoint root.

    Many deployment environments probe `/health` by default. We serve it here
    to avoid falling through to the mounted MLflow WSGI app.

    Returns:
        JSON response with basic status.
    """
    return JSONResponse(content={"status": "ok"})


@health_check_router.get("/ready")
async def health_check_ready() -> JSONResponse:
    """Readiness probe endpoint for Kubernetes.

    Verifies that the application is ready to accept traffic by checking:
    - OIDC client is properly configured and registered
    - Database connection is healthy

    In multi-replica deployments, Kubernetes uses this to determine if a pod
    should receive traffic. A pod that fails readiness will be removed from
    the service load balancer until it passes.

    Returns:
        200 with status if ready, 503 if not ready.
    """
    checks = {
        "oidc": False,
        "database": False,
    }
    all_ready = True

    # Check OIDC client registration
    try:
        checks["oidc"] = is_oidc_configured()
        if not checks["oidc"]:
            all_ready = False
    except Exception:
        all_ready = False

    # Check database connectivity
    try:
        checks["database"] = store.ping()
        if not checks["database"]:
            all_ready = False
    except Exception:
        checks["database"] = False
        all_ready = False

    status_code = 200 if all_ready else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_ready else "not_ready",
            "checks": checks,
        },
    )


@health_check_router.get("/live")
async def health_check_live() -> JSONResponse:
    """Liveness probe endpoint for Kubernetes.

    Verifies that the application process is running and not deadlocked.
    This is a lightweight check that should always pass if the app is responsive.

    In multi-replica deployments, Kubernetes uses this to determine if a pod
    needs to be restarted. A pod that fails liveness will be killed and restarted.

    Returns:
        200 with live status. Should never fail unless the process is hung.
    """
    return JSONResponse(content={"status": "live"})


@health_check_router.get("/startup")
async def health_check_startup() -> JSONResponse:
    """Startup probe endpoint for Kubernetes.

    Verifies that the application has completed its initialization.
    This checks if the OIDC client was successfully registered during startup.

    In multi-replica deployments, Kubernetes uses this to determine when a pod
    has finished starting up. Until startup succeeds, liveness and readiness
    probes are not checked.

    Returns:
        200 if startup complete, 503 if still initializing or failed.
    """
    from mlflow_oidc_auth.app import is_oidc_ready

    oidc_ready = is_oidc_ready()

    if oidc_ready:
        return JSONResponse(content={"status": "started", "oidc_initialized": True})
    else:
        # OIDC not initialized - might be missing config or startup in progress
        # Return 503 so Kubernetes knows startup is not complete
        return JSONResponse(
            status_code=503,
            content={
                "status": "initializing",
                "oidc_initialized": False,
                "message": "OIDC client not yet initialized. Check OIDC configuration.",
            },
        )
