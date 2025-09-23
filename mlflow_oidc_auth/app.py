"""
FastAPI application factory for MLflow OIDC Auth Plugin.

This module provides a FastAPI application factory that can be used as an alternative
to the default MLflow server when OIDC authentication is required.
"""

from typing import Any

from fastapi import FastAPI
from mlflow.server import app
from mlflow.version import VERSION
from starlette.middleware.sessions import SessionMiddleware as StarletteSessionMiddleware

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.exceptions import register_exception_handlers
from mlflow_oidc_auth.hooks import after_request_hook, before_request_hook
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.middleware import AuthAwareWSGIMiddleware, AuthMiddleware
from mlflow_oidc_auth.routers import get_all_routers

logger = get_logger()


def create_app() -> Any:
    """
    Create a FastAPI application with OIDC integration.
    """
    oidc_app = FastAPI(
        title="MLflow Tracking Server with OIDC Auth",
        description="MLflow Tracking Server API with OIDC Authentication",
        version=VERSION,
        docs_url="/docs" if getattr(config, "ENABLE_API_DOCS", True) else None,
        redoc_url="/redoc" if getattr(config, "ENABLE_API_DOCS", True) else None,
        openapi_url="/openapi.json" if getattr(config, "ENABLE_API_DOCS", True) else None,
    )
    register_exception_handlers(oidc_app)
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
    return oidc_app


app = create_app()
