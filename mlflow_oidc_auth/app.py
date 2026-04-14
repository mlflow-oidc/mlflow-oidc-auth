"""
FastAPI application factory for MLflow OIDC Auth Plugin.

This module provides a FastAPI application factory that can be used as an alternative
to the default MLflow server when OIDC authentication is required.
"""

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI
from mlflow.server import app
from mlflow.version import VERSION
from starlette.middleware.sessions import (
    SessionMiddleware as StarletteSessionMiddleware,
)

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.exceptions import register_exception_handlers
from mlflow_oidc_auth.graphql import install_mlflow_graphql_authorization_middleware
from mlflow_oidc_auth.hooks import after_request_hook, before_request_hook
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.middleware import (
    AuthAwareWSGIMiddleware,
    AuthMiddleware,
    ProxyHeadersMiddleware,
    WorkspaceContextMiddleware,
    add_fastapi_permission_middleware,
)
from mlflow_oidc_auth.oauth import ensure_oidc_client_registered
from mlflow_oidc_auth.routers import get_all_routers

logger = get_logger()

# Global flag to track OIDC initialization status for health checks
_oidc_initialized: bool = False


def is_oidc_ready() -> bool:
    """Check if OIDC client has been initialized at startup.

    Returns:
        True if OIDC was successfully registered during app startup.
    """
    return _oidc_initialized


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI lifespan context manager for startup/shutdown events.

    Ensures OIDC client is registered at startup before the app accepts requests.
    This is critical for multi-replica deployments where any replica may receive
    /callback or /logout requests that require the OIDC client to be registered.
    """
    global _oidc_initialized

    # Startup: Register OIDC client
    logger.info("Starting MLflow OIDC Auth Plugin...")
    if ensure_oidc_client_registered():
        _oidc_initialized = True
        logger.info("OIDC client successfully registered at startup")
    else:
        logger.warning(
            "OIDC client registration failed at startup. "
            "This may indicate missing configuration (OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, OIDC_DISCOVERY_URL). "
            "OIDC authentication will not be available until configuration is corrected."
        )

    yield  # App runs here

    # Shutdown: Cleanup if needed
    logger.info("Shutting down MLflow OIDC Auth Plugin...")


def _seed_default_workspace() -> None:
    """Seed the default workspace in MLflow's workspace store if it doesn't already exist.

    Called at app startup when MLFLOW_ENABLE_WORKSPACES is enabled.
    Uses MLflow's native workspace store API to create the 'default' workspace.
    """
    from mlflow.server.handlers import _get_workspace_store
    from mlflow.store.workspace import Workspace

    DEFAULT_WORKSPACE = "default"

    try:
        ws_store = _get_workspace_store()
        # Check if default workspace already exists
        try:
            ws_store.get_workspace(DEFAULT_WORKSPACE)
            logger.debug(f"Default workspace '{DEFAULT_WORKSPACE}' already exists")
        except Exception:
            # Workspace doesn't exist — create it
            ws_store.create_workspace(
                Workspace(
                    name=DEFAULT_WORKSPACE,
                    description="Default workspace",
                )
            )
            logger.info(f"Default workspace '{DEFAULT_WORKSPACE}' created")
    except Exception as e:
        logger.warning(f"Could not seed default workspace: {e}")


def _include_mlflow_fastapi_routers(oidc_app: FastAPI) -> None:
    """Include MLflow's FastAPI-native routers in our application.

    These routers serve endpoints that are NOT handled by Flask and must be
    registered directly on the FastAPI app.  They are included BEFORE the
    Flask WSGI mount so FastAPI routes take precedence.

    Each router is imported and included individually with graceful fallback
    so the plugin continues to work if a particular MLflow module is missing
    (e.g. older MLflow versions without the assistant or job API).
    """
    # OTel trace ingestion: /v1/traces
    try:
        from mlflow.server.otel_api import otel_router

        oidc_app.include_router(otel_router)
        logger.info("Included MLflow OTel router (/v1/traces)")
    except ImportError:
        logger.debug("mlflow.server.otel_api not available — OTel endpoints disabled")

    # Job API: /ajax-api/3.0/jobs/*
    try:
        from mlflow.server.job_api import job_api_router

        oidc_app.include_router(job_api_router)
        logger.info("Included MLflow Job API router (/ajax-api/3.0/jobs)")
    except ImportError:
        logger.debug("mlflow.server.job_api not available — Job API endpoints disabled")

    # AI Gateway invocations: /gateway/*
    try:
        from mlflow.server.gateway_api import gateway_router

        oidc_app.include_router(gateway_router)
        logger.info("Included MLflow Gateway router (/gateway)")
    except ImportError:
        logger.debug("mlflow.server.gateway_api not available — Gateway endpoints disabled")

    # AI Assistant: /ajax-api/3.0/mlflow/assistant/*
    try:
        from mlflow.server.assistant.api import assistant_router

        oidc_app.include_router(assistant_router)
        logger.info("Included MLflow Assistant router (/ajax-api/3.0/mlflow/assistant)")
    except ImportError:
        logger.debug("mlflow.server.assistant.api not available — Assistant endpoints disabled")


def create_app() -> Any:
    """Create a FastAPI application with OIDC integration.

    The app uses a lifespan context manager to ensure OIDC client registration
    happens at startup, making the app ready for multi-replica deployments.
    """
    oidc_app = FastAPI(
        title="MLflow Tracking Server with OIDC Auth",
        description="MLflow Tracking Server API with OIDC Authentication",
        version=VERSION,
        docs_url="/docs" if config.ENABLE_API_DOCS else None,
        redoc_url="/redoc" if config.ENABLE_API_DOCS else None,
        openapi_url="/openapi.json" if config.ENABLE_API_DOCS else None,
        lifespan=lifespan,
    )
    register_exception_handlers(oidc_app)

    # ---------------------------------------------------------------------------
    # Middleware ordering (Starlette executes LAST-added as OUTERMOST):
    #
    #   Request → Session → WorkspaceContext → Auth → ProxyHeaders
    #             → PermissionMiddleware → route handler
    #
    # PermissionMiddleware MUST be added FIRST (innermost) so it runs AFTER
    # AuthMiddleware has set request.state.username / is_admin.
    # ---------------------------------------------------------------------------
    add_fastapi_permission_middleware(oidc_app)
    oidc_app.add_middleware(ProxyHeadersMiddleware)
    oidc_app.add_middleware(AuthMiddleware)
    oidc_app.add_middleware(WorkspaceContextMiddleware)
    oidc_app.add_middleware(StarletteSessionMiddleware, secret_key=config.SECRET_KEY)

    for router in get_all_routers():
        oidc_app.include_router(router)

    # Add links to MLFlow UI
    if config.EXTEND_MLFLOW_MENU:
        from mlflow_oidc_auth import hack

        app.view_functions["serve"] = hack.index

    # Set Flask app secret key
    app.secret_key = config.SECRET_KEY

    # Register Flask hooks directly with the Flask app
    app.before_request(before_request_hook)
    app.after_request(after_request_hook)

    # Seed default workspace and register workspace routers when workspaces are enabled (WSFND-04)
    if config.MLFLOW_ENABLE_WORKSPACES:
        _seed_default_workspace()
        # Register all workspace routers only when workspaces are enabled
        from mlflow_oidc_auth.routers.workspace_permissions import (
            workspace_permissions_router,
        )
        from mlflow_oidc_auth.routers.workspace_regex_permissions import (
            workspace_regex_permissions_router,
        )

        oidc_app.include_router(workspace_permissions_router)
        oidc_app.include_router(workspace_regex_permissions_router)

    # ---------------------------------------------------------------------------
    # Include MLflow's FastAPI-native routers (GAP-ARCH-01 fix)
    #
    # These routers serve endpoints that bypass Flask entirely:
    #   - otel_router:      /v1/traces — OpenTelemetry trace ingestion
    #   - gateway_router:   /gateway/* — AI Gateway invocations
    #   - assistant_router: /ajax-api/3.0/mlflow/assistant/* — AI assistant
    #   - job_api_router:   /ajax-api/3.0/jobs/* — Job API
    #
    # They MUST be included BEFORE the Flask WSGI mount so FastAPI routes
    # take precedence over the catch-all Flask mount.
    # ---------------------------------------------------------------------------
    _include_mlflow_fastapi_routers(oidc_app)

    # Mount Flask app at root with auth passing middleware
    oidc_app.mount("/", AuthAwareWSGIMiddleware(app))

    logger.info("MLflow Flask app mounted at / with FastAPI auth info passing")
    # Ensure MLflow's `/graphql` route applies our per-field authorization middleware.
    install_mlflow_graphql_authorization_middleware()

    return oidc_app


app = create_app()
