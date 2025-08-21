"""
FastAPI application factory for MLflow OIDC Auth Plugin.

This module provides a FastAPI application factory that can be used as an alternative
to the default MLflow server when OIDC authentication is required.
"""

from typing import Any

from mlflow_oidc_auth.logger import get_logger

logger = get_logger()


def create_app() -> Any:
    """
    Create a FastAPI application with OIDC integration.

    This factory function creates a FastAPI app that wraps the Flask app
    (which already has OIDC integration) and adds FastAPI-specific features.

    Returns:
        FastAPI application instance with OIDC integration
    """
    try:
        # CRITICAL: Import the OIDC-modified Flask app first
        # This ensures all OIDC routes, hooks, and middleware are applied
        from mlflow_oidc_auth.app import app as flask_app_with_oidc

        logger.info("OIDC Flask app imported and configured")

        # Import FastAPI components
        from fastapi import FastAPI
        from fastapi.middleware.wsgi import WSGIMiddleware
        from mlflow.version import VERSION

        # Create FastAPI app with metadata
        fastapi_app = FastAPI(
            title="MLflow Tracking Server with OIDC Auth",
            description="MLflow Tracking Server API with OIDC Authentication",
            version=VERSION,
            docs_url=None,
            redoc_url=None,
            openapi_url=None,
            # Enable docs for FastAPI-specific endpoints
            # docs_url="/docs",
            # redoc_url="/redoc",
            # openapi_url="/openapi.json",
        )

        # Add OIDC-specific FastAPI endpoints before mounting Flask app
        # setup_oidc_fastapi_routes(fastapi_app)

        # Mount the OIDC-enhanced Flask application at the root path
        fastapi_app.mount("/", WSGIMiddleware(flask_app_with_oidc))

        logger.info("Successfully created FastAPI app with OIDC integration")
        logger.info("OIDC routes, authentication, and UI should now be available")

        return fastapi_app

    except ImportError as e:
        logger.error(f"Failed to import FastAPI components: {e}")
        logger.info("Falling back to OIDC Flask app")
        from mlflow_oidc_auth.app import app as flask_app

        return flask_app

    except Exception as e:
        logger.error(f"Failed to create FastAPI app, falling back to Flask: {e}")
        from mlflow_oidc_auth.app import app as flask_app

        return flask_app


app = create_app()

# def setup_oidc_fastapi_routes(fastapi_app: Any) -> None:
#     """
#     Set up OIDC-specific FastAPI routes.

#     These routes provide FastAPI-native endpoints for OIDC functionality
#     that complement the Flask routes served via WSGI.

#     Args:
#         fastapi_app: FastAPI application instance
#     """
#     try:
#         from mlflow_oidc_auth.config import config

#         @fastapi_app.get("/api/oidc/health")
#         async def oidc_health():
#             """Health check endpoint for OIDC functionality."""
#             return {
#                 "status": "healthy",
#                 "plugin": "mlflow-oidc-auth",
#                 "provider": config.OIDC_PROVIDER_DISPLAY_NAME,
#                 "authentication": "enabled",
#                 "server_type": "fastapi"
#             }

#         @fastapi_app.get("/api/oidc/status")
#         async def oidc_status():
#             """Detailed status endpoint for OIDC functionality."""
#             return {
#                 "oidc_configured": bool(config.OIDC_DISCOVERY_URL),
#                 "provider_name": config.OIDC_PROVIDER_DISPLAY_NAME,
#                 "groups_enabled": bool(config.OIDC_GROUP_NAME),
#                 "admin_group": config.OIDC_ADMIN_GROUP_NAME,
#                 "menu_extension": config.EXTEND_MLFLOW_MENU,
#                 "ui_available": True,
#                 "routes_mounted": True
#             }

#         @fastapi_app.get("/api/oidc/info")
#         async def oidc_info():
#             """OIDC plugin information endpoint."""
#             return {
#                 "name": "mlflow-oidc-auth",
#                 "version": "5.0.0",
#                 "fastapi_integration": True,
#                 "flask_routes_available": True,
#                 "endpoints": {
#                     "login": "/login",
#                     "logout": "/logout",
#                     "callback": "/callback",
#                     "ui": "/oidc/ui/",
#                     "health": "/api/oidc/health",
#                     "status": "/api/oidc/status"
#                 }
#             }

#         logger.info("OIDC FastAPI routes configured successfully")

#     except Exception as e:
#         logger.error(f"Failed to setup OIDC FastAPI routes: {e}")
