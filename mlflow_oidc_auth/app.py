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
from starlette.middleware.sessions import SessionMiddleware as StarletteSessionMiddleware

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.exceptions import register_exception_handlers
from mlflow_oidc_auth.graphql import install_mlflow_graphql_authorization_middleware
from mlflow_oidc_auth.hooks import after_request_hook, before_request_hook
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.middleware import AuthAwareWSGIMiddleware, AuthMiddleware, ProxyHeadersMiddleware
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


def create_app() -> Any:
    """Create a FastAPI application with OIDC integration.

    The app uses a lifespan context manager to ensure OIDC client registration
    happens at startup, making the app ready for multi-replica deployments.
    """
    oidc_app = FastAPI(
        title="MLflow Tracking Server with OIDC Auth",
        description="MLflow Tracking Server API with OIDC Authentication",
        version=VERSION,
        docs_url="/docs" if getattr(config, "ENABLE_API_DOCS", True) else None,
        redoc_url="/redoc" if getattr(config, "ENABLE_API_DOCS", True) else None,
        openapi_url="/openapi.json" if getattr(config, "ENABLE_API_DOCS", True) else None,
        lifespan=lifespan,
    )
    register_exception_handlers(oidc_app)

    oidc_app.add_middleware(ProxyHeadersMiddleware)
    oidc_app.add_middleware(AuthMiddleware)
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

    # Mount Flask app at root with auth passing middleware
    oidc_app.mount("/", AuthAwareWSGIMiddleware(app))

    logger.info("MLflow Flask app mounted at / with FastAPI auth info passing")
    # Ensure MLflow's `/graphql` route applies our per-field authorization middleware.
    install_mlflow_graphql_authorization_middleware()

    return oidc_app


app = create_app()
